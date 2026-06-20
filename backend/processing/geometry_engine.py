"""
Geometry Engine — converts mathematical shape specifications into exact SVG
vertex coordinates using Python's built-in math module only.

The LLM's job is to identify WHAT the shape is and its measurements
(sides, angles in degrees, named dimensions). This engine's job is to
compute WHERE each vertex sits in the SVG viewport — exactly.

No external dependencies. Uses only the Python stdlib math module.
"""
import math
from typing import Optional

# SVG viewport matches VisualDisplay.tsx viewBox="0 0 200 160"
VW, VH, PAD = 200, 160, 18
_VERTEX_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _find_label(measurements: list, keywords: list) -> Optional[str]:
    """Return the value of the first measurement whose label contains any keyword."""
    for m in measurements:
        lbl = m.get("label", "").lower()
        if any(kw.lower() in lbl for kw in keywords):
            return m.get("value")
    return None


# ── Vertex scaling ────────────────────────────────────────────────────────────

def _scale_math(raw: dict) -> dict:
    """
    Scale vertices from math-coordinate space (y-up) into the SVG viewport
    (y-down, 200×160 with PAD margin). Flips y automatically.
    """
    if not raw:
        return raw
    pts  = list(raw.values())
    xs   = [p[0] for p in pts]
    ys_s = [-p[1] for p in pts]       # flip: math y-up → SVG y-down
    min_x, max_x = min(xs),  max(xs)
    min_y, max_y = min(ys_s), max(ys_s)
    sx, sy = (max_x - min_x) or 1, (max_y - min_y) or 1
    ww, wh = VW - 2*PAD, VH - 2*PAD
    sc = min(ww / sx, wh / sy)
    ox = PAD + (ww - sx*sc) / 2 - min_x*sc
    oy = PAD + (wh - sy*sc) / 2 - min_y*sc
    return {
        k: [round(v[0]*sc + ox, 1), round(-v[1]*sc + oy, 1)]
        for k, v in raw.items()
    }


def _scale_svg(raw: dict) -> dict:
    """
    Scale vertices already in SVG-coordinate space (y-down) into the viewport.
    No y-flip needed.
    """
    if not raw:
        return raw
    pts  = list(raw.values())
    xs   = [p[0] for p in pts]
    ys   = [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    sx, sy = (max_x - min_x) or 1, (max_y - min_y) or 1
    ww, wh = VW - 2*PAD, VH - 2*PAD
    sc = min(ww / sx, wh / sy)
    ox = PAD + (ww - sx*sc) / 2 - min_x*sc
    oy = PAD + (wh - sy*sc) / 2 - min_y*sc
    return {
        k: [round(v[0]*sc + ox, 1), round(v[1]*sc + oy, 1)]
        for k, v in raw.items()
    }


# ── Triangle ─────────────────────────────────────────────────────────────────

def _triangle(spec: dict) -> tuple[dict, dict]:
    """
    Compute triangle vertices (math coords, y-up) and angle annotation dict.
    Handles: right_triangle, SAS, SSS, ASA/AAS.
    Returns (raw_vertices, angles_dict).
    """
    names = spec.get("vertex_names", ["A", "B", "C"])
    An, Bn, Cn = (names + ["A", "B", "C"])[:3]

    # ── Right triangle ────────────────────────────────────────────────────────
    if spec.get("right_angle_at") or "legs" in spec:
        legs = spec.get("legs", {})
        lv   = [float(v) for v in legs.values()]
        l1   = lv[0] if lv else 3.0
        l2   = lv[1] if len(lv) > 1 else 4.0
        # B at origin, C along x (leg 2), A upward (leg 1) — math coords
        raw  = {Bn: [0.0, 0.0], Cn: [l2, 0.0], An: [0.0, l1]}
        return raw, {An: None, Bn: "90°", Cn: None}

    sides  = spec.get("sides", {})
    a_dict = spec.get("angles", {})

    # ── SAS: two sides + one included angle ───────────────────────────────────
    if a_dict and len(sides) >= 2:
        ang_v   = next(iter(a_dict))
        ang_deg = float(next(iter(a_dict.values())))
        ang_rad = math.radians(ang_deg)
        # Sides adjacent to the angle vertex
        adj = {k: float(v) for k, v in sides.items() if ang_v in k}
        if len(adj) >= 2:
            s1, s2 = list(adj.values())[:2]
        else:
            sv = [float(v) for v in sides.values()]
            s1 = sv[0]; s2 = sv[1] if len(sv) > 1 else sv[0]
        raw = {
            Bn: [0.0, 0.0],
            Cn: [s2,  0.0],
            An: [s1 * math.cos(ang_rad), s1 * math.sin(ang_rad)],
        }
        return raw, {An: None, Bn: f"{ang_deg:.0f}°", Cn: None}

    # ── SSS: all three sides known ────────────────────────────────────────────
    if len(sides) >= 3 or spec.get("given", "").upper() == "SSS":
        sv      = [float(v) for v in sides.values()] if sides else [5.0, 7.0, 6.0]
        a, b, c = sv[0], sv[1], sv[2]   # a=BC, b=CA, c=AB
        cos_B   = _clamp((a*a + c*c - b*b) / (2*a*c))
        ang_B   = math.acos(cos_B)
        raw = {
            Bn: [0.0, 0.0],
            Cn: [a,   0.0],
            An: [c * math.cos(ang_B), c * math.sin(ang_B)],
        }
        return raw, {An: None, Bn: None, Cn: None}

    # ── ASA / AAS: two angles + one side ─────────────────────────────────────
    if len(a_dict) >= 2:
        avs  = [float(v) for v in a_dict.values()]
        A_d, C_d = avs[0], avs[1]
        B_d  = max(0.1, 180.0 - A_d - C_d)
        sv   = [float(v) for v in sides.values()] if sides else [5.0]
        side = sv[0]
        sinB = math.sin(math.radians(B_d)) or 1e-9
        BC   = side * math.sin(math.radians(A_d)) / sinB
        AB   = side * math.sin(math.radians(C_d)) / sinB
        ang_B_r = math.radians(B_d)
        raw = {
            Bn: [0.0, 0.0],
            Cn: [BC,  0.0],
            An: [AB * math.cos(ang_B_r), AB * math.sin(ang_B_r)],
        }
        return raw, {An: f"{A_d:.0f}°", Bn: f"{B_d:.0f}°", Cn: f"{C_d:.0f}°"}

    # ── Default: equilateral-ish ──────────────────────────────────────────────
    s   = 5.0
    raw = {An: [s/2, s*math.sqrt(3)/2], Bn: [0.0, 0.0], Cn: [s, 0.0]}
    return raw, {An: None, Bn: None, Cn: None}


# ── Rectangle ─────────────────────────────────────────────────────────────────

def _rectangle(spec: dict) -> dict:
    """Compute rectangle vertices in SVG coords (y-down)."""
    length = float(spec.get("length", 8))
    width  = float(spec.get("width",  5))
    names  = spec.get("vertex_names", ["A", "B", "C", "D"])
    An, Bn, Cn, Dn = (names + ["A", "B", "C", "D"])[:4]
    return _scale_svg({
        An: [0.0,   0.0],
        Bn: [length, 0.0],
        Cn: [length, width],
        Dn: [0.0,   width],
    })


# ── Circle ────────────────────────────────────────────────────────────────────

def _circle_data(spec: dict, measurements: list) -> dict:
    """Build circle_data dict consumed by VisualDisplay.tsx."""
    r    = float(spec.get("radius", 0))
    if not r and "diameter" in spec:
        r = float(spec["diameter"]) / 2
    r    = r or 7.0
    unit = spec.get("unit", "cm")
    return {
        "cx": VW // 2,
        "cy": VH // 2,
        "radius": round(min(r, 70)),      # frontend caps further if needed
        "radius_label":   (_find_label(measurements, ["radius"]) or f"{r} {unit}"),
        "diameter_label": _find_label(measurements, ["diameter"]),
    }


# ── Angle ─────────────────────────────────────────────────────────────────────

def _angle(spec: dict) -> tuple[dict, dict]:
    """Two-arm angle figure. Vertex at origin, arms in math coords (y-up)."""
    deg = float(spec.get("degrees", 90))
    arm = float(spec.get("arm_length", 3))
    Vn  = spec.get("vertex", "O")
    A1  = spec.get("arm1", "A")
    A2  = spec.get("arm2", "B")
    rad = math.radians(deg)
    raw = {
        A1: [arm, 0.0],
        Vn: [0.0, 0.0],
        A2: [arm * math.cos(rad), arm * math.sin(rad)],
    }
    return raw, {Vn: f"{deg:.0f}°"}


# ── Polygon (L-shape, T-shape, etc. via outline) ──────────────────────────────

def _polygon(spec: dict) -> dict:
    """
    Trace polygon vertices from a sequential list of outline steps.
    Each step: {"dir": "right|left|up|down", "len": <number>}
    Coordinates are in SVG space (y increases downward).
    """
    outline = spec.get("outline", [])
    if not outline:
        return {}

    _D: dict[str, tuple[float, float]] = {
        "right": (1, 0),  "r": (1, 0),
        "left":  (-1, 0), "l": (-1, 0),
        "down":  (0, 1),  "d": (0, 1),
        "up":    (0, -1), "u": (0, -1),
    }
    x = y = 0.0
    verts: dict[str, list[float]] = {_VERTEX_LABELS[0]: [x, y]}
    for i, step in enumerate(outline):
        d   = str(step.get("dir", "right")).lower()
        ln  = float(step.get("len", 1))
        dx, dy = _D.get(d, (1, 0))
        x += dx * ln
        y += dy * ln
        # Stop when the outline closes back to the start
        if abs(x) < 1e-9 and abs(y) < 1e-9:
            break
        if i + 1 < len(_VERTEX_LABELS):
            verts[_VERTEX_LABELS[i + 1]] = [round(x, 4), round(y, 4)]

    return _scale_svg(verts)


# ── 3-D shapes (oblique/cabinet projection) ───────────────────────────────────

def _cylinder_data(spec: dict, measurements: list) -> dict:
    """Cylinder: two ellipses connected by vertical lines."""
    r    = float(spec.get("radius", 5))
    h    = float(spec.get("height", 10))
    unit = spec.get("unit", "cm")
    # Scale to fit: target max_rx≈52px, max height≈90px
    sc   = min(52 / r if r else 10, 90 / h if h else 10)
    rx   = round(r * sc)
    hp   = round(h * sc)
    ry   = max(7, round(rx * 0.28))
    cx   = VW // 2
    yb   = VH - PAD - ry - 8
    yt   = yb - hp
    return {
        "cx": cx, "cy_top": yt, "cy_bottom": yb,
        "rx": rx, "ry": ry,
        "radius_label": _find_label(measurements, ["radius", "r"]) or f"{r} {unit}",
        "height_label": _find_label(measurements, ["height", "h"]) or f"{h} {unit}",
    }


def _cone_data(spec: dict, measurements: list) -> dict:
    """Cone: base ellipse + apex point + two slant lines."""
    r    = float(spec.get("base_radius", spec.get("radius", 5)))
    h    = float(spec.get("height", 10))
    unit = spec.get("unit", "cm")
    sc   = min(52 / r if r else 10, 90 / h if h else 10)
    rx   = round(r * sc)
    hp   = round(h * sc)
    ry   = max(7, round(rx * 0.28))
    cx   = VW // 2
    yb   = VH - PAD - ry - 8
    ya   = yb - hp
    return {
        "cx": cx, "apex_y": ya, "base_cy": yb,
        "rx": rx, "ry": ry,
        "radius_label": _find_label(measurements, ["radius", "r"]) or f"{r} {unit}",
        "height_label": _find_label(measurements, ["height", "h"]) or f"{h} {unit}",
        "slant_label":  _find_label(measurements, ["slant", "slant height"]),
    }


def _cuboid_data(spec: dict, measurements: list) -> dict:
    """
    Cuboid using cabinet oblique projection:
    depth at 30°, foreshortened to 50%.
    Returns face polygons and label positions for VisualDisplay.
    """
    l    = float(spec.get("length", 8))
    w    = float(spec.get("width",  5))
    h_d  = float(spec.get("height", 6))
    unit = spec.get("unit", "cm")

    ang_rad = math.radians(30)
    ca, sa  = math.cos(ang_rad), math.sin(ang_rad)
    df      = 0.5                   # cabinet foreshortening factor

    # Scale so the full projected shape fits in (VW-2*PAD-8) × (VH-2*PAD-8)
    proj_w = l + w * df * ca
    proj_h = h_d + w * df * sa
    ww, wh = VW - 2*PAD - 8, VH - 2*PAD - 8
    sc = min((ww / proj_w) if proj_w else 10,
             (wh / proj_h) if proj_h else 10,
             18)                    # cap at 18 px/unit

    W  = round(l   * sc, 1)
    H  = round(h_d * sc, 1)
    D  = w * sc * df                # depth in pixels (foreshortened)
    dx = round(D * ca, 1)           # depth x-component (→ right)
    dy = round(D * sa, 1)           # depth y-component (→ up in SVG = smaller y)

    # Front face top-left corner; push down by dy so back face fits at top
    x0 = float(PAD + 4)
    y0 = float(PAD + dy + 4)

    # Front face corners (SVG y-down)
    Ftl = [x0,     y0]
    Ftr = [x0 + W, y0]
    Fbl = [x0,     y0 + H]
    Fbr = [x0 + W, y0 + H]
    # Back face = front shifted right (+dx) and up (-dy in SVG)
    Btl = [x0 + dx,     y0 - dy]
    Btr = [x0 + W + dx, y0 - dy]
    Bbr = [x0 + W + dx, y0 + H - dy]

    def p(pt: list) -> list:
        return [round(pt[0], 1), round(pt[1], 1)]

    return {
        # Visible faces: front (facing viewer), top, right
        "front": [p(Fbl), p(Fbr), p(Ftr), p(Ftl)],
        "top":   [p(Ftl), p(Ftr), p(Btr), p(Btl)],
        "right": [p(Ftr), p(Btr), p(Bbr), p(Fbr)],
        "labels": {
            "length": _find_label(measurements, ["length", "l"]) or f"{l} {unit}",
            "width":  _find_label(measurements, ["width",  "w"]) or f"{w} {unit}",
            "height": _find_label(measurements, ["height", "h"]) or f"{h_d} {unit}",
        },
        "label_pos": {
            # Below front face centre
            "length": p([(Fbl[0] + Fbr[0]) / 2, Fbl[1] + 10]),
            # Right of right face, mid-height
            "width":  p([Bbr[0] + 8,  (Bbr[1] + Fbr[1]) / 2]),
            # Left of front face, mid-height
            "height": p([Fbl[0] - 8,  (Fbl[1] + Ftl[1]) / 2]),
        },
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def compute_geometry(
    shape: str,
    spec: dict,
    measurements: list,
    description: str = "",
) -> dict:
    """
    Convert a shape spec (from the LLM) into a VisualDisplay-ready dict.
    Output format is identical to what the frontend already expects —
    the spec is consumed here and never sent to the frontend.
    """
    result: dict = {
        "type":         "geometry",
        "shape":        shape,
        "description":  description,
        "measurements": measurements,
        # Plane shape outputs
        "vertices":     None,
        "angles":       {},
        "circle_data":  None,
        # Cube-net output
        "net_cells":    None,
        "cell_labels":  {},
        # 3-D shape outputs (new)
        "cylinder_data": None,
        "cone_data":     None,
        "cuboid_data":   None,
    }

    try:
        if shape in ("triangle", "scalene_triangle", "isosceles_triangle",
                     "equilateral_triangle"):
            raw, angs          = _triangle(spec)
            result["vertices"] = _scale_math(raw)
            result["angles"]   = angs

        elif shape == "right_triangle":
            spec = {**spec, "right_angle_at": spec.get("right_angle_at", "B")}
            raw, angs          = _triangle(spec)
            result["vertices"] = _scale_math(raw)
            result["angles"]   = angs

        elif shape == "square":
            s    = float(spec.get("side", spec.get("length", 5)))
            result["vertices"] = _rectangle({**spec, "length": s, "width": s})
            result["angles"]   = {}

        elif shape == "rectangle":
            result["vertices"] = _rectangle(spec)
            result["angles"]   = {}

        elif shape == "circle":
            result["circle_data"] = _circle_data(spec, measurements)

        elif shape == "angle":
            raw, angs          = _angle(spec)
            result["vertices"] = _scale_math(raw)
            result["angles"]   = angs

        elif shape in ("polygon", "l_shape", "t_shape", "cross",
                       "compound", "irregular", "hexagon", "pentagon",
                       "parallelogram", "trapezium", "rhombus"):
            result["vertices"] = _polygon(spec)
            result["angles"]   = {}

        elif shape == "cylinder":
            result["cylinder_data"] = _cylinder_data(spec, measurements)

        elif shape == "cone":
            result["cone_data"] = _cone_data(spec, measurements)

        elif shape == "cuboid":
            result["cuboid_data"] = _cuboid_data(spec, measurements)

        elif shape == "cube_net":
            result["net_cells"]   = spec.get(
                "net_cells", [[0,1],[1,0],[1,1],[1,2],[1,3],[2,1]])
            result["cell_labels"] = spec.get("cell_labels", {})

        # sphere, prism, pyramid → fall through; frontend shows description card

    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            f"geometry_engine: failed for shape={shape!r}: {exc}", exc_info=True)
        # result retains null vertices → frontend shows description fallback

    return result
