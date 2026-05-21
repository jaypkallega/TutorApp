from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ConceptOut(BaseModel):
    id: int
    concept_name: str
    explanation: str
    textbook_method: Optional[str]
    alternate_method: Optional[str]
    difficulty_hint: Optional[str]
    source_page_start: Optional[int]
    source_page_end: Optional[int]
    ordering: int

    model_config = {"from_attributes": True}


class ChapterOut(BaseModel):
    id: int
    textbook_id: int
    chapter_number: int
    title: str
    summary: Optional[str]
    start_page: Optional[int]
    end_page: Optional[int]
    approved: bool
    teaching_style: Optional[str]
    created_at: datetime
    concepts: List[ConceptOut] = []
    # Enriched at query time — not a DB column
    textbook_title: Optional[str] = None
    textbook_subject: Optional[str] = None

    model_config = {"from_attributes": True}


class ChapterUpdate(BaseModel):
    approved: Optional[bool] = None
    teaching_style: Optional[str] = None
    summary: Optional[str] = None
