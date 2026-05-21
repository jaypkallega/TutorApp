from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.deps import require_parent, get_current_user
from backend.models.user import User
from backend.models.chapter import Chapter
from backend.models.concept import Concept
from backend.schemas.chapter import ChapterOut, ChapterUpdate, ConceptOut

router = APIRouter()


@router.get("", response_model=List[ChapterOut])
def list_chapters(
    textbook_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.models.textbook import Textbook
    q = db.query(Chapter)
    if textbook_id:
        q = q.filter(Chapter.textbook_id == textbook_id)
    chapters = q.order_by(Chapter.textbook_id, Chapter.chapter_number).all()
    result = []
    textbook_cache = {}
    for ch in chapters:
        concepts = db.query(Concept).filter(Concept.chapter_id == ch.id).order_by(Concept.ordering).all()
        ch_dict = ChapterOut.model_validate(ch).model_dump()
        ch_dict["concepts"] = [ConceptOut.model_validate(c).model_dump() for c in concepts]
        # Enrich with textbook info
        if ch.textbook_id not in textbook_cache:
            tb = db.query(Textbook).filter(Textbook.id == ch.textbook_id).first()
            textbook_cache[ch.textbook_id] = {"title": tb.title if tb else "Unknown", "subject": tb.subject if tb else ""}
        ch_dict["textbook_title"] = textbook_cache[ch.textbook_id]["title"]
        ch_dict["textbook_subject"] = textbook_cache[ch.textbook_id]["subject"]
        result.append(ch_dict)
    return result


@router.get("/{chapter_id}", response_model=ChapterOut)
def get_chapter(
    chapter_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ch = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not ch:
        raise HTTPException(404, "Chapter not found")
    concepts = db.query(Concept).filter(Concept.chapter_id == ch.id).order_by(Concept.ordering).all()
    ch_dict = ChapterOut.model_validate(ch).model_dump()
    ch_dict["concepts"] = [ConceptOut.model_validate(c).model_dump() for c in concepts]
    return ch_dict


@router.patch("/{chapter_id}", response_model=ChapterOut)
def update_chapter(
    chapter_id: int,
    req: ChapterUpdate,
    current_user: User = Depends(require_parent),
    db: Session = Depends(get_db),
):
    ch = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not ch:
        raise HTTPException(404, "Chapter not found")
    updates = req.model_dump(exclude_none=True)
    for k, v in updates.items():
        setattr(ch, k, v)
    db.commit()
    db.refresh(ch)
    concepts = db.query(Concept).filter(Concept.chapter_id == ch.id).order_by(Concept.ordering).all()
    ch_dict = ChapterOut.model_validate(ch).model_dump()
    ch_dict["concepts"] = [ConceptOut.model_validate(c).model_dump() for c in concepts]
    return ch_dict


@router.post("/{chapter_id}/explain")
def explain_concept_endpoint(
    chapter_id: int,
    concept_id: int,
    question: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get an LLM explanation for a concept (used in Learn Mode)."""
    concept = db.query(Concept).filter(
        Concept.id == concept_id, Concept.chapter_id == chapter_id
    ).first()
    if not concept:
        raise HTTPException(404, "Concept not found")
    from backend.services.llm_service import explain_concept
    explanation = explain_concept(db, concept.concept_name, concept.explanation, question)
    return {"explanation": explanation}


@router.get("/{chapter_id}/difficulty-recommendation")
def get_difficulty_recommendation(
    chapter_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the adaptive difficulty recommendation for a chapter based on
    the current child's recent performance signals.

    Parent calling: uses the child account's data.
    Child calling: uses their own data.
    """
    from backend.models.user import User as UserModel
    from backend.processing.adaptive import get_chapter_difficulty_recommendation

    ch = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not ch:
        raise HTTPException(404, "Chapter not found")

    # Determine which child_id to use
    if current_user.role == "child":
        child_id = current_user.id
    else:
        # Parent: find the child account
        child = db.query(UserModel).filter(UserModel.role == "child").first()
        if not child:
            return {
                "recommended_difficulty": "easy",
                "signals": {"accuracy": None, "hints_penalty": False, "caution": False},
                "concept_count": 0,
                "has_data": False,
            }
        child_id = child.id

    return get_chapter_difficulty_recommendation(db, child_id, chapter_id)

