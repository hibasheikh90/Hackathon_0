# AI Employee Scheduler -- Setup Guide

## Quick Start

```bash
# Single pass (process inbox now and exit)
python scripts/run_ai_employee.py --once

# Daemon mode (loop every 5 minutes)
python scripts/run_ai_employee.py --daemon

# Daemon with custom interval (10 minutes)
python scripts/run_ai_employee.py --daemon --interval 10
```

---

## Windows Task Scheduler (Recommended for Windows)

### Automatic Setup

Run the included batch script as Administrator:

```
scripts\setup_task_scheduler.bat
```

### Manual Setup

1. Open **Task Scheduler** (search "Task Scheduler" in Start Menu)

2. Click **Create Task** (not "Create Basic Task")

3. **General Tab:**
   - Name: `AI Employee Scheduler`
   - Description: `Runs the AI Employee pipeline every 5 minutes`
   - Check: `Run whether user is logged on or not`
   - Check: `Run with highest privileges`

4. **Triggers Tab:**
   - Click **New...**
   - Begin the task: `On a schedule`
   - Settings: `Daily`, Start: `00:00:00`
   - Check: `Repeat task every: 5 minutes`
   - For a duration of: `Indefinitely`
   - Check: `Enabled`
   - Click **OK**

5. **Actions Tab:**
   - Click **New...**
   - Action: `Start a program`
   - Program/script: `python`
   - Add arguments: `scripts/run_ai_employee.py --once`
   - Start in: `G:\Desktop\Hackathon_0\Bronze`
   - Click **OK**

6. **Conditions Tab:**
   - Uncheck: `Start the task only if the computer is on AC power`

7. **Settings Tab:**
   - Check: `Allow task to be run on demand`
   - Check: `If the running task does not end when requested, force it to stop`
   - Check: `If the task is already running: Do not start a new instance`

8. Click **OK** and enter your Windows password when prompted.

### Verify

```powershell
# Check the task exists
schtasks /query /tn "AI Employee Scheduler" /fo LIST

# Run it manually
schtasks /run /tn "AI Employee Scheduler"

# Check the log
type scripts\scheduler.log
```

### Remove

```powershell
schtasks /delete /tn "AI Employee Scheduler" /f
```

---

## Linux / macOS Cron

### Setup

```bash
# Open crontab editor
crontab -e

# Add this line (runs every 5 minutes):
*/5 * * * * cd /path/to/Bronze && python3 scripts/run_ai_employee.py --once >> scripts/scheduler.log 2>&1
```

Replace `/path/to/Bronze` with your actual project path.

### Using Full Python Path

If `python3` is not in cron's PATH:

```bash
# Find your Python path
which python3

# Use the full path in crontab
*/5 * * * * cd /path/to/Bronze && /usr/bin/python3 scripts/run_ai_employee.py --once >> scripts/scheduler.log 2>&1
```

### Verify

```bash
# List active cron jobs
crontab -l

# Watch the log in real time
tail -f scripts/scheduler.log
```

### Remove

```bash
crontab -e
# Delete the AI Employee line, save and exit
```

---

## macOS launchd (Alternative)

Create `~/Library/LaunchAgents/com.ai-employee.scheduler.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ai-employee.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>scripts/run_ai_employee.py</string>
        <string>--once</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/Bronze</string>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>/path/to/Bronze/scripts/scheduler.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/Bronze/scripts/scheduler.log</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.ai-employee.scheduler.plist
```

---

## Files Created by the Scheduler

| File | Purpose |
|------|---------|
| `scripts/scheduler.log` | Full activity log (append-only) |
| `scripts/.scheduler_state.json` | Tracks processed files to prevent duplicates |
| `scripts/.scheduler.lock` | Prevents overlapping runs |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Another scheduler instance is already running" | Delete `scripts/.scheduler.lock` -- the previous run likely crashed |
| Tasks not being processed | Check `scripts/scheduler.log` for errors |
| Duplicate plans being created | The state file tracks mtimes -- only modified files get reprocessed |
| Python not found by Task Scheduler | Use the full Python path: `C:\Python314\python.exe` |
| Cron job not running | Check `crontab -l`, verify Python path, check system logs with `grep CRON /var/log/syslog` |
