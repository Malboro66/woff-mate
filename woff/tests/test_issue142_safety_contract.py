"""P1 #142 transaction/inventory safety regressions using synthetic pilot data."""
from __future__ import annotations

from typing import Any, cast
from unittest.mock import patch

from ..campaign_engine import CampaignEngine
from ..config import WatchdogConfig
from ..database import DatabaseManager
from ..handler import WoFFEventHandler
from ..ingestion.outcome import ProcessingReason
from .test_handler_integration import _encoded_dossier


def _fixture(tmp_path):
    root = tmp_path / "campaign"
    source = root / "alpha" / "Pilot1Dossier.txt"
    source.parent.mkdir(parents=True)
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "export" / "sqlite.db"),
        watched_extensions=[".txt"],
        stability_timeout_sec=0.1,
        stability_check_interval_sec=0.001,
    )
    db = DatabaseManager(config.export_path, campaign_namespaces=config.campaign_namespaces)
    engine = CampaignEngine(db)
    handler = WoFFEventHandler(config, db, engine)
    return root, source, db, engine, handler


def _pilot(db):
    return db._get_conn().execute(
        "SELECT p.name, b.pilotId FROM pilot_slot_bindings b "
        "JOIN pilots p ON p.id = b.pilotId WHERE b.slot = 1"
    ).fetchone()


def test_known_source_must_not_rebind_when_duplicate_exists(tmp_path):
    root, source, db, engine, handler = _fixture(tmp_path)
    try:
        source.write_bytes(_encoded_dossier("Alpha", "Synthetic", "Captain", "A Squadron"))
        assert handler.processor.process(str(source), "initial").reason is ProcessingReason.SUCCESS
        original = _pilot(db)
        assert original[0] == "Alpha Synthetic"

        duplicate = root / "bravo" / "Pilot1Dossier.txt"
        duplicate.parent.mkdir()
        duplicate.write_bytes(_encoded_dossier("Gamma", "Synthetic", "Captain", "A Squadron"))
        source.write_bytes(_encoded_dossier("Beta", "Synthetic", "Captain", "A Squadron"))
        outcome = handler.processor.process(str(source), "modified")
        assert outcome.reason is ProcessingReason.IDENTITY_REJECTED
        assert _pilot(db) == original
        assert db._get_conn().execute("SELECT COUNT(*) FROM pilots WHERE name = 'Beta Synthetic'").fetchone()[0] == 0
        assert handler._startup_inventory_rejected
    finally:
        handler.shutdown()
        db.close()


def test_duplicate_between_snapshot_and_commit_rolls_back_all_writes(tmp_path):
    root, source, db, engine, handler = _fixture(tmp_path)
    try:
        source.write_bytes(_encoded_dossier("Alpha", "Synthetic", "Captain", "A Squadron"))
        assert handler.processor.process(str(source), "initial").reason is ProcessingReason.SUCCESS
        original = _pilot(db)
        source.write_bytes(_encoded_dossier("Beta", "Synthetic", "Captain", "A Squadron"))
        duplicate = root / "bravo" / "Pilot1Dossier.txt"
        duplicate.parent.mkdir()
        real_import = engine.process_dossier_import

        def introduce_duplicate(*args, **kwargs):
            duplicate.write_bytes(_encoded_dossier("Gamma", "Synthetic", "Captain", "A Squadron"))
            return real_import(*args, **kwargs)

        with patch.object(engine, "process_dossier_import", side_effect=introduce_duplicate):
            outcome = handler.processor.process(str(source), "modified")
        assert duplicate.is_file()
        assert outcome.reason is ProcessingReason.IDENTITY_REJECTED
        assert _pilot(db) == original
        assert db._get_conn().execute("SELECT COUNT(*) FROM pilots WHERE name = 'Beta Synthetic'").fetchone()[0] == 0
    finally:
        handler.shutdown()
        db.close()


def test_late_saturated_positive_revokes_verified_inventory(tmp_path):
    root, source, db, engine, handler = _fixture(tmp_path)
    try:
        handler.begin_startup_inventory()
        handler.record_startup_sources([{"Pilot*Dossier.txt": []}])
        assert handler.finish_startup_inventory(0)
        assert handler.reconciliation_complete is True
        late = root / "Pilot2Dossier.txt"
        late.write_bytes(_encoded_dossier("Late", "Synthetic", "Captain", "A Squadron"))
        with patch.object(handler.scheduler, "submit", return_value=False):
            assert handler._handle(str(late), "created") is False
        assert handler._startup_inventory_verified is False
        assert handler.reconciliation_complete is False
        assert handler._startup_inventory_rejected is True
        assert handler.startup_inventory_epoch() == 1
        assert handler._handle(str(late), "modified") is False
    finally:
        handler.shutdown()
        db.close()


def test_final_startup_inventory_rejects_changed_dossier_generation(tmp_path):
    """Unchanged filenames do not prove the previously imported bytes are current."""
    import pytest
    from .. import woff_watchdog

    root = tmp_path / "campaign"
    source = root / "nested" / "Pilot1Dossier.txt"
    source.parent.mkdir(parents=True)
    source.write_bytes(_encoded_dossier("Alpha", "Synthetic", "Captain", "A Squadron"))
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "export" / "sqlite.db"),
        watched_extensions=[".txt"],
        stability_timeout_sec=0.1,
        stability_check_interval_sec=0.001,
    )
    real_wait = WoFFEventHandler.wait_initial
    changed = []

    def mutate_after_phase(self, paths, timeout):
        settled = real_wait(self, paths, timeout)
        if str(source) in paths and not changed:
            source.write_bytes(
                _encoded_dossier("Beta", "Synthetic", "Captain", "A Squadron")
            )
            changed.append(True)
        return settled

    with patch.object(woff_watchdog, "Observer"), patch.object(
        WoFFEventHandler, "wait_initial", mutate_after_phase
    ):
        watchdog = woff_watchdog.WoFFWatchdog(config)
        with pytest.raises(RuntimeError, match="startup recursive inventory changed"):
            watchdog.start()
    assert changed == [True]


def test_startup_rejection_does_not_commit_an_ambiguous_initial_worker(tmp_path):
    """A live duplicate after preflight invalidates the initial worker before commit."""
    import pytest
    from .. import woff_watchdog

    root = tmp_path / "campaign"
    approved = root / "alpha" / "Pilot1Dossier.txt"
    alternate = root / "bravo" / "Pilot1Dossier.txt"
    approved.parent.mkdir(parents=True)
    approved.write_bytes(_encoded_dossier("Alpha", "Synthetic", "Captain", "A Squadron"))
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "export" / "sqlite.db"),
        watched_extensions=[".txt"],
        stability_timeout_sec=0.1,
        stability_check_interval_sec=0.001,
    )
    baseline = DatabaseManager(
        config.export_path, campaign_namespaces=config.campaign_namespaces,
    )
    baseline_handler = WoFFEventHandler(config, baseline, CampaignEngine(baseline))
    try:
        assert baseline_handler.processor.process(str(approved), "initial").reason is ProcessingReason.SUCCESS
        previous = _pilot(baseline)
    finally:
        baseline_handler.shutdown()
        baseline.close()

    approved.write_bytes(_encoded_dossier("Beta", "Synthetic", "Captain", "A Squadron"))
    submit = WoFFEventHandler.submit_initial
    injected = []

    def submit_with_new_duplicate(self, path):
        if not injected:
            alternate.parent.mkdir()
            alternate.write_bytes(
                _encoded_dossier("Gamma", "Synthetic", "Captain", "A Squadron")
            )
            injected.append(True)
            assert self._handle(str(alternate), "created") is False
        return submit(self, path)

    with patch.object(woff_watchdog, "Observer"), patch.object(
        WoFFEventHandler, "submit_initial", submit_with_new_duplicate,
    ):
        watchdog = woff_watchdog.WoFFWatchdog(config)
        with pytest.raises((OSError, RuntimeError)):
            watchdog.start()
    assert injected == [True]
    verify = DatabaseManager(
        config.export_path, campaign_namespaces=config.campaign_namespaces,
    )
    try:
        assert _pilot(verify) == previous
        assert verify._get_conn().execute(
            "SELECT COUNT(*) FROM pilots WHERE name='Beta Synthetic'"
        ).fetchone()[0] == 0
    finally:
        verify.close()


def test_prelock_callback_delay_cannot_rebind_after_finalization(tmp_path):
    """A callback overtaken by finish still cannot persist a competing slot."""
    import threading
    from .. import woff_watchdog

    root, source, db, engine, handler = _fixture(tmp_path)
    try:
        source.write_bytes(_encoded_dossier("Alpha", "Synthetic", "Captain", "A Squadron"))
        assert handler.processor.process(str(source), "initial").reason is ProcessingReason.SUCCESS
        original = _pilot(db)
        handler.begin_startup_inventory()
        handler.record_startup_sources([woff_watchdog._scan_startup_sources(str(root))])
        duplicate = root / "bravo" / "Pilot1Dossier.txt"
        duplicate.parent.mkdir()
        duplicate.write_bytes(_encoded_dossier("Gamma", "Synthetic", "Captain", "A Squadron"))
        source.write_bytes(_encoded_dossier("Beta", "Synthetic", "Captain", "A Squadron"))
        true_lock = handler._startup_inventory_lock
        entered, release = threading.Event(), threading.Event()
        results = {}

        class DelayedAcquire:
            def __enter__(self):
                if threading.current_thread().name == "delayed-observer":
                    entered.set()
                    assert release.wait(5)
                true_lock.acquire()
                return self

            def __exit__(self, *_args):
                true_lock.release()

        handler._startup_inventory_lock = cast(Any, DelayedAcquire())
        callback = threading.Thread(
            target=lambda: results.update(
                submitted=handler._handle(str(source), "modified")
            ),
            name="delayed-observer",
        )
        callback.start()
        try:
            assert entered.wait(5)
            assert handler.finish_startup_inventory(0) is True
        finally:
            release.set()
            callback.join(5)
        assert not callback.is_alive()
        assert results == {"submitted": False}
        assert _pilot(db) == original
        assert handler._startup_inventory_rejected
    finally:
        handler.shutdown()
        db.close()
