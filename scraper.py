"""
job-radar: scraper module
Pulls jobs from Seek, LinkedIn, and Indeed using JobSpy, then dedupes against a SQLite cache.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from jobspy import scrape_jobs

DB_PATH = Path(__file__).parent / "jobs.db"


def _norm(s: str | None) -> str:
    """Normalise a string for fingerprinting: lowercase, collapse whitespace, strip."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def fingerprint(title: str | None, company: str | None, location: str | None) -> str:
    """
    Content hash to catch the same job posted across multiple sites.
    Uses title + company + location only — salary and description vary even for
    identical jobs, so we leave them out.
    """
    key = f"{_norm(title)}|{_norm(company)}|{_norm(location)}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


@dataclass
class SearchConfig:
    """One search query against the job sites."""
    label: str
    search_term: str
    location: str = "Sydney, Australia"
    # Supported sites by python-jobspy: linkedin, indeed, google, glassdoor, zip_recruiter, bayt, naukri, bdjobs.
    # LinkedIn via jobspy returns no descriptions — use Apify for LinkedIn instead (apify_scraper.py).
    # Glassdoor excluded: location parsing broken for Sydney (returns 400 errors on every request).
    # Seek is handled separately via scrape_seek().
    sites: tuple[str, ...] = ("indeed", "google")
    results_wanted: int = 50
    hours_old: int = 24  # last 24 hours — run daily for fresh ads only


# Edit these to match your target roles.
# The labels are just for your reference. The search_term is what gets queried.
def load_searches_from_profiles(path: Path = Path(__file__).parent / "role_profiles.json") -> list[SearchConfig]:
    """Load search queries from role_profiles.json and return as SearchConfig list."""
    with open(path) as f:
        config = json.load(f)
    searches = []
    for profile in config["profiles"]:
        for query in profile["searches"]:
            searches.append(SearchConfig(
                label=profile["label"],
                search_term=query,
            ))
    return searches

SEARCHES: list[SearchConfig] = load_searches_from_profiles()


# ---------------------------------------------------------------------------
# Seniority pre-filter
# ---------------------------------------------------------------------------
# These keywords in the job TITLE are a hard block — the job is discarded
# before it ever enters the database or gets scored.
# Note: "manager" is intentionally NOT here because many target roles
# (e.g. Customer Success Manager) contain it.
SENIOR_TITLE_BLOCKLIST: list[str] = [
    "senior",
    "lead ",
    " lead",
    "principal",
    "head of",
    "director",
    " vp ",
    "vice president",
]


def is_too_senior(title: str | None) -> bool:
    """Return True if the job title signals a level above associate/mid."""
    if not title:
        return False
    t = title.lower()
    return any(kw in t for kw in SENIOR_TITLE_BLOCKLIST)


def filter_seniority(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows whose title is clearly too senior. Logs how many are removed."""
    if df.empty:
        return df
    mask = df["title"].apply(is_too_senior)
    dropped = mask.sum()
    if dropped:
        print(f"  [seniority filter] removed {dropped} over-senior jobs before storing")
    return df[~mask].reset_index(drop=True)


def init_db() -> None:
    """
    Create the jobs table if it doesn't exist. Safe to call repeatedly.
    Also runs a lightweight migration: adds the `fingerprint` column to existing
    DBs, backfills it, and removes any existing cross-platform duplicates
    (keeping the earliest sighting per fingerprint).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_url TEXT PRIMARY KEY,
            site TEXT,
            title TEXT,
            company TEXT,
            location TEXT,
            description TEXT,
            date_posted TEXT,
            min_amount REAL,
            max_amount REAL,
            currency TEXT,
            search_label TEXT,
            score INTEGER,
            score_reasons TEXT,
            first_seen TEXT,
            applied INTEGER DEFAULT 0,
            hidden INTEGER DEFAULT 0,
            fingerprint TEXT
        )
        """
    )

    # Migrations for columns added after the initial schema.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()]
    if "fingerprint" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN fingerprint TEXT")
    if "description" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN description TEXT")

    new_cols = {
        "salary_min": "INTEGER",
        "salary_max": "INTEGER",
        "salary_raw": "TEXT",
        "primary_role": "TEXT",
        "also_fits": "TEXT",
        "role_scores": "TEXT",
        "match_reasons": "TEXT",
        "user_reaction": "TEXT",
        "user_reaction_reason": "TEXT",
        "reaction_timestamp": "TEXT",
        "digest_sent_at": "TEXT",
        "dismissed": "INTEGER DEFAULT 0",
        "dismissed_reason": "TEXT",
        "status": "TEXT DEFAULT 'new'",
        "notes": "TEXT",
        "cover_letter": "TEXT",
        "company_research": "TEXT",
        "cover_letter_generated_at": "TEXT",
        "resume_match_pct": "INTEGER",
        "resume_matched_skills": "TEXT",
        "resume_missing_skills": "TEXT",
        "ai_match": "TEXT",
        "ai_score": "INTEGER",
        "ai_reason": "TEXT",
    }
    for col, col_type in new_cols.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}")

    # Backfill any rows missing a fingerprint.
    rows = conn.execute(
        "SELECT job_url, title, company, location FROM jobs WHERE fingerprint IS NULL OR fingerprint = ''"
    ).fetchall()
    for url, title, company, location in rows:
        conn.execute(
            "UPDATE jobs SET fingerprint = ? WHERE job_url = ?",
            (fingerprint(title, company, location), url),
        )

    # One-time cleanup: collapse existing duplicates (same fingerprint, different URL),
    # keeping the row with the earliest first_seen.
    conn.execute(
        """
        DELETE FROM jobs
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM jobs
            GROUP BY fingerprint
        )
        """
    )

    # Non-unique index — speeds up the lookup in upsert_jobs without rejecting writes.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(fingerprint)")

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Description fetching
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-AU,en;q=0.9",
}


def _strip_html(html: str) -> str:
    """Strip HTML tags and collapse whitespace to plain text."""
    text = BeautifulSoup(html, "html.parser").get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def parse_salary(text: str | None) -> dict:
    """
    Extract salary information from plain text job descriptions.
    Returns dict with keys: salary_min (int|None), salary_max (int|None), salary_raw (str|None).

    Handles common AU formats:
    - $120k–$150k / $120K - $150K
    - $120,000 - $150,000
    - $140,000 + super / $140k+ super
    - 120k AUD / AUD 140,000
    - "competitive salary" / "market rate" → None (no data)
    """
    if not text:
        return {"salary_min": None, "salary_max": None, "salary_raw": None}

    t = text.lower()

    # Pattern 1: range with k notation — $120k - $150k or $120K–$150K
    m = re.search(
        r"\$\s*([\d,]+\.?\d*)\s*k\s*[-–—to]+\s*\$?\s*([\d,]+\.?\d*)\s*k",
        t, re.IGNORECASE
    )
    if m:
        lo = int(float(m.group(1).replace(",", "")) * 1000)
        hi = int(float(m.group(2).replace(",", "")) * 1000)
        return {"salary_min": lo, "salary_max": hi, "salary_raw": m.group(0)}

    # Pattern 1b: bare k range — 120k-150k or 120K – 150K (no $ sign)
    m = re.search(
        r"\b([\d,]+\.?\d*)\s*k\s*[-–—to]+\s*([\d,]+\.?\d*)\s*k\b",
        t, re.IGNORECASE
    )
    if m:
        lo = int(float(m.group(1).replace(",", "")) * 1000)
        hi = int(float(m.group(2).replace(",", "")) * 1000)
        if 50000 <= lo <= 500000:  # sanity: real salary range
            return {"salary_min": lo, "salary_max": hi, "salary_raw": m.group(0)}

    # Pattern 2: range with full numbers — $120,000 - $150,000
    m = re.search(
        r"\$\s*([\d,]{6,})\s*[-–—to]+\s*\$?\s*([\d,]{6,})",
        t
    )
    if m:
        lo = int(m.group(1).replace(",", ""))
        hi = int(m.group(2).replace(",", ""))
        return {"salary_min": lo, "salary_max": hi, "salary_raw": m.group(0)}

    # Pattern 2b: bare full-number range with AUD marker — 120,000 – 150,000 AUD/pa
    m = re.search(
        r"\b([\d,]{6,})\s*[-–—]\s*([\d,]{6,})\s*(?:aud|per annum|p\.?a\.?|per year)",
        t, re.IGNORECASE
    )
    if m:
        lo = int(m.group(1).replace(",", ""))
        hi = int(m.group(2).replace(",", ""))
        if 50000 <= lo <= 500000:
            return {"salary_min": lo, "salary_max": hi, "salary_raw": m.group(0)}

    # Pattern 3: single value with k — $140k+ or $140k
    m = re.search(r"\$\s*([\d,]+\.?\d*)\s*k\b", t, re.IGNORECASE)
    if m:
        val = int(float(m.group(1).replace(",", "")) * 1000)
        return {"salary_min": val, "salary_max": None, "salary_raw": m.group(0)}

    # Pattern 4: single full number — $140,000 or AUD 140000
    m = re.search(r"(?:aud\s*)?\$\s*([\d,]{6,})", t)
    if m:
        val = int(m.group(1).replace(",", ""))
        return {"salary_min": val, "salary_max": None, "salary_raw": m.group(0)}

    # Pattern 5: AUD prefix — AUD 140,000 or AUD $140k
    m = re.search(r"aud\s+\$?\s*([\d,]+\.?\d*)\s*k?", t, re.IGNORECASE)
    if m:
        raw = m.group(1).replace(",", "")
        val = int(float(raw) * 1000) if "k" in m.group(0).lower() else int(raw)
        if val > 10000:  # sanity check — must be a real salary not a small number
            return {"salary_min": val, "salary_max": None, "salary_raw": m.group(0)}

    return {"salary_min": None, "salary_max": None, "salary_raw": None}


def fetch_description(url: str, site: str) -> str | None:
    """
    Fetch the full plain-text job description from the listing page.
    Returns None on any network or parse failure.
    """
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        site_lower = (site or "").lower()

        if site_lower == "linkedin":
            el = soup.select_one("div.description__text") or soup.select_one("div#job-details")
        elif site_lower == "indeed":
            el = soup.select_one("div#jobDescriptionText")
        elif site_lower == "glassdoor":
            el = soup.select_one("div.jobDescriptionContent")
        elif site_lower == "google":
            # Prefer structured data; fall back to a visible description element.
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    if isinstance(data, dict) and data.get("@type") == "JobPosting":
                        desc = data.get("description", "")
                        if desc:
                            return _strip_html(desc)
                except (json.JSONDecodeError, TypeError):
                    pass
            el = soup.select_one("div[itemprop='description']") or soup.select_one(
                "div[class*='description']"
            )
        elif site_lower == "seek":
            # Seek embeds full description in JSON-LD or __NEXT_DATA__
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    if isinstance(data, dict) and data.get("description"):
                        return _strip_html(data["description"])
                except (json.JSONDecodeError, TypeError):
                    pass
            # Fallback: __NEXT_DATA__ blob
            next_data = soup.find("script", id="__NEXT_DATA__")
            if next_data:
                try:
                    nd = json.loads(next_data.string or "")
                    desc = (nd.get("props", {}).get("pageProps", {})
                              .get("jobDetails", {}).get("content", ""))
                    if desc:
                        return _strip_html(desc)
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
        elif site_lower == "adzuna":
            # Adzuna redirect URLs forward to the real job page on the original
            # job board (allow_redirects=True handles the chain). Try JSON-LD
            # first (works for most modern job boards), then fall through to
            # a generic description element.
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    if isinstance(data, dict) and data.get("@type") == "JobPosting":
                        desc = data.get("description", "")
                        if desc:
                            return _strip_html(desc)
                except (json.JSONDecodeError, TypeError):
                    pass
            el = (
                soup.select_one("div[itemprop='description']")
                or soup.select_one("div#job-details")
                or soup.select_one("div.jobDescriptionText")
                or soup.select_one("div[class*='description']")
            )
        else:
            el = None

        return _strip_html(str(el)) if el else None
    except Exception:
        return None


def enrich_descriptions(df: pd.DataFrame, delay: float = 1.0, short_threshold: int | None = None) -> pd.DataFrame:
    """
    For rows whose description is missing or shorter than the threshold, fetch the
    full description from the job listing page. Operates in-place; returns df.

    short_threshold: if set, use this value for all rows regardless of site.
                     Useful for Adzuna which returns exactly 500-char snippets.
    """
    if df.empty:
        return df
    fetched = 0
    for idx, row in df.iterrows():
        existing = str(row.get("description") or "").strip()
        site = str(row.get("site") or "").lower()
        if short_threshold is not None:
            threshold = short_threshold
        else:
            # Seek teasers can be 100-300 chars — treat anything under 500 as needing enrichment
            threshold = 500 if site == "seek" else 100
        if len(existing) >= threshold:
            continue
        url = row.get("job_url")
        if not url:
            continue
        desc = fetch_description(url, str(row.get("site") or ""))
        if desc:
            df.at[idx, "description"] = desc
            fetched += 1
            time.sleep(delay)
    if fetched:
        print(f"  [enrich] fetched full descriptions for {fetched} jobs")
    return df


def scrape_seek(search_term: str, label: str, location: str = "Sydney NSW", results_wanted: int = 50, hours_old: int = 24) -> pd.DataFrame:
    """
    Scrape Seek.com.au via their unofficial search API.
    Returns a DataFrame with columns matching upsert_jobs() expectations.
    Falls back to empty DataFrame on any network/parse failure.

    hours_old: discard any listing whose listingDate is older than this many hours.
    The Seek API also receives a dateRange hint to pre-filter server-side.
    """
    import urllib.parse
    from datetime import timedelta

    base_url = "https://www.seek.com.au/api/chalice-search/v4/search"
    rows: list[dict] = []
    page = 1
    per_page = min(results_wanted, 100)
    headers = {
        **_HEADERS,
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://www.seek.com.au/{urllib.parse.quote(search_term.replace(' ', '-'))}-jobs/",
    }

    # Map hours_old to Seek's dateRange values (1, 3, 7, 14, 30 days).
    if hours_old <= 24:
        seek_date_range = "1"
    elif hours_old <= 72:
        seek_date_range = "3"
    elif hours_old <= 168:
        seek_date_range = "7"
    else:
        seek_date_range = "14"

    # Cutoff datetime for client-side age filter (belt-and-suspenders).
    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours_old)

    while len(rows) < results_wanted:
        params = {
            "siteKey": "AU-Main",
            "sourcesystem": "houston",
            "keywords": search_term,
            "where": location,
            "page": str(page),
            "pageSize": str(per_page),
            "locale": "en-AU",
            "mode": "Split",
            "dateRange": seek_date_range,
        }
        try:
            resp = requests.get(base_url, params=params, headers=headers, timeout=15)
            if resp.status_code != 200:
                break
            data = resp.json()
        except Exception:
            break

        jobs_data = data.get("data", [])
        if not jobs_data:
            break

        for job in jobs_data:
            job_id = job.get("id", "")
            if not job_id:
                continue
            job_url = f"https://www.seek.com.au/job/{job_id}"
            company_info = job.get("advertiser") or {}
            company = company_info.get("description", "") if isinstance(company_info, dict) else ""
            loc = (job.get("location") or job.get("area") or location or "")
            salary_text = job.get("salary", "") or ""
            # Teaser is only a short preview — leave blank so enrich_descriptions()
            # fetches the full description from the Seek job page.
            description = ""
            listed = job.get("listingDate", "") or ""
            date_posted = listed[:10] if listed else ""

            # Client-side age filter: skip jobs older than hours_old.
            if listed:
                try:
                    listed_dt = datetime.fromisoformat(listed.replace("Z", "+00:00"))
                    if listed_dt < cutoff_dt:
                        continue
                except (ValueError, TypeError):
                    pass  # unparseable date — let it through, age gate in upsert handles it

            # Parse salary from the structured salary field (e.g. "$120k - $150k")
            sal = parse_salary(salary_text)

            rows.append({
                "job_url": job_url,
                "site": "seek",
                "title": job.get("title", ""),
                "company": company,
                "location": loc,
                "description": description,
                "date_posted": date_posted,
                "min_amount": sal["salary_min"],
                "max_amount": sal["salary_max"],
                "currency": "AUD",
                "search_label": label,
                "salary_raw": salary_text,
            })

        if len(jobs_data) < per_page:
            break  # last page
        page += 1

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows[:results_wanted])


def run_searches(searches: list[SearchConfig] = SEARCHES) -> pd.DataFrame:
    """Run every configured search (jobspy + Seek) and return a combined DataFrame."""
    all_frames: list[pd.DataFrame] = []
    for cfg in searches:
        # --- Seek (custom scraper) ---
        print(f"  [seek] {cfg.label} ({cfg.search_term})")
        try:
            seek_df = scrape_seek(cfg.search_term, cfg.label, location="Sydney NSW", results_wanted=cfg.results_wanted, hours_old=cfg.hours_old)
            if seek_df is not None and len(seek_df) > 0:
                all_frames.append(seek_df)
                print(f"    -> {len(seek_df)} seek jobs")
        except Exception as e:
            print(f"    !! seek failed: {e}")

        # --- jobspy (LinkedIn / Indeed / Google) ---
        print(f"  [jobspy] {cfg.label} ({cfg.search_term})")
        try:
            df = scrape_jobs(
                site_name=list(cfg.sites),
                search_term=cfg.search_term,
                location=cfg.location,
                results_wanted=cfg.results_wanted,
                hours_old=cfg.hours_old,
                country_indeed="Australia",
                country_glassdoor="Australia",
                google_search_term=f"{cfg.search_term} jobs near Sydney Australia",
            )
            if df is not None and len(df) > 0:
                df["search_label"] = cfg.label
                all_frames.append(df)
                print(f"    -> {len(df)} jobspy jobs")
        except Exception as e:
            print(f"    !! jobspy failed: {e}")

    if not all_frames:
        return pd.DataFrame()
    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"], keep="first")
    combined = filter_seniority(combined)
    # Enrich short/missing descriptions (skips jobs already with 100+ char descriptions)
    print(f"\n  enriching descriptions for {len(combined)} jobs…")
    combined = enrich_descriptions(combined)
    return combined


def upsert_jobs(df: pd.DataFrame, max_age_days: int = 7) -> dict:
    """
    Insert new jobs. Skip rows whose URL we've seen, AND rows whose
    title+company+location fingerprint matches a job we already have
    (i.e. the same job re-posted on another site).

    max_age_days: hard backstop — any job whose date_posted is parseable and
    older than this is rejected regardless of dedup state. Prevents stale listings
    that slip past the scraper's hours_old filter from ever reaching the DB.

    Returns a stats dict: {"new", "skipped_url", "skipped_fingerprint", "skipped_stale"}.
    """
    from datetime import timedelta

    stats = {"new": 0, "skipped_url": 0, "skipped_fingerprint": 0, "skipped_stale": 0}
    if df.empty:
        return stats

    stale_cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).date()

    conn = sqlite3.connect(DB_PATH)
    now = datetime.now(timezone.utc).isoformat()

    # Track fingerprints inserted within THIS run so we don't accept the same
    # cross-posted job twice from two different searches.
    seen_fps_this_run: set[str] = set()

    def _maybe_update_description(url_col: str, url_val: str, new_desc: str | None) -> None:
        """Backfill description when the stored value is NULL or empty."""
        if not new_desc:
            return
        conn.execute(
            f"UPDATE jobs SET description = ? WHERE {url_col} = ? AND (description IS NULL OR description = '')",
            (new_desc, url_val),
        )

    for _, row in df.iterrows():
        url = row.get("job_url")
        if not url:
            continue

        new_desc = row.get("description") or None

        # 0) Hard age gate: reject jobs whose date_posted is clearly stale.
        raw_date = row.get("date_posted")
        if raw_date:
            try:
                posted_date = datetime.fromisoformat(str(raw_date)[:10]).date()
                if posted_date < stale_cutoff:
                    stats["skipped_stale"] += 1
                    continue
            except (ValueError, TypeError):
                pass  # unparseable — let through, better to show than silently drop

        # Parse salary from description text (structured salary fields are empty for AU listings)
        desc_text = row.get("description") or ""
        salary_parsed = parse_salary(desc_text)
        # Also check the structured fields from JobSpy as a fallback
        sal_min = row.get("min_amount") or salary_parsed["salary_min"]
        sal_max = row.get("max_amount") or salary_parsed["salary_max"]
        sal_raw = salary_parsed["salary_raw"]

        # 1) Same URL already in DB — backfill description if needed then skip.
        if conn.execute("SELECT 1 FROM jobs WHERE job_url = ?", (url,)).fetchone():
            _maybe_update_description("job_url", url, new_desc)
            stats["skipped_url"] += 1
            continue

        # 2) Same job content already in DB or earlier in this run?
        fp = fingerprint(row.get("title"), row.get("company"), row.get("location"))
        existing_fp_row = conn.execute(
            "SELECT job_url FROM jobs WHERE fingerprint = ? LIMIT 1", (fp,)
        ).fetchone()
        if fp in seen_fps_this_run or existing_fp_row:
            if existing_fp_row:
                _maybe_update_description("job_url", existing_fp_row[0], new_desc)
            stats["skipped_fingerprint"] += 1
            continue

        conn.execute(
            """
            INSERT INTO jobs (
                job_url, site, title, company, location, description,
                date_posted, min_amount, max_amount, currency,
                salary_min, salary_max, salary_raw,
                search_label, first_seen, fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                url,
                row.get("site"),
                row.get("title"),
                row.get("company"),
                row.get("location"),
                row.get("description"),
                str(row.get("date_posted")) if row.get("date_posted") else None,
                row.get("min_amount"),
                row.get("max_amount"),
                row.get("currency"),
                sal_min,
                sal_max,
                sal_raw,
                row.get("search_label"),
                now,
                fp,
            ),
        )
        seen_fps_this_run.add(fp)
        stats["new"] += 1

    conn.commit()
    conn.close()
    return stats


def backfill_salary_from_descriptions() -> int:
    """
    For existing jobs in the DB that have descriptions but no salary_min,
    run the salary parser and update. Returns count of rows updated.
    """
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT job_url, description FROM jobs WHERE salary_min IS NULL AND description IS NOT NULL AND length(description) > 100"
    ).fetchall()
    updated = 0
    for url, desc in rows:
        result = parse_salary(desc)
        if result["salary_min"] or result["salary_max"]:
            conn.execute(
                "UPDATE jobs SET salary_min = ?, salary_max = ?, salary_raw = ? WHERE job_url = ?",
                (result["salary_min"], result["salary_max"], result["salary_raw"], url),
            )
            updated += 1
    conn.commit()
    conn.close()
    return updated


def purge_senior_jobs_from_db() -> int:
    """
    Dismiss jobs already in the DB whose title passes is_too_senior().
    These pre-date the seniority filter and were never cleaned up.
    Returns count of jobs dismissed.
    """
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT job_url, title FROM jobs WHERE (dismissed = 0 OR dismissed IS NULL)"
    ).fetchall()
    to_dismiss = [(url,) for url, title in rows if is_too_senior(title)]
    if to_dismiss:
        conn.executemany(
            "UPDATE jobs SET dismissed = 1, dismissed_reason = 'seniority_filter' WHERE job_url = ?",
            to_dismiss,
        )
        conn.commit()
    conn.close()
    return len(to_dismiss)


def backfill_descriptions_from_db(delay: float = 1.5) -> int:
    """
    For jobs already in the DB that have no (or very short) description,
    try to fetch descriptions — skipping LinkedIn which blocks web access.
    Returns count of jobs updated.

    Thresholds by source:
      - seek: < 500 chars  (teasers from the old scraper are 100-300 chars)
      - others: < 100 chars
    """
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT job_url, site FROM jobs
        WHERE (dismissed = 0 OR dismissed IS NULL)
          AND LOWER(site) != 'linkedin'
          AND LOWER(site) != 'linkedin_apify'
          AND (
              description IS NULL
              OR (LOWER(site) = 'seek'   AND length(description) < 500)
              OR (LOWER(site) != 'seek'  AND length(description) < 100)
          )
        """
    ).fetchall()
    conn.close()

    if not rows:
        return 0

    updated = 0
    print(f"  [desc backfill] attempting {len(rows)} non-LinkedIn jobs…")
    conn = sqlite3.connect(DB_PATH)
    for url, site in rows:
        desc = fetch_description(url, site or "")
        if desc and len(desc) >= 100:
            conn.execute(
                "UPDATE jobs SET description = ? WHERE job_url = ?",
                (desc, url),
            )
            updated += 1
            time.sleep(delay)
    conn.commit()
    conn.close()
    return updated


if __name__ == "__main__":
    print("job-radar: starting scrape")
    init_db()
    df = run_searches()
    print(f"\ntotal scraped (deduped within run): {len(df)}")
    stats = upsert_jobs(df)
    print(
        f"new: {stats['new']} | skipped (URL seen): {stats['skipped_url']} | "
        f"skipped (cross-platform dupe): {stats['skipped_fingerprint']}"
    )
