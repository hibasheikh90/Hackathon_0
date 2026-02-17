"""
Gold Tier — Odoo Invoice Operations
=====================================
Create, read, and track invoices in Odoo.

Usage:
    from integrations.odoo.invoices import InvoiceManager

    mgr = InvoiceManager()
    unpaid = mgr.list_unpaid()
    mgr.create_invoice("partner_name", [{"product": "Consulting", "quantity": 10, "price": 150}])
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.event_bus import bus
from core.error_logger import logger as error_logger
from integrations.odoo.client import OdooClient


class InvoiceManager:
    """High-level invoice operations on top of OdooClient."""

    def __init__(self, client: OdooClient | None = None) -> None:
        self.client = client or OdooClient()

    def list_unpaid(self, limit: int = 50) -> list[dict]:
        """List all unpaid (open) customer invoices."""
        invoices = self.client.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("payment_state", "in", ["not_paid", "partial"]),
                ("state", "=", "posted"),
            ],
            fields=["name", "partner_id", "amount_total", "amount_residual",
                     "invoice_date", "invoice_date_due", "payment_state"],
            limit=limit,
            order="invoice_date_due asc",
        )
        error_logger.log_audit("odoo.invoices.list_unpaid", "success", {
            "count": len(invoices),
        })
        return invoices

    def list_overdue(self, days_overdue: int = 0) -> list[dict]:
        """List invoices past their due date."""
        cutoff = (datetime.now() - timedelta(days=days_overdue)).strftime("%Y-%m-%d")
        invoices = self.client.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("payment_state", "in", ["not_paid", "partial"]),
                ("state", "=", "posted"),
                ("invoice_date_due", "<", cutoff),
            ],
            fields=["name", "partner_id", "amount_total", "amount_residual",
                     "invoice_date_due", "payment_state"],
            order="invoice_date_due asc",
        )

        # Emit event for each significantly overdue invoice
        for inv in invoices:
            due_date = inv.get("invoice_date_due")
            if due_date:
                days_late = (datetime.now() - datetime.strptime(due_date, "%Y-%m-%d")).days
                if days_late >= 30:
                    bus.emit("odoo.invoice.overdue", {
                        "invoice": inv["name"],
                        "partner": inv.get("partner_id", [None, "Unknown"])[1],
                        "amount": inv.get("amount_residual", 0),
                        "days_overdue": days_late,
                    })

        return invoices

    def get_invoice(self, invoice_id: int) -> dict | None:
        """Get a single invoice by ID."""
        results = self.client.read("account.move", [invoice_id])
        return results[0] if results else None

    def create_invoice(
        self,
        partner_name: str,
        lines: list[dict[str, Any]],
        due_date: str | None = None,
    ) -> int:
        """Create a draft customer invoice.

        Args:
            partner_name: Customer name (must exist in Odoo as res.partner)
            lines: List of dicts with keys: product, quantity, price
            due_date: Optional due date string (YYYY-MM-DD)

        Returns:
            New invoice ID
        """
        # Find or fail on partner
        partners = self.client.search_read(
            "res.partner",
            [("name", "ilike", partner_name)],
            fields=["id", "name"],
            limit=1,
        )
        if not partners:
            raise ValueError(f"Partner not found in Odoo: {partner_name!r}")

        partner_id = partners[0]["id"]

        # Build invoice line commands (Odoo one2many format)
        invoice_lines = []
        for line in lines:
            invoice_lines.append((0, 0, {
                "name": line.get("product", "Service"),
                "quantity": line.get("quantity", 1),
                "price_unit": line.get("price", 0),
            }))

        values: dict[str, Any] = {
            "move_type": "out_invoice",
            "partner_id": partner_id,
            "invoice_line_ids": invoice_lines,
        }
        if due_date:
            values["invoice_date_due"] = due_date

        invoice_id = self.client.create("account.move", values)

        bus.emit("odoo.invoice.created", {
            "id": invoice_id,
            "partner": partner_name,
            "line_count": len(lines),
        })

        return invoice_id

    def mark_paid(self, invoice_id: int) -> bool:
        """Mark an invoice as paid by creating a payment and reconciling.

        Note: In production, this would use account.payment workflow.
        For simplicity, this toggles the payment_state field.
        """
        result = self.client.write(
            "account.move", [invoice_id], {"payment_state": "paid"}
        )
        if result:
            error_logger.log_audit("odoo.invoice.mark_paid", "success", {
                "invoice_id": invoice_id,
            })
        return result

    def summary(self) -> dict:
        """Return a summary of invoice counts and totals."""
        unpaid = self.list_unpaid(limit=500)
        overdue = self.list_overdue()

        total_outstanding = sum(inv.get("amount_residual", 0) for inv in unpaid)
        total_overdue = sum(inv.get("amount_residual", 0) for inv in overdue)

        return {
            "unpaid_count": len(unpaid),
            "unpaid_total": round(total_outstanding, 2),
            "overdue_count": len(overdue),
            "overdue_total": round(total_overdue, 2),
        }
