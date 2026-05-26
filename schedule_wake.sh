#!/bin/bash
# Sets a one-time pmset wake for tomorrow at 07:55 AM.
# Called daily by launchd at 07:50 AM so the wake is always scheduled ahead.
# Note: pmset schedule wake sets a one-time event; this script refreshes it daily.

TOMORROW=$(date -v+1d '+%m/%d/%Y')
pmset schedule wake "${TOMORROW} 07:55:00" 2>/dev/null
echo "wake scheduled for ${TOMORROW} 07:55:00 at $(date)" >> /tmp/jobradar-wake.log
