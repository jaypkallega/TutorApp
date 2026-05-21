"""
MathTutor v1.2 Database Migration
Run once: python migrate_v1_2.py
Safe to run multiple times (checks before altering).
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "mathtutor.db"

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def table_exists(cursor, table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None

def run():
    if not DB_PATH.exists():
        print("No database found — will be created fresh on next server start. No migration needed.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    changes = 0

    # exercises: add structured_answer
    if not column_exists(cur, "exercises", "structured_answer"):
        cur.execute("ALTER TABLE exercises ADD COLUMN structured_answer TEXT")
        print("  + exercises.structured_answer")
        changes += 1

    # evaluations: add confidence, requires_parent_review, low_confidence_questions, evaluated_by update
    for col, typedef in [
        ("confidence", "REAL DEFAULT 1.0"),
        ("requires_parent_review", "INTEGER DEFAULT 0"),
        ("low_confidence_questions", "TEXT"),
    ]:
        if not column_exists(cur, "evaluations", col):
            cur.execute(f"ALTER TABLE evaluations ADD COLUMN {col} {typedef}")
            print(f"  + evaluations.{col}")
            changes += 1

    # Update evaluated_by default for existing rows
    cur.execute("UPDATE evaluations SET evaluated_by = 'llm' WHERE evaluated_by IS NULL OR evaluated_by = ''")

    # misconceptions table
    if not table_exists(cur, "misconceptions"):
        cur.execute("""
            CREATE TABLE misconceptions (
                id INTEGER PRIMARY KEY,
                subject TEXT NOT NULL DEFAULT 'Mathematics',
                topic TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                pattern TEXT,
                diagnosis TEXT NOT NULL,
                remedy TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  + table: misconceptions")
        changes += 1

    # student_misconception_logs table
    if not table_exists(cur, "student_misconception_logs"):
        cur.execute("""
            CREATE TABLE student_misconception_logs (
                id INTEGER PRIMARY KEY,
                child_id INTEGER NOT NULL,
                misconception_id INTEGER NOT NULL,
                exercise_id INTEGER,
                submission_id INTEGER,
                student_answer TEXT,
                logged_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  + table: student_misconception_logs")
        changes += 1

    conn.commit()
    conn.close()

    if changes == 0:
        print("Database already up to date.")
    else:
        print(f"\nMigration complete — {changes} change(s) applied.")

if __name__ == "__main__":
    print("Running MathTutor v1.2 migration...")
    run()
