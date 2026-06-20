"""
migrate_v1_5.py — MathTutor v1.5 database migration.

Changes:
  1. concept_progress.recommended_difficulty  (TEXT, default 'easy')
  2. concept_progress.difficulty_updated_at   (DATETIME, nullable)
  3. Re-processes all existing exercises with visual_type='geometry' using the
     updated visual extractor prompt (adds vertices / angles / circle_data).

Run once after extracting v1.5 archive:
    python migrate_v1_5.py

Safe to run multiple times — geometry re-processing skips exercises that
already have 'vertices' in their visual_data.
"""

import json
import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def main():
    from backend.database import engine, SessionLocal
    from sqlalchemy import text

    # ------------------------------------------------------------------
    # Step 1: Add new columns to concept_progress
    # ------------------------------------------------------------------
    log.info("Step 1: Adding columns to concept_progress …")
    with engine.connect() as conn:
        existing = [
            row[1]
            for row in conn.execute(text("PRAGMA table_info(concept_progress)")).fetchall()
        ]
        if "recommended_difficulty" not in existing:
            conn.execute(text(
                "ALTER TABLE concept_progress ADD COLUMN recommended_difficulty TEXT DEFAULT 'easy'"
            ))
            log.info("  + recommended_difficulty added")
        else:
            log.info("  - recommended_difficulty already exists, skipping")

        if "difficulty_updated_at" not in existing:
            conn.execute(text(
                "ALTER TABLE concept_progress ADD COLUMN difficulty_updated_at DATETIME"
            ))
            log.info("  + difficulty_updated_at added")
        else:
            log.info("  - difficulty_updated_at already exists, skipping")

        conn.commit()

    # ------------------------------------------------------------------
    # Step 2: Re-process geometry exercises
    # ------------------------------------------------------------------
    log.info("\nStep 2: Re-processing geometry exercises …")

    db = SessionLocal()
    try:
        from backend.models.exercise import Exercise
        geo_exercises = (
            db.query(Exercise)
            .filter(Exercise.visual_type == "geometry")
            .all()
        )
        log.info(f"  Found {len(geo_exercises)} geometry exercise(s)")

        processed = skipped = failed = 0

        for ex in geo_exercises:
            # Idempotency: skip if vertices already present
            try:
                existing_data = json.loads(ex.visual_data or "{}")
                if "vertices" in existing_data:
                    skipped += 1
                    continue
            except Exception:
                pass

            try:
                from backend.processing.visual_extractor import extract_visual_for_exercise
                from backend.models.chapter import Chapter
                from backend.models.textbook import Textbook

                # Get subject + grade for the prompt
                chapter = db.query(Chapter).filter(Chapter.id == ex.chapter_id).first()
                textbook = db.query(Textbook).filter(
                    Textbook.id == chapter.textbook_id
                ).first() if chapter else None
                subject = textbook.subject if textbook else "Mathematics"
                grade = textbook.grade if textbook else 8

                result = extract_visual_for_exercise(
                    db=db,
                    exercise_prompt=ex.prompt,
                    page_image_path=None,   # text-only re-process (no page images needed)
                    subject=subject,
                    grade=grade,
                )

                if result:
                    result["type"] = "geometry"   # ensure type field is preserved
                    ex.visual_data = json.dumps(result)
                    db.commit()
                    processed += 1
                    log.info(f"  ✓ Exercise {ex.id}: {ex.prompt[:60]}…")
                else:
                    skipped += 1

                time.sleep(0.5)   # avoid rate-limiting

            except Exception as e:
                log.warning(f"  ✗ Exercise {ex.id} failed: {e}")
                failed += 1

        log.info(
            f"\n  Geometry re-processing complete: "
            f"{processed} updated, {skipped} skipped, {failed} failed"
        )

    finally:
        db.close()

    log.info("\n✅  migrate_v1_5.py complete. You can now start the app.")


if __name__ == "__main__":
    main()
