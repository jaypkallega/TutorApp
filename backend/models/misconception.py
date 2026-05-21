from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from backend.database import Base


class Misconception(Base):
    """Known common student errors, seeded at startup."""
    __tablename__ = "misconceptions"
    id = Column(Integer, primary_key=True)
    subject = Column(String, nullable=False, default="Mathematics")
    topic = Column(String, nullable=False)
    pattern_type = Column(String, nullable=False)   # 'sympy_check' | 'string_pattern' | 'step_error'
    pattern = Column(String, nullable=True)         # regex or sympy expression
    diagnosis = Column(String, nullable=False)      # short name e.g. "Added denominators directly"
    remedy = Column(String, nullable=False)         # what to tell the student
    created_at = Column(DateTime, default=func.now())


class StudentMisconceptionLog(Base):
    """Tracks which misconceptions a student triggers over time."""
    __tablename__ = "student_misconception_logs"
    id = Column(Integer, primary_key=True)
    child_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    misconception_id = Column(Integer, ForeignKey("misconceptions.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=True)
    student_answer = Column(String, nullable=True)
    logged_at = Column(DateTime, default=func.now())
