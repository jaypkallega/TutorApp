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

If YES, extract the visual as structured JSON. Choose the BEST matching type below:

━━ TABLE ━━
{{"has_visual": true, "type": "table", "title": "optional title",
  "headers": ["Col1", "Col2"], "rows": [["a", "b"], ["c", "d"]]}}

━━ NUMBER LINE ━━
{{"has_visual": true, "type": "number_line", "min": -10, "max": 10,
  "marked_points": [{{"value": 3, "label": "A"}}, {{"value": -5, "label": "B"}}], "arrows": []}}

━━ BAR GRAPH ━━
{{"has_visual": true, "type": "bar_graph", "title": "Graph title",
  "x_label": "Category", "y_label": "Value",
  "bars": [{{"label": "A", "value": 10}}, {{"label": "B", "value": 20}}]}}

━━ PIE CHART ━━
{{"has_visual": true, "type": "pie_chart", "title": "title",
  "slices": [{{"label": "A", "value": 30}}, {{"label": "B", "value": 70}}]}}

━━ COORDINATE AXES / GRAPH (points on x-y grid) ━━
Use this when the question involves plotting points, drawing shapes on a grid, or coordinate geometry.
{{"has_visual": true, "type": "axes",
  "x_min": -5, "x_max": 10, "y_min": -5, "y_max": 10,
  "points": [{{"x": 3, "y": 4, "label": "A"}}, {{"x": -2, "y": 1, "label": "B"}}],
  "segments": [{{"from": [0, 0], "to": [3, 4], "label": "OA", "dashed": false}}],
  "polygon_points": [[2, 3], [-1, 4], [0, -2]],
  "description": "Coordinate plane with points A(3,4) and B(-2,1)"}}
Notes:
  - Set x_min/x_max/y_min/y_max to fit all points with a small margin.
  - polygon_points: list of [x,y] forming a closed shape — use null if no polygon.
  - segments: line segments to draw — use [] if none.
  - points: labelled points — use [] if none.

━━ GEOMETRIC FIGURE — single shape with measurements ━━
Always provide actual vertex coordinates in a 0–200 (x) by 0–160 (y) bounding box.

Triangle ABC with AB=5cm, BC=7cm, angle B=60°:
{{"has_visual": true, "type": "geometry", "shape": "triangle",
  "description": "Triangle ABC with AB=5 cm, BC=7 cm, angle B=60°",
  "vertices": {{"A": [0, 86], "B": [0, 0], "C": [100, 0]}},
  "angles": {{"A": null, "B": "60°", "C": null}},
  "circle_data": null, "net_cells": null, "cell_labels": {{}},
  "measurements": [{{"label": "AB", "value": "5 cm", "type": "side"}},
                   {{"label": "BC", "value": "7 cm", "type": "side"}},
                   {{"label": "∠B", "value": "60°", "type": "angle"}}]}}

Right-angled triangle with legs 3cm, 4cm:
{{"has_visual": true, "type": "geometry", "shape": "right_triangle",
  "description": "Right-angled triangle with legs 3 cm and 4 cm",
  "vertices": {{"A": [0, 75], "B": [0, 0], "C": [100, 0]}},
  "angles": {{"A": null, "B": "90°", "C": null}},
  "circle_data": null, "net_cells": null, "cell_labels": {{}},
  "measurements": [{{"label": "AB", "value": "3 cm", "type": "side"}},
                   {{"label": "BC", "value": "4 cm", "type": "side"}}]}}

Rectangle 8cm × 5cm:
{{"has_visual": true, "type": "geometry", "shape": "rectangle",
  "description": "Rectangle 8 cm by 5 cm",
  "vertices": {{"A": [0, 62], "B": [0, 0], "C": [100, 0], "D": [100, 62]}},
  "angles": {{}}, "circle_data": null, "net_cells": null, "cell_labels": {{}},
  "measurements": [{{"label": "length", "value": "8 cm", "type": "side"}},
                   {{"label": "width", "value": "5 cm", "type": "side"}}]}}

Circle with radius 7cm:
{{"has_visual": true, "type": "geometry", "shape": "circle",
  "description": "Circle with radius 7 cm",
  "vertices": null, "angles": {{}}, "net_cells": null, "cell_labels": {{}},
  "circle_data": {{"cx": 100, "cy": 100, "radius": 70,
                  "radius_label": "7 cm", "diameter_label": null}},
  "measurements": [{{"label": "radius", "value": "7 cm", "type": "radius"}}]}}

Angle of 120°:
{{"has_visual": true, "type": "geometry", "shape": "angle",
  "description": "Angle of 120°",
  "vertices": {{"O": [50, 80], "A": [0, 80], "B": [100, 20]}},
  "angles": {{"O": "120°"}},
  "circle_data": null, "net_cells": null, "cell_labels": {{}},
  "measurements": [{{"label": "∠AOB", "value": "120°", "type": "angle"}}]}}

━━ COMPOUND / L-SHAPED / T-SHAPED POLYGON ━━
For irregular rectilinear figures, use "polygon" shape with 6+ vertices listed in ORDER:
L-shaped figure (6 cm × 8 cm with a 2 cm × 3 cm notch cut from top-right):
{{"has_visual": true, "type": "geometry", "shape": "polygon",
  "description": "L-shaped figure",
  "vertices": {{"A": [0, 0], "B": [120, 0], "C": [120, 60],
               "D": [60, 60], "E": [60, 130], "F": [0, 130]}},
  "angles": {{}}, "circle_data": null, "net_cells": null, "cell_labels": {{}},
  "measurements": [{{"label": "AB", "value": "6 cm", "type": "side"}},
                   {{"label": "AF", "value": "8 cm", "type": "side"}}]}}

━━ CUBE NET (unfolded cube showing 6 connected square faces) ━━
Use this when the question involves drawing, constructing, or examining a net of a cube/solid.
{{"has_visual": true, "type": "geometry", "shape": "cube_net",
  "description": "Net of a cube — cross shape with 6 square faces",
  "vertices": null, "angles": {{}}, "circle_data": null,
  "net_cells": [[0, 1], [1, 0], [1, 1], [1, 2], [1, 3], [2, 1]],
  "cell_labels": {{"0,1": "top", "1,0": "left", "1,1": "front",
                  "1,2": "right", "1,3": "back", "2,1": "bottom"}},
  "measurements": []}}
Notes on net_cells:
  - Each [row, col] pair identifies one square in a 2-D grid.
  - The cross-shaped net above is the most common. Other valid 6-cell arrangements also work.
  - For a cuboid net, use the same format but cells may form an elongated cross.
  - If you cannot determine the exact net shape, use the standard cross above.

━━ MCQ OPTIONS — four visual choices for multiple-choice questions ━━
Use this when the exercise is a multiple-choice question where each option (A, B, C, D) is a visual diagram.
The "options" array contains 4 items, each with a "label" (A-D) and a "visual" sub-object.
The "correct_option" field indicates which label is correct.
Example for "Which of these is a net of a cube?":
{{"has_visual": true, "type": "mcq_options",
  "options": [
    {{"label": "A", "visual": {{"type": "geometry", "shape": "cube_net", "net_cells": [[0,1],[1,0],[1,1],[1,2],[1,3],[2,1]], "description": "Cross-shaped net"}}}},
    {{"label": "B", "visual": {{"type": "geometry", "shape": "cube_net", "net_cells": [[0,0],[0,1],[1,1],[2,1],[3,1],[3,2]], "description": "S-shaped (invalid)"}}}},
    {{"label": "C", "visual": {{"type": "geometry", "shape": "cube_net", "net_cells": [[0,0],[1,0],[1,1],[1,2],[2,2],[3,2]], "description": "L-shaped net"}}}},
    {{"label": "D", "visual": {{"type": "geometry", "shape": "cube_net", "net_cells": [[0,1],[1,0],[1,1],[1,2],[2,1],[2,2]], "description": "Staircase (invalid)"}}}}
  ],
  "correct_option": "A"
}}
Each option's visual can be any valid visual type (geometry, axes, table, etc.).
The frontend will render each option's visual in a 2x2 grid with clickable cards.
RULES:
- Always include exactly 4 options with labels "A", "B", "C", "D".
- Set "correct_option" to the letter of the correct answer.
- Each option's "visual" field should be a complete visual schema (e.g., full geometry object).
- Use this type ONLY for genuine multiple-choice questions with visual options.

RULES:
- Always include the "description" field as a plain-English fallback.
- If coordinates cannot be determined, set "vertices": null (frontend falls back to description).
- Use "axes" type (not "geometry") whenever the question involves a coordinate grid.
- Use "cube_net" shape (not "page_image") whenever a net of a solid is needed.

For anything else you cannot reconstruct into the schemas above:
{{"has_visual": true, "type": "page_image", "description": "brief description of what the visual shows"}}

Return ONLY valid JSON. No explanation.
Exercise text: {exercise_text}
"""


def _normalise_vertices(vertices: dict) -> dict:
    """
    Scale vertex coordinates so the shape fits in a 180x130 viewport
    with 10px padding on each side (working area: 0-200 x, 0-160 y).
    Returns the same dict structure with scaled coords, or original if already fine.
    """
    if not vertices:
        return vertices
    try:
        all_x = [v[0] for v in vertices.values()]
        all_y = [v[1] for v in vertices.values()]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        span_x = max_x - min_x or 1
        span_y = max_y - min_y or 1
        # Target viewport: 20-180 x, 20-140 y  (160 wide, 120 tall)
        scale = min(160 / span_x, 120 / span_y)
        offset_x = 20 + (160 - span_x * scale) / 2 - min_x * scale
        offset_y = 20 + (120 - span_y * scale) / 2 - min_y * scale
        return {
            k: [round(v[0] * scale + offset_x, 1), round(v[1] * scale + offset_y, 1)]
            for k, v in vertices.items()
        }
    except Exception:
        return vertices


# Shapes that use their own coordinate system — do NOT run vertex normalisation
_SKIP_NORMALISE_SHAPES = {"cube_net"}


def _skip_mcq_normalise(vis: dict) -> bool:
    """Check if this is an mcq_options visual — skip normalisation for all sub-visuals."""
    return vis.get("type") == "mcq_options"



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
        # Normalise geometry vertex coordinates to fit SVG viewport
        # Skip shapes that use their own grid coordinate system
        shape = result.get("shape", "")
        if (
            result.get("type") == "geometry"
            and result.get("vertices")
            and shape not in _SKIP_NORMALISE_SHAPES
        ):
            result["vertices"] = _normalise_vertices(result["vertices"])
        # For mcq_options, skip normalisation for all sub-visuals
        if _skip_mcq_normalise(result):
            pass  # No normalisation needed — sub-visuals have their own coords
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
        result = call_llm_json(
            db,
            [{"role": "user", "content": prompt + "\n\n(No image available — infer from text only.)"}],
            max_tokens=700,
        )
        if not result.get("has_visual", False):
            return {}
        result.pop("has_visual", None)
        # Normalise vertices for text-only path too
        shape = result.get("shape", "")
        if (
            result.get("type") == "geometry"
            and result.get("vertices")
            and shape not in _SKIP_NORMALISE_SHAPES
        ):
            result["vertices"] = _normalise_vertices(result["vertices"])
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
