"""
Misconception Matcher — detects known common student errors and logs them.

The misconceptions table is seeded at startup with Grade 8 common mistakes.
When a student's error matches a known pattern, the specific misconception
is logged and targeted remediation is returned.
"""

import re
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Seed data — Grade 8 common misconceptions
# ---------------------------------------------------------------------------

GRADE8_MISCONCEPTIONS = [
    # Mathematics — Fractions
    {
        "subject": "Mathematics", "topic": "Fractions",
        "pattern_type": "string_pattern",
        "pattern": r"(\d+)/(\d+)\s*[+\-]\s*(\d+)/(\d+)\s*=\s*(\d+)/(\d+)",
        "diagnosis": "Added or subtracted denominators directly",
        "remedy": "When adding fractions, find a common denominator first. The denominators cannot be added directly. For example, 1/2 + 1/3 = 3/6 + 2/6 = 5/6, not 2/5.",
    },
    # Mathematics — Distributive property
    {
        "subject": "Mathematics", "topic": "Algebra",
        "pattern_type": "step_error",
        "pattern": "distributive_error",
        "diagnosis": "Did not distribute multiplication across brackets",
        "remedy": "Remember: a(b + c) = ab + ac. Every term inside the bracket must be multiplied. For example, 2(x + 3) = 2x + 6, not 2x + 3.",
    },
    # Mathematics — Indices
    {
        "subject": "Mathematics", "topic": "Indices / Exponents",
        "pattern_type": "string_pattern",
        "pattern": r"[a-z]\*\*(\d+)\s*\*\s*[a-z]\*\*(\d+)",
        "diagnosis": "Multiplied exponents instead of adding them",
        "remedy": "When multiplying powers with the same base, ADD the exponents: a^m × a^n = a^(m+n). For example, x^2 × x^3 = x^5, not x^6.",
    },
    # Mathematics — Percentages
    {
        "subject": "Mathematics", "topic": "Percentages",
        "pattern_type": "string_pattern",
        "pattern": r"(\d+)%\s+of\s+(\d+)",
        "diagnosis": "Inverted percentage calculation",
        "remedy": "To find X% of Y, calculate (X/100) × Y. For example, 20% of 50 = (20/100) × 50 = 10.",
    },
    # Mathematics — Linear equations (transposition)
    {
        "subject": "Mathematics", "topic": "Linear Equations",
        "pattern_type": "step_error",
        "pattern": "sign_change_error",
        "diagnosis": "Did not change sign when transposing term",
        "remedy": "When moving a term from one side of an equation to the other, its sign must change. For example, x + 5 = 10 → x = 10 - 5 (not 10 + 5).",
    },
    # Mathematics — Squares/Square roots
    {
        "subject": "Mathematics", "topic": "Squares and Square Roots",
        "pattern_type": "string_pattern",
        "pattern": r"sqrt\((\d+)\s*[+\-]\s*(\d+)\)",
        "diagnosis": "Applied square root to each term separately",
        "remedy": "√(a + b) is NOT equal to √a + √b. The square root applies to the entire expression under the radical sign.",
    },
    # Mathematics — Factorisation
    {
        "subject": "Mathematics", "topic": "Factorisation",
        "pattern_type": "step_error",
        "pattern": "wrong_factor_pairs",
        "diagnosis": "Incorrect factor pairs in quadratic factorisation",
        "remedy": "For x² + bx + c, find two numbers that MULTIPLY to give c and ADD to give b. Check both conditions before writing the factors.",
    },
    # Science — Photosynthesis
    {
        "subject": "Science", "topic": "Photosynthesis",
        "pattern_type": "string_pattern",
        "pattern": r"\b(oxygen|o2)\b.*(input|taken in|absorbed|used)",
        "diagnosis": "Confused oxygen as input for photosynthesis",
        "remedy": "In photosynthesis, OXYGEN is a product (output), not an input. The inputs are carbon dioxide, water, and sunlight. Oxygen is released as a byproduct.",
    },
    # Science — Respiration
    {
        "subject": "Science", "topic": "Respiration",
        "pattern_type": "string_pattern",
        "pattern": r"\b(breathing|inhaling|lungs)\b",
        "diagnosis": "Confused respiration with breathing",
        "remedy": "Cellular respiration is a chemical process that happens inside cells to release energy from glucose. Breathing (ventilation) is the physical movement of air in and out of lungs — they are different processes.",
    },
    # Physics — Newton's Laws
    {
        "subject": "Physics", "topic": "Newton's Laws",
        "pattern_type": "string_pattern",
        "pattern": r"\b(heavier|more mass).*(falls faster|faster|quicker)\b",
        "diagnosis": "Believed heavier objects fall faster",
        "remedy": "All objects fall at the same rate regardless of mass (in the absence of air resistance). This was proven by Galileo. The acceleration due to gravity is 9.8 m/s² for all objects.",
    },
    # Chemistry — Atoms
    {
        "subject": "Chemistry", "topic": "Atoms and Molecules",
        "pattern_type": "string_pattern",
        "pattern": r"\b(proton|neutron).*(outside|outer|shell|orbit)\b",
        "diagnosis": "Placed protons/neutrons outside the nucleus",
        "remedy": "Protons and neutrons are found in the NUCLEUS (centre) of the atom. Electrons orbit in shells around the nucleus.",
    },
]


def seed_misconceptions(db: Session) -> None:
    """Seed misconception table on startup if empty."""
    from backend.models.misconception import Misconception
    if db.query(Misconception).count() > 0:
        return
    for m in GRADE8_MISCONCEPTIONS:
        db.add(Misconception(**m))
    db.commit()
    logger.info(f"Seeded {len(GRADE8_MISCONCEPTIONS)} misconceptions")


def match_misconceptions(
    db: Session,
    student_answer: str,
    error_description: str = "",
    subject: str = "Mathematics",
    topic: str = "",
) -> list[dict]:
    """
    Check student answer and error description against known misconceptions.
    Returns list of matched misconceptions with diagnosis and remedy.
    """
    from backend.models.misconception import Misconception

    query = db.query(Misconception).filter(Misconception.subject == subject)
    if topic:
        query = query.filter(Misconception.topic == topic)
    misconceptions = query.all()

    matched = []
    text_to_check = (student_answer + " " + error_description).lower()

    for m in misconceptions:
        if m.pattern_type == "string_pattern" and m.pattern:
            try:
                if re.search(m.pattern, text_to_check, re.I):
                    matched.append({
                        "id": m.id,
                        "topic": m.topic,
                        "diagnosis": m.diagnosis,
                        "remedy": m.remedy,
                    })
            except re.error:
                pass
        elif m.pattern_type == "step_error" and error_description:
            # Step errors are matched by keywords in the error description
            keywords = {
                "distributive_error": ["did not distribute", "bracket", "multiply"],
                "sign_change_error": ["sign", "transpos", "moving"],
                "wrong_factor_pairs": ["factor", "quadratic"],
            }
            kws = keywords.get(m.pattern, [])
            if kws and any(kw in error_description.lower() for kw in kws):
                matched.append({
                    "id": m.id,
                    "topic": m.topic,
                    "diagnosis": m.diagnosis,
                    "remedy": m.remedy,
                })

    return matched


def log_misconception(
    db: Session,
    child_id: int,
    misconception_id: int,
    exercise_id: int,
    submission_id: int,
    student_answer: str,
) -> None:
    """Record that a student triggered a specific misconception."""
    from backend.models.misconception import StudentMisconceptionLog
    log = StudentMisconceptionLog(
        child_id=child_id,
        misconception_id=misconception_id,
        exercise_id=exercise_id,
        submission_id=submission_id,
        student_answer=student_answer[:500],  # truncate
    )
    db.add(log)
    db.commit()


def get_child_misconception_summary(db: Session, child_id: int) -> list[dict]:
    """Get misconception frequency summary for a child (for parent dashboard)."""
    from backend.models.misconception import StudentMisconceptionLog, Misconception
    from sqlalchemy import func

    rows = (
        db.query(
            Misconception.topic,
            Misconception.diagnosis,
            func.count(StudentMisconceptionLog.id).label("count"),
        )
        .join(Misconception, StudentMisconceptionLog.misconception_id == Misconception.id)
        .filter(StudentMisconceptionLog.child_id == child_id)
        .group_by(Misconception.id)
        .order_by(func.count(StudentMisconceptionLog.id).desc())
        .all()
    )
    return [{"topic": r.topic, "diagnosis": r.diagnosis, "count": r.count} for r in rows]
