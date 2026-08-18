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
from .. import woff_watchdog

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
        self._handler_pool = self.handler._pool
    
    def tearDown(self):
        # Restaurar e encerrar o pool real antes de libertar o banco no Windows.
        self.handler._pool = self._handler_pool
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

        # FIX: Mockar o pool para executar sincronamente, evitando race conditions
        # e eliminando a necessidade de aceder a _process (atributo privado).
        original_pool = self.handler._pool
        self.handler._pool = MagicMock()

        def sync_submit(fn, *args, **kwargs):
            """Executa a tarefa imediatamente no thread principal."""
            fn(*args, **kwargs)
            return MagicMock()  # Future-like object

        self.handler._pool.submit = sync_submit

        try:
            # Disparar evento — o processamento corre sincronamente
            self.handler.on_modified(event)

            # Verificar se chegou à Base de Dados
            status, rank = self.db.get_pilot_state("James Percival Hartley")
            self.assertIsNotNone(status)
            self.assertEqual(status, "Active")
        finally:
            self.handler._pool = original_pool

    def test_inflight_debounce(self):
        """Testa que eventos rápidos duplicados são ignorados pelo set _inflight."""
        xml_path = os.path.join(self.tmp_dir, "campaign.xml")
        
        # Escrever ficheiro real no disco
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(MOCK_XML_VALID)
            
        from watchdog.events import FileModifiedEvent
        event = FileModifiedEvent(xml_path)
        
        # Fazer Mock do submit para não executar o processamento real,
        # permitindo-nos contar apenas quantas vezes foi chamado.
        self.handler._pool = MagicMock()
        
        # Disparar 5 eventos idênticos imediatamente
        self.handler.on_modified(event)
        self.handler.on_modified(event)
        self.handler.on_modified(event)
        self.handler.on_modified(event)
        self.handler.on_modified(event)
        
        # O _inflight set deve ter bloqueado os 4 últimos eventos
        # O submit só deve ter sido chamado 1 vez
        self.assertEqual(self.handler._pool.submit.call_count, 1)
        
        # Simular o final do processamento (limpar _inflight)
        with self.handler._inflight_lock:
            self.handler._inflight.discard(xml_path)
            
        # Disparar outro evento, agora já deve ser aceite novamente
        self.handler.on_modified(event)
        self.assertEqual(self.handler._pool.submit.call_count, 2)

    def test_configured_components_are_wired(self):
        self.handler.shutdown()
        self.config.watched_extensions = [".xml", ".log"]
        self.handler = WoFFEventHandler(self.config, self.db, self.engine)
        self._handler_pool = self.handler._pool
        self.assertEqual(self.handler.processor.guard.timeout, 1.0)
        self.assertEqual(self.handler.processor.guard.interval, 0.05)
        self.assertEqual(self.handler.watched_extensions, {".xml", ".log"})

    def test_unsupported_extension_prevents_executor_creation(self):
        self.handler.shutdown()
        self.config.watched_extensions = [".dat"]
        with patch("woff.handler.ThreadPoolExecutor") as executor:
            with self.assertRaises(ValueError):
                WoFFEventHandler(self.config, self.db, self.engine)
        executor.assert_not_called()

    def test_invalid_config_prevents_startup_components(self):
        self.handler.shutdown()
        self.config.max_workers = True
        with patch("woff.handler.ThreadPoolExecutor") as executor:
            with self.assertRaises(ValueError):
                WoFFEventHandler(self.config, self.db, self.engine)
        executor.assert_not_called()

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

if __name__ == "__main__":
    unittest.main()
