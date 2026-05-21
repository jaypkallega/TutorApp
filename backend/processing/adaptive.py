"""
Adaptive Difficulty Engine — computes recommended difficulty per concept per child.

READINESS FORMULA (R1):
  readiness = 0.6 × accuracy + 0.2 × independence + 0.2 × stability
  where:
    accuracy     = recent percent correct
    independence = 1 − min(avg_hints_per_q / 3, 1)   — fewer hints = higher score
    stability    = 1.0 if ALL individual evals ≥ 0.65, 0.5 if mixed, 0.0 if all weak

MISCONCEPTION SIGNAL (R2):
  If > 20 % of questions carry a non-empty misconceptions list, block promotion
  and set a 'misconception_caution' flag that surfaces in the reason string.

CONSECUTIVE-SEQUENCE LOGIC (R4):
  Promotion requires readiness ≥ PROMOTE_THRESHOLD in the LAST eval AND
  average readiness ≥ PROMOTE_THRESHOLD across the lookback window.
  (No more lucky-single-high-score promotions.)
  Demotion triggers on readiness < DEMOTE_THRESHOLD in the most-recent eval alone.
  (Quick safety-net — don't wait for 3 bad evals to step back.)

STATE MACHINE:
  easy   → medium : readiness_avg ≥ 0.80 AND last_readiness ≥ 0.75 AND no caution
  medium → hard   : same
  medium → easy   : last_readiness < DEMOTE_THRESHOLD
  hard   → medium : last_readiness < DEMOTE_THRESHOLD
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
PROMOTE_AVG_THRESHOLD  = 0.80   # average readiness across lookback to promote
PROMOTE_LAST_THRESHOLD = 0.75   # last eval readiness must also be this high
DEMOTE_THRESHOLD       = 0.45   # last eval readiness below this → step down
LOOKBACK_EVALS         = 3      # evals needed before promotion is considered
DEMOTION_LOOKBACK      = 1      # one bad recent eval is enough to step back

# Independence sub-signal
MAX_HINTS_PER_Q        = 3.0    # hints/q at which independence score hits 0

# Caution flags
REVIEW_CAUTION_FRAC    = 0.30   # fraction review-flagged → review caution
MISCONCEPTION_FRAC     = 0.20   # fraction with misconceptions → misconception caution

# Stability sub-signal
STABILITY_STRONG_FLOOR = 0.65   # each eval accuracy must reach this to be "stable"

DIFFICULTY_ORDER = ["easy", "medium", "hard"]


# ── Per-eval readiness ────────────────────────────────────────────────────────

def _readiness_for_eval(questions: list[dict]) -> dict:
    """
    Compute the three sub-signals and composite readiness for a single eval's
    questions that belong to a specific concept.

    Returns:
      accuracy, independence, stability (always 1.0 per-eval), readiness, hints_per_q
    """
    total   = len(questions)
    if not total:
        return {"accuracy": 0.5, "independence": 0.5, "readiness": 0.5, "hints_per_q": 0}

    correct   = sum(1 for q in questions if q.get("status") == "correct")
    total_hints = sum(q.get("hints_used", 0) for q in questions)

    accuracy       = correct / total
    hints_per_q    = total_hints / total
    independence   = max(0.0, 1.0 - min(hints_per_q / MAX_HINTS_PER_Q, 1.0))

    readiness = 0.6 * accuracy + 0.2 * independence
    # Stability within a single eval is not meaningful — handled across evals
    return {
        "accuracy": round(accuracy, 3),
        "independence": round(independence, 3),
        "readiness": round(readiness, 3),
        "hints_per_q": round(hints_per_q, 2),
    }


# ── Concept-level signal gathering ───────────────────────────────────────────

def _compute_signals_for_concept(db, child_id: int, concept_id: int) -> dict:
    """
    Gather per-question data from the last LOOKBACK_EVALS evaluations that
    contain exercises belonging to this concept.

    Returns a rich dict consumed by compute_difficulty_for_concept().
    """
    from backend.models.submission import Submission
    from backend.models.evaluation import Evaluation
    from backend.models.exercise import Exercise

    concept_exercise_ids = set(
        ex.id for ex in db.query(Exercise).filter(Exercise.concept_id == concept_id).all()
    )
    if not concept_exercise_ids:
        return {
            "eval_count": 0,
            "per_eval_readiness": [],
            "avg_accuracy": 0.5,
            "avg_independence": 0.5,
            "avg_readiness": 0.5,
            "last_readiness": 0.5,
            "stability": 1.0,
            "review_caution": False,
            "misconception_caution": False,
            "avg_hints_per_q": 0,
            "reason": "No exercises for concept",
        }

    submissions = (
        db.query(Submission)
        .filter(
            Submission.child_id == child_id,
            Submission.processing_status == "done",
        )
        .order_by(Submission.submitted_at.desc())
        .limit(15)
        .all()
    )

    # Collect per-eval question lists in chronological order (most-recent first)
    relevant_evals: list[list[dict]] = []
    for sub in submissions:
        ev = db.query(Evaluation).filter(Evaluation.submission_id == sub.id).first()
        if not ev:
            continue
        try:
            pq = json.loads(ev.per_question or "[]")
        except Exception:
            continue
        relevant_qs = [q for q in pq if q.get("exercise_id") in concept_exercise_ids]
        if relevant_qs:
            relevant_evals.append(relevant_qs)
        if len(relevant_evals) >= LOOKBACK_EVALS:
            break

    if not relevant_evals:
        return {
            "eval_count": 0,
            "per_eval_readiness": [],
            "avg_accuracy": 0.5,
            "avg_independence": 0.5,
            "avg_readiness": 0.5,
            "last_readiness": 0.5,
            "stability": 1.0,
            "review_caution": False,
            "misconception_caution": False,
            "avg_hints_per_q": 0,
            "reason": "No evaluations found for concept",
        }

    # Per-eval readiness scores
    per_eval = [_readiness_for_eval(qs) for qs in relevant_evals]
    avg_accuracy    = sum(e["accuracy"] for e in per_eval) / len(per_eval)
    avg_independence = sum(e["independence"] for e in per_eval) / len(per_eval)
    avg_hints_per_q = sum(e["hints_per_q"] for e in per_eval) / len(per_eval)

    # R4: stability = fraction of evals that individually cleared the floor
    strong_evals = sum(1 for e in per_eval if e["accuracy"] >= STABILITY_STRONG_FLOOR)
    stability    = strong_evals / len(per_eval)

    # Composite readiness per eval (add stability component now)
    # Re-weight: accuracy 0.6, independence 0.2, stability 0.2
    per_eval_readiness = [
        round(0.6 * e["accuracy"] + 0.2 * e["independence"] + 0.2 * stability, 3)
        for e in per_eval
    ]
    avg_readiness  = sum(per_eval_readiness) / len(per_eval_readiness)
    last_readiness = per_eval_readiness[0]  # most recent first

    # R2: caution flags — flatten all questions
    all_qs = [q for qs in relevant_evals for q in qs]
    total  = len(all_qs)
    review_qs        = sum(1 for q in all_qs if q.get("requires_parent_review"))
    misconception_qs = sum(1 for q in all_qs
                           if q.get("misconceptions") and len(q["misconceptions"]) > 0)

    review_caution       = (review_qs / total)        > REVIEW_CAUTION_FRAC  if total else False
    misconception_caution = (misconception_qs / total) > MISCONCEPTION_FRAC   if total else False

    # Build human-readable reason
    reason_parts = [f"accuracy {round(avg_accuracy * 100)}%"]
    reason_parts.append(f"independence {round(avg_independence * 100)}%")
    reason_parts.append(f"stability {round(stability * 100)}%")
    reason_parts.append(f"readiness {round(avg_readiness * 100)}%")
    if review_caution:
        reason_parts.append("⚠ low-confidence answers")
    if misconception_caution:
        reason_parts.append("⚠ recurring misconceptions")

    return {
        "eval_count":            len(relevant_evals),
        "per_eval_readiness":    per_eval_readiness,
        "avg_accuracy":          round(avg_accuracy, 3),
        "avg_independence":      round(avg_independence, 3),
        "avg_readiness":         round(avg_readiness, 3),
        "last_readiness":        round(last_readiness, 3),
        "stability":             round(stability, 3),
        "review_caution":        review_caution,
        "misconception_caution": misconception_caution,
        "avg_hints_per_q":       round(avg_hints_per_q, 2),
        "reason":                ", ".join(reason_parts),
    }


# ── Decision logic ────────────────────────────────────────────────────────────

def compute_difficulty_for_concept(
    db, child_id: int, concept_id: int, current_difficulty: str = "easy"
) -> dict:
    """
    Compute the recommended difficulty for one concept.
    Returns: recommended, current, should_change, reason, cautions, signals.
    """
    signals  = _compute_signals_for_concept(db, child_id, concept_id)

    if signals["eval_count"] == 0:
        return {
            "recommended":    current_difficulty,
            "current":        current_difficulty,
            "should_change":  False,
            "reason":         "Not enough data yet",
            "cautions":       [],
            "signals":        signals,
        }

    avg_r  = signals["avg_readiness"]
    last_r = signals["last_readiness"]
    cautions: list[str] = []
    if signals["review_caution"]:
        cautions.append("Still has low-confidence answers — worth a parent review")
    if signals["misconception_caution"]:
        cautions.append("Recurring misconceptions detected — may need concept reinforcement")

    cur_idx = DIFFICULTY_ORDER.index(current_difficulty) if current_difficulty in DIFFICULTY_ORDER else 0
    new_idx = cur_idx
    change_reason = signals["reason"]

    any_caution = signals["review_caution"] or signals["misconception_caution"]

    # R4: Promotion — average AND last eval must clear thresholds, no caution
    if (
        signals["eval_count"] >= LOOKBACK_EVALS
        and avg_r  >= PROMOTE_AVG_THRESHOLD
        and last_r >= PROMOTE_LAST_THRESHOLD
        and not any_caution
        and cur_idx < len(DIFFICULTY_ORDER) - 1
    ):
        new_idx = cur_idx + 1
        change_reason = f"Promoted: {change_reason}"

    # R4: Demotion — only the last eval needs to be below threshold
    elif (
        signals["eval_count"] >= DEMOTION_LOOKBACK
        and last_r < DEMOTE_THRESHOLD
        and cur_idx > 0
    ):
        new_idx = cur_idx - 1
        change_reason = f"Dropped: {change_reason}"

    recommended = DIFFICULTY_ORDER[new_idx]
    return {
        "recommended":   recommended,
        "current":       current_difficulty,
        "should_change": recommended != current_difficulty,
        "reason":        change_reason,
        "cautions":      cautions,
        "signals":       signals,
    }


# ── Batch update ─────────────────────────────────────────────────────────────

def update_all_concept_difficulties(db, child_id: int) -> None:
    """
    Recompute and store recommended_difficulty for every concept the child has
    progress on. Called automatically after each submission is evaluated.
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
            result  = compute_difficulty_for_concept(db, child_id, cp.concept_id, current)
            if result["should_change"]:
                cp.recommended_difficulty = result["recommended"]
                cp.difficulty_updated_at  = datetime.utcnow()
                logger.info(
                    f"Concept {cp.concept_id} child {child_id}: "
                    f"{result['current']} → {result['recommended']} ({result['reason']})"
                )
        db.commit()
    except Exception as e:
        logger.warning(f"update_all_concept_difficulties failed: {e}")


# ── Chapter-level aggregation ────────────────────────────────────────────────

def get_chapter_difficulty_recommendation(db, child_id: int, chapter_id: int) -> dict:
    """
    Aggregate concept-level recommendations for a chapter.

    Returns the highest recommended difficulty, structured reason + caution
    strings for the parent, and raw signals.
    """
    from backend.models.concept_progress import ConceptProgress
    from backend.models.concept import Concept

    concepts = db.query(Concept).filter(Concept.chapter_id == chapter_id).all()
    if not concepts:
        return {
            "recommended_difficulty": "easy",
            "reason": None,
            "cautions": [],
            "signals": {"avg_accuracy": None, "avg_hints_per_q": None,
                        "stability": None, "readiness": None},
            "concept_count": 0,
            "has_data": False,
        }

    concept_results = []
    all_signals     = []

    for concept in concepts:
        cp = db.query(ConceptProgress).filter(
            ConceptProgress.child_id   == child_id,
            ConceptProgress.concept_id == concept.id,
        ).first()
        current = (cp.recommended_difficulty if cp and cp.recommended_difficulty else "easy")
        rec = compute_difficulty_for_concept(db, child_id, concept.id, current)
        concept_results.append(rec)
        if rec["signals"]["eval_count"] > 0:
            all_signals.append(rec["signals"])

    if not all_signals:
        return {
            "recommended_difficulty": "easy",
            "reason": None,
            "cautions": [],
            "signals": {"avg_accuracy": None, "avg_hints_per_q": None,
                        "stability": None, "readiness": None},
            "concept_count": len(concepts),
            "has_data": False,
        }

    # Highest difficulty among concepts with data
    best_idx = max(
        DIFFICULTY_ORDER.index(r["recommended"]) if r["recommended"] in DIFFICULTY_ORDER else 0
        for r in concept_results
        if r["signals"]["eval_count"] > 0
    )

    avg_accuracy   = sum(s["avg_accuracy"]   for s in all_signals) / len(all_signals)
    avg_hints_per_q = sum(s["avg_hints_per_q"] for s in all_signals) / len(all_signals)
    avg_readiness  = sum(s["avg_readiness"]  for s in all_signals) / len(all_signals)
    avg_stability  = sum(s["stability"]      for s in all_signals) / len(all_signals)

    # Collect all unique caution strings across concepts
    all_cautions = []
    for r in concept_results:
        for c in r["cautions"]:
            if c not in all_cautions:
                all_cautions.append(c)

    # Build a clean reason string for parent UI
    independence_pct = round((1 - min(avg_hints_per_q / MAX_HINTS_PER_Q, 1)) * 100)
    if avg_accuracy >= 0.8 and independence_pct >= 70:
        reason = f"Strong recent accuracy ({round(avg_accuracy*100)}%) with low hint usage"
    elif avg_accuracy >= 0.65:
        reason = f"Good accuracy ({round(avg_accuracy*100)}%), building independence"
    elif avg_hints_per_q > 1.5:
        reason = f"Accuracy at {round(avg_accuracy*100)}% but relies heavily on hints"
    else:
        reason = f"Recent accuracy {round(avg_accuracy*100)}% — more practice recommended"

    return {
        "recommended_difficulty": DIFFICULTY_ORDER[best_idx],
        "reason":   reason,
        "cautions": all_cautions,
        "signals": {
            "avg_accuracy":    round(avg_accuracy, 3),
            "avg_hints_per_q": round(avg_hints_per_q, 2),
            "stability":       round(avg_stability, 3),
            "readiness":       round(avg_readiness, 3),
        },
        "concept_count": len(concepts),
        "has_data": True,
    }


# ── Concept-level recommendation for Teach Mode (R5) ─────────────────────────

def get_concept_recommended_difficulty(db, child_id: int, concept_id: int) -> str:
    """
    Return the recommended difficulty string for a single concept.
    Falls back to 'easy' if no data exists.
    Used by teaching_service to pick practice problem difficulty.
    """
    from backend.models.concept_progress import ConceptProgress

    cp = db.query(ConceptProgress).filter(
        ConceptProgress.child_id   == child_id,
        ConceptProgress.concept_id == concept_id,
    ).first()

    # Use stored value if recent, otherwise compute fresh
    if cp and cp.recommended_difficulty:
        return cp.recommended_difficulty

    result = compute_difficulty_for_concept(db, child_id, concept_id, "easy")
    return result["recommended"]
