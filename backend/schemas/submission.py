from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SubmissionOut(BaseModel):
    id: int
    assignment_id: int
    child_id: int
    attempt_number: int
    input_mode: str
    submitted_at: datetime
    processing_status: str

    model_config = {"from_attributes": True}


class SubmissionCreate(BaseModel):
    assignment_id: int
    input_mode: str   # 'text'
    text_answer: Optional[str] = None
