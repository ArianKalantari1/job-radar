#!/bin/bash
# job-radar daily runner
# Called by cron (or launchd). Scrapes fresh jobs, scores with the fast
# rules-based scorer (no Claude API calls), and renders the dashboard.
# AI scoring via Claude Haiku is intentionally NOT run here — do that manually.

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

# Export last 24 hours of jobs to CSV for Cowork review.
# Ignores the rules-based score filter (--min-score 0) so Claude sees every fresh job.
# Output: jobs_today.csv in this folder — drag it into Cowork each morning.
echo "exporting today's jobs..." >> "$LOG_FILE"
# Date-stamped CSV: jobs_2026-05-26.csv (today's date = the day being scraped)
TODAY=$(date -v-1d '+%Y-%m-%d')
OUT_CSV="$SCRIPT_DIR/jobs_${TODAY}.csv"
"$PYTHON" export_for_gpt.py --days 1 --min-score 0 --output "$OUT_CSV" >> "$LOG_FILE" 2>&1
echo "export done: $(date '+%Y-%m-%d %H:%M:%S') → $OUT_CSV" >> "$LOG_FILE"

# Copy log back to Desktop project folder
cp "$LOG_FILE" "$FINAL_LOG" 2>/dev/null || true

# Stamp last successful run time (used by catchup.sh)
date +%s > /tmp/jobradar-last-run.txt
