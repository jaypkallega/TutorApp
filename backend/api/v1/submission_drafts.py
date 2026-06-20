"""
Submission Drafts API — per-question answer saving.

Flow:
  1. Child opens assignment → POST /draft/start  → get/create draft
  2. Child answers Q1 → PUT /draft/{id}/text or /canvas or /photo
  3. Child answers Q2, Q3... (each saved immediately to server)
  4. Child taps Submit Test → POST /draft/{id}/submit → evaluation runs
  5. Navigate to results page
"""

import json
import base64
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import get_db
from backend.deps import require_child
from backend.models.user import User
from backend.models.submission_draft import SubmissionDraft
from backend.models.assignment import Assignment, AssignmentQuestion
from backend.models.exercise import Exercise
from backend.config import SUBMISSIONS_DIR

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_answers(draft: SubmissionDraft) -> dict:
    try:
        return json.loads(draft.answers or "{}")
    except Exception:
        return {}


def _save_answers(draft: SubmissionDraft, answers: dict, db: Session):
    draft.answers = json.dumps(answers)
    draft.updated_at = datetime.utcnow()
    db.commit()


def _get_exercise_order(assignment_id: int, db: Session) -> list[dict]:
    """Return exercises in assignment order with their IDs."""
    qs = (
        db.query(AssignmentQuestion)
        .filter(AssignmentQuestion.assignment_id == assignment_id)
        .order_by(AssignmentQuestion.ordering)
        .all()
    )
    result = []
    for q in qs:
        ex = db.query(Exercise).filter(Exercise.id == q.exercise_id).first()
        if ex:
            result.append({
                "id": ex.id,
                "prompt": ex.prompt,
                "expected_answer": ex.expected_answer,
                "expected_method": ex.expected_method,
                "structured_answer": ex.structured_answer,
            })
    return result


def _draft_summary(draft: SubmissionDraft, db: Session) -> dict:
    answers = _load_answers(draft)
    exercises = _get_exercise_order(draft.assignment_id, db)
    saved_count = len(answers)
    return {
        "draft_id": draft.id,
        "assignment_id": draft.assignment_id,
        "status": draft.status,
        "total_questions": len(exercises),
        "saved_count": saved_count,
        "answers": {
            str(ex_id): {
                "mode": ans.get("mode"),
                "saved_at": ans.get("saved_at"),
                "text_preview": (ans.get("text") or "")[:80] if ans.get("mode") == "text" else None,
                "has_image": bool(ans.get("image_path")),
                "hints_used": ans.get("hints_used", 0),
            }
            for ex_id, ans in answers.items()
        },
        "exercise_order": [e["id"] for e in exercises],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class StartDraftRequest(BaseModel):
    assignment_id: int


@router.post("/start")
def start_draft(
    req: StartDraftRequest,
    current_user: User = Depends(require_child),
    db: Session = Depends(get_db),
):
    """Get existing in-progress draft or create a new one."""
    assignment = db.query(Assignment).filter(Assignment.id == req.assignment_id).first()
    if not assignment:
        raise HTTPException(404, "Assignment not found")

    # Check for existing in-progress draft
    existing = db.query(SubmissionDraft).filter(
        SubmissionDraft.assignment_id == req.assignment_id,
        SubmissionDraft.child_id == current_user.id,
        SubmissionDraft.status == "in_progress",
    ).first()

    if existing:
        return _draft_summary(existing, db)

    # Create new draft
    draft = SubmissionDraft(
        assignment_id=req.assignment_id,
        child_id=current_user.id,
        answers="{}",
        status="in_progress",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _draft_summary(draft, db)


@router.get("/{draft_id}")
def get_draft(
    draft_id: int,
    current_user: User = Depends(require_child),
    db: Session = Depends(get_db),
):
    draft = db.query(SubmissionDraft).filter(
        SubmissionDraft.id == draft_id,
        SubmissionDraft.child_id == current_user.id,
    ).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    return _draft_summary(draft, db)


# ---------------------------------------------------------------------------
# Hint endpoint
# ---------------------------------------------------------------------------

class HintRequest(BaseModel):
    exercise_id: int
    current_answer: str = ""


MAX_HINTS_PER_QUESTION = 3


@router.post("/{draft_id}/hint")
def get_hint(
    draft_id: int,
    req: HintRequest,
    current_user: User = Depends(require_child),
    db: Session = Depends(get_db),
):
    """
    Return a Socratic hint for one question (max 3 per question).
    Hint count is stored in the draft answers JSON and persists across page refreshes.
    """
    from backend.services.llm_service import generate_hint
    from backend.models.exercise import Exercise

    draft = db.query(SubmissionDraft).filter(
        SubmissionDraft.id == draft_id,
        SubmissionDraft.child_id == current_user.id,
        SubmissionDraft.status == "in_progress",
    ).first()
    if not draft:
        raise HTTPException(404, "Draft not found or already submitted")

    # Verify exercise belongs to this assignment
    from backend.models.assignment import AssignmentQuestion
    aq = db.query(AssignmentQuestion).filter(
        AssignmentQuestion.assignment_id == draft.assignment_id,
        AssignmentQuestion.exercise_id == req.exercise_id,
    ).first()
    if not aq:
        raise HTTPException(404, "Exercise not part of this assignment")

    exercise = db.query(Exercise).filter(Exercise.id == req.exercise_id).first()
    if not exercise:
        raise HTTPException(404, "Exercise not found")

    # Load hint count for this question
    answers = _load_answers(draft)
    ex_key = str(req.exercise_id)
    ex_entry = answers.get(ex_key, {})
    hints_used = ex_entry.get("hints_used", 0)

    if hints_used >= MAX_HINTS_PER_QUESTION:
        raise HTTPException(
            429,
            f"You've used all {MAX_HINTS_PER_QUESTION} hints for this question."
        )

    hint_number = hints_used + 1
    hint_text = generate_hint(
        db=db,
        question_prompt=exercise.prompt,
        expected_answer=exercise.expected_answer or "",
        hint_number=hint_number,
        current_answer=req.current_answer,
    )

    # Persist updated hint count (create entry if not yet answered)
    ex_entry["hints_used"] = hint_number
    if "mode" not in ex_entry:
        # Preserve existing answer data if present, just add hints_used
        pass
    answers[ex_key] = ex_entry
    _save_answers(draft, answers, db)

    return {
        "hint": hint_text,
        "hints_used": hint_number,
        "hints_remaining": MAX_HINTS_PER_QUESTION - hint_number,
    }


@router.put("/{draft_id}/text")
def save_text_answer(
    draft_id: int,
    exercise_id: int = Form(...),
    text: str = Form(...),
    current_user: User = Depends(require_child),
    db: Session = Depends(get_db),
):
    """Save a typed text answer for one question."""
    draft = db.query(SubmissionDraft).filter(
        SubmissionDraft.id == draft_id,
        SubmissionDraft.child_id == current_user.id,
        SubmissionDraft.status == "in_progress",
    ).first()
    if not draft:
        raise HTTPException(404, "Draft not found or already submitted")

    answers = _load_answers(draft)
    answers[str(exercise_id)] = {
        "mode": "text",
        "text": text,
        "saved_at": datetime.utcnow().isoformat(),
    }
    _save_answers(draft, answers, db)
    return {"exercise_id": exercise_id, "mode": "text", "saved": True}


@router.put("/{draft_id}/canvas")
def save_canvas_answer(
    draft_id: int,
    exercise_id: int = Form(...),
    canvas_image: UploadFile = File(...),  # PNG blob from canvas.toBlob()
    current_user: User = Depends(require_child),
    db: Session = Depends(get_db),
):
    """Save a canvas drawing as PNG for one question."""
    draft = db.query(SubmissionDraft).filter(
        SubmissionDraft.id == draft_id,
        SubmissionDraft.child_id == current_user.id,
        SubmissionDraft.status == "in_progress",
    ).first()
    if not draft:
        raise HTTPException(404, "Draft not found or already submitted")

    import asyncio

    async def _read():
        return await canvas_image.read()

    content = asyncio.get_event_loop().run_until_complete(_read()) if False else None
    # Synchronous read via direct call
    import inspect
    content = canvas_image.file.read()

    img_path = SUBMISSIONS_DIR / f"draft_{draft_id}_q{exercise_id}.png"
    with open(img_path, "wb") as f:
        f.write(content)

    answers = _load_answers(draft)
    answers[str(exercise_id)] = {
        "mode": "canvas",
        "image_path": str(img_path),
        "saved_at": datetime.utcnow().isoformat(),
    }
    _save_answers(draft, answers, db)
    return {"exercise_id": exercise_id, "mode": "canvas", "saved": True}


@router.put("/{draft_id}/photo")
async def save_photo_answer(
    draft_id: int,
    exercise_id: int = Form(...),
    photo: UploadFile = File(...),
    current_user: User = Depends(require_child),
    db: Session = Depends(get_db),
):
    """Save a photo upload for one question."""
    draft = db.query(SubmissionDraft).filter(
        SubmissionDraft.id == draft_id,
        SubmissionDraft.child_id == current_user.id,
        SubmissionDraft.status == "in_progress",
    ).first()
    if not draft:
        raise HTTPException(404, "Draft not found or already submitted")

    content = await photo.read()
    ext = Path(photo.filename).suffix.lower() or ".jpg"
    img_path = SUBMISSIONS_DIR / f"draft_{draft_id}_q{exercise_id}_photo{ext}"
    with open(img_path, "wb") as f:
        f.write(content)

    answers = _load_answers(draft)
    answers[str(exercise_id)] = {
        "mode": "photo",
        "image_path": str(img_path),
        "saved_at": datetime.utcnow().isoformat(),
    }
    _save_answers(draft, answers, db)
    return {"exercise_id": exercise_id, "mode": "photo", "saved": True}


@router.post("/{draft_id}/submit")
def submit_draft(
    draft_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_child),
    db: Session = Depends(get_db),
):
    """
    Finalise the draft — compile all answers and trigger evaluation.
    Returns submission_id to poll for results.
    """
    from backend.models.submission import Submission
    from backend.processing.answer_analyzer import process_submission

    draft = db.query(SubmissionDraft).filter(
        SubmissionDraft.id == draft_id,
        SubmissionDraft.child_id == current_user.id,
        SubmissionDraft.status == "in_progress",
    ).first()
    if not draft:
        raise HTTPException(404, "Draft not found or already submitted")

    assignment = db.query(Assignment).filter(Assignment.id == draft.assignment_id).first()
    if not assignment:
        raise HTTPException(404, "Assignment not found")

    exercises = _get_exercise_order(draft.assignment_id, db)
    answers = _load_answers(draft)

    if not answers:
        raise HTTPException(400, "No answers saved yet. Answer at least one question before submitting.")

    # Build ordered text answers — OCR canvas/photo answers
    from backend.services.ocr_service import extract_text_from_image, get_ocr_mode
    ocr_mode = get_ocr_mode(db)

    per_question_texts = []
    input_modes_used = set()

    for ex in exercises:
        ex_id = str(ex["id"])
        ans = answers.get(ex_id)
        if not ans:
            per_question_texts.append("")
            continue

        mode = ans.get("mode", "text")
        input_modes_used.add(mode)

        if mode == "text":
            per_question_texts.append(ans.get("text", ""))
        elif mode in ("canvas", "photo") and ans.get("image_path"):
            try:
                text = extract_text_from_image(ans["image_path"], db=db, mode=ocr_mode)
                per_question_texts.append(text or "")
            except Exception as e:
                logger.warning(f"OCR failed for {ans['image_path']}: {e}")
                per_question_texts.append("")
        else:
            per_question_texts.append("")

    # Determine primary input_mode for the submission record
    if "canvas" in input_modes_used:
        primary_mode = "canvas"
    elif "photo" in input_modes_used:
        primary_mode = "image_upload"
    else:
        primary_mode = "text"

    # Count previous attempts
    prev_count = db.query(Submission).filter(
        Submission.assignment_id == draft.assignment_id,
        Submission.child_id == current_user.id,
    ).count()

    submission = Submission(
        assignment_id=draft.assignment_id,
        child_id=current_user.id,
        attempt_number=prev_count + 1,
        input_mode=primary_mode,
        text_answer=json.dumps(per_question_texts),
        processing_status="pending",
    )
    db.add(submission)

    # Mark draft as submitted
    draft.status = "submitted"
    db.commit()
    db.refresh(submission)

    # Trigger evaluation (pass raw answers so hints_used flows into per_question results)
    background_tasks.add_task(
        process_submission, db, submission.id, exercises, assignment.show_wrong_reasons, answers
    )

    return {"submission_id": submission.id, "status": "processing"}
