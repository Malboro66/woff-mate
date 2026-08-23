import unittest
import tempfile
import threading
import os
import shutil
from unittest.mock import patch, MagicMock


from ..config import WatchdogConfig
from ..database import DatabaseManager
from ..campaign_engine import CampaignEngine
from ..handler import WoFFEventHandler
from ..ingestion.scheduler import EventScheduler
from .. import woff_watchdog
from .test_dossier_parser import _encode_dossier

# Mock de um ficheiro de campanha XML válido
MOCK_XML_VALID = """<?xml version="1.0" encoding="UTF-8"?>
<Campaign>
  <Pilot>
    <PilotName>James Percival Hartley</PilotName>
    <Nation>RFC</Nation>
    <Rank>Captain</Rank>
    <Squadron>No. 56 Squadron RFC</Squadron>
    <Aircraft>SE.5a</Aircraft>
    <Status>Active</Status>
  </Pilot>
</Campaign>
"""


def _encoded_dossier(first_name: str, last_name: str, rank: str, squadron: str):
    lines = ["Null"] * 105
    for index, value in {
        3: rank,
        4: first_name,
        5: last_name,
        11: "60",
        16: "1",
        17: "1",
        41: "50",
        46: "2",
        52: "10",
        83: squadron,
        84: "SE.5a",
        88: "Filescamp",
        89: "Arras",
    }.items():
        lines[index] = value
    return _encode_dossier(lines, "Pilot1Dossier.txt")

class TestHandlerIntegration(unittest.TestCase):
    """Testa o handler com ficheiros reais temporários."""
    
    @classmethod
    def setUpClass(cls):
        # Desativar logs durante os testes para não poluir o terminal
        import logging
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        import logging
        logging.disable(logging.NOTSET)

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")
        self.db = DatabaseManager(self.db_path)
        self.engine = CampaignEngine(self.db)
        
        self.config = WatchdogConfig(
            watch_paths=[self.tmp_dir],
            stability_timeout_sec=1.0, # Reduzir timeout para testes rápidos
            stability_check_interval_sec=0.05
        )
        
        self.handler = WoFFEventHandler(
            config=self.config,
            db_manager=self.db,
            campaign_engine=self.engine
        )
    
    def tearDown(self):
        try:
            self.handler.shutdown()
        finally:
            self.db.close()
            if os.path.exists(self.tmp_dir):
                shutil.rmtree(self.tmp_dir)
    
    def test_file_modified_event(self):
        """Simula evento de modificação e verifica processamento assíncrono determinístico."""
        xml_path = os.path.join(self.tmp_dir, "campaign.xml")

        # Escrever ficheiro real no disco
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(MOCK_XML_VALID)

        from watchdog.events import FileModifiedEvent
        event = FileModifiedEvent(xml_path)

        self.handler.on_modified(event)
        self.handler.shutdown()

        status, rank = self.db.get_pilot_state("James Percival Hartley")
        self.assertIsNone(status)
        self.assertIsNone(rank)
        self.assertEqual(
            self.db._get_conn().execute("SELECT COUNT(*) FROM pilots").fetchone(),
            (0,),
        )

    def test_pilot_log_without_sibling_dossier_performs_no_write(self):
        log_path = os.path.join(self.tmp_dir, "Pilot1Log.txt")
        with open(log_path, "w", encoding="cp1252") as source:
            source.write(
                "1\n6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;"
                "SE.5a;No. 56 Squadron RFC;troops;Target;N50;E2;;"
                "Mission completed.\n"
            )

        self.assertIsNone(self.handler.processor.process(log_path, "created"))
        self.assertEqual(
            self.db._get_conn().execute("SELECT COUNT(*) FROM pilots").fetchone(),
            (0,),
        )
        self.assertEqual(
            self.db._get_conn().execute("SELECT COUNT(*) FROM missions").fetchone(),
            (0,),
        )

    def test_mission_log_cannot_create_identityless_pilot(self):
        mission_log_path = os.path.join(self.tmp_dir, "mission.log")
        with open(mission_log_path, "w", encoding="utf-8") as source:
            source.write(
                "<Mission><Params Date=\"6/15/1917\" "
                "Weather=\"OFFDynamicMissionWeather.xml\"/>"
                "<AirFormation Country=\"RFC\" SquadName=\"No. 56\">"
                "<Unit IsPlayer=\"y\" Type=\"SE.5a\"/>"
                "</AirFormation></Mission>\nMissionEnded"
            )

        self.assertIsNone(
            self.handler.processor.process(mission_log_path, "created")
        )
        self.assertEqual(
            self.db._get_conn().execute("SELECT COUNT(*) FROM pilots").fetchone(),
            (0,),
        )
        self.assertEqual(
            self.db._get_conn().execute("SELECT COUNT(*) FROM missions").fetchone(),
            (0,),
        )

    def test_new_slot_log_waits_for_changed_dossier_before_writing(self):
        dossier_path = os.path.join(self.tmp_dir, "Pilot1Dossier.txt")
        log_path = os.path.join(self.tmp_dir, "Pilot1Log.txt")
        with open(dossier_path, "wb") as source:
            source.write(
                _encoded_dossier("Alice", "Able", "Captain", "Old Sqn")
            )
        with open(log_path, "w", encoding="cp1252") as source:
            source.write(
                "1\n6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;"
                "SE.5a;New Sqn;troops;Target;N50;E2;;Mission completed.\n"
            )

        processor = self.handler.processor
        self.assertIsNotNone(processor.process(dossier_path, "initial"))
        old_id = self.db._get_conn().execute(
            "SELECT id FROM pilots"
        ).fetchone()[0]
        old_snapshot = self.db._get_conn().execute(
            "SELECT name, rank, squadron, source_file FROM pilots WHERE id=?",
            (old_id,),
        ).fetchone()

        with open(dossier_path, "wb") as source:
            source.write(
                _encoded_dossier("Bob", "Baker", "Lieutenant", "New Sqn")
            )
        self.assertIsNone(processor.process(log_path, "modified"))
        self.assertEqual(
            self.db._get_conn().execute("SELECT COUNT(*) FROM missions").fetchone(),
            (0,),
        )
        self.assertEqual(
            self.db._get_conn().execute(
                "SELECT name, rank, squadron, source_file FROM pilots WHERE id=?",
                (old_id,),
            ).fetchone(),
            old_snapshot,
        )

        self.assertIsNotNone(processor.process(dossier_path, "modified"))
        new_id = self.db._get_conn().execute(
            "SELECT pilotId FROM pilot_slot_bindings WHERE slot=1"
        ).fetchone()[0]
        self.assertNotEqual(new_id, old_id)
        self.assertEqual(
            self.db._get_conn().execute(
                "SELECT COUNT(*) FROM diary_entries WHERE pilotId IN (?, ?)",
                (old_id, new_id),
            ).fetchone(),
            (0,),
        )
        self.assertIsNotNone(processor.process(log_path, "retry"))
        self.assertEqual(
            self.db._get_conn().execute(
                "SELECT pilotId FROM missions"
            ).fetchone(),
            (new_id,),
        )
        self.assertEqual(
            self.db._get_conn().execute(
                "SELECT name, rank, squadron, source_file FROM pilots WHERE id=?",
                (old_id,),
            ).fetchone(),
            old_snapshot,
        )

    def test_move_uses_destination_and_filters_moves_away(self):
        from watchdog.events import FileMovedEvent

        self.handler.shutdown()
        self.handler.scheduler = MagicMock()
        destination = os.path.join(self.tmp_dir, "campaign.xml")
        self.handler.on_moved(FileMovedEvent(os.path.join(self.tmp_dir, "upload.tmp"), destination))
        self.handler.scheduler.submit.assert_called_once_with(destination, "moved")

        self.handler.scheduler.reset_mock()
        self.handler.on_moved(FileMovedEvent(destination, os.path.join(self.tmp_dir, "campaign.tmp")))
        self.handler.scheduler.submit.assert_not_called()

    def test_configured_components_are_wired(self):
        self.handler.shutdown()
        self.config.watched_extensions = [".xml", ".log"]
        self.config.max_pending_events = 17
        self.handler = WoFFEventHandler(self.config, self.db, self.engine)
        self.assertEqual(self.handler.processor.guard.timeout, 1.0)
        self.assertEqual(self.handler.processor.guard.interval, 0.05)
        self.assertEqual(self.handler.watched_extensions, {".xml", ".log"})
        self.assertEqual(self.handler.scheduler.max_pending_events, 17)

    def test_worker_and_admission_limits_are_passed_to_scheduler(self):
        self.handler.shutdown()
        self.config.max_workers = 3
        self.config.max_pending_events = 29
        with patch("woff.handler.EventScheduler") as scheduler:
            WoFFEventHandler(self.config, self.db, self.engine)
        scheduler.assert_called_once()
        self.assertEqual(scheduler.call_args.kwargs["max_workers"], 3)
        self.assertEqual(scheduler.call_args.kwargs["max_pending_events"], 29)

    def test_unsupported_extension_prevents_executor_creation(self):
        self.handler.shutdown()
        self.config.watched_extensions = [".dat"]
        with patch("woff.handler.EventScheduler") as scheduler:
            with self.assertRaises(ValueError):
                WoFFEventHandler(self.config, self.db, self.engine)
        scheduler.assert_not_called()

    def test_invalid_config_prevents_startup_components(self):
        self.handler.shutdown()
        self.config.max_workers = True
        with patch("woff.handler.EventScheduler") as scheduler:
            with self.assertRaises(ValueError):
                WoFFEventHandler(self.config, self.db, self.engine)
        scheduler.assert_not_called()

        self.config.max_workers = 1
        self.config.export_path = " "
        with patch.object(woff_watchdog, "DatabaseManager") as database:
            with self.assertRaises(ValueError):
                woff_watchdog.WoFFWatchdog(self.config)
        database.assert_not_called()

    def test_main_applies_configured_log_level(self):
        config = WatchdogConfig(log_level="error")
        with patch.object(woff_watchdog, "load_config", return_value=config), patch.object(woff_watchdog, "run_parse_file"), patch.object(woff_watchdog.logging.getLogger(), "setLevel") as set_level, patch("sys.argv", ["woff-watchdog", "--parse-file", "sample.xml"]):
            woff_watchdog.main()
        set_level.assert_called_with(woff_watchdog.logging.ERROR)


class TestWatchdogStartup(unittest.TestCase):
    def test_live_file_created_after_observer_start_is_not_baseline_submitted(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        path = os.path.join(tmp_dir, "Pilot1Log.txt")
        config = WatchdogConfig(
            watch_paths=[tmp_dir], export_path=os.path.join(tmp_dir, "live.db"),
            watched_extensions=[".txt"], max_workers=2, max_pending_events=2,
        )
        processing_started = threading.Event()
        release_processing = threading.Event()
        processed = []
        initial_submissions = []

        class Handler:
            def __init__(self, *_args):
                self.scheduler = EventScheduler(
                    self.process, 2, 2, retry_process=self.retry
                )

            def process(self, submitted_path, event_type, previous=None):
                processing_started.set()
                assert release_processing.wait(2)
                if previous != "generation":
                    processed.append(os.path.basename(submitted_path).lower())
                return "generation"

            def retry(self, submitted_path, event_type, previous):
                return self.process(submitted_path, event_type, previous)

            def _handle(self, submitted_path, event_type):
                return self.scheduler.submit(submitted_path, event_type)

            def submit_initial(self, submitted_path):
                initial_submissions.append(submitted_path)
                return self.scheduler.submit(submitted_path, "initial")

            def wait_initial(self, paths, timeout):
                return self.scheduler.wait_for_paths(paths, timeout)

            def shutdown(self):
                self.scheduler.shutdown()

        class Observer:
            def schedule(self, handler, watched_path, recursive=True):
                self.handler = handler

            def start(self):
                self.running = True
                with open(path, "w", encoding="utf-8") as source:
                    source.write("approved live file")
                assert self.handler._handle(path, "created")
                assert processing_started.wait(2)
                assert self.handler._handle(path.upper(), "modified")
                release_processing.set()

            def stop(self):
                self.running = False

            def join(self, timeout=None):
                pass

        with patch.object(woff_watchdog, "catalog_medals"), patch.object(
            woff_watchdog, "catalog_squadrons"
        ), patch.object(woff_watchdog, "CampaignEngine"), patch.object(
            woff_watchdog, "WoFFEventHandler", Handler
        ), patch.object(woff_watchdog, "Observer", Observer), patch.object(
            woff_watchdog.glob, "glob", return_value=[]
        ) as baseline:
            watchdog = woff_watchdog.WoFFWatchdog(config)
            self.assertFalse(os.path.exists(path))
            self.assertTrue(watchdog.start())
            handler = watchdog._handler
            watchdog.stop()

        self.assertEqual(baseline.call_count, 4)
        self.assertEqual(initial_submissions, [])
        self.assertEqual(processed, ["pilot1log.txt"])
        self.assertIsNotNone(handler)
        assert handler is not None
        self.assertEqual(handler.scheduler.admitted_paths, 0)
        self.assertEqual(handler.scheduler.metrics(), {
            "queued": 0, "active": 0, "coalesced": 1,
            "rejected": 0, "retried": 1,
        })

    def test_partially_started_observer_is_owned_and_original_error_survives_cleanup(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        config = WatchdogConfig(
            watch_paths=[tmp_dir], export_path=os.path.join(tmp_dir, "partial.db")
        )
        calls = []

        class PartialObserver:
            def schedule(self, handler, path, recursive=True):
                calls.append("schedule")

            def start(self):
                calls.append("start")
                raise RuntimeError("original observer startup failure")

            def stop(self):
                calls.append("stop")
                raise RuntimeError("cleanup stop failure")

            def join(self, timeout=None):
                calls.append(("join", timeout))

        handler = MagicMock()
        database = MagicMock()
        with patch.object(woff_watchdog, "DatabaseManager", return_value=database), patch.object(
            woff_watchdog, "CampaignEngine"
        ), patch.object(woff_watchdog, "WoFFEventHandler", return_value=handler), patch.object(
            woff_watchdog, "Observer", PartialObserver
        ):
            watchdog = woff_watchdog.WoFFWatchdog(config)
            with self.assertRaisesRegex(
                RuntimeError, "original observer startup failure"
            ):
                watchdog.start()

        self.assertEqual(calls, ["schedule", "start", "stop", ("join", 5)])
        handler.shutdown.assert_called_once_with()
        database.close.assert_called_once_with()

    def test_startup_phases_wait_for_all_dossiers_before_dependents(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        files = {
            pattern: [os.path.join(tmp_dir, pattern.replace("*", "1"))]
            for pattern in (
                "Pilot*Dossier.txt", "Pilot*Log.txt",
                "Pilot*Claims.txt", "Pilot*Squads.txt",
            )
        }
        config = WatchdogConfig(
            watch_paths=[tmp_dir], export_path=os.path.join(tmp_dir, "ordered.db"),
            watched_extensions=[".txt"], max_workers=4, max_pending_events=8,
        )
        completed = []

        class Handler:
            def __init__(self, *_args):
                self.scheduler = EventScheduler(self.process, 4, 8)

            def process(self, path, event_type):
                completed.append(os.path.basename(path))

            def submit_initial(self, path):
                return self.scheduler.submit(path, "initial")

            def wait_initial(self, paths, timeout):
                return self.scheduler.wait_for_paths(paths, timeout)

            def shutdown(self):
                self.scheduler.shutdown()

        observer = MagicMock()
        observer.start.side_effect = lambda: completed.append("observer-started")
        with patch.object(woff_watchdog, "catalog_medals"), patch.object(
            woff_watchdog, "catalog_squadrons"
        ), patch.object(woff_watchdog, "CampaignEngine"), patch.object(
            woff_watchdog, "WoFFEventHandler", Handler
        ), patch.object(woff_watchdog, "Observer", return_value=observer), patch.object(
            woff_watchdog.glob, "glob",
            side_effect=lambda path: files[os.path.basename(path)],
        ):
            watchdog = woff_watchdog.WoFFWatchdog(config)
            self.assertTrue(watchdog.start())
            watchdog.stop()

        self.assertEqual(completed, [
            "observer-started", "Pilot1Dossier.txt", "Pilot1Log.txt",
            "Pilot1Claims.txt", "Pilot1Squads.txt",
        ])

    def test_startup_failure_rolls_back_observer_scheduler_and_database(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        config = WatchdogConfig(
            watch_paths=[tmp_dir], export_path=os.path.join(tmp_dir, "rollback.db")
        )
        observer = MagicMock()
        handler = MagicMock()
        database = MagicMock()

        with patch.object(woff_watchdog, "DatabaseManager", return_value=database), patch.object(
            woff_watchdog, "CampaignEngine"
        ), patch.object(woff_watchdog, "WoFFEventHandler", return_value=handler), patch.object(
            woff_watchdog, "Observer", return_value=observer
        ), patch.object(
            woff_watchdog, "catalog_medals", side_effect=RuntimeError("catalog failed")
        ), patch.object(woff_watchdog.os.path, "exists", return_value=True):
            watchdog = woff_watchdog.WoFFWatchdog(config)
            with self.assertRaisesRegex(RuntimeError, "catalog failed"):
                watchdog.start()

        observer.stop.assert_called_once_with()
        observer.join.assert_called_once_with(timeout=5)
        handler.shutdown.assert_called_once_with()
        database.close.assert_called_once_with()

    def _start_with_extensions(self, watched_extensions):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        os.mkdir(os.path.join(tmp_dir, "Medals"))
        os.mkdir(os.path.join(tmp_dir, "Scratchpad"))
        config = WatchdogConfig(
            watch_paths=[tmp_dir],
            export_path=os.path.join(tmp_dir, "test.db"),
            watched_extensions=watched_extensions,
        )

        patches = [
            patch.object(woff_watchdog, "catalog_medals"),
            patch.object(woff_watchdog, "catalog_squadrons"),
            patch.object(woff_watchdog, "CampaignEngine"),
            patch.object(woff_watchdog, "WoFFEventHandler"),
            patch.object(woff_watchdog, "Observer"),
            patch.object(woff_watchdog.glob, "glob", return_value=[]),
        ]
        mocks = [patcher.start() for patcher in patches]
        for patcher in patches:
            self.addCleanup(patcher.stop)

        watchdog = woff_watchdog.WoFFWatchdog(config)
        self.addCleanup(watchdog.db_manager.close)
        self.assertTrue(watchdog.start())
        return mocks

    def test_txt_disabled_skips_initial_sync_but_starts_other_components(self):
        medals, squadrons, engine, handler, observer, pilot_glob = (
            self._start_with_extensions([".xml", ".log"])
        )

        pilot_glob.assert_not_called()
        medals.assert_called_once()
        squadrons.assert_called_once()
        engine.assert_called_once()
        handler.assert_called_once()
        observer.return_value.schedule.assert_called_once()
        observer.return_value.start.assert_called_once()

    def test_txt_enabled_runs_initial_sync_and_starts_runtime_components(self):
        _, _, engine, handler, observer, pilot_glob = self._start_with_extensions(
            [".txt"]
        )

        self.assertEqual(pilot_glob.call_count, 4)
        engine.assert_called_once()
        handler.assert_called_once()
        observer.return_value.schedule.assert_called_once()
        observer.return_value.start.assert_called_once()

    def test_observation_precedes_bounded_startup_reconciliation(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        pilot_path = os.path.join(tmp_dir, "Pilot1Log.txt")
        with open(pilot_path, "w", encoding="utf-8") as source:
            source.write("synthetic")
        config = WatchdogConfig(
            watch_paths=[tmp_dir],
            export_path=os.path.join(tmp_dir, "startup.db"),
            watched_extensions=[".txt"],
            max_workers=1,
            max_pending_events=1,
        )
        order = []
        blocked = threading.Event()
        resume = threading.Event()
        generation = {"value": "A"}
        side_effects = {
            "missions": 0, "victories": 0, "wingmen": 0, "diary": 0,
        }

        class StartupHandler:
            def __init__(self, *_args, **_kwargs):
                self.scheduler = EventScheduler(
                    self.process, 1, 1, retry_process=self.retry_process
                )

            def process(self, path, event_type, previous=None):
                observed = generation["value"]
                if observed == "A":
                    blocked.set()
                    test_case.assertTrue(resume.wait(2))
                    observed = generation["value"]
                if observed != previous:
                    for name in side_effects:
                        side_effects[name] += 1
                return observed

            def retry_process(self, path, event_type, previous):
                return self.process(path, event_type, previous)

            def _handle(self, path, event_type):
                return self.scheduler.submit(path, event_type)

            def submit_initial(self, path):
                order.append("baseline")
                accepted = self.scheduler.submit(path, "initial")
                resume.set()
                return accepted

            def wait_initial(self, paths, timeout):
                return self.scheduler.wait_for_paths(paths, timeout)

            def shutdown(self):
                self.scheduler.shutdown()

        test_case = self

        class StartupObserver:
            def schedule(self, handler, path, recursive=True):
                self.handler = handler

            def start(self):
                order.append("observer")
                self.handler._handle(pilot_path, "created")
                test_case.assertTrue(blocked.wait(2))
                generation["value"] = "B"
                self.handler._handle(pilot_path.upper(), "modified")
                generation["value"] = "C"
                self.handler._handle(pilot_path, "modified")

            def stop(self):
                pass

            def join(self, timeout=None):
                pass

        with patch.object(woff_watchdog, "catalog_medals"), patch.object(
            woff_watchdog, "catalog_squadrons"
        ), patch.object(woff_watchdog, "CampaignEngine"), patch.object(
            woff_watchdog, "WoFFEventHandler", StartupHandler
        ), patch.object(woff_watchdog, "Observer", StartupObserver), patch.object(
            woff_watchdog.glob, "glob", side_effect=[[pilot_path], [], [], []]
        ):
            watchdog = woff_watchdog.WoFFWatchdog(config)
            self.addCleanup(watchdog.db_manager.close)
            self.assertTrue(watchdog.start())
            handler = watchdog._handler
            self.assertIsNotNone(handler)
            watchdog.stop()

        self.assertEqual(order, ["observer", "baseline"])
        self.assertEqual(generation["value"], "C")
        self.assertEqual(side_effects, {
            "missions": 1, "victories": 1, "wingmen": 1, "diary": 1,
        })
        assert handler is not None
        self.assertEqual(handler.scheduler.admitted_paths, 0)
        self.assertEqual(handler.scheduler.metrics(), {
            "queued": 0, "active": 0, "coalesced": 3,
            "rejected": 0, "retried": 1,
        })

if __name__ == "__main__":
    unittest.main()
