# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Personal job-hunt automation for Ari Kalantari (Sydney, AU). Scrapes job listings at midnight, deduplicates across sources, scores them with rules-based heuristics, and exports a CSV. Each morning Ari feeds that CSV to a Claude Code session (using the `job-radar-daily-review` skill) which ranks the top 10 matches against his two CVs.

This is a single-user tool — not a product, not multi-tenant.

## Commands

```bash
# Daily pipeline: scrape → score → export CSV
python run.py --fast

# Full pipeline flags
python run.py                 # full pipeline (scrape + score + export CSV)
python run.py --fast          # same as above (kept for backward compat with run_daily.sh)
python run.py --no-scrape     # skip scraping, just rescore + re-export

# Manual CSV export (the pipeline already does this automatically)
python export_for_gpt.py                  # last 24h, score >= 50
python export_for_gpt.py --days 2         # missed yesterday
python export_for_gpt.py --min-score 0    # everything

# Smoke test (run before first full run to verify connectivity)
python smoke_test.py

# Test Adzuna API credentials
python test_adzuna.py
python test_adzuna_fetch.py
```

The scheduled runner is `run_daily.sh`, called by cron/launchd at midnight. It runs `python run.py --fast` then exports `jobs_YYYY-MM-DD.csv`.

## Architecture

The pipeline flows in one direction:

```
Scrapers → DataFrame → upsert_jobs() → SQLite → scorer → export CSV
```

### Scraping layer (3 files, 3 sources)

- **`scraper.py`** — The largest and most critical file. Owns the DB schema (`init_db`), dedup logic (`upsert_jobs`), description fetching (`fetch_description`), and two scrapers: Seek (custom) and JobSpy (Indeed + Google). Also owns all backfill functions.
- **`apify_scraper.py`** — LinkedIn via Apify API. Paid (~$0.10/run). Only runs when `APIFY_TOKEN` is set.
- **`adzuna_scraper.py`** — Adzuna API. Free tier (2,500 calls/month). Only runs when `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` are set.

All three scrapers return a pandas DataFrame with a standard schema. `run.py` passes each to `upsert_jobs()`.

### Deduplication (in `upsert_jobs()`)

Two-layer dedup prevents the same job from appearing twice:
1. **URL match** — exact `job_url` already in DB → skip
2. **Fingerprint match** — MD5 of `(title + company + location)` → catches same job posted on LinkedIn AND Indeed AND Seek

Jobs older than 7 days are rejected at upsert time.

### Scoring (`scorer.py`)

Rules-based, zero cost, instant. Scores each job 0–100 against all 5 role profiles in `role_profiles.json`. Assigns `primary_role`, `also_fits`, and `match_reasons`. Also computes resume skill-gap analysis if `resume.txt` exists.

Scoring formula: baseline 50 ± skill matches (+6/+2) ± seniority fit ± salary vs floor ($140k AUD) ± location (Sydney +10, AU remote +5, elsewhere -10).

### Export (`export_for_gpt.py`)

Exports filtered jobs to CSV. Called automatically at the end of `run.py`. The output CSV is what Ari feeds into his morning Claude Code review session.

### Daily review skill (`job-radar-daily-review/SKILL.md`)

A Claude Code skill that encodes Ari's full CV, hard-reject rules, salary benchmarks, and output format. Triggered when Ari uploads a CSV and asks for top matches. The skill ignores the `score` column and reads every description in full.

## Data flow: descriptions

Descriptions are critical for scoring quality. Different sources handle them differently:

- **Seek**: Intentionally saves empty description at scrape time. `enrich_descriptions()` fetches the full text via `fetch_description()` using JSON-LD / `__NEXT_DATA__` parsing. Uses a **500-char threshold** (vs 100 for other sources).
- **Adzuna**: API returns 500-char truncated descriptions. `adzuna_scraper.py` calls `enrich_descriptions()` to follow the redirect URL and fetch the full page.
- **LinkedIn (Apify)**: Returns full descriptions natively.
- **Indeed/Google (JobSpy)**: Returns full or partial descriptions depending on the listing.

`backfill_descriptions_from_db()` applies the same site-aware thresholds retroactively to existing DB records.

## Cost controls

Both paid scrapers use a **today-guard** pattern: before calling the API, they check the DB for jobs from that source with `first_seen >= today`. If any exist, the run is skipped entirely. This prevents double-billing from accidental re-runs.

- **Apify**: `RESULTS_PER_QUERY = 20`. Free plan cap $5/month. ~$0.10/run at 11 searches.
- **Adzuna**: `RESULTS_PER_QUERY = 20`. Free limits: 250/day, 1,000/week, 2,500/month. At 11 searches/day = 13% of monthly allowance.

## Environment variables (.env)

| Variable | Required | Purpose |
|---|---|---|
| `APIFY_TOKEN` | Optional | LinkedIn scraping (paid) |
| `ADZUNA_APP_ID` | Optional | Adzuna free job API |
| `ADZUNA_APP_KEY` | Optional | Adzuna free job API |

## Database (jobs.db — never commit)

Single `jobs` table. PK is `job_url`. Key columns: `site`, `title`, `company`, `location`, `description`, `date_posted`, `min_amount`, `max_amount`, `salary_raw`, `fingerprint`, `first_seen`, `score`, `primary_role`, `also_fits`, `match_reasons`, `dismissed`, `applied`, `status`.

Schema is managed by `init_db()` which uses `ALTER TABLE ADD COLUMN` migrations — it only adds columns, never restructures.

## What NOT to touch without careful thought

- **`init_db()`** — only ADD columns, never restructure or rename existing ones
- **`upsert_jobs()`** — fingerprint dedup logic is battle-tested
- **`fetch_description()`** — CSS selectors are fragile and site-specific; test any changes against live URLs
- **`enrich_descriptions()`** — the site-aware threshold logic (500 for Seek, 100 for others) is intentional
- **`role_profiles.json`** — changing `searches` affects API call counts and costs; changing `skills_*` changes every job's score
- **Today-guard blocks** in `apify_scraper.py` and `adzuna_scraper.py` — they prevent double-billing

## Adding a new data source

Follow the pattern in `adzuna_scraper.py`:
1. Add a today-guard checking DB for `site='your_source'` jobs with `first_seen >= today`
2. Fetch jobs and map to the standard DataFrame schema (see `_map_item()` in any scraper)
3. Call `enrich_descriptions()` if the source returns truncated descriptions
4. Return a DataFrame — `run.py` handles `upsert_jobs()` from there
5. Wire into `run.py` with an env-var guard so it only runs when configured

## Role profiles (role_profiles.json)

5 profiles: Data Analyst, Analytics Engineer, Data Scientist, Product Manager (AI/Data), Project Manager. Each defines `searches` (query strings), `title_keywords`, `skills_high` (+6 pts), `skills_mid` (+2 pts), `negative_title_signals` (hard penalty), and optional `must_also_contain` (context gate for PM roles).

## Key decisions log

| Date | Decision | Reason |
|---|---|---|
| May 2026 | Added Apify today-guard | Hit $5 free cap due to accidental double-runs |
| May 2026 | Reduced `RESULTS_PER_QUERY` 40→20 | Halves Apify cost; 24h filter means <20 new jobs/query/day |
| May 2026 | Fixed Seek descriptions (teaser→full) | Teaser text too short for meaningful review |
| May 2026 | Added Adzuna as free source | Supplements LinkedIn coverage at zero cost |
| May 2026 | Added Adzuna today-guard | Protects 250 hits/day free tier limit |
