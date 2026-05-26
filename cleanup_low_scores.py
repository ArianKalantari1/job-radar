"""
One-time cleanup: dismiss all existing jobs scoring below the auto-dismiss
threshold (40) that slipped through before this feature was added.

Run once with the server stopped:
    python cleanup_low_scores.py

Safe to re-run — already-dismissed jobs are not touched.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"
THRESHOLD = 40

conn = sqlite3.connect(DB_PATH)

# Dismiss AI-scored jobs below threshold
r1 = conn.execute(
    """
    UPDATE jobs SET dismissed = 1, dismissed_reason = 'low_score'
    WHERE ai_score IS NOT NULL
      AND ai_score < ?
      AND (dismissed = 0 OR dismissed IS NULL)
    """,
    (THRESHOLD,),
)

# Dismiss rules-scored-only jobs below threshold (no AI score yet)
r2 = conn.execute(
    """
    UPDATE jobs SET dismissed = 1, dismissed_reason = 'low_score'
    WHERE ai_score IS NULL
      AND score IS NOT NULL AND score < ?
      AND (dismissed = 0 OR dismissed IS NULL)
    """,
    (THRESHOLD,),
)

conn.commit()

remaining = conn.execute(
    "SELECT COUNT(*) FROM jobs WHERE dismissed = 0 OR dismissed IS NULL"
).fetchone()[0]

above50 = conn.execute(
    """SELECT COUNT(*) FROM jobs
       WHERE (dismissed = 0 OR dismissed IS NULL)
         AND COALESCE(ai_score, score, 0) >= 50"""
).fetchone()[0]

conn.close()

print(f"Dismissed {r1.rowcount} AI-scored + {r2.rowcount} rules-scored low jobs (score < {THRESHOLD})")
print(f"Remaining visible on board : {remaining}")
print(f"Of those, score ≥ 50 (board default): {above50}")
