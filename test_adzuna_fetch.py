"""
Test: does fetch_description() work with Adzuna redirect URLs?

Fetches 1 job from Adzuna, then calls fetch_description() on the redirect URL
to get the full description from the real job page.

Run with: python test_adzuna_fetch.py
"""
import json
import os
import urllib.request
from dotenv import load_dotenv

load_dotenv()

APP_ID  = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")

if not APP_ID or not APP_KEY:
    print("ERROR: ADZUNA_APP_ID or ADZUNA_APP_KEY not set in .env")
    raise SystemExit(1)

# ── Step 1: pull 1 job from Adzuna ─────────────────────────────────────────
url = (
    f"https://api.adzuna.com/v1/api/jobs/au/search/1"
    f"?app_id={APP_ID}&app_key={APP_KEY}"
    f"&results_per_page=1"
    f"&what=data+analyst"
    f"&where=Sydney"
)
print("Step 1: Calling Adzuna API for 1 job...")
req = urllib.request.Request(url, headers={"Accept": "application/json"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())

jobs = data.get("results", [])
if not jobs:
    print("No results — check credentials.")
    raise SystemExit(1)

job       = jobs[0]
title     = job.get("title", "N/A")
company   = job.get("company", {}).get("display_name", "N/A")
api_desc  = job.get("description", "")
redir_url = job.get("redirect_url", "")

print(f"  Title:           {title}")
print(f"  Company:         {company}")
print(f"  Adzuna URL:      {redir_url}")
print(f"  API description: {len(api_desc)} chars (truncated preview)")
print()

# ── Step 2: use fetch_description() to get the full description ─────────────
print("Step 2: Calling fetch_description() to get full description from job page...")
from scraper import fetch_description

full_desc = fetch_description(redir_url, "adzuna")

if full_desc:
    print(f"  ✅ Full description fetched: {len(full_desc)} chars")
    print(f"  Preview (first 500 chars):")
    print(f"  {full_desc[:500]}{'...' if len(full_desc) > 500 else ''}")
else:
    print("  ⚠ fetch_description() returned None — page may have blocked the request")
    print("  The Adzuna redirect URL destination was:")
    import requests
    r = requests.get(redir_url, allow_redirects=True, timeout=10)
    print(f"  Final URL after redirect: {r.url}")
    print(f"  Status code: {r.status_code}")

print()
print("=" * 60)
if full_desc and len(full_desc) > 200:
    print("✅ PASS — fetch_description works with Adzuna URLs. Safe to integrate.")
elif full_desc:
    print("⚠ PARTIAL — got a short description. May need parser tuning.")
else:
    print("❌ FAIL — could not fetch full description from Adzuna redirect URL.")
