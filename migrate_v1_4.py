"""
MathTutor v1.4 Database Migration
Run once: python migrate_v1_4.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "mathtutor.db"

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

    if not table_exists(cur, "submission_drafts"):
        cur.execute("""
            CREATE TABLE submission_drafts (
                id INTEGER PRIMARY KEY,
                assignment_id INTEGER NOT NULL,
                child_id INTEGER NOT NULL,
                answers TEXT DEFAULT '{}',
                status TEXT DEFAULT 'in_progress',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  + table: submission_drafts")
        changes += 1

    conn.commit()
    conn.close()
    if changes == 0:
        print("Database already up to date.")
    else:
        print(f"\nMigration complete — {changes} change(s) applied.")

if __name__ == "__main__":
    print("Running MathTutor v1.4 migration...")
    run()
