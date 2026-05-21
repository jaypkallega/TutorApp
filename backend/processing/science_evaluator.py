"""
Science Evaluator — deterministic keyword/rubric-based grading for
conceptual answers in Science, Biology, Chemistry, Physics.

No LLM involvement in correctness determination.
LLM is only called later for feedback text.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def keyword_present(text_norm: str, keyword: str, synonyms: list[str]) -> bool:
    """Check if a keyword or any of its synonyms appear in the text."""
    all_terms = [keyword] + (synonyms or [])
    for term in all_terms:
        term_norm = normalize_text(term)
        # Word boundary matching — "ox" should not match "oxygen"
        if re.search(r'\b' + re.escape(term_norm) + r'\b', text_norm):
            return True
    return False


def evaluate_conceptual(student_answer: str, structured_answer: dict) -> dict:
    """
    Evaluate a science/conceptual answer against a keyword rubric.

    structured_answer must contain:
        rubric: {
            required_concepts: [{keyword, weight, synonyms}, ...],
            optional_concepts: [{keyword, weight, synonyms}, ...],
            min_required_score: int,
            max_score: int
        }

    Returns:
        correct: bool
        status: 'correct' | 'partial' | 'wrong' | 'skipped'
        score: float (0-1)
        confidence: float
        matched_concepts: list of matched keywords
        missing_concepts: list of missing required keywords
    """
    if not student_answer or not student_answer.strip():
        return {
            "correct": False,
            "status": "skipped",
            "score": 0.0,
            "confidence": 0.95,
            "method": "keyword_rubric",
            "matched_concepts": [],
            "missing_concepts": [],
        }

    rubric = structured_answer.get("rubric")
    if not rubric:
        # No rubric — fall through to LLM
        return {
            "correct": None,
            "status": None,
            "score": None,
            "confidence": 0.0,
            "method": "no_rubric",
        }

    text_norm = normalize_text(student_answer)
    required = rubric.get("required_concepts", [])
    optional = rubric.get("optional_concepts", [])
    min_score = rubric.get("min_required_score", 0)
    max_score = rubric.get("max_score", 1)

    matched = []
    missing = []
    total_score = 0

    for concept in required:
        kw = concept.get("keyword", "")
        syns = concept.get("synonyms", [])
        weight = concept.get("weight", 1)
        if keyword_present(text_norm, kw, syns):
            matched.append(kw)
            total_score += weight
        else:
            missing.append(kw)

    for concept in optional:
        kw = concept.get("keyword", "")
        syns = concept.get("synonyms", [])
        weight = concept.get("weight", 1)
        if keyword_present(text_norm, kw, syns):
            matched.append(kw)
            total_score += weight

    # Normalise score to 0-1
    score_ratio = total_score / max_score if max_score > 0 else 0.0
    score_ratio = min(score_ratio, 1.0)

    # Determine status
    if total_score >= min_score and score_ratio >= 0.8:
        status = "correct"
        correct = True
    elif total_score >= min_score * 0.5 and score_ratio >= 0.4:
        status = "partial"
        correct = False
    else:
        status = "wrong"
        correct = False

    # Borderline detection: between 40-70% triggers lower confidence
    borderline = 0.4 <= score_ratio <= 0.7
    confidence = 0.75 if borderline else 0.90

    return {
        "correct": correct,
        "status": status,
        "score": round(score_ratio, 3),
        "confidence": confidence,
        "method": "keyword_rubric",
        "matched_concepts": matched,
        "missing_concepts": missing,
        "total_score": total_score,
        "max_score": max_score,
        "borderline": borderline,
    }


# ---------------------------------------------------------------------------
# Rubric generation helper (called at exercise creation time, not eval time)
# ---------------------------------------------------------------------------

RUBRIC_GENERATION_PROMPT = """\
You are building a keyword rubric for evaluating Grade 8 {subject} answers.

Question: {question}
Expected answer: {expected_answer}

Generate a grading rubric as JSON. Include the key concepts a student MUST mention
for a correct answer, and optional bonus concepts.

Return ONLY this JSON format:
{{
  "required_concepts": [
    {{"keyword": "photosynthesis", "weight": 2, "synonyms": ["food making", "light reaction"]}},
    {{"keyword": "chlorophyll", "weight": 2, "synonyms": ["green pigment"]}},
    {{"keyword": "sunlight", "weight": 1, "synonyms": ["light energy", "solar energy"]}}
  ],
  "optional_concepts": [
    {{"keyword": "oxygen", "weight": 1, "synonyms": ["O2"]}}
  ],
  "min_required_score": 4,
  "max_score": 6
}}

Rules:
- required_concepts: 3-6 key ideas that MUST appear for full credit
- optional_concepts: 1-3 bonus ideas
- weight 2 = core concept, weight 1 = supporting detail
- min_required_score = minimum to be marked correct (usually 60-70% of max)
- max_score = sum of all weights
"""


def generate_rubric_for_question(db, question: str, expected_answer: str, subject: str = "Science") -> Optional[dict]:
    """
    Call LLM once at exercise creation time to generate the keyword rubric.
    Returns the rubric dict or None if generation fails.
    """
    try:
        from backend.services.llm_service import call_llm_json
        messages = [
            {
                "role": "user",
                "content": RUBRIC_GENERATION_PROMPT.format(
                    subject=subject,
                    question=question,
                    expected_answer=expected_answer,
                )
            }
        ]
        rubric = call_llm_json(db, messages, max_tokens=800)
        # Validate structure
        if "required_concepts" in rubric and "max_score" in rubric:
            return rubric
        return None
    except Exception as e:
        logger.error(f"Rubric generation failed: {e}")
        return None
