"""
MathTutor v1.3 Database Migration
Run once: python migrate_v1_3.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "mathtutor.db"

def column_exists(cur, table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

def table_exists(cur, table):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None

def run():
    if not DB_PATH.exists():
        print("No database found — will be created fresh on next server start.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    changes = 0

    # exercises: visual columns
    for col, typedef in [
        ("visual_type", "TEXT"),
        ("visual_data", "TEXT"),
    ]:
        if not column_exists(cur, "exercises", col):
            cur.execute(f"ALTER TABLE exercises ADD COLUMN {col} {typedef}")
            print(f"  + exercises.{col}")
            changes += 1

    # concept_progress table
    if not table_exists(cur, "concept_progress"):
        cur.execute("""
            CREATE TABLE concept_progress (
                id INTEGER PRIMARY KEY,
                child_id INTEGER NOT NULL,
                concept_id INTEGER NOT NULL,
                mastery_level TEXT DEFAULT 'not_started',
                teach_sessions_completed INTEGER DEFAULT 0,
                socratic_exchanges INTEGER DEFAULT 0,
                exercises_attempted INTEGER DEFAULT 0,
                exercises_correct INTEGER DEFAULT 0,
                last_interaction DATETIME,
                unlocked_for_test INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  + table: concept_progress")
        changes += 1

    # teaching_sessions table
    if not table_exists(cur, "teaching_sessions"):
        cur.execute("""
            CREATE TABLE teaching_sessions (
                id INTEGER PRIMARY KEY,
                child_id INTEGER NOT NULL,
                concept_id INTEGER NOT NULL,
                phase TEXT DEFAULT 'hook',
                messages TEXT,
                completed INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  + table: teaching_sessions")
        changes += 1

    conn.commit()
    conn.close()

    if changes == 0:
        print("Database already up to date.")
    else:
        print(f"\nMigration complete — {changes} change(s) applied.")

if __name__ == "__main__":
    print("Running MathTutor v1.3 migration...")
    run()
