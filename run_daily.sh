#!/bin/bash
# job-radar daily runner
# Called by cron (or launchd) at midnight. Scrapes fresh jobs, scores with
# the rules-based scorer, and exports a date-stamped CSV.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/jobradar-run.log"
FINAL_LOG="$SCRIPT_DIR/job-radar.log"
PYTHON="$SCRIPT_DIR/.venv/bin/python"

echo "========================================" >> "$LOG_FILE"
echo "run started: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"

cd "$SCRIPT_DIR" || exit 1

"$PYTHON" run.py --fast >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

echo "run finished: $(date '+%Y-%m-%d %H:%M:%S') | exit=$EXIT_CODE" >> "$LOG_FILE"

# Export last 24 hours of jobs to a date-stamped CSV for morning review.
# Running at midnight means yesterday's jobs — name the file accordingly.
echo "exporting jobs..." >> "$LOG_FILE"
SCRAPE_DATE=$(date -d "yesterday" '+%Y-%m-%d' 2>/dev/null || date -v-1d '+%Y-%m-%d')
OUT_CSV="$SCRIPT_DIR/jobs_${SCRAPE_DATE}.csv"
"$PYTHON" export_for_gpt.py --days 1 --min-score 0 --output "$OUT_CSV" >> "$LOG_FILE" 2>&1
echo "export done: $(date '+%Y-%m-%d %H:%M:%S') → $OUT_CSV" >> "$LOG_FILE"

# Copy log back to project folder
cp "$LOG_FILE" "$FINAL_LOG" 2>/dev/null || true

# Stamp last successful run time (used by catchup.sh)
date +%s > /tmp/jobradar-last-run.txt
