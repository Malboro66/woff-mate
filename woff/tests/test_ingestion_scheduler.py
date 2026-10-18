import threading
from queue import Queue
from unittest.mock import Mock

import pytest

from ..database import DatabaseManager
from ..ingestion.scheduler import EventScheduler, canonical_windows_path


def _metrics(**overrides):
    values = {
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
    values.update(overrides)
    return values


def test_windows_aliases_share_one_latest_pending_generation():
    started = threading.Event()
    release = threading.Event()
    calls = []

    def process(path, event_type):
        calls.append((path, event_type))
        if len(calls) == 1:
            started.set()
            assert release.wait(2)

    scheduler = EventScheduler(process, max_workers=1, max_pending_events=2, sqlite_capability="no-sqlite")
    assert scheduler.submit(r"C:\Campaign\Pilot.LOG", "created")
    assert started.wait(2)
    assert scheduler.submit(r"c:/campaign/pilot.log", "modified")
    assert scheduler.submit(r"\\?\C:\CAMPAIGN\pilot.log", "created")
    release.set()
    scheduler.shutdown()

    assert calls == [
        (r"C:\Campaign\Pilot.LOG", "created"),
        (r"\\?\C:\CAMPAIGN\pilot.log", "created"),
    ]
    assert scheduler.metrics() == _metrics(coalesced=2, retried=1)


def test_unc_and_extended_unc_aliases_have_the_same_identity():
    assert canonical_windows_path(r"\\server\share\Pilots\A.xml") == canonical_windows_path(
        r"\\?\UNC\SERVER\share/Pilots/A.XML"
    )


def test_unique_path_burst_is_bounded_and_saturation_is_visible(caplog):
    started = threading.Event()
    release = threading.Event()

    def process(path, event_type):
        started.set()
        assert release.wait(2)

    scheduler = EventScheduler(process, max_workers=1, max_pending_events=2, sqlite_capability="no-sqlite")
    assert scheduler.submit("first.xml", "created")
    assert started.wait(2)
    assert scheduler.submit("second.xml", "created")
    assert not scheduler.submit("third.xml", "created")
    assert scheduler.metrics() == _metrics(
        queued=1, active=1, rejected=1, saturated=1
    )
    assert "saturated" in caplog.text.lower()
    release.set()
    scheduler.shutdown()
    assert scheduler.metrics()["queued"] == scheduler.metrics()["active"] == 0


class FailingExecutor:
    def submit(self, *args, **kwargs):
        raise RuntimeError("submit failed")

    def shutdown(self, wait=True):
        pass


def test_submit_failure_releases_admission_state():
    scheduler = EventScheduler(Mock(), 1, 1, executor=FailingExecutor(), sqlite_capability="no-sqlite")
    with pytest.raises(RuntimeError, match="submit failed"):
        scheduler.submit("pilot.xml", "created")
    assert scheduler.metrics()["queued"] == 0
    assert scheduler.metrics()["submission_failures"] == 1
    assert scheduler.admitted_paths == 0


def test_shutdown_rejects_new_work_and_drains_accepted_work():
    called = threading.Event()
    scheduler = EventScheduler(lambda *_: called.set(), 1, 1, sqlite_capability="no-sqlite")
    assert scheduler.submit("pilot.xml", "created")
    scheduler.shutdown()
    assert called.is_set()
    assert not scheduler.submit("other.xml", "created")
    assert scheduler.metrics()["rejected"] == 1
    assert scheduler.metrics()["shutdown_rejected"] == 1


def test_bounded_startup_admission_waits_for_capacity_without_second_queue():
    first_started = threading.Event()
    release_first = threading.Event()
    calls = []

    def process(path, event_type):
        calls.append(path)
        if path == "Pilot1Dossier.txt":
            first_started.set()
            assert release_first.wait(2)

    scheduler = EventScheduler(process, max_workers=2, max_pending_events=1, sqlite_capability="no-sqlite")
    assert scheduler.submit("Pilot1Dossier.txt", "initial")
    assert first_started.wait(2)

    admitted = []
    submitter = threading.Thread(
        target=lambda: admitted.append(
            scheduler.submit(
                "Pilot1Log.txt", "initial", admission_timeout=1.0
            )
        )
    )
    submitter.start()
    assert submitter.is_alive()
    release_first.set()
    submitter.join(2)
    scheduler.shutdown()

    assert admitted == [True]
    assert calls == ["Pilot1Dossier.txt", "Pilot1Log.txt"]


def test_startup_admission_timeout_is_bounded_and_diagnostic(caplog):
    started = threading.Event()
    release = threading.Event()
    scheduler = EventScheduler(
        lambda *_: (started.set(), release.wait(2)), 1, 1,
        sqlite_capability="no-sqlite",
    )
    assert scheduler.submit("Pilot1Dossier.txt", "initial")
    assert started.wait(2)
    assert not scheduler.submit(
        "Pilot2Dossier.txt", "initial", admission_timeout=0.01
    )
    assert "saturated" in caplog.text.lower()
    release.set()
    scheduler.shutdown()


def test_scheduler_does_not_depend_on_executor_private_internals():
    assert not any(name.startswith("_") for name in EventScheduler.executor_attributes_used)


def test_successful_processing_cleanup_failure_is_reported_at_shutdown(caplog):
    events = []

    def process(*_event):
        events.append("processed")

    def cleanup():
        events.append("cleanup")
        raise OSError("private path and campaign data")

    scheduler = EventScheduler(
        process, 1, 1, worker_task_cleanup=cleanup,
        sqlite_capability="sqlite-capable",
    )
    assert scheduler.submit("synthetic.xml", "created")

    with pytest.raises(RuntimeError, match="1 task"):
        scheduler.shutdown()

    assert events == ["processed", "cleanup"]
    assert "exception_type=OSError" in caplog.text
    assert "private path" not in caplog.text
    assert "campaign data" not in caplog.text


def test_processing_failure_remains_logged_when_cleanup_also_fails(caplog):
    def process(*_event):
        raise ValueError("synthetic processing failure")

    def cleanup():
        raise OSError("private path")

    scheduler = EventScheduler(
        process, 1, 1, worker_task_cleanup=cleanup,
        sqlite_capability="sqlite-capable",
    )
    assert scheduler.submit("synthetic.xml", "created")

    with pytest.raises(RuntimeError, match="1 task"):
        scheduler.shutdown()

    processing_errors = [
        record.exc_info[1]
        for record in caplog.records
        if record.exc_info is not None
    ]
    assert any(
        isinstance(error, ValueError)
        and str(error) == "synthetic processing failure"
        for error in processing_errors
    )
    assert "exception_type=OSError" in caplog.text
    assert "private path" not in caplog.text


def test_transaction_rolls_back_before_worker_cleanup(tmp_path, caplog):
    database = DatabaseManager(str(tmp_path / "cleanup.sqlite"))
    cleanup_observations = []

    def process(*_event):
        with database.transaction() as connection:
            connection.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?)",
                ("cleanup-rollback", "uncommitted"),
            )
            raise ValueError("synthetic transaction failure")

    def cleanup():
        connection = getattr(database._local, "conn", None)
        cleanup_observations.append(
            (
                threading.get_ident(),
                connection.in_transaction if connection is not None else None,
            )
        )
        database.close()

    scheduler = EventScheduler(
        process, 1, 1, worker_task_cleanup=cleanup,
        sqlite_capability="sqlite-capable",
    )
    try:
        assert scheduler.submit("synthetic-transaction", "created")
        scheduler.shutdown()

        assert len(cleanup_observations) == 1
        assert cleanup_observations[0][1] is False
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM meta WHERE key = ?",
            ("cleanup-rollback",),
        ).fetchone() == (0,)
        assert any(
            record.exc_info is not None
            and isinstance(record.exc_info[1], ValueError)
            for record in caplog.records
        )
    finally:
        database.close()


def test_multiple_cleanup_failures_are_reported_after_drain_and_monitor_join(
    caplog,
):
    processed = []
    cleanup_count = []
    monitor = Mock()

    def process(path, _event_type):
        processed.append(path)

    def cleanup():
        cleanup_count.append(threading.get_ident())
        raise OSError("synthetic cleanup failure")

    scheduler = EventScheduler(
        process, 1, 2, worker_task_cleanup=cleanup,
        sqlite_capability="sqlite-capable",
    )

    def join_monitor():
        assert processed == ["first.xml", "second.xml"]
        assert len(cleanup_count) == 2

    monitor.join.side_effect = join_monitor
    with scheduler._lock:
        scheduler._dependency_monitor = monitor

    assert scheduler.submit("first.xml", "created")
    assert scheduler.submit("second.xml", "created")

    with pytest.raises(RuntimeError, match="2 task"):
        scheduler.shutdown()

    monitor.join.assert_called_once_with()
    assert processed == ["first.xml", "second.xml"]
    assert len(cleanup_count) == 2
    assert caplog.text.count("Worker task cleanup failed") == 2


def test_shutdown_succeeds_when_worker_cleanup_succeeds():
    events = []
    scheduler = EventScheduler(
        lambda *_event: events.append("processed"),
        1,
        1,
        worker_task_cleanup=lambda: events.append("cleanup"),
        sqlite_capability="sqlite-capable",
    )
    assert scheduler.submit("synthetic.xml", "created")

    scheduler.shutdown()

    assert events == ["processed", "cleanup"]


def test_worker_cleanup_follows_coalescing_and_reused_worker_tasks(tmp_path):
    database = DatabaseManager(str(tmp_path / "worker-lifecycle.sqlite"))
    first_callback_started = threading.Event()
    release_first_callback = threading.Event()
    cleanup_records = Queue()
    callbacks = []

    def process(path, event_type):
        connection = database._get_conn()
        callbacks.append((path, event_type, threading.get_ident(), connection))
        connection.execute("SELECT 1").fetchone()
        if event_type == "initial":
            first_callback_started.set()
            assert release_first_callback.wait(2)

    def cleanup():
        connection = getattr(database._local, "conn", None)
        cleanup_records.put((threading.get_ident(), connection))
        database.close()

    scheduler = EventScheduler(
        process, 1, 2, worker_task_cleanup=cleanup,
        sqlite_capability="sqlite-capable",
    )
    try:
        assert scheduler.submit("initial.xml", "initial")
        assert first_callback_started.wait(2)
        assert scheduler.submit("initial.xml", "coalesced")
        release_first_callback.set()

        first_cleanup = cleanup_records.get(timeout=2)
        assert scheduler.wait_for_paths(["initial.xml"], 2)

        assert scheduler.submit("live.xml", "modified")
        scheduler.shutdown()
        second_cleanup = cleanup_records.get(timeout=2)

        assert [(path, event_type) for path, event_type, _, _ in callbacks] == [
            ("initial.xml", "initial"),
            ("initial.xml", "coalesced"),
            ("live.xml", "modified"),
        ]
        initial_connection = callbacks[0][3]
        assert callbacks[1][3] is initial_connection
        assert first_cleanup == (callbacks[0][2], initial_connection)
        assert callbacks[1][2] == callbacks[0][2]
        assert second_cleanup == (callbacks[2][2], callbacks[2][3])
        assert callbacks[2][2] == callbacks[0][2]
        assert callbacks[2][3] is not initial_connection
        assert scheduler.metrics()["coalesced"] == 1
        assert scheduler.metrics()["retried"] == 1
        assert scheduler.metrics()["queued"] == 0
        assert scheduler.metrics()["active"] == 0
    finally:
        release_first_callback.set()
        if scheduler.accepting:
            scheduler.shutdown()
        database.close()

def test_scheduler_requires_explicit_sqlite_capability_before_dispatch():
    ran = threading.Event()
    with pytest.raises(ValueError, match="sqlite_capability"):
        EventScheduler(lambda *_: ran.set(), 1, 1)
    assert not ran.is_set()


@pytest.mark.parametrize("invalid", [None, "", "unknown", "SQLite-capable", 0, False])
def test_scheduler_rejects_invalid_sqlite_capability_before_dispatch(invalid):
    ran = threading.Event()
    with pytest.raises(ValueError, match="sqlite_capability"):
        EventScheduler(
            lambda *_: ran.set(), 1, 1,
            sqlite_capability=invalid,
        )
    assert not ran.is_set()


@pytest.mark.parametrize("invalid_cleanup", [None, object()])
def test_sqlite_capable_scheduler_requires_callable_cleanup_before_dispatch(
    invalid_cleanup,
):
    ran = threading.Event()
    with pytest.raises(ValueError, match="worker_task_cleanup"):
        EventScheduler(
            lambda *_: ran.set(), 1, 1,
            sqlite_capability="sqlite-capable",
            worker_task_cleanup=invalid_cleanup,
        )
    assert not ran.is_set()


def test_genuine_no_sqlite_scheduler_does_not_require_worker_cleanup():
    completed = []
    scheduler = EventScheduler(
        lambda path, event: completed.append((path, event)), 1, 2,
        sqlite_capability="no-sqlite",
    )
    assert scheduler.submit("synthetic.txt", "created")
    scheduler.shutdown()
    assert completed == [("synthetic.txt", "created")]


def test_sqlite_capable_direct_scheduler_closes_connection_on_owner_thread(tmp_path):
    manager = DatabaseManager(str(tmp_path / "direct.sqlite"))
    worker_threads = []
    closed_threads = []

    def process(*_args):
        worker_threads.append(threading.get_ident())
        manager._get_conn().execute("SELECT 1").fetchone()

    def cleanup():
        closed_threads.append(threading.get_ident())
        manager.close()

    scheduler = EventScheduler(
        process, 1, 1,
        sqlite_capability="sqlite-capable",
        worker_task_cleanup=cleanup,
    )
    try:
        assert scheduler.submit("synthetic.txt", "created")
        scheduler.shutdown()
        assert worker_threads == closed_threads
        assert len(worker_threads) == 1
        assert getattr(manager._local, "conn", None) is None
        manager._get_conn().execute("SELECT 1").fetchone()
    finally:
        manager.close()
