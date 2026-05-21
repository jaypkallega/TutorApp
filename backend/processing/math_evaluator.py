"""
Math Evaluator — deterministic mathematical correctness checking using SymPy.

Handles: numeric, algebraic, equation, fraction, expression_set answer types.
Never calls LLM. Returns a result dict that the routing layer uses.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input normalisation — convert student notation to sympy-parseable form
# ---------------------------------------------------------------------------

def normalize_math_input(text: str) -> str:
    """
    Convert common student/textbook notation to SymPy-parseable form.
    Examples:
      2x      → 2*x
      x^2     → x**2
      2(x+3)  → 2*(x+3)
      √x      → sqrt(x)
      ²       → **2  (superscript)
    """
    if not text:
        return ""
    s = text.strip()

    # Remove LaTeX wrappers if present
    s = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)', s)
    s = re.sub(r'\\sqrt\{([^}]+)\}', r'sqrt(\1)', s)
    s = re.sub(r'\\left|\\right', '', s)

    # Unicode superscripts → **n
    superscript_map = {'⁰':'0','¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9'}
    for sup, digit in superscript_map.items():
        s = s.replace(sup, f'**{digit}')

    # √ → sqrt()
    s = re.sub(r'√\(([^)]+)\)', r'sqrt(\1)', s)
    s = re.sub(r'√([a-zA-Z0-9]+)', r'sqrt(\1)', s)

    # ^ → **
    s = s.replace('^', '**')

    # Insert * between coefficient and variable: 2x → 2*x, 3y → 3*y
    s = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', s)

    # Insert * between ) and (: )(  →  )*(
    s = re.sub(r'\)\s*\(', r')*(', s)

    # Insert * between digit/var and (: 2( → 2*(
    s = re.sub(r'(\d)\s*\(', r'\1*(', s)
    s = re.sub(r'([a-zA-Z])\s*\(', r'\1*(', s)

    return s.strip()


def detect_answer_type(text: str) -> str:
    """
    Rule-based answer type detection.
    Returns: numeric | fraction | equation | algebraic | expression_set | conceptual | unknown
    """
    if not text:
        return "unknown"
    s = text.strip()

    # Expression set: {2, -3} or (1, 2)
    if re.match(r'^\{.+\}$', s) or re.match(r'^\(.+,.+\)$', s):
        return "expression_set"

    # Equation: contains = (but not ==)
    if '=' in s and '==' not in s:
        return "equation"

    # Pure fraction: digits/digits possibly with signs
    if re.match(r'^-?\d+\s*/\s*-?\d+$', s):
        return "fraction"

    # Pure numeric (int or decimal)
    try:
        float(s.replace(',', ''))
        return "numeric"
    except ValueError:
        pass

    # Contains letters — likely algebraic or conceptual
    if re.search(r'[a-zA-Z]', s):
        # Short algebraic expression (few words)
        word_count = len(s.split())
        if word_count <= 5 and not re.search(r'\b(the|is|are|because|since|when)\b', s, re.I):
            return "algebraic"
        return "conceptual"

    return "unknown"


# ---------------------------------------------------------------------------
# Individual evaluators
# ---------------------------------------------------------------------------

def evaluate_numeric(student: str, expected_value: float, tolerance: float = 0.01) -> dict:
    """Compare a numeric answer with tolerance."""
    try:
        student_val = float(student.replace(',', '').strip())
        diff = abs(student_val - expected_value)
        correct = diff <= tolerance
        return {
            "correct": correct,
            "student_value": student_val,
            "expected_value": expected_value,
            "difference": diff,
            "tolerance_used": tolerance,
            "confidence": 0.99,
            "method": "numeric_tolerance",
        }
    except (ValueError, AttributeError):
        return {
            "correct": False,
            "confidence": 0.4,
            "method": "numeric_tolerance",
            "parse_error": f"Could not parse '{student}' as a number",
        }


def evaluate_algebraic(student: str, expected_sympy: str) -> dict:
    """Check symbolic equivalence using SymPy."""
    try:
        from sympy import simplify, sympify, SympifyError

        s_norm = normalize_math_input(student)
        e_norm = normalize_math_input(expected_sympy)

        student_expr = sympify(s_norm)
        expected_expr = sympify(e_norm)
        diff = simplify(student_expr - expected_expr)
        correct = diff == 0

        return {
            "correct": correct,
            "student_simplified": str(simplify(student_expr)),
            "expected_simplified": str(simplify(expected_expr)),
            "difference": str(diff),
            "confidence": 0.98,
            "method": "sympy_simplify",
        }
    except Exception as e:
        logger.warning(f"SymPy algebraic eval failed: {e}")
        # Fall back to normalized string comparison
        s_clean = re.sub(r'\s+', '', normalize_math_input(student).lower())
        e_clean = re.sub(r'\s+', '', normalize_math_input(expected_sympy).lower())
        return {
            "correct": s_clean == e_clean,
            "confidence": 0.5,
            "method": "string_fallback",
            "parse_error": str(e),
        }


def evaluate_equation(student: str, expected_sympy: str) -> dict:
    """Solve both equations and compare solution sets."""
    try:
        from sympy import symbols, solve, sympify, SympifyError, Eq
        from sympy.parsing.sympy_parser import parse_expr

        def parse_equation(eq_str: str):
            """Split on = and return (lhs, rhs) as sympy expressions."""
            norm = normalize_math_input(eq_str)
            if '=' in norm:
                parts = norm.split('=', 1)
                lhs = sympify(parts[0].strip())
                rhs = sympify(parts[1].strip()) if parts[1].strip() else sympify('0')
            else:
                lhs = sympify(norm)
                rhs = sympify('0')
            return lhs, rhs

        s_lhs, s_rhs = parse_equation(student)
        e_lhs, e_rhs = parse_equation(expected_sympy)

        # Detect variables (use x by default, then y)
        from sympy import free_symbols
        all_syms = (s_lhs - s_rhs).free_symbols | (e_lhs - e_rhs).free_symbols
        if not all_syms:
            # Numeric equation — just check equality
            from sympy import simplify
            correct = simplify(s_lhs - s_rhs - (e_lhs - e_rhs)) == 0
            return {"correct": correct, "confidence": 0.98, "method": "numeric_equation"}

        var = sorted(all_syms, key=str)[0]
        student_sols = set(solve(Eq(s_lhs, s_rhs), var))
        expected_sols = set(solve(Eq(e_lhs, e_rhs), var))

        correct = student_sols == expected_sols
        return {
            "correct": correct,
            "student_solutions": [str(s) for s in student_sols],
            "expected_solutions": [str(s) for s in expected_sols],
            "confidence": 0.97,
            "method": "sympy_solve",
        }
    except Exception as e:
        logger.warning(f"SymPy equation eval failed: {e}")
        return {
            "correct": False,
            "confidence": 0.3,
            "method": "equation_fallback",
            "parse_error": str(e),
        }


def evaluate_fraction(student: str, expected_sympy: str) -> dict:
    """Compare fractions using SymPy Rational normalisation."""
    try:
        from sympy import nsimplify, sympify, Rational
        s_norm = normalize_math_input(student)
        e_norm = normalize_math_input(expected_sympy)
        s_expr = nsimplify(sympify(s_norm))
        e_expr = nsimplify(sympify(e_norm))
        correct = s_expr == e_expr
        return {
            "correct": correct,
            "student_simplified": str(s_expr),
            "expected_simplified": str(e_expr),
            "confidence": 0.98,
            "method": "sympy_rational",
        }
    except Exception as e:
        logger.warning(f"SymPy fraction eval failed: {e}")
        return evaluate_algebraic(student, expected_sympy)


def evaluate_expression_set(student: str, expected_sympy: str) -> dict:
    """Compare sets of expressions (e.g. roots of a quadratic)."""
    try:
        from sympy import sympify, simplify

        def parse_set(s: str):
            s = s.strip()
            if s.startswith('{') and s.endswith('}'):
                s = s[1:-1]
            elif s.startswith('(') and s.endswith(')'):
                s = s[1:-1]
            parts = [p.strip() for p in s.split(',')]
            return {sympify(normalize_math_input(p)) for p in parts}

        student_set = parse_set(student)
        expected_set = parse_set(expected_sympy)

        correct = all(
            any(simplify(s - e) == 0 for e in expected_set)
            for s in student_set
        ) and len(student_set) == len(expected_set)

        return {
            "correct": correct,
            "student_set": [str(s) for s in student_set],
            "expected_set": [str(s) for s in expected_set],
            "confidence": 0.96,
            "method": "sympy_set_compare",
        }
    except Exception as e:
        logger.warning(f"Expression set eval failed: {e}")
        return {
            "correct": False,
            "confidence": 0.3,
            "method": "set_fallback",
            "parse_error": str(e),
        }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def evaluate_math_answer(
    student_answer: str,
    structured_answer: dict,
) -> dict:
    """
    Route to the correct evaluator based on answer_type.
    Returns a result dict with at minimum: correct (bool), confidence (float), method (str).
    """
    answer_type = structured_answer.get("answer_type", "unknown")
    sympy_expr = structured_answer.get("sympy_expr") or structured_answer.get("canonical_value", "")
    tolerance = structured_answer.get("tolerance", 0.01)

    if answer_type == "numeric":
        try:
            expected_val = float(str(sympy_expr).replace(',', ''))
        except ValueError:
            expected_val = 0.0
        return evaluate_numeric(student_answer, expected_val, tolerance)

    elif answer_type == "fraction":
        return evaluate_fraction(student_answer, sympy_expr)

    elif answer_type == "equation":
        return evaluate_equation(student_answer, sympy_expr)

    elif answer_type == "expression_set":
        return evaluate_expression_set(student_answer, sympy_expr)

    elif answer_type in ("algebraic", "multi_step"):
        # For multi_step, check just the final answer algebraically
        return evaluate_algebraic(student_answer, sympy_expr)

    else:
        return {
            "correct": None,    # None = undetermined, needs other layer
            "confidence": 0.0,
            "method": "not_applicable",
        }
