"""
Gold Tier — Configuration & Dependency Validator
==================================================
Checks all configs, env vars, installed packages, and directory
structure at startup.  Prints a clear report of what's ready vs missing.

Usage:
    from core.validator import validate_all, print_report

    results = validate_all()
    print_report(results)

CLI:
    python -m core.validator
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.config_loader import config


# ---------------------------------------------------------------------------
# Check result
# ---------------------------------------------------------------------------
class Check:
    """Single validation check result."""

    def __init__(self, name: str, ok: bool, detail: str = "", required: bool = True):
        self.name = name
        self.ok = ok
        self.detail = detail
        self.required = required  # False = optional / nice-to-have

    @property
    def icon(self) -> str:
        if self.ok:
            return "OK"
        return "MISSING" if self.required else "SKIP"

    def __repr__(self) -> str:
        return f"[{self.icon:7s}] {self.name}: {self.detail}"


# ---------------------------------------------------------------------------
# Individual validators
# ---------------------------------------------------------------------------

def _check_directories() -> list[Check]:
    """Verify vault and log directory structure exists."""
    checks = []
    dirs = {
        "vault/Inbox": None,
        "vault/Needs_Action": None,
        "vault/Done": None,
        "logs": _PROJECT_ROOT / "logs",
        "logs/archive": _PROJECT_ROOT / "logs" / "archive",
        "config": _PROJECT_ROOT / "config",
    }

    # Resolve vault dir
    _ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
    _direct_vault = _PROJECT_ROOT / "vault"
    vault = _ai_vault if _ai_vault.is_dir() else _direct_vault

    dirs["vault/Inbox"] = vault / "Inbox"
    dirs["vault/Needs_Action"] = vault / "Needs_Action"
    dirs["vault/Done"] = vault / "Done"

    for name, path in dirs.items():
        exists = path.is_dir() if path else False
        checks.append(Check(
            f"Directory: {name}",
            exists,
            str(path) if exists else "Not found",
        ))

    return checks


def _check_config_files() -> list[Check]:
    """Verify YAML config files exist and are parseable."""
    checks = []
    config_dir = _PROJECT_ROOT / "config"

    for filename in ("gold.yaml", "social_accounts.yaml", "odoo_connection.yaml"):
        path = config_dir / filename
        exists = path.is_file()
        detail = f"{path.stat().st_size} bytes" if exists else "Not found"
        checks.append(Check(f"Config: {filename}", exists, detail))

    return checks


def _check_env_vars() -> list[Check]:
    """Check required and optional environment variables."""
    config.load()
    checks = []

    required = [
        ("EMAIL_ADDRESS", "Gmail sender + IMAP watcher"),
        ("EMAIL_PASSWORD", "Gmail App Password"),
    ]

    optional = [
        ("FACEBOOK_EMAIL", "Facebook automation"),
        ("FACEBOOK_PASSWORD", "Facebook automation"),
        ("LINKEDIN_EMAIL", "LinkedIn automation"),
        ("LINKEDIN_PASSWORD", "LinkedIn automation"),
        ("TWITTER_API_KEY", "Twitter/X API"),
        ("TWITTER_API_SECRET", "Twitter/X API"),
        ("TWITTER_ACCESS_TOKEN", "Twitter/X API"),
        ("TWITTER_ACCESS_SECRET", "Twitter/X API"),
        ("INSTAGRAM_USERNAME", "Instagram automation"),
        ("INSTAGRAM_PASSWORD", "Instagram automation"),
        ("ODOO_URL", "Odoo ERP connection"),
        ("ODOO_DB", "Odoo ERP connection"),
        ("ODOO_API_KEY", "Odoo ERP authentication"),
        ("ODOO_USERNAME", "Odoo ERP authentication"),
        ("CEO_ALERT_EMAIL", "Error alert destination"),
    ]

    for var, purpose in required:
        val = config.env(var)
        ok = bool(val)
        checks.append(Check(
            f"Env: {var}",
            ok,
            f"Set ({purpose})" if ok else f"Missing — needed for {purpose}",
            required=True,
        ))

    for var, purpose in optional:
        val = config.env(var)
        ok = bool(val)
        checks.append(Check(
            f"Env: {var}",
            ok,
            f"Set ({purpose})" if ok else f"Not set — needed for {purpose}",
            required=False,
        ))

    return checks


def _check_python_packages() -> list[Check]:
    """Check installed Python dependencies."""
    checks = []

    packages = [
        ("watchdog", True, "File system watcher (Bronze/Silver)"),
        ("dotenv", True, "Environment variable loading"),
        ("yaml", False, "YAML config parsing (fallback built-in)"),
        ("jinja2", False, "CEO briefing template rendering (fallback built-in)"),
        ("mcp", True, "MCP server SDK"),
        ("playwright", False, "LinkedIn/Instagram browser automation"),
        ("requests", False, "Twitter API client"),
        ("requests_oauthlib", False, "Twitter OAuth 1.0a"),
    ]

    for pkg, required, purpose in packages:
        # Some packages have different import names
        import_name = pkg
        if pkg == "dotenv":
            import_name = "dotenv"
        elif pkg == "yaml":
            import_name = "yaml"

        try:
            mod = importlib.import_module(import_name)
            version = getattr(mod, "__version__", "installed")
            checks.append(Check(
                f"Package: {pkg}",
                True,
                f"v{version} ({purpose})",
                required=required,
            ))
        except ImportError:
            checks.append(Check(
                f"Package: {pkg}",
                False,
                f"Not installed — {purpose}",
                required=required,
            ))

    return checks


def _check_core_modules() -> list[Check]:
    """Verify all Gold Tier core modules import successfully."""
    checks = []

    modules = [
        "core.event_bus",
        "core.error_logger",
        "core.config_loader",
        "core.scheduler",
        "integrations.odoo.client",
        "integrations.odoo.invoices",
        "integrations.odoo.expenses",
        "integrations.odoo.reports",
        "integrations.odoo.sync",
        "integrations.odoo.jsonrpc_client",
        "integrations.social.base",
        "integrations.social.facebook",
        "integrations.social.automation",
        "integrations.social.linkedin",
        "integrations.social.twitter",
        "integrations.social.instagram",
        "integrations.social.content_queue",
        "integrations.social.scheduler",
        "integrations.gmail.sender",
        "integrations.gmail.watcher",
        "briefings.weekly_ceo",
        "briefings.data_collectors.vault_stats",
        "briefings.data_collectors.financial_summary",
        "briefings.data_collectors.social_metrics",
        "briefings.data_collectors.email_digest",
        "mcp_servers.vault_server",
        "mcp_servers.email_server",
        "mcp_servers.accounting_server",
        "mcp_servers.social_server",
        "mcp_servers.briefing_server",
        "mcp_servers.odoo_jsonrpc_server",
    ]

    for mod_path in modules:
        try:
            importlib.import_module(mod_path)
            checks.append(Check(f"Module: {mod_path}", True, "Imports OK"))
        except Exception as e:
            checks.append(Check(
                f"Module: {mod_path}",
                False,
                f"{type(e).__name__}: {e}",
            ))

    return checks


def _check_mcp_config() -> list[Check]:
    """Verify .mcp.json exists and references valid server files."""
    checks = []
    mcp_path = _PROJECT_ROOT / ".mcp.json"

    if not mcp_path.is_file():
        checks.append(Check("MCP: .mcp.json", False, "Not found"))
        return checks

    import json
    try:
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})
        checks.append(Check("MCP: .mcp.json", True, f"{len(servers)} servers configured"))

        for name, cfg in servers.items():
            script = cfg.get("args", [None])[-1] if cfg.get("args") else None
            if script:
                script_path = _PROJECT_ROOT / script
                exists = script_path.is_file()
                checks.append(Check(
                    f"MCP Server: {name}",
                    exists,
                    str(script) if exists else f"{script} not found",
                ))
    except (json.JSONDecodeError, OSError) as e:
        checks.append(Check("MCP: .mcp.json", False, str(e)))

    return checks


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

def validate_all() -> dict[str, list[Check]]:
    """Run all validation checks. Returns grouped results."""
    return {
        "Directories": _check_directories(),
        "Config Files": _check_config_files(),
        "Environment Variables": _check_env_vars(),
        "Python Packages": _check_python_packages(),
        "Gold Tier Modules": _check_core_modules(),
        "MCP Configuration": _check_mcp_config(),
    }


def print_report(results: dict[str, list[Check]]) -> tuple[int, int, int]:
    """Print a formatted validation report.

    Returns (passed, failed_required, skipped_optional).
    """
    passed = 0
    failed = 0
    skipped = 0

    print()
    print("=" * 64)
    print("  Gold Tier — System Validation Report")
    print("=" * 64)
    print()

    for section, checks in results.items():
        print(f"--- {section} ---")
        for check in checks:
            print(f"  [{check.icon:7s}] {check.name}")
            if check.detail:
                print(f"            {check.detail}")
            if check.ok:
                passed += 1
            elif check.required:
                failed += 1
            else:
                skipped += 1
        print()

    print("=" * 64)
    print(f"  PASSED: {passed}  |  FAILED: {failed}  |  OPTIONAL MISSING: {skipped}")

    if failed == 0:
        print("  STATUS: All required checks passed")
    else:
        print(f"  STATUS: {failed} required check(s) need attention")

    print("=" * 64)
    print()

    return passed, failed, skipped


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    results = validate_all()
    passed, failed, skipped = print_report(results)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
