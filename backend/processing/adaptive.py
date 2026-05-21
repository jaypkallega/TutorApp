"""
Adaptive Difficulty Engine — computes recommended difficulty per concept per child.

Three signals combined:
  1. recent_accuracy   — average correct% over last 3 evaluations involving this concept
  2. hints_penalty     — if child used >=2 hints on >50% of questions, reduce effective accuracy
  3. caution_flag      — if >30% of questions required parent review, hold difficulty promotion

State machine (per concept):
  easy   → medium : effective_accuracy >= 0.80 AND no caution flag
  medium → hard   : effective_accuracy >= 0.80 AND no caution flag
  medium → easy   : effective_accuracy < 0.40 (safety net — last 2 evals)
  hard   → medium : effective_accuracy < 0.40 (safety net — last 2 evals)
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

PROMOTE_THRESHOLD    = 0.80   # accuracy needed to go up
DEMOTE_THRESHOLD     = 0.40   # accuracy below which we drop down
LOOKBACK_EVALS       = 3      # number of recent evaluations to consider
DEMOTION_LOOKBACK    = 2      # fewer evals needed to trigger a drop
HINT_HEAVY_FRACTION  = 0.50   # fraction of questions with >=2 hints to apply penalty
HINT_PENALTY         = 0.10   # reduce effective accuracy by this much if hints heavy
CAUTION_FRACTION     = 0.30   # fraction of low-confidence questions to set caution flag

DIFFICULTY_ORDER = ["easy", "medium", "hard"]


def _get_concept_ids_for_chapter(db, chapter_id: int) -> list[int]:
    from backend.models.concept import Concept
    return [c.id for c in db.query(Concept).filter(Concept.chapter_id == chapter_id).all()]


def _compute_signals_for_concept(db, child_id: int, concept_id: int) -> dict:
    """
    Gather per-question data from the last LOOKBACK_EVALS evaluations that
    contain exercises belonging to this concept.

    Returns:
        {
          "eval_count": int,          # how many evaluations found
          "accuracy": float,          # raw correct / total
          "effective_accuracy": float,# after hints penalty
          "caution": bool,            # True if too many low-confidence answers
          "reason": str,              # human-readable explanation
        }
    """
    from backend.models.submission import Submission
    from backend.models.evaluation import Evaluation
    from backend.models.exercise import Exercise
    from backend.models.assignment import Assignment, AssignmentQuestion

    # Find all exercises belonging to this concept
    concept_exercise_ids = set(
        ex.id for ex in db.query(Exercise).filter(Exercise.concept_id == concept_id).all()
    )
    if not concept_exercise_ids:
        return {"eval_count": 0, "accuracy": 0.5, "effective_accuracy": 0.5,
                "caution": False, "reason": "No exercises for concept"}

    # Get recent submissions by this child
    submissions = (
        db.query(Submission)
        .filter(
            Submission.child_id == child_id,
            Submission.processing_status == "done",
        )
        .order_by(Submission.submitted_at.desc())
        .limit(10)   # look in last 10 submissions to find ones with this concept
        .all()
    )

    relevant_evals = []
    for sub in submissions:
        ev = db.query(Evaluation).filter(Evaluation.submission_id == sub.id).first()
        if not ev:
            continue
        try:
            pq = json.loads(ev.per_question or "[]")
        except Exception:
            continue
        # Check if any question in this eval belongs to our concept
        relevant_qs = [q for q in pq if q.get("exercise_id") in concept_exercise_ids]
        if relevant_qs:
            relevant_evals.append(relevant_qs)
        if len(relevant_evals) >= LOOKBACK_EVALS:
            break

    if not relevant_evals:
        return {"eval_count": 0, "accuracy": 0.5, "effective_accuracy": 0.5,
                "caution": False, "reason": "No evaluations found for concept"}

    # Flatten all relevant questions across evals
    all_qs = [q for qs in relevant_evals for q in qs]
    total   = len(all_qs)
    correct = sum(1 for q in all_qs if q.get("status") == "correct")
    accuracy = correct / total if total else 0.5

    # Signal 2: hints penalty
    heavy_hint_qs = sum(1 for q in all_qs if q.get("hints_used", 0) >= 2)
    hints_heavy = (heavy_hint_qs / total) > HINT_HEAVY_FRACTION if total else False
    effective_accuracy = accuracy - (HINT_PENALTY if hints_heavy else 0.0)

    # Signal 3: caution flag
    review_qs = sum(1 for q in all_qs if q.get("requires_parent_review"))
    caution = (review_qs / total) > CAUTION_FRACTION if total else False

    reason_parts = [f"accuracy {round(accuracy*100)}%"]
    if hints_heavy:
        reason_parts.append(f"hints penalty -{round(HINT_PENALTY*100)}%")
    if caution:
        reason_parts.append("caution: low-confidence answers")

    return {
        "eval_count": len(relevant_evals),
        "accuracy": round(accuracy, 3),
        "effective_accuracy": round(max(0.0, effective_accuracy), 3),
        "caution": caution,
        "reason": ", ".join(reason_parts),
    }


def compute_difficulty_for_concept(db, child_id: int, concept_id: int, current_difficulty: str = "easy") -> dict:
    """
    Compute the recommended difficulty for one concept.
    Returns a dict with: recommended, current, should_change, reason, signals.
    """
    signals = _compute_signals_for_concept(db, child_id, concept_id)

    if signals["eval_count"] == 0:
        return {
            "recommended": current_difficulty,
            "current": current_difficulty,
            "should_change": False,
            "reason": "Not enough data yet",
            "signals": signals,
        }

    eff_acc  = signals["effective_accuracy"]
    caution  = signals["caution"]
    cur_idx  = DIFFICULTY_ORDER.index(current_difficulty) if current_difficulty in DIFFICULTY_ORDER else 0

    new_idx = cur_idx
    change_reason = signals["reason"]

    # Promotion check (need LOOKBACK_EVALS evaluations)
    if (signals["eval_count"] >= LOOKBACK_EVALS
            and eff_acc >= PROMOTE_THRESHOLD
            and not caution
            and cur_idx < len(DIFFICULTY_ORDER) - 1):
        new_idx = cur_idx + 1
        change_reason = f"Promoted: {change_reason}"

    # Demotion check (only need DEMOTION_LOOKBACK evaluations)
    elif (signals["eval_count"] >= DEMOTION_LOOKBACK
            and eff_acc < DEMOTE_THRESHOLD
            and cur_idx > 0):
        new_idx = cur_idx - 1
        change_reason = f"Dropped: {change_reason}"

    recommended = DIFFICULTY_ORDER[new_idx]
    return {
        "recommended": recommended,
        "current": current_difficulty,
        "should_change": recommended != current_difficulty,
        "reason": change_reason,
        "signals": signals,
    }


def update_all_concept_difficulties(db, child_id: int) -> None:
    """
    Recompute and store recommended_difficulty for every concept the child has progress on.
    Called automatically after each submission is evaluated.
    """
    from backend.models.concept_progress import ConceptProgress

    try:
        progresses = (
            db.query(ConceptProgress)
            .filter(ConceptProgress.child_id == child_id)
            .all()
        )
        for cp in progresses:
            current = getattr(cp, "recommended_difficulty", None) or "easy"
            result = compute_difficulty_for_concept(db, child_id, cp.concept_id, current)
            if result["should_change"]:
                cp.recommended_difficulty = result["recommended"]
                cp.difficulty_updated_at = datetime.utcnow()
                logger.info(
                    f"Concept {cp.concept_id} child {child_id}: "
                    f"{result['current']} → {result['recommended']} ({result['reason']})"
                )
        db.commit()
    except Exception as e:
        logger.warning(f"update_all_concept_difficulties failed: {e}")


def get_chapter_difficulty_recommendation(db, child_id: int, chapter_id: int) -> dict:
    """
    Aggregate concept-level recommendations for a chapter.
    Returns the highest recommended difficulty among all concepts in the chapter,
    plus per-concept breakdown and aggregate signals.
    """
    from backend.models.concept_progress import ConceptProgress
    from backend.models.concept import Concept

    concepts = db.query(Concept).filter(Concept.chapter_id == chapter_id).all()
    if not concepts:
        return {
            "recommended_difficulty": "easy",
            "signals": {"accuracy": None, "hints_penalty": False, "caution": False},
            "concept_count": 0,
            "has_data": False,
        }

    # Collect recommendations for each concept
    recommendations = []
    all_signals = []
    for concept in concepts:
        cp = db.query(ConceptProgress).filter(
            ConceptProgress.child_id == child_id,
            ConceptProgress.concept_id == concept.id,
        ).first()
        current = (cp.recommended_difficulty if cp and cp.recommended_difficulty else "easy")
        rec = compute_difficulty_for_concept(db, child_id, concept.id, current)
        recommendations.append(rec["recommended"])
        if rec["signals"]["eval_count"] > 0:
            all_signals.append(rec["signals"])

    if not all_signals:
        return {
            "recommended_difficulty": "easy",
            "signals": {"accuracy": None, "hints_penalty": False, "caution": False},
            "concept_count": len(concepts),
            "has_data": False,
        }

    # Highest difficulty among concepts with data
    best_idx = max(
        DIFFICULTY_ORDER.index(r) if r in DIFFICULTY_ORDER else 0
        for r in recommendations
    )
    avg_accuracy = sum(s["accuracy"] for s in all_signals) / len(all_signals)
    any_caution  = any(s["caution"] for s in all_signals)

    return {
        "recommended_difficulty": DIFFICULTY_ORDER[best_idx],
        "signals": {
            "accuracy": round(avg_accuracy, 3),
            "hints_penalty": any(s["effective_accuracy"] < s["accuracy"] for s in all_signals),
            "caution": any_caution,
        },
        "concept_count": len(concepts),
        "has_data": True,
    }
