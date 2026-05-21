import os
import shutil
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.deps import require_parent
from backend.models.user import User
from backend.models.textbook import Textbook
from backend.models.chapter import Chapter
from backend.schemas.textbook import TextbookOut, TextbookList
from backend.config import TEXTBOOKS_DIR, PAGE_IMAGES_DIR, ALLOWED_TEXTBOOK_EXTENSIONS, MAX_UPLOAD_SIZE_MB

router = APIRouter()


@router.get("", response_model=TextbookList)
def list_textbooks(
    current_user: User = Depends(require_parent),
    db: Session = Depends(get_db),
):
    items = db.query(Textbook).order_by(Textbook.created_at.desc()).all()
    return {"items": items, "total": len(items)}


@router.post("", response_model=TextbookOut)
async def upload_textbook(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    grade: int = Form(default=8),
    subject: str = Form(default="Mathematics"),
    file: UploadFile = File(...),
    current_user: User = Depends(require_parent),
    db: Session = Depends(get_db),
):
    # Validate extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_TEXTBOOK_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Use PDF or images.")

    # Check file size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(413, f"File too large ({size_mb:.1f} MB). Max {MAX_UPLOAD_SIZE_MB} MB.")

    # Save file
    dest_path = TEXTBOOKS_DIR / file.filename
    with open(dest_path, "wb") as f:
        f.write(content)

    upload_type = "pdf" if ext == ".pdf" else "images"
    textbook = Textbook(
        title=title,
        subject=subject,
        grade=grade,
        file_path=str(dest_path),
        upload_type=upload_type,
        status="pending",
    )
    db.add(textbook)
    db.commit()
    db.refresh(textbook)

    # Start background processing
    if upload_type == "pdf":
        from backend.processing.pdf_parser import process_textbook
        page_img_dir = str(PAGE_IMAGES_DIR / f"textbook_{textbook.id}")
        background_tasks.add_task(
            process_textbook, db, textbook.id, str(dest_path), page_img_dir
        )

    return textbook


@router.get("/{textbook_id}", response_model=TextbookOut)
def get_textbook(
    textbook_id: int,
    current_user: User = Depends(require_parent),
    db: Session = Depends(get_db),
):
    tb = db.query(Textbook).filter(Textbook.id == textbook_id).first()
    if not tb:
        raise HTTPException(404, "Textbook not found")
    return tb



@router.get("/{textbook_id}/page/{page_number}")
def get_page_image(
    textbook_id: int,
    page_number: int,
    db: Session = Depends(get_db),
):
    """Serve a stored page image for display in the frontend."""
    from backend.config import PAGE_IMAGES_DIR
    page_dir = PAGE_IMAGES_DIR / f"textbook_{textbook_id}"
    for ext in ["png", "jpg", "jpeg"]:
        path = page_dir / f"page_{page_number:04d}.{ext}"
        if path.exists():
            return FileResponse(str(path), media_type=f"image/{ext}")
    raise HTTPException(404, f"Page image {page_number} not found for textbook {textbook_id}")


@router.delete("/{textbook_id}")
def delete_textbook(
    textbook_id: int,
    current_user: User = Depends(require_parent),
    db: Session = Depends(get_db),
):
    tb = db.query(Textbook).filter(Textbook.id == textbook_id).first()
    if not tb:
        raise HTTPException(404, "Textbook not found")
    # Delete file
    try:
        os.remove(tb.file_path)
    except Exception:
        pass
    db.delete(tb)
    db.commit()
    return {"message": "Textbook deleted"}
