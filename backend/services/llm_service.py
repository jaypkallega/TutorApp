"""
LLM Service — wraps LiteLLM for unified access to OpenAI / Anthropic / Gemini.
All prompts are Grade 8 Mathematics (CBSE) focused.
"""

import json
import logging
from typing import Optional, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _get_llm_settings(db: Session) -> dict:
    """Read LLM config from DB settings table."""
    from backend.models.settings import AppSetting
    rows = db.query(AppSetting).filter(
        AppSetting.key.in_(["llm_provider", "llm_api_key", "llm_model_name", "llm_base_url"])
    ).all()
    cfg = {r.key: r.value for r in rows}
    return cfg


def _build_model_string(provider: str, model: str) -> str:
    """
    LiteLLM expects 'provider/model' for non-openai providers.
    OpenAI models are passed as-is.
    """
    provider = (provider or "openai").lower()
    if provider == "openai":
        return model
    return f"{provider}/{model}"


def call_llm(
    db: Session,
    messages: list[dict],
    max_tokens: int = 2000,
    temperature: float = 0.3,
    json_mode: bool = False,
) -> str:
    """
    Core LLM call. Returns the text content of the first choice.
    Raises an exception on failure (caller handles it).
    """
    import litellm

    cfg = _get_llm_settings(db)
    provider = cfg.get("llm_provider", "openai")
    api_key = cfg.get("llm_api_key", "")
    model = cfg.get("llm_model_name", "gpt-4o")
    base_url = cfg.get("llm_base_url") or None

    if not api_key:
        raise ValueError("No LLM API key configured. Go to Settings to add your key.")

    model_str = _build_model_string(provider, model)

    kwargs: dict[str, Any] = {
        "model": model_str,
        "messages": messages,
        "api_key": api_key,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if base_url:
        kwargs["base_url"] = base_url
    if json_mode and provider == "openai":
        kwargs["response_format"] = {"type": "json_object"}

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content


def call_llm_json(db: Session, messages: list[dict], max_tokens: int = 2000) -> dict:
    """Call LLM and parse JSON from the response."""
    text = call_llm(db, messages, max_tokens=max_tokens, json_mode=True)
    # Strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


# ---------------------------------------------------------------------------
# Textbook analysis
# ---------------------------------------------------------------------------

STRUCTURE_PROMPT_TEMPLATE = """\
You are a Grade 8 Mathematics curriculum expert.
You will receive extracted text from pages of a math textbook.
Your job is to identify the structure: chapters, their page ranges, key concepts, and exercises.

Return ONLY valid JSON in this exact format:
{
  "chapters": [
    {
      "chapter_number": 1,
      "title": "Rational Numbers",
      "start_page": 1,
      "end_page": 20,
      "summary": "Brief summary of what this chapter covers",
      "concepts": [
        {
          "name": "Properties of Rational Numbers",
          "explanation": "Clear explanation for a Grade 8 student",
          "textbook_method": "How the textbook teaches it",
          "alternate_method": "An alternate approach if applicable",
          "difficulty_hint": "Common misconceptions or tricky parts",
          "page_start": 2,
          "page_end": 5
        }
      ],
      "exercises": [
        {
          "prompt": "Exact question text",
          "difficulty": "easy|medium|hard",
          "type": "calculation|word_problem|proof",
          "expected_answer": "Answer if visible",
          "page": 10
        }
      ]
    }
  ]
}
"""


def analyze_textbook_structure(db: Session, page_texts: list[str], subject: str = "Mathematics", grade: int = 8) -> dict:
    """
    Send page texts to LLM and get back structured chapters/concepts/exercises.
    For large books, this is called in chunks.
    """
    combined = "\n\n--- PAGE BREAK ---\n\n".join(
        f"[Page {i+1}]\n{t}" for i, t in enumerate(page_texts)
    )
    # Truncate to avoid token limits
    if len(combined) > 80000:
        combined = combined[:80000] + "\n...[truncated]"

    prompt = STRUCTURE_PROMPT_TEMPLATE.replace("{grade}", str(grade)).replace("{subject}", subject)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Analyze this textbook content:\n\n{combined}"},
    ]
    return call_llm_json(db, messages, max_tokens=4000)


# ---------------------------------------------------------------------------
# Exercise generation
# ---------------------------------------------------------------------------

GENERATE_EXERCISES_PROMPT = """\
You are a Grade 8 Mathematics teacher creating practice exercises.
Create original math exercises for the given concept and difficulty.
Return ONLY valid JSON:
{
  "exercises": [
    {
      "prompt": "Full question text — be specific and clear",
      "difficulty": "easy|medium|hard",
      "type": "calculation|word_problem|proof",
      "expected_answer": "Complete worked answer",
      "expected_method": "Step-by-step method to solve"
    }
  ]
}
"""


def generate_exercises(
    db: Session,
    chapter_title: str,
    concept_name: str,
    concept_explanation: str,
    difficulty: str,
    count: int = 5,
    subject: str = "Mathematics",
) -> list[dict]:
    messages = [
        {"role": "system", "content": GENERATE_EXERCISES_PROMPT},
        {
            "role": "user",
            "content": (
                f"Chapter: {chapter_title}\n"
                f"Concept: {concept_name}\n"
                f"Explanation: {concept_explanation}\n"
                f"Difficulty: {difficulty}\n"
                f"Generate {count} unique exercises."
            ),
        },
    ]
    result = call_llm_json(db, messages, max_tokens=3000)
    return result.get("exercises", [])


# ---------------------------------------------------------------------------
# Concept explanation (for child's Learn Mode)
# ---------------------------------------------------------------------------

def explain_concept(
    db: Session,
    concept_name: str,
    explanation: str,
    question: Optional[str] = None,
    subject: str = "Mathematics",
) -> str:
    """Generate a friendly, step-by-step explanation for a Grade 8 student."""
    system = (
        f"You are a friendly, patient Grade 8 {subject} tutor. "
        "Explain concepts clearly with examples. Use simple language. "
        "Never just give answers — guide the student to understand."
    )
    user_msg = f"Concept: {concept_name}\n\nBase explanation: {explanation}"
    if question:
        user_msg += f"\n\nStudent's question: {question}"
    else:
        user_msg += "\n\nPlease give a clear, engaging explanation with a worked example."

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]
    return call_llm(db, messages, max_tokens=1000, temperature=0.5)


# ---------------------------------------------------------------------------
# Answer evaluation
# ---------------------------------------------------------------------------

EVALUATE_PROMPT = """\
You are a Grade 8 Mathematics teacher evaluating a student's handwritten/typed answers.
You will receive the exercise prompts and the student's OCR-extracted or typed answers.
Evaluate each answer and return ONLY valid JSON:
{
  "results": [
    {
      "question_index": 0,
      "status": "correct|wrong|partial|skipped",
      "feedback": "Specific, encouraging feedback. For wrong answers, explain the mistake.",
      "marks": 1.0
    }
  ],
  "overall_feedback": "Brief overall encouragement and summary."
}
Status rules:
- correct: fully correct answer and method
- partial: right approach but arithmetic/minor error
- wrong: fundamentally wrong approach
- skipped: blank or illegible
Marks: 1.0 for correct, 0.5 for partial, 0 for wrong/skipped.
"""


def evaluate_submission(
    db: Session,
    exercises: list[dict],
    ocr_results: list[str],
    show_wrong_reasons: bool = True,
) -> dict:
    """
    Evaluate a student's answers against the exercise expected answers.
    exercises: list of {prompt, expected_answer, expected_method}
    ocr_results: list of strings (one per question, from OCR or text input)
    """
    qa_pairs = []
    for i, (ex, ans) in enumerate(zip(exercises, ocr_results)):
        qa_pairs.append(
            f"Q{i+1}: {ex['prompt']}\n"
            f"Expected: {ex.get('expected_answer', 'N/A')}\n"
            f"Student wrote: {ans or '[blank]'}"
        )

    messages = [
        {"role": "system", "content": EVALUATE_PROMPT},
        {
            "role": "user",
            "content": (
                f"Evaluate these {len(exercises)} answers:\n\n"
                + "\n\n".join(qa_pairs)
                + (
                    "\n\nNote: Do NOT reveal the expected answers in feedback."
                    if not show_wrong_reasons
                    else ""
                )
            ),
        },
    ]
    return call_llm_json(db, messages, max_tokens=2000)


# ---------------------------------------------------------------------------
# LLM connection test
# ---------------------------------------------------------------------------

def test_connection(db: Session) -> dict:
    import time
    start = time.time()
    try:
        response = call_llm(
            db,
            [{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=5,
        )
        latency_ms = int((time.time() - start) * 1000)
        cfg = _get_llm_settings(db)
        return {
            "success": True,
            "provider": cfg.get("llm_provider", "openai"),
            "model": cfg.get("llm_model_name", "gpt-4o"),
            "latency_ms": latency_ms,
            "message": f"Connection successful. Response: {response.strip()}",
        }
    except Exception as e:
        cfg = _get_llm_settings(db)
        return {
            "success": False,
            "provider": cfg.get("llm_provider", "openai"),
            "model": cfg.get("llm_model_name", "gpt-4o"),
            "latency_ms": None,
            "message": str(e),
        }


# ---------------------------------------------------------------------------
# Step 2: Structured answer generation (called at exercise creation time)
# ---------------------------------------------------------------------------

STRUCTURED_ANSWER_PROMPT = """\
You are building a structured answer schema for a Grade {grade} {subject} exercise.

Question: {question}
Expected answer (freeform): {expected_answer}
Subject: {subject}
Exercise type: {exercise_type}

Analyse the answer and return ONLY valid JSON in exactly this format:

For numeric answers (single number result):
{{"answer_type": "numeric", "canonical_value": "42", "sympy_expr": "42", "tolerance": 0.01, "unit": "cm"}}

For fractions:
{{"answer_type": "fraction", "canonical_value": "3/4", "sympy_expr": "3/4", "tolerance": 0.001, "unit": null}}

For algebraic expressions:
{{"answer_type": "algebraic", "canonical_value": "2x + 3", "sympy_expr": "2*x + 3", "tolerance": null, "unit": null}}

For equations (solving for variable):
{{"answer_type": "equation", "canonical_value": "x = 5", "sympy_expr": "x - 5", "tolerance": null, "unit": null}}

For sets of roots/solutions:
{{"answer_type": "expression_set", "canonical_value": "{{2, -3}}", "sympy_expr": "{{2, -3}}", "tolerance": null, "unit": null}}

For multi-step working problems:
{{"answer_type": "multi_step", "canonical_value": "x = 2", "sympy_expr": "2", "steps": ["2(x+3)=10", "2x+6=10", "2x=4", "x=2"], "tolerance": null, "unit": null}}

For science/conceptual answers:
{{"answer_type": "conceptual", "canonical_value": "brief answer", "rubric": {{"required_concepts": [{{"keyword": "photosynthesis", "weight": 2, "synonyms": ["food making"]}}], "optional_concepts": [], "min_required_score": 3, "max_score": 4}}, "sympy_expr": null, "tolerance": null}}

Rules:
- sympy_expr must be parseable by Python SymPy (use * for multiplication, ** for power)
- For equations, sympy_expr is the expression equal to zero (move everything to LHS)
- tolerance: use 0.01 for integers, 0.001 for decimals, null for symbolic
- Return ONLY the JSON object, no explanation
"""


def generate_structured_answer(
    db,
    question: str,
    expected_answer: str,
    subject: str = "Mathematics",
    exercise_type: str = "calculation",
    grade: int = 8,
) -> dict:
    """
    Generate a structured answer schema for deterministic evaluation.
    Called once at exercise creation — never at evaluation time.
    """
    try:
        messages = [
            {
                "role": "user",
                "content": STRUCTURED_ANSWER_PROMPT.format(
                    grade=grade,
                    subject=subject,
                    question=question,
                    expected_answer=expected_answer,
                    exercise_type=exercise_type,
                )
            }
        ]
        result = call_llm_json(db, messages, max_tokens=500)
        # Validate required field
        if "answer_type" not in result:
            return {}
        return result
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Structured answer generation failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Hint generation (used during SolveWorkspace — Socratic, never gives answer)
# ---------------------------------------------------------------------------

HINT_PROMPT = """\
You are a patient, encouraging Grade 8 tutor helping a student who is stuck.
The student has asked for hint #{hint_number} of 3 for this question.

QUESTION: {question}
EXPECTED ANSWER (do NOT reveal this): {expected_answer}
STUDENT'S CURRENT ATTEMPT (may be empty): {current_answer}

STRICT RULES — never break these:
1. NEVER give the answer, any part of the answer, or a formula that directly solves it.
2. Give EXACTLY ONE guiding nudge — one question or one observation. Not two.
3. Maximum 2 sentences total. Short is better.
4. Hint 1 → point the student toward the right concept, method, or formula name only.
   Hint 2 → describe the very first step they should take, phrased as a question.
   Hint 3 → if the student has a current attempt, identify the specific part that is wrong;
             if no attempt, give a tiny concrete example using different numbers.
5. Use friendly, encouraging language suitable for a 13-year-old.
6. Do NOT start with "Hint:" or a number. Just the nudge itself.
"""


def generate_hint(
    db: Session,
    question_prompt: str,
    expected_answer: str,
    hint_number: int,
    current_answer: str = "",
) -> str:
    """
    Generate a Socratic hint for a student who is stuck on a question.
    hint_number: 1, 2, or 3 — controls the specificity of the hint.
    Never reveals the answer — enforced by the prompt.
    """
    prompt = (
        HINT_PROMPT
        .replace("{hint_number}", str(hint_number))
        .replace("{question}", question_prompt)
        .replace("{expected_answer}", expected_answer or "(not specified)")
        .replace("{current_answer}", current_answer.strip() if current_answer else "(no attempt yet)")
    )
    try:
        return call_llm(
            db,
            [{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.4,
        ).strip()
    except Exception as e:
        logger.warning(f"Hint generation failed: {e}")
        # Fallback hints that never give the answer
        fallbacks = [
            "Think about which formula or concept from this chapter applies here.",
            "What is the very first operation you need to do? Write just that step first.",
            "Check your working carefully — does each step follow logically from the one before?",
        ]
        return fallbacks[min(hint_number - 1, 2)]
