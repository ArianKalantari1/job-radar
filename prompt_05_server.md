# Prompt 05 — Flask Server (`server.py`)
## Context
You are working on the `job-radar` project. Read `scraper.py` and `scorer.py` to understand DB_PATH, column names, and data structures before writing this file.

## Task — Create `server.py`

Create a new file `server.py` in the project root. This is a lightweight Flask API that:
- Serves job data to the dashboard
- Handles Slack swipe reactions (thumbs up/down)
- Updates job status (Kanban drag-drop)
- Handles job dismissals
- Handles notes on jobs
- Triggers cover letter generation (Phase 4 — stub only for now)

```python
"""
job-radar: Flask API server

Serves the Kanban dashboard and handles all job state mutations.
Run with: python server.py

Endpoints:
  GET  /                          → serves dashboard.html
  GET  /api/jobs                  → all non-dismissed jobs as JSON
  GET  /api/jobs/<id>/reaction/<type>  → record Slack swipe (good|bad)
  POST /api/jobs/<id>/status      → update Kanban status
  POST /api/jobs/<id>/dismiss     → dismiss with reason
  POST /api/jobs/<id>/notes       → update notes
  GET  /api/stats                 → summary counts
  POST /api/jobs/<id>/cover-letter  → generate cover letter (stub)
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(__file__).parent / "jobs.db"
DASHBOARD_PATH = Path(__file__).parent / "dashboard.html"
PORT = int(os.getenv("SERVER_PORT", "5000"))

app = Flask(__name__)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_file(DASHBOARD_PATH)


# ---------------------------------------------------------------------------
# Jobs API
# ---------------------------------------------------------------------------

@app.route("/api/jobs")
def get_jobs():
    """Return all non-dismissed jobs, sorted by score desc."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT job_url, site, title, company, location, description,
               date_posted, salary_min, salary_max, salary_raw,
               search_label, score, score_reasons, match_reasons,
               primary_role, also_fits, role_scores,
               first_seen, applied, status, notes,
               user_reaction, cover_letter, company_research,
               min_amount, max_amount, currency
        FROM jobs
        WHERE dismissed = 0 OR dismissed IS NULL
        ORDER BY score DESC, first_seen DESC
        """
    ).fetchall()
    conn.close()
    jobs = []
    for row in rows:
        j = dict(row)
        # Parse JSON fields safely
        for field in ("also_fits", "role_scores", "match_reasons"):
            if j.get(field):
                try:
                    j[field] = json.loads(j[field])
                except (json.JSONDecodeError, TypeError):
                    j[field] = []
        jobs.append(j)
    return jsonify(jobs)


@app.route("/api/stats")
def get_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM jobs WHERE dismissed = 0 OR dismissed IS NULL").fetchone()[0]
    by_role = conn.execute(
        "SELECT primary_role, COUNT(*) FROM jobs WHERE (dismissed = 0 OR dismissed IS NULL) GROUP BY primary_role"
    ).fetchall()
    by_status = conn.execute(
        "SELECT status, COUNT(*) FROM jobs WHERE (dismissed = 0 OR dismissed IS NULL) GROUP BY status"
    ).fetchall()
    conn.close()
    return jsonify({
        "total": total,
        "by_role": {r[0]: r[1] for r in by_role},
        "by_status": {r[0]: r[1] for r in by_status},
    })


# ---------------------------------------------------------------------------
# Reactions (for Slack buttons — GET so Slack link buttons work)
# ---------------------------------------------------------------------------

@app.route("/api/jobs/<path:job_id>/reaction/<reaction_type>")
def record_reaction(job_id: str, reaction_type: str):
    """
    Record a swipe reaction. Called by Slack button links.
    reaction_type: 'good' or 'bad'
    Optional query param: ?reason=<text>
    """
    if reaction_type not in ("good", "bad"):
        return "Invalid reaction", 400

    reason = request.args.get("reason", "")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        UPDATE jobs SET
            user_reaction = ?,
            user_reaction_reason = ?,
            reaction_timestamp = ?,
            status = CASE WHEN ? = 'good' THEN 'saved' ELSE status END,
            dismissed = CASE WHEN ? = 'bad' THEN 1 ELSE dismissed END
        WHERE job_url = ?
        """,
        (reaction_type, reason, now_iso(), reaction_type, reaction_type, job_id),
    )
    conn.commit()
    conn.close()

    emoji = "👍" if reaction_type == "good" else "👎"
    action = "Saved to dashboard" if reaction_type == "good" else "Dismissed"
    return f"""
    <html><body style="font-family:monospace;padding:2rem;background:#111;color:#eee;">
    <h2>{emoji} {action}</h2>
    <p>Job has been {action.lower()}. You can close this tab.</p>
    </body></html>
    """, 200


# ---------------------------------------------------------------------------
# Status update (Kanban drag-drop)
# ---------------------------------------------------------------------------

@app.route("/api/jobs/<path:job_id>/status", methods=["POST"])
def update_status(job_id: str):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    valid_statuses = ["new", "saved", "applying", "applied", "phone_screen", "interview", "offer", "rejected"]
    if not status or status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {valid_statuses}"}), 400

    conn = sqlite3.connect(DB_PATH)
    extra_updates = ""
    params = [status]

    # Auto-set applied_date when moved to applied
    if status == "applied":
        extra_updates = ", applied = 1, date_applied = ?"
        params.append(now_iso())

    params.append(job_id)
    conn.execute(
        f"UPDATE jobs SET status = ? {extra_updates} WHERE job_url = ?",
        params,
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "status": status})


# ---------------------------------------------------------------------------
# Dismiss
# ---------------------------------------------------------------------------

@app.route("/api/jobs/<path:job_id>/dismiss", methods=["POST"])
def dismiss_job(job_id: str):
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "")
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE jobs SET dismissed = 1, dismissed_reason = ? WHERE job_url = ?",
        (reason, job_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

@app.route("/api/jobs/<path:job_id>/notes", methods=["POST"])
def update_notes(job_id: str):
    data = request.get_json(silent=True) or {}
    notes = data.get("notes", "")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE jobs SET notes = ? WHERE job_url = ?", (notes, job_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Cover letter (stub — Phase 4 will implement this fully)
# ---------------------------------------------------------------------------

@app.route("/api/jobs/<path:job_id>/cover-letter", methods=["POST"])
def generate_cover_letter(job_id: str):
    """
    STUB: Returns a placeholder. Phase 4 will implement full LLM generation.
    """
    return jsonify({
        "ok": False,
        "message": "Cover letter generation not yet implemented. Coming in Phase 4.",
    }), 501


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"job-radar server running on http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    app.run(host="0.0.0.0", port=PORT, debug=False)
```

## Validation
Run:
```bash
python server.py
```

In a second terminal, test the endpoints:
```bash
# Get jobs
curl http://localhost:5000/api/jobs | python -m json.tool | head -50

# Get stats
curl http://localhost:5000/api/stats

# Test reaction (replace JOB_URL with a real URL from your DB)
# curl "http://localhost:5000/api/jobs/https%3A%2F%2F.../reaction/good"
```

Expected: `/api/jobs` returns a JSON array, `/api/stats` returns counts by role and status.

## Do NOT
- Do not modify `scraper.py`, `scorer.py`, `dashboard.py`, or `run.py`
- Do not implement the cover letter generation yet — that is Phase 4
- Do not add authentication — this runs locally only
- Do not use Flask-SQLAlchemy — use plain `sqlite3` to match the existing codebase
