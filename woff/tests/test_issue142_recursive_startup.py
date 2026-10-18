"""Synthetic-only regression tests for Issue #142 recursive startup inventory."""
from __future__ import annotations

import os
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
