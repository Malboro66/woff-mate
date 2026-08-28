from concurrent.futures import ThreadPoolExecutor
import threading
import time
import unittest
from typing import Any, Callable
from unittest import mock

from ..ingestion import outcome as outcome_module
from ..ingestion.deferred import DependencyRetryPolicy
from ..ingestion.outcome import (
    ProcessingOutcome,
    ProcessingReason,
    VerifiedProcessingInput,
)
from ..ingestion.scheduler import EventScheduler
from ..ingestion.snapshot import (
    FileGeneration,
    StableFileSnapshot,
)


DEPENDENCY_KEY = ("root-v1:synthetic", 1)


class _ReplayFailingExecutor:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._submissions = 0

    def submit(self, fn: Callable[..., Any], *args: Any) -> Any:
        self._submissions += 1
        if self._submissions == 3:
            raise RuntimeError("synthetic dependency replay submission failure")
        return self._executor.submit(fn, *args)

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)


def _pending_outcome(
    path: str,
    data: bytes = b"verified",
    dependency_key: tuple[str, int] = DEPENDENCY_KEY,
) -> ProcessingOutcome:
    generation = FileGeneration(1, 2, len(data), 3, 4, "a" * 64)
    snapshot = StableFileSnapshot(
        data=data,
        path=path,
        name=path.rsplit("/", 1)[-1],
        generation=generation,
        attempts=2,
    )
    return ProcessingOutcome.dependency_pending(
        VerifiedProcessingInput(snapshot), dependency_key
    )


def _resolved_outcome(
    path: str, dependency_key: tuple[str, int] = DEPENDENCY_KEY
) -> ProcessingOutcome:
    generation = _retained_input(_pending_outcome(path)).snapshot.generation
    return ProcessingOutcome.success(
        generation,
        resolved_dependency=dependency_key,
    )


def _retained_input(outcome: ProcessingOutcome) -> VerifiedProcessingInput:
    if outcome.retry_input is None:
        raise AssertionError("test outcome must retain verified input")
    return outcome.retry_input


def _wait_for_metric(
    scheduler: EventScheduler, name: str, expected: int
) -> bool:
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if scheduler.metrics().get(name) == expected:
            return True
        time.sleep(0.001)
    return False


class TestDeferredIngestion(unittest.TestCase):
    def test_identity_pending_reason_requires_retained_dependency_input(self):
        with self.assertRaises(ValueError):
            ProcessingOutcome.permanent(ProcessingReason.IDENTITY_PENDING)

        retained = _retained_input(
            _pending_outcome("/campaign/Pilot1Log.txt")
        )
        for dependency_key in (("", 1), ("root-v1:a", 0)):
            with self.subTest(dependency_key=dependency_key):
                with self.assertRaises(ValueError):
                    ProcessingOutcome.dependency_pending(
                        retained, dependency_key
                    )

    def test_dependency_retry_policy_rejects_unbounded_values(self):
        default = DependencyRetryPolicy()
        self.assertEqual(default.max_attempts, 4)
        self.assertEqual(default.max_age_seconds, 300.0)
        self.assertEqual(default.max_retained_bytes, 64 * 1024 * 1024)

        invalid = (
            lambda: DependencyRetryPolicy(max_attempts=0),
            lambda: DependencyRetryPolicy(max_attempts=True),
            lambda: DependencyRetryPolicy(max_age_seconds=0),
            lambda: DependencyRetryPolicy(max_age_seconds=float("inf")),
            lambda: DependencyRetryPolicy(max_retained_bytes=0),
            lambda: DependencyRetryPolicy(max_retained_bytes=True),
        )
        for factory in invalid:
            with self.subTest(factory=factory):
                with self.assertRaises(ValueError):
                    factory()

    def test_deferred_paths_share_the_scheduler_count_bound(self):
        first = "/private/campaign/Pilot1Log.txt"
        second = "/private/campaign/Pilot2Log.txt"
        scheduler = EventScheduler(
            lambda path, _event_type: _pending_outcome(
                path,
                dependency_key=(
                    DEPENDENCY_KEY[0],
                    1 if path == first else 2,
                ),
            ),
            max_workers=1,
            max_pending_events=1,
        )
        self.assertTrue(scheduler.submit(first, "created"))
        self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 1))

        with self.assertLogs("WoFFWatch", level="WARNING") as records:
            self.assertFalse(scheduler.submit(second, "created"))

        self.assertEqual(scheduler.admitted_paths, 1)
        self.assertEqual(scheduler.metrics()["saturated"], 1)
        self.assertEqual(
            records.output,
            [
                "WARNING:WoFFWatch:Filesystem event rejected: "
                "scheduler saturated"
            ],
        )
        with self.assertLogs("WoFFWatch", level="ERROR"):
            scheduler.shutdown()

    def test_shutdown_cancels_retained_dependency_and_releases_capacity(self):
        path = "/private/campaign/Pilot1Log.txt"
        scheduler = EventScheduler(
            lambda *_: _pending_outcome(path),
            max_workers=1,
            max_pending_events=2,
        )
        self.assertTrue(scheduler.submit(path, "created"))
        self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 1))
        self.assertTrue(scheduler.submit(path, "modified"))

        with self.assertLogs("WoFFWatch", level="ERROR") as records:
            scheduler.shutdown()

        self.assertEqual(scheduler.admitted_paths, 0)
        self.assertEqual(scheduler.metrics()["queued"], 0)
        self.assertEqual(scheduler.metrics()["dependency_pending"], 0)
        self.assertEqual(scheduler.metrics()["dependency_shutdown"], 1)
        self.assertEqual(
            records.output,
            [
                "ERROR:WoFFWatch:Deferred dependency cancelled at shutdown: "
                "source=Pilot1Log.txt category=identity-pending slot=1"
            ],
        )

    def test_missing_dossier_expires_with_one_final_diagnostic(self):
        policy = DependencyRetryPolicy(
            max_attempts=4,
            max_age_seconds=0.02,
            max_retained_bytes=1024,
        )
        path = "/private/campaign/Pilot1Log.txt"
        scheduler = EventScheduler(
            lambda *_: _pending_outcome(path),
            max_workers=1,
            max_pending_events=2,
            dependency_retry_policy=policy,
        )

        with self.assertLogs("WoFFWatch", level="ERROR") as records:
            self.assertTrue(scheduler.submit(path, "created"))
            self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 1))
            self.assertTrue(scheduler.submit(path, "modified"))
            self.assertTrue(scheduler.wait_for_paths([path], 1.0))
            scheduler.shutdown()

        self.assertEqual(scheduler.admitted_paths, 0)
        self.assertEqual(scheduler.metrics()["queued"], 0)
        self.assertEqual(scheduler.metrics()["dependency_pending"], 0)
        self.assertEqual(scheduler.metrics()["dependency_expired"], 1)
        self.assertEqual(
            records.output,
            [
                "ERROR:WoFFWatch:Deferred dependency expired: "
                "source=Pilot1Log.txt category=identity-pending slot=1 "
                "attempts=1"
            ],
        )

    def test_retained_snapshot_bytes_are_globally_bounded(self):
        policy = DependencyRetryPolicy(
            max_attempts=4,
            max_age_seconds=300.0,
            max_retained_bytes=4,
        )
        first = "/private/campaign/Pilot1Log.txt"
        second = "/private/campaign/Pilot2Log.txt"

        def process(path, _event_type):
            slot = 1 if path == first else 2
            return _pending_outcome(
                path,
                data=b"four",
                dependency_key=("root-v1:synthetic", slot),
            )

        scheduler = EventScheduler(
            process,
            max_workers=1,
            max_pending_events=2,
            dependency_retry_policy=policy,
        )
        self.assertTrue(scheduler.submit(first, "created"))
        self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 1))

        with self.assertLogs("WoFFWatch", level="ERROR") as records:
            self.assertTrue(scheduler.submit(second, "created"))
            self.assertTrue(scheduler.wait_for_paths([second], 1.0))

        metrics = scheduler.metrics()
        self.assertEqual(metrics["dependency_pending"], 1)
        self.assertEqual(metrics["dependency_retained_bytes"], 4)
        self.assertEqual(metrics["dependency_saturated"], 1)
        self.assertEqual(
            records.output,
            [
                "ERROR:WoFFWatch:Deferred dependency memory limit reached: "
                "source=Pilot2Log.txt category=identity-pending slot=2 "
                "retained_bytes=4 limit_bytes=4"
            ],
        )
        with self.assertLogs("WoFFWatch", level="ERROR"):
            scheduler.shutdown()

    def test_dependency_replay_exhausts_after_four_total_attempts(self):
        source_path = "/private/campaign/Pilot1Log.txt"
        dossier_path = "/private/campaign/Pilot1Dossier.txt"
        replayed_snapshots = []

        def process(path, _event_type):
            if path == dossier_path:
                return _resolved_outcome(path)
            return _pending_outcome(path)

        def replay_dependency(_path, _event_type, outcome):
            replayed_snapshots.append(_retained_input(outcome).snapshot)
            return _pending_outcome(source_path)

        scheduler = EventScheduler(
            process,
            max_workers=1,
            max_pending_events=2,
            dependency_retry_process=replay_dependency,
        )
        self.assertTrue(scheduler.submit(source_path, "created"))
        self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 1))

        for expected_replays in (1, 2):
            self.assertTrue(scheduler.submit(dossier_path, "modified"))
            self.assertTrue(
                _wait_for_metric(
                    scheduler, "dependency_replays", expected_replays
                )
            )
            self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 1))

        with self.assertLogs("WoFFWatch", level="ERROR") as records:
            self.assertTrue(scheduler.submit(dossier_path, "modified"))
            self.assertTrue(scheduler.wait_for_paths([source_path], 1.0))

        metrics = scheduler.metrics()
        self.assertEqual(metrics["dependency_replays"], 3)
        self.assertEqual(metrics["dependency_exhausted"], 1)
        self.assertEqual(metrics["dependency_pending"], 0)
        self.assertEqual(len(replayed_snapshots), 3)
        self.assertEqual(
            records.output,
            [
                "ERROR:WoFFWatch:Deferred dependency exhausted: "
                "source=Pilot1Log.txt category=identity-pending slot=1 "
                "attempts=4"
            ],
        )
        scheduler.shutdown()

    def test_dependency_replay_composes_with_persistence_retry(self):
        source_path = "/private/campaign/Pilot1Log.txt"
        dossier_path = "/private/campaign/Pilot1Dossier.txt"
        retained = _pending_outcome(source_path)
        callbacks = []

        def process(path, _event_type):
            if path == dossier_path:
                return _resolved_outcome(path)
            return retained

        def replay_dependency(_path, _event_type, outcome):
            retry_input = _retained_input(outcome)
            callbacks.append(("dependency", retry_input.snapshot))
            return ProcessingOutcome.transient(
                retry_input, ProcessingReason.SQLITE_BUSY
            )

        def replay_persistence(_path, _event_type, outcome):
            retry_input = _retained_input(outcome)
            callbacks.append(
                ("persistence", retry_input.snapshot)
            )
            return ProcessingOutcome.success(retry_input.snapshot.generation)

        scheduler = EventScheduler(
            process,
            max_workers=1,
            max_pending_events=2,
            dependency_retry_process=replay_dependency,
            persistence_retry_process=replay_persistence,
            persistence_retry_policy=outcome_module.PersistenceRetryPolicy(
                max_attempts=4,
                initial_delay=0,
                max_delay=0,
            ),
        )
        self.assertTrue(scheduler.submit(source_path, "created"))
        self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 1))
        self.assertTrue(scheduler.submit(dossier_path, "created"))
        self.assertTrue(
            scheduler.wait_for_paths([source_path, dossier_path], 1.0)
        )
        scheduler.shutdown()

        self.assertEqual(
            callbacks,
            [
                ("dependency", _retained_input(retained).snapshot),
                ("persistence", _retained_input(retained).snapshot),
            ],
        )
        metrics = scheduler.metrics()
        self.assertEqual(metrics["dependency_replays"], 1)
        self.assertEqual(metrics["transient_retries"], 1)
        self.assertEqual(metrics["successful_replays"], 1)

    def test_dossier_releases_dependency_only_after_persistence_succeeds(self):
        source_path = "/private/campaign/Pilot1Log.txt"
        dossier_path = "/private/campaign/Pilot1Dossier.txt"
        dossier_retry_input = _retained_input(
            _pending_outcome(dossier_path)
        )
        persistence_started = threading.Event()
        allow_persistence = threading.Event()
        replayed = []

        def process(path, _event_type):
            if path == dossier_path:
                return ProcessingOutcome.transient(
                    dossier_retry_input, ProcessingReason.SQLITE_BUSY
                )
            return _pending_outcome(path)

        def replay_persistence(_path, _event_type, _outcome):
            persistence_started.set()
            self.assertTrue(allow_persistence.wait(1.0))
            return ProcessingOutcome.success(
                dossier_retry_input.snapshot.generation,
                resolved_dependency=DEPENDENCY_KEY,
            )

        def replay_dependency(path, _event_type, outcome):
            replayed.append(path)
            return ProcessingOutcome.success(
                _retained_input(outcome).snapshot.generation
            )

        scheduler = EventScheduler(
            process,
            max_workers=2,
            max_pending_events=2,
            dependency_retry_process=replay_dependency,
            persistence_retry_process=replay_persistence,
            persistence_retry_policy=outcome_module.PersistenceRetryPolicy(
                max_attempts=4,
                initial_delay=0,
                max_delay=0,
            ),
        )
        self.assertTrue(scheduler.submit(source_path, "created"))
        self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 1))
        self.assertTrue(scheduler.submit(dossier_path, "created"))
        self.assertTrue(persistence_started.wait(1.0))
        self.assertEqual(replayed, [])
        self.assertEqual(scheduler.metrics()["dependency_pending"], 1)

        allow_persistence.set()
        self.assertTrue(
            scheduler.wait_for_paths([source_path, dossier_path], 1.0)
        )
        scheduler.shutdown()

        self.assertEqual(replayed, [source_path])
        self.assertEqual(scheduler.metrics()["dependency_pending"], 0)

    def test_dossier_resolution_before_deferral_registration_is_not_lost(self):
        source_path = "/private/campaign/Pilot1Log.txt"
        dossier_path = "/private/campaign/Pilot1Dossier.txt"
        source_started = threading.Event()
        dossier_submitted = threading.Event()
        scheduler_holder = []
        replayed = []

        def process(path, _event_type):
            if path == dossier_path:
                return _resolved_outcome(path)
            source_started.set()
            if not dossier_submitted.wait(1.0):
                raise AssertionError("Dossier was not submitted")
            if not scheduler_holder[0].wait_for_paths(
                [dossier_path], 1.0
            ):
                raise AssertionError("Dossier did not finish")
            return _pending_outcome(path)

        def replay_dependency(path, _event_type, outcome):
            replayed.append(path)
            return ProcessingOutcome.success(
                _retained_input(outcome).snapshot.generation
            )

        scheduler = EventScheduler(
            process,
            max_workers=2,
            max_pending_events=2,
            dependency_retry_process=replay_dependency,
        )
        scheduler_holder.append(scheduler)
        self.assertTrue(scheduler.submit(source_path, "created"))
        self.assertTrue(source_started.wait(1.0))
        self.assertTrue(scheduler.submit(dossier_path, "created"))
        dossier_submitted.set()
        self.assertTrue(
            scheduler.wait_for_paths([source_path, dossier_path], 1.0)
        )
        scheduler.shutdown()

        self.assertEqual(replayed, [source_path])
        metrics = scheduler.metrics()
        self.assertEqual(metrics["dependency_replays"], 1)
        self.assertEqual(metrics["dependency_deferred"], 0)
        self.assertEqual(metrics["dependency_pending"], 0)

    def test_resolution_older_than_source_attempt_does_not_trigger_replay(self):
        source_path = "/private/campaign/Pilot1Log.txt"
        dossier_path = "/private/campaign/Pilot1Dossier.txt"
        replayed: list[str] = []

        def process(path, _event_type):
            if path == dossier_path:
                return _resolved_outcome(path)
            return _pending_outcome(path)

        def replay_dependency(path, _event_type, _outcome):
            replayed.append(path)
            return _pending_outcome(path)

        scheduler = EventScheduler(
            process,
            max_workers=1,
            max_pending_events=1,
            dependency_retry_process=replay_dependency,
        )
        self.assertTrue(scheduler.submit(dossier_path, "created"))
        self.assertTrue(scheduler.wait_for_paths([dossier_path], 1.0))
        self.assertTrue(scheduler.submit(source_path, "created"))
        self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 1))
        self.assertEqual(replayed, [])
        self.assertEqual(scheduler.metrics()["dependency_replays"], 0)
        with self.assertLogs("WoFFWatch", level="ERROR"):
            scheduler.shutdown()

    def test_new_coalesced_generation_gets_a_fresh_attempt_budget(self):
        source_path = "/private/campaign/Pilot1Log.txt"
        dossier_path = "/private/campaign/Pilot1Dossier.txt"
        dependency_replays = 0

        def process(path, _event_type):
            if path == dossier_path:
                return _resolved_outcome(path)
            return _pending_outcome(path)

        def replay_dependency(_path, _event_type, outcome):
            nonlocal dependency_replays
            dependency_replays += 1
            if dependency_replays == 3:
                return ProcessingOutcome.success(
                    _retained_input(outcome).snapshot.generation
                )
            return _pending_outcome(source_path)

        scheduler = EventScheduler(
            process,
            max_workers=1,
            max_pending_events=2,
            retry_process=lambda path, *_: _pending_outcome(path),
            dependency_retry_process=replay_dependency,
        )
        self.assertTrue(scheduler.submit(source_path, "created"))
        self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 1))
        self.assertTrue(scheduler.submit(source_path, "modified"))

        for expected_replays in (1, 2, 3):
            self.assertTrue(scheduler.submit(dossier_path, "modified"))
            self.assertTrue(
                _wait_for_metric(
                    scheduler, "dependency_replays", expected_replays
                )
            )
            if expected_replays < 3:
                self.assertTrue(
                    _wait_for_metric(scheduler, "dependency_pending", 1)
                )

        fresh_generation_pending = _wait_for_metric(
            scheduler, "dependency_pending", 1
        )
        metrics = scheduler.metrics()
        if fresh_generation_pending:
            with self.assertLogs("WoFFWatch", level="ERROR"):
                scheduler.shutdown()
        else:
            scheduler.shutdown()

        self.assertTrue(fresh_generation_pending)
        self.assertEqual(metrics["dependency_exhausted"], 0)
        self.assertEqual(metrics["dependency_replays"], 3)

    def test_same_slot_in_two_roots_releases_only_matching_dependency(self):
        source_a = "/campaign-a/Pilot1Log.txt"
        source_b = "/campaign-b/Pilot1Log.txt"
        dossier_a = "/campaign-a/Pilot1Dossier.txt"
        dossier_b = "/campaign-b/Pilot1Dossier.txt"
        keys = {
            source_a: ("root-v1:a", 1),
            source_b: ("root-v1:b", 1),
            dossier_a: ("root-v1:a", 1),
            dossier_b: ("root-v1:b", 1),
        }
        replayed = []

        def process(path, _event_type):
            if path in {dossier_a, dossier_b}:
                return _resolved_outcome(path, keys[path])
            return _pending_outcome(path, dependency_key=keys[path])

        def replay_dependency(path, _event_type, outcome):
            replayed.append((path, outcome.dependency_key))
            return ProcessingOutcome.success(
                _retained_input(outcome).snapshot.generation
            )

        scheduler = EventScheduler(
            process,
            max_workers=2,
            max_pending_events=4,
            dependency_retry_process=replay_dependency,
        )
        self.assertTrue(scheduler.submit(source_a, "created"))
        self.assertTrue(scheduler.submit(source_b, "created"))
        self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 2))

        self.assertTrue(scheduler.submit(dossier_a, "created"))
        self.assertTrue(scheduler.wait_for_paths([source_a, dossier_a], 1.0))
        self.assertEqual(replayed, [(source_a, keys[source_a])])
        self.assertEqual(scheduler.metrics()["dependency_pending"], 1)

        self.assertTrue(scheduler.submit(dossier_b, "created"))
        self.assertTrue(
            scheduler.wait_for_paths(
                [source_a, source_b, dossier_a, dossier_b], 1.0
            )
        )
        scheduler.shutdown()

        self.assertCountEqual(
            replayed,
            [(source_a, keys[source_a]), (source_b, keys[source_b])],
        )
        self.assertEqual(scheduler.metrics()["dependency_pending"], 0)

    def test_coalesced_event_while_deferred_keeps_queue_gauges_balanced(self):
        source_path = "/campaign/Pilot1Log.txt"
        dossier_path = "/campaign/Pilot1Dossier.txt"
        callbacks: list[tuple[str, str]] = []

        def process(path, event_type):
            callbacks.append(("process", event_type))
            if path == dossier_path:
                return _resolved_outcome(path)
            return _pending_outcome(path)

        def replay_dependency(path, event_type, outcome):
            callbacks.append(("dependency", event_type))
            return ProcessingOutcome.success(
                _retained_input(outcome).snapshot.generation
            )

        def replay_coalesced(path, event_type, _outcome):
            callbacks.append(("coalesced", event_type))
            return ProcessingOutcome.success(
                _retained_input(_pending_outcome(path)).snapshot.generation
            )

        scheduler = EventScheduler(
            process,
            max_workers=1,
            max_pending_events=2,
            retry_process=replay_coalesced,
            dependency_retry_process=replay_dependency,
        )
        self.assertTrue(scheduler.submit(source_path, "created"))
        self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 1))
        self.assertTrue(scheduler.submit(source_path, "modified"))
        self.assertTrue(scheduler.submit(dossier_path, "created"))
        self.assertTrue(
            scheduler.wait_for_paths([source_path, dossier_path], 1.0)
        )
        scheduler.shutdown()

        self.assertEqual(
            callbacks,
            [
                ("process", "created"),
                ("process", "created"),
                ("dependency", "created"),
                ("coalesced", "modified"),
            ],
        )
        metrics = scheduler.metrics()
        self.assertEqual(metrics["queued"], 0)
        self.assertEqual(metrics["active"], 0)
        self.assertEqual(metrics["dependency_pending"], 0)

    def test_dependency_replay_submission_failure_releases_all_states(self):
        source_path = "/campaign/Pilot1Log.txt"
        dossier_path = "/campaign/Pilot1Dossier.txt"

        def process(path, _event_type):
            if path == dossier_path:
                return _resolved_outcome(path)
            return _pending_outcome(path)

        scheduler = EventScheduler(
            process,
            max_workers=2,
            max_pending_events=2,
            executor=_ReplayFailingExecutor(),
            dependency_retry_process=lambda *_: ProcessingOutcome.success(
                _retained_input(
                    _pending_outcome(source_path)
                ).snapshot.generation
            ),
        )
        self.assertTrue(scheduler.submit(source_path, "created"))
        self.assertTrue(_wait_for_metric(scheduler, "dependency_pending", 1))

        with self.assertLogs("WoFFWatch", level="WARNING") as records:
            self.assertTrue(scheduler.submit(dossier_path, "created"))
            self.assertTrue(
                scheduler.wait_for_paths(
                    [source_path, dossier_path], 1.0
                )
            )
        scheduler.shutdown()

        self.assertEqual(scheduler.admitted_paths, 0)
        self.assertEqual(scheduler.metrics()["submission_failures"], 1)
        self.assertEqual(
            records.output,
            [
                "WARNING:WoFFWatch:Deferred dependency submission failed; "
                "state released"
            ],
        )

    def test_dependency_monitor_start_failure_releases_retained_state(self):
        source_path = "/campaign/Pilot1Log.txt"
        scheduler = EventScheduler(
            lambda *_: _pending_outcome(source_path),
            max_workers=1,
            max_pending_events=1,
        )

        with mock.patch.object(
            scheduler,
            "_start_dependency_monitor_locked",
            side_effect=RuntimeError("synthetic monitor failure"),
        ):
            with self.assertLogs("WoFFWatch", level="WARNING") as records:
                self.assertTrue(scheduler.submit(source_path, "created"))
                self.assertTrue(scheduler.wait_for_paths([source_path], 1.0))
        scheduler.shutdown()

        self.assertEqual(
            records.output,
            [
                "WARNING:WoFFWatch:Deferred dependency monitor unavailable; "
                "state released"
            ],
        )
        metrics = scheduler.metrics()
        self.assertEqual(scheduler.admitted_paths, 0)
        self.assertEqual(metrics["dependency_pending"], 0)
        self.assertEqual(metrics["dependency_retained_bytes"], 0)
        self.assertEqual(metrics["submission_failures"], 1)


if __name__ == "__main__":
    unittest.main()
