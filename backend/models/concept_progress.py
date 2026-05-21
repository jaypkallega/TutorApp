from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.sql import func
from backend.database import Base


class ConceptProgress(Base):
    """Tracks a child's mastery progress through each concept."""
    __tablename__ = "concept_progress"
    id = Column(Integer, primary_key=True)
    child_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=False)
    # Mastery levels: not_started → introduced → practised → mastered
    mastery_level = Column(String, default="not_started")
    teach_sessions_completed = Column(Integer, default=0)
    socratic_exchanges = Column(Integer, default=0)  # total back-and-forth turns
    exercises_attempted = Column(Integer, default=0)
    exercises_correct = Column(Integer, default=0)
    last_interaction = Column(DateTime, nullable=True)
    unlocked_for_test = Column(Boolean, default=False)  # true when introduced
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class TeachingSession(Base):
    """A single adaptive teaching session for one concept."""
    __tablename__ = "teaching_sessions"
    id = Column(Integer, primary_key=True)
    child_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=False)
    phase = Column(String, default="hook")  # hook|explore|generalise|example|practice|complete
    messages = Column(String, nullable=True)  # JSON array of {role, content, timestamp}
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
