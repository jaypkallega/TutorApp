from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class ProgressState(Base):
    __tablename__ = "progress_states"
    id = Column(Integer, primary_key=True)
    child_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    current_chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True)
    current_assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    current_question_idx = Column(Integer, default=0)
    resume_payload = Column(String, nullable=True)  # JSON blob
    saved_at = Column(DateTime, default=func.now())
