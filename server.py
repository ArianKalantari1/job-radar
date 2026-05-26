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
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(__file__).parent / "jobs.db"
DASHBOARD_PATH = Path(__file__).parent / "dashboard.html"
RESUME_PATH = Path(__file__).parent / "resume.txt"
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
    """
    Return non-dismissed jobs, sorted by score desc.

    Query params:
      min_score (int, default 50) — only return jobs scoring at or above this.
                                    Pass 0 to see everything.
      hours (int, default 0)      — rolling window: last N hours. Takes priority over days.
      days (int, default 2)       — calendar-day window. Pass 0 for all-time.
    """
    from datetime import datetime, timedelta, timezone
    min_score = int(request.args.get("min_score", 50))
    hours = int(request.args.get("hours", 0))
    days = int(request.args.get("days", 2))
    conn = get_conn()

    where_clauses = ["(dismissed = 0 OR dismissed IS NULL)", "COALESCE(ai_score, score, 0) >= ?"]
    params = [min_score]

    if hours > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        where_clauses.append("first_seen >= ?")
        params.append(cutoff)
    elif days > 0:
        where_clauses.append("substr(first_seen, 1, 10) >= date('now', ?)")
        params.append(f"-{days - 1} days")

    rows = conn.execute(
        f"""
        SELECT job_url, site, title, company, location, description,
               date_posted, salary_min, salary_max, salary_raw,
               search_label, score, score_reasons, match_reasons,
               primary_role, also_fits, role_scores,
               first_seen, applied, status, notes,
               user_reaction, cover_letter, company_research,
               min_amount, max_amount, currency,
               resume_match_pct, resume_matched_skills, resume_missing_skills,
               ai_score, ai_match, ai_stage, ai_reason, ai_gaps
        FROM jobs
        WHERE {" AND ".join(where_clauses)}
        ORDER BY COALESCE(ai_score, score, 0) DESC, first_seen DESC
        """,
        params,
    ).fetchall()
    conn.close()
    jobs = []
    for row in rows:
        j = dict(row)
        # Parse JSON fields safely
        for field in ("also_fits", "role_scores", "match_reasons",
                      "resume_matched_skills", "resume_missing_skills"):
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
# Resume upload + gap analysis
# ---------------------------------------------------------------------------

@app.route("/api/resume", methods=["GET"])
def get_resume():
    """Return resume status and extracted skill list."""
    if not RESUME_PATH.exists():
        return jsonify({"uploaded": False, "skills": []})

    resume_text = RESUME_PATH.read_text(encoding="utf-8")

    # Load skills from role profiles
    profiles_path = Path(__file__).parent / "role_profiles.json"
    skills: list[str] = []
    if profiles_path.exists():
        config = json.loads(profiles_path.read_text())
        seen: set[str] = set()
        for profile in config.get("profiles", []):
            for s in profile.get("skills_high", []) + profile.get("skills_mid", []):
                if s not in seen:
                    seen.add(s)
                    skills.append(s)

    resume_l = resume_text.lower()
    found_skills = [s for s in skills if s in resume_l]

    return jsonify({
        "uploaded": True,
        "chars": len(resume_text),
        "skills": found_skills,
    })


@app.route("/api/resume", methods=["POST"])
def upload_resume():
    """
    Accept a PDF or plain text resume.
    - multipart/form-data with field 'file' (PDF)
    - OR raw text/plain body
    Extracts text, saves to resume.txt, rescores all jobs.
    """
    import io

    # Determine content type
    content_type = request.content_type or ""

    if "multipart/form-data" in content_type or "application/pdf" in content_type:
        uploaded_file = request.files.get("file")
        if not uploaded_file:
            return jsonify({"error": "No file provided. Send PDF as field 'file'."}), 400

        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
            resume_text = "\n".join(pages).strip()
        except Exception as e:
            return jsonify({"error": f"Could not parse PDF: {e}"}), 400

    elif "text/plain" in content_type:
        resume_text = request.get_data(as_text=True).strip()
    else:
        # Try multipart anyway (browser form)
        uploaded_file = request.files.get("file")
        if uploaded_file:
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
                    pages = [page.extract_text() or "" for page in pdf.pages]
                resume_text = "\n".join(pages).strip()
            except Exception as e:
                return jsonify({"error": f"Could not parse PDF: {e}"}), 400
        else:
            return jsonify({"error": "Unsupported content type. Send PDF (multipart) or text/plain."}), 415

    if not resume_text:
        return jsonify({"error": "Could not extract text from the uploaded file."}), 400

    RESUME_PATH.write_text(resume_text, encoding="utf-8")

    # Trigger rescore with resume matching
    try:
        from scorer import score_all_jobs
        scored = score_all_jobs()
    except Exception as e:
        scored = 0

    return jsonify({"ok": True, "chars": len(resume_text), "jobs_rescored": scored})


@app.route("/api/gap-analysis")
def gap_analysis():
    """
    Returns skills that appear most often in active job postings but are NOT in the resume.
    Used to show the user which skills to learn/add to their resume.
    """
    if not RESUME_PATH.exists():
        return jsonify({"error": "No resume uploaded yet. POST to /api/resume first."}), 400

    conn = get_conn()
    rows = conn.execute(
        """
        SELECT resume_missing_skills
        FROM jobs
        WHERE (dismissed = 0 OR dismissed IS NULL)
          AND resume_missing_skills IS NOT NULL
          AND resume_missing_skills != '[]'
        ORDER BY score DESC
        LIMIT 150
        """
    ).fetchall()
    conn.close()

    skill_counts: dict[str, int] = {}
    for row in rows:
        try:
            skills = json.loads(row["resume_missing_skills"])
        except Exception:
            skills = []
        for s in skills:
            skill_counts[s] = skill_counts.get(s, 0) + 1

    ranked = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)
    return jsonify({
        "gaps": [{"skill": s, "job_count": c} for s, c in ranked[:30]],
        "total_jobs_analysed": len(rows),
    })


@app.route("/api/export-csv")
def export_csv():
    """
    Export jobs as CSV for Claude review.

    The exported CSV includes two blank columns — ai_stage and ai_reason —
    for Claude to fill in and return. When you import the file back via
    /api/import-csv, those columns drive what happens to each job:
      - ai_stage='applying'  → moves job to the Applying column on the board
      - ai_stage='dismissed' → archives the job (hides from board, kept in DB)
      - ai_stage='saved'     → marks job as saved for later
      - (leave blank)        → no change

    Query params:
      min_score (int, default 0)  — only export jobs scoring at or above this
      role (str)                  — filter to a specific primary_role
      hours (int)                 — rolling window: last N hours (e.g. hours=24, hours=48).
                                    More precise than days — use this for daily morning review.
      days (int)                  — calendar-day window matching dashboard pills
                                    (1=Today, 2=Today+Yesterday, 7=Last 7 days).
                                    If neither days nor hours given, defaults to hours=24.
    """
    import csv, io
    from datetime import datetime, timedelta, timezone
    min_score = int(request.args.get("min_score", 0))
    role = request.args.get("role", None)
    days = int(request.args.get("days", 0))
    hours = int(request.args.get("hours", 0))

    conn = get_conn()
    query = """
        SELECT title, company, location, primary_role, score, salary_raw,
               job_url, date_posted, description
        FROM jobs
        WHERE (dismissed = 0 OR dismissed IS NULL)
          AND description IS NOT NULL
          AND LENGTH(description) > 50
          AND score >= ?
    """
    params = [min_score]
    if role:
        query += " AND primary_role = ?"
        params.append(role)

    if hours > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        query += " AND first_seen >= ?"
        params.append(cutoff)
    elif days > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query += " AND first_seen >= ?"
        params.append(cutoff)
    else:
        # Safe default: last 24 hours. Prevents accidentally exporting all jobs.
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        query += " AND first_seen >= ?"
        params.append(cutoff)
        hours = 24  # for label below

    query += " ORDER BY score DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    # Build a descriptive filename so the download reflects the active filter
    if hours > 0:
        label = f"last_{hours}h"
    elif days == 1:
        label = "today"
    elif days == 2:
        label = "today_yesterday"
    elif days > 0:
        label = f"last_{days}_days"
    else:
        label = "all"
    filename = f"jobs_for_claude_{label}.csv"

    output = io.StringIO()
    # ai_stage and ai_reason are intentionally blank — Claude fills them in.
    # Import this file back via /api/import-csv once Claude has reviewed it.
    data_fields = ["title", "company", "location", "primary_role", "score",
                   "salary_raw", "job_url", "date_posted", "description"]
    all_fields  = data_fields + ["ai_stage", "ai_reason"]

    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(all_fields)
    for row in rows:
        writer.writerow([row[f] for f in data_fields] + ["", ""])

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route("/api/import-csv", methods=["POST"])
def import_csv():
    """
    Import a Claude-reviewed CSV back into the DB.

    Expected columns (all optional except job_url):
      job_url    — must match a URL in the DB
      ai_stage   — one of the valid Kanban statuses, OR 'dismissed' to archive the job
      ai_match   — e.g. 'strong', 'good', 'weak'
      ai_score   — integer 0-100
      ai_reason  — why Claude picked or skipped this job
      ai_gaps    — skills gaps noted by Claude

    When ai_stage='dismissed': sets dismissed=1 so the job disappears from the board
    (but stays in the DB for reference). All other valid stages update the Kanban column.

    Returns counts: updated, dismissed, skipped.
    """
    import csv, io

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Send as multipart/form-data with field 'file'."}), 400

    f = request.files["file"]
    content = f.read().decode("utf-8-sig")  # strip BOM if present
    reader = csv.DictReader(io.StringIO(content))

    required = {"job_url"}
    if not required.issubset(set(reader.fieldnames or [])):
        return jsonify({"error": "CSV must have at least a 'job_url' column."}), 400

    valid_statuses = {"new", "saved", "applying", "applied", "phone_screen", "interview", "offer", "rejected"}
    updated = 0
    dismissed_count = 0
    skipped = 0

    conn = sqlite3.connect(DB_PATH)
    for row in reader:
        url = (row.get("job_url") or "").strip()
        if not url:
            skipped += 1
            continue

        ai_match  = (row.get("ai_match")  or "").strip().lower() or None
        ai_reason = (row.get("ai_reason") or "").strip() or None
        ai_gaps   = (row.get("ai_gaps")   or "").strip() or None
        ai_stage  = (row.get("ai_stage")  or "").strip().lower() or None
        try:
            ai_score = int(row.get("ai_score") or 0) or None
        except (ValueError, TypeError):
            ai_score = None

        exists = conn.execute("SELECT 1 FROM jobs WHERE job_url = ?", (url,)).fetchone()
        if not exists:
            skipped += 1
            continue

        # --- Dismissed: archive the job so it vanishes from the board ---
        if ai_stage == "dismissed":
            fields = ["dismissed = 1", "dismissed_reason = 'csv_import'"]
            params = []
            if ai_reason is not None: fields.append("ai_reason = ?"); params.append(ai_reason)
            params.append(url)
            conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE job_url = ?", params)
            dismissed_count += 1
            continue

        # --- All other stages: update Kanban + AI annotations ---
        fields, params = [], []
        if ai_match  is not None: fields.append("ai_match = ?");  params.append(ai_match)
        if ai_score  is not None: fields.append("ai_score = ?");  params.append(ai_score)
        if ai_reason is not None: fields.append("ai_reason = ?"); params.append(ai_reason)
        if ai_gaps   is not None: fields.append("ai_gaps = ?");   params.append(ai_gaps)
        if ai_stage and ai_stage in valid_statuses:
            fields.append("status = ?")
            params.append(ai_stage)

        if not fields:
            skipped += 1
            continue

        params.append(url)
        conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE job_url = ?", params)
        updated += 1

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "updated": updated, "dismissed": dismissed_count, "skipped": skipped})


# ---------------------------------------------------------------------------
# Pipeline runner (background scrape → score → render)
# ---------------------------------------------------------------------------

_pipeline: dict = {
    "running": False,
    "log": [],
    "last_run": None,
    "exit_code": None,
}
_pipeline_lock = threading.Lock()


def _run_pipeline_bg(fast: bool = False) -> None:
    """Run the full job-radar pipeline in a background thread, capturing output."""
    cmd = [sys.executable, str(Path(__file__).parent / "run.py")]
    if fast:
        cmd.append("--fast")

    with _pipeline_lock:
        _pipeline["running"] = True
        _pipeline["log"] = ["[job-radar] pipeline started…"]
        _pipeline["exit_code"] = None

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            cwd=str(Path(__file__).parent),
        )
        for line in proc.stdout:
            with _pipeline_lock:
                _pipeline["log"].append(line.rstrip())
        proc.wait()
        exit_code = proc.returncode
    except Exception as exc:
        exit_code = -1
        with _pipeline_lock:
            _pipeline["log"].append(f"[error] {exc}")

    with _pipeline_lock:
        _pipeline["running"] = False
        _pipeline["exit_code"] = exit_code
        _pipeline["last_run"] = datetime.now(timezone.utc).isoformat()
        status = "✅ done" if exit_code == 0 else f"❌ exited with code {exit_code}"
        _pipeline["log"].append(f"[job-radar] {status}")


@app.route("/api/run-pipeline", methods=["POST"])
def run_pipeline():
    """Start the full scrape → score → render pipeline in the background."""
    with _pipeline_lock:
        if _pipeline["running"]:
            return jsonify({"error": "Pipeline already running"}), 409

    data = request.get_json(silent=True) or {}
    fast = bool(data.get("fast", False))
    thread = threading.Thread(target=_run_pipeline_bg, args=(fast,), daemon=True)
    thread.start()
    return jsonify({"started": True, "fast": fast})


@app.route("/api/pipeline-status")
def pipeline_status():
    """Return current pipeline state for the frontend to poll."""
    with _pipeline_lock:
        return jsonify({
            "running": _pipeline["running"],
            "log": list(_pipeline["log"]),
            "last_run": _pipeline["last_run"],
            "exit_code": _pipeline["exit_code"],
        })


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"job-radar server running on http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    app.run(host="0.0.0.0", port=PORT, debug=False)
