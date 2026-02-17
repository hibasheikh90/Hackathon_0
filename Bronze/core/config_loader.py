"""
Gold Tier — Configuration Loader
=================================
Loads YAML config files from config/ and merges with .env variables.

Usage:
    from core.config_loader import config

    # Access top-level config sections
    config.scheduler          # dict from gold.yaml -> scheduler
    config.social_accounts    # dict from social_accounts.yaml
    config.odoo               # dict from odoo_connection.yaml

    # Access with dot notation
    config.get("scheduler.vault_scan_interval_min", default=5)

    # Access env vars (merged from .env)
    config.env("ODOO_API_KEY")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = _PROJECT_ROOT / "config"
ENV_FILE = _PROJECT_ROOT / ".env"


def _load_yaml(path: Path) -> dict:
    """Load a YAML file.  Returns empty dict if file missing or yaml unavailable."""
    if not path.is_file():
        return {}
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except ImportError:
        # Fallback: parse simple key: value YAML without the yaml library
        return _parse_simple_yaml(path)
    except Exception:
        return {}


def _parse_simple_yaml(path: Path) -> dict:
    """Minimal YAML parser for flat and one-level-nested key: value files.

    Handles:
        key: value
        key: "quoted value"
        section:
          nested_key: value
    """
    result: dict[str, Any] = {}
    current_section: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        # Skip comments and blank lines
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())

        if ":" not in stripped:
            continue

        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if indent == 0:
            if value:
                result[key] = _coerce(value)
                current_section = None
            else:
                # Section header
                current_section = key
                result[current_section] = {}
        elif current_section is not None and indent > 0:
            result[current_section][key] = _coerce(value)

    return result


def _coerce(value: str) -> Any:
    """Convert string values to appropriate Python types."""
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    if value.lower() in ("null", "none", "~"):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict.  Does NOT override existing env vars."""
    env_vars: dict[str, str] = {}
    if not path.is_file():
        return env_vars

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            env_vars[key] = value
    return env_vars


class Config:
    """Unified configuration loaded from YAML files and .env."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._env_vars: dict[str, str] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all config files.  Safe to call multiple times (reloads)."""
        # Load .env into both our dict and os.environ
        self._env_vars = _load_env_file(ENV_FILE)
        for key, value in self._env_vars.items():
            if key not in os.environ:
                os.environ[key] = value

        # Load YAML configs
        gold = _load_yaml(CONFIG_DIR / "gold.yaml")
        social = _load_yaml(CONFIG_DIR / "social_accounts.yaml")
        odoo = _load_yaml(CONFIG_DIR / "odoo_connection.yaml")

        self._data = {
            **gold,  # top-level keys from gold.yaml (scheduler, error_logging, etc.)
            "social_accounts": social,
            "odoo": odoo,
        }
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    # ------------------------------------------------------------------
    # Access methods
    # ------------------------------------------------------------------

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Fetch a value using dot notation: ``config.get("scheduler.vault_scan_interval_min")``."""
        self._ensure_loaded()
        keys = dotted_key.split(".")
        node: Any = self._data
        for k in keys:
            if isinstance(node, dict):
                node = node.get(k)
            else:
                return default
            if node is None:
                return default
        return node

    def section(self, name: str) -> dict[str, Any]:
        """Return an entire config section as a dict."""
        self._ensure_loaded()
        val = self._data.get(name, {})
        return val if isinstance(val, dict) else {}

    def env(self, key: str, default: str | None = None) -> str | None:
        """Fetch an environment variable (checks .env + os.environ)."""
        self._ensure_loaded()
        return os.environ.get(key, self._env_vars.get(key, default))

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def scheduler(self) -> dict[str, Any]:
        return self.section("scheduler")

    @property
    def error_logging(self) -> dict[str, Any]:
        return self.section("error_logging")

    @property
    def social_accounts(self) -> dict[str, Any]:
        return self.section("social_accounts")

    @property
    def odoo(self) -> dict[str, Any]:
        return self.section("odoo")

    @property
    def briefing(self) -> dict[str, Any]:
        return self.section("briefing")

    @property
    def raw(self) -> dict[str, Any]:
        """Full merged config dict (read-only snapshot)."""
        self._ensure_loaded()
        return dict(self._data)

    def __repr__(self) -> str:
        self._ensure_loaded()
        sections = list(self._data.keys())
        return f"<Config sections={sections} env_vars={len(self._env_vars)}>"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
config = Config()
