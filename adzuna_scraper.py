"""
job-radar: Adzuna job scraper
Fetches Australian jobs with descriptions via the free Adzuna API,
maps them to the same schema used by scraper.py, and upserts into jobs.db.

API: https://developer.adzuna.com/
  Free tier: 250 hits/day · 1,000/week · 2,500/month
  With 11 searches/day this uses ~11 calls — well within limits.

Setup:
    1. Register at https://developer.adzuna.com/signup
    2. Add to .env:
         ADZUNA_APP_ID=your_app_id
         ADZUNA_APP_KEY=your_app_key
    3. Run:  python adzuna_scraper.py
       or:   python run.py  (runs automatically when ADZUNA keys are set)

Note: Adzuna returns only a 500-char description snippet. We call
      fetch_description() on each redirect URL to get the full text.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from scraper import (
    DB_PATH,
    fingerprint,
    init_db,
    is_too_senior,
    upsert_jobs,
    fetch_description,
    enrich_descriptions,
)

load_dotenv()

RESULTS_PER_QUERY = 20   # per search term; Adzuna free limit is 250 hits/day total
_API_BASE = "https://api.adzuna.com/v1/api/jobs/au/search/1"
_PROFILES_PATH = Path(__file__).parent / "role_profiles.json"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _load_queries() -> list[tuple[str, str]]:
    """Return list of (label, search_term) from role_profiles.json."""
    with open(_PROFILES_PATH) as f:
        config = json.load(f)
    queries = []
    for profile in config["profiles"]:
        for query in profile["searches"]:
            queries.append((profile["label"], query))
    return queries


def _map_item(item: dict, label: str) -> dict | None:
    """Map one Adzuna API result to our DB schema."""
    title = item.get("title") or ""
    if not title or is_too_senior(title):
        return None

    # redirect_url is the tracking link that forwards to the real job page
    url = item.get("redirect_url") or ""
    if not url:
        return None

    company  = item.get("company", {}).get("display_name") or ""
    location = item.get("location", {}).get("display_name") or "Sydney, Australia"

    # API returns a 500-char snippet — enrich_descriptions() will upgrade this
    description = item.get("description") or ""
    description = re.sub(r"\s+", " ", description).strip() or None

    # created is ISO datetime e.g. "2026-05-13T08:22:11Z"
    created_raw = item.get("created") or ""
    date_posted = created_raw[:10] if created_raw else datetime.now(timezone.utc).date().isoformat()

    salary_min = item.get("salary_min")
    salary_max = item.get("salary_max")
    # Adzuna salary fields are numeric — convert to float if present
    try:
        salary_min = float(salary_min) if salary_min else None
        salary_max = float(salary_max) if salary_max else None
    except (TypeError, ValueError):
        salary_min = salary_max = None

    fp = fingerprint(title, company, location)

    return {
        "job_url":      url,
        "site":         "adzuna",
        "title":        title,
        "company":      company,
        "location":     location,
        "description":  description,
        "date_posted":  date_posted,
        "min_amount":   salary_min,
        "max_amount":   salary_max,
        "currency":     "AUD",
        "search_label": label,
        "salary_raw":   None,
        "fingerprint":  fp,
        "first_seen":   datetime.now(timezone.utc).isoformat(),
    }


# ── Main scrape function ─────────────────────────────────────────────────────

def scrape_jobs_via_adzuna(
    app_id: str | None = None,
    app_key: str | None = None,
) -> pd.DataFrame:
    """
    Run all role-profile searches against Adzuna's AU jobs API.
    One API call per search term (11 total by default).
    Returns a DataFrame in the same format as scraper.run_searches().
    """
    app_id  = app_id  or os.getenv("ADZUNA_APP_ID")
    app_key = app_key or os.getenv("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        print("  [adzuna] ADZUNA_APP_ID / ADZUNA_APP_KEY not set — skipping")
        return pd.DataFrame()

    # ── Today-guard: skip if we already scraped Adzuna jobs today ───────────
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        conn = sqlite3.connect(DB_PATH)
        (already_today,) = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE site='adzuna' AND first_seen >= ?",
            (today,),
        ).fetchone()
        conn.close()
        if already_today > 0:
            print(
                f"  [adzuna] ✓ already scraped {already_today} Adzuna jobs today "
                f"({today}) — skipping to stay within free tier limits"
            )
            return pd.DataFrame()
    except Exception:
        pass  # DB not yet initialised — safe to continue
    # ────────────────────────────────────────────────────────────────────────

    queries = _load_queries()
    print(f"  [adzuna] running {len(queries)} searches via Adzuna API…")

    all_rows: list[dict] = []

    for label, search_term in queries:
        # Strip location suffix if present (e.g. "data analyst Sydney" → "data analyst")
        clean_term = re.sub(r"\s+sydney.*$", "", search_term, flags=re.IGNORECASE).strip()

        params = urllib.parse.urlencode({
            "app_id":           app_id,
            "app_key":          app_key,
            "results_per_page": RESULTS_PER_QUERY,
            "what":             clean_term,
            "where":            "Sydney",
            "max_days_old":     1,       # last 24 hours only
            "sort_by":          "date",
        })
        url = f"{_API_BASE}?{params}"

        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except Exception as exc:
            print(f"    [adzuna] ✗ '{clean_term}': {exc}")
            continue

        items = data.get("results", [])
        for item in items:
            row = _map_item(item, label)
            if row:
                all_rows.append(row)

        print(f"    [adzuna] '{clean_term}' → {len(items)} raw / {sum(1 for r in all_rows if r)} mapped so far")
        time.sleep(0.3)   # be polite — well within rate limits

    if not all_rows:
        print("  [adzuna] no jobs fetched")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(subset=["job_url"])
    print(f"  [adzuna] {len(df)} jobs after dedup — enriching descriptions…")

    # Upgrade 500-char API snippets to full descriptions from the real job pages.
    # Pass short_threshold=501 so anything 500 chars or under gets enriched.
    df = enrich_descriptions(df, delay=1.2, short_threshold=501)

    print(f"  [adzuna] ✓ done — {len(df)} Adzuna jobs ready")
    return df


# ── Standalone run ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    df = scrape_jobs_via_adzuna()
    if df.empty:
        print("No jobs fetched. Check ADZUNA_APP_ID and ADZUNA_APP_KEY in .env")
    else:
        stats = upsert_jobs(df)
        print(
            f"Done: {stats['new']} new | {stats['skipped_url']} URL-dupe | "
            f"{stats['skipped_fingerprint']} cross-platform-dupe"
        )
