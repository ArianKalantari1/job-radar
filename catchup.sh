#!/bin/bash
# catchup.sh — runs job-radar only if last scrape was more than 20 hours ago.
# Called every 30 minutes by launchd so if Mac was asleep at midnight,
# it catches up the moment the Mac wakes up.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP_FILE="/tmp/jobradar-last-run.txt"
MIN_GAP_HOURS=20

# Read last run timestamp
if [ -f "$STAMP_FILE" ]; then
    LAST_RUN=$(cat "$STAMP_FILE")
    NOW=$(date +%s)
    GAP_SECONDS=$(( NOW - LAST_RUN ))
    GAP_HOURS=$(( GAP_SECONDS / 3600 ))
else
    GAP_HOURS=999
fi

echo "catchup check: gap=${GAP_HOURS}h (threshold=${MIN_GAP_HOURS}h)" >> /tmp/jobradar-catchup.log

if [ "$GAP_HOURS" -ge "$MIN_GAP_HOURS" ]; then
    echo "gap exceeded — running scrape at $(date)" >> /tmp/jobradar-catchup.log
    bash "$SCRIPT_DIR/run_daily.sh"
    date +%s > "$STAMP_FILE"
    echo "scrape done at $(date)" >> /tmp/jobradar-catchup.log
else
    echo "recent run found — skipping" >> /tmp/jobradar-catchup.log
fi
