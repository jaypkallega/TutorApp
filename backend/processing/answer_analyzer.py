"""
Answer Analyzer — processes student submissions through the hybrid evaluation pipeline.

Flow:
  1. Extract text from submission (OCR for canvas/image, direct for text)
  2. For each question, call evaluator.evaluate_single_answer()
  3. Deterministic layer handles typed math answers (SymPy)
  4. Keyword rubric handles science conceptual answers
  5. LLM called ONLY for: feedback text + canvas/image correctness
  6. Save Evaluation with confidence scores and parent review flags
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def canvas_json_to_image(canvas_json: str, output_path: str) -> str:
    import json as _json
    from PIL import Image, ImageDraw
    data = _json.loads(canvas_json)
    strokes = data.get("strokes", [])
    all_x = [p["x"] for s in strokes for p in s.get("points", [])]
    all_y = [p["y"] for s in strokes for p in s.get("points", [])]
    if not all_x:
        img = Image.new("RGB", (800, 400), "white")
        img.save(output_path)
        return output_path
    width = max(int(max(all_x)) + 20, 100)
    height = max(int(max(all_y)) + 20, 100)
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    for stroke in strokes:
        points = stroke.get("points", [])
        color = stroke.get("color", "#000000")
        line_width = max(int(stroke.get("width", 2)), 1)
        if len(points) >= 2:
            coords = [(p["x"], p["y"]) for p in points]
            draw.line(coords, fill=color, width=line_width, joint="curve")
        elif len(points) == 1:
            p = points[0]
            r = line_width
            draw.ellipse([p["x"]-r, p["y"]-r, p["x"]+r, p["y"]+r], fill=color)
    img.save(output_path)
    return output_path


def process_submission(
    db,
    submission_id: int,
    exercises: list[dict],
    show_wrong_reasons: bool = True,
    draft_answers: dict = None,   # raw answers JSON from draft (for hints_used)
) -> None:
    from backend.models.submission import Submission
    from backend.models.evaluation import Evaluation
    from backend.services.ocr_service import extract_text_from_image, get_ocr_mode
    from backend.processing.evaluator import evaluate_single_answer
    from backend.processing.misconception_matcher import seed_misconceptions
    from backend.database import SessionLocal
    from backend.config import SUBMISSIONS_DIR

    session = SessionLocal()

    def update_status(status: str):
        sub = session.query(Submission).filter(Submission.id == submission_id).first()
        if sub:
            sub.processing_status = status
            session.commit()

    try:
        update_status("processing")
        seed_misconceptions(session)

        sub = session.query(Submission).filter(Submission.id == submission_id).first()
        if not sub:
            logger.error(f"Submission {submission_id} not found")
            return

        input_mode = sub.input_mode
        ocr_mode = get_ocr_mode(session)

        # Step 1: Extract text per question
        if input_mode == "text":
            raw_text = sub.text_answer or ""
            try:
                parsed = json.loads(raw_text)
                per_question_answers = [str(a) for a in parsed] if isinstance(parsed, list) else [raw_text] * len(exercises)
            except (json.JSONDecodeError, TypeError):
                per_question_answers = [raw_text] * len(exercises)
        elif input_mode == "canvas" and sub.canvas_json:
            img_path = str(SUBMISSIONS_DIR / f"canvas_{submission_id}.png")
            canvas_json_to_image(sub.canvas_json, img_path)
            raw_text = extract_text_from_image(img_path, db=session, mode=ocr_mode)
            per_question_answers = [raw_text] * len(exercises)
        elif input_mode == "image_upload" and sub.image_path:
            raw_text = extract_text_from_image(sub.image_path, db=session, mode=ocr_mode)
            per_question_answers = [raw_text] * len(exercises)
        else:
            per_question_answers = [""] * len(exercises)

        while len(per_question_answers) < len(exercises):
            per_question_answers.append("")
        per_question_answers = per_question_answers[:len(exercises)]

        # Step 2: Evaluate each answer through hybrid pipeline
        per_question_results = []
        correct = wrong = skipped = 0
        all_confidences = []
        low_confidence_qs = []

        for i, (exercise, student_ans) in enumerate(zip(exercises, per_question_answers)):
            result = evaluate_single_answer(
                db=session,
                student_answer=student_ans,
                exercise=exercise,
                submission_id=submission_id,
                child_id=sub.child_id,
                show_wrong_reasons=show_wrong_reasons,
                input_mode=input_mode,
            )
            result["question_index"] = i
            # Attach hints_used from draft if available
            if draft_answers:
                ex_entry = draft_answers.get(str(exercise.get("id", "")), {})
                result["hints_used"] = ex_entry.get("hints_used", 0)
            else:
                result["hints_used"] = 0
            status = result.get("status", "skipped")
            if status == "correct":
                correct += 1
            elif status in ("wrong", "partial"):
                wrong += 1
            else:
                skipped += 1
            q_confidence = result.get("confidence", 1.0)
            all_confidences.append(q_confidence)
            if result.get("requires_parent_review"):
                low_confidence_qs.append(i)
            per_question_results.append(result)

        # Step 3: Overall summary via LLM (summary only)
        overall_feedback = _generate_overall_feedback(session, correct, len(exercises), per_question_results)

        # Step 4: Aggregate confidence
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 1.0
        requires_parent_review = bool(low_confidence_qs)

        # Step 5: Save evaluation
        evaluation = Evaluation(
            submission_id=submission_id,
            total_questions=len(exercises),
            correct_count=correct,
            wrong_count=wrong,
            skipped_count=skipped,
            per_question=json.dumps(per_question_results),
            overall_feedback=overall_feedback,
            confidence=round(avg_confidence, 3),
            requires_parent_review=requires_parent_review,
            low_confidence_questions=json.dumps(low_confidence_qs) if low_confidence_qs else None,
            evaluated_by="hybrid",
        )
        session.add(evaluation)
        update_status("done")
        session.commit()
        logger.info(f"Submission {submission_id}: {correct}/{len(exercises)} correct, conf={avg_confidence:.2f}")

        # Update adaptive difficulty recommendations for all concepts
        try:
            from backend.processing.adaptive import update_all_concept_difficulties
            sub = session.query(Submission).filter(Submission.id == submission_id).first()
            if sub:
                update_all_concept_difficulties(session, sub.child_id)
        except Exception as ae:
            logger.warning(f"Adaptive difficulty update failed (non-critical): {ae}")

    except Exception as e:
        logger.error(f"Answer analysis failed for submission {submission_id}: {e}", exc_info=True)
        update_status("error")
    finally:
        session.close()


def _generate_overall_feedback(session, correct: int, total: int, results: list[dict]) -> str:
    try:
        from backend.services.llm_service import call_llm
        score_pct = round(correct / total * 100) if total > 0 else 0
        misconceptions_found = []
        for r in results:
            for m in r.get("misconceptions", []):
                if m["diagnosis"] not in misconceptions_found:
                    misconceptions_found.append(m["diagnosis"])
        misconception_note = f" Recurring pattern: {'; '.join(misconceptions_found[:2])}." if misconceptions_found else ""
        system = "You are a friendly Grade 8 tutor. Write ONE encouraging sentence summarising performance. Do not list questions."
        user = f"Score: {correct}/{total} ({score_pct}%).{misconception_note} Write a brief encouraging summary:"
        return call_llm(session, [{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=80, temperature=0.5)
    except Exception:
        score_pct = round(correct / total * 100) if total > 0 else 0
        if score_pct >= 80: return "Excellent work! Keep it up!"
        elif score_pct >= 50: return "Good effort! Review the questions you missed and try again."
        else: return "Keep practising — every attempt helps you improve!"
