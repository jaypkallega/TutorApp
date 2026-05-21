from pydantic import BaseModel, Field
from typing import Optional


class SetupRequest(BaseModel):
    parent_display_name: str = Field(..., min_length=1, max_length=50)
    parent_pin: str = Field(..., min_length=4, max_length=8, pattern=r"^\d+$")
    child_display_name: str = Field(..., min_length=1, max_length=50)


class LoginRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    display_name: str


class SetupStatus(BaseModel):
    setup_complete: bool
