from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    title = Column(String, nullable=True)
    question_count = Column(Integer, nullable=False)
    allowed_difficulties = Column(String, nullable=False)  # JSON array e.g. '["easy","medium"]'
    explanation_policy = Column(String, default="locked")  # 'locked' | 'after_attempt' | 'always'
    show_wrong_reasons = Column(Boolean, default=False)
    due_date = Column(DateTime, nullable=True)
    status = Column(String, default="active")  # active | completed | archived
    created_at = Column(DateTime, default=func.now())


class AssignmentQuestion(Base):
    __tablename__ = "assignment_questions"
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    ordering = Column(Integer, nullable=False)
    locked = Column(Boolean, default=False)
