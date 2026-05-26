# Prompt 08 — Kanban Dashboard Rebuild
## Context
You are working on the `job-radar` project. Read `dashboard.py`, `server.py`, and `role_profiles.json` before making changes.

The current `dashboard.py` generates a static HTML file. We are rebuilding the dashboard as a **dynamic single-page app** that reads from the Flask API (`server.py`) instead of being generated server-side. The new dashboard is a Kanban board with role-family filters.

## Task — Rebuild `dashboard.py` and `dashboard.html`

### Step 1 — Update `dashboard.py`
Replace the contents of `dashboard.py` with this minimal version that just writes a static HTML shell. The actual data is loaded dynamically via JS from the API:

```python
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
    print("Run `python server.py` to view it at http://localhost:5000")


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>job radar</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Sortable/1.15.2/Sortable.min.js"></script>
<style>
:root {
  --bg: #0e0e0f;
  --bg-card: #1a1a1c;
  --bg-card-hover: #222226;
  --fg: #ededed;
  --muted: #888;
  --accent: #ff6b35;
  --accent-soft: #ff6b3520;
  --high: #4ade80;
  --mid: #facc15;
  --low: #94a3b8;
  --border: #2a2a2e;
  --col-width: 280px;

  /* role colours */
  --role-data_analyst: #3b82f6;
  --role-analytics_engineer: #14b8a6;
  --role-data_scientist: #8b5cf6;
  --role-product_manager: #f97316;
  --role-project_manager: #6b7280;
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
  background: var(--bg);
  z-index: 100;
  flex-wrap: wrap;
}
h1 { font-family: Georgia, serif; font-weight: 400; font-size: 1.5rem; }
h1 .accent { color: var(--accent); }
.stats { color: var(--muted); font-size: 0.8rem; }
.stats strong { color: var(--fg); }

/* ---- ROLE FILTER TABS ---- */
.role-tabs {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid var(--border);
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
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
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
  transition: background 0.15s, border-color 0.15s, transform 0.1s;
  position: relative;
}
.card:hover { background: var(--bg-card-hover); border-color: #3a3a3e; }
.card:active { cursor: grabbing; }
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.4rem;
  gap: 0.4rem;
}
.score-pill {
  font-size: 0.85rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  min-width: 2rem;
  text-align: center;
  flex-shrink: 0;
}
.score-high { background: #4ade8020; color: var(--high); }
.score-mid  { background: #facc1520; color: var(--mid); }
.score-low  { background: #94a3b820; color: var(--low); }
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

/* ---- MODAL ---- */
.modal-overlay {
  display: none;
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.7);
  z-index: 200;
  align-items: center;
  justify-content: center;
}
.modal-overlay.open { display: flex; }
.modal {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.5rem;
  width: 400px;
  max-width: 90vw;
}
.modal h3 { margin-bottom: 1rem; font-family: Georgia, serif; font-weight: 400; }
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
</style>
</head>
<body>

<div class="topbar">
  <h1>job <span class="accent">radar</span></h1>
  <div class="stats" id="stats">loading...</div>
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

async function loadJobs() {
  const res = await fetch("/api/jobs");
  allJobs = await res.json();
  renderBoard();
  updateStats();
}

function filteredJobs() {
  if (activeRole === "all") return allJobs;
  return allJobs.filter(j => j.primary_role === activeRole);
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
  const score = job.score || 0;
  const scoreBand = score >= 75 ? "high" : score >= 60 ? "mid" : "low";
  const salary = formatSalary(job);
  const role = job.primary_role || "";
  const roleLabel = ROLE_LABELS[role] || role;
  const reasons = (job.match_reasons || []).slice(0, 2).join(" · ") || "";

  const card = document.createElement("article");
  card.className = "card";
  card.dataset.url = job.job_url;
  card.innerHTML = `
    <div class="card-top">
      <div class="card-title">
        <a href="${job.job_url}" target="_blank" rel="noopener">${esc(job.title)}</a>
      </div>
      <div class="score-pill score-${scoreBand}">${score}</div>
    </div>
    <div class="card-company">${esc(job.company)} · ${esc(job.location || "")}</div>
    <div>
      <span class="role-tag ${role}">${roleLabel}</span>
      ${salary ? `<span class="salary-tag">💰 ${esc(salary)}</span>` : ""}
    </div>
    ${reasons ? `<div style="font-size:0.65rem;color:var(--muted);margin-top:0.3rem">${esc(reasons)}</div>` : ""}
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
  const jobs = filteredJobs();
  const total = jobs.length;
  const high = jobs.filter(j => (j.score || 0) >= 75).length;
  const applied = jobs.filter(j => j.status === "applied").length;
  document.getElementById("stats").innerHTML =
    `<strong>${total}</strong> jobs · <strong>${high}</strong> high-match · <strong>${applied}</strong> applied`;
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

function esc(str) {
  return String(str || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

loadJobs();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    write_dashboard()
```

### Step 2 — Update `run.py`
In `run.py`, change the `[3/3] rendering dashboard` section to call `write_dashboard()` instead of `OUTPUT_PATH.write_text(out)`:

```python
from dashboard import write_dashboard, OUTPUT_PATH

# replace:
#   out = render_dashboard()
#   OUTPUT_PATH.write_text(out)
# with:
write_dashboard()
```

Also update the print message at the end:
```python
print("\ndone. run `python server.py` then open http://localhost:5000")
```

## Validation
```bash
python run.py --no-scrape
python server.py
```
Open http://localhost:5000 in your browser.

Expected:
- Kanban board with 8 columns
- Role filter tabs at the top
- Cards with colour-coded role tags
- Drag a card between columns — it should move and the status should persist (check with `--no-scrape` run after)
- Click "✕ Dismiss" — reason modal should appear, job should disappear after confirming

## Do NOT
- Do not modify `scraper.py`, `scorer.py`, `server.py`, or `digest.py`
- Do not add the cover letter UI yet — that is Phase 4
- Do not add resume upload UI yet — that is Phase 3
