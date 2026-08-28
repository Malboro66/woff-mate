"""Bounded, path-keyed scheduling between Watchdog and file processing."""

from __future__ import annotations

import logging
import ntpath
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, Set, Tuple

from ..campaign_namespace import canonical_windows_path
from .deferred import DependencyKey, DependencyRetryPolicy
from .outcome import (
    PersistenceRetryPolicy,
    ProcessingOutcome,
    ProcessingReason,
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
    terminal_outcome: Optional[ProcessingOutcome] = None
    deferred_event: Optional[Event] = None
    deferred_outcome: Optional[ProcessingOutcome] = None
    dependency_baseline: int = 0
    dependency_attempts: int = 0
    deferred_since: Optional[float] = None
    retained_bytes: int = 0


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
        dependency_retry_process: Optional[
            Callable[[str, str, ProcessingOutcome], Any]
        ] = None,
        persistence_retry_policy: Optional[PersistenceRetryPolicy] = None,
        dependency_retry_policy: Optional[DependencyRetryPolicy] = None,
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
        self._dependency_retry_process = dependency_retry_process
        self._persistence_retry_policy = (
            persistence_retry_policy or PersistenceRetryPolicy()
        )
        self._dependency_retry_policy = (
            dependency_retry_policy or DependencyRetryPolicy()
        )
        self._executor = executor or ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="woff-worker"
        )
        self._max_pending_events = max_pending_events
        self._states: Dict[str, _PathState] = {}
        self._terminal_outcomes: OrderedDict[str, ProcessingOutcome] = (
            OrderedDict()
        )
        self._deferred_by_dependency: Dict[DependencyKey, Set[str]] = {}
        self._dependency_resolutions: OrderedDict[DependencyKey, int] = (
            OrderedDict()
        )
        self._dependency_resolution_sequence = 0
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
            "dependency_pending": 0,
            "dependency_deferred": 0,
            "dependency_replays": 0,
            "dependency_shutdown": 0,
            "dependency_expired": 0,
            "dependency_exhausted": 0,
            "dependency_saturated": 0,
            "dependency_retained_bytes": 0,
        }
        self._dependency_monitor: Optional[threading.Thread] = None

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

    @property
    def dependency_retry_policy(self) -> DependencyRetryPolicy:
        return self._dependency_retry_policy

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
            terminal_outcome = self._terminal_outcomes.pop(key, None)
            self._states[key] = _PathState(
                terminal_outcome=terminal_outcome
            )
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

    def _discard_pending_locked(self, state: _PathState) -> None:
        """Release the queued gauge when a deferred path terminates."""
        if state.pending is None:
            return
        state.pending = None
        self._metrics["queued"] -= 1

    @staticmethod
    def _take_pending_locked(state: _PathState) -> Event:
        """Start a coalesced generation with a fresh dependency budget."""
        pending = state.pending
        if pending is None:
            raise RuntimeError("pending event required")
        state.pending = None
        state.dependency_attempts = 0
        state.deferred_since = None
        return pending

    def _run(
        self,
        key: str,
        event: Event,
        dependency_outcome: Optional[ProcessingOutcome] = None,
    ) -> None:
        state = self._states[key]
        previous_result: Any = dependency_outcome or state.terminal_outcome
        coalesced_retry = state.terminal_outcome is not None
        persistence_retry = False
        dependency_retry = dependency_outcome is not None
        persistence_attempts = 0
        while True:
            with self._lock:
                state.dependency_baseline = (
                    self._dependency_resolution_sequence
                )
                self._metrics["queued"] -= 1
                self._metrics["active"] += 1
            try:
                if dependency_retry:
                    if (
                        self._dependency_retry_process is None
                        or not isinstance(previous_result, ProcessingOutcome)
                    ):
                        raise RuntimeError(
                            "dependency retry requires a typed retry callback"
                        )
                    previous_result = self._dependency_retry_process(
                        *event, previous_result
                    )
                elif persistence_retry:
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
                    retry_reference = state.terminal_outcome or previous_result
                    previous_result = self._retry_process(
                        *event, retry_reference
                    )
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
                        if (
                            state.terminal_outcome is not None
                            and outcome.generation
                            != state.terminal_outcome.generation
                        ):
                            state.terminal_outcome = None
                    elif outcome.status is ProcessingStatus.PERMANENT_REJECTION:
                        self._metrics["permanent_rejections"] += 1
                    if (
                        was_persistence_retry
                        and outcome.status
                        in {ProcessingStatus.SUCCESS, ProcessingStatus.UNCHANGED}
                    ):
                        self._metrics["successful_replays"] += 1

                if (
                    outcome is not None
                    and outcome.resolved_dependency is not None
                    and outcome.status
                    in {ProcessingStatus.SUCCESS, ProcessingStatus.UNCHANGED}
                ):
                    self._resolve_dependency_locked(
                        outcome.resolved_dependency
                    )

                if (
                    outcome is not None
                    and outcome.status is ProcessingStatus.DEPENDENCY_PENDING
                ):
                    self._defer_dependency_locked(key, event, state, outcome)
                    self._changed.notify_all()
                    return

                if (
                    outcome is not None
                    and outcome.status is not ProcessingStatus.TRANSIENT_FAILURE
                    and outcome.reason is not ProcessingReason.RETRY_TERMINATED
                ):
                    state.terminal_outcome = None

                if state.pending is not None and (
                    outcome is None
                    or outcome.status is not ProcessingStatus.TRANSIENT_FAILURE
                ):
                    event = self._take_pending_locked(state)
                    self._metrics["retried"] += 1
                    persistence_attempts = 0
                    coalesced_retry = True
                    persistence_retry = False
                    dependency_retry = False
                    continue

                if (
                    outcome is None
                    or outcome.status is not ProcessingStatus.TRANSIENT_FAILURE
                ):
                    if state.terminal_outcome is not None:
                        self._remember_terminal_locked(
                            key, state.terminal_outcome
                        )
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
                    state.terminal_outcome = outcome
                    if state.pending is not None:
                        event = self._take_pending_locked(state)
                        self._metrics["retried"] += 1
                        persistence_attempts = 0
                        coalesced_retry = True
                        persistence_retry = False
                        dependency_retry = False
                        continue
                    self._remember_terminal_locked(key, outcome)
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
                        event = self._take_pending_locked(state)
                        self._metrics["retried"] += 1
                        persistence_attempts = 0
                        coalesced_retry = True
                        persistence_retry = False
                        dependency_retry = False
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
                            event = self._take_pending_locked(state)
                            self._metrics["retried"] += 1
                            persistence_attempts = 0
                            coalesced_retry = True
                            persistence_retry = False
                            dependency_retry = False
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
                        dependency_retry = False
                        break
                    self._changed.wait(remaining)

    def _defer_dependency_locked(
        self,
        key: str,
        event: Event,
        state: _PathState,
        outcome: ProcessingOutcome,
    ) -> None:
        dependency_key = outcome.dependency_key
        retry_input = outcome.retry_input
        if dependency_key is None or retry_input is None:
            raise RuntimeError(
                "pending dependency requires retained input and a binding key"
            )
        if not self._accepting:
            self._metrics["dependency_shutdown"] += 1
            self._log_dependency_terminal(
                "Deferred dependency cancelled at shutdown", event, outcome
            )
            self._discard_pending_locked(state)
            del self._states[key]
            return
        now = time.monotonic()
        if state.deferred_since is None:
            state.deferred_since = now
        state.dependency_attempts += 1
        if state.dependency_attempts >= self._dependency_retry_policy.max_attempts:
            self._metrics["dependency_exhausted"] += 1
            self._log_dependency_terminal(
                "Deferred dependency exhausted",
                event,
                outcome,
                state.dependency_attempts,
            )
            self._discard_pending_locked(state)
            del self._states[key]
            return
        if (
            now - state.deferred_since
            >= self._dependency_retry_policy.max_age_seconds
        ):
            self._metrics["dependency_expired"] += 1
            self._log_dependency_terminal(
                "Deferred dependency expired",
                event,
                outcome,
                state.dependency_attempts,
            )
            self._discard_pending_locked(state)
            del self._states[key]
            return
        resolution_sequence = self._dependency_resolutions.get(
            dependency_key, 0
        )
        if resolution_sequence > state.dependency_baseline:
            self._metrics["queued"] += 1
            self._metrics["retried"] += 1
            self._metrics["dependency_replays"] += 1
            try:
                self._executor.submit(self._run, key, event, outcome)
            except Exception:
                self._metrics["queued"] -= 1
                self._metrics["rejected"] += 1
                self._metrics["submission_failures"] += 1
                self._discard_pending_locked(state)
                del self._states[key]
                log.warning(
                    "Deferred dependency submission failed; state released"
                )
            return
        retained_bytes = len(retry_input.snapshot.data)
        if (
            self._metrics["dependency_retained_bytes"] + retained_bytes
            > self._dependency_retry_policy.max_retained_bytes
        ):
            self._metrics["dependency_saturated"] += 1
            self._log_dependency_memory_terminal(
                event,
                outcome,
                self._metrics["dependency_retained_bytes"],
                self._dependency_retry_policy.max_retained_bytes,
            )
            self._discard_pending_locked(state)
            del self._states[key]
            return
        state.deferred_event = event
        state.deferred_outcome = outcome
        state.retained_bytes = retained_bytes
        self._deferred_by_dependency.setdefault(
            dependency_key, set()
        ).add(key)
        self._metrics["dependency_pending"] += 1
        self._metrics["dependency_deferred"] += 1
        self._metrics["dependency_retained_bytes"] += state.retained_bytes
        try:
            self._start_dependency_monitor_locked()
        except Exception:
            waiting = self._deferred_by_dependency.get(dependency_key)
            if waiting is not None:
                waiting.discard(key)
                if not waiting:
                    del self._deferred_by_dependency[dependency_key]
            self._metrics["dependency_pending"] -= 1
            self._metrics["dependency_retained_bytes"] -= state.retained_bytes
            state.deferred_event = None
            state.deferred_outcome = None
            state.retained_bytes = 0
            self._metrics["rejected"] += 1
            self._metrics["submission_failures"] += 1
            self._discard_pending_locked(state)
            del self._states[key]
            log.warning(
                "Deferred dependency monitor unavailable; state released"
            )

    def _start_dependency_monitor_locked(self) -> None:
        if self._dependency_monitor is not None:
            return
        monitor = threading.Thread(
            target=self._monitor_dependencies,
            name="woff-dependency-monitor",
            daemon=True,
        )
        monitor.start()
        self._dependency_monitor = monitor

    def _cancel_deferred_locked(
        self, key: str, state: _PathState
    ) -> None:
        outcome = state.deferred_outcome
        event = state.deferred_event
        if outcome is None or event is None:
            return
        dependency_key = outcome.dependency_key
        if dependency_key is not None:
            waiting = self._deferred_by_dependency.get(dependency_key)
            if waiting is not None:
                waiting.discard(key)
                if not waiting:
                    del self._deferred_by_dependency[dependency_key]
        self._metrics["dependency_pending"] -= 1
        self._metrics["dependency_retained_bytes"] -= state.retained_bytes
        state.retained_bytes = 0
        self._metrics["dependency_shutdown"] += 1
        self._log_dependency_terminal(
            "Deferred dependency cancelled at shutdown", event, outcome
        )
        self._discard_pending_locked(state)
        del self._states[key]

    def _expire_deferred_locked(
        self, key: str, state: _PathState
    ) -> None:
        outcome = state.deferred_outcome
        event = state.deferred_event
        if outcome is None or event is None:
            return
        dependency_key = outcome.dependency_key
        if dependency_key is not None:
            waiting = self._deferred_by_dependency.get(dependency_key)
            if waiting is not None:
                waiting.discard(key)
                if not waiting:
                    del self._deferred_by_dependency[dependency_key]
        self._metrics["dependency_pending"] -= 1
        self._metrics["dependency_retained_bytes"] -= state.retained_bytes
        self._metrics["dependency_expired"] += 1
        self._log_dependency_terminal(
            "Deferred dependency expired",
            event,
            outcome,
            state.dependency_attempts,
        )
        self._discard_pending_locked(state)
        del self._states[key]

    def _monitor_dependencies(self) -> None:
        while True:
            with self._changed:
                if not self._accepting:
                    return
                deadlines = [
                    state.deferred_since
                    + self._dependency_retry_policy.max_age_seconds
                    for state in self._states.values()
                    if state.deferred_outcome is not None
                    and state.deferred_since is not None
                ]
                if not deadlines:
                    self._changed.wait()
                    continue
                remaining = min(deadlines) - time.monotonic()
                if remaining > 0:
                    self._changed.wait(remaining)
                    continue
                now = time.monotonic()
                for key, state in list(self._states.items()):
                    if (
                        state.deferred_outcome is not None
                        and state.deferred_since is not None
                        and now - state.deferred_since
                        >= self._dependency_retry_policy.max_age_seconds
                    ):
                        self._expire_deferred_locked(key, state)
                self._changed.notify_all()

    def _resolve_dependency_locked(
        self, dependency_key: DependencyKey
    ) -> None:
        self._dependency_resolution_sequence += 1
        self._dependency_resolutions[dependency_key] = (
            self._dependency_resolution_sequence
        )
        self._dependency_resolutions.move_to_end(dependency_key)
        while len(self._dependency_resolutions) > self._max_pending_events:
            self._dependency_resolutions.popitem(last=False)
        self._release_dependency_locked(dependency_key)

    def _release_dependency_locked(
        self, dependency_key: DependencyKey
    ) -> None:
        waiting = self._deferred_by_dependency.pop(dependency_key, set())
        for key in waiting:
            state = self._states.get(key)
            if (
                state is None
                or state.deferred_event is None
                or state.deferred_outcome is None
            ):
                continue
            event = state.deferred_event
            outcome = state.deferred_outcome
            state.deferred_event = None
            state.deferred_outcome = None
            self._metrics["dependency_pending"] -= 1
            self._metrics["dependency_retained_bytes"] -= state.retained_bytes
            state.retained_bytes = 0
            self._metrics["queued"] += 1
            self._metrics["retried"] += 1
            self._metrics["dependency_replays"] += 1
            try:
                self._executor.submit(self._run, key, event, outcome)
            except Exception:
                self._metrics["queued"] -= 1
                self._metrics["rejected"] += 1
                self._metrics["submission_failures"] += 1
                self._discard_pending_locked(state)
                del self._states[key]
                log.warning(
                    "Deferred dependency submission failed; state released"
                )

    def _remember_terminal_locked(
        self, key: str, outcome: ProcessingOutcome
    ) -> None:
        """Retain one exhausted generation per recently active path."""
        self._terminal_outcomes[key] = outcome
        self._terminal_outcomes.move_to_end(key)
        while len(self._terminal_outcomes) > self._max_pending_events:
            self._terminal_outcomes.popitem(last=False)

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

    @staticmethod
    def _log_dependency_terminal(
        message: str,
        event: Event,
        outcome: ProcessingOutcome,
        attempts: Optional[int] = None,
    ) -> None:
        slot = outcome.dependency_key[1] if outcome.dependency_key else 0
        if attempts is not None:
            log.error(
                "%s: source=%s category=%s slot=%d attempts=%d",
                message,
                _safe_filename(event[0]),
                outcome.reason.value,
                slot,
                attempts,
            )
            return
        log.error(
            "%s: source=%s category=%s slot=%d",
            message,
            _safe_filename(event[0]),
            outcome.reason.value,
            slot,
        )

    @staticmethod
    def _log_dependency_memory_terminal(
        event: Event,
        outcome: ProcessingOutcome,
        retained_bytes: int,
        limit_bytes: int,
    ) -> None:
        slot = outcome.dependency_key[1] if outcome.dependency_key else 0
        log.error(
            "Deferred dependency memory limit reached: "
            "source=%s category=%s slot=%d retained_bytes=%d limit_bytes=%d",
            _safe_filename(event[0]),
            outcome.reason.value,
            slot,
            retained_bytes,
            limit_bytes,
        )

    def shutdown(self) -> None:
        """Stop admission and wait for every accepted generation to finish."""
        with self._changed:
            self._accepting = False
            for key, state in list(self._states.items()):
                if state.deferred_outcome is not None:
                    self._cancel_deferred_locked(key, state)
            dependency_monitor = self._dependency_monitor
            self._changed.notify_all()
        self._executor.shutdown(wait=True)
        if dependency_monitor is not None:
            dependency_monitor.join()

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
