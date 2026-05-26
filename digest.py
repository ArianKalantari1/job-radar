"""
job-radar: Slack digest sender

Sends new jobs to Slack, grouped by role family.
Each role family gets its own message.

Usage:
    python digest.py          # send digest for all new jobs
    python digest.py --dry-run  # print what would be sent without posting to Slack
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

DB_PATH = Path(__file__).parent / "jobs.db"
PROFILES_PATH = Path(__file__).parent / "role_profiles.json"

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL_ID", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5000").rstrip("/")


def get_profile_order() -> list[dict]:
    """Return profiles in display order from role_profiles.json."""
    with open(PROFILES_PATH) as f:
        config = json.load(f)
    return config["profiles"]


def fetch_new_jobs() -> list[dict]:
    """Fetch jobs not yet sent in a digest, not dismissed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT job_url, title, company, location,
               score, primary_role, also_fits, match_reasons,
               salary_min, salary_max, salary_raw,
               min_amount, max_amount
        FROM jobs
        WHERE (dismissed = 0 OR dismissed IS NULL)
          AND (digest_sent_at IS NULL OR digest_sent_at = '')
          AND (user_reaction IS NULL OR user_reaction = '')
        ORDER BY score DESC
        """
    ).fetchall()
    conn.close()
    jobs = []
    for row in rows:
        j = dict(row)
        for field in ("also_fits", "match_reasons"):
            if j.get(field):
                try:
                    j[field] = json.loads(j[field])
                except Exception:
                    j[field] = []
        jobs.append(j)
    return jobs


def format_salary(job: dict) -> str:
    """Format salary for display."""
    lo = job.get("salary_min") or job.get("min_amount")
    hi = job.get("salary_max") or job.get("max_amount")
    raw = job.get("salary_raw")
    if lo and hi:
        return f"${int(lo):,} – ${int(hi):,} AUD"
    if lo:
        return f"${int(lo):,}+ AUD"
    if raw:
        return raw
    return "Salary not listed"


def build_job_block(job: dict, profile_label: str) -> list[dict]:
    """Build Slack Block Kit blocks for a single job."""
    from urllib.parse import quote
    title = job.get("title") or "Untitled"
    company = job.get("company") or "Unknown"
    location = job.get("location") or ""
    score = job.get("score") or 0
    salary = format_salary(job)
    job_url = job.get("job_url") or "#"

    # Top 3 match reasons, cleaned up
    reasons = job.get("match_reasons") or []
    reasons_text = "\n".join(f"• {r}" for r in reasons[:3]) if reasons else "• No reasons available"

    # also_fits tags
    also_fits = job.get("also_fits") or []
    also_fits_text = f"🏷️ Also fits: {', '.join(also_fits)}" if also_fits else ""

    # Score emoji
    score_emoji = "🟢" if score >= 75 else ("🟡" if score >= 60 else "🔴")

    # Reaction URLs — URL-encode the job_url
    encoded_url = quote(job_url, safe="")
    good_url = f"{PUBLIC_BASE_URL}/api/jobs/{encoded_url}/reaction/good"
    bad_url = f"{PUBLIC_BASE_URL}/api/jobs/{encoded_url}/reaction/bad"

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*<{job_url}|{title}>*\n"
                    f"{company}  ·  {location}\n"
                    f"{score_emoji} Score: *{score}*  ·  💰 {salary}"
                ),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Why it matched:*\n{reasons_text}"
                + (f"\n{also_fits_text}" if also_fits_text else ""),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "👍 Good match"},
                    "style": "primary",
                    "url": good_url,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "👎 Not for me"},
                    "style": "danger",
                    "url": bad_url,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔗 View job"},
                    "url": job_url,
                },
            ],
        },
        {"type": "divider"},
    ]
    return blocks


def build_role_message(profile: dict, jobs: list[dict]) -> dict:
    """Build the full Slack message for one role family."""
    label = profile["label"]
    count = len(jobs)
    now = datetime.now(timezone.utc).strftime("%a %d %b, %I:%M %p UTC")

    header_blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📋 {label} — {count} new job{'s' if count != 1 else ''}",
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"job-radar digest · {now}"}
            ],
        },
        {"type": "divider"},
    ]

    job_blocks = []
    for job in jobs:
        job_blocks.extend(build_job_block(job, label))

    return {
        "channel": SLACK_CHANNEL,
        "blocks": header_blocks + job_blocks,
        "text": f"{label}: {count} new jobs",  # fallback for notifications
    }


def mark_jobs_sent(job_urls: list[str]) -> None:
    """Mark jobs as included in digest so they don't appear again."""
    if not job_urls:
        return
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "UPDATE jobs SET digest_sent_at = ? WHERE job_url = ?",
        [(now, url) for url in job_urls],
    )
    conn.commit()
    conn.close()


def send_digest(dry_run: bool = False) -> dict:
    """
    Main entry point. Fetches new jobs, groups by role, sends to Slack.
    Returns summary dict.
    """
    profiles = get_profile_order()
    jobs = fetch_new_jobs()

    if not jobs:
        print("No new jobs to send.")
        return {"total": 0, "by_role": {}}

    # Group by primary_role
    by_role: dict[str, list[dict]] = {}
    for job in jobs:
        role = job.get("primary_role") or "unknown"
        by_role.setdefault(role, []).append(job)

    print(f"Found {len(jobs)} new jobs across {len(by_role)} role families.")

    client = WebClient(token=SLACK_TOKEN) if not dry_run else None
    sent_urls: list[str] = []
    summary: dict = {"total": len(jobs), "by_role": {}}

    for profile in profiles:
        role_id = profile["id"]
        role_jobs = by_role.get(role_id, [])
        if not role_jobs:
            continue

        message = build_role_message(profile, role_jobs)
        summary["by_role"][role_id] = len(role_jobs)

        if dry_run:
            print(f"\n--- DRY RUN: {profile['label']} ({len(role_jobs)} jobs) ---")
            for job in role_jobs:
                print(f"  [{job.get('score'):3}] {job.get('title')} @ {job.get('company')}")
                reasons = job.get("match_reasons") or []
                for r in reasons[:2]:
                    print(f"         {r}")
        else:
            try:
                client.chat_postMessage(**message)
                sent_urls.extend(j["job_url"] for j in role_jobs)
                print(f"  ✓ Sent {profile['label']}: {len(role_jobs)} jobs")
            except SlackApiError as e:
                print(f"  ✗ Failed {profile['label']}: {e.response['error']}")

    if not dry_run and sent_urls:
        mark_jobs_sent(sent_urls)
        print(f"\nMarked {len(sent_urls)} jobs as sent.")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print digest without sending to Slack")
    args = parser.parse_args()
    send_digest(dry_run=args.dry_run)
