from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from backend.database import Base


class SubmissionDraft(Base):
    """
    Stores per-question answers progressively as the child works through a test.
    One draft per (child, assignment). Finalised on 'Submit Test'.
    """
    __tablename__ = "submission_drafts"
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    child_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # JSON: { "exercise_id": { "mode": "text|canvas|photo", "text": "...", "image_path": "...", "saved_at": "..." } }
    answers = Column(Text, nullable=True, default="{}")
    status = Column(String, default="in_progress")  # in_progress | submitted
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
