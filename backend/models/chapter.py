from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class Chapter(Base):
    __tablename__ = "chapters"
    id = Column(Integer, primary_key=True)
    textbook_id = Column(Integer, ForeignKey("textbooks.id"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(String, nullable=True)
    start_page = Column(Integer, nullable=True)
    end_page = Column(Integer, nullable=True)
    approved = Column(Boolean, default=False)
    teaching_style = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
