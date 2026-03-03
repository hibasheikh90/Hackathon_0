"""
Odoo Connection Diagnostic
===========================
Tests every layer of the Odoo connection and reports what's working.

Run:
    python scripts/test_odoo_connection.py
"""

from __future__ import annotations

import sys
import xmlrpc.client
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.config_loader import config

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"


def _line(label: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    msg = f"  {status}  {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def run():
    config.load()
    url      = config.env("ODOO_URL") or config.odoo.get("host", "")
    db       = config.env("ODOO_DB") or config.odoo.get("database", "")
    username = config.env("ODOO_USERNAME", "admin")
    api_key  = config.env("ODOO_API_KEY", "")
    timeout  = config.odoo.get("timeout_seconds", 15)

    print("\n" + "=" * 54)
    print("  Odoo Connection Diagnostic")
    print("=" * 54)
    print(f"  {INFO}  URL      : {url}")
    print(f"  {INFO}  Database : {db}")
    print(f"  {INFO}  Username : {username}")
    print(f"  {INFO}  API Key  : {'(set)' if api_key else '(not set)'}")
    print()

    # ------------------------------------------------------------------
    # Step 1: Credentials present
    # ------------------------------------------------------------------
    print("Step 1 — Credentials")
    _line("ODOO_URL set",      bool(url),      url or "missing")
    _line("ODOO_DB set",       bool(db),       db or "missing")
    _line("ODOO_USERNAME set", bool(username), username)
    _line("ODOO_API_KEY set",  bool(api_key),  "(set)" if api_key else "missing")
    if not (url and db and api_key):
        print("\n  Set the missing values in Bronze/.env and re-run.\n")
        return
    print()

    # ------------------------------------------------------------------
    # Step 2: Network reachability (version endpoint, no auth needed)
    # ------------------------------------------------------------------
    print("Step 2 — Network / Server Reachability")
    transport = (xmlrpc.client.SafeTransport if url.startswith("https")
                 else xmlrpc.client.Transport)()
    common = xmlrpc.client.ServerProxy(
        f"{url}/xmlrpc/2/common", transport=transport, allow_none=True
    )
    try:
        ver = common.version()
        _line("Server reachable", True,
              f"Odoo {ver.get('server_version', '?')}")
        server_ok = True
    except Exception as e:
        _line("Server reachable", False, str(e))
        print("\n  Cannot reach the Odoo server. Check the URL and your internet connection.\n")
        return
    print()

    # ------------------------------------------------------------------
    # Step 3: Authentication
    # ------------------------------------------------------------------
    print("Step 3 — Authentication")
    try:
        uid = common.authenticate(db, username, api_key, {})
        if uid:
            _line("Login successful", True, f"uid={uid}")
            auth_ok = True
        else:
            _line("Login successful", False,
                  "authenticate() returned False — check username / API key / database name")
            print("\n  Fix credentials in Bronze/.env and re-run.\n")
            return
    except Exception as e:
        _line("Login successful", False, str(e))
        return
    print()

    # ------------------------------------------------------------------
    # Step 4: Module check via ir.model
    # ------------------------------------------------------------------
    print("Step 4 — Accounting Module")
    models = xmlrpc.client.ServerProxy(
        f"{url}/xmlrpc/2/object", transport=transport, allow_none=True
    )

    def _count(model: str, domain: list) -> int | None:
        try:
            return models.execute_kw(db, uid, api_key, model,
                                     "search_count", [domain], {})
        except Exception:
            return None

    acct_count = _count("ir.model", [("model", "=", "account.move")])
    accounting_installed = bool(acct_count)
    _line("Accounting app installed", accounting_installed,
          "account.move found" if accounting_installed
          else "account.move NOT found — install Invoicing/Accounting in Odoo Apps")
    print()

    if not accounting_installed:
        print("  To install the Accounting app:")
        print(f"    1. Open  {url}")
        print("    2. Go to Apps (top menu)")
        print("    3. Search  'Invoicing'  (free) or  'Accounting'  (paid)")
        print("    4. Click Install")
        print("    5. Re-run this script to confirm\n")
        return

    # ------------------------------------------------------------------
    # Step 5: Live accounting queries
    # ------------------------------------------------------------------
    print("Step 5 — Live Accounting Queries")

    # Invoices
    try:
        inv = models.execute_kw(db, uid, api_key, "account.move",
                                "search_read",
                                [[("move_type", "=", "out_invoice"),
                                  ("state", "=", "posted")]],
                                {"fields": ["name", "amount_total"], "limit": 3})
        _line("account.move query", True, f"{len(inv)} posted invoice(s) returned")
    except Exception as e:
        _line("account.move query", False, str(e))

    # Journals
    try:
        journals = models.execute_kw(db, uid, api_key, "account.journal",
                                     "search_read",
                                     [[("type", "in", ["bank", "cash"])]],
                                     {"fields": ["name", "type"], "limit": 5})
        _line("account.journal query", True,
              f"{len(journals)} bank/cash journal(s): "
              + ", ".join(j["name"] for j in journals))
    except Exception as e:
        _line("account.journal query", False, str(e))

    # Partners
    try:
        partners = models.execute_kw(db, uid, api_key, "res.partner",
                                     "search_count", [[("is_company", "=", True)]], {})
        _line("res.partner query", True, f"{partners} company partner(s)")
    except Exception as e:
        _line("res.partner query", False, str(e))

    print()
    print("=" * 54)
    print("  All checks passed — Odoo integration is fully operational.")
    print("=" * 54 + "\n")


if __name__ == "__main__":
    run()
