from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.deps import get_current_user
from backend.models.user import User
from backend.models.exercise import Exercise
from backend.models.chapter import Chapter
from backend.models.concept import Concept
from backend.schemas.exercise import ExerciseOut, GenerateExercisesRequest

router = APIRouter()


@router.get("", response_model=List[ExerciseOut])
def list_exercises(
    chapter_id: int = None,
    difficulty: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Exercise)
    if chapter_id:
        q = q.filter(Exercise.chapter_id == chapter_id)
    if difficulty:
        q = q.filter(Exercise.difficulty == difficulty)
    return q.order_by(Exercise.created_at).all()


@router.get("/{exercise_id}", response_model=ExerciseOut)
def get_exercise(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ex = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not ex:
        raise HTTPException(404, "Exercise not found")
    return ex


@router.post("/generate", response_model=List[ExerciseOut])
def generate_exercises(
    req: GenerateExercisesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate new AI exercises for a chapter/concept."""
    chapter = db.query(Chapter).filter(Chapter.id == req.chapter_id).first()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    concept = None
    concept_name = "General"
    concept_explanation = chapter.summary or chapter.title
    if req.concept_id:
        concept = db.query(Concept).filter(Concept.id == req.concept_id).first()
        if concept:
            concept_name = concept.concept_name
            concept_explanation = concept.explanation

    from backend.services.llm_service import generate_exercises as gen_ex
    raw_exercises = gen_ex(
        db,
        chapter_title=chapter.title,
        concept_name=concept_name,
        concept_explanation=concept_explanation,
        difficulty=req.difficulty,
        count=req.count,
    )

    from backend.services.llm_service import generate_structured_answer
    from backend.models.textbook import Textbook
    import json as _json

    # Get subject from chapter's textbook
    from backend.models.textbook import Textbook
    subject = "Mathematics"
    if chapter.textbook_id:
        tb = db.query(Textbook).filter(Textbook.id == chapter.textbook_id).first()
        if tb:
            subject = tb.subject or "Mathematics"

    saved = []
    for e_data in raw_exercises:
        prompt = e_data.get("prompt", "")
        expected = e_data.get("expected_answer", "")
        ex_type = e_data.get("type", "calculation")

        # Generate structured answer for deterministic evaluation
        structured = {}
        if prompt and expected:
            try:
                structured = generate_structured_answer(
                    db, prompt, expected, subject=subject,
                    exercise_type=ex_type, grade=8
                )
            except Exception:
                pass

        ex = Exercise(
            chapter_id=req.chapter_id,
            concept_id=req.concept_id,
            source="ai_generated",
            difficulty=req.difficulty,
            exercise_type=ex_type,
            prompt=prompt,
            expected_answer=expected,
            expected_method=e_data.get("expected_method"),
            structured_answer=_json.dumps(structured) if structured else None,
        )
        db.add(ex)
        db.flush()
        saved.append(ex)
    db.commit()
    for ex in saved:
        db.refresh(ex)
    return saved
