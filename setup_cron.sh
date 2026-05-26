#!/bin/bash
# setup_cron.sh — install the job-radar daily cron job.
# Runs the scraper every day at 7:00 AM.
# Safe to re-run: won't add duplicate entries.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER="$SCRIPT_DIR/run_daily.sh"
CRON_COMMENT="# job-radar daily scrape"

# Make the runner executable
chmod +x "$RUNNER"

# Check if already installed
if crontab -l 2>/dev/null | grep -qF "$RUNNER"; then
    echo "✓ cron job already installed. No changes made."
    echo ""
    echo "Current entry:"
    crontab -l | grep -F "$RUNNER"
    exit 0
fi

# Add the new entry (preserve existing crontab)
(crontab -l 2>/dev/null; echo ""; echo "$CRON_COMMENT"; echo "0 8 * * * $RUNNER") | crontab -

echo "✓ cron job installed — runs every day at 8:00 AM."
echo ""
echo "Useful commands:"
echo "  crontab -l               → view all cron jobs"
echo "  crontab -e               → edit cron jobs manually"
echo "  tail -f $SCRIPT_DIR/job-radar.log   → watch live output"
echo ""
echo "To change the time, run:  crontab -e"
echo "  Format: minute hour * * *"
echo "  Examples:"
echo "    0 8  * * *   → 8:00 AM every day (current)"
echo "    0 8  * * *   → 8:00 AM every day"
echo "    0 7  * * 1-5 → 7:00 AM weekdays only"
echo ""
echo "To remove the job:  crontab -e  and delete the job-radar line."
