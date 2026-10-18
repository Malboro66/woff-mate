"""Synthetic-only regression tests for Issue #142 recursive startup inventory."""
from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from .. import woff_watchdog
from ..config import WatchdogConfig
from ..campaign_namespace import campaign_namespace_for_root
from .test_handler_integration import _encoded_dossier


def _scan(root: Path) -> dict[str, list[str]]:
    return woff_watchdog._scan_startup_sources(str(root))


def test_nested_source_types_are_enumerated_once_with_root_sources(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    nested = root / "nested" / "inside"
    nested.mkdir(parents=True)
    files = (
        root / "Pilot1Dossier.txt",
        nested / "Pilot2Dossier.txt",
        nested / "Pilot2Log.txt",
        nested / "Pilot3Claims.txt",
        nested / "Pilot4Squads.txt",
    )
    for p in files:
        p.write_bytes(b"synthetic")
    (nested / "unrelated.txt").write_bytes(b"ignored")
    (nested / "Pilot2Dossier.bin").write_bytes(b"ignored")
    inventory = _scan(root)
    assert set(inventory) == set(woff_watchdog._STARTUP_PILOT_PATTERNS)
    discovered = {Path(p) for paths in inventory.values() for p in paths}
    assert discovered == set(files)
    assert len(discovered) == sum(len(paths) for paths in inventory.values())


def test_nested_scan_does_not_follow_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    nested = root / "nested"
    nested.mkdir(parents=True)
    original_scandir = os.scandir

    def inaccessible(path: str):
        if os.path.normcase(os.fspath(path)) == os.path.normcase(str(nested)):
            raise PermissionError("synthetic-denied-subtree")
        return original_scandir(path)

    with patch.object(woff_watchdog.os, "scandir", side_effect=inaccessible):
        with pytest.raises(PermissionError, match="synthetic-denied-subtree"):
            _scan(root)


def test_changed_recursive_inventory_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    (root / "Pilot1Dossier.txt").write_bytes(b"synthetic")
    original_scandir = os.scandir
    mutated = False

    def changed(path: str):
        nonlocal mutated
        if os.path.normcase(os.fspath(path)) == os.path.normcase(str(root)) and not mutated:
            mutated = True
            (root / "new-nested").mkdir()
            # Set a guaranteed changed mtime even on filesystems with
            # directory timestamp granularity / deferred updates.
            metadata = root.stat()
            os.utime(root, ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 5_000_000_000))
        return original_scandir(path)

    with patch.object(woff_watchdog.os, "scandir", side_effect=changed):
        with pytest.raises(OSError, match="changed-startup-inventory"):
            _scan(root)
    assert mutated


def test_invalid_subtree_stops_before_positive_admission(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    (root / "Pilot1Dossier.txt").write_bytes(b"synthetic")
    (root / "blocked").mkdir()
    output = tmp_path / "output" / "sqlite.db"
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(output),
        watched_extensions=[".txt"],
    )
    observer = MagicMock()
    handler = MagicMock()
    original_scandir = os.scandir

    def broken(path: str):
        if os.path.basename(os.fspath(path)) == "blocked":
            raise PermissionError("synthetic-inaccessible-subtree")
        return original_scandir(path)

    with patch.object(woff_watchdog, "Observer", return_value=observer), patch.object(
        woff_watchdog, "WoFFEventHandler", return_value=handler
    ), patch.object(woff_watchdog, "CampaignEngine"), patch.object(
        woff_watchdog, "catalog_medals"
    ), patch.object(woff_watchdog, "catalog_squadrons"), patch.object(
        woff_watchdog.os, "scandir", side_effect=broken
    ):
        watchdog = woff_watchdog.WoFFWatchdog(config)
        with pytest.raises(PermissionError, match="synthetic-inaccessible-subtree"):
            watchdog.start()
    handler.submit_initial.assert_not_called()
    handler.submit_initial_vacancy.assert_not_called()
    observer.stop.assert_called_once()
    handler.shutdown.assert_called_once()


def test_nested_dossier_is_persisted_on_startup_without_later_event(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    nested = root / "nested"
    nested.mkdir(parents=True)
    source = nested / "Pilot1Dossier.txt"
    source.write_bytes(_encoded_dossier("Fictional", "Airman", "Captain", "A Squadron"))
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "export" / "db.sqlite"),
        watched_extensions=[".txt"],
        stability_timeout_sec=0.1,
        stability_check_interval_sec=0.001,
    )
    observer = MagicMock()
    with patch.object(woff_watchdog, "Observer", return_value=observer), patch.object(
        woff_watchdog, "catalog_medals"
    ), patch.object(woff_watchdog, "catalog_squadrons"):
        watchdog = woff_watchdog.WoFFWatchdog(config)
        try:
            assert watchdog.start() is True
            pilots = watchdog.db_manager._get_conn().execute(
                "SELECT name FROM pilots"
            ).fetchall()
            assert len(pilots) == 1
            assert "Fictional" in pilots[0][0]
        finally:
            watchdog.stop()
    observer.schedule.assert_called_once()
    assert observer.schedule.call_args.kwargs["recursive"] is True


def test_nested_same_pilot_slot_remains_separate_across_roots(tmp_path: Path) -> None:
    roots = [tmp_path / "campaign-a", tmp_path / "campaign-b"]
    for root, first_name in zip(roots, ("Ada", "Bea")):
        nested = root / "nested"
        nested.mkdir(parents=True)
        (nested / "Pilot1Dossier.txt").write_bytes(
            _encoded_dossier(first_name, "Fictional", "Captain", "A Squadron")
        )
    config = WatchdogConfig(
        watch_paths=[str(root) for root in roots],
        export_path=str(tmp_path / "export" / "db.sqlite"),
        watched_extensions=[".txt"],
        stability_timeout_sec=0.1,
        stability_check_interval_sec=0.001,
    )
    with patch.object(woff_watchdog, "Observer") as observer, patch.object(
        woff_watchdog, "catalog_medals"
    ), patch.object(woff_watchdog, "catalog_squadrons"):
        watchdog = woff_watchdog.WoFFWatchdog(config)
        try:
            assert watchdog.start() is True
            conn = watchdog.db_manager._get_conn()
            pilot_ids = dict(conn.execute("SELECT name, id FROM pilots"))
            assert set(pilot_ids) == {"Ada Fictional", "Bea Fictional"}
            bindings = conn.execute(
                "SELECT campaign_namespace, slot, pilotId FROM pilot_slot_bindings"
            ).fetchall()
            assert set(bindings) == {
                (campaign_namespace_for_root(str(root)), 1, pilot_ids[name])
                for root, name in zip(roots, ("Ada Fictional", "Bea Fictional"))
            }
        finally:
            watchdog.stop()
    assert observer.call_count == 2



def test_all_nested_source_families_use_bounded_phase_order(tmp_path: Path) -> None:
    roots = [tmp_path / "alpha", tmp_path / "bravo"]
    samples = []
    for index, root in enumerate(roots, start=1):
        nested = root / "nested"
        nested.mkdir(parents=True)
        for suffix in ("Dossier", "Log", "Claims", "Squads"):
            source = nested / f"Pilot{index}{suffix}.txt"
            source.write_bytes(b"synthetic")
            samples.append(source)

    config = WatchdogConfig(
        watch_paths=[str(root) for root in roots],
        export_path=str(tmp_path / "output" / "db.sqlite"),
        watched_extensions=[".txt"],
        stability_timeout_sec=0.05,
        stability_check_interval_sec=0.001,
    )
    admissions = []
    waits = []
    observer_calls = []

    class Handler:
        def __init__(self, *_args):
            pass

        def submit_initial(self, path: str) -> bool:
            admissions.append(Path(path))
            return True

        def startup_phase_timeout(self, files):
            return 0.5

        def wait_initial(self, files, timeout):
            waits.append(tuple(Path(path) for path in files))
            assert timeout == 0.5
            return True

        def shutdown(self):
            pass

    class Observer:
        def schedule(self, _handler, path, recursive):
            observer_calls.append((path, recursive))

        def start(self):
            pass

        def stop(self):
            pass

        def join(self, timeout):
            pass

    with patch.object(woff_watchdog, "Observer", Observer), patch.object(
        woff_watchdog, "WoFFEventHandler", Handler
    ), patch.object(woff_watchdog, "CampaignEngine"), patch.object(
        woff_watchdog, "catalog_medals"
    ), patch.object(woff_watchdog, "catalog_squadrons"):
        watchdog = woff_watchdog.WoFFWatchdog(config)
        try:
            assert watchdog.start()
        finally:
            watchdog.stop()

    phase_groups = [
        tuple(root / "nested" / f"Pilot{i}{suffix}.txt"
              for i, root in enumerate(roots, start=1))
        for suffix in ("Dossier", "Log", "Claims", "Squads")
    ]
    assert tuple(admissions) == tuple(path for phase in phase_groups for path in phase)
    assert waits == phase_groups
    assert observer_calls == [(str(root), True) for root in roots]
    assert set(admissions) == set(samples)

@pytest.mark.parametrize("family", ("Dossier", "Log", "Claims", "Squads"))
def test_duplicate_slot_in_one_root_fails_closed(tmp_path: Path, family: str) -> None:
    root = tmp_path / "campaign"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / f"Pilot1{family}.txt").write_bytes(b"synthetic")
    (nested / f"PILOT1{family.upper()}.TXT").write_bytes(b"synthetic")
    with pytest.raises(OSError, match="ambiguous-startup-pilot-slot"):
        _scan(root)


def test_case_variants_follow_live_slot_policy(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    nested = root / "nested"
    nested.mkdir(parents=True)
    for name in (
        "pilot1dossier.txt",
        "PILOT2LOG.TXT",
        "pIlOt3cLaImS.tXt",
        "Pilot4squads.TXT",
    ):
        (nested / name).write_bytes(b"synthetic")
    inventory = _scan(root)
    assert [len(inventory[k]) for k in woff_watchdog._STARTUP_PILOT_PATTERNS] == [1] * 4


def test_irrelevant_file_alias_is_ignored_but_approved_alias_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    harmless = root / "irrelevant.txt"
    supported = root / "Pilot1Dossier.txt"
    harmless.write_bytes(b"unrelated")
    supported.write_bytes(b"synthetic")
    original_scandir = os.scandir

    class Alias:
        def __init__(self, entry):
            self._entry = entry
            self.name = entry.name
            self.path = entry.path

        def stat(self, **kwargs):
            return self._entry.stat(**kwargs)

        def is_symlink(self):
            return True

        def is_dir(self, *, follow_symlinks=True):
            return False

    @contextmanager
    def simulated_scandir(path: str, alias_name: str):
        with original_scandir(path) as iterator:
            entries = [Alias(entry) if entry.name == alias_name else entry
                       for entry in iterator]
            yield entries

    with patch.object(
        woff_watchdog.os, "scandir",
        side_effect=lambda directory: simulated_scandir(directory, harmless.name),
    ):
        assert _scan(root)[woff_watchdog._STARTUP_PILOT_PATTERNS[0]] == [
            str(supported)
        ]
    with patch.object(
        woff_watchdog.os, "scandir",
        side_effect=lambda directory: simulated_scandir(directory, supported.name),
    ):
        with pytest.raises(OSError, match="unverified-startup-source"):
            _scan(root)


def test_file_added_after_child_scan_forces_startup_retry_not_false_success(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    first = root / "a-child"
    sibling = root / "z-child"
    first.mkdir(parents=True)
    sibling.mkdir()
    source = first / "Pilot2Dossier.txt"
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "export" / "db.sqlite"),
        watched_extensions=[".txt"],
    )
    original_scandir = os.scandir
    added = False

    @contextmanager
    def ordered_root_entries(directory: str):
        # scandir order is filesystem-specific; explicitly visit the first
        # child before the sibling that triggers a late write.
        with original_scandir(directory) as iterator:
            yield sorted(iterator, key=lambda entry: entry.name)

    def simulate_late_nested_source(directory: str):
        nonlocal added
        if str(directory) == str(root):
            return ordered_root_entries(directory)
        if str(directory) == str(sibling) and not added:
            added = True
            source.write_bytes(b"synthetic")
        return original_scandir(directory)

    fake_handler = MagicMock()
    with patch.object(
        woff_watchdog.os, "scandir", side_effect=simulate_late_nested_source
    ), patch.object(woff_watchdog, "Observer"), patch.object(
        woff_watchdog, "WoFFEventHandler", return_value=fake_handler
    ), patch.object(woff_watchdog, "CampaignEngine"), patch.object(
        woff_watchdog, "catalog_medals"
    ), patch.object(woff_watchdog, "catalog_squadrons"):
        watchdog = woff_watchdog.WoFFWatchdog(config)
        with pytest.raises(RuntimeError, match="startup recursive inventory changed"):
            watchdog.start()
    assert added
    fake_handler.submit_initial.assert_not_called()
    fake_handler.shutdown.assert_called_once()


def test_live_event_during_startup_cannot_run_a_worker(
    tmp_path: Path,
) -> None:
    """A concurrent live positive must fail startup without a preflight DB write."""
    from ..handler import WoFFEventHandler
    from ..database import DatabaseManager
    from ..campaign_engine import CampaignEngine

    root = tmp_path / "campaign"
    root.mkdir()
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "export" / "db.sqlite"),
        watched_extensions=[".txt"],
    )
    db = DatabaseManager(config.export_path, campaign_namespaces=config.campaign_namespaces)
    handler = WoFFEventHandler(config, db, CampaignEngine(db))
    path = str(root / "Pilot2Dossier.txt")
    try:
        handler.begin_startup_inventory()
        with patch.object(handler.scheduler, "submit", return_value=True) as submit:
            assert handler._handle(path, "created") is False
            submit.assert_not_called()
            assert handler.startup_inventory_epoch() == 1
            assert handler.finish_startup_inventory(0) is False
            # Once startup is closed, ordinary live admission still works.
            assert handler._handle(path, "modified") is True
            submit.assert_called_once_with(path, "modified")
    finally:
        handler.shutdown()
        db.close()


def test_live_scheduler_rejection_during_startup_remains_a_blocker(
    tmp_path: Path,
) -> None:
    from ..handler import WoFFEventHandler
    from ..database import DatabaseManager
    from ..campaign_engine import CampaignEngine

    root = tmp_path / "campaign"
    root.mkdir()
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "export" / "db.sqlite"),
        watched_extensions=[".txt"],
    )
    db = DatabaseManager(config.export_path, campaign_namespaces=config.campaign_namespaces)
    handler = WoFFEventHandler(config, db, CampaignEngine(db))
    try:
        handler.begin_startup_inventory()
        with patch.object(handler.scheduler, "submit", return_value=False):
            assert not handler._handle(str(root / "Pilot1Dossier.txt"), "created")
        assert handler.startup_inventory_epoch() == 1
        assert handler.finish_startup_inventory() is False
    finally:
        handler.shutdown()
        db.close()



def test_phase_event_invalidates_verification_epoch(tmp_path: Path) -> None:
    """An accepted live update during Log must invalidate Dossier-first startup."""
    root = tmp_path / "campaign"
    root.mkdir()
    (root / "Pilot1Dossier.txt").write_bytes(b"synthetic")
    (root / "Pilot1Log.txt").write_bytes(b"synthetic")
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "export" / "db.sqlite"),
        watched_extensions=[".txt"],
    )
    handler = MagicMock()
    epoch = 0
    seen_log = False

    def get_epoch() -> int:
        return epoch

    def phase_wait(paths, _timeout):
        nonlocal epoch, seen_log
        if any(str(path).endswith("Pilot1Log.txt") for path in paths):
            epoch += 1
            seen_log = True
        return True

    handler.startup_inventory_epoch.side_effect = get_epoch
    handler.wait_initial.side_effect = phase_wait
    handler.submit_initial.return_value = True
    handler.startup_phase_timeout.return_value = 0.1

    with patch.object(woff_watchdog, "Observer"), patch.object(
        woff_watchdog, "WoFFEventHandler", return_value=handler
    ), patch.object(woff_watchdog, "CampaignEngine"), patch.object(
        woff_watchdog, "catalog_medals"
    ), patch.object(woff_watchdog, "catalog_squadrons"), patch.object(
        woff_watchdog.WoFFWatchdog, "_reconcile_vacant_slots", return_value=None
    ):
        watchdog = woff_watchdog.WoFFWatchdog(config)
        with pytest.raises(RuntimeError, match="startup recursive inventory changed"):
            watchdog.start()
    assert seen_log
    handler.shutdown.assert_called_once()
    handler.finish_startup_inventory.assert_not_called()


def test_finalization_rejects_new_event_after_last_epoch_read(
    tmp_path: Path,
) -> None:
    """An event just before finalization must not disappear after the final scan."""
    from ..handler import WoFFEventHandler
    from ..database import DatabaseManager
    from ..campaign_engine import CampaignEngine

    root = tmp_path / "campaign"
    root.mkdir()
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "export" / "db.sqlite"),
        watched_extensions=[".txt"],
    )
    db = DatabaseManager(config.export_path, campaign_namespaces=config.campaign_namespaces)
    handler = WoFFEventHandler(config, db, CampaignEngine(db))
    try:
        handler.begin_startup_inventory()
        initial_epoch = handler.startup_inventory_epoch()
        with patch.object(handler.scheduler, "submit", return_value=True) as submit:
            assert not handler._handle(str(root / "Pilot1Dossier.txt"), "created")
            submit.assert_not_called()
        assert handler.startup_inventory_epoch() == initial_epoch + 1
        assert handler.finish_startup_inventory(initial_epoch) is False
    finally:
        handler.shutdown()
        db.close()


@pytest.mark.parametrize("family", ("Log", "Claims", "Squads"))
def test_known_dossier_in_other_subdirectory_is_rejected(
    tmp_path: Path, family: str,
) -> None:
    root = tmp_path / "campaign"
    (root / "alpha").mkdir(parents=True)
    (root / "bravo").mkdir()
    (root / "alpha" / "Pilot1Dossier.txt").write_bytes(b"synthetic")
    (root / "bravo" / f"Pilot1{family}.txt").write_bytes(b"synthetic")
    with pytest.raises(OSError, match="unresolvable-startup-dependent-identity"):
        _scan(root)


@pytest.mark.parametrize("family", ("Log", "Claims", "Squads"))
def test_known_dossier_beside_dependent_is_accepted(
    tmp_path: Path, family: str,
) -> None:
    root = tmp_path / "campaign"
    subfolder = root / "nested"
    subfolder.mkdir(parents=True)
    dossier = subfolder / "Pilot1Dossier.txt"
    dependent = subfolder / f"Pilot1{family}.txt"
    dossier.write_bytes(b"synthetic")
    dependent.write_bytes(b"synthetic")
    inventory = _scan(root)
    assert inventory["Pilot*Dossier.txt"] == [str(dossier)]
    assert inventory[f"Pilot*{family}.txt"] == [str(dependent)]


def test_unknown_dossier_keeps_existing_pending_policy(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    path = root / "Pilot1Log.txt"
    path.write_bytes(b"synthetic")
    inventory = _scan(root)
    assert inventory["Pilot*Dossier.txt"] == []
    assert inventory["Pilot*Log.txt"] == [str(path)]


def test_cross_directory_dependent_cannot_submit_any_startup_sources(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    (root / "alpha").mkdir(parents=True)
    (root / "bravo").mkdir()
    (root / "alpha" / "Pilot1Dossier.txt").write_bytes(b"synthetic")
    (root / "bravo" / "Pilot1Log.txt").write_bytes(b"synthetic")
    handler = MagicMock()
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "export" / "db.sqlite"),
        watched_extensions=[".txt"],
    )
    with patch.object(woff_watchdog, "Observer"), patch.object(
        woff_watchdog, "WoFFEventHandler", return_value=handler
    ), patch.object(woff_watchdog, "CampaignEngine"), patch.object(
        woff_watchdog, "catalog_medals"
    ), patch.object(woff_watchdog, "catalog_squadrons"):
        watchdog = woff_watchdog.WoFFWatchdog(config)
        with pytest.raises(OSError, match="unresolvable-startup-dependent-identity"):
            watchdog.start()
    handler.submit_initial.assert_not_called()
    handler.submit_initial_vacancy.assert_not_called()
    handler.shutdown.assert_called_once()


@pytest.mark.parametrize("event_type", ("deleted", "moved-away"))
def test_directory_departure_during_startup_cannot_run_vacancy_worker(
    tmp_path: Path, event_type: str,
) -> None:
    """A subtree departure fails cold startup before any vacancy persistence."""
    from ..handler import WoFFEventHandler
    from ..database import DatabaseManager
    from ..campaign_engine import CampaignEngine

    root = tmp_path / "campaign"
    root.mkdir()
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "export" / "db.sqlite"),
        watched_extensions=[".txt"],
    )
    db = DatabaseManager(config.export_path, campaign_namespaces=config.campaign_namespaces)
    handler = WoFFEventHandler(config, db, CampaignEngine(db))
    try:
        handler.begin_startup_inventory()
        with patch.object(
            handler.processor, "vacancy_paths_for_directory"
        ) as vacancy, patch.object(handler.scheduler, "submit") as submit:
            handler._reconcile_directory(str(root / "nested"), event_type)
            vacancy.assert_not_called()
            submit.assert_not_called()
        assert handler.startup_inventory_epoch() == 1
        assert handler.finish_startup_inventory(0) is False
    finally:
        handler.shutdown()
        db.close()
