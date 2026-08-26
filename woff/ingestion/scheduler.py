"""Bounded, path-keyed scheduling between Watchdog and file processing."""

from __future__ import annotations

import logging
import ntpath
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, Tuple

from ..campaign_namespace import canonical_windows_path
from .outcome import (
    PersistenceRetryPolicy,
    ProcessingOutcome,
    ProcessingStatus,
)

log = logging.getLogger("WoFFWatch")

Event = Tuple[str, str]


def _safe_filename(path: str) -> str:
    """Return only the final component for native or Windows-style paths."""
    return ntpath.basename(path.replace("/", "\\"))


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
        persistence_retry_process: Optional[
            Callable[[str, str, ProcessingOutcome], Any]
        ] = None,
        persistence_retry_policy: Optional[PersistenceRetryPolicy] = None,
    ) -> None:
        if (
            isinstance(max_pending_events, bool)
            or not isinstance(max_pending_events, int)
            or max_pending_events <= 0
        ):
            raise ValueError("max_pending_events must be a positive integer")
        self._process = process
        self._retry_process = retry_process
        self._persistence_retry_process = persistence_retry_process
        self._persistence_retry_policy = (
            persistence_retry_policy or PersistenceRetryPolicy()
        )
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
            "saturated": 0,
            "shutdown_rejected": 0,
            "submission_failures": 0,
            "permanent_rejections": 0,
            "transient_failures": 0,
            "transient_retries": 0,
            "successful_replays": 0,
            "retry_pending": 0,
            "retry_exhausted": 0,
            "retry_shutdown": 0,
            "superseded_retries": 0,
        }

    @property
    def admitted_paths(self) -> int:
        with self._lock:
            return len(self._states)

    @property
    def max_pending_events(self) -> int:
        return self._max_pending_events

    @property
    def accepting(self) -> bool:
        with self._lock:
            return self._accepting

    @property
    def persistence_retry_policy(self) -> PersistenceRetryPolicy:
        return self._persistence_retry_policy

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
                self._changed.notify_all()
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
                self._metrics["submission_failures"] += 1
                log.warning(
                    "Filesystem event submission failed; admission state released"
                )
                raise
            return True

    def _reject_locked(self, reason: str) -> None:
        self._metrics["rejected"] += 1
        if reason == "saturated":
            self._metrics["saturated"] += 1
        elif reason == "shutdown":
            self._metrics["shutdown_rejected"] += 1
        log.warning("Filesystem event rejected: scheduler %s", reason)

    def _run(self, key: str, event: Event) -> None:
        previous_result: Any = None
        coalesced_retry = False
        persistence_retry = False
        persistence_attempts = 0
        while True:
            with self._lock:
                self._metrics["queued"] -= 1
                self._metrics["active"] += 1
            try:
                if persistence_retry:
                    if (
                        self._persistence_retry_process is None
                        or not isinstance(previous_result, ProcessingOutcome)
                    ):
                        raise RuntimeError(
                            "persistence retry requires a typed retry callback"
                        )
                    previous_result = self._persistence_retry_process(
                        *event, previous_result
                    )
                elif coalesced_retry and self._retry_process is not None:
                    previous_result = self._retry_process(*event, previous_result)
                else:
                    previous_result = self._process(*event)
            except Exception:
                log.exception("Unhandled filesystem event processing failure")
                previous_result = None
            with self._changed:
                state = self._states[key]
                self._metrics["active"] -= 1

                outcome = (
                    previous_result
                    if isinstance(previous_result, ProcessingOutcome)
                    else None
                )
                was_persistence_retry = persistence_retry
                if outcome is not None:
                    if outcome.status is ProcessingStatus.TRANSIENT_FAILURE:
                        self._metrics["transient_failures"] += 1
                        persistence_attempts += 1
                    elif outcome.status is ProcessingStatus.PERMANENT_REJECTION:
                        self._metrics["permanent_rejections"] += 1
                    if (
                        was_persistence_retry
                        and outcome.status
                        in {ProcessingStatus.SUCCESS, ProcessingStatus.UNCHANGED}
                    ):
                        self._metrics["successful_replays"] += 1

                if state.pending is not None and (
                    outcome is None
                    or outcome.status is not ProcessingStatus.TRANSIENT_FAILURE
                ):
                    event = state.pending
                    state.pending = None
                    self._metrics["retried"] += 1
                    persistence_attempts = 0
                    coalesced_retry = True
                    persistence_retry = False
                    continue

                if (
                    outcome is None
                    or outcome.status is not ProcessingStatus.TRANSIENT_FAILURE
                ):
                    del self._states[key]
                    self._changed.notify_all()
                    return

                if (
                    self._persistence_retry_process is None
                    or persistence_attempts
                    >= self._persistence_retry_policy.max_attempts
                ):
                    self._metrics["retry_exhausted"] += 1
                    self._log_retry_terminal(
                        "Persistence retry exhausted",
                        event,
                        outcome,
                        persistence_attempts,
                    )
                    if state.pending is not None:
                        event = state.pending
                        state.pending = None
                        self._metrics["retried"] += 1
                        persistence_attempts = 0
                        coalesced_retry = True
                        persistence_retry = False
                        continue
                    del self._states[key]
                    self._changed.notify_all()
                    return

                if not self._accepting:
                    self._metrics["retry_shutdown"] += 1
                    self._log_retry_terminal(
                        "Persistence retry cancelled at shutdown",
                        event,
                        outcome,
                        persistence_attempts,
                    )
                    if state.pending is not None:
                        event = state.pending
                        state.pending = None
                        self._metrics["retried"] += 1
                        persistence_attempts = 0
                        coalesced_retry = True
                        persistence_retry = False
                        continue
                    del self._states[key]
                    self._changed.notify_all()
                    return

                delay = self._persistence_retry_policy.delay_after_failure(
                    persistence_attempts
                )
                deadline = time.monotonic() + delay
                self._metrics["retry_pending"] += 1
                while True:
                    if not self._accepting:
                        self._metrics["retry_pending"] -= 1
                        self._metrics["retry_shutdown"] += 1
                        self._log_retry_terminal(
                            "Persistence retry cancelled at shutdown",
                            event,
                            outcome,
                            persistence_attempts,
                        )
                        if state.pending is not None:
                            event = state.pending
                            state.pending = None
                            self._metrics["retried"] += 1
                            persistence_attempts = 0
                            coalesced_retry = True
                            persistence_retry = False
                            break
                        del self._states[key]
                        self._changed.notify_all()
                        return
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        self._metrics["retry_pending"] -= 1
                        self._metrics["queued"] += 1
                        self._metrics["retried"] += 1
                        self._metrics["transient_retries"] += 1
                        coalesced_retry = False
                        persistence_retry = True
                        break
                    self._changed.wait(remaining)

    @staticmethod
    def _log_retry_terminal(
        message: str,
        event: Event,
        outcome: ProcessingOutcome,
        attempts: int,
    ) -> None:
        log.error(
            "%s: source=%s category=%s attempts=%d",
            message,
            _safe_filename(event[0]),
            outcome.reason.value,
            attempts,
        )

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
