import threading
import shutil
import sqlite3
from unittest.mock import Mock

import pytest

from ..ingestion.scheduler import EventScheduler, canonical_windows_path
from ..database import DatabaseManager


def test_worker_closes_own_connection_before_shutdown_and_directory_removal(tmp_path):
    database_directory = tmp_path / "worker-db"
    database_directory.mkdir()
    db = DatabaseManager(str(database_directory / "test.db"))
    opened = []
    closed = []
    original_close = db.close

    def process(_path, _event):
        with db.transaction() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS lifecycle (value INTEGER)")
            conn.execute("INSERT INTO lifecycle VALUES (1)")
            opened.append((threading.get_ident(), conn))

    def close_worker():
        closed.append((threading.get_ident(), opened[-1][1].in_transaction))
        original_close()

    scheduler = EventScheduler(
        process, 1, 2, worker_cleanup=close_worker
    )
    assert scheduler.submit("synthetic.xml", "created")
    scheduler.shutdown()

    assert closed == [(opened[0][0], False)]
    with pytest.raises(sqlite3.ProgrammingError):
        opened[0][1].execute("SELECT 1")
    with sqlite3.connect(database_directory / "test.db") as reopened:
        assert reopened.execute("SELECT value FROM lifecycle").fetchall() == [(1,)]
        assert reopened.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    db.close()
    shutil.rmtree(database_directory)
    assert not database_directory.exists()


def test_worker_rolls_back_before_owner_cleanup_on_processing_exception(tmp_path, caplog):
    db = DatabaseManager(str(tmp_path / "failure.db"))
    observed = []
    original_close = db.close

    def process(_path, _event):
        with db.transaction() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS lifecycle (value INTEGER)")
            conn.execute("INSERT INTO lifecycle VALUES (2)")
            observed.append((threading.get_ident(), conn))
            raise ValueError("synthetic processing failure")

    def close_worker():
        owner, conn = observed[0]
        assert threading.get_ident() == owner
        assert not conn.in_transaction
        original_close()

    scheduler = EventScheduler(process, 1, 2, worker_cleanup=close_worker)
    assert scheduler.submit("synthetic.xml", "created")
    scheduler.shutdown()
    assert "synthetic processing failure" in caplog.text
    with pytest.raises(sqlite3.ProgrammingError):
        observed[0][1].execute("SELECT 1")
    with sqlite3.connect(db.db_path) as reopened:
        assert reopened.execute("SELECT name FROM sqlite_master WHERE name='lifecycle'").fetchone() is None
        assert reopened.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()


def test_cleanup_failure_survives_processing_error_and_fails_shutdown(caplog):
    processed = []

    def process(_path, _event):
        processed.append(threading.get_ident())
        raise ValueError("synthetic processing failure")

    def cleanup():
        assert threading.get_ident() == processed[0]
        raise OSError("synthetic cleanup failure")

    scheduler = EventScheduler(process, 1, 2, worker_cleanup=cleanup)
    assert scheduler.submit("synthetic.xml", "created")
    with pytest.raises(RuntimeError, match="Worker resource cleanup failed") as failure:
        scheduler.shutdown()
    assert isinstance(failure.value.__cause__, OSError)
    assert "synthetic processing failure" in caplog.text
    assert "synthetic cleanup failure" in caplog.text
    assert scheduler.metrics()["active"] == 0


def test_coalesced_task_and_reused_worker_close_at_task_boundaries(tmp_path):
    db = DatabaseManager(str(tmp_path / "reuse.db"))
    opened = []
    closed = []
    first_closed = threading.Event()
    original_close = db.close
    scheduler = None

    def process(path, event):
        with db.transaction() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS lifecycle (value TEXT)")
            conn.execute("INSERT INTO lifecycle VALUES (?)", (event,))
            opened.append((threading.get_ident(), conn))
        if event == "created":
            assert scheduler is not None
            assert scheduler.submit(path, "modified")

    def close_worker():
        closed.append(threading.get_ident())
        original_close()
        first_closed.set()

    scheduler = EventScheduler(process, 1, 2, worker_cleanup=close_worker)
    assert scheduler.submit("synthetic.xml", "created")
    assert first_closed.wait(2)
    assert scheduler.submit("second.xml", "initial")
    scheduler.shutdown()
    assert len(opened) == 3
    assert closed == [opened[0][0], opened[2][0]]
    assert opened[0][1] is opened[1][1]
    assert opened[2][1] is not opened[0][1]
    with sqlite3.connect(db.db_path) as reopened:
        assert reopened.execute("SELECT value FROM lifecycle").fetchall() == [
            ("created",), ("modified",), ("initial",)
        ]
    db.close()


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

    scheduler = EventScheduler(process, max_workers=1, max_pending_events=2)
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

    scheduler = EventScheduler(process, max_workers=1, max_pending_events=2)
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
    scheduler = EventScheduler(Mock(), 1, 1, executor=FailingExecutor())
    with pytest.raises(RuntimeError, match="submit failed"):
        scheduler.submit("pilot.xml", "created")
    assert scheduler.metrics()["queued"] == 0
    assert scheduler.metrics()["submission_failures"] == 1
    assert scheduler.admitted_paths == 0


def test_shutdown_rejects_new_work_and_drains_accepted_work():
    called = threading.Event()
    scheduler = EventScheduler(lambda *_: called.set(), 1, 1)
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

    scheduler = EventScheduler(process, max_workers=2, max_pending_events=1)
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
        lambda *_: (started.set(), release.wait(2)), 1, 1
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
