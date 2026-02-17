"""
Gold Tier — Odoo JSON-RPC MCP Server
=======================================
Connects the AI Employee to Odoo ERP via JSON-RPC and saves
accounting logs into the Obsidian vault.

Tools (10):
    create_invoice         — Create a draft customer invoice
    get_invoice            — Read a single invoice by ID
    list_unpaid_invoices   — List unpaid customer invoices
    list_overdue_invoices  — List invoices past due date
    read_transactions      — Read journal entries / transactions
    get_customer           — Get a customer by name or ID
    list_customers         — Search / list customers
    get_account_balance    — Bank + cash balances
    log_to_vault           — Save any accounting note to Obsidian vault
    sync_overdue_to_vault  — Pull overdue invoices into vault/Inbox

Vault logging:
    Every mutating tool (create_invoice, sync_overdue_to_vault) automatically
    writes a Markdown log into vault/Done/accounting_logs/ so there is a
    permanent audit trail inside Obsidian.

Run:
    python mcp_servers/odoo_jsonrpc_server.py

Config:
    Reads ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY from .env.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP
from core.error_logger import logger as error_logger

# ---------------------------------------------------------------------------
# Vault paths
# ---------------------------------------------------------------------------
_ai_vault = _PROJECT_ROOT / "AI_Employee_Vault" / "vault"
_direct_vault = _PROJECT_ROOT / "vault"
VAULT_DIR = _ai_vault if _ai_vault.is_dir() else _direct_vault
INBOX_DIR = VAULT_DIR / "Inbox"
DONE_DIR = VAULT_DIR / "Done"
LOG_DIR = DONE_DIR / "accounting_logs"

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "odoo_jsonrpc",
    instructions=(
        "Odoo ERP integration for the AI Employee using JSON-RPC. "
        "Create invoices, read transactions, look up customers, and "
        "save accounting logs into the Obsidian vault. "
        "Requires ODOO_URL, ODOO_DB, ODOO_USERNAME, and ODOO_API_KEY in .env."
    ),
)


# ---------------------------------------------------------------------------
# Client helper
# ---------------------------------------------------------------------------
def _get_client():
    """Create and authenticate an OdooJsonRpcClient.

    Returns (client, None) on success or (None, error_string) on failure.
    """
    from integrations.odoo.jsonrpc_client import OdooJsonRpcClient, OdooConnectionError
    client = OdooJsonRpcClient()
    try:
        client.authenticate()
        return client, None
    except OdooConnectionError as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# Vault logging helpers
# ---------------------------------------------------------------------------
def _vault_log(title: str, body: str, *, subfolder: str = "") -> Path:
    """Write a Markdown log file into the Obsidian vault.

    Returns the path to the written file.
    """
    target_dir = LOG_DIR / subfolder if subfolder else LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now()
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    filename = f"{ts:%Y%m%d_%H%M%S}_{safe_title}.md"
    path = target_dir / filename

    header = (
        f"# {title}\n\n"
        f"**Generated:** {ts:%Y-%m-%d %H:%M:%S}\n"
        f"**Source:** Odoo JSON-RPC MCP Server\n\n"
        f"---\n\n"
    )
    path.write_text(header + body + "\n", encoding="utf-8")
    return path


def _vault_log_json(title: str, data: Any, *, subfolder: str = "") -> Path:
    """Write a JSON-pretty-printed vault log."""
    formatted = json.dumps(data, indent=2, default=str)
    body = f"```json\n{formatted}\n```\n"
    return _vault_log(title, body, subfolder=subfolder)


# ===================================================================
# Tool 1 — Create Invoice
# ===================================================================
@mcp.tool()
def create_invoice(
    partner_name: str,
    lines: list[dict],
    due_date: str = "",
) -> dict:
    """Create a draft customer invoice in Odoo and log it to the vault.

    Args:
        partner_name: Customer name (must exist in Odoo as res.partner).
        lines: Line items — each dict needs 'product', 'quantity', 'price'.
                Example: [{"product": "Consulting", "quantity": 10, "price": 150}]
        due_date: Optional due date in YYYY-MM-DD format.

    Returns:
        Dict with invoice_id, status, and vault_log path.
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    # Resolve partner
    partners = client.search_read(
        "res.partner",
        [("name", "ilike", partner_name)],
        fields=["id", "name"],
        limit=1,
    )
    if not partners:
        return {"error": f"Customer not found in Odoo: {partner_name!r}"}
    partner_id = partners[0]["id"]
    partner_display = partners[0]["name"]

    # Build one2many line commands
    invoice_lines = []
    total = 0.0
    for ln in lines:
        qty = ln.get("quantity", 1)
        price = ln.get("price", 0)
        total += qty * price
        invoice_lines.append((0, 0, {
            "name": ln.get("product", "Service"),
            "quantity": qty,
            "price_unit": price,
        }))

    values: dict[str, Any] = {
        "move_type": "out_invoice",
        "partner_id": partner_id,
        "invoice_line_ids": invoice_lines,
    }
    if due_date:
        values["invoice_date_due"] = due_date

    try:
        invoice_id = client.create("account.move", values)
    except Exception as exc:
        error_logger.log_error("odoo.jsonrpc.create_invoice", exc)
        return {"error": str(exc)}

    # Log to vault
    line_table = "| Product | Qty | Unit Price |\n|---|---|---|\n"
    for ln in lines:
        line_table += f"| {ln.get('product','Service')} | {ln.get('quantity',1)} | ${ln.get('price',0):,.2f} |\n"

    vault_body = (
        f"## Invoice Created\n\n"
        f"- **Invoice ID:** {invoice_id}\n"
        f"- **Customer:** {partner_display}\n"
        f"- **Due Date:** {due_date or 'Not set'}\n"
        f"- **Total:** ${total:,.2f}\n\n"
        f"### Line Items\n\n{line_table}\n"
        f"#accounting #invoice #odoo\n"
    )
    log_path = _vault_log(f"Invoice_{invoice_id}_{partner_display}", vault_body, subfolder="invoices")

    return {
        "status": "created",
        "invoice_id": invoice_id,
        "partner": partner_display,
        "total": round(total, 2),
        "vault_log": str(log_path.relative_to(_PROJECT_ROOT)),
    }


# ===================================================================
# Tool 2 — Get Invoice
# ===================================================================
@mcp.tool()
def get_invoice(invoice_id: int) -> dict:
    """Read a single invoice by its Odoo ID.

    Args:
        invoice_id: The numeric ID of the invoice in Odoo.
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    results = client.read(
        "account.move", [invoice_id],
        fields=[
            "name", "partner_id", "move_type", "state",
            "amount_total", "amount_residual", "amount_paid",
            "invoice_date", "invoice_date_due", "payment_state",
            "invoice_line_ids",
        ],
    )
    if not results:
        return {"error": f"Invoice {invoice_id} not found"}

    inv = results[0]

    # Resolve line items
    line_ids = inv.pop("invoice_line_ids", [])
    if line_ids:
        inv["lines"] = client.read(
            "account.move.line", line_ids,
            fields=["name", "quantity", "price_unit", "price_subtotal"],
        )

    return inv


# ===================================================================
# Tool 3 — List Unpaid Invoices
# ===================================================================
@mcp.tool()
def list_unpaid_invoices(limit: int = 50) -> dict:
    """List all unpaid (open) customer invoices.

    Args:
        limit: Maximum number of results.
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    invoices = client.search_read(
        "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("payment_state", "in", ["not_paid", "partial"]),
            ("state", "=", "posted"),
        ],
        fields=[
            "name", "partner_id", "amount_total", "amount_residual",
            "invoice_date", "invoice_date_due", "payment_state",
        ],
        limit=limit,
        order="invoice_date_due asc",
    )

    return {"count": len(invoices), "invoices": invoices}


# ===================================================================
# Tool 4 — List Overdue Invoices
# ===================================================================
@mcp.tool()
def list_overdue_invoices(days_overdue: int = 0) -> dict:
    """List invoices that are past their due date.

    Args:
        days_overdue: Minimum days past due (0 = all overdue).
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    cutoff = (datetime.now() - timedelta(days=days_overdue)).strftime("%Y-%m-%d")

    invoices = client.search_read(
        "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("payment_state", "in", ["not_paid", "partial"]),
            ("state", "=", "posted"),
            ("invoice_date_due", "<", cutoff),
        ],
        fields=[
            "name", "partner_id", "amount_total", "amount_residual",
            "invoice_date_due", "payment_state",
        ],
        order="invoice_date_due asc",
    )

    # Enrich with days-overdue count
    today = datetime.now().date()
    for inv in invoices:
        due = inv.get("invoice_date_due")
        if due:
            inv["days_overdue"] = (today - datetime.strptime(due, "%Y-%m-%d").date()).days

    return {"count": len(invoices), "invoices": invoices}


# ===================================================================
# Tool 5 — Read Transactions (Journal Entries)
# ===================================================================
@mcp.tool()
def read_transactions(
    date_from: str = "",
    date_to: str = "",
    journal_type: str = "",
    limit: int = 100,
) -> dict:
    """Read posted journal entries (transactions) from Odoo.

    Args:
        date_from: Start date filter (YYYY-MM-DD).  Defaults to 30 days ago.
        date_to:   End date filter (YYYY-MM-DD).  Defaults to today.
        journal_type: Optional filter: 'sale', 'purchase', 'bank', 'cash', 'general'.
        limit: Max records to return.
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")

    domain: list = [
        ("state", "=", "posted"),
        ("date", ">=", date_from),
        ("date", "<=", date_to),
    ]
    if journal_type:
        domain.append(("journal_id.type", "=", journal_type))

    entries = client.search_read(
        "account.move",
        domain,
        fields=[
            "name", "date", "move_type", "partner_id",
            "amount_total", "state", "journal_id", "ref",
        ],
        limit=limit,
        order="date desc",
    )

    summary = {
        "total_amount": round(sum(e.get("amount_total", 0) for e in entries), 2),
        "count": len(entries),
    }

    return {
        "date_from": date_from,
        "date_to": date_to,
        "summary": summary,
        "transactions": entries,
    }


# ===================================================================
# Tool 6 — Get Customer
# ===================================================================
@mcp.tool()
def get_customer(name: str = "", customer_id: int = 0) -> dict:
    """Look up a customer (res.partner) by name or ID.

    Args:
        name: Partial customer name to search (case-insensitive).
        customer_id: Exact Odoo partner ID.  Takes priority over name.
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    if customer_id:
        results = client.read(
            "res.partner", [customer_id],
            fields=[
                "name", "email", "phone", "street", "city",
                "country_id", "vat", "is_company",
                "total_invoiced", "total_due",
            ],
        )
        if not results:
            return {"error": f"Customer ID {customer_id} not found"}
        return results[0]

    if not name:
        return {"error": "Provide either name or customer_id"}

    results = client.search_read(
        "res.partner",
        [("name", "ilike", name), ("customer_rank", ">", 0)],
        fields=[
            "name", "email", "phone", "city",
            "country_id", "is_company",
            "total_invoiced", "total_due",
        ],
        limit=10,
    )

    return {"count": len(results), "customers": results}


# ===================================================================
# Tool 7 — List Customers
# ===================================================================
@mcp.tool()
def list_customers(
    is_company: bool = True,
    limit: int = 50,
    search: str = "",
) -> dict:
    """List customers from Odoo.

    Args:
        is_company: If True, only return company-type partners.
        limit: Max results.
        search: Optional name filter (case-insensitive substring).
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    domain: list = [("customer_rank", ">", 0)]
    if is_company:
        domain.append(("is_company", "=", True))
    if search:
        domain.append(("name", "ilike", search))

    customers = client.search_read(
        "res.partner",
        domain,
        fields=["name", "email", "phone", "city", "total_invoiced", "total_due"],
        limit=limit,
        order="name asc",
    )

    return {"count": len(customers), "customers": customers}


# ===================================================================
# Tool 8 — Account Balance (Cash Position)
# ===================================================================
@mcp.tool()
def get_account_balance() -> dict:
    """Get current bank and cash account balances from Odoo."""
    client, err = _get_client()
    if err:
        return {"error": err}

    journals = client.search_read(
        "account.journal",
        [("type", "in", ["bank", "cash"])],
        fields=["name", "type", "default_account_id"],
    )

    accounts = []
    total = 0.0

    for journal in journals:
        account_id = journal.get("default_account_id")
        if not account_id:
            continue
        acct_id = account_id[0] if isinstance(account_id, (list, tuple)) else account_id

        move_lines = client.search_read(
            "account.move.line",
            [
                ("account_id", "=", acct_id),
                ("parent_state", "=", "posted"),
            ],
            fields=["debit", "credit"],
        )
        balance = sum(ml.get("debit", 0) - ml.get("credit", 0) for ml in move_lines)

        accounts.append({
            "journal": journal["name"],
            "type": journal["type"],
            "balance": round(balance, 2),
        })
        total += balance

    return {
        "total": round(total, 2),
        "accounts": accounts,
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ===================================================================
# Tool 9 — Log to Vault (manual)
# ===================================================================
@mcp.tool()
def log_to_vault(
    title: str,
    content: str,
    tags: str = "#accounting",
) -> dict:
    """Save an accounting note or log entry into the Obsidian vault.

    Use this to record decisions, meeting notes, or any free-form
    accounting information that should be preserved.

    Args:
        title: Short title for the log entry.
        content: Markdown body text.
        tags: Space-separated tags (default: #accounting).
    """
    body = f"{content}\n\n{tags}\n"
    path = _vault_log(title, body)
    return {
        "status": "saved",
        "file": str(path.relative_to(_PROJECT_ROOT)),
        "title": title,
    }


# ===================================================================
# Tool 10 — Sync Overdue Invoices to Vault
# ===================================================================
@mcp.tool()
def sync_overdue_to_vault(days_overdue: int = 0) -> dict:
    """Pull overdue invoices from Odoo and create alert files in vault/Inbox.

    Each overdue invoice becomes a Markdown task file so it enters the
    normal vault triage pipeline (Inbox -> Needs_Action -> Done).

    Args:
        days_overdue: Minimum days past due to include (0 = all overdue).
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    cutoff = (datetime.now() - timedelta(days=days_overdue)).strftime("%Y-%m-%d")
    invoices = client.search_read(
        "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("payment_state", "in", ["not_paid", "partial"]),
            ("state", "=", "posted"),
            ("invoice_date_due", "<", cutoff),
        ],
        fields=[
            "name", "partner_id", "amount_total", "amount_residual",
            "invoice_date_due", "payment_state",
        ],
        order="invoice_date_due asc",
    )

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    created = []
    skipped = 0

    today = datetime.now().date()
    for inv in invoices:
        inv_name = inv.get("name", "unknown")
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in inv_name)
        alert_file = INBOX_DIR / f"odoo_overdue_{safe_name}.md"

        if alert_file.exists():
            skipped += 1
            continue

        partner = inv.get("partner_id", [None, "Unknown"])
        partner_name = partner[1] if isinstance(partner, (list, tuple)) else str(partner)
        amount = inv.get("amount_residual", 0)
        due_date = inv.get("invoice_date_due", "unknown")
        days_late = (today - datetime.strptime(due_date, "%Y-%m-%d").date()).days if due_date != "unknown" else 0

        content = (
            f"# Overdue Invoice: {inv_name}\n\n"
            f"**Source:** Odoo ERP (JSON-RPC sync)\n"
            f"**Generated:** {datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
            f"---\n\n"
            f"## Details\n\n"
            f"| Field | Value |\n"
            f"|---|---|\n"
            f"| Invoice | {inv_name} |\n"
            f"| Customer | {partner_name} |\n"
            f"| Amount Outstanding | ${amount:,.2f} |\n"
            f"| Due Date | {due_date} |\n"
            f"| Days Overdue | {days_late} |\n\n"
            f"## Action Required\n\n"
            f"- [ ] Send payment reminder to {partner_name}\n"
            f"- [ ] Escalate to collections if > 60 days\n"
            f"- [ ] Negotiate payment plan\n\n"
            f"#accounting #overdue #urgent\n"
        )

        alert_file.write_text(content, encoding="utf-8")
        created.append({"file": alert_file.name, "invoice": inv_name, "amount": amount})

    # Log the sync itself to vault
    if created:
        summary_lines = "\n".join(
            f"- **{c['invoice']}** — ${c['amount']:,.2f}" for c in created
        )
        _vault_log(
            "Overdue_Sync",
            f"## Synced {len(created)} overdue invoices to vault/Inbox\n\n{summary_lines}\n\n"
            f"Skipped {skipped} already-existing alerts.\n\n#accounting #sync\n",
            subfolder="syncs",
        )

    return {
        "created": len(created),
        "skipped": skipped,
        "total_overdue": len(invoices),
        "alerts": created,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
