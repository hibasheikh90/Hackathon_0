"""
Gold Tier — Accounting MCP Server
====================================
Exposes Odoo ERP financial operations to Claude via MCP.

Tools:
    get_unpaid_invoices  — List all unpaid customer invoices
    get_overdue_invoices — List invoices past due date
    create_invoice       — Create a new draft invoice in Odoo
    get_profit_loss      — P&L report for a date range
    get_cash_position    — Current bank/cash balances
    get_ar_aging         — Accounts receivable aging breakdown
    get_expense_summary  — Weekly expense summary

Run:
    python mcp_servers/accounting_server.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "accounting",
    instructions=(
        "Odoo ERP accounting integration for the AI Employee. "
        "Query invoices, pull financial reports, and track expenses. "
        "Requires ODOO_URL, ODOO_DB, and ODOO_API_KEY in .env."
    ),
)


def _get_client():
    """Create and authenticate an OdooClient, returning (client, error)."""
    from integrations.odoo.client import OdooClient, OdooConnectionError
    client = OdooClient()
    try:
        client.authenticate()
        return client, None
    except OdooConnectionError as e:
        return None, str(e)


@mcp.tool()
def get_unpaid_invoices(limit: int = 50) -> dict:
    """List all unpaid customer invoices from Odoo.

    Args:
        limit: Maximum number of invoices to return
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    from integrations.odoo.invoices import InvoiceManager
    mgr = InvoiceManager(client)
    invoices = mgr.list_unpaid(limit=limit)
    return {"count": len(invoices), "invoices": invoices}


@mcp.tool()
def get_overdue_invoices(days_overdue: int = 0) -> dict:
    """List invoices past their due date.

    Args:
        days_overdue: Minimum days past due (0 = all overdue)
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    from integrations.odoo.invoices import InvoiceManager
    mgr = InvoiceManager(client)
    invoices = mgr.list_overdue(days_overdue=days_overdue)
    return {"count": len(invoices), "invoices": invoices}


@mcp.tool()
def create_invoice(partner_name: str, lines: list[dict], due_date: str = "") -> dict:
    """Create a new draft customer invoice in Odoo.

    Args:
        partner_name: Customer name (must exist in Odoo)
        lines: List of line items, each with 'product', 'quantity', 'price'
        due_date: Optional due date (YYYY-MM-DD)
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    from integrations.odoo.invoices import InvoiceManager
    mgr = InvoiceManager(client)

    try:
        invoice_id = mgr.create_invoice(
            partner_name=partner_name,
            lines=lines,
            due_date=due_date or None,
        )
        return {"status": "created", "invoice_id": invoice_id}
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
def get_profit_loss(date_from: str, date_to: str) -> dict:
    """Get profit and loss report for a date range.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    from integrations.odoo.reports import FinancialReports
    reports = FinancialReports(client)
    return reports.get_profit_loss(date_from, date_to)


@mcp.tool()
def get_cash_position() -> dict:
    """Get current bank and cash balances from Odoo."""
    client, err = _get_client()
    if err:
        return {"error": err}

    from integrations.odoo.reports import FinancialReports
    reports = FinancialReports(client)
    return reports.get_cash_position()


@mcp.tool()
def get_ar_aging() -> dict:
    """Get accounts receivable aging breakdown (current, 1-30, 31-60, 61-90, 90+ days)."""
    client, err = _get_client()
    if err:
        return {"error": err}

    from integrations.odoo.reports import FinancialReports
    reports = FinancialReports(client)
    return reports.get_ar_aging()


@mcp.tool()
def get_expense_summary(weeks_back: int = 1) -> dict:
    """Get expense summary grouped by category.

    Args:
        weeks_back: How many weeks of data to include
    """
    client, err = _get_client()
    if err:
        return {"error": err}

    from integrations.odoo.expenses import ExpenseManager
    mgr = ExpenseManager(client)
    return mgr.summary(weeks_back=weeks_back)


if __name__ == "__main__":
    mcp.run()
