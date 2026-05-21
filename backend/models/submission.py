from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    child_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    attempt_number = Column(Integer, default=1)
    input_mode = Column(String, nullable=False)   # 'canvas' | 'image_upload' | 'text'
    image_path = Column(String, nullable=True)
    canvas_json = Column(String, nullable=True)
    text_answer = Column(String, nullable=True)
    submitted_at = Column(DateTime, default=func.now())
    processing_status = Column(String, default="pending")  # pending|processing|done|error
