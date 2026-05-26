"""
Export today's (or recent) scraped jobs to CSV for sharing with Claude/ChatGPT.

DEFAULT BEHAVIOUR: exports jobs scraped in the last 24 hours (based on first_seen).
This means running `python export_for_gpt.py` each morning gives you only fresh jobs.

Usage:
    python export_for_gpt.py                  # last 24h (default — use this daily)
    python export_for_gpt.py --days 2         # last 48h (if you missed yesterday)
    python export_for_gpt.py --days 7         # last week
    python export_for_gpt.py --all            # everything (no date filter)
    python export_for_gpt.py --min-score 60   # raise score threshold
    python export_for_gpt.py --role data_scientist
    python export_for_gpt.py --output my_jobs.csv
"""
import argparse
import csv
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"
DEFAULT_OUT = Path(__file__).parent / "jobs_for_claude.csv"

FIELDS = [
    "title", "company", "location", "site",
    "primary_role", "score", "salary_raw",
    "job_url", "date_posted", "first_seen", "description",
]


def _clean_description(text: str | None) -> str:
    """Strip embedded newlines and collapse whitespace so CSV rows don't break."""
    if not text:
        return ""
    return re.sub(r"[\n\r]+", " ", text).strip()


def export(min_score: int, role: str | None, since: str | None, output: Path, show_all: bool):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    query = """
        SELECT title, company, location, site,
               primary_role, score, salary_raw,
               job_url, date_posted, first_seen, description
        FROM jobs
        WHERE (dismissed = 0 OR dismissed IS NULL)
          AND description IS NOT NULL
          AND LENGTH(description) > 50
          AND score >= ?
    """
    params: list = [min_score]

    if role:
        query += " AND primary_role = ?"
        params.append(role)

    if not show_all and since:
        query += " AND first_seen >= ?"
        params.append(since)

    query += " ORDER BY score DESC, first_seen DESC"

    rows = con.execute(query, params).fetchall()
    con.close()

    if not rows:
        print("No jobs found matching those filters.")
        sys.exit(1)

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            d = dict(row)
            d["description"] = _clean_description(d.get("description"))
            writer.writerow(d)

    label = "all time" if show_all else f"scraped since {since[:10]}"
    print(f"✅ Exported {len(rows)} jobs ({label}) → {output}")
    print(f"   Min score: {min_score} | Role filter: {role or 'all roles'}")
    print(f"   Share this CSV with Claude and ask: 'Which of these jobs match my CV best?'")


def main():
    p = argparse.ArgumentParser(description="Export freshly scraped jobs to CSV for Claude/ChatGPT review")
    p.add_argument("--days", type=int, default=1,
                   help="Export jobs scraped in the last N days (default: 1 = today only). Use 2 if you missed yesterday.")
    p.add_argument("--all", action="store_true",
                   help="No date filter — export everything (ignores --days).")
    p.add_argument("--min-score", type=int, default=50,
                   help="Minimum rules-based score to include (default: 50).")
    p.add_argument("--role", type=str, default=None,
                   help="Filter by role: data_analyst, analytics_engineer, data_scientist, product_manager, project_manager")
    p.add_argument("--output", type=Path, default=DEFAULT_OUT,
                   help=f"Output CSV path (default: {DEFAULT_OUT.name})")
    args = p.parse_args()

    # Calculate the cutoff datetime in UTC
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()

    export(
        min_score=args.min_score,
        role=args.role,
        since=cutoff,
        output=args.output,
        show_all=args.all,
    )


if __name__ == "__main__":
    main()
