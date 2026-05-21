import socket
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.deps import require_parent
from backend.models.settings import AppSetting
from backend.models.user import User
from backend.schemas.settings import SettingsUpdate, LLMTestResult, NetworkInfo

router = APIRouter()


@router.get("")
def get_settings(
    current_user: User = Depends(require_parent),
    db: Session = Depends(get_db),
):
    settings = db.query(AppSetting).all()
    result = {s.key: (s.value or "") for s in settings}
    # Mask API key
    key = result.get("llm_api_key", "")
    if key:
        result["llm_api_key"] = "●●●●●●●●" + key[-4:]
    return result


@router.put("")
def update_settings(
    req: SettingsUpdate,
    current_user: User = Depends(require_parent),
    db: Session = Depends(get_db),
):
    updates = req.model_dump(exclude_none=True)
    for key, value in updates.items():
        setting = db.query(AppSetting).filter(AppSetting.key == key).first()
        if setting:
            setting.value = value
        else:
            db.add(AppSetting(key=key, value=value))
    db.commit()
    return {"message": "Settings updated successfully"}


@router.post("/llm/test", response_model=LLMTestResult)
def test_llm(
    current_user: User = Depends(require_parent),
    db: Session = Depends(get_db),
):
    from backend.services.llm_service import test_connection
    result = test_connection(db)
    return result


@router.get("/network-info", response_model=NetworkInfo)
def network_info(current_user: User = Depends(require_parent)):
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"
    return {
        "hostname": hostname,
        "local_ip": local_ip,
        "port": 8000,
        "access_url": f"http://{local_ip}:8000",
        "ipad_instructions": f"On your iPad, open Safari and go to: http://{local_ip}:8000",
    }
