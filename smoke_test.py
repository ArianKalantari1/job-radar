"""
Quick local smoke test. Run this BEFORE `python run.py` to confirm
JobSpy can actually reach the job sites from your machine.

Usage:
    python smoke_test.py
"""
from __future__ import annotations

from jobspy import scrape_jobs

SITES = ["linkedin", "indeed", "google", "glassdoor"]

print("smoke test: 3 results per site, 1 search\n")

for site in SITES:
    try:
        df = scrape_jobs(
            site_name=[site],
            search_term="analytics engineer",
            location="Sydney, Australia",
            results_wanted=3,
            hours_old=168,
            country_indeed="Australia",
            country_glassdoor="Australia",
            google_search_term="analytics engineer jobs near Sydney Australia",
        )
        n = 0 if df is None else len(df)
        flag = "OK" if n > 0 else "EMPTY"
        print(f"  [{flag:5}] {site:10} -> {n} rows")
    except Exception as e:
        print(f"  [FAIL ] {site:10} -> {type(e).__name__}: {str(e)[:120]}")

print("\nIf at least 2 of these returned > 0 rows, you're good to run `python run.py`.")
print("If all are 0/FAILED, your IP may be blocked or you need a VPN.")
