#!/usr/bin/env python3
"""
Módulo de Eventos e Processamento (handler.py)
══════════════════════════════════════════════════════════════════
Implementa o padrão Pipeline para desacoplar a escuta de ficheiros 
do processamento de domínio (Parse, DB, RPG).
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import ntpath
import os
from datetime import datetime
from typing import Optional, List

from watchdog.events import FileSystemEventHandler

from .database import DatabaseManager
from .campaign_engine import CampaignEngine
from .config import SUPPORTED_WATCHED_EXTENSIONS
from .discovery import is_preview_allowed
from .ingestion.scheduler import EventScheduler
from .ingestion.snapshot import (
    FileGeneration,
    SnapshotFailure,
    StableFileSnapshot,
    StableSnapshotReader,
)

from .parsers.xml_parser import WoFFXMLParser
from .parsers.mission_log_parser import WoFFMissionLogParser
from .parsers.pilot_data_parser import WoFFPilotDataParser
from .parsers.dossier_parser import WoFFDossierParser

log = logging.getLogger("WoFFWatch")


class _PersistenceRejected(Exception):
    """Abort a composable transaction when core persistence reports failure."""


def _safe_filename(path: str) -> str:
    """Return only the final component for native or Windows-style paths."""
    return ntpath.basename(path.replace("/", "\\"))


def get_latest_mission_id(parser):
    """Return the newest mission id from a parser, or None when no missions exist.

    Parser mission lists preserve source order, which may be chronological from
    oldest to newest. Consumers that trigger RPG/diary processing need the
    mission with the greatest (date, time) tuple instead of assuming source order.
    """
    if not parser.missions:
        return None
    latest = max(parser.missions, key=lambda m: (m.date, m.time))
    return latest.id


class FileStabilityGuard(StableSnapshotReader):
    """Compatibility name for the generation-verifying snapshot reader."""


class FileProcessor:
    """
    Pipeline de processamento de ficheiros.
    Desacopla a lógica de negócio do event handler do watchdog.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        campaign_engine: CampaignEngine,
        discovery=None,
        stability_timeout: float = 3.0,
        stability_interval: float = 0.15,
    ):
        self.db_manager = db_manager
        self.campaign_engine = campaign_engine
        self.discovery = discovery
        self.guard = FileStabilityGuard(timeout=stability_timeout, interval=stability_interval)

    def process(
        self,
        path: str,
        event_type: str,
        previous_generation: Optional[FileGeneration] = None,
    ) -> Optional[FileGeneration]:
        """Executa a cadeia de processamento."""
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in {".txt", ".log"} and not is_preview_allowed(path):
                log.debug("Unsupported WoFF filename ignored: %s", _safe_filename(path))
                return None
            snapshot = self.guard.acquire(path)
            if snapshot.generation == previous_generation:
                log.debug("Snapshot generation already processed: %s", _safe_filename(path))
                return snapshot.generation

            # 2. Discovery (Log)
            if self.discovery and os.path.exists(path):
                self.discovery.log_file(path, event_type)

            # 3. Roteamento e Parse
            fname = os.path.basename(path).lower()

            persisted = False
            if ext == ".xml":
                persisted = self._process_xml(path, snapshot)
            elif ext in SUPPORTED_WATCHED_EXTENSIONS:
                persisted = self._process_text(path, fname, snapshot)
            return snapshot.generation if persisted else None

        except SnapshotFailure as failure:
            log.warning(
                "Snapshot rejected: source=%s state=%s attempts=%d",
                _safe_filename(path), failure.kind.value, failure.attempts,
            )
            return None
        except Exception:
            log.exception("Erro no pipeline de processamento para %s", _safe_filename(path))
            return None

    @staticmethod
    def _parser_input(path: str, snapshot: Optional[StableFileSnapshot]) -> tuple[bytes, str]:
        if snapshot is not None:
            return snapshot.data, snapshot.name
        with open(path, "rb") as source:
            return source.read(), os.path.basename(path)

    def _process_xml(self, path: str, snapshot: Optional[StableFileSnapshot] = None) -> bool:
        parser = WoFFXMLParser()
        data, name = self._parser_input(path, snapshot)
        if parser.parse_bytes(data, name):
            # FIX: Captura o pilot_id real devolvido pelo merge.
            real_pilot_id = self.db_manager.merge_and_write(
                pilot=parser.pilot,
                missions=parser.missions,
                victories=parser.victories,
                decorations=parser.decorations,
            )
            if not real_pilot_id:
                return False
            # FIX: Se houver missões e um pilot_id real, processa o fim de missão.
            latest_mission_id = get_latest_mission_id(parser)
            if real_pilot_id and latest_mission_id:
                latest_mission = max(parser.missions, key=lambda m: (m.date, m.time))
                persisted_mission_id = self.db_manager.get_mission_id_by_natural_key(
                    real_pilot_id, latest_mission
                )
                if not persisted_mission_id:
                    return False
                derived_result = self.campaign_engine.process_mission_end(
                    real_pilot_id, persisted_mission_id
                )
                if derived_result is not True:
                    return False
            return True
        return False

    def _process_text(
        self, path: str, fname: str, snapshot: Optional[StableFileSnapshot] = None
    ) -> bool:
        data, name = self._parser_input(path, snapshot)
        if "dossier" in fname:
            parser = WoFFDossierParser()
            if parser.parse_bytes(data, name) and parser.pilot:
                old_status, old_rank = self.db_manager.get_pilot_state(
                    parser.pilot.name
                )

                try:
                    with self.db_manager.transaction():
                        # Compare before the merge, but roll derived writes back if
                        # core persistence rejects this generation.
                        event_date = datetime.fromtimestamp(
                            snapshot.generation.modified_ns / 1_000_000_000
                        ).strftime("%Y-%m-%d") if snapshot is not None else None
                        self.campaign_engine.process_wingmen_changes(
                            parser.pilot.name, parser.wingmen, event_date=event_date
                        )

                        real_pilot_id = self.db_manager.merge_and_write(
                            pilot=parser.pilot,
                            missions=[],
                            victories=[],
                            decorations=parser.decorations,
                            wingmen=parser.wingmen,
                        )
                        if not real_pilot_id:
                            raise _PersistenceRejected

                        new_status = parser.pilot.status
                        new_rank = parser.pilot.rank
                        old_status_str = old_status if old_status is not None else ""
                        old_rank_str = old_rank if old_rank is not None else ""

                        if (old_status_str != new_status) or (
                            old_rank_str != new_rank and new_rank
                        ):
                            self.campaign_engine.process_life_events(
                                parser.pilot.name,
                                str(new_status),
                                str(new_rank),
                                old_status,
                                old_rank,
                                event_date=event_date,
                            )
                except _PersistenceRejected:
                    return False
                return True
            return False

        if fname == "mission.log":
            parser = WoFFMissionLogParser()
            if parser.parse_bytes(data, name):
                real_pilot_id = self.db_manager.merge_and_write(
                    pilot=parser.pilot,
                    missions=[parser.mission] if parser.mission else [],
                    victories=[],
                    decorations=[],
                )
                return bool(real_pilot_id)
            return False

        # Ficheiros de piloto (Log, Claims, Squads)
        parser = WoFFPilotDataParser()
        if parser.parse_bytes(data, name) and parser.pilot:
            # FIX: Usa resolve_pilot_id com source_file para resolver "Pilot X" → UUID real.
            real_pilot_id = self.db_manager.resolve_pilot_id(
                parser.pilot.name,
                source_file=parser.pilot.source_file,
            )
            if not real_pilot_id:
                log.warning(
                    f"Não foi possível resolver pilot_id para '{parser.pilot.name}' "
                    f"(source: {parser.pilot.source_file}). Abortando processamento."
                )
                return False

            persisted_pilot_id = self.db_manager.merge_and_write(
                pilot=parser.pilot,
                missions=parser.missions,
                victories=parser.victories,
                decorations=[],
            )
            if not persisted_pilot_id:
                return False
            # FIX: Só invoca o RPG se tivermos um ID real e missões.
            latest_mission_id = get_latest_mission_id(parser)
            if latest_mission_id:
                latest_mission = max(parser.missions, key=lambda m: (m.date, m.time))
                persisted_mission_id = self.db_manager.get_mission_id_by_natural_key(
                    real_pilot_id, latest_mission
                )
                if not persisted_mission_id:
                    return False
                derived_result = self.campaign_engine.process_mission_end(
                    real_pilot_id, persisted_mission_id
                )
                if derived_result is not True:
                    return False
            return True
        return False


class WoFFEventHandler(FileSystemEventHandler):
    """
    Listener puro do Watchdog.
    Filtra ficheiros e delega para o FileProcessor.
    """

    IGNORED = {"desktop.ini", "thumbs.db", ".tmp", "~", ".bak", ".lnk"}

    def __init__(
        self,
        config,
        db_manager: DatabaseManager,
        campaign_engine: CampaignEngine,
        discovery=None,
    ):
        config.validate()
        self.config = config
        self.watched_extensions = set(config.watched_extensions)
        self.discovery = discovery
        self.processor = FileProcessor(db_manager, campaign_engine, discovery, config.stability_timeout_sec, config.stability_check_interval_sec)
        self.scheduler = EventScheduler(
            self._execute_pipeline,
            max_workers=config.max_workers,
            max_pending_events=config.max_pending_events,
            retry_process=self._execute_retry_pipeline,
        )
        self._startup_admission_timeout = config.stability_timeout_sec

    def on_modified(self, event):
        if not event.is_directory:
            self._handle(str(event.src_path), "modified")

    def on_created(self, event):
        if not event.is_directory:
            self._handle(str(event.src_path), "created")

    def on_moved(self, event):
        if not event.is_directory:
            self._handle(str(event.dest_path), "moved")

    def _handle(self, path: str, event_type: str):
        bn = os.path.basename(path).lower()
        ext = os.path.splitext(path)[1].lower()

        if ext not in self.watched_extensions or any(p in bn for p in self.IGNORED):
            return False
        if ext in {".txt", ".log"} and not is_preview_allowed(path):
            if self.discovery:
                self.discovery.log_file(path, event_type)
            return False

        return self.scheduler.submit(path, event_type)

    def submit_initial(self, path: str) -> bool:
        """Route startup reconciliation through the bounded live scheduler."""
        return self.scheduler.submit(
            path, "initial", admission_timeout=self._startup_admission_timeout
        )

    def wait_initial(self, paths: list[str], timeout: float) -> bool:
        """Wait for a startup dependency phase without creating another queue."""
        return self.scheduler.wait_for_paths(paths, timeout)

    def _execute_pipeline(self, path: str, event_type: str):
        """Método executado na thread pool."""
        log.info(f"Detectado [{event_type}]: {os.path.basename(path)}")
        return self.processor.process(path, event_type)

    def _execute_retry_pipeline(
        self, path: str, event_type: str, previous_generation: Optional[FileGeneration]
    ) -> Optional[FileGeneration]:
        """Process a coalesced event while suppressing an identical generation."""
        log.info(f"Detectado [{event_type}]: {os.path.basename(path)}")
        return self.processor.process(path, event_type, previous_generation)

    def metrics(self):
        return self.scheduler.metrics()

    def shutdown(self):
        log.info("A aguardar conclusão das threads de processamento...")
        self.scheduler.shutdown()
