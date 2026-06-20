import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.deps import get_current_user
from backend.models.user import User
from backend.models.evaluation import Evaluation
from backend.models.submission import Submission
from backend.models.assignment import Assignment, AssignmentQuestion
from backend.models.exercise import Exercise

router = APIRouter()


@router.get("/submission/{submission_id}")
def get_evaluation_for_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    evaluation = db.query(Evaluation).filter(
        Evaluation.submission_id == submission_id
    ).first()

    if not evaluation:
        sub = db.query(Submission).filter(Submission.id == submission_id).first()
        if sub and sub.processing_status in ("pending", "processing"):
            return {"status": "processing", "message": "Evaluation in progress..."}
        raise HTTPException(404, "Evaluation not found")

    per_q_raw = json.loads(evaluation.per_question) if evaluation.per_question else []

    # --- FIX #5: enrich each question result with the exercise prompt ---
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if sub:
        aq_rows = (
            db.query(AssignmentQuestion)
            .filter(AssignmentQuestion.assignment_id == sub.assignment_id)
            .order_by(AssignmentQuestion.ordering)
            .all()
        )
        exercise_map = {}
        for aq in aq_rows:
            ex = db.query(Exercise).filter(Exercise.id == aq.exercise_id).first()
            if ex:
                exercise_map[aq.ordering] = {
                    "prompt": ex.prompt,
                    "difficulty": ex.difficulty,
                    "exercise_type": ex.exercise_type,
                    "visual_data": ex.visual_data,  # Include for MCQ rendering
                    "visual_type": ex.visual_type,
                }

    enriched = []
    for i, qr in enumerate(per_q_raw):
        ex_info = exercise_map.get(i, {}) if sub else {}
        enriched.append({
            **qr,
            "question_prompt": ex_info.get("prompt", ""),
            "difficulty": ex_info.get("difficulty", ""),
            "visual_data": ex_info.get("visual_data"),  # For MCQ option rendering
            "visual_type": ex_info.get("visual_type"),
        })

    return {
        "id": evaluation.id,
        "submission_id": evaluation.submission_id,
        "total_questions": evaluation.total_questions,
        "correct_count": evaluation.correct_count,
        "wrong_count": evaluation.wrong_count,
        "skipped_count": evaluation.skipped_count,
        "score_percent": round(
            evaluation.correct_count / evaluation.total_questions * 100
            if evaluation.total_questions > 0 else 0
        ),
        "per_question": enriched,
        "overall_feedback": evaluation.overall_feedback,
        "evaluated_at": evaluation.evaluated_at,
        "status": "done",
    }


@router.get("/assignment/{assignment_id}/submissions")
def get_assignment_submissions_with_evals(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FIX #2: Parent view — all submissions + evaluations for an assignment."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(404, "Assignment not found")

    # Get questions with prompts
    aq_rows = (
        db.query(AssignmentQuestion)
        .filter(AssignmentQuestion.assignment_id == assignment_id)
        .order_by(AssignmentQuestion.ordering)
        .all()
    )
    questions = []
    for aq in aq_rows:
        ex = db.query(Exercise).filter(Exercise.id == aq.exercise_id).first()
        if ex:
            questions.append({
                "ordering": aq.ordering,
                "exercise_id": ex.id,
                "prompt": ex.prompt,
                "difficulty": ex.difficulty,
                "expected_answer": ex.expected_answer,
            })

    # Get submissions + evaluations
    subs = (
        db.query(Submission)
        .filter(Submission.assignment_id == assignment_id)
        .order_by(Submission.submitted_at.desc())
        .all()
    )
    submissions = []
    for sub in subs:
        ev = db.query(Evaluation).filter(Evaluation.submission_id == sub.id).first()
        per_q = json.loads(ev.per_question) if ev and ev.per_question else []
        # Enrich per_q with prompts
        for i, qr in enumerate(per_q):
            ex_info = questions[i] if i < len(questions) else {}
            qr["question_prompt"] = ex_info.get("prompt", "")
        submissions.append({
            "id": sub.id,
            "attempt_number": sub.attempt_number,
            "input_mode": sub.input_mode,
            "submitted_at": sub.submitted_at,
            "processing_status": sub.processing_status,
            "evaluation": {
                "correct_count": ev.correct_count,
                "wrong_count": ev.wrong_count,
                "skipped_count": ev.skipped_count,
                "total_questions": ev.total_questions,
                "score_percent": round(
                    ev.correct_count / ev.total_questions * 100
                    if ev.total_questions > 0 else 0
                ),
                "overall_feedback": ev.overall_feedback,
                "per_question": per_q,
            } if ev else None,
        })

    return {
        "assignment_id": assignment_id,
        "title": assignment.title,
        "questions": questions,
        "submissions": submissions,
    }


@router.get("/child/{child_id}/history")
def child_history(
    child_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == "child" and current_user.id != child_id:
        raise HTTPException(403, "Access denied")
    subs = (
        db.query(Submission)
        .filter(Submission.child_id == child_id)
        .order_by(Submission.submitted_at.desc())
        .all()
    )
    history = []
    for sub in subs:
        ev = db.query(Evaluation).filter(Evaluation.submission_id == sub.id).first()
        history.append({
            "submission_id": sub.id,
            "assignment_id": sub.assignment_id,
            "submitted_at": sub.submitted_at,
            "processing_status": sub.processing_status,
            "evaluation": {
                "correct_count": ev.correct_count,
                "total_questions": ev.total_questions,
                "score_percent": round(
                    ev.correct_count / ev.total_questions * 100
                    if ev.total_questions > 0 else 0
                ),
            } if ev else None,
        })
    return history
