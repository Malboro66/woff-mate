"""Bounded, path-keyed scheduling between Watchdog and file processing."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, Tuple

from ..campaign_namespace import canonical_windows_path

log = logging.getLogger("WoFFWatch")

Event = Tuple[str, str]


class _Executor(Protocol):
    def submit(self, fn: Callable[..., Any], *args: Any) -> Any: ...

    def shutdown(self, wait: bool = True) -> None: ...


@dataclass
class _PathState:
    pending: Optional[Event] = None


class EventScheduler:
    """Admit a bounded number of paths and retain one latest rerun per path."""

    # Kept explicit for an executable guard against relying on executor internals.
    executor_attributes_used = ("submit", "shutdown")

    def __init__(
        self,
        process: Callable[[str, str], Any],
        max_workers: int,
        max_pending_events: int,
        *,
        executor: Optional[_Executor] = None,
        retry_process: Optional[Callable[[str, str, Any], Any]] = None,
    ) -> None:
        if (
            isinstance(max_pending_events, bool)
            or not isinstance(max_pending_events, int)
            or max_pending_events <= 0
        ):
            raise ValueError("max_pending_events must be a positive integer")
        self._process = process
        self._retry_process = retry_process
        self._executor = executor or ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="woff-worker"
        )
        self._max_pending_events = max_pending_events
        self._states: Dict[str, _PathState] = {}
        self._lock = threading.Lock()
        self._changed = threading.Condition(self._lock)
        self._accepting = True
        self._metrics = {
            "queued": 0,
            "active": 0,
            "coalesced": 0,
            "rejected": 0,
            "retried": 0,
        }

    @property
    def admitted_paths(self) -> int:
        with self._lock:
            return len(self._states)

    @property
    def max_pending_events(self) -> int:
        return self._max_pending_events

    def metrics(self) -> Dict[str, int]:
        """Return an atomic snapshot of scheduler gauges and counters."""
        with self._lock:
            return dict(self._metrics)

    def submit(
        self, path: str, event_type: str, *, admission_timeout: float = 0.0
    ) -> bool:
        """Admit within a bounded deadline; return false on shutdown/saturation."""
        key = canonical_windows_path(path)
        event = (path, event_type)
        deadline = time.monotonic() + admission_timeout
        with self._changed:
            if not self._accepting:
                self._reject_locked("shutdown")
                return False
            state = self._states.get(key)
            if state is not None:
                if state.pending is None:
                    self._metrics["queued"] += 1
                state.pending = event
                self._metrics["coalesced"] += 1
                return True
            while len(self._states) >= self._max_pending_events:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._reject_locked("saturated")
                    return False
                self._changed.wait(remaining)
                if not self._accepting:
                    self._reject_locked("shutdown")
                    return False
            self._states[key] = _PathState()
            self._metrics["queued"] += 1
            try:
                self._executor.submit(self._run, key, event)
            except Exception:
                del self._states[key]
                self._metrics["queued"] -= 1
                self._metrics["rejected"] += 1
                log.warning(
                    "Filesystem event submission failed; admission state released"
                )
                raise
            return True

    def _reject_locked(self, reason: str) -> None:
        self._metrics["rejected"] += 1
        log.warning("Filesystem event rejected: scheduler %s", reason)

    def _run(self, key: str, event: Event) -> None:
        previous_result: Any = None
        is_retry = False
        while True:
            with self._lock:
                state = self._states[key]
                self._metrics["queued"] -= 1
                self._metrics["active"] += 1
            try:
                if is_retry and self._retry_process is not None:
                    previous_result = self._retry_process(*event, previous_result)
                else:
                    previous_result = self._process(*event)
            except Exception:
                log.exception("Unhandled filesystem event processing failure")
                previous_result = None
            with self._lock:
                state = self._states[key]
                self._metrics["active"] -= 1
                if state.pending is None:
                    del self._states[key]
                    self._changed.notify_all()
                    return
                event = state.pending
                state.pending = None
                self._metrics["retried"] += 1
                is_retry = True

    def shutdown(self) -> None:
        """Stop admission and wait for every accepted generation to finish."""
        with self._changed:
            self._accepting = False
            self._changed.notify_all()
        self._executor.shutdown(wait=True)

    def wait_for_paths(self, paths: list[str], timeout: float) -> bool:
        """Wait at most ``timeout`` for the named admitted paths to drain."""
        keys = {canonical_windows_path(path) for path in paths}
        deadline = time.monotonic() + timeout
        with self._changed:
            while keys.intersection(self._states):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._changed.wait(remaining)
            return True
