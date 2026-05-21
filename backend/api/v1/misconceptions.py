"""Misconception API — exposes child misconception summaries for parent dashboard."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.deps import get_current_user
from backend.models.user import User
from backend.processing.misconception_matcher import get_child_misconception_summary

router = APIRouter()

@router.get("/child/{child_id}/summary")
def child_misconception_summary(
    child_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == "child" and current_user.id != child_id:
        from fastapi import HTTPException
        raise HTTPException(403, "Access denied")
    return get_child_misconception_summary(db, child_id)
