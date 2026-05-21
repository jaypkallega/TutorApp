from pydantic import BaseModel
from typing import Optional


class SettingsOut(BaseModel):
    llm_provider: str
    llm_api_key: str    # masked
    llm_model_name: str
    llm_base_url: str
    ocr_mode: str
    lan_only_mode: str
    app_version: str


class SettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model_name: Optional[str] = None
    llm_base_url: Optional[str] = None
    ocr_mode: Optional[str] = None
    lan_only_mode: Optional[str] = None


class LLMTestResult(BaseModel):
    success: bool
    provider: str
    model: str
    latency_ms: Optional[int] = None
    message: str


class NetworkInfo(BaseModel):
    hostname: str
    local_ip: str
    port: int
    access_url: str
    ipad_instructions: str
