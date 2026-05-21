"""
PDF Parser — converts a textbook PDF into images and extracted text,
then sends to LLM for structured chapter/concept/exercise extraction.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def pdf_to_page_images(pdf_path: str, output_dir: str, dpi: int = 150) -> list[str]:
    """
    Render each PDF page to a PNG image using PyMuPDF (fitz).
    Returns list of image file paths.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    image_paths = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        img_path = output_path / f"page_{page_num + 1:04d}.png"
        pix.save(str(img_path))
        image_paths.append(str(img_path))

    doc.close()
    logger.info(f"Rendered {len(image_paths)} pages from {pdf_path}")
    return image_paths


def extract_text_from_pdf(pdf_path: str) -> list[str]:
    """
    Extract text from each page using pdfplumber (better for math text layout).
    Returns list of strings, one per page.
    """
    import pdfplumber

    page_texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            page_texts.append(text)
    logger.info(f"Extracted text from {len(page_texts)} pages")
    return page_texts


def extract_text_from_images(image_paths: list[str], db=None) -> list[str]:
    """
    Run OCR on a list of page images.
    Used when the PDF has scanned/non-selectable content.
    """
    from backend.services.ocr_service import extract_text_from_image, get_ocr_mode
    mode = get_ocr_mode(db) if db else "local"
    texts = []
    for img_path in image_paths:
        text = extract_text_from_image(img_path, db=db, mode=mode)
        texts.append(text)
    return texts


def process_textbook(
    db,
    textbook_id: int,
    pdf_path: str,
    page_images_dir: str,
) -> None:
    """
    Full pipeline: PDF → images → text → LLM analysis → save to DB.
    Runs as a background task. Updates textbook.status during processing.
    """
    from backend.models.textbook import Textbook
    from backend.models.chapter import Chapter
    from backend.models.concept import Concept
    from backend.models.exercise import Exercise
    from backend.services.llm_service import analyze_textbook_structure
    from backend.database import SessionLocal

    # Use a fresh DB session for background task
    session = SessionLocal()

    def update_status(status: str, log: str = ""):
        tb = session.query(Textbook).filter(Textbook.id == textbook_id).first()
        if tb:
            tb.status = status
            if log:
                tb.analysis_log = log
            session.commit()

    try:
        update_status("processing", "Extracting PDF pages...")

        # Step 1: Render pages to images
        image_paths = pdf_to_page_images(pdf_path, page_images_dir)
        page_count = len(image_paths)

        tb = session.query(Textbook).filter(Textbook.id == textbook_id).first()
        if tb:
            tb.page_count = page_count
            session.commit()

        update_status("processing", f"Extracted {page_count} pages. Reading text...")

        # Step 2: Extract text (try direct PDF first, fall back to OCR)
        page_texts = extract_text_from_pdf(pdf_path)
        # Check if text is usable (many scanned books have empty pages)
        total_chars = sum(len(t) for t in page_texts)
        if total_chars < page_count * 50:
            update_status("processing", "PDF appears scanned — running OCR...")
            page_texts = extract_text_from_images(image_paths, db=session)

        update_status("processing", "Sending to AI for structure analysis...")

        # Step 3: LLM analysis — process in chunks of 30 pages
        chunk_size = 30
        all_chapters = []
        tb = session.query(Textbook).filter(Textbook.id == textbook_id).first()
        for start in range(0, len(page_texts), chunk_size):
            chunk = page_texts[start:start + chunk_size]
            try:
                result = analyze_textbook_structure(session, chunk, subject=tb.subject if tb else "Mathematics", grade=tb.grade if tb else 8)
                chapters = result.get("chapters", [])
                # Adjust page numbers for chunk offset
                for ch in chapters:
                    ch["start_page"] = (ch.get("start_page") or 1) + start
                    ch["end_page"] = (ch.get("end_page") or 1) + start
                all_chapters.extend(chapters)
            except Exception as e:
                logger.error(f"LLM analysis chunk {start} failed: {e}")

        if not all_chapters:
            update_status("error", "AI analysis returned no chapters. Check API key and model.")
            session.close()
            return

        update_status("processing", f"Saving {len(all_chapters)} chapters to database...")

        # Step 4: Save chapters, concepts, exercises to DB
        tb = session.query(Textbook).filter(Textbook.id == textbook_id).first()
        for ch_data in all_chapters:
            chapter = Chapter(
                textbook_id=textbook_id,
                chapter_number=ch_data.get("chapter_number", 0),
                title=ch_data.get("title", "Untitled"),
                summary=ch_data.get("summary"),
                start_page=ch_data.get("start_page"),
                end_page=ch_data.get("end_page"),
                approved=False,
            )
            session.add(chapter)
            session.flush()  # get chapter.id

            for i, c_data in enumerate(ch_data.get("concepts", [])):
                concept = Concept(
                    chapter_id=chapter.id,
                    concept_name=c_data.get("name", ""),
                    explanation=c_data.get("explanation", ""),
                    textbook_method=c_data.get("textbook_method"),
                    alternate_method=c_data.get("alternate_method"),
                    difficulty_hint=c_data.get("difficulty_hint"),
                    source_page_start=c_data.get("page_start"),
                    source_page_end=c_data.get("page_end"),
                    ordering=i,
                )
                session.add(concept)
                session.flush()

                # Link exercises to this concept
                for e_data in ch_data.get("exercises", []):
                    exercise = Exercise(
                        chapter_id=chapter.id,
                        concept_id=concept.id,
                        source="textbook",
                        difficulty=e_data.get("difficulty", "medium"),
                        exercise_type=e_data.get("type", "calculation"),
                        prompt=e_data.get("prompt", ""),
                        expected_answer=e_data.get("expected_answer"),
                        source_page=e_data.get("page"),
                    )
                    session.add(exercise)

        session.commit()
        update_status("ready", f"Analysis complete: {len(all_chapters)} chapters found.")
        logger.info(f"Textbook {textbook_id} processing complete")

    except Exception as e:
        logger.error(f"Textbook processing failed: {e}", exc_info=True)
        update_status("error", f"Processing failed: {str(e)}")
    finally:
        session.close()
