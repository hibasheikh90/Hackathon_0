"""
Gold Tier — Odoo Financial Reports
====================================
Pull P&L, balance sheet, cash flow, and AR aging from Odoo.

Usage:
    from integrations.odoo.reports import FinancialReports

    reports = FinancialReports()
    pnl = reports.get_profit_loss("2026-01-01", "2026-01-31")
    cash = reports.get_cash_position()
    aging = reports.get_ar_aging()
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.error_logger import logger as error_logger
from integrations.odoo.client import OdooClient


class FinancialReports:
    """High-level financial reporting from Odoo data."""

    def __init__(self, client: OdooClient | None = None) -> None:
        self.client = client or OdooClient()

    def get_profit_loss(self, date_from: str, date_to: str) -> dict:
        """Calculate P&L summary for a date range.

        Returns dict with revenue, expenses, and net_profit.
        """
        # Revenue: sum of posted customer invoices
        revenue_invoices = self.client.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", date_from),
                ("invoice_date", "<=", date_to),
            ],
            fields=["amount_total"],
        )
        revenue = sum(inv.get("amount_total", 0) for inv in revenue_invoices)

        # Expenses: sum of posted vendor bills
        expense_bills = self.client.search_read(
            "account.move",
            [
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", date_from),
                ("invoice_date", "<=", date_to),
            ],
            fields=["amount_total"],
        )
        expenses = sum(bill.get("amount_total", 0) for bill in expense_bills)

        # Credit notes (refunds) reduce revenue
        credit_notes = self.client.search_read(
            "account.move",
            [
                ("move_type", "=", "out_refund"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", date_from),
                ("invoice_date", "<=", date_to),
            ],
            fields=["amount_total"],
        )
        refunds = sum(cn.get("amount_total", 0) for cn in credit_notes)

        net_revenue = revenue - refunds
        net_profit = net_revenue - expenses

        result = {
            "date_from": date_from,
            "date_to": date_to,
            "revenue": round(net_revenue, 2),
            "expenses": round(expenses, 2),
            "refunds": round(refunds, 2),
            "net_profit": round(net_profit, 2),
        }

        error_logger.log_audit("odoo.reports.pnl", "success", result)
        return result

    def get_cash_position(self) -> dict:
        """Get current bank/cash balances from Odoo journal entries.

        Reads the balance of bank and cash type journals.
        """
        # Get bank journals
        journals = self.client.search_read(
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

            # Sum all posted journal items for this account
            move_lines = self.client.search_read(
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

        result = {
            "total": round(total, 2),
            "accounts": accounts,
            "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        error_logger.log_audit("odoo.reports.cash_position", "success", {
            "total": result["total"], "account_count": len(accounts),
        })
        return result

    def get_ar_aging(self) -> dict:
        """Accounts receivable aging breakdown.

        Buckets: current, 1-30 days, 31-60 days, 61-90 days, 90+ days.
        """
        unpaid = self.client.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("payment_state", "in", ["not_paid", "partial"]),
                ("state", "=", "posted"),
            ],
            fields=["name", "partner_id", "amount_residual", "invoice_date_due"],
        )

        buckets = {
            "current": 0.0,
            "1_30_days": 0.0,
            "31_60_days": 0.0,
            "61_90_days": 0.0,
            "over_90_days": 0.0,
        }
        today = datetime.now().date()

        for inv in unpaid:
            due_str = inv.get("invoice_date_due")
            amount = inv.get("amount_residual", 0)
            if not due_str:
                buckets["current"] += amount
                continue

            due_date = datetime.strptime(due_str, "%Y-%m-%d").date()
            days_overdue = (today - due_date).days

            if days_overdue <= 0:
                buckets["current"] += amount
            elif days_overdue <= 30:
                buckets["1_30_days"] += amount
            elif days_overdue <= 60:
                buckets["31_60_days"] += amount
            elif days_overdue <= 90:
                buckets["61_90_days"] += amount
            else:
                buckets["over_90_days"] += amount

        total = sum(buckets.values())
        result = {
            "buckets": {k: round(v, 2) for k, v in buckets.items()},
            "total": round(total, 2),
            "invoice_count": len(unpaid),
            "as_of": today.isoformat(),
        }

        error_logger.log_audit("odoo.reports.ar_aging", "success", {
            "total": result["total"], "count": len(unpaid),
        })
        return result
