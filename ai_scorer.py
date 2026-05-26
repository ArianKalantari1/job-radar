"""
job-radar: Claude API scorer
Scores each job against Arian's CV using semantic matching.
Only scores jobs that have a meaningful description (≥300 chars).
Jobs without enough description are skipped and logged — run the description
backfiller first, then come back to score them.

Usage:
    python ai_scorer.py                  # score all unscored jobs with descriptions
    python ai_scorer.py --limit 10       # test on first 10 (check quality before bulk)
    python ai_scorer.py --rescore        # force re-score ALL jobs (wipe existing ai_scores)
    python ai_scorer.py --rescore --limit 20  # re-score just 20 (calibration)

Cost: ~$0.001-0.003 per job (claude-haiku). Jobs without descriptions are never charged.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import anthropic

DB_PATH = Path(__file__).parent / "jobs.db"

# Minimum description length to attempt scoring.
# Below this threshold we have almost no signal — just a job title and a teaser.
# The description backfiller will eventually fetch the full text; score then.
MIN_DESC_CHARS = 300

# How many chars of the description to send to the model.
# 5000 chars ≈ ~1000 tokens — enough to cover full JDs without excessive cost.
DESC_WINDOW = 5000

# Jobs scoring below this threshold are automatically dismissed after scoring.
# They stay in the DB for auditing but disappear from the board immediately.
# Set to 0 to disable auto-dismiss.
AUTO_DISMISS_BELOW = 40

# ---------------------------------------------------------------------------
# Candidate CV — single source of truth for scoring
# ---------------------------------------------------------------------------
CV = """
ARIAN KALANTARI — Analytics Engineer | 4 years delivery consulting | Bilingual EN/JP

BACKGROUND CONTEXT (important for calibration):
- Early-career: ~4 years total experience but most of it is in consulting/PM, not pure engineering
- Engineering depth is real but recent: Domain internship (5 months), self-built AI projects
- Strong on delivery, stakeholder management, cross-functional work
- Genuinely strong on LLMs/RAG from self-directed projects — not just buzzwords
- Visa 485: full work rights, but cannot apply for citizenship-required or clearance roles

CURRENT PROJECTS:
- PatientFlow: Product Lead. On-device AI agent for GP medical documentation. Local LLM inference, healthcare data sovereignty. Plus Eight Sprint #3 finalist. Western Sydney AI Innovation Hackathon finalist.
- CareerSync: RAG-based resume feedback system. FastAPI, ChromaDB, LLM APIs (Claude + OpenAI). Three-layer prompt injection defence (input sanitisation, hardened system prompt, output validator). Hybrid evaluation engine (rule-based + AI checks, schema validation).
- job-radar: Personal job board scraper built in Python.

WORK EXPERIENCE:
- Analytics Engineer Intern, Domain Group (Jul-Nov 2025): Snowflake, dbt, Streamlit. Built production Streamlit app replacing 2 Tableau dashboards used by 10 stakeholders. dbt models for data governance initiative.
- Digital Project Manager / Implementation Consultant, AFK Agency (Jun 2019 - Nov 2023): 10+ digital projects for MINI Australia and BMW. Python automation (8hr to 30min). NLP + clustering UX redesign ($120k project). End-to-end client delivery.
- Sales and Marketing Officer, Linx Institute (Dec 2017 - Mar 2019): Zoho CRM automation, reporting, data cleaning.

EDUCATION: Master of Data Science, Macquarie University (Feb 2026). Bachelor of Mathematics, University of Toyama Japan.

CERTIFICATIONS: dbt Essential, Snowflake Core Associate (in progress)

TECHNICAL SKILLS: RAG, LLM APIs (Claude, OpenAI), local LLM inference, prompt injection defence, evaluation frameworks, dbt, Snowflake, SQL, Python, FastAPI, Tableau, Streamlit, Git

LANGUAGES: English (fluent), Japanese (native)

TARGET ROLES: AI Engineer, Analytics Engineer, Solutions Engineer, Forward Deployed Engineer, Data Engineer. Sydney. $100-120k+. Permanent preferred.

VISA: Subclass 485 — full working rights. NOT Australian citizen or PR. Cannot apply to roles requiring citizenship or security clearance.
"""

_SCORING_PROMPT = """\
You are a career advisor evaluating a job posting for a specific candidate. Be calibrated and honest — not every job is a good fit.
Return ONLY valid JSON with no other text, markdown, or backticks.

CANDIDATE PROFILE:
{cv}

JOB TITLE: {title}
COMPANY: {company}
JOB DESCRIPTION:
{description}

Evaluate the fit and return this exact JSON:
{{
  "ai_match": "yes" | "maybe" | "no",
  "ai_score": <integer 0-100>,
  "ai_stage": "applying" | "saved" | "new" | "rejected",
  "ai_reason": "<one specific sentence about the primary reason for/against this match>",
  "ai_gaps": "<one sentence on the biggest concrete gap, e.g. missing years of experience, wrong stack, etc — or 'none' if strong fit>"
}}

SCORING BANDS:
- 75-100 → applying. Strong semantic fit. Candidate clearly meets most stated requirements. Should apply now.
- 60-74 → saved. Decent fit with some gaps. Worth monitoring.
- 45-59 → new. Unclear fit. Key requirements are missing or unclear.
- 0-44  → rejected. Poor fit, wrong domain, too senior, clearance required, or core skills absent.

HARD DISQUALIFIERS (score 0, stage "rejected"):
- Role explicitly requires Australian citizenship or security clearance
- Role requires 5+ years of hands-on engineering experience as a hard minimum
- Role is clearly non-technical (pure sales, pure marketing, pure ops)

CALIBRATION NOTES — read carefully before scoring:
- The candidate has real but early-career engineering depth. Do NOT penalise for having 4 years total experience if the role suits someone at that level.
- "Consulting background" counts as a genuine strength for customer-facing engineering roles (solutions engineer, implementation consultant, forward deployed engineer).
- LLM/RAG/AI project work is legitimate even if from self-directed projects — weight it seriously.
- Japanese fluency is a genuine bonus for companies with Japanese operations or clients — call it out in ai_reason if relevant.
- If the JD asks for "2-3 years experience" and the candidate has that level of hands-on engineering, that is a match, not a gap.
- Be specific in ai_reason and ai_gaps. "Good match" is not acceptable — name the actual skills or requirements you matched or missed.\
"""


def ai_score_job(title: str, company: str, description: str) -> dict:
    """
    Score a single job against Arian's CV using Claude Haiku.
    Returns dict: ai_match, ai_score, ai_stage, ai_reason, ai_gaps.
    Raises json.JSONDecodeError on bad model output, anthropic.APIError on API failure.
    """
    client = anthropic.Anthropic()

    prompt = _SCORING_PROMPT.format(
        cv=CV.strip(),
        title=title or "(unknown title)",
        company=company or "(unknown company)",
        description=(description or "")[:DESC_WINDOW],
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=350,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    result = json.loads(raw)

    # Coerce + validate types
    result["ai_score"] = max(0, min(100, int(result.get("ai_score") or 0)))

    match_val = str(result.get("ai_match") or "no").lower()
    result["ai_match"] = match_val if match_val in ("yes", "maybe", "no") else "no"

    valid_stages = {"applying", "saved", "new", "rejected"}
    stage_val = str(result.get("ai_stage") or "new").lower()
    result["ai_stage"] = stage_val if stage_val in valid_stages else "new"

    # Blank out uninformative gap strings
    gaps = str(result.get("ai_gaps") or "").strip()
    result["ai_gaps"] = None if gaps.lower() in ("none", "n/a", "", "no gaps") else gaps

    return result


def ai_score_all_jobs(limit: int | None = None, rescore: bool = False) -> int:
    """
    Score jobs in the DB using Claude API.

    - By default: only processes jobs where ai_score IS NULL and description ≥ MIN_DESC_CHARS.
    - With rescore=True: wipes existing ai_score first, then re-scores all jobs with descriptions.
    - Jobs with short/missing descriptions are skipped and counted separately — run the
      description backfiller (python run.py --no-scrape) first, then score.

    Returns the count of jobs successfully scored.
    """
    conn = sqlite3.connect(DB_PATH)

    # Schema migration: add ai_gaps if missing
    cols = [r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()]
    if "ai_gaps" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN ai_gaps TEXT")
        conn.commit()

    if rescore:
        print("  [ai_scorer] --rescore: clearing existing ai_score values…")
        conn.execute(
            "UPDATE jobs SET ai_score = NULL, ai_match = NULL, ai_stage = NULL, "
            "ai_reason = NULL, ai_gaps = NULL "
            "WHERE dismissed = 0 OR dismissed IS NULL"
        )
        conn.commit()

    # Jobs with a real description that haven't been scored yet
    eligible_query = """
        SELECT job_url, title, company, description
        FROM jobs
        WHERE ai_score IS NULL
          AND (dismissed = 0 OR dismissed IS NULL)
          AND description IS NOT NULL
          AND LENGTH(description) >= ?
        ORDER BY first_seen DESC
    """
    if limit:
        eligible_query += f" LIMIT {limit}"

    rows = conn.execute(eligible_query, (MIN_DESC_CHARS,)).fetchall()
    total = len(rows)

    # Count jobs being skipped due to short/missing description
    skipped_no_desc = conn.execute(
        """
        SELECT COUNT(*) FROM jobs
        WHERE ai_score IS NULL
          AND (dismissed = 0 OR dismissed IS NULL)
          AND (description IS NULL OR LENGTH(description) < ?)
        """,
        (MIN_DESC_CHARS,),
    ).fetchone()[0]

    if skipped_no_desc:
        print(
            f"  [ai_scorer] skipping {skipped_no_desc} jobs with no/short description "
            f"(<{MIN_DESC_CHARS} chars) — run description backfiller first"
        )

    if not total:
        print("  [ai_scorer] no scoreable jobs found — nothing to do")
        conn.close()
        return 0

    print(f"  [ai_scorer] scoring {total} jobs via Claude Haiku…")
    count = 0
    errors = 0
    auto_dismissed = 0

    for url, title, company, desc in rows:
        try:
            result = ai_score_job(
                title=title or "",
                company=company or "",
                description=desc or "",
            )
            job_score = result.get("ai_score") or 0

            # Auto-dismiss low scorers immediately — they never appear on the board.
            if AUTO_DISMISS_BELOW > 0 and job_score < AUTO_DISMISS_BELOW:
                conn.execute(
                    """
                    UPDATE jobs
                    SET ai_match  = ?,
                        ai_score  = ?,
                        ai_stage  = ?,
                        ai_reason = ?,
                        ai_gaps   = ?,
                        dismissed = 1,
                        dismissed_reason = 'low_score'
                    WHERE job_url = ?
                    """,
                    (
                        result.get("ai_match"),
                        job_score,
                        result.get("ai_stage"),
                        result.get("ai_reason"),
                        result.get("ai_gaps"),
                        url,
                    ),
                )
                auto_dismissed += 1
            else:
                conn.execute(
                    """
                    UPDATE jobs
                    SET ai_match  = ?,
                        ai_score  = ?,
                        ai_stage  = ?,
                        ai_reason = ?,
                        ai_gaps   = ?
                    WHERE job_url = ?
                    """,
                    (
                        result.get("ai_match"),
                        job_score,
                        result.get("ai_stage"),
                        result.get("ai_reason"),
                        result.get("ai_gaps"),
                        url,
                    ),
                )
            count += 1
            if count % 10 == 0:
                conn.commit()
                print(f"  [ai_scorer] {count}/{total} scored…")
        except json.JSONDecodeError as e:
            errors += 1
            print(f"  [ai_scorer] bad JSON for '{title}' @ {company}: {e}")
        except Exception as e:
            errors += 1
            print(f"  [ai_scorer] error scoring '{title}' @ {company}: {e}")

    # One-time cleanup: dismiss any previously-scored jobs that are below the
    # threshold but slipped through before this feature existed.
    if AUTO_DISMISS_BELOW > 0:
        result_cleanup = conn.execute(
            """
            UPDATE jobs
            SET dismissed = 1, dismissed_reason = 'low_score'
            WHERE ai_score IS NOT NULL
              AND ai_score < ?
              AND (dismissed = 0 OR dismissed IS NULL)
            """,
            (AUTO_DISMISS_BELOW,),
        )
        cleanup_count = result_cleanup.rowcount
        if cleanup_count:
            print(f"  [ai_scorer] cleanup: dismissed {cleanup_count} existing low-score jobs (<{AUTO_DISMISS_BELOW})")

    conn.commit()
    conn.close()

    summary = f"  [ai_scorer] done — {count}/{total} scored"
    if auto_dismissed:
        summary += f", {auto_dismissed} auto-dismissed (score <{AUTO_DISMISS_BELOW})"
    if errors:
        summary += f", {errors} errors"
    if skipped_no_desc:
        summary += f", {skipped_no_desc} awaiting description"
    print(summary)
    return count


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Score jobs in jobs.db using Claude API")
    p.add_argument(
        "--limit", type=int, default=None,
        help="Only score this many jobs — use for testing before a full run",
    )
    p.add_argument(
        "--rescore", action="store_true",
        help="Wipe existing ai_scores and re-score all jobs. Use when recalibrating the prompt.",
    )
    args = p.parse_args()
    n = ai_score_all_jobs(limit=args.limit, rescore=args.rescore)
    print(f"AI scored {n} jobs")
