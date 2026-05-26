# GitHub Copilot Instructions — job-rader

This file is read automatically by GitHub Copilot for repository-level context.
Full documentation is in `CLAUDE.md` at the repo root — read that first.

---

## Project summary

Personal job-hunt tool for Ari Kalantari (Sydney, AU).
Scrapes jobs daily from Seek, Indeed, Google Jobs, LinkedIn (Apify), and Adzuna.
Deduplicates, scores against 5 role profiles, renders an HTML Kanban dashboard,
and sends Slack digests.

**Stack:** Python 3.11 · SQLite · Flask · jobspy · Apify · Adzuna API · Claude Haiku

---

## Files to understand before editing

1. `CLAUDE.md` — full architecture, decisions log, cost controls, gotchas
2. `role_profiles.json` — drives ALL search queries and scoring weights
3. `scraper.py` — core DB logic (`init_db`, `upsert_jobs`, `fetch_description`)

---

## Hard rules

- **Never commit** `.env`, `jobs.db`, or `resume.txt` — all in `.gitignore`
- **Never restructure** existing DB columns in `init_db()` — only add migrations
- **Never rewrite** `upsert_jobs()`, `fetch_description()`, or `enrich_descriptions()` — these are stable and tested
- **Always check** `RESULTS_PER_QUERY` limits in `apify_scraper.py` and `adzuna_scraper.py` before increasing — they control API costs
- **Always preserve** the today-guard blocks at the top of `scrape_linkedin_via_apify()` and `scrape_jobs_via_adzuna()` — they prevent double-billing

---

## Adding a new data source

Follow the pattern in `adzuna_scraper.py`:
1. Today-guard → check DB for `site='your_source'` jobs with `first_seen >= today`
2. Fetch jobs → map to the standard schema (see `_map_item()` in any scraper)
3. Call `enrich_descriptions()` if the source returns truncated descriptions
4. Return a DataFrame — `run.py` handles `upsert_jobs()` from there
5. Wire into `run.py` with an env-var guard so it only activates when configured

---

## Schema — standard job row

```python
{
    "job_url":      str,   # unique, used as primary key
    "site":         str,   # "seek" | "indeed" | "linkedin_apify" | "adzuna" | ...
    "title":        str,
    "company":      str,
    "location":     str,
    "description":  str | None,
    "date_posted":  str,   # ISO date YYYY-MM-DD
    "min_amount":   float | None,
    "max_amount":   float | None,
    "currency":     str,   # "AUD"
    "search_label": str,   # matches role profile label
    "fingerprint":  str,   # MD5(title+company+location) for cross-platform dedup
    "first_seen":   str,   # ISO datetime UTC
}
```

---

## Running the project

```bash
source .venv/bin/activate
python run.py --fast     # daily use (no AI scorer, no API cost)
python run.py            # full run with Claude Haiku scorer
python run.py --no-scrape --rescore  # re-score existing jobs only
python server.py         # start Flask API (needed for Slack swipe callbacks)
```
