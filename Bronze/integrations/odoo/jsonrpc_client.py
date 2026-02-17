"""
Gold Tier — Odoo JSON-RPC Client
==================================
Connects to Odoo via its JSON-RPC API (``/jsonrpc``).

JSON-RPC is the native web protocol that Odoo's own JS frontend uses,
and supports the same ``execute_kw`` calls as XML-RPC, but over plain
HTTP(S) + JSON — easier to debug and firewall-friendly.

Usage:
    from integrations.odoo.jsonrpc_client import OdooJsonRpcClient

    client = OdooJsonRpcClient()
    client.authenticate()
    partners = client.search_read(
        "res.partner",
        [("is_company", "=", True)],
        ["name", "email"],
    )
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.config_loader import config
from core.error_logger import logger as error_logger


class OdooConnectionError(Exception):
    """Raised when Odoo connection or authentication fails."""


class OdooJsonRpcClient:
    """Odoo client using the JSON-RPC 2.0 endpoint (``/jsonrpc``).

    Every Odoo HTTP request is a JSON-RPC call to ``/jsonrpc`` with:
        service  — "common" (auth) or "object" (model CRUD)
        method   — "authenticate", "execute_kw", etc.
        args     — positional arguments for the service method
    """

    def __init__(self) -> None:
        config.load()
        odoo_cfg = config.odoo

        self.url: str = (config.env("ODOO_URL") or odoo_cfg.get("host", "")).rstrip("/")
        self.db: str = config.env("ODOO_DB") or odoo_cfg.get("database", "")
        self.username: str = config.env("ODOO_USERNAME", "admin")
        self.api_key: str = config.env("ODOO_API_KEY", "")
        self.timeout: int = odoo_cfg.get("timeout_seconds", 10)
        self.max_retries: int = odoo_cfg.get("max_retries", 2)

        self._uid: int | None = None

    # ------------------------------------------------------------------
    # Low-level JSON-RPC transport
    # ------------------------------------------------------------------

    def _jsonrpc(self, service: str, method: str, args: list) -> Any:
        """Send a single JSON-RPC 2.0 request to ``/jsonrpc``.

        Raises OdooConnectionError on transport or Odoo-level errors.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": random.randint(1, 1_000_000_000),
            "method": "call",
            "params": {
                "service": service,
                "method": method,
                "args": args,
            },
        }

        body = json.dumps(payload).encode("utf-8")
        req = Request(
            f"{self.url}/jsonrpc",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, OSError) as exc:
            raise OdooConnectionError(f"HTTP error calling {service}/{method}: {exc}") from exc

        if data.get("error"):
            err = data["error"]
            msg = err.get("data", {}).get("message") or err.get("message") or str(err)
            raise OdooConnectionError(f"Odoo JSON-RPC error: {msg}")

        return data.get("result")

    def _call_with_retry(self, service: str, method: str, args: list) -> Any:
        """Wrap ``_jsonrpc`` with retry + exponential backoff."""
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._jsonrpc(service, method, args)
            except OdooConnectionError:
                raise
            except Exception as exc:
                last_error = exc
                error_logger.log_error("odoo.jsonrpc", exc, {
                    "service": service, "method": method, "attempt": attempt,
                })
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 8))

        raise OdooConnectionError(
            f"{service}/{method} failed after {self.max_retries} attempts: {last_error}"
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self) -> int:
        """Authenticate and store the uid.  Returns the user id."""
        if not self.url or not self.db:
            raise OdooConnectionError(
                "Set ODOO_URL and ODOO_DB in .env or config/odoo_connection.yaml"
            )

        uid = self._call_with_retry(
            "common", "authenticate",
            [self.db, self.username, self.api_key, {}],
        )

        if not uid:
            raise OdooConnectionError("Authentication returned no UID — check credentials")

        self._uid = uid
        error_logger.log_audit("odoo.jsonrpc.auth", "success", {
            "url": self.url, "db": self.db, "uid": uid,
        })
        return uid

    @property
    def uid(self) -> int:
        if self._uid is None:
            self.authenticate()
        return self._uid

    def _ensure_auth(self) -> None:
        if self._uid is None:
            self.authenticate()

    # ------------------------------------------------------------------
    # execute_kw helper
    # ------------------------------------------------------------------

    def _execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
        self._ensure_auth()
        return self._call_with_retry(
            "object", "execute_kw",
            [self.db, self._uid, self.api_key, model, method, args, kwargs or {}],
        )

    # ------------------------------------------------------------------
    # CRUD shortcuts
    # ------------------------------------------------------------------

    def search_read(
        self,
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict]:
        kw: dict[str, Any] = {"limit": limit, "offset": offset}
        if fields:
            kw["fields"] = fields
        if order:
            kw["order"] = order
        return self._execute_kw(model, "search_read", [domain or []], kw)

    def search(self, model: str, domain: list | None = None, limit: int = 100) -> list[int]:
        return self._execute_kw(model, "search", [domain or []], {"limit": limit})

    def read(self, model: str, ids: list[int], fields: list[str] | None = None) -> list[dict]:
        kw = {"fields": fields} if fields else {}
        return self._execute_kw(model, "read", [ids], kw)

    def create(self, model: str, values: dict) -> int:
        result = self._execute_kw(model, "create", [values])
        error_logger.log_audit("odoo.jsonrpc.create", "success", {
            "model": model, "id": result,
        })
        return result

    def write(self, model: str, ids: list[int], values: dict) -> bool:
        result = self._execute_kw(model, "write", [ids, values])
        error_logger.log_audit("odoo.jsonrpc.write", "success", {
            "model": model, "ids": ids,
        })
        return result

    def count(self, model: str, domain: list | None = None) -> int:
        return self._execute_kw(model, "search_count", [domain or []])

    # ------------------------------------------------------------------
    # Pretty repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        status = "connected" if self._uid else "disconnected"
        return f"<OdooJsonRpcClient url={self.url!r} db={self.db!r} {status}>"
