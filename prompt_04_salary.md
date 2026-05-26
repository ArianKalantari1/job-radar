# Prompt 04 — Salary Parser
## Context
You are working on the `job-radar` project. Read `scraper.py` fully before making changes.

The DB audit shows 0/449 jobs have salary data from JobSpy's structured fields. The only source of salary is plain text inside job descriptions. We need to extract it from there.

## Task — Add `parse_salary()` to `scraper.py` and call it in `upsert_jobs()`

### Step 1 — Add the parser function
Add this function to `scraper.py` after the `_strip_html()` function:

```python
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

    # Pattern 2: range with full numbers — $120,000 - $150,000
    m = re.search(
        r"\$\s*([\d,]{6,})\s*[-–—to]+\s*\$?\s*([\d,]{6,})",
        t
    )
    if m:
        lo = int(m.group(1).replace(",", ""))
        hi = int(m.group(2).replace(",", ""))
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
```

### Step 2 — Call it in `upsert_jobs()`
In `upsert_jobs()`, inside the `for _, row in df.iterrows():` loop, after the fingerprint check and before the `conn.execute("INSERT INTO jobs ...")` call, add:

```python
# Parse salary from description text (structured salary fields are empty for AU listings)
desc_text = row.get("description") or ""
salary_parsed = parse_salary(desc_text)
# Also check the structured fields from JobSpy as a fallback
sal_min = row.get("min_amount") or salary_parsed["salary_min"]
sal_max = row.get("max_amount") or salary_parsed["salary_max"]
sal_raw = salary_parsed["salary_raw"]
```

### Step 3 — Store parsed salary in INSERT
In the same `upsert_jobs()` function, update the `INSERT INTO jobs` statement to also include `salary_min`, `salary_max`, `salary_raw`:

Add these columns to the INSERT column list:
```
salary_min, salary_max, salary_raw,
```

And add these values to the VALUES tuple:
```python
sal_min,
sal_max,
sal_raw,
```

Make sure the positions match (columns and values must align).

### Step 4 — Backfill existing rows
Add a new function after `upsert_jobs()`:

```python
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
```

### Step 5 — Call backfill in `run.py`
In `run.py`, add this import at the top:
```python
from scraper import init_db, run_searches, upsert_jobs, backfill_salary_from_descriptions
```

After the `upsert_jobs(df)` call (or after the `--no-scrape` block), add:
```python
print("\n[1.5/3] backfilling salary from descriptions...")
filled = backfill_salary_from_descriptions()
print(f"  -> updated salary for {filled} existing jobs")
```

## Validation
Run:
```bash
python run.py --no-scrape
```

Then check salary coverage:
```bash
python -c "
import sqlite3
conn = sqlite3.connect('jobs.db')
total = conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
has_sal = conn.execute('SELECT COUNT(*) FROM jobs WHERE salary_min IS NOT NULL').fetchone()[0]
print(f'Salary coverage: {has_sal}/{total}')
rows = conn.execute('SELECT title, salary_min, salary_max, salary_raw FROM jobs WHERE salary_min IS NOT NULL LIMIT 10').fetchall()
for r in rows: print(r)
conn.close()
"
```

Expected: at least some jobs now have salary data. Even 5-10% is a win — most AU job listings don't disclose salary in text either.

## Do NOT
- Do not modify `init_db()`, `fetch_description()`, `enrich_descriptions()`, or `run_searches()`
- Do not change the `score` column — that is handled by `scorer.py`
- Do not touch `scorer.py`, `dashboard.py`, or `role_profiles.json`
