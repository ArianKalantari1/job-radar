"""
job-radar: main entry point
Runs the full pipeline: scrape -> dedupe -> score -> render dashboard.

Usage:
    python run.py               # full pipeline with Claude AI scorer
    python run.py --fast        # use rules-based scorer (no API calls, no cost)
    python run.py --no-scrape   # skip scraping, just rescore + rerender
    python run.py --rescore     # wipe existing ai_scores and re-score everything
    python run.py --open        # open dashboard in browser when done
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

import os
from dotenv import load_dotenv
load_dotenv(override=True)

from scraper import init_db, run_searches, upsert_jobs, backfill_salary_from_descriptions, purge_senior_jobs_from_db, backfill_descriptions_from_db
from dashboard import write_dashboard, OUTPUT_PATH


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        help="Skip scraping, just rescore and rerender dashboard from existing DB",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use rules-based scorer instead of Claude API (no API credits used)",
    )
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="Wipe existing ai_scores and re-score all jobs. Use when recalibrating.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the dashboard in your default browser when done",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("job-radar")
    print("=" * 50)

    init_db()

    if not args.no_scrape:
        print("\n[1/3] scraping job sites...")
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
            print("\n[1.1/3] scraping LinkedIn via Apify (with descriptions)...")
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
            print("\n[1.1/3] skipped Apify LinkedIn (APIFY_TOKEN not set)")

        # Adzuna — only runs when ADZUNA keys are set
        if os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY"):
            print("\n[1.2/3] scraping Adzuna jobs (with full descriptions)...")
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
            print("\n[1.2/3] skipped Adzuna (ADZUNA_APP_ID / ADZUNA_APP_KEY not set)")
    else:
        print("\n[1/3] skipped scrape (--no-scrape)")

    print("\n[1.3/3] purging over-senior jobs from DB...")
    purged = purge_senior_jobs_from_db()
    print(f"  -> dismissed {purged} jobs with senior/lead/director titles")

    print("\n[1.5/3] backfilling salary from descriptions...")
    filled = backfill_salary_from_descriptions()
    print(f"  -> updated salary for {filled} existing jobs")

    print("\n[1.7/3] backfilling descriptions for non-LinkedIn jobs...")
    desc_filled = backfill_descriptions_from_db()
    print(f"  -> fetched descriptions for {desc_filled} jobs")

    print("\n[2/3] scoring all jobs in DB...")
    if args.fast:
        print("  (--fast mode: using rules-based scorer, no API calls)")
        from scorer import score_all_jobs
        n = score_all_jobs()
    else:
        from ai_scorer import ai_score_all_jobs
        n = ai_score_all_jobs(rescore=args.rescore)
    print(f"  -> scored {n} jobs")

    print("\n[3/3] rendering dashboard...")
    write_dashboard()

    if args.open:
        webbrowser.open(f"file://{OUTPUT_PATH.absolute()}")

    scorer_note = "(rules-based, --fast mode)" if args.fast else "(Claude AI scorer)"
    print(f"\ndone {scorer_note}. run `python server.py` then open http://localhost:5000")

    # Auto-export last 24h of jobs to CSV so it's ready for Claude review each morning.
    print("\n[4/3] exporting last 24h jobs to jobs_today.csv...")
    from export_for_gpt import export
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    out_path = Path(__file__).parent / "jobs_today.csv"
    export(min_score=0, role=None, since=cutoff, output=out_path, show_all=False)

    return 0


if __name__ == "__main__":
    sys.exit(main())
