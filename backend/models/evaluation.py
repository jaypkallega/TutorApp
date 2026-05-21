from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.sql import func
from backend.database import Base


class Evaluation(Base):
    __tablename__ = "evaluations"
    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), unique=True)
    total_questions = Column(Integer, nullable=False)
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    per_question = Column(String, nullable=False)   # JSON list
    overall_feedback = Column(String, nullable=True)
    # Step 9: confidence and review flags
    confidence = Column(Float, default=1.0)         # 0.0 - 1.0
    requires_parent_review = Column(Boolean, default=False)
    low_confidence_questions = Column(String, nullable=True)  # JSON list of Q indices
    evaluated_at = Column(DateTime, default=func.now())
    evaluated_by = Column(String, default="hybrid") # 'hybrid' | 'llm' | 'sympy'
