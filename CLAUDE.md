# job-rader — CLAUDE.md

This file is read automatically by Claude Code and serves as the authoritative
guide to the codebase. Keep it up to date whenever the architecture changes.

---

## What this project is

A personal job-hunt automation tool for **Ari Kalantari** (Sydney, AU).
It scrapes job listings daily, deduplicates them, scores them against Ari's CV
and target role profiles, and renders a Kanban-style HTML dashboard.
It also sends a Slack digest and exposes a Flask API for swipe/dismiss reactions.

This is a **personal use** tool — not a product, not multi-tenant.

---

## File map

| File | Role |
|---|---|
| `run.py` | Main entry point — orchestrates the full pipeline |
| `scraper.py` | Core scraper: Seek (custom) + jobspy (Indeed/Google). Also owns `init_db`, `upsert_jobs`, `fetch_description`, `enrich_descriptions`, `backfill_*` |
| `apify_scraper.py` | LinkedIn scraper via Apify API (paid, ~$0.10/run) |
| `adzuna_scraper.py` | Free job scraper via Adzuna API (free tier: 2,500 calls/month) |
| `scorer.py` | Fast rules-based scorer — no API calls |
| `ai_scorer.py` | Claude Haiku AI scorer — costs money, run manually |
| `dashboard.py` | Renders `dashboard.html` — Kanban board |
| `server.py` | Flask API — swipe/dismiss/apply endpoints |
| `digest.py` | Sends role-grouped Slack digest |
| `role_profiles.json` | 5 role profiles with search queries, skill weights, seniority rules |
| `jobs.db` | SQLite database — **never commit this** |
| `.env` | Secrets — **never commit this** |
| `.env.example` | Template for `.env` — safe to commit |
| `resume.txt` | Ari's resume — **never commit this** (in .gitignore) |

---

## Pipeline (run.py step by step)

```
[1]   scraper.run_searches()       → Seek + Indeed + Google (free, no API key)
[1.1] apify_scraper (if token set) → LinkedIn with full descriptions (paid)
[1.2] adzuna_scraper (if keys set) → AU jobs with full descriptions (free)
[1.3] purge_senior_jobs_from_db()  → hard-removes over-senior titles
[1.5] backfill_salary_from_descriptions()
[1.7] backfill_descriptions_from_db() → fills gaps for non-LinkedIn jobs
[2]   scorer (rules) OR ai_scorer (Claude Haiku)
[3]   dashboard.write_dashboard()  → renders dashboard.html
```

Run flags:
- `python run.py`           — full pipeline with AI scorer
- `python run.py --fast`    — rules scorer only (no API cost)
- `python run.py --no-scrape` — skip scraping, rescore only
- `python run.py --rescore` — wipe ai_scores and re-score everything

---

## Data sources

| Source | File | Cost | Descriptions |
|---|---|---|---|
| Seek | `scraper.py → scrape_seek()` | Free | Full (via `fetch_description`) |
| Indeed | `scraper.py → run_searches()` | Free | Full (via jobspy) |
| Google Jobs | `scraper.py → run_searches()` | Free | Partial |
| LinkedIn | `apify_scraper.py` | ~$0.10/run (Apify) | Full |
| Adzuna | `adzuna_scraper.py` | Free (2,500/month) | Full (via `fetch_description`) |

**Important:** Adzuna API returns a 500-char truncated description. `adzuna_scraper.py`
calls `enrich_descriptions()` after fetching, which calls `fetch_description()` on each
redirect URL to retrieve the full description from the destination job page.

---

## Environment variables (.env)

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | For AI scoring only | Claude Haiku scorer |
| `APIFY_TOKEN` | Optional | LinkedIn scraping (paid) |
| `ADZUNA_APP_ID` | Optional | Adzuna free job API |
| `ADZUNA_APP_KEY` | Optional | Adzuna free job API |
| `SLACK_BOT_TOKEN` | Optional | Slack digest |
| `SLACK_CHANNEL_ID` | Optional | Slack digest |
| `SERVER_PORT` | Optional | Flask server (default 5000) |
| `PUBLIC_BASE_URL` | Optional | ngrok URL for Slack callbacks |

---

## Deduplication logic

Jobs are deduplicated two ways (in `upsert_jobs()`):

1. **URL match** — exact `job_url` already in DB → skip
2. **Fingerprint match** — MD5 of `(title + company + location)` already seen → skip
   This catches the same job posted on LinkedIn AND Indeed AND Seek.

Jobs older than 7 days are also rejected at upsert time (`max_age_days=7`).

---

## Cost controls

### Apify (LinkedIn)
- `RESULTS_PER_QUERY = 20` — max results per search URL (was 40, halved May 2026)
- **Today-guard**: checks DB for `site='linkedin_apify'` jobs with `first_seen >= today`
  before calling the API. If any exist, skips the run entirely. Prevents double-billing.
- Free plan cap: $5/month. At 11 searches × 20 results = ~$0.10/run → ~$3/month daily.
- If Apify fails (no credits, network error): returns empty DataFrame. Pipeline continues.

### Adzuna (free tier)
- `RESULTS_PER_QUERY = 20` — per search term
- **Today-guard**: same pattern as Apify — checks for `site='adzuna'` jobs today.
- Free limits: 250 hits/day · 1,000/week · 2,500/month
- At 11 searches/day = 11 calls/day → ~330/month (13% of free allowance)

### AI scorer (Claude Haiku)
- NOT run in the daily cron (`run_daily.sh` uses `--fast` flag)
- Run manually when recalibrating: `python run.py --rescore`

---

## Seek descriptions — important note

`scrape_seek()` intentionally saves an **empty description** (not the teaser).
This forces `enrich_descriptions()` to fetch the full description from the
Seek job page using `fetch_description()`. The Seek handler in `fetch_description()`
uses JSON-LD and `__NEXT_DATA__` parsing.

`enrich_descriptions()` uses a **500-char threshold for Seek** (vs 100 for all other
sources) so that any teaser that slips through still gets enriched.

`backfill_descriptions_from_db()` applies the same site-aware thresholds to
existing DB records retroactively.

---

## fetch_description() — supported sites

| site value | How description is fetched |
|---|---|
| `linkedin` | `div.description__text` or `div#job-details` |
| `indeed` | `div#jobDescriptionText` |
| `glassdoor` | `div.jobDescriptionContent` |
| `google` | JSON-LD `JobPosting` schema |
| `seek` | JSON-LD → `__NEXT_DATA__` blob fallback |
| `adzuna` | JSON-LD → generic div selectors (follows redirect to real job page) |

---

## Role profiles (role_profiles.json)

5 profiles, each with:
- `searches` — list of search terms sent to every scraper
- `title_keywords` — for scoring title match
- `skills_high` / `skills_mid` — weighted skill matching
- `seniority_target` — junior / mid / senior
- `negative_title_signals` — hard-block these title words

Profiles: Data Analyst · Analytics Engineer · Data Scientist · Product Manager (AI/Data) · Project Manager

---

## Database schema (jobs.db — jobs table)

Key columns: `job_url` (PK), `site`, `title`, `company`, `location`, `description`,
`date_posted`, `min_amount`, `max_amount`, `currency`, `search_label`, `fingerprint`,
`first_seen`, `score`, `primary_role`, `also_fits`, `match_reasons`, `ai_score`,
`ai_reasoning`, `applied`, `dismissed`, `dismiss_reason`, `salary_raw`

---

## What NOT to touch without careful thought

- `init_db()` — only ADD migrations, never restructure existing columns
- `upsert_jobs()` — fingerprint dedup logic is battle-tested
- `fetch_description()` — selectors are fragile, test before changing
- `enrich_descriptions()` — the site-aware threshold logic is intentional
- `role_profiles.json` — changing search terms affects API call counts and costs

---

## Scheduled run (macOS launchd)

`setup_launchd.sh` installs a launchd agent that runs `run_daily.sh` at 8am daily.
`run_daily.sh` calls `python run.py --fast` (rules scorer, no Claude API cost).

To install: `bash setup_launchd.sh`
To check: `launchctl list | grep jobradar`
To remove: `launchctl unload ~/Library/LaunchAgents/com.jobradar.daily.plist`

---

## Testing scripts

| Script | Purpose |
|---|---|
| `smoke_test.py` | Quick connectivity test — run before first full run |
| `test_adzuna.py` | Tests Adzuna API credentials and response shape |
| `test_adzuna_fetch.py` | Tests `fetch_description()` on a live Adzuna redirect URL |

---

## Key decisions log

| Date | Decision | Reason |
|---|---|---|
| May 2026 | Added Apify today-guard | Hit $5 free cap due to accidental double-runs |
| May 2026 | Reduced `RESULTS_PER_QUERY` 40→20 | Halves Apify cost; 24h filter means <20 new jobs/query/day in Sydney |
| May 2026 | Fixed Seek descriptions (teaser→full) | Teaser text too short for AI scoring |
| May 2026 | Added Adzuna as free source | Supplements LinkedIn coverage at zero cost |
| May 2026 | Added Adzuna today-guard | Protects 250 hits/day free tier limit |
