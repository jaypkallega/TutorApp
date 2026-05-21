from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TextbookOut(BaseModel):
    id: int
    title: str
    subject: str
    grade: int
    upload_type: str
    page_count: Optional[int]
    status: str
    analysis_log: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class TextbookList(BaseModel):
    items: list[TextbookOut]
    total: int
