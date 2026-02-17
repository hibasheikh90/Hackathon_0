# Daily Error Summary — 2026-02-17

**Generated:** 2026-02-17 16:00
**Period:** Last 24 hours (since 2026-02-16 16:00)
**System Health:** [ERR] DEGRADED

---

## Overview

| Metric | Count |
|---|---|
| Total errors | 122 |
| Critical | 0 |
| Errors | 122 |
| Warnings | 0 |

---

## Errors by Source

| Source | Count | Last Error | Severity |
|---|---|---|---|
| `gmail.sender` | 61 | (535, b'5.7.8 Username and Password not accepted. For more i... | ERROR |
| `odoo.auth` | 43 | Request-sent | ERROR |
| `briefing.collector.financial` | 18 | Failed after 2 attempts: Request-sent | ERROR |

---

## Error Types

| Type | Count |
|---|---|
| `SMTPAuthenticationError` | 61 |
| `ProtocolError` | 29 |
| `OdooConnectionError` | 18 |
| `ResponseNotReady` | 14 |

---

## Recovery & Retry Status

| Metric | Count |
|---|---|
| Tasks retried | 0 |
| Successfully recovered | 0 |
| Queue — pending retry | 0 |
| Queue — permanently failed | 0 |
| Queue — resolved | 1 |

---

## Recent Error Timeline

- `2026-02-17T12:36:26` [ERROR] **briefing.collector.financial** — Failed after 2 attempts: Request-sent
- `2026-02-17T12:36:27` [ERROR] **odoo.auth** — <ProtocolError for your-company.odoo.com/xmlrpc/2/common: 404 Not Found>
- `2026-02-17T12:36:29` [ERROR] **odoo.auth** — Request-sent
- `2026-02-17T12:36:29` [ERROR] **briefing.collector.financial** — Failed after 2 attempts: Request-sent
- `2026-02-17T15:32:03` [ERROR] **odoo.auth** — <ProtocolError for your-company.odoo.com/xmlrpc/2/common: 404 Not Found>
- `2026-02-17T15:32:05` [ERROR] **odoo.auth** — Request-sent
- `2026-02-17T15:32:05` [ERROR] **briefing.collector.financial** — Failed after 2 attempts: Request-sent
- `2026-02-17T15:36:09` [ERROR] **odoo.auth** — <ProtocolError for your-company.odoo.com/xmlrpc/2/common: 404 Not Found>
- `2026-02-17T15:36:11` [ERROR] **odoo.auth** — Request-sent
- `2026-02-17T15:36:11` [ERROR] **briefing.collector.financial** — Failed after 2 attempts: Request-sent

---

*Generated 2026-02-17 16:00 by AI Employee Error Monitor*
