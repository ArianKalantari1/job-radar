"""
Quick Adzuna API test — scrapes 2 jobs and shows whether descriptions come through.
Run with: python test_adzuna.py
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

url = (
    f"https://api.adzuna.com/v1/api/jobs/au/search/1"
    f"?app_id={APP_ID}&app_key={APP_KEY}"
    f"&results_per_page=2"
    f"&what=data+analyst"
    f"&where=Sydney"
)

print("Calling Adzuna API...")
req = urllib.request.Request(url, headers={"Accept": "application/json"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())

total = data.get("count", "N/A")
results = data.get("results", [])
print(f"Total jobs available for 'data analyst' in Sydney: {total}")
print(f"Jobs returned in this test: {len(results)}\n")

for i, job in enumerate(results, 1):
    title    = job.get("title", "N/A")
    company  = job.get("company", {}).get("display_name", "N/A")
    location = job.get("location", {}).get("display_name", "N/A")
    created  = job.get("created", "N/A")[:10]
    url_out  = job.get("redirect_url", "N/A")
    desc     = job.get("description", "")
    sal_min  = job.get("salary_min")
    sal_max  = job.get("salary_max")

    print(f"{'='*60}")
    print(f"Job {i}: {title}")
    print(f"Company:     {company}")
    print(f"Location:    {location}")
    print(f"Posted:      {created}")
    print(f"Salary:      {sal_min} – {sal_max}" if sal_min or sal_max else "Salary:      not listed")
    print(f"URL:         {url_out}")
    print(f"Description: {len(desc)} characters")
    if desc:
        print(f"Preview:     {desc[:400]}{'...' if len(desc) > 400 else ''}")
    else:
        print("Preview:     ⚠ NO DESCRIPTION RETURNED")
    print()

print("="*60)
print("✅ Test complete." if results else "⚠ No results returned — check credentials.")
