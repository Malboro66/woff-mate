import sqlite3
import threading
import time

import pytest

from ..campaign_engine import CampaignEngine
from ..config import WatchdogConfig
from ..database import DatabaseManager
from ..handler import WoFFEventHandler
from ..ingestion.outcome import (
    PersistenceRetryPolicy,
    ProcessingReason,
    ProcessingStatus,
    classify_transient_sqlite_error,
)
from .test_dossier_parser import _encode_dossier


def _encoded_dossier() -> bytes:
    lines = ["Null"] * 105
    for index, value in {
        3: "Captain",
        4: "Alice",
        5: "Able",
        11: "60",
        16: "1",
        17: "1",
        41: "50",
        46: "2",
        52: "10",
        83: "No. 56 Squadron RFC",
        84: "SE.5a",
        88: "Filescamp",
        89: "Arras",
    }.items():
        lines[index] = value
    return _encode_dossier(lines, "Pilot1Dossier.txt")


def _pilot_log(day: int, note: str) -> str:
    return (
        f"1\n{day};4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;"
        "SE.5a;No. 56 Squadron RFC;troops;Target;N50;E2;;"
        f"{note}\n"
    )


@pytest.fixture
def retry_ingestion(tmp_path, monkeypatch):
    database_path = tmp_path / "retry.sqlite"
    config = WatchdogConfig(
        watch_paths=[str(tmp_path)],
        export_path=str(database_path),
        stability_timeout_sec=0.05,
        stability_check_interval_sec=0.001,
        max_workers=1,
        max_pending_events=1,
    )
    database = DatabaseManager(
        str(database_path), campaign_namespaces=config.campaign_namespaces
    )
    handler = WoFFEventHandler(config, database, CampaignEngine(database))
    dossier_path = tmp_path / "Pilot1Dossier.txt"
    log_path = tmp_path / "Pilot1Log.txt"
    dossier_path.write_bytes(_encoded_dossier())
    log_path.write_text(_pilot_log(6, "Generation A."), encoding="cp1252")

    dossier = handler.processor.process(str(dossier_path), "initial")
    assert dossier.status is ProcessingStatus.SUCCESS

    original_open = database._open_conn

    def open_with_short_busy_timeout():
        connection = original_open()
        connection.execute("PRAGMA busy_timeout=1")
        return connection

    monkeypatch.setattr(database, "_open_conn", open_with_short_busy_timeout)
    monkeypatch.setattr(
        "woff.campaign_engine.narrative_generator.generate",
        lambda *_args, **_kwargs: "deterministic mission narrative",
    )

    yield handler, database, database_path, log_path, dossier_path

    handler.shutdown()
    database.close()


def _hold_external_write_lock(database_path):
    connection = sqlite3.connect(database_path, timeout=0.1, isolation_level=None)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("BEGIN IMMEDIATE")
    return connection


def _release_write_lock(connection):
    connection.execute("ROLLBACK")
    connection.close()


def _pause_first_transient(monkeypatch, handler):
    transient_seen = threading.Event()
    allow_result = threading.Event()
    original_process = handler.processor.process

    def observed_process(path, event_type, previous_generation=None):
        outcome = original_process(path, event_type, previous_generation)
        if (
            outcome.status is ProcessingStatus.TRANSIENT_FAILURE
            and not transient_seen.is_set()
        ):
            transient_seen.set()
            assert allow_result.wait(2)
        return outcome

    monkeypatch.setattr(handler.processor, "process", observed_process)
    return transient_seen, allow_result


@pytest.mark.parametrize(
    ("code", "reason"),
    [
        (5, ProcessingReason.SQLITE_BUSY),
        (261, ProcessingReason.SQLITE_BUSY),
        (6, ProcessingReason.SQLITE_LOCKED),
        (262, ProcessingReason.SQLITE_LOCKED),
        (15, ProcessingReason.SQLITE_PROTOCOL),
        (2826, ProcessingReason.SQLITE_IO_BLOCKED),
    ],
)
def test_only_verified_transient_sqlite_codes_are_classified(code, reason):
    error = sqlite3.OperationalError("synthetic SQLite failure")
    setattr(error, "sqlite_errorcode", code)
    assert classify_transient_sqlite_error(error) is reason

    permanent = sqlite3.OperationalError("database is locked")
    setattr(permanent, "sqlite_errorcode", 1)
    assert classify_transient_sqlite_error(permanent) is None


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("database is locked", ProcessingReason.SQLITE_BUSY),
        ("database table is locked: missions", ProcessingReason.SQLITE_LOCKED),
        ("database schema is locked: main", ProcessingReason.SQLITE_LOCKED),
        ("locking protocol", ProcessingReason.SQLITE_PROTOCOL),
    ],
)
def test_python_310_exact_sqlite_messages_have_a_bounded_fallback(
    message, reason
):
    assert (
        classify_transient_sqlite_error(sqlite3.OperationalError(message))
        is reason
    )


def test_mission_history_read_propagates_transient_sqlite_failure(
    tmp_path, monkeypatch
):
    database = DatabaseManager(str(tmp_path / "read-failure.sqlite"))

    class LockedReadConnection:
        row_factory = None

        def execute(self, _sql, _parameters=()):
            raise sqlite3.OperationalError("database is locked")

    connection = LockedReadConnection()
    monkeypatch.setattr(database, "_get_conn", lambda: connection)
    try:
        with pytest.raises(sqlite3.OperationalError, match="database is locked"):
            database.get_mission_and_history("pilot-id", "mission-id")
        assert connection.row_factory is None
    finally:
        database.close()


def test_default_persistence_retry_policy_has_documented_total_bound(tmp_path):
    policy = PersistenceRetryPolicy()
    delays = [
        policy.delay_after_failure(failure)
        for failure in range(1, policy.max_attempts)
    ]
    assert policy.max_attempts == 4
    assert delays == [0.1, 0.2, 0.4]
    assert sum(delays) == pytest.approx(0.7)

    database = DatabaseManager(str(tmp_path / "busy-timeout.sqlite"))
    try:
        assert database._get_conn().execute(
            "PRAGMA busy_timeout"
        ).fetchone() == (5000,)
    finally:
        database.close()


def test_startup_wait_budget_covers_every_bounded_persistence_attempt(
    retry_ingestion
):
    handler, _database, _database_path, _log_path, _dossier_path = retry_ingestion
    policy = handler.scheduler.persistence_retry_policy
    backoff = sum(
        policy.delay_after_failure(failure)
        for failure in range(1, policy.max_attempts)
    )
    minimum_per_path = (
        handler.config.stability_timeout_sec
        + (policy.max_attempts * 5.0)
        + backoff
    )

    assert handler.startup_phase_timeout(1) >= minimum_per_path
    assert handler.startup_phase_timeout(2) >= 2 * minimum_per_path


def test_startup_budget_counts_both_snapshots_for_dependent_paths(
    retry_ingestion, tmp_path
):
    handler, _database, _database_path, log_path, _dossier_path = retry_ingestion
    dependent_paths = [str(log_path), str(tmp_path / "Pilot2Claims.txt")]
    policy = handler.scheduler.persistence_retry_policy
    retry_backoff = sum(
        policy.delay_after_failure(failure)
        for failure in range(1, policy.max_attempts)
    )
    persistence_per_path = (
        policy.max_attempts * 5.0
    ) + retry_backoff
    required = (
        handler.config.stability_timeout_sec
        + (4 * handler.config.stability_timeout_sec)
        + (2 * persistence_per_path)
    )

    assert handler.startup_phase_timeout(dependent_paths) >= required


def test_real_sqlite_contention_replays_verified_generation_once(
    retry_ingestion, monkeypatch
):
    handler, database, database_path, log_path, dossier_path = retry_ingestion
    lock = _hold_external_write_lock(database_path)
    transient_seen, allow_result = _pause_first_transient(monkeypatch, handler)
    acquired = []
    original_acquire = handler.processor.guard.acquire

    def tracked_acquire(path):
        acquired.append(path)
        return original_acquire(path)

    monkeypatch.setattr(handler.processor.guard, "acquire", tracked_acquire)
    try:
        assert handler.scheduler.submit(str(log_path), "modified")
        assert transient_seen.wait(2)
        assert handler.scheduler.admitted_paths == 1
        log_path.write_text(
            _pilot_log(7, "Unannounced mutable bytes."), encoding="cp1252"
        )
        _release_write_lock(lock)
        lock = None
        allow_result.set()
        assert handler.scheduler.wait_for_paths([str(log_path)], timeout=2)
        handler.shutdown()
    finally:
        if lock is not None:
            _release_write_lock(lock)

    connection = database._get_conn()
    assert connection.execute("SELECT COUNT(*) FROM missions").fetchone() == (1,)
    assert connection.execute("SELECT date FROM missions").fetchall() == [
        ("1917-04-06",)
    ]
    assert connection.execute("SELECT COUNT(*) FROM diary_entries").fetchone() == (1,)
    assert connection.execute("SELECT COUNT(*) FROM pilot_rpg_stats").fetchone() == (1,)
    assert acquired == [str(log_path), str(dossier_path)]
    assert handler.metrics()["transient_failures"] == 1
    assert handler.metrics()["transient_retries"] == 1
    assert handler.metrics()["successful_replays"] == 1
    assert handler.metrics()["permanent_rejections"] == 0
    assert handler.metrics()["saturated"] == 0


def test_partial_generation_replay_recomputes_corrected_pending_mission(
    retry_ingestion, monkeypatch
):
    handler, database, _database_path, log_path, _dossier_path = retry_ingestion
    first_derived_read = threading.Event()
    release_first_read = threading.Event()
    original_read = database.get_mission_and_history
    read_calls = 0

    def fail_first_derived_read(pilot_id, mission_id):
        nonlocal read_calls
        read_calls += 1
        if read_calls == 1:
            first_derived_read.set()
            assert release_first_read.wait(2)
            raise sqlite3.OperationalError("database is locked")
        return original_read(pilot_id, mission_id)

    monkeypatch.setattr(
        database, "get_mission_and_history", fail_first_derived_read
    )
    monkeypatch.setattr(
        "woff.campaign_engine.narrative_generator.generate",
        lambda _pilot_name, mission: f"narrative:{mission['notes']}",
    )
    monkeypatch.setattr(
        "woff.campaign_engine.rpg_system.calculate_stress",
        lambda missions: 80 if missions[0]["notes"] == "Generation B." else 10,
    )

    assert handler.scheduler.submit(str(log_path), "modified")
    assert first_derived_read.wait(2)
    connection = database._get_conn()
    assert connection.execute("SELECT date FROM missions").fetchall() == [
        ("1917-04-06",)
    ]
    assert connection.execute(
        "SELECT COUNT(*) FROM diary_entries"
    ).fetchone() == (0,)

    log_path.write_text(_pilot_log(6, "Generation B."), encoding="cp1252")
    assert handler.scheduler.submit(str(log_path), "modified")
    release_first_read.set()
    assert handler.scheduler.wait_for_paths([str(log_path)], timeout=2)
    handler.shutdown()

    assert connection.execute(
        "SELECT date, notes FROM missions"
    ).fetchall() == [("1917-04-06", "Generation B.")]
    assert connection.execute(
        "SELECT narrative FROM diary_entries"
    ).fetchall() == [("narrative:Generation B.",)]
    assert connection.execute(
        "SELECT stress FROM pilot_rpg_stats"
    ).fetchall() == [(80,)]
    assert handler.metrics()["successful_replays"] == 1
    assert handler.metrics()["permanent_rejections"] == 0


def test_newer_event_waits_for_retained_retry_then_processes_latest_generation(
    retry_ingestion, monkeypatch
):
    handler, database, database_path, log_path, _dossier_path = retry_ingestion
    lock = _hold_external_write_lock(database_path)
    transient_seen, allow_result = _pause_first_transient(monkeypatch, handler)
    try:
        assert handler.scheduler.submit(str(log_path), "modified")
        assert transient_seen.wait(2)
        log_path.write_text(_pilot_log(7, "Generation B."), encoding="cp1252")
        assert handler.scheduler.submit(str(log_path), "modified")
        _release_write_lock(lock)
        lock = None
        allow_result.set()
        assert handler.scheduler.wait_for_paths([str(log_path)], timeout=2)
        handler.shutdown()
    finally:
        if lock is not None:
            _release_write_lock(lock)

    connection = database._get_conn()
    assert connection.execute(
        "SELECT date FROM missions ORDER BY date"
    ).fetchall() == [("1917-04-06",), ("1917-04-07",)]
    assert handler.metrics()["superseded_retries"] == 0
    assert handler.metrics()["transient_retries"] == 1
    assert handler.metrics()["successful_replays"] == 1


def test_repeated_sqlite_contention_stops_at_documented_bound(
    retry_ingestion, caplog
):
    handler, database, database_path, log_path, _dossier_path = retry_ingestion
    lock = _hold_external_write_lock(database_path)
    try:
        assert handler.scheduler.submit(str(log_path), "modified")
        assert handler.scheduler.wait_for_paths([str(log_path)], timeout=2)
    finally:
        _release_write_lock(lock)
        handler.shutdown()

    metrics = handler.metrics()
    assert metrics["transient_failures"] == 4
    assert metrics["transient_retries"] == 3
    assert metrics["retry_exhausted"] == 1
    assert metrics["successful_replays"] == 0
    assert database._get_conn().execute(
        "SELECT COUNT(*) FROM missions"
    ).fetchone() == (0,)
    diagnostic = [
        record.getMessage()
        for record in caplog.records
        if "Persistence retry exhausted" in record.getMessage()
    ]
    assert diagnostic == [
        "Persistence retry exhausted: source=Pilot1Log.txt "
        "category=sqlite-busy attempts=4"
    ]
    assert str(database_path.parent) not in diagnostic[0]


def test_duplicate_notifications_do_not_restart_retry_budget(
    retry_ingestion, monkeypatch
):
    handler, database, database_path, log_path, _dossier_path = retry_ingestion
    lock = _hold_external_write_lock(database_path)
    transient_seen, allow_result = _pause_first_transient(monkeypatch, handler)
    try:
        assert handler.scheduler.submit(str(log_path), "modified")
        assert transient_seen.wait(2)
        for _ in range(5):
            assert handler.scheduler.submit(str(log_path), "modified")
        allow_result.set()
        assert handler.scheduler.wait_for_paths([str(log_path)], timeout=2)
    finally:
        _release_write_lock(lock)
        handler.shutdown()

    metrics = handler.metrics()
    assert metrics["transient_failures"] == 4
    assert metrics["transient_retries"] == 3
    assert metrics["retry_exhausted"] == 1
    assert database._get_conn().execute(
        "SELECT COUNT(*) FROM missions"
    ).fetchone() == (0,)


def test_late_duplicate_after_retry_exhaustion_keeps_terminal_budget(
    retry_ingestion,
):
    handler, database, database_path, log_path, _dossier_path = retry_ingestion
    lock = _hold_external_write_lock(database_path)
    try:
        assert handler.scheduler.submit(str(log_path), "modified")
        assert handler.scheduler.wait_for_paths([str(log_path)], timeout=2)
        assert handler.metrics()["transient_failures"] == 4
        assert handler.metrics()["retry_exhausted"] == 1

        assert handler.scheduler.submit(str(log_path), "modified")
        assert handler.scheduler.wait_for_paths([str(log_path)], timeout=2)
    finally:
        _release_write_lock(lock)
        handler.shutdown()

    metrics = handler.metrics()
    assert metrics["transient_failures"] == 4
    assert metrics["transient_retries"] == 3
    assert metrics["retry_exhausted"] == 1
    assert metrics["permanent_rejections"] == 1
    assert database._get_conn().execute(
        "SELECT COUNT(*) FROM missions"
    ).fetchone() == (0,)


def test_newer_generation_runs_after_older_retry_exhaustion(
    retry_ingestion, monkeypatch
):
    handler, database, database_path, log_path, _dossier_path = retry_ingestion
    lock = _hold_external_write_lock(database_path)
    fourth_failure = threading.Event()
    allow_terminal_result = threading.Event()
    original_replay = handler.processor.replay
    replay_failures = 0

    def observed_replay(outcome, event_type):
        nonlocal replay_failures
        result = original_replay(outcome, event_type)
        if result.status is ProcessingStatus.TRANSIENT_FAILURE:
            replay_failures += 1
            if replay_failures == 3:
                fourth_failure.set()
                assert allow_terminal_result.wait(2)
        return result

    monkeypatch.setattr(handler.processor, "replay", observed_replay)
    try:
        assert handler.scheduler.submit(str(log_path), "modified")
        assert fourth_failure.wait(2)
        log_path.write_text(_pilot_log(7, "Generation B."), encoding="cp1252")
        assert handler.scheduler.submit(str(log_path), "modified")
        _release_write_lock(lock)
        lock = None
        allow_terminal_result.set()
        assert handler.scheduler.wait_for_paths([str(log_path)], timeout=2)
    finally:
        if lock is not None:
            _release_write_lock(lock)
        handler.shutdown()

    assert database._get_conn().execute(
        "SELECT date FROM missions"
    ).fetchall() == [("1917-04-07",)]
    assert handler.metrics()["transient_failures"] == 4
    assert handler.metrics()["retry_exhausted"] == 1


def test_shutdown_cancels_retained_retry_with_final_diagnostic(
    retry_ingestion, monkeypatch, caplog
):
    handler, database, database_path, log_path, _dossier_path = retry_ingestion
    lock = _hold_external_write_lock(database_path)
    transient_seen, allow_result = _pause_first_transient(monkeypatch, handler)
    assert handler.scheduler.submit(str(log_path), "modified")
    assert transient_seen.wait(2)
    log_path.write_text(_pilot_log(7, "Accepted before shutdown."), encoding="cp1252")
    assert handler.scheduler.submit(str(log_path), "modified")

    shutdown = threading.Thread(target=handler.shutdown)
    shutdown.start()
    deadline = time.monotonic() + 1
    while handler.scheduler.accepting and time.monotonic() < deadline:
        shutdown.join(0.001)
    assert not handler.scheduler.accepting
    allow_result.set()
    shutdown.join(2)
    _release_write_lock(lock)

    assert not shutdown.is_alive()
    assert handler.metrics()["transient_failures"] == 2
    assert handler.metrics()["transient_retries"] == 0
    assert handler.metrics()["retry_shutdown"] == 2
    assert handler.metrics()["superseded_retries"] == 0
    assert database._get_conn().execute(
        "SELECT COUNT(*) FROM missions"
    ).fetchone() == (0,)
    diagnostic = [
        record.getMessage()
        for record in caplog.records
        if "Persistence retry cancelled at shutdown" in record.getMessage()
    ]
    assert diagnostic == [
        "Persistence retry cancelled at shutdown: source=Pilot1Log.txt "
        "category=sqlite-busy attempts=1",
        "Persistence retry cancelled at shutdown: source=Pilot1Log.txt "
        "category=sqlite-busy attempts=1"
    ]
    assert str(database_path.parent) not in diagnostic[0]


def test_permanent_parser_rejection_is_typed_and_never_retried(
    retry_ingestion, monkeypatch
):
    handler, _database, _database_path, log_path, _dossier_path = retry_ingestion
    log_path.write_text("not a supported pilot record\n", encoding="cp1252")
    outcomes = []
    original_process = handler.processor.process

    def observed_process(path, event_type, previous_generation=None):
        outcome = original_process(path, event_type, previous_generation)
        outcomes.append(outcome)
        return outcome

    monkeypatch.setattr(handler.processor, "process", observed_process)
    assert handler.scheduler.submit(str(log_path), "modified")
    handler.shutdown()

    assert [outcome.status for outcome in outcomes] == [
        ProcessingStatus.PERMANENT_REJECTION
    ]
    assert outcomes[0].reason is ProcessingReason.PARSER_REJECTED
    assert handler.metrics()["permanent_rejections"] == 1
    assert handler.metrics()["transient_retries"] == 0
    assert handler.metrics()["successful_replays"] == 0
