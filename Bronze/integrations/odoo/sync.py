"""
Gold Tier — Vault <-> Odoo Bidirectional Sync
===============================================
Watches vault/Needs_Action/ for files tagged #accounting and pushes
relevant data to Odoo.  Pulls Odoo alerts (overdue invoices) into
vault/Inbox/ so the triage pipeline handles them.

Usage:
    from integrations.odoo.sync import OdooSync

    sync = OdooSync()
    sync.run_sync()          # called by Gold scheduler every 5 min
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.event_bus import bus
from core.error_logger import logger as error_logger
from integrations.odoo.client import OdooClient, OdooConnectionError
from integrations.odoo.invoices import InvoiceManager

# Vault paths
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
INBOX_DIR = VAULT_DIR / "Inbox"
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"

# Tag that marks a vault file as accounting-related
ACCOUNTING_TAG = "#accounting"

# State file to track which Odoo alerts we've already pushed to vault
_SYNC_STATE = _PROJECT_ROOT / "core" / ".odoo_sync_state"


class OdooSync:
    """Bidirectional sync between Obsidian vault and Odoo."""

    def __init__(self, client: OdooClient | None = None) -> None:
        self.client = client or OdooClient()
        self.invoices = InvoiceManager(self.client)
        self._synced_alerts: set[str] = self._load_synced()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run_sync(self) -> dict:
        """Full sync cycle. Returns stats dict."""
        stats = {"pushed": 0, "pulled": 0, "errors": 0}

        try:
            self.client.authenticate()
        except OdooConnectionError as e:
            error_logger.log_error("odoo.sync", e, {"phase": "connect"})
            stats["errors"] += 1
            return stats

        # Push: vault -> Odoo
        pushed = self._push_vault_to_odoo()
        stats["pushed"] = pushed

        # Pull: Odoo -> vault
        pulled = self._pull_odoo_to_vault()
        stats["pulled"] = pulled

        self._save_synced()

        bus.emit("odoo.sync.complete", stats)
        error_logger.log_audit("odoo.sync", "complete", stats)

        return stats

    # ------------------------------------------------------------------
    # Push: vault -> Odoo
    # ------------------------------------------------------------------

    def _push_vault_to_odoo(self) -> int:
        """Scan Needs_Action/ for #accounting files and push to Odoo."""
        count = 0
        if not NEEDS_ACTION_DIR.is_dir():
            return count

        for md_file in NEEDS_ACTION_DIR.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
            except OSError:
                continue

            if ACCOUNTING_TAG not in content.lower():
                continue

            # Check if this file has already been synced (simple marker)
            if "<!-- odoo-synced -->" in content:
                continue

            # Try to extract invoice data from the file
            invoice_data = self._parse_invoice_from_vault(content)
            if invoice_data:
                try:
                    invoice_id = self.invoices.create_invoice(
                        partner_name=invoice_data["partner"],
                        lines=invoice_data["lines"],
                        due_date=invoice_data.get("due_date"),
                    )
                    # Mark file as synced
                    md_file.write_text(
                        content + f"\n<!-- odoo-synced invoice_id={invoice_id} -->\n",
                        encoding="utf-8",
                    )
                    count += 1
                except Exception as e:
                    error_logger.log_error("odoo.sync.push", e, {
                        "file": md_file.name,
                    })

        return count

    def _parse_invoice_from_vault(self, content: str) -> dict | None:
        """Extract invoice fields from a vault markdown file.

        Expected format in the file:
            Partner: Company Name
            Due: 2026-03-01
            - Item description | qty | price
        """
        partner_match = re.search(r"(?:partner|client|customer):\s*(.+)", content, re.IGNORECASE)
        if not partner_match:
            return None

        partner = partner_match.group(1).strip()

        due_match = re.search(r"(?:due|due_date|deadline):\s*(\d{4}-\d{2}-\d{2})", content, re.IGNORECASE)
        due_date = due_match.group(1) if due_match else None

        # Parse line items: "- description | quantity | price"
        lines = []
        for match in re.finditer(r"^-\s+(.+?)\s*\|\s*(\d+(?:\.\d+)?)\s*\|\s*(\d+(?:\.\d+)?)", content, re.MULTILINE):
            lines.append({
                "product": match.group(1).strip(),
                "quantity": float(match.group(2)),
                "price": float(match.group(3)),
            })

        if not lines:
            return None

        return {"partner": partner, "lines": lines, "due_date": due_date}

    # ------------------------------------------------------------------
    # Pull: Odoo -> vault
    # ------------------------------------------------------------------

    def _pull_odoo_to_vault(self) -> int:
        """Check for overdue invoices in Odoo, create vault/Inbox/ alerts."""
        count = 0
        INBOX_DIR.mkdir(parents=True, exist_ok=True)

        try:
            overdue = self.invoices.list_overdue(days_overdue=0)
        except Exception as e:
            error_logger.log_error("odoo.sync.pull", e)
            return 0

        for inv in overdue:
            inv_name = inv.get("name", "unknown")
            alert_key = f"overdue_{inv_name}"

            if alert_key in self._synced_alerts:
                continue

            partner = inv.get("partner_id", [None, "Unknown"])
            partner_name = partner[1] if isinstance(partner, (list, tuple)) else str(partner)
            amount = inv.get("amount_residual", 0)
            due_date = inv.get("invoice_date_due", "unknown")

            # Create vault inbox file
            safe_name = re.sub(r"[^\w\-]", "_", inv_name)
            alert_file = INBOX_DIR / f"odoo_overdue_{safe_name}.md"

            if alert_file.exists():
                self._synced_alerts.add(alert_key)
                continue

            content = f"""# Overdue Invoice: {inv_name}

**Source:** Odoo ERP (auto-sync)
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Details
- **Invoice:** {inv_name}
- **Customer:** {partner_name}
- **Amount Outstanding:** ${amount:,.2f}
- **Due Date:** {due_date}
- **Status:** Payment overdue

## Action Required
Review this overdue invoice and decide on next steps:
1. Send payment reminder to {partner_name}
2. Escalate to collections
3. Negotiate payment plan

#accounting #urgent
"""
            try:
                alert_file.write_text(content, encoding="utf-8")
                self._synced_alerts.add(alert_key)
                count += 1
                bus.emit("odoo.invoice.overdue", {
                    "invoice": inv_name,
                    "partner": partner_name,
                    "amount": amount,
                })
            except OSError as e:
                error_logger.log_error("odoo.sync.pull.write", e, {
                    "invoice": inv_name,
                })

        return count

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _load_synced(self) -> set[str]:
        if _SYNC_STATE.is_file():
            try:
                return set(_SYNC_STATE.read_text(encoding="utf-8").strip().splitlines())
            except OSError:
                pass
        return set()

    def _save_synced(self) -> None:
        try:
            _SYNC_STATE.write_text("\n".join(sorted(self._synced_alerts)), encoding="utf-8")
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Module-level function for scheduler import
# ---------------------------------------------------------------------------
def run_sync() -> dict:
    """Entry point called by core/scheduler.py."""
    sync = OdooSync()
    return sync.run_sync()
