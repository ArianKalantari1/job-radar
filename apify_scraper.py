"""
job-radar: Apify LinkedIn scraper
Fetches LinkedIn jobs (with full descriptions) via the Apify platform,
maps them to the same schema used by scraper.py, and upserts into jobs.db.

Actor: curious_coder/linkedin-jobs-scraper
  - Input:  urls (LinkedIn jobs search URLs), maxResults
  - Output: title, companyName, location, descriptionText, postedAt, link, salary

The actor takes LinkedIn search URLs directly, so we build one URL per search
query using the f_TPR=r86400 filter (last 24 hours) to match our daily schedule.

Setup:
    1. Go to https://console.apify.com/settings/integrations
    2. Copy your API token
    3. Add to .env:  APIFY_TOKEN=apify_xxxx...
    4. Run:  python apify_scraper.py
       or:   python run.py  (runs automatically if APIFY_TOKEN is set)
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

try:
    from apify_client import ApifyClient
except ImportError:
    ApifyClient = None  # type: ignore

from scraper import DB_PATH, fingerprint, init_db, is_too_senior, upsert_jobs

load_dotenv(override=True)

ACTOR_ID = "curious_coder/linkedin-jobs-scraper"
RESULTS_PER_QUERY = 20   # per search URL — 20 is plenty for 24h Sydney searches

_PROFILES_PATH = Path(__file__).parent / "role_profiles.json"

# f_TPR=r86400 = posted in last 24 hours (matches our daily schedule)
_LI_SEARCH_BASE = "https://www.linkedin.com/jobs/search/?{params}"
_TIME_FILTER = "r86400"   # 86400 seconds = 24 hours


def _build_linkedin_url(query: str, location: str = "Sydney, Australia") -> str:
    """Build a LinkedIn job search URL with 24h time filter."""
    params = urllib.parse.urlencode({
        "keywords": query,
        "location": location,
        "f_TPR": _TIME_FILTER,
        "position": 1,
        "pageNum": 0,
    })
    return _LI_SEARCH_BASE.format(params=params)


def _load_queries() -> list[tuple[str, str]]:
    """Return list of (label, search_term) from role_profiles.json."""
    with open(_PROFILES_PATH) as f:
        config = json.load(f)
    queries = []
    for profile in config["profiles"]:
        for query in profile["searches"]:
            queries.append((profile["label"], query))
    return queries


def _parse_salary(raw: str | None) -> tuple[float | None, float | None]:
    """Parse '$100k - $130k' or '$120,000' into (min, max) AUD."""
    if not raw:
        return None, None
    nums = re.findall(r"[\d,]+", raw.replace("k", "000").replace("K", "000"))
    cleaned = []
    for n in nums:
        try:
            cleaned.append(float(n.replace(",", "")))
        except ValueError:
            pass
    if not cleaned:
        return None, None
    if len(cleaned) == 1:
        return cleaned[0], cleaned[0]
    return min(cleaned), max(cleaned)


def _map_item(item: dict, label: str) -> dict | None:
    """Map one curious_coder/linkedin-jobs-scraper result to our DB schema."""
    title = item.get("title") or ""
    if not title or is_too_senior(title):
        return None

    url = item.get("link") or item.get("applyUrl") or ""
    if not url:
        return None
    # Normalise to canonical job view URL (strip tracking params)
    job_id_match = re.search(r"-(\d{10,})(?:\?|$)", url)
    if job_id_match:
        url = f"https://www.linkedin.com/jobs/view/{job_id_match.group(1)}"

    company = item.get("companyName") or ""
    location = item.get("location") or "Sydney, Australia"

    # descriptionText is clean plain text; descriptionHtml available if needed
    description = item.get("descriptionText") or ""
    description = re.sub(r"\s+", " ", description).strip() or None

    # postedAt is ISO datetime string e.g. "2026-05-04T06:36:24.000Z"
    posted_raw = item.get("postedAt") or ""
    date_posted = posted_raw[:10] if posted_raw else datetime.now(timezone.utc).date().isoformat()

    salary_raw = item.get("salary") or None
    salary_min, salary_max = _parse_salary(str(salary_raw) if salary_raw else None)

    fp = fingerprint(title, company, location)

    return {
        "job_url": url,
        "site": "linkedin_apify",
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        "date_posted": date_posted,
        "min_amount": salary_min,
        "max_amount": salary_max,
        "currency": "AUD",
        "search_label": label,
        "salary_raw": str(salary_raw) if salary_raw else None,
        "fingerprint": fp,
        "first_seen": datetime.now(timezone.utc).isoformat(),
    }


def scrape_linkedin_via_apify(token: str | None = None) -> pd.DataFrame:
    """
    Run all role-profile searches against LinkedIn via Apify.
    Batches all search URLs into a single actor run to conserve API quota.
    Returns a DataFrame in the same format as scraper.run_searches().
    """
    if ApifyClient is None:
        print("  [apify] apify-client not installed — run: pip install apify-client")
        return pd.DataFrame()
    token = token or os.getenv("APIFY_TOKEN")
    if not token:
        print("  [apify] APIFY_TOKEN not set — skipping LinkedIn via Apify")
        return pd.DataFrame()

    # ── Today-guard: skip if we already scraped LinkedIn jobs today ──────────
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        conn = sqlite3.connect(DB_PATH)
        (already_today,) = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE site='linkedin_apify' AND first_seen >= ?",
            (today,),
        ).fetchone()
        conn.close()
        if already_today > 0:
            print(
                f"  [apify] ✓ already scraped {already_today} LinkedIn jobs today "
                f"({today}) — skipping to save Apify credits"
            )
            return pd.DataFrame()
    except Exception:
        pass  # DB not yet initialised — safe to continue
    # ─────────────────────────────────────────────────────────────────────────

    client = ApifyClient(token)
    queries = _load_queries()

    # Build one LinkedIn search URL per query and batch them all in one run
    url_to_label: dict[str, str] = {}
    for label, query in queries:
        # Strip location from query if it's appended (e.g. "data analyst sql python Sydney")
        clean_query = re.sub(r"\s+sydney.*$", "", query, flags=re.IGNORECASE).strip()
        url = _build_linkedin_url(clean_query)
        url_to_label[url] = label

    search_urls = list(url_to_label.keys())
    print(f"  [apify] running {len(search_urls)} LinkedIn searches in one batch via Apify…")

    try:
        run = client.actor(ACTOR_ID).call(
            run_input={
                "urls": search_urls,
                "maxResults": RESULTS_PER_QUERY,
            }
        )
        if not run:
            print("  [apify] ✗ actor run failed")
            return pd.DataFrame()

        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        print(f"  [apify] ✓ raw items from LinkedIn: {len(items)}")

    except Exception as exc:
        print(f"  [apify] ✗ error: {exc}")
        return pd.DataFrame()

    all_rows: list[dict] = []
    no_desc = 0
    for item in items:
        # Assign label based on search URL if available, else use first label
        row = _map_item(item, "LinkedIn")
        if row:
            if not row["description"]:
                no_desc += 1
            all_rows.append(row)

    if no_desc:
        print(f"  [apify] ⚠ {no_desc}/{len(all_rows)} jobs had no description (will be filtered from CSV export)")

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(subset=["job_url"])
    print(f"  [apify] total LinkedIn jobs after dedup: {len(df)}")
    return df


if __name__ == "__main__":
    """Run standalone: python apify_scraper.py"""
    init_db()
    df = scrape_linkedin_via_apify()
    if df.empty:
        print("No jobs fetched. Check APIFY_TOKEN in .env")
    else:
        stats = upsert_jobs(df)
        print(
            f"Done: {stats['new']} new | {stats['skipped_url']} URL-dupe | "
            f"{stats['skipped_fingerprint']} cross-platform-dupe"
        )
