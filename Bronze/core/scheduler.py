"""
Gold Tier — Master Scheduler
=============================
Orchestrates every Gold Tier subsystem on configurable intervals.

Schedules:
    Every 5 min   — Vault inbox scan (triage + plan)
    Every 5 min   — Social content queue check
    Every 5 min   — Odoo sync
    Every 1 hour  — Log rotation check
    Every day 18:00  — Daily report
    Every Monday 08:00 — Weekly CEO briefing

Modes:
    --once     Single pass of all "every 5 min" jobs, then exit
    --daemon   Continuous loop with all schedules active

Usage:
    python -m core.scheduler --once
    python -m core.scheduler --daemon
    python -m core.scheduler --daemon --interval 5
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve paths before any imports that depend on them
# ---------------------------------------------------------------------------
_CORE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _CORE_DIR.parent

# Add project root to sys.path so all Gold modules are importable
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.event_bus import bus
from core.error_logger import logger as error_logger
from core.config_loader import config
from core.recovery import recovery_manager

# ---------------------------------------------------------------------------
# Wire up event bus <-> error logger
# ---------------------------------------------------------------------------
bus.set_error_logger(error_logger)
error_logger.set_event_bus(bus)


# ---------------------------------------------------------------------------
# Alert escalation: send email when error threshold exceeded
# ---------------------------------------------------------------------------
def _on_error_alert(data: dict) -> None:
    """Handle error.alert_triggered events by sending an alert email."""
    try:
        from integrations.gmail.sender import GmailSender
        sender = GmailSender()
        if sender.is_configured():
            source = data.get("source", "unknown")
            count = data.get("error_count", 0)
            window = data.get("window_seconds", 3600)
            sender.send_alert(
                subject=f"Error spike: {source} ({count} errors in {window // 60}min)",
                body=(
                    f"The AI Employee error logger detected {count} errors "
                    f"from '{source}' within the last {window // 60} minutes.\n\n"
                    f"Timestamp: {data.get('ts', 'unknown')}\n\n"
                    f"Please check logs/error.log for details."
                ),
            )
    except Exception:
        pass  # Don't let alert sending crash the scheduler


bus.on("error.alert_triggered", _on_error_alert)

# ---------------------------------------------------------------------------
# Vault paths (same logic as Silver — supports both vault locations)
# ---------------------------------------------------------------------------
_ai_vault = PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
INBOX_DIR = VAULT_DIR / "Inbox"
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
DONE_DIR = VAULT_DIR / "Done"

STATE_FILE = PROJECT_ROOT / "core" / ".gold_scheduler_state.json"
LOCK_FILE = PROJECT_ROOT / "core" / ".gold_scheduler.lock"

# ---------------------------------------------------------------------------
# Logging — dual output: file + console
# ---------------------------------------------------------------------------
def _setup_logging() -> logging.Logger:
    log = logging.getLogger("gold_scheduler")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    log.addHandler(ch)

    log_file = PROJECT_ROOT / "logs" / "scheduler.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    return log


log = _setup_logging()


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------
def _load_state() -> dict:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log.warning("Corrupt Gold state file, starting fresh")
    return {
        "processed": {},
        "cycle_count": 0,
        "last_run": None,
        "last_daily_report": None,
        "last_weekly_briefing": None,
    }


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Lock file
# ---------------------------------------------------------------------------
def _acquire_lock() -> bool:
    if LOCK_FILE.is_file():
        try:
            data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            pid = data.get("pid", 0)
            try:
                os.kill(pid, 0)
                return False
            except (OSError, ProcessLookupError):
                log.warning("Stale lock from PID %d, overriding", pid)
        except (json.JSONDecodeError, OSError):
            log.warning("Corrupt lock file, overriding")

    LOCK_FILE.write_text(
        json.dumps({"pid": os.getpid(), "started": datetime.now().isoformat()}),
        encoding="utf-8",
    )
    return True


def _release_lock() -> None:
    if LOCK_FILE.is_file():
        LOCK_FILE.unlink()


# ===================================================================
# JOB: Vault scan (triage + plan) — reuses Silver pipeline logic
# ===================================================================
def _job_vault_scan(state: dict) -> dict:
    """Scan vault/Inbox/ for new .md files, triage and plan them.

    This imports the Silver scheduler's core functions to avoid duplication.
    """
    stats = {"scanned": 0, "triaged": 0, "planned": 0, "skipped": 0, "errors": 0}

    for d in (INBOX_DIR, NEEDS_ACTION_DIR, DONE_DIR):
        d.mkdir(parents=True, exist_ok=True)

    inbox_files = sorted(INBOX_DIR.glob("*.md"))
    stats["scanned"] = len(inbox_files)

    if not inbox_files:
        return stats

    # Try to import Silver's pipeline functions
    silver_scheduler = PROJECT_ROOT / "scripts" / "run_ai_employee.py"
    if silver_scheduler.is_file():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "silver_scheduler", str(silver_scheduler)
            )
            silver = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(silver)

            for fpath in inbox_files:
                fname = fpath.name
                file_mtime = fpath.stat().st_mtime
                prev = state["processed"].get(fname)
                if prev and prev.get("mtime") == file_mtime:
                    stats["skipped"] += 1
                    continue

                log.info("  [PROCESSING] %s", fname)

                try:
                    triage_out, triage_status = silver.triage_file(fpath)
                    if triage_out:
                        stats["triaged"] += 1
                        bus.emit("vault.task.triaged", {
                            "file": fname, "status": triage_status,
                        })
                except Exception as e:
                    error_logger.log_error("vault.triage", e, {"file": fname})
                    stats["errors"] += 1

                try:
                    plan_path = silver.create_plan(fpath)
                    if plan_path:
                        stats["planned"] += 1
                except Exception as e:
                    error_logger.log_error("vault.plan", e, {"file": fname})
                    stats["errors"] += 1

                state["processed"][fname] = {
                    "mtime": file_mtime,
                    "processed_at": datetime.now().isoformat(),
                }

                bus.emit("vault.task.new", {"file": fname})
                error_logger.log_audit("vault.scan", "processed", {"file": fname})

            return stats
        except Exception as e:
            error_logger.log_error("vault.import_silver", e)
            log.warning("Could not import Silver scheduler: %s", e)

    log.info("Silver scheduler not available — vault scan skipped")
    return stats


# ===================================================================
# JOB: Gmail inbox check (Phase 2)
# ===================================================================
def _job_gmail_check(state: dict) -> None:
    """Check Gmail for new emails and route them to vault/Inbox/."""
    try:
        from integrations.gmail.watcher import GmailWatcher
        watcher = GmailWatcher()
        if watcher.is_configured():
            count = watcher.check_new()
            if count > 0:
                log.info("  Gmail: imported %d new email(s)", count)
    except ImportError:
        pass
    except Exception as e:
        error_logger.log_error("gmail.watcher", e)


# ===================================================================
# JOB: Social content queue check (Phase 2)
# ===================================================================
def _job_social_check(state: dict) -> None:
    """Check social content queue for posts ready to publish."""
    try:
        from integrations.social.content_queue import process_queue
        from integrations.social.scheduler import SocialScheduler

        sched = SocialScheduler()
        posted = process_queue()
        if posted > 0:
            log.info("  Social: published %d post(s)", posted)
    except ImportError:
        pass
    except Exception as e:
        error_logger.log_error("social.queue_check", e)


# ===================================================================
# JOB: Odoo sync (Phase 2)
# ===================================================================
def _job_odoo_sync(state: dict) -> None:
    """Run Odoo bidirectional sync."""
    try:
        from integrations.odoo.sync import run_sync
        stats = run_sync()
        if stats.get("pushed", 0) > 0 or stats.get("pulled", 0) > 0:
            log.info("  Odoo: pushed=%d pulled=%d", stats["pushed"], stats["pulled"])
    except ImportError:
        pass
    except Exception as e:
        error_logger.log_error("odoo.sync", e)


# ===================================================================
# JOB: Ralph Wiggum — autonomous task processing
# ===================================================================
def _job_ralph(state: dict) -> None:
    """Run a single pass of the Ralph Wiggum autonomous loop."""
    try:
        from core.ralph import ralph
        stats = ralph.run_once()
        completed = stats.get("completed", 0)
        processed = stats.get("processed", 0)
        if completed > 0 or processed > 0:
            log.info(
                "  Ralph: processed=%d completed=%d blocked=%d remaining=%d",
                processed, completed, stats.get("blocked", 0), stats.get("remaining", 0),
            )
    except Exception as e:
        error_logger.log_error("ralph.scheduler_job", e)


# ===================================================================
# JOB: Recovery — retry failed tasks
# ===================================================================
def _job_recovery() -> dict[str, int]:
    """Run the recovery manager to retry failed tasks."""
    try:
        stats = recovery_manager.run_recovery()
        if stats["attempted"] > 0:
            log.info(
                "  Recovery: attempted=%d recovered=%d failed=%d skipped=%d",
                stats["attempted"], stats["recovered"],
                stats["failed"], stats["skipped"],
            )
        return stats
    except Exception as e:
        error_logger.log_error("recovery.job", e)
        return {"attempted": 0, "recovered": 0, "failed": 0, "skipped": 0}


# ===================================================================
# JOB: Log rotation
# ===================================================================
def _job_log_rotation() -> None:
    """Rotate logs if they exceed the configured max size."""
    archived = error_logger.rotate_if_needed()
    if archived:
        log.info("Rotated logs: %s", ", ".join(archived))
        error_logger.log_audit("system.log_rotation", "success", {"archived": archived})


# ===================================================================
# JOB: Daily report
# ===================================================================
def _job_daily_report(state: dict) -> None:
    """Generate the daily report (Silver skill)."""
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get("last_daily_report") == today:
        return

    report_script = (
        PROJECT_ROOT / "AI_Employee_Vault" / ".claude" / "skills"
        / "daily-report" / "scripts" / "generate_report.py"
    )
    if not report_script.is_file():
        log.info("Daily report skill not found, skipping")
        return

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("generate_report", str(report_script))
        mod = importlib.util.module_from_spec(spec)
        old_argv = sys.argv
        sys.argv = [str(report_script)]
        try:
            spec.loader.exec_module(mod)
            mod.main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv

        state["last_daily_report"] = today
        log.info("Daily report generated for %s", today)
        bus.emit("briefing.daily.generated", {"date": today})
        error_logger.log_audit("briefing.daily", "success", {"date": today})
    except Exception as e:
        error_logger.log_error("briefing.daily", e)


# ===================================================================
# JOB: Daily error summary
# ===================================================================
def _job_daily_error_summary(state: dict) -> None:
    """Generate the daily error summary report."""
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get("last_error_summary") == today:
        return

    try:
        from briefings.daily_error_summary import generate_error_summary
        path = generate_error_summary()
        if path:
            state["last_error_summary"] = today
            log.info("Daily error summary generated for %s", today)
    except Exception as e:
        error_logger.log_error("briefing.error_summary", e)


# ===================================================================
# JOB: Weekly CEO briefing (stub — Phase 3)
# ===================================================================
def _job_weekly_briefing(state: dict) -> None:
    """Generate the weekly CEO briefing."""
    now = datetime.now()
    week_key = now.strftime("%Y-W%W")
    if state.get("last_weekly_briefing") == week_key:
        return

    try:
        from briefings.weekly_ceo import generate_briefing
        generate_briefing()
        state["last_weekly_briefing"] = week_key
        log.info("Weekly CEO briefing generated for %s", week_key)
        bus.emit("briefing.generated", {"week": week_key})
        error_logger.log_audit("briefing.weekly", "success", {"week": week_key})
    except ImportError:
        pass  # Phase 3 not yet built
    except Exception as e:
        error_logger.log_error("briefing.weekly", e)


# ===================================================================
# Time-check helpers
# ===================================================================
def _is_time_for(target_time_str: str, last_check: datetime, now: datetime) -> bool:
    """Return True if *target_time_str* (HH:MM) falls between last_check and now."""
    try:
        hour, minute = map(int, target_time_str.split(":"))
    except (ValueError, AttributeError):
        return False

    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return last_check < target <= now


def _is_day_of_week(day_name: str) -> bool:
    """Return True if today matches *day_name* (e.g. 'monday')."""
    return datetime.now().strftime("%A").lower() == day_name.lower()


# ===================================================================
# Core pipeline — one full cycle
# ===================================================================
def run_cycle(state: dict) -> dict:
    """Execute one full Gold Tier pipeline cycle."""
    config.load()  # reload config on each cycle

    log.info("--- Gmail check ---")
    _job_gmail_check(state)

    log.info("--- Vault scan ---")
    stats = _job_vault_scan(state)
    log.info(
        "Vault: scanned=%d triaged=%d planned=%d skipped=%d errors=%d",
        stats["scanned"], stats["triaged"], stats["planned"],
        stats["skipped"], stats["errors"],
    )

    log.info("--- Social queue check ---")
    _job_social_check(state)

    log.info("--- Odoo sync ---")
    _job_odoo_sync(state)

    log.info("--- Ralph Wiggum (autonomous task loop) ---")
    _job_ralph(state)

    log.info("--- Recovery (retry failed tasks) ---")
    _job_recovery()

    log.info("--- Log rotation check ---")
    _job_log_rotation()

    # Time-based jobs
    scheduler_cfg = config.scheduler
    now = datetime.now()
    last_run_str = state.get("last_run")
    last_check = (
        datetime.fromisoformat(last_run_str) if last_run_str else
        now.replace(hour=0, minute=0, second=0)
    )

    # Daily report + error summary
    daily_time = scheduler_cfg.get("daily_report_time", "18:00")
    if _is_time_for(daily_time, last_check, now):
        log.info("--- Daily report (scheduled at %s) ---", daily_time)
        _job_daily_report(state)
        log.info("--- Daily error summary ---")
        _job_daily_error_summary(state)

    # Weekly briefing
    briefing_day = scheduler_cfg.get("weekly_briefing_day", "monday")
    briefing_time = scheduler_cfg.get("weekly_briefing_time", "08:00")
    if _is_day_of_week(briefing_day) and _is_time_for(briefing_time, last_check, now):
        log.info("--- Weekly CEO briefing (scheduled %s %s) ---", briefing_day, briefing_time)
        _job_weekly_briefing(state)

    return stats


# ===================================================================
# Main
# ===================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gold Tier Scheduler — orchestrates all AI Employee subsystems.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Run one cycle and exit")
    mode.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument(
        "-i", "--interval", type=int, default=5,
        help="Minutes between cycles in daemon mode (default: 5)",
    )

    args = parser.parse_args()

    # Load config
    config.load()

    # Banner
    log.info("=" * 60)
    log.info("  Gold Tier Scheduler — Personal AI Employee")
    log.info("  Vault:    %s", VAULT_DIR)
    log.info("  Mode:     %s", "daemon" if args.daemon else "once")
    if args.daemon:
        interval = args.interval or config.get("scheduler.vault_scan_interval_min", 5)
        log.info("  Interval: %d minute(s)", interval)
    log.info("  Config:   %s", config)
    log.info("=" * 60)

    if not _acquire_lock():
        log.error("Another Gold scheduler is already running. Exiting.")
        sys.exit(1)

    state = _load_state()

    try:
        if args.once:
            state["cycle_count"] = state.get("cycle_count", 0) + 1
            state["last_run"] = datetime.now().isoformat()
            run_cycle(state)
            _save_state(state)
            log.info("Single cycle complete.")

        elif args.daemon:
            interval = args.interval or config.get("scheduler.vault_scan_interval_min", 5)
            log.info("Daemon started. Ctrl+C to stop.\n")

            while True:
                state["cycle_count"] = state.get("cycle_count", 0) + 1
                state["last_run"] = datetime.now().isoformat()
                cycle_num = state["cycle_count"]

                log.info("====== Cycle #%d ======", cycle_num)
                run_cycle(state)
                _save_state(state)

                log.info("Cycle #%d done. Next in %d min...\n", cycle_num, interval)
                time.sleep(interval * 60)

    except KeyboardInterrupt:
        log.info("\nShutdown requested.")
        _save_state(state)

    finally:
        _release_lock()
        log.info("Gold scheduler stopped.")


if __name__ == "__main__":
    main()
