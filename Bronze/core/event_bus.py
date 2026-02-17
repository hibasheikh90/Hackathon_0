"""
Gold Tier — Event Bus
=====================
In-process pub/sub system connecting all Gold Tier modules.

Usage:
    from core.event_bus import bus

    # Subscribe to events
    bus.on("vault.task.new", my_handler)
    bus.on("odoo.*", my_wildcard_handler)   # wildcards supported

    # Emit events
    bus.emit("vault.task.new", {"file": "task.md", "source": "inbox"})

    # Unsubscribe
    bus.off("vault.task.new", my_handler)

Events are processed synchronously in the order handlers were registered.
Handler exceptions are caught and forwarded to the error logger (if available).
"""

from __future__ import annotations

import fnmatch
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

# Type alias for handler functions
Handler = Callable[[dict[str, Any]], None]


@dataclass
class _EventRecord:
    """Internal record of an emitted event (for replay / debugging)."""
    event: str
    data: dict[str, Any]
    timestamp: float
    handler_count: int = 0
    errors: list[str] = field(default_factory=list)


class EventBus:
    """Simple synchronous pub/sub event bus with wildcard support."""

    def __init__(self, max_history: int = 200) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._wildcard_handlers: list[tuple[str, Handler]] = []
        self._history: list[_EventRecord] = []
        self._max_history = max_history
        self._lock = threading.Lock()
        self._error_logger = None  # set after error_logger is initialised

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_error_logger(self, logger) -> None:
        """Attach the centralized error logger (avoids circular import)."""
        self._error_logger = logger

    def on(self, event_pattern: str, handler: Handler) -> None:
        """Subscribe *handler* to events matching *event_pattern*.

        Patterns can be exact (``"vault.task.new"``) or use ``*`` /
        ``**`` wildcards (``"odoo.*"``, ``"social.**"``).
        """
        with self._lock:
            if "*" in event_pattern or "?" in event_pattern:
                self._wildcard_handlers.append((event_pattern, handler))
            else:
                self._handlers[event_pattern].append(handler)

    def off(self, event_pattern: str, handler: Handler) -> bool:
        """Remove *handler* from *event_pattern*.  Returns True if found."""
        with self._lock:
            if "*" in event_pattern or "?" in event_pattern:
                before = len(self._wildcard_handlers)
                self._wildcard_handlers = [
                    (p, h) for p, h in self._wildcard_handlers
                    if not (p == event_pattern and h is handler)
                ]
                return len(self._wildcard_handlers) < before

            handlers = self._handlers.get(event_pattern, [])
            try:
                handlers.remove(handler)
                return True
            except ValueError:
                return False

    def emit(self, event: str, data: dict[str, Any] | None = None) -> _EventRecord:
        """Publish *event* with optional *data* dict.

        All matching handlers are called synchronously.  Exceptions in
        handlers are caught, logged, and do **not** prevent other handlers
        from running.
        """
        data = data or {}
        record = _EventRecord(event=event, data=data, timestamp=time.time())

        with self._lock:
            targets: list[Handler] = list(self._handlers.get(event, []))
            for pattern, handler in self._wildcard_handlers:
                if fnmatch.fnmatch(event, pattern):
                    targets.append(handler)

        for handler in targets:
            try:
                handler(data)
                record.handler_count += 1
            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                record.errors.append(error_msg)
                self._report_error(event, handler, exc)

        with self._lock:
            self._history.append(record)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        return record

    def handlers_for(self, event: str) -> list[Handler]:
        """Return all handlers that would fire for *event* (for testing)."""
        with self._lock:
            result = list(self._handlers.get(event, []))
            for pattern, handler in self._wildcard_handlers:
                if fnmatch.fnmatch(event, pattern):
                    result.append(handler)
        return result

    def clear(self) -> None:
        """Remove all handlers and history (mainly for tests)."""
        with self._lock:
            self._handlers.clear()
            self._wildcard_handlers.clear()
            self._history.clear()

    @property
    def history(self) -> list[_EventRecord]:
        """Recent event history (read-only copy)."""
        with self._lock:
            return list(self._history)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _report_error(self, event: str, handler: Handler, exc: Exception) -> None:
        """Forward handler errors to the error logger if available."""
        handler_name = getattr(handler, "__name__", repr(handler))
        if self._error_logger:
            self._error_logger.log_error(
                source="event_bus",
                error=exc,
                context={"event": event, "handler": handler_name},
            )
        else:
            # Fallback: print to stderr so errors are never silently lost
            import sys
            print(
                f"[EVENT_BUS ERROR] {event} -> {handler_name}: {exc}",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Module-level singleton — import this from anywhere
# ---------------------------------------------------------------------------
bus = EventBus()
