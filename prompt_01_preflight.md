# Prompt 01 — Pre-flight Fixes
## Context
You are working on the `job-radar` project. Read `scraper.py`, `scorer.py`, `run.py`, and `dashboard.py` before making any changes.

## Tasks

### Fix 1 — Call the seniority pre-filter that already exists
In `scraper.py`, the function `filter_seniority(df)` is defined but never called.
In `run_searches()`, after `combined = combined.drop_duplicates(...)`, add:
```python
combined = filter_seniority(combined)
```
Do not modify `filter_seniority()` itself.

### Fix 2 — Cap score at 100 in scorer.py
In `scorer.py`, at the end of `score_job()`, before the return statement, add:
```python
score = max(0, min(100, score))
```

### Fix 3 — Schema migration for new columns
In `scraper.py`, inside `init_db()`, after the existing migration block that adds `fingerprint` and `description`, add migrations for these new columns. Use the same pattern already there (check `cols`, then `ALTER TABLE`):

```python
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
}
for col, col_type in new_cols.items():
    if col not in cols:
        conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}")
```

### Fix 4 — Update requirements.txt
Add these lines to `requirements.txt` (do not remove existing lines):
```
flask>=3.0
python-dotenv>=1.0
anthropic>=0.25
pdfplumber>=0.10
slack-sdk>=3.27
```

### Fix 5 — Create .env.example
Create a new file `.env.example` in the project root:
```bash
# Anthropic Claude API
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL_COVER_LETTER=claude-sonnet-4-5-20251001
LLM_MODEL_REASONING=claude-haiku-4-5-20251001

# Scoring config
SALARY_FLOOR_AUD=140000
SALARY_PENALTY_NO_DATA=20
SALARY_PENALTY_PER_10K_BELOW=5

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C...

# Server
SERVER_PORT=5000
PUBLIC_BASE_URL=https://your-ngrok-url.ngrok-free.app
```

### Fix 6 — Update .gitignore
Ensure `.gitignore` contains these entries (add any that are missing):
```
.env
*.db
resume.txt
role_profiles_personalized.json
scoring_weights.json
__pycache__/
.venv/
*.pyc
```

## Validation
After making all changes, run:
```bash
python run.py --no-scrape
```
It should complete without errors. Then run:
```bash
python -c "import sqlite3; conn = sqlite3.connect('jobs.db'); print([r[1] for r in conn.execute('PRAGMA table_info(jobs)').fetchall()])"
```
Confirm that `primary_role`, `status`, `dismissed`, and `user_reaction` appear in the output.

## Do NOT
- Do not modify `upsert_jobs()`, `run_searches()` (beyond Fix 1), or `fetch_description()`
- Do not change the existing column names or types
- Do not restructure any existing functions
