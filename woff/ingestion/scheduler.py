"""Bounded, path-keyed scheduling between Watchdog and file processing."""

from __future__ import annotations

import logging
import ntpath
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, Tuple

log = logging.getLogger("WoFFWatch")

Event = Tuple[str, str]


class _Executor(Protocol):
    def submit(self, fn: Callable[..., Any], *args: Any) -> Any: ...

    def shutdown(self, wait: bool = True) -> None: ...


def canonical_windows_path(path: str) -> str:
    """Return a Windows identity key while leaving the submitted path untouched.

    Watchdog's path remains the path supplied to the processor.  This function is
    used only for identity so that drive-letter, separator, case, UNC, and Win32
    extended-length spellings cannot occupy separate scheduler slots.
    """
    normalized = path.replace("/", "\\")
    lowered = normalized.lower()
    if lowered.startswith("\\\\?\\unc\\"):
        normalized = "\\\\" + normalized[8:]
    elif lowered.startswith("\\\\?\\"):
        normalized = normalized[4:]
    return ntpath.normcase(ntpath.normpath(normalized))


@dataclass
class _PathState:
    pending: Optional[Event] = None


class EventScheduler:
    """Admit a bounded number of paths and retain one latest rerun per path."""

    # Kept explicit for an executable guard against relying on executor internals.
    executor_attributes_used = ("submit", "shutdown")

    def __init__(
        self,
        process: Callable[[str, str], None],
        max_workers: int,
        max_pending_events: int,
        *,
        executor: Optional[_Executor] = None,
    ) -> None:
        if (
            isinstance(max_pending_events, bool)
            or not isinstance(max_pending_events, int)
            or max_pending_events <= 0
        ):
            raise ValueError("max_pending_events must be a positive integer")
        self._process = process
        self._executor = executor or ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="woff-worker"
        )
        self._max_pending_events = max_pending_events
        self._states: Dict[str, _PathState] = {}
        self._lock = threading.Lock()
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

    def submit(self, path: str, event_type: str) -> bool:
        """Admit without blocking; return false when shutdown or capacity rejects."""
        key = canonical_windows_path(path)
        event = (path, event_type)
        with self._lock:
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
            if len(self._states) >= self._max_pending_events:
                self._reject_locked("saturated")
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
        while True:
            with self._lock:
                state = self._states[key]
                self._metrics["queued"] -= 1
                self._metrics["active"] += 1
            try:
                self._process(*event)
            except Exception:
                log.exception("Unhandled filesystem event processing failure")
            with self._lock:
                state = self._states[key]
                self._metrics["active"] -= 1
                if state.pending is None:
                    del self._states[key]
                    return
                event = state.pending
                state.pending = None
                self._metrics["retried"] += 1

    def shutdown(self) -> None:
        """Stop admission and wait for every accepted generation to finish."""
        with self._lock:
            self._accepting = False
        self._executor.shutdown(wait=True)
