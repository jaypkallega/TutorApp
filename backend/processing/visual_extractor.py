"""
Visual Extractor — detects and extracts visual content from textbook pages.

For each exercise, determines if it requires a diagram/table/graph to understand,
then extracts structured data that the frontend can render as SVG or HTML.

Visual types handled:
  table       → rows/columns of data rendered as HTML table
  number_line → line with points/arrows rendered as SVG
  bar_graph   → labelled bars rendered as SVG
  geometry    → shapes with measurements rendered as SVG
  page_image  → fallback: store page image reference, display as <img>
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM prompt for visual detection and extraction
# ---------------------------------------------------------------------------

VISUAL_EXTRACT_PROMPT = """\
You are analysing a page from a Grade {grade} {subject} textbook.

Look at the exercise/question provided and the page image.
Determine if this exercise REQUIRES a visual element (table, diagram, graph, number line) to understand or solve.

If NO visual is needed, return: {{"has_visual": false}}

If YES, extract the visual as structured JSON:

For a TABLE:
{{"has_visual": true, "type": "table", "title": "optional title", "headers": ["Col1", "Col2"], "rows": [["a", "b"], ["c", "d"]]}}

For a NUMBER LINE:
{{"has_visual": true, "type": "number_line", "min": -10, "max": 10, "marked_points": [{{"value": 3, "label": "A"}}, {{"value": -5, "label": "B"}}], "arrows": []}}

For a BAR GRAPH:
{{"has_visual": true, "type": "bar_graph", "title": "Graph title", "x_label": "Category", "y_label": "Value", "bars": [{{"label": "A", "value": 10}}, {{"label": "B", "value": 20}}]}}

For a GEOMETRIC FIGURE (triangle, polygon, angle diagram):
{{"has_visual": true, "type": "geometry", "shape": "triangle", "description": "Triangle ABC with AB=5cm, BC=7cm, angle B=60°", "measurements": [{{"label": "AB", "value": "5 cm"}}, {{"label": "angle B", "value": "60°"}}]}}

For a PIE CHART:
{{"has_visual": true, "type": "pie_chart", "title": "title", "slices": [{{"label": "A", "value": 30}}, {{"label": "B", "value": 70}}]}}

For anything else you cannot reconstruct structurally:
{{"has_visual": true, "type": "page_image", "description": "brief description of what the visual shows"}}

Return ONLY valid JSON. No explanation.
Exercise text: {exercise_text}
"""


def extract_visual_for_exercise(
    db,
    exercise_prompt: str,
    page_image_path: Optional[str],
    subject: str = "Mathematics",
    grade: int = 8,
) -> dict:
    """
    Call LLM vision to detect and extract visual content for one exercise.
    Returns visual dict or {} if no visual needed.
    """
    if not page_image_path or not Path(page_image_path).exists():
        return _text_only_visual_detection(db, exercise_prompt, subject, grade)

    try:
        import litellm
        import base64
        from backend.services.llm_service import _get_llm_settings, _build_model_string

        cfg = _get_llm_settings(db)
        provider = cfg.get("llm_provider", "openai")
        api_key = cfg.get("llm_api_key", "")
        model = cfg.get("llm_model_name", "gpt-4o")
        base_url = cfg.get("llm_base_url") or None

        if not api_key:
            return {}

        with open(page_image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        model_str = _build_model_string(provider, model)
        prompt = VISUAL_EXTRACT_PROMPT.format(
            grade=grade, subject=subject, exercise_text=exercise_prompt
        )

        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }]

        kwargs = {"model": model_str, "messages": messages, "api_key": api_key, "max_tokens": 600}
        if base_url:
            kwargs["base_url"] = base_url

        response = litellm.completion(**kwargs)
        text = response.choices[0].message.content.strip()

        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        result = json.loads(text)
        if not result.get("has_visual", False):
            return {}
        result.pop("has_visual", None)
        return result

    except Exception as e:
        logger.warning(f"Visual extraction failed: {e}")
        return {}


def _text_only_visual_detection(db, exercise_prompt: str, subject: str, grade: int) -> dict:
    """
    Fallback: detect visual need from text only (no image available).
    Used when page images haven't been generated yet.
    """
    try:
        from backend.services.llm_service import call_llm_json

        prompt = VISUAL_EXTRACT_PROMPT.format(
            grade=grade, subject=subject, exercise_text=exercise_prompt
        )
        result = call_llm_json(db, [{"role": "user", "content": prompt + "\n\n(No image available — infer from text only.)"}], max_tokens=400)
        if not result.get("has_visual", False):
            return {}
        result.pop("has_visual", None)
        return result
    except Exception as e:
        logger.warning(f"Text-only visual detection failed: {e}")
        return {}


def get_page_image_path(textbook_id: int, page_number: int) -> Optional[str]:
    """Return the path to a stored page image if it exists."""
    from backend.config import PAGE_IMAGES_DIR
    page_dir = PAGE_IMAGES_DIR / f"textbook_{textbook_id}"
    path = page_dir / f"page_{page_number:04d}.png"
    if path.exists():
        return str(path)
    # Try jpg
    path_jpg = page_dir / f"page_{page_number:04d}.jpg"
    if path_jpg.exists():
        return str(path_jpg)
    return None
