#!/bin/bash
# setup_launchd.sh — install job-radar as a macOS launchd agent.
#
# Unlike cron, launchd runs the job shortly after wake if the Mac was
# sleeping at the scheduled time. Safe to re-run.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER="$SCRIPT_DIR/run_daily.sh"
PLIST_LABEL="com.jobradar.daily"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"

chmod +x "$RUNNER"

# Write the plist
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$RUNNER</string>
    </array>

    <!-- Run at 8:00 AM every day -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <!-- If the Mac was asleep at 8am, run shortly after next wake -->
    <key>RunAtLoad</key>
    <false/>

    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/job-radar.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/job-radar.log</string>
</dict>
</plist>
EOF

# Unload old version if running, then load fresh
launchctl unload "$PLIST_PATH" 2>/dev/null
launchctl load "$PLIST_PATH"

echo "✓ launchd agent installed — runs at 8:00 AM daily."
echo "  Missed runs (e.g. Mac was asleep) fire shortly after next wake."
echo ""
echo "Useful commands:"
echo "  launchctl list | grep jobradar   → check it's loaded"
echo "  launchctl unload $PLIST_PATH     → remove it"
echo "  tail -f $SCRIPT_DIR/job-radar.log → watch live output"
