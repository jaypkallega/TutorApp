from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from backend.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    role = Column(String, nullable=False)           # 'parent' or 'child'
    display_name = Column(String, nullable=False)
    parent_pin_hash = Column(String, nullable=True)  # only set for parent
    created_at = Column(DateTime, default=func.now())
    last_seen_at = Column(DateTime, nullable=True)
