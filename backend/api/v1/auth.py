from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt
import bcrypt

from backend.database import get_db
from backend.models.user import User
from backend.schemas.auth import SetupRequest, LoginRequest, TokenResponse, SetupStatus
from backend.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_HOURS

router = APIRouter()


def hash_pin(pin: str) -> str:
    """Hash a PIN using bcrypt directly (avoids passlib compatibility issues)."""
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_pin(pin: str, hashed: str) -> bool:
    """Verify a PIN against its bcrypt hash."""
    try:
        return bcrypt.checkpw(pin.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: int, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "role": role, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


@router.get("/status", response_model=SetupStatus)
def check_setup(db: Session = Depends(get_db)):
    has_users = db.query(User).first() is not None
    return {"setup_complete": has_users}


@router.post("/setup", response_model=TokenResponse)
def setup(req: SetupRequest, db: Session = Depends(get_db)):
    if db.query(User).first():
        raise HTTPException(400, "App already set up. Use /login instead.")
    parent = User(
        role="parent",
        display_name=req.parent_display_name,
        parent_pin_hash=hash_pin(req.parent_pin),
    )
    child = User(role="child", display_name=req.child_display_name)
    db.add(parent)
    db.add(child)
    db.commit()
    db.refresh(parent)
    return {
        "access_token": create_token(parent.id, "parent"),
        "token_type": "bearer",
        "role": "parent",
        "user_id": parent.id,
        "display_name": parent.display_name,
    }


@router.post("/parent/login", response_model=TokenResponse)
def parent_login(req: LoginRequest, db: Session = Depends(get_db)):
    parent = db.query(User).filter(User.role == "parent").first()
    if not parent or not verify_pin(req.pin, parent.parent_pin_hash):
        raise HTTPException(401, "Invalid PIN")
    parent.last_seen_at = datetime.utcnow()
    db.commit()
    return {
        "access_token": create_token(parent.id, "parent"),
        "token_type": "bearer",
        "role": "parent",
        "user_id": parent.id,
        "display_name": parent.display_name,
    }


@router.post("/child/session", response_model=TokenResponse)
def child_session(db: Session = Depends(get_db)):
    child = db.query(User).filter(User.role == "child").first()
    if not child:
        raise HTTPException(404, "No child account found. Complete setup first.")
    child.last_seen_at = datetime.utcnow()
    db.commit()
    return {
        "access_token": create_token(child.id, "child"),
        "token_type": "bearer",
        "role": "child",
        "user_id": child.id,
        "display_name": child.display_name,
    }
