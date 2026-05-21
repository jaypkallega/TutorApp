from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ExerciseOut(BaseModel):
    id: int
    chapter_id: int
    concept_id: Optional[int]
    source: str
    difficulty: str
    exercise_type: Optional[str]
    prompt: str
    expected_answer: Optional[str]
    expected_method: Optional[str]
    source_page: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerateExercisesRequest(BaseModel):
    chapter_id: int
    count: int = Field(default=5, ge=1, le=20)
    difficulty: str = Field(default="medium", pattern=r"^(easy|medium|hard)$")
    concept_id: Optional[int] = None
