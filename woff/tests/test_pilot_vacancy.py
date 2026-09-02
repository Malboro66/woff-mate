"""Observed slot vacancy must never change a historical career."""

from dataclasses import replace
from pathlib import Path
import sqlite3
import threading
from unittest.mock import Mock

import pytest
from watchdog.events import FileCreatedEvent, FileDeletedEvent, FileMovedEvent

from .. import woff_watchdog
from ..campaign_engine import CampaignEngine
from ..campaign_namespace import campaign_namespace_for_root
from ..career_selection import list_careers, resolve_career
from ..config import WatchdogConfig
from ..database import DatabaseManager
from ..handler import FileProcessor, WoFFEventHandler
from ..ingestion.outcome import (
    PersistenceRetryPolicy,
    ProcessingOutcome,
    ProcessingReason,
    ProcessingStatus,
)
from ..ingestion.scheduler import EventScheduler
from ..ingestion.vacancy import (
    DossierVacancyGuard,
    DossierInventory,
    VacancyState,
    scan_dossiers,
)
from .test_dossier_parser import _dossier_fixture, _encode_dossier


@pytest.fixture
def runtime(tmp_path):
    root = tmp_path / "Synthetic campaign"
    root.mkdir()
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "vacancy.sqlite"),
        stability_timeout_sec=0.01,
        stability_check_interval_sec=0.001,
    )
    database = DatabaseManager(
        config.export_path, campaign_namespaces=config.campaign_namespaces
    )
    handler = WoFFEventHandler(config, database, CampaignEngine(database))
    yield root, config, database, handler
    handler.shutdown()
    database.close()


def _occupy(root, handler, slot=1):
    path = root / f"Pilot{slot}Dossier.txt"
    path.write_bytes(
        _encode_dossier(_dossier_fixture("current_full_sanitized.txt"), path.name)
    )
    assert handler.processor.process(str(path), "created").status is (
        ProcessingStatus.SUCCESS
    )
    return path


def _bindings(database):
    return (
        database._get_conn()
        .execute(
            "SELECT campaign_namespace, slot, pilotId FROM pilot_slot_bindings "
            "ORDER BY campaign_namespace, slot"
        )
        .fetchall()
    )


def _history(database):
    connection = database._get_conn()
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name != 'pilot_slot_bindings'"
        )
    ]
    return {
        table: set(
            connection.execute(
                f'SELECT * FROM "{table}"'
                + (
                    " WHERE key NOT LIKE 'pilot_slot_vacancy:%' AND key != 'last_updated'"
                    if table == "meta"
                    else ""
                )
            ).fetchall()
        )
        for table in tables
    }


def _delete(path, handler):
    path.unlink()
    handler.on_deleted(FileDeletedEvent(str(path)))
    assert handler.scheduler.wait_for_paths([str(path)], 2)


def _write_log(root, slot=1):
    path = root / f"Pilot{slot}Log.txt"
    path.write_text(
        "1\n6;4;1917;10;30;Arras;A Field;OP;SE.5a;;45;100;"
        "SE.5a;A Squadron;troops;Target;N50;E2;;Synthetic mission.\n",
        encoding="ascii",
    )
    return path


def test_live_deletion_vacates_only_the_deleted_dossier_slot(runtime):
    root, _config, database, handler = runtime
    paths = [_occupy(root, handler, slot) for slot in (1, 2, 3)]
    before = _bindings(database)
    history = (
        database._get_conn().execute("SELECT * FROM pilots ORDER BY id").fetchall()
    )
    (root / "Pilot1Log.txt").write_text("0\n", encoding="ascii")
    (root / "Pilot1Claims.txt").write_text("0\n", encoding="ascii")
    paths[0].unlink()

    handler.on_deleted(FileDeletedEvent(str(paths[0])))
    assert handler.scheduler.wait_for_paths([str(paths[0])], 2)

    assert _bindings(database) == before[1:]
    assert (
        database._get_conn().execute("SELECT * FROM pilots ORDER BY id").fetchall()
        == history
    )


def test_restart_reconciles_a_sparse_dossier_inventory(runtime, monkeypatch):
    root, config, database, handler = runtime
    paths = [_occupy(root, handler, slot) for slot in (1, 2, 3)]
    before = _bindings(database)
    paths[0].unlink()
    handler.shutdown()
    database.close()
    monkeypatch.setattr(woff_watchdog, "Observer", Mock)

    watchdog = woff_watchdog.WoFFWatchdog(config)
    try:
        assert watchdog.start()
        assert _bindings(watchdog.db_manager) == before[1:]
    finally:
        watchdog.stop()


@pytest.mark.parametrize("same_name", [True, False])
def test_vacancy_preserves_all_history_and_reuse_allocates_a_new_career(
    runtime, same_name
):
    root, config, database, handler = runtime
    path = _occupy(root, handler)
    old_id = _bindings(database)[0][2]
    log_path = _write_log(root)
    assert (
        handler.processor.process(str(log_path), "created").status
        is ProcessingStatus.SUCCESS
    )
    claims = root / "Pilot1Claims.txt"
    claims.write_text(
        "1\n8;4;1917;10;35;Arras;A Field;OP;SE.5a;1;"
        "Albatros D.III;Destroyed Confirmed;Albatros\n",
        encoding="ascii",
    )
    assert (
        handler.processor.process(str(claims), "created").status
        is ProcessingStatus.SUCCESS
    )
    before = _history(database)
    assert before["missions"] and before["victories"]
    assert before["diary_entries"] and before["pilot_rpg_stats"]

    _delete(path, handler)

    assert _history(database) == before
    assert _bindings(database) == []
    assert resolve_career(database._get_conn(), pilot_id=old_id).slot is None
    assert database.get_slot_epoch(config.campaign_namespaces[0], 1) == 1
    lines = _dossier_fixture("current_full_sanitized.txt")
    if not same_name:
        lines[4:6] = ["Another", "Synthetic"]
    path.write_bytes(_encode_dossier(lines, path.name))
    assert (
        handler.processor.process(str(path), "created").status
        is ProcessingStatus.SUCCESS
    )
    new_id = _bindings(database)[0][2]
    assert new_id != old_id
    after = _history(database)
    assert all(rows <= after[table] for table, rows in before.items())
    for table in ("missions", "victories", "pilot_rpg_stats"):
        assert database._get_conn().execute(
            f"SELECT count(*) FROM {table} WHERE pilotId=?", (new_id,)
        ).fetchone() == (0,)
    assert (
        handler.processor.process(str(path), "modified").status
        is ProcessingStatus.SUCCESS
    )
    assert _bindings(database)[0][2] == new_id


def test_observed_vacancy_and_epoch_survive_database_reopen(runtime):
    root, config, database, handler = runtime
    path = _occupy(root, handler)
    old_id = _bindings(database)[0][2]
    _delete(path, handler)
    database.close()
    assert database.get_slot_epoch(config.campaign_namespaces[0], 1) == 1
    _occupy(root, handler)
    assert _bindings(database)[0][2] != old_id
    assert database._get_conn().execute("PRAGMA integrity_check").fetchall() == [
        ("ok",)
    ]
    assert database._get_conn().execute("PRAGMA foreign_key_check").fetchall() == []


def test_transient_replace_preserves_binding_through_the_stability_window(
    runtime, monkeypatch
):
    root, config, database, handler = runtime
    path = _occupy(root, handler)
    before = _bindings(database)
    data = path.read_bytes()
    path.unlink()
    delays = []

    def restore_during_wait(delay):
        delays.append(delay)
        path.write_bytes(data)

    monkeypatch.setattr(handler.processor.vacancy_guard, "_sleep", restore_during_wait)
    outcome = handler.processor.process(str(path), "deleted")
    assert outcome.status is ProcessingStatus.SUCCESS
    assert delays and sum(delays) <= config.stability_timeout_sec
    assert _bindings(database) == before
    assert database.get_slot_epoch(config.campaign_namespaces[0], 1) == 0


@pytest.mark.parametrize("remaining", [b"", b"unstable"])
def test_present_but_unparseable_dossier_never_vacates(runtime, remaining):
    root, config, database, handler = runtime
    path = _occupy(root, handler)
    before = _bindings(database)
    path.write_bytes(remaining)
    handler.processor.process(str(path), "deleted")
    assert _bindings(database) == before
    assert database.get_slot_epoch(config.campaign_namespaces[0], 1) == 0


@pytest.mark.parametrize("move_inside_root", [False, True])
def test_move_away_and_move_within_one_namespace(runtime, move_inside_root):
    root, _config, database, handler = runtime
    path = _occupy(root, handler)
    before = _bindings(database)
    target = root / "nested" if move_inside_root else root.parent / "outside"
    target.mkdir()
    destination = target / path.name
    path.rename(destination)
    handler.on_moved(FileMovedEvent(str(path), str(destination)))
    assert handler.scheduler.wait_for_paths([str(path), str(destination)], 2)
    assert _bindings(database) == (before if move_inside_root else [])


def test_zero_count_sources_and_dependent_deletions_do_not_define_occupancy(runtime):
    root, _config, database, handler = runtime
    path = _occupy(root, handler)
    before = _bindings(database)
    for kind in ("Log", "Claims"):
        dependent = root / f"Pilot1{kind}.txt"
        dependent.write_text("0\n", encoding="ascii")
        assert (
            handler.processor.process(str(dependent), "created").status
            is ProcessingStatus.SUCCESS
        )
        _delete(dependent, handler)
        assert _bindings(database) == before
        assert (
            handler.processor.process(str(dependent), "modified").reason
            is ProcessingReason.SNAPSHOT_REJECTED
        )
    _delete(path, handler)
    assert _bindings(database) == []


@pytest.mark.parametrize("root_failure", ["missing", "inaccessible", "partial"])
def test_unavailable_or_incompletely_scanned_root_preserves_bindings(
    runtime, monkeypatch, root_failure
):
    root, _config, database, handler = runtime
    path = _occupy(root, handler)
    before = _bindings(database)
    path.unlink()
    if root_failure == "missing":
        root.rmdir()
    else:
        real_scan = handler.processor.vacancy_guard._scan
        calls = 0

        def fail_scan(directory):
            nonlocal calls
            calls += 1
            if root_failure == "inaccessible" or calls == 2:
                raise PermissionError("synthetic private path must not appear")
            return real_scan(directory)

        monkeypatch.setattr(handler.processor.vacancy_guard, "_scan", fail_scan)
    outcome = handler.processor.process(str(path), "deleted")
    assert outcome.reason is ProcessingReason.VACANCY_DEFERRED
    assert _bindings(database) == before


def test_complete_inventory_rejects_partial_subtree_and_detects_sparse_nested_slots(
    tmp_path, monkeypatch
):
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "Pilot2Dossier.txt").touch()
    (nested / "pilot3dossier.TXT").touch()
    (root / "Pilot1Log.txt").touch()
    assert scan_dossiers(str(root)).slots == frozenset({2, 3})
    from ..ingestion import vacancy

    original = vacancy.os.scandir

    def incomplete(path):
        if Path(path) == nested:
            raise PermissionError("synthetic subtree failure")
        return original(path)

    monkeypatch.setattr(vacancy.os, "scandir", incomplete)
    with pytest.raises(OSError):
        scan_dossiers(str(root))


def test_root_replacement_cannot_confirm_absence():
    inventories = iter(
        [
            DossierInventory((1, 2), frozenset()),
            DossierInventory((1, 3), frozenset()),
        ]
    )
    guard = DossierVacancyGuard(
        0.1, 0.01, scan=lambda _: next(inventories), sleep=lambda _: None
    )
    assert guard.confirm("synthetic", 1).state is VacancyState.DEFERRED


def test_windows_reparse_directory_cannot_prove_absence(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from ..ingestion import vacancy

    root = tmp_path / "synthetic junction"
    root.mkdir()
    original_stat = vacancy.os.stat

    def reparse_stat(path, **kwargs):
        value = original_stat(path, **kwargs)
        if Path(path) == root:
            return SimpleNamespace(st_mode=value.st_mode, st_file_attributes=0x400)
        return value

    monkeypatch.setattr(vacancy.os, "stat", reparse_stat)
    guard = DossierVacancyGuard(0.01, 0.001, sleep=lambda _: None)
    assert guard.confirm(str(root), 1).state is VacancyState.DEFERRED


def test_absence_requires_every_bounded_observation():
    delays = []
    scan = Mock(return_value=DossierInventory((1, 2), frozenset({2, 3})))
    guard = DossierVacancyGuard(3.0, 0.15, scan=scan, sleep=delays.append)
    confirmed = guard.confirm("synthetic", 1)
    assert confirmed.state is VacancyState.ABSENT
    assert scan.call_count == len(delays) + 1
    assert sum(delays) == pytest.approx(3.0)
    scan.return_value = DossierInventory((1, 2), frozenset({1, 2, 3}))
    assert guard.confirm("synthetic", 1).state is VacancyState.PRESENT


def test_release_is_conditional_idempotent_and_rolls_back_epoch_failure(runtime):
    root, config, database, handler = runtime
    _occupy(root, handler)
    namespace = config.campaign_namespaces[0]
    expected = database.get_slot_binding(namespace, 1)
    assert expected is not None
    before = _history(database)
    assert not database.release_slot_binding(replace(expected, pilot_id="stale-id"))
    with database.transaction() as connection:
        connection.execute(
            "CREATE TRIGGER reject_vacancy BEFORE INSERT ON meta "
            "WHEN NEW.key LIKE 'pilot_slot_vacancy:%' "
            "BEGIN SELECT RAISE(ABORT, 'synthetic vacancy failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        database.release_slot_binding(expected)
    assert database.get_slot_binding(namespace, 1) == expected
    assert database.get_slot_epoch(namespace, 1) == 0
    assert _history(database) == before
    with database.transaction() as connection:
        connection.execute("DROP TRIGGER reject_vacancy")
    assert database.release_slot_binding(expected)
    assert not database.release_slot_binding(expected)
    assert database.get_slot_epoch(namespace, 1) == 1
    assert _history(database) == before


@pytest.mark.parametrize("pending_kind", ["dependency", "persistence"])
def test_pre_vacancy_retained_source_cannot_replay_into_same_name_reuse(
    runtime, pending_kind
):
    root, config, database, handler = runtime
    dossier = _occupy(root, handler)
    processor = handler.processor
    path = _write_log(root)
    snapshot = processor.guard.acquire(str(path))
    retained = processor._verified_processing_input(str(path), snapshot, 0)
    if pending_kind == "dependency":
        pending = processor._dependency_pending(retained)
    else:
        pending = ProcessingOutcome.transient(retained, ProcessingReason.SQLITE_BUSY)
    _delete(dossier, handler)
    _occupy(root, handler)
    before = _history(database)
    result = (
        processor.replay_dependency(pending, "created")
        if pending_kind == "dependency"
        else processor.replay(pending, "created")
    )
    assert result.reason is ProcessingReason.IDENTITY_REJECTED
    assert _history(database) == before
    assert database.get_slot_epoch(config.campaign_namespaces[0], 1) == 1


def test_same_name_reuse_after_confirmation_survives_a_busy_persistence_retry(
    runtime, monkeypatch
):
    root, config, database, handler = runtime
    path = _occupy(root, handler)
    old_id = _bindings(database)[0][2]
    data = path.read_bytes()
    path.unlink()
    original_release = database.release_slot_binding
    calls = 0

    def busy_once(expected):
        nonlocal calls
        calls += 1
        if calls == 1:
            path.write_bytes(data)
            raise sqlite3.OperationalError("database is locked")
        return original_release(expected)

    monkeypatch.setattr(database, "release_slot_binding", busy_once)
    monkeypatch.setattr(handler.processor, "_retry_sleep", lambda _: None)
    handler.processor.process(str(path), "deleted")
    handler.processor.process(str(path), "created")
    assert database.get_slot_epoch(config.campaign_namespaces[0], 1) == 1
    assert _bindings(database)[0][2] != old_id


def test_failed_vacancy_stays_bounded_and_dependent_input_waits_for_recovery(
    runtime, monkeypatch
):
    root, config, database, handler = runtime
    path = _occupy(root, handler)
    old_id = _bindings(database)[0][2]
    data = path.read_bytes()
    original_release = database.release_slot_binding
    blocked = Mock(side_effect=sqlite3.OperationalError("database is locked"))
    monkeypatch.setattr(database, "release_slot_binding", blocked)
    handler.processor.vacancy_retry_policy = PersistenceRetryPolicy(
        max_attempts=2, initial_delay=0, max_delay=0
    )
    _delete(path, handler)
    assert blocked.call_count == 2
    assert handler.scheduler.admitted_paths == 1
    assert database.get_slot_epoch(config.campaign_namespaces[0], 1) == 0
    assert _bindings(database)[0][2] == old_id

    path.write_bytes(data)
    log_path = _write_log(root)
    assert handler._handle(str(log_path), "created")
    assert handler.wait_initial([str(log_path)], 2)
    assert handler.metrics()["dependency_pending"] == 1
    assert database._get_conn().execute("SELECT count(*) FROM missions").fetchone() == (
        0,
    )

    monkeypatch.setattr(database, "release_slot_binding", original_release)
    handler.on_created(FileCreatedEvent(str(path)))
    assert handler.scheduler.wait_for_paths([str(path), str(log_path)], 2)
    new_id = _bindings(database)[0][2]
    assert new_id != old_id
    assert database._get_conn().execute("SELECT pilotId FROM missions").fetchall() == [
        (new_id,)
    ]
    assert database.get_slot_epoch(config.campaign_namespaces[0], 1) == 1
    assert handler.scheduler.admitted_paths == 0
    assert handler.metrics()["dependency_retained_bytes"] == 0
    assert handler.processor._confirmed_vacancies == {}


def test_unpersisted_proof_cannot_be_evicted_or_exceed_scheduler_capacity(runtime):
    root, config, database, handler = runtime
    _occupy(root, handler)
    proof = database.get_slot_binding(config.campaign_namespaces[0], 1)
    assert proof is not None
    calls = 0

    def process(*_args):
        nonlocal calls
        calls += 1
        return ProcessingOutcome.reconciled(
            (
                ProcessingReason.VACANCY_DEFERRED
                if calls == 1
                else ProcessingReason.SLOT_VACANT
            ),
            proof if calls == 1 else None,
        )

    scheduler = EventScheduler(
        process,
        max_workers=1,
        max_pending_events=1,
        retry_process=process,
    )
    try:
        assert scheduler.submit("Pilot1Dossier.txt", "deleted")
        assert scheduler.wait_for_paths(["Pilot1Dossier.txt"], 2)
        assert scheduler.admitted_paths == 1
        assert not scheduler.submit("Pilot2Dossier.txt", "deleted")
        assert scheduler.submit("Pilot1Dossier.txt", "created")
        assert scheduler.wait_for_paths(["Pilot1Dossier.txt"], 2)
        assert scheduler.admitted_paths == 0
        assert scheduler.metrics()["saturated"] == 1
    finally:
        scheduler.shutdown()


def test_a_failed_boundary_cannot_be_bypassed_by_a_dossier_path_move(
    runtime, monkeypatch
):
    root, config, database, handler = runtime
    path = _occupy(root, handler)
    old_id = _bindings(database)[0][2]
    data = path.read_bytes()
    release = database.release_slot_binding
    monkeypatch.setattr(
        database,
        "release_slot_binding",
        Mock(side_effect=sqlite3.IntegrityError("synthetic failure")),
    )
    _delete(path, handler)
    assert handler.scheduler.admitted_paths == 1
    monkeypatch.setattr(database, "release_slot_binding", release)
    nested = root / "nested"
    nested.mkdir()
    destination = nested / path.name
    destination.write_bytes(data)
    handler.on_created(FileCreatedEvent(str(destination)))
    assert handler.scheduler.wait_for_paths([str(destination)], 2)
    assert _bindings(database)[0][2] != old_id
    assert database.get_slot_epoch(config.campaign_namespaces[0], 1) == 1
    assert handler.scheduler.admitted_paths == 0


def test_vacancy_in_one_root_is_idempotent_and_does_not_block_another_root(
    runtime, monkeypatch
):
    root, config, database, handler = runtime
    first = _occupy(root, handler)
    _occupy(root, handler, 2)
    other = root.parent / "Other synthetic root"
    other.mkdir()
    processor = FileProcessor(
        database,
        CampaignEngine(database),
        watch_roots=[str(root), str(other)],
        stability_timeout=0.01,
        stability_interval=0.001,
    )
    second = other / first.name
    second.write_bytes(first.read_bytes())
    assert processor.process(str(second), "created").status is ProcessingStatus.SUCCESS
    before = _bindings(database)
    first.unlink()
    confirming = threading.Event()
    continue_confirmation = threading.Event()
    result = []

    def pause(_delay):
        confirming.set()
        assert continue_confirmation.wait(2)

    monkeypatch.setattr(processor.vacancy_guard, "_sleep", pause)
    worker = threading.Thread(
        target=lambda: result.append(processor.process(str(first), "deleted"))
    )
    worker.start()
    try:
        assert confirming.wait(2)
        assert (
            processor.process(str(second), "modified").status
            is ProcessingStatus.SUCCESS
        )
    finally:
        continue_confirmation.set()
        worker.join(2)
    assert not worker.is_alive()
    assert result[0].reason is ProcessingReason.SLOT_VACANT
    for _ in range(3):
        processor.process(str(first), "deleted")
    assert _bindings(database) == [
        row for row in before if row[:2] != (config.campaign_namespaces[0], 1)
    ]
    assert database.get_slot_epoch(config.campaign_namespaces[0], 1) == 1
    assert database.get_slot_epoch(campaign_namespace_for_root(str(other)), 1) == 0
    assert {career.slot for career in list_careers(database._get_conn())} == {
        None,
        1,
        2,
    }


@pytest.mark.parametrize("failed_root", ["missing", "incomplete"])
def test_startup_never_treats_an_unavailable_root_as_empty(
    runtime, monkeypatch, failed_root
):
    root, config, database, handler = runtime
    path = _occupy(root, handler)
    before = _bindings(database)
    path.unlink()
    other = root.parent / "available"
    other.mkdir()
    config.watch_paths.append(str(other))
    if failed_root == "missing":
        root.rmdir()
    else:
        monkeypatch.setattr(
            woff_watchdog,
            "scan_dossiers",
            Mock(side_effect=PermissionError("synthetic failure")),
        )
    handler.shutdown()
    database.close()
    monkeypatch.setattr(woff_watchdog, "Observer", Mock)
    watchdog = woff_watchdog.WoFFWatchdog(config)
    try:
        assert watchdog.start()
        assert _bindings(watchdog.db_manager) == before
    finally:
        watchdog.stop()


def test_startup_vacancy_budget_covers_release_and_a_new_dossier(runtime, monkeypatch):
    root, config, database, handler = runtime
    path = _occupy(root, handler)
    path.unlink()
    handler.shutdown()
    database.close()
    monkeypatch.setattr(woff_watchdog, "Observer", Mock)
    original_wait = WoFFEventHandler.wait_initial
    budgets = []

    def capture_wait(self, paths, timeout):
        if str(path) in paths:
            budgets.append((timeout, self.startup_phase_timeout(paths)))
        return original_wait(self, paths, timeout)

    monkeypatch.setattr(WoFFEventHandler, "wait_initial", capture_wait)
    watchdog = woff_watchdog.WoFFWatchdog(config)
    try:
        assert watchdog.start()
        assert budgets and budgets[0][0] == 2 * budgets[0][1]
        assert _bindings(watchdog.db_manager) == []
    finally:
        watchdog.stop()


def test_vacancy_diagnostics_never_include_source_paths_or_names(
    runtime, caplog, monkeypatch
):
    root, _config, database, handler = runtime
    path = _occupy(root, handler)
    pilot_name = database._get_conn().execute("SELECT name FROM pilots").fetchone()[0]
    path.unlink()
    monkeypatch.setattr(
        handler.processor.vacancy_guard,
        "_scan",
        Mock(side_effect=PermissionError(str(root))),
    )
    caplog.clear()
    handler.processor.process(str(path), "deleted")
    assert "Dossier vacancy deferred" in caplog.text
    assert str(root) not in caplog.text
    assert pilot_name not in caplog.text
    assert "PermissionError" not in caplog.text


def test_read_contract_exposes_source_presence_independently_from_military_status(
    runtime,
):
    root, config, database, handler = runtime
    first = _occupy(root, handler)
    _occupy(root, handler, 3)
    namespace = config.campaign_namespaces[0]
    before = database.list_slot_bindings(namespace)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE pilots SET status='KIA' WHERE id=?", (before[1].pilot_id,)
        )
    assert [binding.slot for binding in database.list_slot_bindings(namespace)] == [
        1,
        3,
    ]
    _delete(first, handler)
    assert database.get_slot_binding(namespace, 1) is None
    assert database.get_slot_binding(namespace, 3) == before[1]
    assert database.get_pilot_state_by_id(before[1].pilot_id)[0] == "KIA"
    assert (
        resolve_career(database._get_conn(), pilot_id=before[0].pilot_id).slot is None
    )


@pytest.mark.parametrize(
    "status", [ProcessingStatus.SUCCESS, ProcessingStatus.PERMANENT_REJECTION]
)
def test_reconciliation_proof_cannot_be_disguised_as_a_file_generation(runtime, status):
    root, config, database, handler = runtime
    _occupy(root, handler)
    proof = database.get_slot_binding(config.campaign_namespaces[0], 1)
    with pytest.raises(ValueError):
        ProcessingOutcome(
            status, ProcessingReason.VACANCY_DEFERRED, confirmed_vacancy=proof
        )
