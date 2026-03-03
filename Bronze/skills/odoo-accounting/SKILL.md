# Skill: Odoo Accounting

## Description

Integrates the AI Employee with Odoo Community ERP for full accounting operations: create and track invoices, log expenses, generate financial reports (P&L, cash position, AR aging), and bidirectionally sync vault tasks with Odoo data.

## Prerequisites

1. Odoo Community instance running (local or remote).
2. `.env` file with:
   ```
   ODOO_URL="http://localhost:8069"
   ODOO_DB="your_database"
   ODOO_USERNAME="admin"
   ODOO_API_KEY="your_api_key"
   ```
3. Dependencies: `pip install requests pyyaml python-dotenv`
4. `config/odoo_connection.yaml` configured with host, database, and credentials.

## Usage

```bash
# List all unpaid invoices
python -c "from integrations.odoo.invoices import InvoiceManager; print(InvoiceManager().list_unpaid())"

# List overdue invoices (30+ days)
python -c "from integrations.odoo.invoices import InvoiceManager; print(InvoiceManager().list_overdue(30))"

# Create an invoice
python -c "
from integrations.odoo.invoices import InvoiceManager
mgr = InvoiceManager()
mgr.create_invoice('Acme Corp', [{'product': 'Consulting', 'quantity': 10, 'price': 150}])
"

# Log an expense
python -c "
from integrations.odoo.expenses import ExpenseManager
mgr = ExpenseManager()
mgr.log_expense('Software subscription', 49.99, 'Technology')
"

# Generate P&L report
python -c "from integrations.odoo.reports import ReportManager; print(ReportManager().profit_and_loss())"

# Run vault <-> Odoo sync (called by Gold scheduler every 5 min)
python -c "from integrations.odoo.sync import OdooSync; OdooSync().run_sync()"

# Use JSON-RPC MCP server
python mcp_servers/odoo_jsonrpc_server.py
```

## Inputs

| Module | Class / Function | Key Parameters |
|--------|-----------------|----------------|
| `integrations/odoo/invoices.py` | `InvoiceManager` | partner name, line items, due date |
| `integrations/odoo/expenses.py` | `ExpenseManager` | name, amount, category |
| `integrations/odoo/reports.py` | `ReportManager` | date range, report type |
| `integrations/odoo/sync.py` | `OdooSync` | vault path (auto-detected) |

## Output

| Operation | Result |
|-----------|--------|
| `list_unpaid()` | List of dicts with invoice name, partner, amount, due date |
| `list_overdue(days)` | List of overdue invoices past the given day threshold |
| `create_invoice(...)` | Odoo invoice ID; fires `odoo.invoice.created` event |
| `log_expense(...)` | Odoo expense ID; fires `odoo.expense.logged` event |
| `profit_and_loss()` | Dict with revenue, expenses, net profit |
| `run_sync()` | Creates vault Inbox files for overdue invoices; pushes `#accounting`-tagged tasks to Odoo |

## Workflow

1. **Inbound (Odoo → Vault):** `OdooSync.run_sync()` queries Odoo for overdue invoices and writes alert `.md` files to `vault/Inbox/` so the triage pipeline handles them.
2. **Outbound (Vault → Odoo):** Files in `vault/Needs_Action/` tagged `#accounting` are parsed and pushed as Odoo records (invoices or expenses).
3. **Events fired:**
   - `odoo.invoice.created` — new invoice registered
   - `odoo.invoice.overdue` — overdue invoice detected
   - `odoo.expense.logged` — expense recorded
   - `odoo.sync.complete` — sync cycle finished
4. All actions are logged to `logs/audit.log`.

## MCP Integration

The `mcp_servers/accounting_server.py` exposes these operations as Claude-callable tools:

| Tool | Description |
|------|-------------|
| `get_unpaid_invoices` | Fetch all open invoices |
| `create_invoice` | Create a new customer invoice |
| `get_profit_loss` | Retrieve P&L report for a date range |
| `get_ar_aging` | Accounts receivable aging report |

## Sensitive Action Policy

Creating or posting invoices/payments **always** requires human approval. Claude will write an approval request to `vault/Pending_Approval/` before any write operation is sent to Odoo. Move the file to `vault/Approved/` to proceed, or `vault/Rejected/` to cancel.
