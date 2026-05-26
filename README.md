# job-radar

A personal job scraper. Pulls roles from Seek, Indeed, Google Jobs, LinkedIn (via Apify), and Adzuna, scores them against your skill profile, and exports a ranked CSV for morning review.

## What it does

1. **Scrapes** Seek (custom), Indeed + Google Jobs ([JobSpy](https://github.com/cullenwatson/JobSpy)), LinkedIn (Apify), and Adzuna
2. **Dedupes** against a local SQLite cache so you only see new jobs
3. **Scores** each job 0–100 against 5 role profiles (rules-based, no API cost)
4. **Exports** a date-stamped CSV for review in Claude Code each morning

Core pipeline needs no API keys. Apify (LinkedIn) and Adzuna are optional paid/free add-ons.

## Setup

```bash
cd job-radar
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit with your API keys if using Apify/Adzuna
```

## Verify it works

```bash
python smoke_test.py
```

If at least two sites return > 0 rows, you're good.

## Usage

```bash
python run.py               # full pipeline: scrape → score → export CSV
python run.py --no-scrape   # skip scraping, just rescore + re-export
```

The pipeline outputs `jobs_today.csv` in the project folder.

## Manual CSV export

```bash
python export_for_gpt.py                  # last 24h, score >= 50
python export_for_gpt.py --days 2         # last 48h (missed yesterday)
python export_for_gpt.py --min-score 0    # all jobs regardless of score
python export_for_gpt.py --role data_scientist  # filter by role
```

## Daily automation

Schedule the scraper to run at midnight so fresh jobs are ready each morning:

**macOS (launchd — recommended):**
```bash
bash setup_launchd.sh
```

**Linux / macOS (cron):**
```bash
bash setup_cron.sh
```

Both install a midnight job that runs `run_daily.sh`, which scrapes, scores, and exports a date-stamped CSV (`jobs_YYYY-MM-DD.csv`).

## Customising

**`role_profiles.json`** — search queries, title keywords, skill weights, and seniority rules for all 5 role profiles. This is the main configuration file.

**`scorer.py`** — rules-based scoring logic. Tune skill lists, salary floor, location bonuses, and seniority penalties.

**`.env`** — API keys for optional data sources (Apify for LinkedIn, Adzuna for free job listings).
