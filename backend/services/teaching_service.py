"""
Teaching Service — Socratic adaptive teaching engine.

Manages teaching sessions for individual concepts.
The AI never gives answers directly — it guides through questions.

Phase progression:
  hook        → engage with real-world connection or puzzling question
  explore     → guide child to observe patterns through guided examples
  generalise  → child states the rule in their own words
  example     → work through a concrete example together
  practice    → child tries a problem with AI guidance if needed
  complete    → concept marked 'introduced', unlocked for testing

Progress advancement rules:
  introduced  → after 1 completed session
  practised   → after 3 sessions OR 5+ correct exercises
  mastered    → after 5+ sessions AND 80%+ exercise accuracy
"""

import json
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase definitions — how many exchanges before advancing
# ---------------------------------------------------------------------------
PHASE_ORDER = ["hook", "explore", "generalise", "example", "practice", "complete"]

PHASE_MIN_EXCHANGES = {
    "hook": 1,
    "explore": 2,
    "generalise": 1,
    "example": 1,
    "practice": 2,
}

# ---------------------------------------------------------------------------
# System prompts per phase
# ---------------------------------------------------------------------------

BASE_SYSTEM = """\
You are an adaptive tutor for a Grade {grade} student learning {subject}.
Current concept: {concept_name}
Concept background: {concept_explanation}

CRITICAL RULES — NEVER BREAK THESE:
1. NEVER give the answer or the rule directly. Always guide through questions.
2. Ask ONE question at a time. Never overwhelm with multiple questions.
3. Praise correct observations specifically ("That's exactly right — you noticed that...")
4. If the student is wrong, do NOT say "wrong" — say "Interesting, what happens if we try..." and redirect.
5. Use simple language appropriate for Grade {grade}.
6. Keep responses SHORT — maximum 4 sentences. Students lose focus with long explanations.
7. You are in the {phase} phase. Follow the phase instructions below.
"""

PHASE_INSTRUCTIONS = {
    "hook": """\
HOOK PHASE: Your goal is to spark curiosity.
- Start with a surprising real-world question or scenario connected to {concept_name}.
- Do NOT mention the concept name yet. Let the student wonder.
- End with a question that makes them think.
Example hook for fractions: "If you and 3 friends share a pizza equally, how much does each person get? What if there were 7 friends?" """,

    "explore": """\
EXPLORE PHASE: Guide the student to discover patterns.
- Give a simple concrete example. Ask the student to observe something about it.
- Build from their observation to a slightly harder example.
- Never state the pattern — ask "what do you notice?" and "why do you think that is?"
- If they see the pattern, validate and ask them to test it with one more example they choose.""",

    "generalise": """\
GENERALISE PHASE: Help the student state the rule in their own words.
- Ask: "So based on what we explored, how would you explain this to a friend?"
- Accept their phrasing — do not correct to textbook language.
- If incomplete, ask a targeted question to fill the gap.
- Once they have stated something reasonable, confirm and refine gently.""",

    "example": """\
EXAMPLE PHASE: Work through one concrete problem together.
- Give a specific problem (not the same as the exercises they'll be tested on).
- Ask "What should we do first?" — let THEM drive the steps.
- If they get a step right, say "Perfect — now what?"
- If stuck, ask "What information do we have?" not "The next step is..." """,

    "practice": """\
PRACTICE PHASE: Student tries a problem independently.
- Give ONE clear practice problem appropriate to {concept_name} and grade {grade}.
- Say "Have a go — show me your thinking step by step."
- When they respond, evaluate their approach first, then their answer.
- If correct: celebrate specifically and confirm the concept is solid.
- If wrong: identify exactly which step went wrong and ask one guiding question about that step.""",

    "complete": """\
COMPLETE PHASE: Wrap up the session warmly.
- Summarise what the student discovered in ONE sentence using THEIR words from the session.
- Tell them they are now ready to practise this in exercises.
- Be warm and encouraging.""",
}


def _build_system_prompt(concept: dict, phase: str, subject: str = "Mathematics", grade: int = 8) -> str:
    base = BASE_SYSTEM.format(
        grade=grade,
        subject=subject,
        concept_name=concept.get("concept_name", ""),
        concept_explanation=concept.get("explanation", ""),
        phase=phase,
    )
    phase_instr = PHASE_INSTRUCTIONS.get(phase, "")
    phase_instr = phase_instr.replace("{concept_name}", concept.get("concept_name", ""))
    phase_instr = phase_instr.replace("{grade}", str(grade))
    return base + "\n\n" + phase_instr


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def get_or_create_session(db: Session, child_id: int, concept_id: int):
    """Get the latest incomplete session for a concept, or create a new one."""
    from backend.models.concept_progress import TeachingSession

    session = (
        db.query(TeachingSession)
        .filter(
            TeachingSession.child_id == child_id,
            TeachingSession.concept_id == concept_id,
            TeachingSession.completed == False,
        )
        .order_by(TeachingSession.created_at.desc())
        .first()
    )
    if not session:
        session = TeachingSession(
            child_id=child_id,
            concept_id=concept_id,
            phase="hook",
            messages=json.dumps([]),
            completed=False,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def get_session_messages(session) -> list[dict]:
    """Parse messages from session."""
    try:
        return json.loads(session.messages or "[]")
    except Exception:
        return []


def advance_phase(current_phase: str, messages: list[dict]) -> str:
    """Determine if we should advance to the next phase based on exchange count."""
    current_idx = PHASE_ORDER.index(current_phase)
    if current_idx >= len(PHASE_ORDER) - 1:
        return current_phase

    # Count student messages in this phase
    phase_student_msgs = sum(1 for m in messages if m.get("role") == "user" and m.get("phase") == current_phase)
    min_required = PHASE_MIN_EXCHANGES.get(current_phase, 1)

    if phase_student_msgs >= min_required:
        next_phase = PHASE_ORDER[current_idx + 1]
        logger.info(f"Advancing from {current_phase} → {next_phase} after {phase_student_msgs} exchanges")
        return next_phase
    return current_phase


def start_session(
    db: Session,
    child_id: int,
    concept_id: int,
    subject: str = "Mathematics",
    grade: int = 8,
) -> dict:
    """Start or resume a teaching session. Returns the first AI message."""
    from backend.models.concept import Concept
    from backend.models.concept_progress import TeachingSession
    from backend.services.llm_service import call_llm

    concept = db.query(Concept).filter(Concept.id == concept_id).first()
    if not concept:
        return {"error": "Concept not found"}

    concept_dict = {
        "concept_name": concept.concept_name,
        "explanation": concept.explanation,
        "textbook_method": concept.textbook_method,
    }

    session = get_or_create_session(db, child_id, concept_id)
    messages = get_session_messages(session)

    # If session already has messages, resume it
    if messages:
        last_ai = next((m for m in reversed(messages) if m["role"] == "assistant"), None)
        return {
            "session_id": session.id,
            "phase": session.phase,
            "message": last_ai["content"] if last_ai else "Let's continue where we left off.",
            "messages": messages,
            "is_resume": True,
        }

    # New session — generate opening hook
    system = _build_system_prompt(concept_dict, "hook", subject, grade)
    opening = call_llm(
        db,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Start teaching me about {concept.concept_name}."},
        ],
        max_tokens=300,
        temperature=0.7,
    )

    msg = {"role": "assistant", "content": opening, "phase": "hook", "timestamp": datetime.utcnow().isoformat()}
    messages.append(msg)
    session.messages = json.dumps(messages)
    db.commit()

    return {
        "session_id": session.id,
        "phase": "hook",
        "message": opening,
        "messages": messages,
        "is_resume": False,
    }


def send_message(
    db: Session,
    session_id: int,
    child_id: int,
    child_message: str,
    subject: str = "Mathematics",
    grade: int = 8,
) -> dict:
    """Process a child's message and return the AI's response."""
    from backend.models.concept_progress import TeachingSession
    from backend.models.concept import Concept
    from backend.services.llm_service import call_llm

    session = db.query(TeachingSession).filter(
        TeachingSession.id == session_id,
        TeachingSession.child_id == child_id,
    ).first()
    if not session:
        return {"error": "Session not found"}

    concept = db.query(Concept).filter(Concept.id == session.concept_id).first()
    if not concept:
        return {"error": "Concept not found"}

    concept_dict = {
        "concept_name": concept.concept_name,
        "explanation": concept.explanation,
        "textbook_method": concept.textbook_method,
    }

    messages = get_session_messages(session)
    current_phase = session.phase

    # Add child message
    child_msg = {
        "role": "user",
        "content": child_message,
        "phase": current_phase,
        "timestamp": datetime.utcnow().isoformat(),
    }
    messages.append(child_msg)

    # Check if we should advance phase
    new_phase = advance_phase(current_phase, messages)
    if new_phase == "complete" and not session.completed:
        session.completed = True
        _update_progress(db, child_id, session.concept_id)

    session.phase = new_phase

    # Build conversation for LLM (last 10 messages for context window)
    system = _build_system_prompt(concept_dict, new_phase, subject, grade)
    llm_messages = [{"role": "system", "content": system}]
    for m in messages[-10:]:
        llm_messages.append({"role": m["role"], "content": m["content"]})

    ai_response = call_llm(db, llm_messages, max_tokens=300, temperature=0.6)

    ai_msg = {
        "role": "assistant",
        "content": ai_response,
        "phase": new_phase,
        "timestamp": datetime.utcnow().isoformat(),
    }
    messages.append(ai_msg)

    session.messages = json.dumps(messages)
    session.updated_at = datetime.utcnow()
    db.commit()

    return {
        "session_id": session.id,
        "phase": new_phase,
        "message": ai_response,
        "phase_changed": new_phase != current_phase,
        "session_complete": session.completed,
        "messages": messages,
    }


def _update_progress(db: Session, child_id: int, concept_id: int) -> None:
    """Update ConceptProgress after a session completes."""
    from backend.models.concept_progress import ConceptProgress

    progress = db.query(ConceptProgress).filter(
        ConceptProgress.child_id == child_id,
        ConceptProgress.concept_id == concept_id,
    ).first()

    if not progress:
        progress = ConceptProgress(
            child_id=child_id,
            concept_id=concept_id,
            mastery_level="not_started",
        )
        db.add(progress)
        db.flush()

    progress.teach_sessions_completed += 1
    progress.last_interaction = datetime.utcnow()
    progress.unlocked_for_test = True

    sessions = progress.teach_sessions_completed
    correct_ratio = (
        progress.exercises_correct / progress.exercises_attempted
        if progress.exercises_attempted > 0 else 0
    )

    if sessions >= 5 and correct_ratio >= 0.8:
        progress.mastery_level = "mastered"
    elif sessions >= 3 or progress.exercises_correct >= 5:
        progress.mastery_level = "practised"
    else:
        progress.mastery_level = "introduced"

    db.commit()


def get_concept_progress(db: Session, child_id: int) -> list[dict]:
    """Get progress overview for all concepts a child has interacted with."""
    from backend.models.concept_progress import ConceptProgress
    from backend.models.concept import Concept
    from backend.models.chapter import Chapter

    rows = (
        db.query(ConceptProgress, Concept, Chapter)
        .join(Concept, ConceptProgress.concept_id == Concept.id)
        .join(Chapter, Concept.chapter_id == Chapter.id)
        .filter(ConceptProgress.child_id == child_id)
        .all()
    )

    return [
        {
            "concept_id": cp.concept_id,
            "concept_name": c.concept_name,
            "chapter_title": ch.title,
            "chapter_id": c.chapter_id,
            "mastery_level": cp.mastery_level,
            "teach_sessions_completed": cp.teach_sessions_completed,
            "unlocked_for_test": cp.unlocked_for_test,
            "exercises_attempted": cp.exercises_attempted,
            "exercises_correct": cp.exercises_correct,
            "last_interaction": cp.last_interaction,
        }
        for cp, c, ch in rows
    ]


def update_exercise_progress(db: Session, child_id: int, concept_id: int, correct: bool) -> None:
    """Update concept progress when a child completes an exercise."""
    from backend.models.concept_progress import ConceptProgress

    progress = db.query(ConceptProgress).filter(
        ConceptProgress.child_id == child_id,
        ConceptProgress.concept_id == concept_id,
    ).first()
    if progress:
        progress.exercises_attempted += 1
        if correct:
            progress.exercises_correct += 1
        progress.last_interaction = datetime.utcnow()
        db.commit()
