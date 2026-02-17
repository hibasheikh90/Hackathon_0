"""
Gold Tier — Odoo XML-RPC Client
================================
Low-level connection to Odoo ERP via XML-RPC.

Usage:
    from integrations.odoo.client import OdooClient

    client = OdooClient()
    client.authenticate()
    partners = client.search_read("res.partner", [("is_company", "=", True)], ["name", "email"])
"""

from __future__ import annotations

import http.client
import sys
import time
import xmlrpc.client
from pathlib import Path
from typing import Any

# Add project root for imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.config_loader import config
from core.error_logger import logger as error_logger


class _TimeoutTransport(xmlrpc.client.Transport):
    """XML-RPC transport with configurable connection timeout."""

    def __init__(self, timeout: int = 10, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class _TimeoutSafeTransport(xmlrpc.client.SafeTransport):
    """XML-RPC HTTPS transport with configurable connection timeout."""

    def __init__(self, timeout: int = 10, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class OdooConnectionError(Exception):
    """Raised when Odoo connection or authentication fails."""


class OdooClient:
    """XML-RPC client for Odoo ERP."""

    def __init__(self) -> None:
        config.load()
        odoo_cfg = config.odoo

        self.url = config.env("ODOO_URL") or odoo_cfg.get("host", "")
        self.db = config.env("ODOO_DB") or odoo_cfg.get("database", "")
        self.username = config.env("ODOO_USERNAME", "admin")
        self.api_key = config.env("ODOO_API_KEY", "")
        self.timeout = odoo_cfg.get("timeout_seconds", 30)
        self.max_retries = odoo_cfg.get("max_retries", 3)

        self._uid: int | None = None
        self._common: xmlrpc.client.ServerProxy | None = None
        self._models: xmlrpc.client.ServerProxy | None = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def authenticate(self) -> int:
        """Authenticate with Odoo. Returns the user ID (uid).

        Raises OdooConnectionError on failure.
        """
        if not self.url or not self.db:
            raise OdooConnectionError(
                "Odoo URL and database must be configured. "
                "Set ODOO_URL and ODOO_DB in .env or config/odoo_connection.yaml"
            )

        last_error = None
        transport_cls = _TimeoutSafeTransport if self.url.startswith("https") else _TimeoutTransport
        transport = transport_cls(timeout=self.timeout)
        for attempt in range(1, self.max_retries + 1):
            try:
                self._common = xmlrpc.client.ServerProxy(
                    f"{self.url}/xmlrpc/2/common",
                    transport=transport,
                )
                uid = self._common.authenticate(
                    self.db, self.username, self.api_key, {}
                )
                if not uid:
                    raise OdooConnectionError("Authentication returned no UID — check credentials")

                self._uid = uid
                self._models = xmlrpc.client.ServerProxy(
                    f"{self.url}/xmlrpc/2/object",
                    transport=transport,
                )
                error_logger.log_audit("odoo.auth", "success", {
                    "url": self.url, "db": self.db, "uid": uid,
                })
                return uid

            except OdooConnectionError:
                raise
            except Exception as e:
                last_error = e
                error_logger.log_error("odoo.auth", e, {
                    "url": self.url, "attempt": attempt,
                })
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)

        raise OdooConnectionError(f"Failed after {self.max_retries} attempts: {last_error}")

    @property
    def uid(self) -> int:
        if self._uid is None:
            self.authenticate()
        return self._uid

    def _ensure_connected(self) -> None:
        if self._models is None or self._uid is None:
            self.authenticate()

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def _execute(self, model: str, method: str, *args, **kwargs) -> Any:
        """Execute an Odoo model method with retry logic."""
        self._ensure_connected()

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = self._models.execute_kw(
                    self.db, self._uid, self.api_key,
                    model, method, list(args), kwargs,
                )
                return result
            except Exception as e:
                last_error = e
                error_logger.log_error("odoo.execute", e, {
                    "model": model, "method": method, "attempt": attempt,
                })
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)

        raise OdooConnectionError(
            f"Odoo {model}.{method} failed after {self.max_retries} attempts: {last_error}"
        )

    def search_read(
        self,
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict]:
        """Search and read records from an Odoo model."""
        kwargs: dict[str, Any] = {"limit": limit, "offset": offset}
        if fields:
            kwargs["fields"] = fields
        if order:
            kwargs["order"] = order
        return self._execute(model, "search_read", domain or [], **kwargs)

    def search(self, model: str, domain: list | None = None, limit: int = 100) -> list[int]:
        """Search for record IDs matching domain."""
        return self._execute(model, "search", domain or [], limit=limit)

    def read(self, model: str, ids: list[int], fields: list[str] | None = None) -> list[dict]:
        """Read specific records by ID."""
        kwargs = {"fields": fields} if fields else {}
        return self._execute(model, "read", ids, **kwargs)

    def create(self, model: str, values: dict) -> int:
        """Create a new record. Returns the new record ID."""
        result = self._execute(model, "create", [values])
        error_logger.log_audit("odoo.create", "success", {
            "model": model, "id": result,
        })
        return result

    def write(self, model: str, ids: list[int], values: dict) -> bool:
        """Update existing records."""
        result = self._execute(model, "write", ids, values)
        error_logger.log_audit("odoo.write", "success", {
            "model": model, "ids": ids,
        })
        return result

    def unlink(self, model: str, ids: list[int]) -> bool:
        """Delete records."""
        result = self._execute(model, "unlink", ids)
        error_logger.log_audit("odoo.unlink", "success", {
            "model": model, "ids": ids,
        })
        return result

    def count(self, model: str, domain: list | None = None) -> int:
        """Count records matching domain."""
        return self._execute(model, "search_count", domain or [])

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def version(self) -> dict:
        """Get Odoo server version info (does not require authentication)."""
        if self._common is None:
            transport_cls = _TimeoutSafeTransport if self.url.startswith("https") else _TimeoutTransport
            self._common = xmlrpc.client.ServerProxy(
                f"{self.url}/xmlrpc/2/common",
                transport=transport_cls(timeout=self.timeout),
            )
        return self._common.version()

    def __repr__(self) -> str:
        status = "connected" if self._uid else "disconnected"
        return f"<OdooClient url={self.url!r} db={self.db!r} {status}>"
