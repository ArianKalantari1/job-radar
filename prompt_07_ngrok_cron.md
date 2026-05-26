# Prompt 07 — ngrok + Cron Setup (Manual Steps)
## ⚠️ This is NOT a Copilot prompt
This file contains manual steps you (Ari) need to do yourself.
Copilot cannot click dashboards, install system daemons, or configure terminal sessions.

---

## Step 1 — Install ngrok

```bash
# macOS with Homebrew
brew install ngrok

# Or download from https://ngrok.com/download
```

Sign up for a free ngrok account at https://ngrok.com.
Then authenticate:
```bash
ngrok config add-authtoken YOUR_AUTHTOKEN
```

---

## Step 2 — Start your local server + ngrok

You need TWO terminal windows running simultaneously:

**Terminal 1 — Flask server:**
```bash
cd ~/Desktop/job-radar   # or wherever your project is
source .venv/bin/activate
python server.py
```

**Terminal 2 — ngrok tunnel:**
```bash
ngrok http 5000
```

ngrok will show you a URL like:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:5000
```

Copy that URL (e.g. `https://abc123.ngrok-free.app`) and add it to your `.env`:
```bash
PUBLIC_BASE_URL=https://abc123.ngrok-free.app
```

⚠️ **Important:** The ngrok URL changes every time you restart ngrok on the free plan.
When it changes, update `.env` and re-run the digest — otherwise Slack buttons will 404.

**Workaround options:**
- ngrok paid plan (~$10/month) → static URL, never changes
- Cloudflare Tunnel (free, stable) → see Step 2b below

---

## Step 2b — Cloudflare Tunnel (recommended free alternative)

If you don't want to pay for ngrok:

```bash
# Install cloudflared
brew install cloudflared

# Log in
cloudflared tunnel login

# Create a named tunnel
cloudflared tunnel create job-radar

# Start tunnel pointing to local server
cloudflared tunnel --url http://localhost:5000
```

This gives you a stable `*.trycloudflare.com` URL. Add it to `.env` as `PUBLIC_BASE_URL`.

---

## Step 3 — Schedule scrape + digest twice daily (macOS launchd)

**Option A: cron (simpler)**

Open your crontab:
```bash
crontab -e
```

Add these two lines (adjust the path to match where your project actually lives):
```cron
0 8  * * * cd /Users/YOUR_USERNAME/Desktop/job-radar && /Users/YOUR_USERNAME/Desktop/job-radar/.venv/bin/python run.py && /Users/YOUR_USERNAME/Desktop/job-radar/.venv/bin/python digest.py >> /tmp/job-radar.log 2>&1

0 18 * * * cd /Users/YOUR_USERNAME/Desktop/job-radar && /Users/YOUR_USERNAME/Desktop/job-radar/.venv/bin/python run.py && /Users/YOUR_USERNAME/Desktop/job-radar/.venv/bin/python digest.py >> /tmp/job-radar.log 2>&1
```

To verify it's saved:
```bash
crontab -l
```

To check logs:
```bash
tail -f /tmp/job-radar.log
```

**Option B: launchd (more macOS-native, survives sleep)**

Create `/Library/LaunchDaemons/com.job-radar.morning.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.job-radar.morning</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd /Users/YOUR_USERNAME/Desktop/job-radar && .venv/bin/python run.py && .venv/bin/python digest.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/job-radar-morning.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/job-radar-morning-error.log</string>
</dict>
</plist>
```

**Recommendation: use cron (Option A) for v1.** It's simpler and enough for a one-user tool.

---

## Step 4 — Verify the full loop end-to-end

1. Make sure `server.py` is running and ngrok is running
2. Update `PUBLIC_BASE_URL` in `.env` with the ngrok URL
3. Run the digest manually:
   ```bash
   python digest.py
   ```
4. Check Slack — you should see role-grouped messages with buttons
5. Click a 👍 button — your browser should open a page saying "Saved to dashboard"
6. Check the DB:
   ```bash
   python -c "
   import sqlite3
   conn = sqlite3.connect('jobs.db')
   rows = conn.execute(\"SELECT title, user_reaction, status FROM jobs WHERE user_reaction IS NOT NULL LIMIT 5\").fetchall()
   for r in rows: print(r)
   "
   ```
   Expected: rows with `user_reaction = 'good'` and `status = 'saved'`

---

## Step 5 — Run `digest.py --dry-run` first, always

Before sending real Slack messages on a new scrape, always sanity-check:
```bash
python digest.py --dry-run
```
This prints everything that would be sent without actually posting. Catch garbage data here before it hits Slack.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Slack buttons 404 | ngrok URL changed — update PUBLIC_BASE_URL in .env |
| No jobs in digest | All jobs already have `digest_sent_at` set — run scraper first (`python run.py`) |
| `slack_sdk` not found | `pip install slack-sdk` in your venv |
| Buttons open but don't update DB | `server.py` isn't running — start it first |
| cron job not running | Use full absolute paths to python and the project directory |
