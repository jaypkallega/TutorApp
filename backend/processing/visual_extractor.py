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
  - segments: line segments to draw — use [] ━━ GEOMETRIC FIGURE — provide MATHEMATICAL PARAMETERS, not pixel coordinates ━━
A Python geometry engine will compute exact SVG coordinates from your spec.
Provide side lengths (numbers), angles in degrees (numbers), named dimensions.

Triangle ABC, AB=5 cm, BC=7 cm, ∠B=60° (SAS):
{{"has_visual": true, "type": "geometry", "shape": "triangle",
  "description": "Triangle ABC, AB=5 cm, BC=7 cm, ∠B=60°",
  "spec": {{"given": "SAS", "sides": {{"AB": 5, "BC": 7}}, "angles": {{"B": 60}},
           "unit": "cm", "vertex_names": ["A", "B", "C"]}},
  "measurements": [{{"label": "AB", "value": "5 cm"}}, {{"label": "BC", "value": "7 cm"}},
                   {{"label": "∠B", "value": "60°"}}]}}

Right-angled triangle, legs AB=3 cm, BC=4 cm:
{{"has_visual": true, "type": "geometry", "shape": "right_triangle",
  "description": "Right-angled triangle with legs 3 cm and 4 cm",
  "spec": {{"right_angle_at": "B", "legs": {{"AB": 3, "BC": 4}},
           "unit": "cm", "vertex_names": ["A", "B", "C"]}},
  "measurements": [{{"label": "AB", "value": "3 cm"}}, {{"label": "BC", "value": "4 cm"}}]}}

Rectangle 8 cm × 5 cm:
{{"has_visual": true, "type": "geometry", "shape": "rectangle",
  "description": "Rectangle 8 cm × 5 cm",
  "spec": {{"length": 8, "width": 5, "unit": "cm"}},
  "measurements": [{{"label": "length", "value": "8 cm"}}, {{"label": "width", "value": "5 cm"}}]}}

Circle, radius 7 cm:
{{"has_visual": true, "type": "geometry", "shape": "circle",
  "description": "Circle with radius 7 cm",
  "spec": {{"radius": 7, "unit": "cm"}},
  "measurements": [{{"label": "radius", "value": "7 cm"}}]}}

Angle AOB = 120°:
{{"has_visual": true, "type": "geometry", "shape": "angle",
  "description": "Angle AOB = 120°",
  "spec": {{"vertex": "O", "arm1": "A", "arm2": "B", "degrees": 120,
           "arm_length": 3, "unit": "cm"}},
  "measurements": [{{"label": "∠AOB", "value": "120°"}}]}}

L-shaped figure (6 cm × 8 cm total, with a 2 cm × 3 cm notch cut from top-right):
{{"has_visual": true, "type": "geometry", "shape": "polygon",
  "description": "L-shaped figure",
  "spec": {{"outline": [
    {{"dir": "right", "len": 6}}, {{"dir": "down", "len": 3}},
    {{"dir": "left",  "len": 2}}, {{"dir": "down", "len": 5}},
    {{"dir": "left",  "len": 4}}, {{"dir": "up",   "len": 8}}
  ], "unit": "cm"}},
  "measurements": [{{"label": "AB", "value": "6 cm"}}, {{"label": "FA", "value": "8 cm"}}]}}
Note: outline steps trace the perimeter clockwise; the last step must close back to the start.
Label only the measurements explicitly given in the problem.

Cylinder, radius 7 cm, height 10 cm:
{{"has_visual": true, "type": "geometry", "shape": "cylinder",
  "description": "Cylinder, radius 7 cm, height 10 cm",
  "spec": {{"radius": 7, "height": 10, "unit": "cm"}},
  "measurements": [{{"label": "radius", "value": "7 cm"}}, {{"label": "height", "value": "10 cm"}}]}}

Cone, base radius 5 cm, height 12 cm:
{{"has_visual": true, "type": "geometry", "shape": "cone",
  "description": "Cone, base radius 5 cm, height 12 cm",
  "spec": {{"base_radius": 5, "height": 12, "unit": "cm"}},
  "measurements": [{{"label": "radius", "value": "5 cm"}}, {{"label": "height", "value": "12 cm"}}]}}

Cuboid 8 cm × 5 cm × 6 cm:
{{"has_visual": true, "type": "geometry", "shape": "cuboid",
  "description": "Cuboid 8 cm × 5 cm × 6 cm",
  "spec": {{"length": 8, "width": 5, "height": 6, "unit": "cm"}},
  "measurements": [{{"label": "length", "value": "8 cm"}},
                   {{"label": "width",  "value": "5 cm"}},
                   {{"label": "height", "value": "6 cm"}}]}}

━━ CUBE NET — unfolded cube/cuboid ━━
Use when the question involves nets of solids.
{{"has_visual": true, "type": "geometry", "shape": "cube_net",
  "description": "Net of a cube — cross shape with 6 square faces",
  "spec": {{"net_cells": [[0,1],[1,0],[1,1],[1,2],[1,3],[2,1]],
           "cell_labels": {{"0,1": "top", "1,1": "front", "2,1": "bottom"}}}},
  "measurements": []}}

━━ MCQ OPTIONS — four visual choices for multiple-choice questions ━━
Use this when each option (A, B, C, D) is a distinct visual diagram.
Example — "Which is a valid net of a cube?":
{{"has_visual": true, "type": "mcq_options",
  "options": [
    {{"label": "A", "visual": {{"type": "geometry", "shape": "cube_net",
      "spec": {{"net_cells": [[0,1],[1,0],[1,1],[1,2],[1,3],[2,1]]}}, "description": "Cross net"}}}},
    {{"label": "B", "visual": {{"type": "geometry", "shape": "cube_net",
      "spec": {{"net_cells": [[0,0],[0,1],[1,1],[2,1],[3,1],[3,2]]}}, "description": "S-shaped"}}}},
    {{"label": "C", "visual": {{"type": "geometry", "shape": "cube_net",
      "spec": {{"net_cells": [[0,0],[1,0],[1,1],[1,2],[2,2],[3,2]]}}, "description": "L-shaped"}}}},
    {{"label": "D", "visual": {{"type": "geometry", "shape": "cube_net",
      "spec": {{"net_cells": [[0,1],[1,0],[1,1],[1,2],[2,1],[2,2]]}}, "description": "Staircase"}}}}
  ],
  "correct_option": "A"
}}
RULES for mcq_options:
- Always 4 options labelled A–D. Set correct_option to the right letter.
- Each option visual can be any valid type (geometry, axes, table …).
- Use ONLY for genuine multiple-choice questions with visual options.

GENERAL RULES:
- Always include the "description" field as a plain-English fallback.
- Use "axes" type (not "geometry") for coordinate-grid / plotting questions.
- Use "cube_net" shape (not "page_image") whenever a net of a solid is needed.
- For geometry shapes: always provide "spec" — do NOT provide raw pixel "vertices".
- For shapes not covered above, use:
  {{"has_visual": true, "type": "page_image", "description": "brief description"}}

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

def _apply_geometry_engine(result: dict) -> dict:
    """
    Post-process the LLM visual response:
    - If a "spec" key is present, call the geometry engine for exact coordinates.
    - If only raw "vertices" are present (old format / image extraction fallback),
      run the existing vertex normaliser.
    - MCQ options sub-visuals are processed individually.
    Returns the (possibly updated) result dict.
    """
    vtype = result.get("type")

    # Handle mcq_options: process each sub-visual recursively
    if vtype == "mcq_options":
        for opt in result.get("options", []):
            vis = opt.get("visual")
            if isinstance(vis, dict):
                opt["visual"] = _apply_geometry_engine(vis)
        return result

    if vtype != "geometry":
        return result

    shape = result.get("shape", "")
    spec  = result.pop("spec", None)   # consume spec — never sent to frontend

    if spec is not None:
        # New path: compute exact geometry from mathematical parameters
        from backend.processing.geometry_engine import compute_geometry
        return compute_geometry(
            shape,
            spec,
            result.get("measurements", []),
            result.get("description", ""),
        )

    # Old path: LLM returned raw vertices (image extraction fallback)
    if result.get("vertices") and shape not in _SKIP_NORMALISE_SHAPES:
        result["vertices"] = _normalise_vertices(result["vertices"])
    return result



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
        # Geometry: prefer spec → engine path; fall back to normalise for raw vertices
        result = _apply_geometry_engine(result)
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
        result = _apply_geometry_engine(result)
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
