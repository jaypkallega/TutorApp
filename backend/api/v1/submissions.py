import json
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form
from sqlalchemy.orm import Session
from typing import Optional, List

from backend.database import get_db
from backend.deps import require_child, get_current_user
from backend.models.user import User
from backend.models.submission import Submission
from backend.models.assignment import Assignment, AssignmentQuestion
from backend.models.exercise import Exercise
from backend.config import SUBMISSIONS_DIR

router = APIRouter()


def _get_assignment_exercises(assignment_id: int, db: Session) -> list[dict]:
    qs = (
        db.query(AssignmentQuestion)
        .filter(AssignmentQuestion.assignment_id == assignment_id)
        .order_by(AssignmentQuestion.ordering)
        .all()
    )
    exercises = []
    for q in qs:
        ex = db.query(Exercise).filter(Exercise.id == q.exercise_id).first()
        if ex:
            exercises.append({
                "id": ex.id,
                "prompt": ex.prompt,
                "expected_answer": ex.expected_answer,
                "expected_method": ex.expected_method,
            })
    return exercises


@router.post("/text")
def submit_text(
    assignment_id: int = Form(...),
    answers: str = Form(...),  # JSON array of strings
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(require_child),
    db: Session = Depends(get_db),
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(404, "Assignment not found")

    prev = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.child_id == current_user.id,
    ).count()

    submission = Submission(
        assignment_id=assignment_id,
        child_id=current_user.id,
        attempt_number=prev + 1,
        input_mode="text",
        text_answer=answers,
        processing_status="pending",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    exercises = _get_assignment_exercises(assignment_id, db)
    from backend.processing.answer_analyzer import process_submission
    background_tasks.add_task(
        process_submission, db, submission.id, exercises, assignment.show_wrong_reasons
    )
    return {"submission_id": submission.id, "status": "processing"}


@router.post("/image")
async def submit_image(
    assignment_id: int = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    file: UploadFile = File(...),
    current_user: User = Depends(require_child),
    db: Session = Depends(get_db),
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(404, "Assignment not found")

    prev = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.child_id == current_user.id,
    ).count()

    ext = Path(file.filename).suffix.lower()
    save_path = SUBMISSIONS_DIR / f"sub_{current_user.id}_{assignment_id}_{prev+1}{ext}"
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    submission = Submission(
        assignment_id=assignment_id,
        child_id=current_user.id,
        attempt_number=prev + 1,
        input_mode="image_upload",
        image_path=str(save_path),
        processing_status="pending",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    exercises = _get_assignment_exercises(assignment_id, db)
    from backend.processing.answer_analyzer import process_submission
    background_tasks.add_task(
        process_submission, db, submission.id, exercises, assignment.show_wrong_reasons
    )
    return {"submission_id": submission.id, "status": "processing"}


@router.post("/canvas")
def submit_canvas(
    assignment_id: int = Form(...),
    canvas_json: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(require_child),
    db: Session = Depends(get_db),
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(404, "Assignment not found")

    prev = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.child_id == current_user.id,
    ).count()

    submission = Submission(
        assignment_id=assignment_id,
        child_id=current_user.id,
        attempt_number=prev + 1,
        input_mode="canvas",
        canvas_json=canvas_json,
        processing_status="pending",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    exercises = _get_assignment_exercises(assignment_id, db)
    from backend.processing.answer_analyzer import process_submission
    background_tasks.add_task(
        process_submission, db, submission.id, exercises, assignment.show_wrong_reasons
    )
    return {"submission_id": submission.id, "status": "processing"}


@router.get("/{submission_id}/status")
def submission_status(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(404, "Submission not found")
    return {"submission_id": submission_id, "status": sub.processing_status}


@router.get("/assignment/{assignment_id}")
def list_submissions_for_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subs = (
        db.query(Submission)
        .filter(Submission.assignment_id == assignment_id)
        .order_by(Submission.submitted_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "attempt_number": s.attempt_number,
            "input_mode": s.input_mode,
            "submitted_at": s.submitted_at,
            "processing_status": s.processing_status,
        }
        for s in subs
    ]
