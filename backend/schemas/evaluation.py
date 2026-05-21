from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class QuestionResult(BaseModel):
    question_index: int
    exercise_id: int
    status: str          # 'correct' | 'wrong' | 'partial' | 'skipped'
    ocr_text: Optional[str]
    feedback: Optional[str]
    correct_answer: Optional[str]
    marks: float = 0.0


class EvaluationOut(BaseModel):
    id: int
    submission_id: int
    total_questions: int
    correct_count: int
    wrong_count: int
    skipped_count: int
    per_question: List[QuestionResult]
    overall_feedback: Optional[str]
    evaluated_at: datetime

    model_config = {"from_attributes": True}
