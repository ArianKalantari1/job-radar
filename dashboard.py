"""
job-radar: dashboard generator (v2 — Kanban)
Writes the static HTML shell. Data is loaded dynamically from the Flask API.
Run `python server.py` to serve the dashboard at http://localhost:5000
"""
from __future__ import annotations

from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "dashboard.html"


def render_dashboard() -> str:
    """Return the dashboard HTML shell. Data loaded dynamically via /api/jobs."""
    return DASHBOARD_HTML


def write_dashboard() -> None:
    OUTPUT_PATH.write_text(render_dashboard(), encoding="utf-8")
    print(f"Dashboard written to: {OUTPUT_PATH}")
    print("Run `python server.py` then open http://localhost:5000")


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>job radar</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Sortable/1.15.2/Sortable.min.js"></script>
<style>
:root {
  --bg: #f0f2f5;
  --bg-card: #ffffff;
  --bg-card-hover: #f8f9fb;
  --fg: #111827;
  --muted: #6b7280;
  --accent: #e85d2f;
  --accent-soft: #e85d2f18;
  --high: #16a34a;
  --mid: #d97706;
  --low: #64748b;
  --border: #e2e6ea;
  --col-width: 280px;

  /* role colours */
  --role-data_analyst: #2563eb;
  --role-analytics_engineer: #0d9488;
  --role-data_scientist: #7c3aed;
  --role-product_manager: #ea580c;
  --role-project_manager: #4b5563;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.5;
  overflow-x: auto;
}

/* ---- TOP BAR ---- */
.topbar {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: #ffffff;
  z-index: 100;
  flex-wrap: wrap;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
h1 { font-family: Georgia, serif; font-weight: 400; font-size: 1.5rem; }
h1 .accent { color: var(--accent); }
.stats { color: var(--muted); font-size: 0.8rem; }
.stats strong { color: var(--fg); }

.topbar-actions { margin-left: auto; display: flex; gap: 0.5rem; align-items: center; }
.btn-resume {
  font-size: 0.75rem;
  padding: 0.35rem 0.85rem;
  border-radius: 6px;
  border: 1px solid var(--accent);
  background: none;
  color: var(--accent);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}
.btn-resume:hover { background: var(--accent); color: #fff; }
.btn-resume.uploaded { border-color: var(--high); color: var(--high); }
.btn-resume.uploaded:hover { background: var(--high); color: #fff; }
.btn-gap {
  font-size: 0.75rem;
  padding: 0.35rem 0.85rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: none;
  color: var(--muted);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}
.btn-gap:hover { border-color: var(--fg); color: var(--fg); }
.btn-toggle {
  font-size: 0.75rem;
  padding: 0.35rem 0.85rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: none;
  color: var(--muted);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}
.btn-toggle:hover { border-color: var(--fg); color: var(--fg); }
.btn-toggle.active { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
.btn-csv-export, .btn-csv-import {
  font-size: 0.75rem;
  padding: 0.35rem 0.85rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: none;
  color: var(--muted);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}
.btn-csv-export:hover { border-color: #10b981; color: #10b981; }
.btn-csv-import:hover { border-color: #f59e0b; color: #f59e0b; }
.card.no-desc { opacity: 0.45; }
.no-desc-badge {
  font-size: 0.6rem;
  color: var(--mid);
  padding: 0.1rem 0.35rem;
  background: #fef3c7;
  border-radius: 3px;
  margin-left: 0.3rem;
}

/* ---- DATE FILTER PILLS ---- */
.date-filter-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1.5rem;
  background: #fff;
  border-bottom: 1px solid var(--border);
  font-size: 0.8rem;
}
.date-filter-bar label { color: var(--muted); font-weight: 500; margin-right: 0.25rem; }
.date-pill {
  padding: 0.2rem 0.7rem;
  border-radius: 99px;
  border: 1px solid var(--border);
  background: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.75rem;
  transition: all 0.15s;
}
.date-pill:hover { border-color: var(--fg); color: var(--fg); }
.date-pill.active { background: var(--accent); color: #fff; border-color: var(--accent); }

/* ---- SCORE FLOOR SLIDER ---- */
.score-floor-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 1.5rem;
  background: #fafafa;
  border-bottom: 1px solid var(--border);
  font-size: 0.8rem;
  color: var(--muted);
}
.score-floor-bar label { white-space: nowrap; font-weight: 500; }
.score-floor-bar input[type=range] { flex: 0 0 160px; accent-color: var(--accent); }
#scoreFloorVal { min-width: 2.5rem; font-weight: 700; color: var(--fg); }
#scoreFloorCount { color: var(--muted); font-size: 0.75rem; }

/* ---- ROLE FILTER TABS ---- */
.role-tabs {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid var(--border);
  background: #ffffff;
}
.role-tab {
  padding: 0.25rem 0.75rem;
  border-radius: 99px;
  font-size: 0.75rem;
  cursor: pointer;
  border: 1px solid var(--border);
  background: none;
  color: var(--muted);
  transition: all 0.15s;
}
.role-tab:hover { border-color: var(--fg); color: var(--fg); }
.role-tab.active { color: #fff; border-color: currentColor; }
.role-tab[data-role="all"] { border-color: var(--accent); }
.role-tab[data-role="all"].active { background: var(--accent); color: #fff; }
.role-tab[data-role="data_analyst"].active { background: var(--role-data_analyst); }
.role-tab[data-role="analytics_engineer"].active { background: var(--role-analytics_engineer); }
.role-tab[data-role="data_scientist"].active { background: var(--role-data_scientist); }
.role-tab[data-role="product_manager"].active { background: var(--role-product_manager); }
.role-tab[data-role="project_manager"].active { background: var(--role-project_manager); }

/* ---- KANBAN ---- */
.kanban {
  display: flex;
  gap: 0.75rem;
  padding: 1rem 1.5rem 2rem;
  min-height: calc(100vh - 130px);
  overflow-x: auto;
}
.column {
  min-width: var(--col-width);
  max-width: var(--col-width);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.col-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.75rem;
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.col-header .count {
  background: var(--border);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-size: 0.7rem;
}
.drop-zone {
  flex: 1;
  min-height: 80px;
  border-radius: 6px;
  border: 1px dashed var(--border);
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.drop-zone.drag-over { border-color: var(--accent); background: var(--accent-soft); }

/* ---- CARDS ---- */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.75rem;
  cursor: grab;
  transition: background 0.15s, border-color 0.15s, transform 0.1s, box-shadow 0.15s;
  position: relative;
  box-shadow: 0 1px 3px rgba(0,0,0,0.07);
}
.card:hover { background: var(--bg-card-hover); border-color: #c8cdd3; box-shadow: 0 3px 8px rgba(0,0,0,0.1); }
.card:active { cursor: grabbing; }
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.4rem;
  gap: 0.4rem;
}
.score-block { display: flex; flex-direction: column; align-items: center; gap: 0.15rem; flex-shrink: 0; }
.score-pill {
  font-size: 0.85rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  min-width: 2rem;
  text-align: center;
}
.score-high { background: #dcfce7; color: var(--high); }
.score-mid  { background: #fef3c7; color: var(--mid); }
.score-low  { background: #f1f5f9; color: var(--low); }
.match-pill {
  font-size: 0.6rem;
  font-weight: 700;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  text-align: center;
  min-width: 2rem;
  background: #ede9fe;
  color: #6d28d9;
  white-space: nowrap;
}
.ai-score-pill {
  font-size: 0.6rem;
  font-weight: 700;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  text-align: center;
  min-width: 2rem;
  white-space: nowrap;
}
.ai-score-yes    { background: #dcfce7; color: #15803d; }
.ai-score-maybe  { background: #fef9c3; color: #a16207; }
.ai-score-no     { background: #fee2e2; color: #b91c1c; }
.ai-reason {
  font-size: 0.65rem;
  color: var(--muted);
  margin-top: 0.3rem;
  line-height: 1.35;
}
.ai-gaps {
  font-size: 0.62rem;
  color: #c2410c;
  background: #fff7ed;
  border-left: 2px solid #f97316;
  padding: 0.15rem 0.35rem;
  margin-top: 0.3rem;
  border-radius: 0 3px 3px 0;
  line-height: 1.3;
}

/* ---- PIPELINE BUTTON ---- */
.btn-run {
  font-size: 0.75rem;
  padding: 0.35rem 0.85rem;
  border-radius: 6px;
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  font-family: inherit;
  font-weight: 600;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.btn-run:hover:not(:disabled) { background: #c94d23; border-color: #c94d23; }
.btn-run:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-run.running { background: var(--mid); border-color: var(--mid); animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.65; } }

/* ---- PIPELINE MODAL ---- */
#pipelineModal .modal { width: 600px; max-width: 95vw; }
.pipeline-log {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 0.72rem;
  background: #0f172a;
  color: #94a3b8;
  border-radius: 6px;
  padding: 0.75rem 1rem;
  height: 320px;
  overflow-y: auto;
  margin: 1rem 0;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
.pipeline-log .log-done   { color: #4ade80; font-weight: 700; }
.pipeline-log .log-error  { color: #f87171; font-weight: 700; }
.pipeline-log .log-info   { color: #e2e8f0; }
.pipeline-status-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.78rem;
  color: var(--muted);
  margin-bottom: 0.75rem;
}
.pipeline-spinner {
  display: inline-block;
  width: 10px; height: 10px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.pipeline-mode {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.pipeline-mode label {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.78rem;
  cursor: pointer;
  color: var(--muted);
}
.pipeline-mode label:hover { color: var(--fg); }
.card-title {
  font-family: Georgia, serif;
  font-size: 0.85rem;
  line-height: 1.3;
  flex: 1;
}
.card-title a { color: var(--fg); text-decoration: none; }
.card-title a:hover { color: var(--accent); }
.card-company { font-size: 0.72rem; color: var(--muted); margin-bottom: 0.4rem; }
.role-tag {
  display: inline-block;
  font-size: 0.65rem;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  margin-bottom: 0.4rem;
  opacity: 0.85;
  color: #fff;
}
.role-tag.data_analyst      { background: var(--role-data_analyst); }
.role-tag.analytics_engineer { background: var(--role-analytics_engineer); }
.role-tag.data_scientist    { background: var(--role-data_scientist); }
.role-tag.product_manager   { background: var(--role-product_manager); }
.role-tag.project_manager   { background: var(--role-project_manager); }

.salary-tag {
  font-size: 0.65rem;
  color: var(--accent);
  margin-left: 0.4rem;
}
.card-actions {
  display: flex;
  gap: 0.3rem;
  margin-top: 0.5rem;
}
.btn-dismiss {
  font-size: 0.65rem;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  background: none;
  border: 1px solid var(--border);
  color: var(--muted);
  cursor: pointer;
}
.btn-dismiss:hover { border-color: #e55; color: #e55; }

/* ---- MODAL (shared) ---- */
.modal-overlay {
  display: none;
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.6);
  z-index: 200;
  align-items: center;
  justify-content: center;
}
.modal-overlay.open { display: flex; }
.modal {
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.5rem;
  width: 480px;
  max-width: 92vw;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0,0,0,0.18);
}
.modal h3 { margin-bottom: 1rem; font-family: Georgia, serif; font-weight: 400; font-size: 1.1rem; }
.dismiss-reasons { display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 1rem; }
.dismiss-reasons button {
  padding: 0.4rem 0.75rem;
  background: none;
  border: 1px solid var(--border);
  color: var(--fg);
  border-radius: 4px;
  cursor: pointer;
  text-align: left;
  font-size: 0.8rem;
}
.dismiss-reasons button:hover { border-color: var(--accent); color: var(--accent); }
.modal-cancel {
  font-size: 0.75rem;
  color: var(--muted);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.4rem;
}
.modal-cancel:hover { color: var(--fg); }

/* ---- RESUME MODAL ---- */
#resumeModal .modal { width: 420px; }
.upload-area {
  border: 2px dashed var(--border);
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  color: var(--muted);
  transition: border-color 0.15s, background 0.15s;
  margin-bottom: 1rem;
}
.upload-area:hover, .upload-area.drag-active {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
}
.upload-area p { font-size: 0.85rem; margin-top: 0.5rem; }
.resume-status {
  font-size: 0.8rem;
  color: var(--muted);
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: var(--bg);
  border-radius: 6px;
}
.resume-status.ok { color: var(--high); }
.resume-skills {
  font-size: 0.7rem;
  color: var(--muted);
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.5rem;
}
.skill-chip {
  padding: 0.15rem 0.4rem;
  background: #ede9fe;
  color: #6d28d9;
  border-radius: 3px;
}
.upload-progress {
  display: none;
  font-size: 0.8rem;
  color: var(--muted);
  text-align: center;
  padding: 0.5rem;
}

/* ---- GAP ANALYSIS MODAL ---- */
#gapModal .modal { width: 520px; }
.gap-list { display: flex; flex-direction: column; gap: 0.5rem; margin-top: 1rem; }
.gap-item { display: flex; align-items: center; gap: 0.75rem; }
.gap-skill { font-size: 0.8rem; min-width: 140px; font-weight: 500; }
.gap-bar-wrap { flex: 1; background: var(--border); border-radius: 99px; height: 8px; }
.gap-bar { background: var(--accent); border-radius: 99px; height: 8px; transition: width 0.4s; }
.gap-count { font-size: 0.7rem; color: var(--muted); min-width: 50px; text-align: right; }
.gap-intro { font-size: 0.82rem; color: var(--muted); line-height: 1.6; }
</style>
</head>
<body>

<div class="topbar">
  <h1>job <span class="accent">radar</span></h1>
  <div class="stats" id="stats">loading...</div>
  <div class="topbar-actions">
    <button class="btn-run" id="btnRun" onclick="openPipelineModal()">▶ Run scraper</button>
    <button class="btn-toggle active" id="btnHideNoDesc" onclick="toggleHideNoDesc()" title="Hide jobs with no description">🚫 No description</button>
    <button class="btn-csv-export" onclick="exportCSV()" title="Export jobs to CSV for AI review">⬇️ Export CSV</button>
    <button class="btn-csv-import" onclick="document.getElementById('csvFileInput').click()" title="Import AI-reviewed CSV back to update job stages">⬆️ Import CSV</button>
    <input type="file" id="csvFileInput" accept=".csv" style="display:none" onchange="importCSV(this)">
    <button class="btn-resume" id="btnResume" onclick="openResumeModal()">📄 Upload Resume</button>
    <button class="btn-gap" id="btnGap" onclick="openGapModal()" style="display:none">🧠 Skill Gaps</button>
  </div>
</div>

<div class="date-filter-bar">
  <label>Showing:</label>
  <button class="date-pill" data-days="1" onclick="setDateFilter(1)">Today</button>
  <button class="date-pill active" data-days="2" onclick="setDateFilter(2)">Today + Yesterday</button>
  <button class="date-pill" data-days="7" onclick="setDateFilter(7)">Last 7 days</button>
  <button class="date-pill" data-days="0" onclick="setDateFilter(0)">All time</button>
</div>

<div class="score-floor-bar">
  <label for="scoreFloor">Min score</label>
  <input type="range" id="scoreFloor" min="0" max="90" step="5" value="50"
         oninput="onScoreFloorChange(this.value)">
  <span id="scoreFloorVal">50</span>
  <span id="scoreFloorCount"></span>
</div>

<div class="role-tabs" id="roleTabs">
  <button class="role-tab active" data-role="all">All roles</button>
  <button class="role-tab" data-role="data_analyst">Data Analyst</button>
  <button class="role-tab" data-role="analytics_engineer">Analytics Engineer</button>
  <button class="role-tab" data-role="data_scientist">Data Scientist</button>
  <button class="role-tab" data-role="product_manager">PM (AI/Data)</button>
  <button class="role-tab" data-role="project_manager">Project Manager</button>
</div>

<div class="kanban" id="kanban"></div>

<!-- Dismiss modal -->
<div class="modal-overlay" id="dismissModal">
  <div class="modal">
    <h3>Why not this job?</h3>
    <div class="dismiss-reasons">
      <button onclick="confirmDismiss('Job no longer available')">🚫 Job no longer available</button>
      <button onclick="confirmDismiss('Too senior')">Too senior</button>
      <button onclick="confirmDismiss('Too junior')">Too junior</button>
      <button onclick="confirmDismiss('Wrong tech stack')">Wrong tech stack</button>
      <button onclick="confirmDismiss('Bad location')">Bad location</button>
      <button onclick="confirmDismiss('Salary too low')">Salary too low</button>
      <button onclick="confirmDismiss('Not interested in company')">Not interested in company</button>
      <button onclick="confirmDismiss('Other')">Other</button>
    </div>
    <button class="modal-cancel" onclick="closeDismissModal()">Cancel</button>
  </div>
</div>

<!-- Resume upload modal -->
<div class="modal-overlay" id="resumeModal">
  <div class="modal">
    <h3>📄 Resume Match</h3>
    <div id="resumeStatus" class="resume-status">Checking...</div>
    <div
      class="upload-area"
      id="uploadArea"
      onclick="document.getElementById('resumeFile').click()"
      ondragover="event.preventDefault(); this.classList.add('drag-active')"
      ondragleave="this.classList.remove('drag-active')"
      ondrop="handleDrop(event)"
    >
      <div style="font-size:2rem">📄</div>
      <p>Click or drag & drop your resume PDF here</p>
      <p style="font-size:0.7rem;margin-top:0.25rem">PDF files only · text extracted automatically</p>
    </div>
    <input type="file" id="resumeFile" accept=".pdf" style="display:none" onchange="uploadResume(this.files[0])"/>
    <div class="upload-progress" id="uploadProgress">⏳ Uploading and scoring jobs…</div>
    <button class="modal-cancel" onclick="closeResumeModal()">Close</button>
  </div>
</div>

<!-- Gap analysis modal -->
<div class="modal-overlay" id="gapModal">
  <div class="modal">
    <h3>🧠 Skill Gap Analysis</h3>
    <p class="gap-intro">
      Skills that appear most often in active job postings but are <strong>missing from your resume</strong>.
      Add these to close the gap and score higher.
    </p>
    <div class="gap-list" id="gapList">Loading…</div>
    <button class="modal-cancel" onclick="closeGapModal()" style="margin-top:1rem">Close</button>
  </div>
</div>

<!-- Pipeline runner modal -->
<div class="modal-overlay" id="pipelineModal">
  <div class="modal">
    <h3>▶ Run scraper</h3>
    <p style="font-size:0.8rem;color:var(--muted);margin-bottom:0.75rem">
      Scrapes fresh jobs from Seek, Indeed &amp; Google, scores them with Claude, and refreshes the board.
    </p>

    <div class="pipeline-mode">
      <label>
        <input type="radio" name="pipelineMode" value="ai" checked>
        <span><strong>Full run</strong> — scrape + Claude AI scoring (~$0.15–0.30)</span>
      </label>
      <label>
        <input type="radio" name="pipelineMode" value="fast">
        <span><strong>Fast run</strong> — scrape + rules-based scoring (free)</span>
      </label>
    </div>

    <div class="pipeline-status-bar" id="pipelineStatusBar" style="display:none">
      <span class="pipeline-spinner" id="pipelineSpinner"></span>
      <span id="pipelineStatusText">Starting…</span>
    </div>

    <div class="pipeline-log" id="pipelineLog" style="display:none"></div>

    <div style="display:flex;gap:0.5rem;align-items:center;margin-top:0.25rem">
      <button class="btn-run" id="btnRunStart" onclick="startPipeline()">▶ Start</button>
      <button class="modal-cancel" onclick="closePipelineModal()">Close</button>
      <span id="pipelineLastRun" style="font-size:0.7rem;color:var(--muted);margin-left:auto"></span>
    </div>
  </div>
</div>

<script>
const COLUMNS = [
  { id: "new",          label: "New" },
  { id: "saved",        label: "Saved" },
  { id: "applying",     label: "Applying" },
  { id: "applied",      label: "Applied" },
  { id: "phone_screen", label: "Phone Screen" },
  { id: "interview",    label: "Interview" },
  { id: "offer",        label: "Offer 🎉" },
  { id: "rejected",     label: "Rejected" },
];

const ROLE_LABELS = {
  data_analyst: "Data Analyst",
  analytics_engineer: "Analytics Eng",
  data_scientist: "Data Scientist",
  product_manager: "PM (AI)",
  project_manager: "Project Mgr",
};

let allJobs = [];
let activeRole = "all";
let dismissJobUrl = null;
let resumeUploaded = false;
let hideNoDesc = true;
let currentScoreFloor = 50;
let currentDays = 2;

async function loadJobs(minScore, days) {
  if (minScore === undefined) minScore = currentScoreFloor;
  if (days === undefined) days = currentDays;
  const res = await fetch(`/api/jobs?min_score=${minScore}&days=${days}`);
  allJobs = await res.json();
  renderBoard();
  updateStats();
  const countEl = document.getElementById("scoreFloorCount");
  if (countEl) countEl.textContent = `· ${allJobs.length} jobs shown`;
}

function onScoreFloorChange(val) {
  currentScoreFloor = parseInt(val, 10);
  document.getElementById("scoreFloorVal").textContent = val;
  loadJobs(currentScoreFloor, currentDays);
}

function setDateFilter(days) {
  currentDays = days;
  document.querySelectorAll(".date-pill").forEach(btn => {
    btn.classList.toggle("active", parseInt(btn.dataset.days) === days);
  });
  loadJobs(currentScoreFloor, currentDays);
}

function toggleHideNoDesc() {
  hideNoDesc = !hideNoDesc;
  const btn = document.getElementById("btnHideNoDesc");
  btn.classList.toggle("active", hideNoDesc);
  renderBoard();
  updateStats();
}

function exportCSV() {
  const params = new URLSearchParams();
  if (activeRole !== "all") params.set("role", activeRole);
  if (currentDays > 0) params.set("days", currentDays);
  const qs = params.toString() ? `?${params.toString()}` : "";
  window.location.href = `/api/export-csv${qs}`;
}

async function importCSV(input) {
  const file = input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const btn = document.querySelector(".btn-csv-import");
  btn.textContent = "⏳ Importing…";
  btn.disabled = true;
  try {
    const res = await fetch("/api/import-csv", { method: "POST", body: form });
    const data = await res.json();
    if (data.ok) {
      alert(`✅ Import done!\n${data.updated} jobs updated, ${data.skipped} skipped.\n\nPage will refresh to show new stages.`);
      location.reload();
    } else {
      alert("❌ Import failed: " + (data.error || JSON.stringify(data)));
    }
  } catch (e) {
    alert("❌ Error: " + e.message);
  } finally {
    btn.textContent = "⬆️ Import CSV";
    btn.disabled = false;
    input.value = "";
  }
}

function filteredJobs() {
  let jobs = activeRole === "all" ? allJobs : allJobs.filter(j => j.primary_role === activeRole);
  if (hideNoDesc) {
    jobs = jobs.filter(j => j.description && j.description.length > 50);
  }
  // Sort: resume match % (if uploaded) > ai_score > rules score
  jobs = [...jobs].sort((a, b) => {
    if (resumeUploaded) {
      const am = a.resume_match_pct != null ? a.resume_match_pct : -1;
      const bm = b.resume_match_pct != null ? b.resume_match_pct : -1;
      if (bm !== am) return bm - am;
    }
    const as_ = a.ai_score ?? a.score ?? 0;
    const bs_ = b.ai_score ?? b.score ?? 0;
    return bs_ - as_;
  });
  return jobs;
}

function renderBoard() {
  const jobs = filteredJobs();
  const kanban = document.getElementById("kanban");
  kanban.innerHTML = "";

  COLUMNS.forEach(col => {
    const colJobs = jobs.filter(j => (j.status || "new") === col.id);
    const colEl = document.createElement("div");
    colEl.className = "column";
    colEl.innerHTML = `
      <div class="col-header">
        ${col.label}
        <span class="count">${colJobs.length}</span>
      </div>
      <div class="drop-zone" data-status="${col.id}" id="col-${col.id}"></div>
    `;
    kanban.appendChild(colEl);
    const zone = colEl.querySelector(".drop-zone");
    colJobs.forEach(job => zone.appendChild(buildCard(job)));
    new Sortable(zone, {
      group: "kanban",
      animation: 150,
      onEnd: async (evt) => {
        const jobUrl = evt.item.dataset.url;
        const newStatus = evt.to.dataset.status;
        await fetch(`/api/jobs/${encodeURIComponent(jobUrl)}/status`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus }),
        });
        const job = allJobs.find(j => j.job_url === jobUrl);
        if (job) job.status = newStatus;
        updateStats();
      },
    });
  });
}

function buildCard(job) {
  const score = job.ai_score ?? job.score ?? 0;
  const scoreBand = score >= 75 ? "high" : score >= 60 ? "mid" : "low";
  const salary = formatSalary(job);
  const role = job.primary_role || "";
  const roleLabel = ROLE_LABELS[role] || role;
  const reasons = (job.match_reasons || []).slice(0, 2).join(" · ") || "";
  const hasDesc = job.description && job.description.length > 50;

  // AI scorer fields
  const aiMatch = job.ai_match || null;   // "yes" | "maybe" | "no" | null
  const aiScore = job.ai_score != null ? job.ai_score : null;
  const aiReason = job.ai_reason || null;
  const aiGaps = (job.ai_gaps && job.ai_gaps.toLowerCase() !== "none") ? job.ai_gaps : null;

  const aiScoreBadge = aiScore != null
    ? `<div class="ai-score-pill ai-score-${aiMatch || 'no'}">AI ${aiScore}</div>`
    : "";

  const matchPct = job.resume_match_pct;
  const matchBadge = (resumeUploaded && matchPct != null)
    ? `<div class="match-pill">${matchPct}% match</div>`
    : "";

  const noDescBadge = !hasDesc
    ? `<span class="no-desc-badge">no description</span>`
    : "";

  const card = document.createElement("article");
  card.className = "card" + (!hasDesc ? " no-desc" : "");
  card.dataset.url = job.job_url;
  card.innerHTML = `
    <div class="card-top">
      <div class="card-title">
        <a href="${job.job_url}" target="_blank" rel="noopener">${esc(job.title)}</a>${noDescBadge}
      </div>
      <div class="score-block">
        <div class="score-pill score-${scoreBand}">${score}</div>
        ${aiScoreBadge}
        ${matchBadge}
      </div>
    </div>
    <div class="card-company">${esc(job.company)} · ${esc(job.location || "")}</div>
    <div>
      <span class="role-tag ${role}">${roleLabel}</span>
      ${salary ? `<span class="salary-tag">💰 ${esc(salary)}</span>` : ""}
    </div>
    ${aiReason ? `<div class="ai-reason">🤖 ${esc(aiReason)}</div>` : reasons ? `<div style="font-size:0.65rem;color:var(--muted);margin-top:0.3rem">${esc(reasons)}</div>` : ""}
    ${aiGaps ? `<div class="ai-gaps">⚠ ${esc(aiGaps)}</div>` : ""}
    <div class="card-actions">
      <button class="btn-dismiss" onclick="openDismissModal('${esc(job.job_url)}')">✕ Dismiss</button>
    </div>
  `;
  return card;
}

function formatSalary(job) {
  const lo = job.salary_min || job.min_amount;
  const hi = job.salary_max || job.max_amount;
  if (lo && hi) return `$${Math.round(lo/1000)}k–$${Math.round(hi/1000)}k`;
  if (lo) return `$${Math.round(lo/1000)}k+`;
  return "";
}

function updateStats() {
  const all = filteredJobs();
  const total = allJobs.filter(j => activeRole === "all" || j.primary_role === activeRole).length;
  const withDesc = all.filter(j => j.description && j.description.length > 50).length;
  const high = all.filter(j => (j.score || 0) >= 75).length;
  const applied = all.filter(j => j.status === "applied").length;
  const hidden = total - withDesc;
  const matchInfo = resumeUploaded
    ? ` · <strong>${all.filter(j => (j.resume_match_pct || 0) >= 60).length}</strong> resume≥60%`
    : "";
  const hideInfo = hideNoDesc && hidden > 0
    ? ` · <span style="color:var(--mid)">${hidden} hidden (no description)</span>`
    : "";
  document.getElementById("stats").innerHTML =
    `<strong>${all.length}</strong> jobs · <strong>${high}</strong> high-match · <strong>${applied}</strong> applied${matchInfo}${hideInfo}`;
}

// Role filter tabs
document.getElementById("roleTabs").addEventListener("click", (e) => {
  const tab = e.target.closest(".role-tab");
  if (!tab) return;
  document.querySelectorAll(".role-tab").forEach(t => t.classList.remove("active"));
  tab.classList.add("active");
  activeRole = tab.dataset.role;
  renderBoard();
  updateStats();
});

// Dismiss modal
function openDismissModal(url) {
  dismissJobUrl = url;
  document.getElementById("dismissModal").classList.add("open");
}
function closeDismissModal() {
  dismissJobUrl = null;
  document.getElementById("dismissModal").classList.remove("open");
}
async function confirmDismiss(reason) {
  if (!dismissJobUrl) return;
  await fetch(`/api/jobs/${encodeURIComponent(dismissJobUrl)}/dismiss`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  allJobs = allJobs.filter(j => j.job_url !== dismissJobUrl);
  closeDismissModal();
  renderBoard();
  updateStats();
}

// ---- Resume modal ----
async function openResumeModal() {
  document.getElementById("resumeModal").classList.add("open");
  const res = await fetch("/api/resume");
  const data = await res.json();
  const statusEl = document.getElementById("resumeStatus");
  if (data.uploaded) {
    resumeUploaded = true;
    const skillChips = (data.skills || []).map(s => `<span class="skill-chip">${esc(s)}</span>`).join("");
    statusEl.className = "resume-status ok";
    statusEl.innerHTML = `✅ Resume loaded · ${data.chars} chars detected<br>
      <span style="color:var(--muted);font-size:0.7rem">Skills found on your resume:</span>
      <div class="resume-skills">${skillChips || "<em>none detected yet</em>"}</div>`;
    document.getElementById("btnResume").className = "btn-resume uploaded";
    document.getElementById("btnResume").textContent = "📄 Resume ✓";
    document.getElementById("btnGap").style.display = "";
  } else {
    statusEl.className = "resume-status";
    statusEl.textContent = "No resume uploaded yet. Upload your PDF below.";
  }
}
function closeResumeModal() {
  document.getElementById("resumeModal").classList.remove("open");
}
function handleDrop(event) {
  event.preventDefault();
  document.getElementById("uploadArea").classList.remove("drag-active");
  const file = event.dataTransfer.files[0];
  if (file) uploadResume(file);
}
async function uploadResume(file) {
  if (!file) return;
  document.getElementById("uploadProgress").style.display = "block";
  document.getElementById("uploadArea").style.pointerEvents = "none";
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await fetch("/api/resume", { method: "POST", body: form });
    const data = await res.json();
    if (data.ok) {
      resumeUploaded = true;
      document.getElementById("btnResume").className = "btn-resume uploaded";
      document.getElementById("btnResume").textContent = "📄 Resume ✓";
      document.getElementById("btnGap").style.display = "";
      // Reload jobs to get updated match %
      await loadJobs();
      await openResumeModal();
    } else {
      alert("Upload failed: " + (data.error || "unknown error"));
    }
  } catch (e) {
    alert("Upload failed: " + e);
  } finally {
    document.getElementById("uploadProgress").style.display = "none";
    document.getElementById("uploadArea").style.pointerEvents = "";
  }
}

// ---- Gap analysis modal ----
async function openGapModal() {
  document.getElementById("gapModal").classList.add("open");
  const listEl = document.getElementById("gapList");
  listEl.innerHTML = "Loading…";
  try {
    const res = await fetch("/api/gap-analysis");
    if (!res.ok) {
      const err = await res.json();
      listEl.innerHTML = `<p style="color:#e55;font-size:0.8rem">${esc(err.error || "Error loading gaps")}</p>`;
      return;
    }
    const data = await res.json();
    if (!data.gaps || data.gaps.length === 0) {
      listEl.innerHTML = `<p style="color:var(--muted);font-size:0.8rem">No skill gaps detected. Great news!</p>`;
      return;
    }
    const max = data.gaps[0].job_count;
    listEl.innerHTML = data.gaps.map(g => `
      <div class="gap-item">
        <span class="gap-skill">${esc(g.skill)}</span>
        <div class="gap-bar-wrap">
          <div class="gap-bar" style="width:${Math.round(g.job_count/max*100)}%"></div>
        </div>
        <span class="gap-count">${g.job_count} job${g.job_count !== 1 ? "s" : ""}</span>
      </div>
    `).join("");
    listEl.insertAdjacentHTML("afterbegin",
      `<p style="font-size:0.72rem;color:var(--muted);margin-bottom:0.75rem">
        Analysed ${data.total_jobs_analysed} jobs · top ${data.gaps.length} missing skills shown
      </p>`);
  } catch (e) {
    listEl.innerHTML = `<p style="color:#e55;font-size:0.8rem">Failed to load: ${esc(String(e))}</p>`;
  }
}
function closeGapModal() {
  document.getElementById("gapModal").classList.remove("open");
}

// Close modals on overlay click
document.querySelectorAll(".modal-overlay").forEach(el => {
  el.addEventListener("click", e => {
    if (e.target === el) el.classList.remove("open");
  });
});

function esc(str) {
  return String(str || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// Check resume status on load (to restore upload button state without opening modal)
async function checkResumeOnLoad() {
  try {
    const res = await fetch("/api/resume");
    const data = await res.json();
    if (data.uploaded) {
      resumeUploaded = true;
      document.getElementById("btnResume").className = "btn-resume uploaded";
      document.getElementById("btnResume").textContent = "📄 Resume ✓";
      document.getElementById("btnGap").style.display = "";
    }
  } catch (e) { /* ignore */ }
}

loadJobs().then(checkResumeOnLoad);

// ---- Pipeline runner ----
let _pipelinePoll = null;
let _pipelineLogLen = 0;

async function openPipelineModal() {
  document.getElementById("pipelineModal").classList.add("open");
  // Check if something's already running (e.g. server was mid-run when page loaded)
  const status = await fetch("/api/pipeline-status").then(r => r.json()).catch(() => null);
  if (status && status.running) {
    _startPolling();
  } else if (status && status.last_run) {
    const when = new Date(status.last_run).toLocaleString();
    document.getElementById("pipelineLastRun").textContent = `Last run: ${when}`;
    if (status.log && status.log.length) {
      showLog(status.log);
    }
  }
}

function closePipelineModal() {
  document.getElementById("pipelineModal").classList.remove("open");
  // Keep polling alive in background so button state stays correct
}

async function startPipeline() {
  const fast = document.querySelector('input[name="pipelineMode"]:checked').value === "fast";
  const btn = document.getElementById("btnRunStart");
  btn.disabled = true;
  btn.textContent = "Starting…";

  try {
    const res = await fetch("/api/run-pipeline", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fast }),
    });
    const data = await res.json();
    if (res.status === 409) {
      // Already running
    } else if (!data.started) {
      btn.disabled = false;
      btn.textContent = "▶ Start";
      return;
    }
    _startPolling();
  } catch (e) {
    btn.disabled = false;
    btn.textContent = "▶ Start";
    alert("Could not start pipeline: " + e);
  }
}

function _startPolling() {
  _pipelineLogLen = 0;
  document.getElementById("pipelineStatusBar").style.display = "flex";
  document.getElementById("pipelineLog").style.display = "block";
  document.getElementById("btnRunStart").disabled = true;
  document.getElementById("btnRunStart").textContent = "Running…";
  document.getElementById("btnRun").classList.add("running");
  document.getElementById("btnRun").textContent = "⏳ Running…";

  if (_pipelinePoll) clearInterval(_pipelinePoll);
  _pipelinePoll = setInterval(_pollStatus, 2000);
  _pollStatus(); // immediate first tick
}

async function _pollStatus() {
  try {
    const data = await fetch("/api/pipeline-status").then(r => r.json());

    // Append only new log lines (avoid redrawing whole log)
    if (data.log && data.log.length > _pipelineLogLen) {
      const newLines = data.log.slice(_pipelineLogLen);
      _pipelineLogLen = data.log.length;
      const logEl = document.getElementById("pipelineLog");
      newLines.forEach(line => {
        const div = document.createElement("div");
        div.className = line.startsWith("[job-radar] ✅") ? "log-done"
                      : line.startsWith("[job-radar] ❌") || line.startsWith("[error]") ? "log-error"
                      : "log-info";
        div.textContent = line;
        logEl.appendChild(div);
      });
      logEl.scrollTop = logEl.scrollHeight;
    }

    const statusText = document.getElementById("pipelineStatusText");
    if (data.running) {
      const last = data.log && data.log.length ? data.log[data.log.length - 1] : "running…";
      statusText.textContent = last.replace(/^\[job-radar\]\s*/, "");
    }

    if (!data.running && data.exit_code !== null) {
      // Done
      clearInterval(_pipelinePoll);
      _pipelinePoll = null;

      document.getElementById("pipelineSpinner").style.display = "none";
      statusText.textContent = data.exit_code === 0 ? "✅ Done!" : `❌ Finished with errors (code ${data.exit_code})`;

      const btn = document.getElementById("btnRunStart");
      btn.disabled = false;
      btn.textContent = "▶ Run again";

      document.getElementById("btnRun").classList.remove("running");
      document.getElementById("btnRun").textContent = "▶ Run scraper";

      if (data.last_run) {
        document.getElementById("pipelineLastRun").textContent =
          `Last run: ${new Date(data.last_run).toLocaleString()}`;
      }

      // Reload jobs in the background so the board is fresh
      if (data.exit_code === 0) {
        await loadJobs();
      }
    }
  } catch (e) {
    // Network hiccup — keep polling
  }
}

function showLog(lines) {
  const logEl = document.getElementById("pipelineLog");
  logEl.innerHTML = "";
  logEl.style.display = "block";
  _pipelineLogLen = lines.length;
  lines.forEach(line => {
    const div = document.createElement("div");
    div.className = line.includes("✅") ? "log-done"
                  : line.includes("❌") || line.includes("[error]") ? "log-error"
                  : "log-info";
    div.textContent = line;
    logEl.appendChild(div);
  });
  logEl.scrollTop = logEl.scrollHeight;
}

// On page load: check if pipeline is already running (e.g. server restarted mid-run)
(async () => {
  try {
    const data = await fetch("/api/pipeline-status").then(r => r.json());
    if (data.running) {
      document.getElementById("btnRun").classList.add("running");
      document.getElementById("btnRun").textContent = "⏳ Running…";
      _startPolling();
    } else if (data.last_run) {
      document.getElementById("pipelineLastRun") &&
        (document.getElementById("pipelineLastRun").textContent = "");
    }
  } catch (e) { /* ignore */ }
})();

loadJobs().then(checkResumeOnLoad);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    write_dashboard()
