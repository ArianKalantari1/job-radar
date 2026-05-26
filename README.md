# job-radar

A personal job board scraper. Pulls roles from LinkedIn, Indeed, Google Jobs, and Glassdoor, scores them against your skill profile, and outputs a single HTML dashboard you can open every morning.

> **Note:** The PyPI `python-jobspy` package no longer supports Seek directly. Indeed + LinkedIn together cover most AU listings, and Google Jobs is a meta-aggregator that picks up the rest (including Seek postings re-syndicated elsewhere).

## What it does

1. **Scrapes** LinkedIn, Indeed, Google Jobs, and Glassdoor using [JobSpy](https://github.com/cullenwatson/JobSpy)
2. **Dedupes** against a local SQLite cache so you only see new jobs
3. **Scores** each job 0-100 against your skills, target seniority, and domain
4. **Renders** a static HTML dashboard, ranked by score

No API keys. No login required. Runs entirely on your laptop.

## Setup

```bash
# Clone or download the repo, then:
cd job-radar

# Set up a virtualenv (recommended)
python -m venv .venv
source .venv/bin/activate  # mac/linux
# or: .venv\Scripts\activate  # windows

# Install dependencies
pip install -r requirements.txt
```

## Verify it works on your machine

Before the first full run, do a quick connectivity test:

```bash
python smoke_test.py
```

If at least two sites return > 0 rows, you're good. If everything is 0 or FAIL, your network is likely blocking the requests — try a VPN or switch networks.

## Usage

```bash
# Full run: scrape + score + render dashboard
python run.py

# Open the dashboard in your browser when done
python run.py --open

# Skip scraping, just rescore (fast — for tuning your scoring rules)
python run.py --no-scrape
```

Then open `dashboard.html` in your browser.

## Customising for you

**`scraper.py`** — edit the `SEARCHES` list. Each entry is one search query. Add or remove role types as your job hunt evolves.

**`scorer.py`** — this is where the matching logic lives. Tune three lists:

- `SKILLS_STRONG` — your top skills. Each match is +5 to the score.
- `SKILLS_NICE` — supporting skills. Each match is +2.
- `DOMAIN_BONUS` — industries you have a track record in. +3.

Title penalties knock down the score for roles too senior for you. Years-of-experience patterns boost or cut based on what the description asks for.

The whole scoring system is ~30 lines of Python. Read it, tune it, own it.

## Daily routine

```bash
python run.py --open
```

That's it. New jobs every day, ranked, with apply links.

## Optional: schedule it

On macOS / Linux, add to your crontab to run every morning at 7am:

```
0 7 * * * cd /path/to/job-radar && /path/to/.venv/bin/python run.py
```

On Windows, use Task Scheduler.

## Future ideas

- Pipe the top 5 jobs into a daily email
- Use the Anthropic API to generate a tailored cover letter for any job in one click
- Track which jobs you've applied to (the `applied` column already exists in the schema)
- Add a "hidden" toggle so you can hide jobs that scored high but you don't want
- Add JobAdder / Hatch / Ethical Jobs as additional sources
- Build a custom Seek scraper (would need a maintained scraper since JobSpy dropped support)

## How the dashboard looks

Each card shows:
- Match score (0-100, colour-coded)
- Site (Seek / LinkedIn / Indeed)
- Title, company, location
- Salary (if disclosed)
- 280-char description preview
- "why this score" — the exact reasons the scorer assigned the score

Click the title to open the full job ad on the source site.
