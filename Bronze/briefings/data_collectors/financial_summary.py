"""
Gold Tier — Financial Summary Collector
=========================================
Pulls financial data from Odoo for the CEO briefing.

Metrics:
    - Revenue (this week vs last week)
    - Expenses (this week vs last week)
    - Outstanding AR and aging
    - Cash position

Usage:
    from briefings.data_collectors.financial_summary import collect

    data = collect()
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.error_logger import logger as error_logger


def _week_range(weeks_back: int = 0) -> tuple[str, str]:
    """Return (start_date, end_date) strings for a week ending on the most recent Sunday."""
    today = datetime.now().date()
    # End of the target week (last Sunday, or today if Sunday)
    days_since_monday = today.weekday()  # Monday=0, Sunday=6
    end = today - timedelta(days=days_since_monday + 1 + 7 * weeks_back)
    if end > today:
        end = today
    start = end - timedelta(days=6)
    return start.isoformat(), end.isoformat()


def collect() -> dict:
    """Collect financial summary data.

    Tries to connect to Odoo. If Odoo is not configured or unreachable,
    returns a skeleton dict with None values so the template can show
    'N/A' instead of crashing.
    """
    skeleton = {
        "available": False,
        "revenue_this_week": None,
        "revenue_last_week": None,
        "revenue_change_pct": None,
        "expenses_this_week": None,
        "expenses_last_week": None,
        "expenses_change_pct": None,
        "ar_total": None,
        "ar_aging": None,
        "cash_position": None,
        "cash_accounts": [],
    }

    try:
        from integrations.odoo.client import OdooClient, OdooConnectionError
        from integrations.odoo.reports import FinancialReports
        from integrations.odoo.invoices import InvoiceManager
        from integrations.odoo.expenses import ExpenseManager

        client = OdooClient()
        client.authenticate()
        reports = FinancialReports(client)

    except ImportError:
        error_logger.log_audit("briefing.collector.financial", "skipped", {
            "reason": "Odoo integration not available",
        })
        return skeleton
    except Exception as e:
        error_logger.log_error("briefing.collector.financial", e, {
            "phase": "connect",
        })
        return skeleton

    result = {"available": True}

    # --- Revenue & Expenses: this week vs last week ---
    try:
        tw_start, tw_end = _week_range(0)
        lw_start, lw_end = _week_range(1)

        pnl_this = reports.get_profit_loss(tw_start, tw_end)
        pnl_last = reports.get_profit_loss(lw_start, lw_end)

        result["revenue_this_week"] = pnl_this["revenue"]
        result["revenue_last_week"] = pnl_last["revenue"]
        result["expenses_this_week"] = pnl_this["expenses"]
        result["expenses_last_week"] = pnl_last["expenses"]

        if pnl_last["revenue"] and pnl_last["revenue"] != 0:
            result["revenue_change_pct"] = round(
                ((pnl_this["revenue"] - pnl_last["revenue"]) / pnl_last["revenue"]) * 100, 1
            )
        else:
            result["revenue_change_pct"] = None

        if pnl_last["expenses"] and pnl_last["expenses"] != 0:
            result["expenses_change_pct"] = round(
                ((pnl_this["expenses"] - pnl_last["expenses"]) / pnl_last["expenses"]) * 100, 1
            )
        else:
            result["expenses_change_pct"] = None

    except Exception as e:
        error_logger.log_error("briefing.collector.financial.pnl", e)
        result.update({
            "revenue_this_week": None, "revenue_last_week": None,
            "revenue_change_pct": None, "expenses_this_week": None,
            "expenses_last_week": None, "expenses_change_pct": None,
        })

    # --- AR Aging ---
    try:
        aging = reports.get_ar_aging()
        result["ar_total"] = aging["total"]
        result["ar_aging"] = aging["buckets"]
    except Exception as e:
        error_logger.log_error("briefing.collector.financial.ar", e)
        result["ar_total"] = None
        result["ar_aging"] = None

    # --- Cash Position ---
    try:
        cash = reports.get_cash_position()
        result["cash_position"] = cash["total"]
        result["cash_accounts"] = cash["accounts"]
    except Exception as e:
        error_logger.log_error("briefing.collector.financial.cash", e)
        result["cash_position"] = None
        result["cash_accounts"] = []

    error_logger.log_audit("briefing.collector.financial", "success", {
        "revenue": result.get("revenue_this_week"),
        "cash": result.get("cash_position"),
    })

    return result
