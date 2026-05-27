"""
job-radar: main entry point
Runs the full pipeline: scrape -> dedupe -> score -> export CSV.

Usage:
    python run.py               # full pipeline
    python run.py --no-scrape   # skip scraping, just rescore + re-export
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import os
from dotenv import load_dotenv
load_dotenv(override=True)

from scraper import init_db, run_searches, upsert_jobs, backfill_salary_from_descriptions, purge_senior_jobs_from_db, backfill_descriptions_from_db


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        help="Skip scraping, just rescore and re-export CSV from existing DB",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Accepted for backward compatibility (now the default behaviour)",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("job-radar")
    print("=" * 50)

    init_db()

    if not args.no_scrape:
        print("\n[1/4] scraping job sites...")
        df = run_searches()
        stats = upsert_jobs(df)
        print(
            f"  -> {len(df)} scraped | {stats['new']} new | "
            f"{stats['skipped_url']} URL-dupe | "
            f"{stats['skipped_fingerprint']} cross-platform-dupe | "
            f"{stats['skipped_stale']} stale (>7d)"
        )

        # LinkedIn via Apify — only runs when APIFY_TOKEN is set
        if os.getenv("APIFY_TOKEN"):
            print("\n[1.1] scraping LinkedIn via Apify (with descriptions)...")
            from apify_scraper import scrape_linkedin_via_apify
            li_df = scrape_linkedin_via_apify()
            if not li_df.empty:
                li_stats = upsert_jobs(li_df)
                print(
                    f"  -> {len(li_df)} LinkedIn | {li_stats['new']} new | "
                    f"{li_stats['skipped_url']} URL-dupe | "
                    f"{li_stats['skipped_fingerprint']} cross-platform-dupe"
                )
        else:
            print("\n[1.1] skipped Apify LinkedIn (APIFY_TOKEN not set)")

        # Adzuna — only runs when ADZUNA keys are set
        if os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY"):
            print("\n[1.2] scraping Adzuna jobs (with full descriptions)...")
            from adzuna_scraper import scrape_jobs_via_adzuna
            az_df = scrape_jobs_via_adzuna()
            if not az_df.empty:
                az_stats = upsert_jobs(az_df)
                print(
                    f"  -> {len(az_df)} Adzuna | {az_stats['new']} new | "
                    f"{az_stats['skipped_url']} URL-dupe | "
                    f"{az_stats['skipped_fingerprint']} cross-platform-dupe"
                )
        else:
            print("\n[1.2] skipped Adzuna (ADZUNA_APP_ID / ADZUNA_APP_KEY not set)")
    else:
        print("\n[1/4] skipped scrape (--no-scrape)")

    print("\n[2/4] cleaning + backfilling...")
    purged = purge_senior_jobs_from_db()
    print(f"  -> dismissed {purged} over-senior jobs")
    filled = backfill_salary_from_descriptions()
    print(f"  -> backfilled salary for {filled} jobs")
    desc_filled = backfill_descriptions_from_db()
    print(f"  -> fetched descriptions for {desc_filled} jobs")

    print("\n[3/4] scoring all jobs in DB...")
    from scorer import score_all_jobs
    n = score_all_jobs()
    print(f"  -> scored {n} jobs")

    print("\n[4/4] exporting last 24h jobs to CSV...")
    from export_for_gpt import export
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    out_path = Path(__file__).parent / "jobs_today.csv"
    export(min_score=0, role=None, since=cutoff, output=out_path, show_all=False)

    print("\ndone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
