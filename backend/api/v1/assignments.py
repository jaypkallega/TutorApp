import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.deps import get_current_user
from backend.models.user import User
from backend.models.assignment import Assignment, AssignmentQuestion
from backend.models.exercise import Exercise
from backend.schemas.assignment import CreateAssignmentRequest

router = APIRouter()

# Explanation policies the CHILD is allowed to use (never 'always')
CHILD_ALLOWED_POLICIES = ("locked", "after_attempt")


def _enrich_assignment(assignment: Assignment, db: Session) -> dict:
    qs = (
        db.query(AssignmentQuestion)
        .filter(AssignmentQuestion.assignment_id == assignment.id)
        .order_by(AssignmentQuestion.ordering)
        .all()
    )
    questions = []
    for q in qs:
        ex = db.query(Exercise).filter(Exercise.id == q.exercise_id).first()
        questions.append({
            "id": q.id,
            "exercise_id": q.exercise_id,
            "ordering": q.ordering,
            "locked": q.locked,
            "exercise": {
                "id": ex.id,
                "prompt": ex.prompt,
                "difficulty": ex.difficulty,
                "exercise_type": ex.exercise_type,
            } if ex else None,
        })
    d = {c.name: getattr(assignment, c.name) for c in assignment.__table__.columns}
    d["questions"] = questions
    d["is_self_assigned"] = assignment.created_by == assignment.assigned_to
    return d


@router.get("", response_model=List[dict])
def list_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == "parent":
        assignments = db.query(Assignment).order_by(Assignment.created_at.desc()).all()
    else:
        assignments = (
            db.query(Assignment)
            .filter(
                Assignment.assigned_to == current_user.id,
                Assignment.status == "active",
            )
            .order_by(Assignment.created_at.desc())
            .all()
        )
    return [_enrich_assignment(a, db) for a in assignments]


@router.post("", response_model=dict)
def create_assignment(
    req: CreateAssignmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Both parent and child can create assignments
    if current_user.role == "child":
        # Child can only assign to themselves
        assigned_to_id = current_user.id
        # Restrict explanation policy
        if req.explanation_policy == "always":
            req.explanation_policy = "after_attempt"
    else:
        # Parent assigns to child
        child = db.query(User).filter(User.role == "child").first()
        if not child:
            raise HTTPException(404, "No child account found")
        assigned_to_id = child.id

    # Fix 4: deduplicate exercise_ids while preserving order
    seen = set()
    req.exercise_ids = [x for x in req.exercise_ids if not (x in seen or seen.add(x))]

    assignment = Assignment(
        created_by=current_user.id,
        assigned_to=assigned_to_id,
        chapter_id=req.chapter_id,
        title=req.title,
        question_count=len(req.exercise_ids),
        allowed_difficulties=json.dumps(req.allowed_difficulties),
        explanation_policy=req.explanation_policy,
        show_wrong_reasons=req.show_wrong_reasons,
        due_date=req.due_date,
        status="active",
    )
    db.add(assignment)
    db.flush()

    for i, ex_id in enumerate(req.exercise_ids):
        ex = db.query(Exercise).filter(Exercise.id == ex_id).first()
        if not ex:
            raise HTTPException(404, f"Exercise {ex_id} not found")
        db.add(AssignmentQuestion(
            assignment_id=assignment.id,
            exercise_id=ex_id,
            ordering=i,
        ))
    db.commit()
    db.refresh(assignment)
    return _enrich_assignment(assignment, db)


@router.get("/{assignment_id}", response_model=dict)
def get_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    return _enrich_assignment(assignment, db)


@router.patch("/{assignment_id}/archive")
def archive_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    # Child can only archive their own self-assignments
    if current_user.role == "child" and assignment.created_by != current_user.id:
        raise HTTPException(403, "Cannot archive parent-assigned work")
    assignment.status = "archived"
    db.commit()
    return {"message": "Assignment archived"}
