from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class Concept(Base):
    __tablename__ = "concepts"
    id = Column(Integer, primary_key=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    concept_name = Column(String, nullable=False)
    explanation = Column(String, nullable=False)
    textbook_method = Column(String, nullable=True)
    alternate_method = Column(String, nullable=True)
    difficulty_hint = Column(String, nullable=True)
    source_page_start = Column(Integer, nullable=True)
    source_page_end = Column(Integer, nullable=True)
    ordering = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
