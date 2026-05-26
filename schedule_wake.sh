#!/bin/bash
# Sets a one-time pmset wake for tomorrow at 23:55 (5 min before midnight scrape).
# Called daily by launchd so the wake is always scheduled ahead.
# macOS-only (pmset does not exist on Linux).

TOMORROW=$(date -v+1d '+%m/%d/%Y')
pmset schedule wake "${TOMORROW} 23:55:00" 2>/dev/null
echo "wake scheduled for ${TOMORROW} 23:55:00 at $(date)" >> /tmp/jobradar-wake.log
