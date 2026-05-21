from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class Textbook(Base):
    __tablename__ = "textbooks"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    subject = Column(String, default="Mathematics")
    grade = Column(Integer, nullable=False, default=8)
    file_path = Column(String, nullable=False)
    upload_type = Column(String, nullable=False)   # 'pdf' or 'images'
    page_count = Column(Integer, nullable=True)
    status = Column(String, default="pending")     # pending|processing|ready|error
    analysis_log = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
