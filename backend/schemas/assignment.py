from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class AssignmentQuestionOut(BaseModel):
    id: int
    exercise_id: int
    ordering: int
    locked: bool
    exercise: Optional[dict] = None  # populated on detail endpoint

    model_config = {"from_attributes": True}


class AssignmentOut(BaseModel):
    id: int
    chapter_id: int
    title: Optional[str]
    question_count: int
    allowed_difficulties: str
    explanation_policy: str
    show_wrong_reasons: bool
    due_date: Optional[datetime]
    status: str
    created_at: datetime
    questions: List[AssignmentQuestionOut] = []

    model_config = {"from_attributes": True}


class CreateAssignmentRequest(BaseModel):
    chapter_id: int
    title: Optional[str] = None
    exercise_ids: List[int] = Field(..., min_length=1, max_length=30)
    allowed_difficulties: List[str] = Field(default=["easy", "medium", "hard"])
    explanation_policy: str = Field(default="locked", pattern=r"^(locked|after_attempt|always)$")
    show_wrong_reasons: bool = False
    due_date: Optional[datetime] = None
