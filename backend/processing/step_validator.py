"""
Step Validator — validates multi-step mathematical working line by line.

For questions requiring shown working (derivations, equation solving),
each step is checked for mathematical validity independently.
A wrong step is caught immediately rather than just checking the final answer.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def split_into_steps(working: str) -> list[str]:
    """
    Split student working into individual steps.
    Handles newlines, numbered steps (1. 2. 3.), and => arrows.
    """
    # Split on newlines first
    lines = working.strip().split('\n')
    steps = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove step numbering: "1.", "Step 1:", "(i)"
        line = re.sub(r'^(step\s*)?\d+[.):\s]+', '', line, flags=re.I)
        line = re.sub(r'^[ivxIVX]+[.):\s]+', '', line)
        if line:
            steps.append(line)

    # Also split on => or ⟹ arrows within a single block
    expanded = []
    for step in steps:
        parts = re.split(r'=>|⟹|→|therefore|∴', step, flags=re.I)
        expanded.extend([p.strip() for p in parts if p.strip()])
    return expanded


def parse_as_equation(step: str):
    """
    Try to parse a step as a SymPy Eq(lhs, rhs).
    Returns (lhs, rhs, equation) or (expr, 0, None) for plain expressions.
    Returns None if parsing fails.
    """
    try:
        from sympy import sympify, Eq
        from backend.processing.math_evaluator import normalize_math_input

        norm = normalize_math_input(step)
        if '=' in norm and '==' not in norm:
            parts = norm.split('=', 1)
            lhs = sympify(parts[0].strip())
            rhs = sympify(parts[1].strip()) if parts[1].strip() else sympify('0')
            return lhs, rhs, Eq(lhs, rhs)
        else:
            expr = sympify(norm)
            return expr, None, None
    except Exception:
        return None


def get_solution_from_step(lhs, rhs) -> set:
    """Solve an equation step for all free symbols."""
    try:
        from sympy import solve, Eq, free_symbols
        all_syms = (lhs - rhs).free_symbols
        if not all_syms:
            return set()
        var = sorted(all_syms, key=str)[0]
        return set(solve(Eq(lhs, rhs), var))
    except Exception:
        return set()


def validate_steps(steps: list[str], expected_final: Optional[str] = None) -> dict:
    """
    Validate a sequence of working steps.

    Returns:
        {
            valid: bool,
            first_error_index: int or None,
            first_error_step: str or None,
            error_description: str or None,
            steps_validated: int,
            final_answer_correct: bool or None,
            confidence: float,
        }
    """
    if not steps:
        return {
            "valid": False,
            "first_error_index": None,
            "first_error_step": None,
            "error_description": "No steps found",
            "steps_validated": 0,
            "final_answer_correct": None,
            "confidence": 0.3,
        }

    parsed = []
    for step in steps:
        result = parse_as_equation(step)
        parsed.append(result)

    # Strategy: for equation-solving steps, all valid steps should preserve
    # the solution set. Find the first step where it changes.
    solutions_at_step = []
    for i, p in enumerate(parsed):
        if p is None:
            solutions_at_step.append(None)
            continue
        lhs, rhs, eq = p
        if rhs is not None:
            sols = get_solution_from_step(lhs, rhs)
            solutions_at_step.append(sols)
        else:
            solutions_at_step.append(None)

    # Find first non-None solution (the reference)
    reference_solutions = None
    reference_idx = None
    for i, s in enumerate(solutions_at_step):
        if s is not None:
            reference_solutions = s
            reference_idx = i
            break

    if reference_solutions is None:
        # Could not parse any step as an equation — expression validation
        return {
            "valid": True,
            "first_error_index": None,
            "first_error_step": None,
            "error_description": None,
            "steps_validated": len(steps),
            "final_answer_correct": None,
            "confidence": 0.4,  # Low confidence — couldn't verify
        }

    # Check each subsequent equation step preserves solution
    first_error_idx = None
    first_error_step = None
    error_description = None

    for i in range(reference_idx + 1, len(solutions_at_step)):
        s = solutions_at_step[i]
        if s is None:
            continue  # Expression step — skip
        if s != reference_solutions:
            first_error_idx = i
            first_error_step = steps[i]
            error_description = (
                f"Step {i+1} changes the solution. "
                f"Expected solution {reference_solutions}, got {s}. "
                f"Check step: '{steps[i]}'"
            )
            break

    # Check final answer if provided
    final_correct = None
    if expected_final and steps:
        from backend.processing.math_evaluator import evaluate_equation, evaluate_algebraic
        last_step = steps[-1]
        # Try equation comparison first
        result = evaluate_equation(last_step, expected_final)
        if result.get("confidence", 0) < 0.5:
            result = evaluate_algebraic(last_step, expected_final)
        final_correct = result.get("correct", None)

    confidence = 0.95 if first_error_idx is None else 0.97
    if any(s is None for s in solutions_at_step):
        confidence -= 0.1  # Some steps couldn't be parsed

    return {
        "valid": first_error_idx is None,
        "first_error_index": first_error_idx,
        "first_error_step": first_error_step,
        "error_description": error_description,
        "steps_validated": len([s for s in solutions_at_step if s is not None]),
        "final_answer_correct": final_correct,
        "confidence": max(confidence, 0.1),
        "reference_solutions": [str(s) for s in reference_solutions] if reference_solutions else [],
    }


def evaluate_multi_step(student_working: str, structured_answer: dict) -> dict:
    """
    Full evaluation of a multi-step answer.
    Splits into steps, validates each, checks final answer.
    """
    steps = split_into_steps(student_working)
    if not steps:
        return {
            "correct": False,
            "status": "skipped",
            "confidence": 0.9,
            "method": "step_validator",
            "detail": "No working found",
        }

    expected_final = structured_answer.get("sympy_expr") or structured_answer.get("canonical_value")
    result = validate_steps(steps, expected_final)

    if result["valid"] and result.get("final_answer_correct") is not False:
        status = "correct"
        correct = True
    elif not result["valid"] and result.get("final_answer_correct"):
        # Wrong step but somehow got right answer — partial credit
        status = "partial"
        correct = False
    elif not result["valid"]:
        status = "wrong"
        correct = False
    else:
        status = "partial"
        correct = False

    return {
        "correct": correct,
        "status": status,
        "confidence": result["confidence"],
        "method": "step_validator",
        "steps_validated": result["steps_validated"],
        "first_error_index": result.get("first_error_index"),
        "first_error_step": result.get("first_error_step"),
        "error_description": result.get("error_description"),
        "final_answer_correct": result.get("final_answer_correct"),
    }
