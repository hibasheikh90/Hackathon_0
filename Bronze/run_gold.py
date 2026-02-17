"""
Gold Tier — Single Entry Point
================================
Validates configuration, wires up all subsystems, and runs the
Gold scheduler.

Usage:
    python run_gold.py --once              # single pass
    python run_gold.py --daemon            # continuous (every 5 min)
    python run_gold.py --daemon -i 10      # continuous (every 10 min)
    python run_gold.py --validate          # validate only, don't run
    python run_gold.py --briefing          # generate CEO briefing now
    python run_gold.py --ralph             # run Ralph Wiggum autonomous loop
    python run_gold.py --ralph --cycles 20 # Ralph with custom cycle limit
    python run_gold.py --test              # run end-to-end tests
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def cmd_validate() -> int:
    """Run config validation and print report."""
    from core.validator import validate_all, print_report
    results = validate_all()
    _, failed, _ = print_report(results)
    return 1 if failed > 0 else 0


def cmd_briefing() -> int:
    """Generate the weekly CEO briefing now."""
    from briefings.weekly_ceo import generate_briefing
    path = generate_briefing()
    return 0 if path else 1


def cmd_ralph(cycles: int, daemon: bool, interval: int) -> int:
    """Run the Ralph Wiggum autonomous task loop."""
    from core.ralph import ralph
    if daemon:
        ralph.run_daemon(interval_minutes=interval, max_cycles_per_run=cycles)
    else:
        ralph.run(max_cycles=cycles)
    return 0


def cmd_test() -> int:
    """Run the end-to-end test suite."""
    import unittest
    loader = unittest.TestLoader()
    suite = loader.discover(str(PROJECT_ROOT / "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def cmd_scheduler(once: bool, interval: int) -> int:
    """Run the Gold scheduler."""
    # Quick validation first
    from core.validator import validate_all
    results = validate_all()
    all_modules = results.get("Gold Tier Modules", [])
    failed_modules = [c for c in all_modules if not c.ok and c.required]
    if failed_modules:
        print("\n[ERROR] Some required modules failed to import:")
        for c in failed_modules:
            print(f"  {c.name}: {c.detail}")
        print("\nFix these issues before running the scheduler.")
        return 1

    # Build argv for the scheduler
    sys.argv = ["core.scheduler"]
    if once:
        sys.argv.append("--once")
    else:
        sys.argv.append("--daemon")
        sys.argv.extend(["-i", str(interval)])

    from core.scheduler import main
    main()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gold Tier AI Employee — Single Entry Point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  python run_gold.py --validate          Check configuration
  python run_gold.py --test              Run test suite
  python run_gold.py --briefing          Generate CEO briefing now
  python run_gold.py --ralph             Run Ralph Wiggum autonomous loop
  python run_gold.py --ralph --cycles 20 Ralph with 20 max cycles
  python run_gold.py --once              Run one scheduler cycle
  python run_gold.py --daemon            Run continuously (Ctrl+C to stop)
  python run_gold.py --daemon -i 10      Run every 10 minutes
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate", action="store_true", help="Validate config and dependencies")
    group.add_argument("--test", action="store_true", help="Run end-to-end tests")
    group.add_argument("--briefing", action="store_true", help="Generate CEO briefing now")
    group.add_argument("--ralph", action="store_true", help="Run Ralph Wiggum autonomous task loop")
    group.add_argument("--once", action="store_true", help="Run one scheduler cycle")
    group.add_argument("--daemon", action="store_true", help="Run scheduler continuously")

    parser.add_argument("-i", "--interval", type=int, default=5,
                        help="Minutes between cycles (default: 5)")
    parser.add_argument("--cycles", type=int, default=10,
                        help="Max cycles for Ralph loop (default: 10)")

    args = parser.parse_args()

    if args.validate:
        sys.exit(cmd_validate())
    elif args.test:
        sys.exit(cmd_test())
    elif args.briefing:
        sys.exit(cmd_briefing())
    elif args.ralph:
        sys.exit(cmd_ralph(
            cycles=args.cycles,
            daemon=args.daemon if hasattr(args, 'daemon') else False,
            interval=args.interval,
        ))
    else:
        sys.exit(cmd_scheduler(once=args.once, interval=args.interval))


if __name__ == "__main__":
    main()
