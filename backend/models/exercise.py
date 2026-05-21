from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from backend.database import Base


class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=True)
    source = Column(String, nullable=False)          # 'textbook' | 'ai_generated'
    difficulty = Column(String, nullable=False)      # 'easy' | 'medium' | 'hard'
    exercise_type = Column(String, nullable=True)    # 'calculation' | 'word_problem' | 'proof'
    prompt = Column(String, nullable=False)
    expected_answer = Column(String, nullable=True)  # human-readable freeform
    expected_method = Column(String, nullable=True)
    # Step 1: structured answer for deterministic evaluation
    structured_answer = Column(Text, nullable=True)  # JSON — see evaluator.py for schema
    visual_type = Column(String, nullable=True)   # null|table|number_line|bar_graph|geometry|page_image
    visual_data = Column(Text, nullable=True)     # JSON — rendered by VisualDisplay component
    source_page = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
