"""Teaching API — Socratic teaching sessions and concept progress."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend.deps import get_current_user, require_child
from backend.models.user import User

router = APIRouter()


class StartSessionRequest(BaseModel):
    concept_id: int


class SendMessageRequest(BaseModel):
    session_id: int
    message: str


@router.post("/session/start")
def start_session(
    req: StartSessionRequest,
    current_user: User = Depends(require_child),
    db: Session = Depends(get_db),
):
    from backend.services.teaching_service import start_session as _start
    from backend.models.concept import Concept
    from backend.models.chapter import Chapter
    from backend.models.textbook import Textbook

    concept = db.query(Concept).filter(Concept.id == req.concept_id).first()
    if not concept:
        raise HTTPException(404, "Concept not found")

    chapter = db.query(Chapter).filter(Chapter.id == concept.chapter_id).first()
    subject = "Mathematics"
    grade = 8
    if chapter:
        tb = db.query(Textbook).filter(Textbook.id == chapter.textbook_id).first()
        if tb:
            subject = tb.subject or "Mathematics"
            grade = tb.grade or 8

    return _start(db, current_user.id, req.concept_id, subject=subject, grade=grade)


@router.post("/session/message")
def send_message(
    req: SendMessageRequest,
    current_user: User = Depends(require_child),
    db: Session = Depends(get_db),
):
    from backend.services.teaching_service import send_message as _send
    from backend.models.concept import Concept
    from backend.models.chapter import Chapter
    from backend.models.textbook import Textbook
    from backend.models.concept_progress import TeachingSession

    session = db.query(TeachingSession).filter(
        TeachingSession.id == req.session_id,
        TeachingSession.child_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    concept = db.query(Concept).filter(Concept.id == session.concept_id).first()
    chapter = db.query(Chapter).filter(Chapter.id == concept.chapter_id).first() if concept else None
    subject, grade = "Mathematics", 8
    if chapter:
        tb = db.query(Textbook).filter(Textbook.id == chapter.textbook_id).first()
        if tb:
            subject = tb.subject or "Mathematics"
            grade = tb.grade or 8

    return _send(db, req.session_id, current_user.id, req.message, subject=subject, grade=grade)


@router.get("/progress")
def get_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.services.teaching_service import get_concept_progress
    # Parent can view child progress; child views their own
    if current_user.role == "parent":
        child = db.query(User).filter(User.role == "child").first()
        child_id = child.id if child else current_user.id
    else:
        child_id = current_user.id
    return get_concept_progress(db, child_id)


@router.get("/progress/{concept_id}")
def get_concept_progress_single(
    concept_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.models.concept_progress import ConceptProgress
    child_id = current_user.id
    if current_user.role == "parent":
        child = db.query(User).filter(User.role == "child").first()
        child_id = child.id if child else current_user.id

    progress = db.query(ConceptProgress).filter(
        ConceptProgress.child_id == child_id,
        ConceptProgress.concept_id == concept_id,
    ).first()

    if not progress:
        return {
            "concept_id": concept_id,
            "mastery_level": "not_started",
            "teach_sessions_completed": 0,
            "unlocked_for_test": False,
            "exercises_attempted": 0,
            "exercises_correct": 0,
        }
    return {
        "concept_id": concept_id,
        "mastery_level": progress.mastery_level,
        "teach_sessions_completed": progress.teach_sessions_completed,
        "unlocked_for_test": progress.unlocked_for_test,
        "exercises_attempted": progress.exercises_attempted,
        "exercises_correct": progress.exercises_correct,
        "last_interaction": progress.last_interaction,
    }
