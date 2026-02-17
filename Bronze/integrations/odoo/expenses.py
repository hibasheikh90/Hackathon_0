"""
Gold Tier — Odoo Expense Tracking
===================================
Log and categorize expenses in Odoo.

Usage:
    from integrations.odoo.expenses import ExpenseManager

    mgr = ExpenseManager()
    mgr.log_expense(250.00, "Travel", "Flight to client meeting")
    weekly = mgr.get_weekly_expenses()
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.error_logger import logger as error_logger
from integrations.odoo.client import OdooClient


class ExpenseManager:
    """High-level expense operations on top of OdooClient."""

    def __init__(self, client: OdooClient | None = None) -> None:
        self.client = client or OdooClient()

    def log_expense(
        self,
        amount: float,
        category: str,
        description: str,
        date: str | None = None,
        employee_id: int | None = None,
    ) -> int:
        """Create an expense record in Odoo.

        Returns the new expense ID.
        """
        values: dict[str, Any] = {
            "name": description,
            "unit_amount": amount,
            "date": date or datetime.now().strftime("%Y-%m-%d"),
        }

        # Try to find product matching the category for proper accounting
        products = self.client.search_read(
            "product.product",
            [("name", "ilike", category), ("can_be_expensed", "=", True)],
            fields=["id", "name"],
            limit=1,
        )
        if products:
            values["product_id"] = products[0]["id"]

        if employee_id:
            values["employee_id"] = employee_id

        expense_id = self.client.create("hr.expense", values)

        error_logger.log_audit("odoo.expense.created", "success", {
            "id": expense_id,
            "amount": amount,
            "category": category,
        })

        return expense_id

    def get_weekly_expenses(self, weeks_back: int = 1) -> list[dict]:
        """Get expenses from the last N weeks."""
        start_date = (
            datetime.now() - timedelta(weeks=weeks_back)
        ).strftime("%Y-%m-%d")

        expenses = self.client.search_read(
            "hr.expense",
            [("date", ">=", start_date)],
            fields=["name", "unit_amount", "date", "product_id", "state"],
            order="date desc",
        )

        return expenses

    def get_monthly_expenses(self, year: int | None = None, month: int | None = None) -> list[dict]:
        """Get expenses for a specific month."""
        now = datetime.now()
        year = year or now.year
        month = month or now.month

        start = f"{year}-{month:02d}-01"
        if month == 12:
            end = f"{year + 1}-01-01"
        else:
            end = f"{year}-{month + 1:02d}-01"

        expenses = self.client.search_read(
            "hr.expense",
            [("date", ">=", start), ("date", "<", end)],
            fields=["name", "unit_amount", "date", "product_id", "state"],
            order="date desc",
        )

        return expenses

    def summary(self, weeks_back: int = 1) -> dict:
        """Expense summary for the CEO briefing."""
        expenses = self.get_weekly_expenses(weeks_back)

        total = sum(e.get("unit_amount", 0) for e in expenses)

        # Group by category
        by_category: dict[str, float] = {}
        for e in expenses:
            product = e.get("product_id")
            cat = product[1] if isinstance(product, (list, tuple)) and len(product) > 1 else "Uncategorized"
            by_category[cat] = by_category.get(cat, 0) + e.get("unit_amount", 0)

        return {
            "total": round(total, 2),
            "count": len(expenses),
            "by_category": {k: round(v, 2) for k, v in by_category.items()},
        }
