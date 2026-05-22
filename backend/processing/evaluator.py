"""
Evaluator — master routing layer.

Routes each answer through the correct evaluation pipeline:
  1. Determine input source (text typed / OCR from canvas or image)
  2. Detect answer type from structured_answer
  3. Route to deterministic evaluator (SymPy / keyword rubric / step validator)
  4. If deterministic succeeds with high confidence → done
  5. If confidence low or type is conceptual-without-rubric → escalate to LLM feedback
  6. Match misconceptions
  7. Build final result with confidence score and parent review flag

The LLM is NEVER the authority on correctness.
It is only called to write feedback text after correctness is decided.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Confidence threshold below which we flag for parent review
PARENT_REVIEW_THRESHOLD = 0.60


def evaluate_single_answer(
    db,
    student_answer: str,
    exercise: dict,
    submission_id: int,
    child_id: int,
    show_wrong_reasons: bool = True,
    input_mode: str = "text",
) -> dict:
    """
    Evaluate one student answer against one exercise.

    exercise dict must have:
        id, prompt, expected_answer, structured_answer (JSON string or dict)

    Returns:
        {
          question_index, exercise_id,
          status: correct|wrong|partial|skipped,
          ocr_text, feedback, correct_answer, marks,
          confidence, requires_parent_review,
          misconceptions: [...],
          method: sympy|keyword_rubric|step_validator|llm_fallback|skipped,
        }
    """
    from backend.processing.math_evaluator import evaluate_math_answer, detect_answer_type
    from backend.processing.step_validator import evaluate_multi_step, split_into_steps
    from backend.processing.science_evaluator import evaluate_conceptual
    from backend.processing.misconception_matcher import match_misconceptions, log_misconception

    exercise_id = exercise.get("id", 0)
    prompt = exercise.get("prompt", "")
    expected_freeform = exercise.get("expected_answer", "")

    # Parse structured_answer
    structured_raw = exercise.get("structured_answer")
    structured: dict = {}
    if structured_raw:
        try:
            structured = json.loads(structured_raw) if isinstance(structured_raw, str) else structured_raw
        except (json.JSONDecodeError, TypeError):
            structured = {}

    answer_type = structured.get("answer_type", "unknown")

    # --- Handle blank/skipped ---
    if not student_answer or not student_answer.strip():
        return _build_result(
            exercise_id=exercise_id,
            status="skipped",
            correct=False,
            marks=0.0,
            confidence=1.0,
            method="skipped",
            ocr_text=student_answer,
            feedback="No answer provided for this question.",
            correct_answer=expected_freeform if show_wrong_reasons else None,
            misconceptions=[],
            requires_review=False,
        )

    # --- Route by answer type ---
    eval_result = None
    method = "unknown"

    if answer_type == "mcq":
        # Multiple-choice: simple letter comparison
        correct_opt = structured.get("correct_option", "").strip().upper()
        student_opt = student_answer.strip().upper()
        correct = (student_opt == correct_opt)
        eval_result = {
            "correct": correct,
            "confidence": 0.99,  # deterministic — no ambiguity
            "status": "correct" if correct else "wrong",
            "method": "mcq_exact",
        }
        method = "mcq_exact"

    elif answer_type in ("numeric", "fraction", "algebraic", "equation", "expression_set"):
        eval_result = evaluate_math_answer(student_answer, structured)
        method = eval_result.get("method", "sympy")

    elif answer_type == "multi_step":
        steps = split_into_steps(student_answer)
        if len(steps) >= 2:
            eval_result = evaluate_multi_step(student_answer, structured)
            method = "step_validator"
        else:
            # Single line — treat as equation/algebraic
            eval_result = evaluate_math_answer(student_answer, structured)
            method = eval_result.get("method", "sympy")

    elif answer_type == "conceptual":
        eval_result = evaluate_conceptual(student_answer, structured)
        method = "keyword_rubric"

    else:
        # Unknown type — try to auto-detect
        detected = detect_answer_type(student_answer)
        if detected in ("numeric", "fraction", "algebraic", "equation"):
            # Build minimal structured_answer from expected
            auto_structured = {
                "answer_type": detected,
                "sympy_expr": expected_freeform or "",
                "tolerance": 0.01,
            }
            eval_result = evaluate_math_answer(student_answer, auto_structured)
            method = eval_result.get("method", "auto_detect")
        else:
            eval_result = None
            method = "unknown"

    # --- Determine if we need LLM fallback ---
    confidence = eval_result.get("confidence", 0.0) if eval_result else 0.0
    correct = eval_result.get("correct") if eval_result else None
    needs_llm = (
        eval_result is None
        or correct is None
        or confidence < PARENT_REVIEW_THRESHOLD
        or answer_type == "conceptual" and eval_result.get("borderline", False)
    )

    # For canvas/image inputs, OCR is already done — but confidence may be low
    # In that case always use LLM as fallback for correctness
    if input_mode in ("canvas", "image_upload"):
        needs_llm = True  # OCR output needs LLM to interpret
        confidence = min(confidence, 0.7)

    # --- LLM fallback for correctness (canvas/image or unknown type) ---
    if needs_llm and input_mode in ("canvas", "image_upload"):
        llm_result = _llm_evaluate_single(db, prompt, student_answer, expected_freeform, show_wrong_reasons)
        if correct is None:
            # LLM is the only judge here
            correct = llm_result.get("correct", False)
            method = "llm_fallback"
            confidence = 0.75  # LLM result — lower than deterministic
        # Merge feedback
        feedback_text = llm_result.get("feedback", "")
    else:
        feedback_text = None

    # --- Determine final status ---
    if eval_result and eval_result.get("status"):
        status = eval_result["status"]
    elif correct is True:
        status = "correct"
    elif correct is False:
        status = "wrong"
    else:
        status = "skipped"

    # Marks
    marks = 1.0 if status == "correct" else (0.5 if status == "partial" else 0.0)

    # --- Generate targeted feedback via LLM (feedback-only, not correctness) ---
    if feedback_text is None:
        error_desc = eval_result.get("error_description", "") if eval_result else ""
        feedback_text = _generate_feedback(
            db=db,
            status=status,
            prompt=prompt,
            student_answer=student_answer,
            expected_answer=expected_freeform if show_wrong_reasons else None,
            error_description=error_desc,
            eval_detail=eval_result or {},
        )

    # --- Misconception matching ---
    misconceptions = []
    if status in ("wrong", "partial"):
        error_desc = eval_result.get("error_description", "") if eval_result else ""
        subject = exercise.get("subject", "Mathematics")
        misconceptions = match_misconceptions(db, student_answer, error_desc, subject)
        for m in misconceptions:
            try:
                log_misconception(db, child_id, m["id"], exercise_id, submission_id, student_answer)
            except Exception as e:
                logger.warning(f"Could not log misconception: {e}")

    requires_review = confidence < PARENT_REVIEW_THRESHOLD

    return _build_result(
        exercise_id=exercise_id,
        status=status,
        correct=correct or False,
        marks=marks,
        confidence=confidence,
        method=method,
        ocr_text=student_answer,
        feedback=feedback_text,
        correct_answer=expected_freeform if show_wrong_reasons else None,
        misconceptions=misconceptions,
        requires_review=requires_review,
    )


def _build_result(
    exercise_id, status, correct, marks, confidence, method,
    ocr_text, feedback, correct_answer, misconceptions, requires_review,
) -> dict:
    return {
        "exercise_id": exercise_id,
        "status": status,
        "correct": correct,
        "marks": marks,
        "confidence": round(confidence, 3),
        "method": method,
        "ocr_text": ocr_text,
        "feedback": feedback,
        "correct_answer": correct_answer,
        "misconceptions": misconceptions,
        "requires_parent_review": requires_review,
    }


def _generate_feedback(
    db,
    status: str,
    prompt: str,
    student_answer: str,
    expected_answer: Optional[str],
    error_description: str,
    eval_detail: dict,
) -> Optional[str]:
    """
    Call LLM only to generate the feedback text.
    Correctness is already determined — LLM cannot change the grade.
    """
    try:
        from backend.services.llm_service import call_llm

        # Build a tight, constrained prompt
        if status == "correct":
            return None  # No feedback needed for correct answers

        misconception_hint = ""
        if eval_detail.get("missing_concepts"):
            missing = ", ".join(eval_detail["missing_concepts"][:3])
            misconception_hint = f"\nThe student's answer is missing these key concepts: {missing}."

        if eval_detail.get("first_error_step"):
            error_info = f"\nThe error occurred at step: '{eval_detail['first_error_step']}'. {error_description}"
        else:
            error_info = f"\n{error_description}" if error_description else ""

        system = (
            "You are a Grade 8 tutor writing feedback. "
            "Correctness has ALREADY been determined by a mathematical engine — do NOT re-evaluate. "
            "Write ONE to THREE sentences of encouraging, specific feedback explaining the mistake. "
            "Do not give the full solution. Guide the student to the next step."
        )
        user = (
            f"Question: {prompt}\n"
            f"Student answered: {student_answer}\n"
            f"Result: {status.upper()}"
            + (f"\nCorrect answer: {expected_answer}" if expected_answer else "")
            + error_info
            + misconception_hint
            + "\n\nWrite the feedback now:"
        )
        return call_llm(db, [{"role": "system", "content": system}, {"role": "user", "content": user}],
                        max_tokens=200, temperature=0.4)
    except Exception as e:
        logger.warning(f"Feedback generation failed: {e}")
        return None


def _llm_evaluate_single(
    db,
    prompt: str,
    student_answer: str,
    expected_answer: str,
    show_wrong_reasons: bool,
) -> dict:
    """
    LLM evaluation for canvas/image input where deterministic eval cannot run.
    Returns {correct: bool, feedback: str}.
    """
    try:
        from backend.services.llm_service import call_llm_json
        system = (
            "You are evaluating a Grade 8 student's handwritten answer that was read by OCR. "
            "The OCR may have introduced errors — be lenient with formatting. "
            "Return ONLY JSON: {\"correct\": true/false, \"status\": \"correct|wrong|partial|skipped\", "
            "\"feedback\": \"one sentence\"}"
        )
        user = (
            f"Question: {prompt}\n"
            f"OCR-extracted student answer: {student_answer}\n"
            f"Expected answer: {expected_answer or 'Not provided'}\n"
            "Evaluate and return JSON only."
        )
        result = call_llm_json(db, [{"role": "system", "content": system}, {"role": "user", "content": user}],
                               max_tokens=200)
        return {
            "correct": result.get("status") == "correct",
            "status": result.get("status", "wrong"),
            "feedback": result.get("feedback", ""),
        }
    except Exception as e:
        logger.error(f"LLM single eval failed: {e}")
        return {"correct": False, "status": "wrong", "feedback": ""}
