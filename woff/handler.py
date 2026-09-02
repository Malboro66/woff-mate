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
import sqlite3
import time
import threading
import weakref
from contextlib import nullcontext
from typing import Any, Optional, List, Sequence

from watchdog.events import FileSystemEventHandler

from .campaign_namespace import (
    CampaignNamespaceError, CampaignNamespaceResolver, campaign_namespace_label,
)
from .database import (
    DatabaseManager,
    MergeWriteOutcome,
    SQLITE_BUSY_TIMEOUT_SECONDS,
)
from .campaign_engine import CampaignEngine
from .config import SUPPORTED_WATCHED_EXTENSIONS
from .discovery import is_preview_allowed
from .ingestion.scheduler import EventScheduler
from .ingestion.outcome import (
    ProcessingOutcome,
    ProcessingReason,
    ProcessingStatus,
    PersistenceRetryPolicy,
    VerifiedProcessingInput,
    classify_transient_sqlite_error,
)
from .ingestion.snapshot import (
    FileGeneration,
    SnapshotFailure,
    StableFileSnapshot,
    StableSnapshotReader,
)
from .ingestion.vacancy import DossierVacancyGuard, VacancyState
from .identity import (
    PilotIdentityError,
    PilotIdentityEvidence,
    PilotIdentityKind,
    PilotIdentityRejected,
    PilotIdentityUnavailable,
    PilotSlotBinding,
    dossier_source_name,
    is_dossier_source,
    pilot_slot,
)
from .normalization import canonical_mission_order_key

from .parsers.xml_parser import WoFFXMLParser
from .parsers.mission_log_parser import WoFFMissionLogParser
from .parsers.pilot_data_parser import WoFFPilotDataParser
from .parsers.dossier_parser import WoFFDossierParser

log = logging.getLogger("WoFFWatch")


class _MissionDerivedWriteRejected(Exception):
    pass


def _safe_filename(path: str) -> str:
    """Return only the final component for native or Windows-style paths."""
    return ntpath.basename(path.replace("/", "\\"))


def _requires_dependent_identity(source_name: str) -> bool:
    filename = _safe_filename(source_name).lower()
    return (
        pilot_slot(source_name) is not None
        and "dossier" not in filename
        and filename != "mission.log"
    )


def _mission_order_key(mission):
    return canonical_mission_order_key(
        mission.date,
        mission.time,
        (
            mission.missionType,
            mission.aircraft,
            mission.sector,
            mission.source_file,
            mission.id,
        ),
    )


def get_latest_mission(parser):
    """Return the newest valid mission under the canonical temporal contract.

    Parser mission lists preserve source order, which may be chronological from
    oldest to newest. Known times outrank missing times on the same date, and
    semantic fields provide a stable final tie-breaker.
    """
    candidates = []
    for mission in parser.missions:
        order_key = _mission_order_key(mission)
        if order_key is not None:
            candidates.append((order_key, mission))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def get_latest_mission_id(parser):
    """Return the deterministic latest valid mission ID, if one exists."""
    latest = get_latest_mission(parser)
    return latest.id if latest is not None else None


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
        watch_roots: Optional[Sequence[str]] = None,
    ):
        self.db_manager = db_manager
        self.campaign_engine = campaign_engine
        self.discovery = discovery
        self.guard = FileStabilityGuard(timeout=stability_timeout, interval=stability_interval)
        self.vacancy_guard = DossierVacancyGuard(stability_timeout, stability_interval)
        self.vacancy_retry_policy = PersistenceRetryPolicy()
        self._retry_sleep = time.sleep
        self._campaign_namespaces = CampaignNamespaceResolver(watch_roots)
        self._slot_locks: weakref.WeakValueDictionary[tuple[str, int], Any] = (
            weakref.WeakValueDictionary()
        )
        self._slot_locks_guard = threading.Lock()
        # The scheduler reserves one admission slot for each unpersisted proof.
        # Keep it namespace-keyed as well, so sibling sources and path moves
        # cannot bypass a confirmed boundary while SQLite is unavailable.
        self._confirmed_vacancies: dict[tuple[str, int], PilotSlotBinding] = {}

    def _slot_lock(self, path: str):
        if pilot_slot(path) is None:
            return nullcontext()
        try:
            key = self._dependent_binding_key(path, _safe_filename(path))
        except PilotIdentityError:
            return nullcontext()
        with self._slot_locks_guard:
            lock = self._slot_locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._slot_locks[key] = lock
            return lock

    def vacancy_pending(self, binding: PilotSlotBinding) -> bool:
        """Nonblocking scheduler check for a retained, unpersisted boundary."""
        return self._confirmed_vacancies.get(
            (binding.campaign_namespace, binding.slot)
        ) == binding

    def process(
        self,
        path: str,
        event_type: str,
        previous_generation: Optional[FileGeneration] | ProcessingOutcome = None,
    ) -> ProcessingOutcome:
        # Serialize one logical slot, not every root or all workers. This also
        # covers Dossier aliases in different subdirectories of the same root.
        with self._slot_lock(path):
            return self._process(path, event_type, previous_generation)

    def _process(
        self,
        path: str,
        event_type: str,
        previous_generation: Optional[FileGeneration] | ProcessingOutcome = None,
    ) -> ProcessingOutcome:
        """Process one path and return an explicit acknowledgement contract."""
        try:
            confirmed_vacancy = (
                previous_generation.confirmed_vacancy
                if isinstance(previous_generation, ProcessingOutcome) else None
            )
            if pilot_slot(path) is not None:
                key = self._dependent_binding_key(path, _safe_filename(path))
                confirmed_vacancy = self._confirmed_vacancies.get(key, confirmed_vacancy)
            if confirmed_vacancy is not None or (is_dossier_source(path) and (
                event_type in {"deleted", "moved-away", "initial-vacancy"}
            )):
                vacancy = self._reconcile_vacancy(path, confirmed_vacancy)
                if vacancy is not None:
                    if (vacancy.confirmed_vacancy is not None
                            and _requires_dependent_identity(path)):
                        # Fresh dependent bytes observed after the boundary
                        # belong to the next epoch, but cannot write before the
                        # vacancy and the next Dossier both commit.
                        snapshot = self.guard.acquire(path)
                        next_epoch = self.db_manager.get_slot_epoch(
                            *self._dependent_binding_key(path, snapshot.name)
                        ) + 1
                        return self._dependency_pending(
                            VerifiedProcessingInput(snapshot, slot_epoch=next_epoch)
                        )
                    return vacancy
            previous_outcome = (
                previous_generation
                if isinstance(previous_generation, ProcessingOutcome)
                else None
            )
            if isinstance(previous_generation, ProcessingOutcome):
                previous_generation = (
                    previous_generation.generation
                    if (
                        previous_generation.status
                        is ProcessingStatus.TRANSIENT_FAILURE
                        or previous_generation.reason
                        is ProcessingReason.RETRY_TERMINATED
                    )
                    else previous_generation.acknowledged_generation
                )
            ext = os.path.splitext(path)[1].lower()
            if ext in {".txt", ".log"} and not is_preview_allowed(path):
                log.debug("Unsupported WoFF filename ignored: %s", _safe_filename(path))
                return ProcessingOutcome.permanent(
                    ProcessingReason.UNSUPPORTED_SOURCE
                )
            snapshot = self.guard.acquire(path)
            if snapshot.generation == previous_generation:
                if (
                    previous_outcome is not None
                    and (
                        previous_outcome.status
                        is ProcessingStatus.TRANSIENT_FAILURE
                        or previous_outcome.reason
                        is ProcessingReason.RETRY_TERMINATED
                    )
                ):
                    log.debug(
                        "Terminal retry generation already considered: %s",
                        _safe_filename(path),
                    )
                    return ProcessingOutcome.permanent(
                        ProcessingReason.RETRY_TERMINATED
                    )
                log.debug("Snapshot generation already processed: %s", _safe_filename(path))
                return ProcessingOutcome.unchanged(
                    snapshot.generation,
                    self._resolved_dependency(snapshot),
                )

            slot_epoch = None
            if pilot_slot(path) is not None:
                slot_epoch = self.db_manager.get_slot_epoch(
                    *self._dependent_binding_key(path, snapshot.name)
                )
            try:
                retry_input = self._verified_processing_input(path, snapshot, slot_epoch)
            except SnapshotFailure:
                if not _requires_dependent_identity(snapshot.name):
                    raise
                retry_input = VerifiedProcessingInput(snapshot, slot_epoch=slot_epoch)
                return self._dependency_pending(retry_input)
            return self._process_verified(
                retry_input, event_type, record_discovery=True
            )

        except SnapshotFailure as failure:
            log.warning(
                "Snapshot rejected: source=%s state=%s attempts=%d",
                _safe_filename(path), failure.kind.value, failure.attempts,
            )
            return ProcessingOutcome.permanent(
                ProcessingReason.SNAPSHOT_REJECTED
            )
        except PilotIdentityError as error:
            return self._identity_rejection(path, error)
        except Exception:
            log.exception("Erro no pipeline de processamento para %s", _safe_filename(path))
            return ProcessingOutcome.permanent(
                ProcessingReason.UNEXPECTED_ERROR
            )

    def _reconcile_vacancy(
        self, path: str, confirmed: Optional[PilotSlotBinding] = None
    ) -> Optional[ProcessingOutcome]:
        namespace, slot = self._dependent_binding_key(path, _safe_filename(path))
        root = self._campaign_namespaces.root_for(path)
        if confirmed is not None and (confirmed.campaign_namespace, confirmed.slot) != (
            namespace, slot
        ):
            raise PilotIdentityRejected("vacancy-binding-key-mismatch", slot)
        expected = confirmed or self.db_manager.get_slot_binding(namespace, slot)
        if expected is None:
            return (
                None if os.path.exists(path)
                else ProcessingOutcome.reconciled(ProcessingReason.SLOT_UNCHANGED)
            )
        if confirmed is None:
            observation = self.vacancy_guard.confirm(root, slot)
            if observation.state is VacancyState.PRESENT:
                return None if os.path.exists(path) else ProcessingOutcome.reconciled(
                    ProcessingReason.SLOT_UNCHANGED
                )
            if observation.state is VacancyState.DEFERRED:
                return self._vacancy_deferred(namespace, slot)

        # Once the full window proves absence, later arrival is a new career
        # boundary even if persistence was busy. Never cancel this proof merely
        # because a Dossier reappears while the transaction is retried.
        self._confirmed_vacancies[(namespace, slot)] = expected

        policy = self.vacancy_retry_policy
        for attempt in range(1, policy.max_attempts + 1):
            try:
                with self.db_manager.transaction():
                    if self.db_manager.get_slot_binding(namespace, slot) != expected:
                        self._confirmed_vacancies.pop((namespace, slot), None)
                        return None if os.path.exists(path) else ProcessingOutcome.reconciled(
                            ProcessingReason.SLOT_UNCHANGED
                        )
                    released = self.db_manager.release_slot_binding(expected)
                self._confirmed_vacancies.pop((namespace, slot), None)
                if released:
                    log.info(
                        "Dossier vacancy confirmed: namespace=%s slot=%d",
                        campaign_namespace_label(namespace), slot,
                    )
                    return None if os.path.exists(path) else ProcessingOutcome.reconciled(
                        ProcessingReason.SLOT_VACANT
                    )
                return ProcessingOutcome.reconciled(ProcessingReason.SLOT_UNCHANGED)
            except Exception as error:
                reason = classify_transient_sqlite_error(error)
                log.warning(
                    "Vacancy persistence deferred: namespace=%s slot=%d "
                    "category=%s attempts=%d",
                    campaign_namespace_label(namespace), slot,
                    (reason or ProcessingReason.SQLITE_PERMANENT).value, attempt,
                )
                if reason is None or attempt == policy.max_attempts:
                    return self._vacancy_deferred(namespace, slot, expected)
                self._retry_sleep(policy.delay_after_failure(attempt))
        return self._vacancy_deferred(namespace, slot, expected)

    @staticmethod
    def _vacancy_deferred(
        namespace: str, slot: int, confirmed: Optional[PilotSlotBinding] = None
    ) -> ProcessingOutcome:
        log.warning(
            "Dossier vacancy deferred: namespace=%s slot=%d "
            "category=%s",
            campaign_namespace_label(namespace), slot,
            "persistence-pending" if confirmed is not None else "unconfirmed-absence",
        )
        return ProcessingOutcome.reconciled(ProcessingReason.VACANCY_DEFERRED, confirmed)

    def replay(
        self, outcome: ProcessingOutcome, event_type: str
    ) -> ProcessingOutcome:
        """Replay the exact retained bytes and identity after SQLite recovery."""
        if (
            outcome.status is not ProcessingStatus.TRANSIENT_FAILURE
            or outcome.retry_input is None
        ):
            raise ValueError("only a transient processing outcome can be replayed")
        with self._slot_lock(outcome.retry_input.snapshot.path):
            return self._process_verified(
                outcome.retry_input, event_type, record_discovery=False
            )

    def replay_dependency(
        self, outcome: ProcessingOutcome, event_type: str
    ) -> ProcessingOutcome:
        if outcome.retry_input is None:
            raise ValueError("only a pending dependency can be replayed")
        with self._slot_lock(outcome.retry_input.snapshot.path):
            return self._replay_dependency(outcome, event_type)

    def _replay_dependency(
        self, outcome: ProcessingOutcome, event_type: str
    ) -> ProcessingOutcome:
        """Replay retained source bytes after its Dossier dependency changes."""
        if (
            outcome.status is not ProcessingStatus.DEPENDENCY_PENDING
            or outcome.retry_input is None
        ):
            raise ValueError("only a pending dependency can be replayed")
        retained = outcome.retry_input
        snapshot = retained.snapshot
        try:
            identity = self._dependent_identity(
                snapshot.path, snapshot.name, retained.slot_epoch
            )
        except SnapshotFailure:
            return self._dependency_pending(retained)
        except PilotIdentityError as error:
            return self._identity_rejection(snapshot.path, error)
        return self._process_verified(
            VerifiedProcessingInput(snapshot, identity, retained.slot_epoch),
            event_type,
            record_discovery=False,
        )

    def _verified_processing_input(
        self, path: str, snapshot: StableFileSnapshot, slot_epoch: Optional[int] = None
    ) -> VerifiedProcessingInput:
        source_name = snapshot.name
        dependent_identity = None
        if _requires_dependent_identity(source_name):
            dependent_identity = self._dependent_identity(path, source_name, slot_epoch)
        return VerifiedProcessingInput(snapshot, dependent_identity, slot_epoch)

    def _process_verified(
        self,
        retry_input: VerifiedProcessingInput,
        event_type: str,
        *,
        record_discovery: bool,
    ) -> ProcessingOutcome:
        snapshot = retry_input.snapshot
        path = snapshot.path
        try:
            if pilot_slot(path) is not None:
                key = self._dependent_binding_key(path, snapshot.name)
                if key in self._confirmed_vacancies:
                    return self._identity_rejection(
                        path, PilotIdentityRejected("vacancy-persistence-pending", key[1])
                    )
            if record_discovery and self.discovery and os.path.exists(path):
                self.discovery.log_file(path, event_type)

            ext = os.path.splitext(path)[1].lower()
            filename = _safe_filename(path).lower()
            if ext == ".xml":
                rejection = self._process_xml(path, snapshot)
            elif ext in SUPPORTED_WATCHED_EXTENSIONS:
                rejection = self._process_text(
                    path,
                    filename,
                    snapshot,
                    dependent_identity=retry_input.dependent_identity,
                    slot_epoch=retry_input.slot_epoch,
                )
            else:
                return ProcessingOutcome.permanent(
                    ProcessingReason.UNSUPPORTED_SOURCE
                )
            if rejection is None:
                return ProcessingOutcome.success(
                    snapshot.generation,
                    self._resolved_dependency(snapshot),
                )
            return ProcessingOutcome.permanent(rejection)
        except PilotIdentityUnavailable:
            return self._dependency_pending(retry_input)
        except PilotIdentityError as error:
            return self._identity_rejection(path, error)
        except sqlite3.Error as error:
            reason = classify_transient_sqlite_error(error)
            if reason is not None:
                log.warning(
                    "Transient persistence failure retained: source=%s category=%s",
                    _safe_filename(path),
                    reason.value,
                )
                return ProcessingOutcome.transient(retry_input, reason)
            log.error(
                "Persistence rejected: source=%s category=%s",
                _safe_filename(path),
                ProcessingReason.SQLITE_PERMANENT.value,
            )
            return ProcessingOutcome.permanent(
                ProcessingReason.SQLITE_PERMANENT
            )
        except Exception:
            log.exception(
                "Erro no pipeline de processamento para %s", _safe_filename(path)
            )
            return ProcessingOutcome.permanent(
                ProcessingReason.UNEXPECTED_ERROR
            )

    def _dependency_pending(
        self, retry_input: VerifiedProcessingInput
    ) -> ProcessingOutcome:
        identity = retry_input.dependent_identity
        dependency_key = (
            identity.binding_key
            if identity is not None
            else self._dependent_binding_key(
                retry_input.snapshot.path,
                retry_input.snapshot.name,
            )
        )
        log.info(
            "Pilot identity dependency retained: source=%s slot=%d",
            _safe_filename(retry_input.snapshot.path),
            dependency_key[1],
        )
        return ProcessingOutcome.dependency_pending(
            retry_input, dependency_key
        )

    @staticmethod
    def _identity_rejection(
        path: str, error: PilotIdentityError
    ) -> ProcessingOutcome:
        log.warning(
            "Pilot identity rejected: source=%s category=%s slot=%s",
            _safe_filename(path),
            error.reason,
            error.slot or "none",
        )
        return ProcessingOutcome.permanent(ProcessingReason.IDENTITY_REJECTED)

    @staticmethod
    def _parser_input(path: str, snapshot: Optional[StableFileSnapshot]) -> tuple[bytes, str]:
        if snapshot is not None:
            return snapshot.data, snapshot.name
        with open(path, "rb") as source:
            return source.read(), os.path.basename(path)

    def _dossier_identity(
        self,
        snapshot: Optional[StableFileSnapshot],
        slot_epoch: Optional[int] = None,
    ) -> PilotIdentityEvidence:
        if snapshot is None:
            raise PilotIdentityRejected("missing-stable-snapshot")
        slot = pilot_slot(snapshot.name)
        if slot is None:
            raise PilotIdentityRejected("invalid-slot-source")
        try:
            campaign_namespace = self._campaign_namespaces.namespace_for(
                snapshot.path
            )
        except CampaignNamespaceError as error:
            raise PilotIdentityRejected(str(error), slot) from error
        return PilotIdentityEvidence(
            PilotIdentityKind.DOSSIER,
            slot,
            snapshot.generation.digest,
            campaign_namespace,
            slot_epoch,
        )

    def _resolved_dependency(
        self, snapshot: StableFileSnapshot
    ) -> Optional[tuple[str, int]]:
        slot = pilot_slot(snapshot.name)
        if (
            slot is None
            or snapshot.name.lower() != dossier_source_name(slot).lower()
        ):
            return None
        return self._dossier_identity(snapshot).binding_key

    def _merge_and_process_latest_mission(
        self,
        parser: Any,
        identity: PilotIdentityEvidence,
    ) -> Optional[str]:
        latest_mission = get_latest_mission(parser)
        mission_id = None
        try:
            with self.db_manager.transaction():
                merge_result = self.db_manager.merge_and_write(
                    pilot=parser.pilot,
                    missions=parser.missions,
                    victories=parser.victories,
                    decorations=getattr(parser, "decorations", []),
                    identity=identity,
                    return_outcome=True,
                )
                if not merge_result:
                    raise _MissionDerivedWriteRejected
                if isinstance(merge_result, MergeWriteOutcome):
                    pilot_id = merge_result.pilot_id
                    updated_mission_ids = merge_result.updated_mission_ids
                else:
                    pilot_id = merge_result
                    updated_mission_ids = frozenset()

                if latest_mission is not None:
                    mission_id = self.db_manager.get_mission_id_by_natural_key(
                        pilot_id, latest_mission
                    )
                    if not mission_id:
                        raise _MissionDerivedWriteRejected
                    if mission_id in updated_mission_ids:
                        derived_result = self.campaign_engine.process_mission_end(
                            pilot_id,
                            mission_id,
                            replace_existing_diary=True,
                        )
                        if derived_result is not True:
                            raise _MissionDerivedWriteRejected
                        return pilot_id
        except _MissionDerivedWriteRejected:
            return None

        if mission_id is not None:
            derived_result = self.campaign_engine.process_mission_end(
                pilot_id, mission_id
            )
            if derived_result is not True:
                return None
        return pilot_id

    def _dependent_identity(
        self, path: str, source_name: str, slot_epoch: Optional[int] = None
    ) -> PilotIdentityEvidence:
        campaign_namespace, slot = self._dependent_binding_key(
            path, source_name
        )
        dossier_path = os.path.join(
            os.path.dirname(path), dossier_source_name(slot)
        )
        dossier = self.guard.acquire(dossier_path)
        return PilotIdentityEvidence(
            PilotIdentityKind.SLOT_DEPENDENT,
            slot,
            dossier.generation.digest,
            campaign_namespace,
            slot_epoch,
        )

    def _dependent_binding_key(
        self, path: str, source_name: str
    ) -> tuple[str, int]:
        slot = pilot_slot(source_name)
        if slot is None:
            raise PilotIdentityRejected("invalid-slot-source")
        try:
            campaign_namespace = self._campaign_namespaces.namespace_for(path)
        except CampaignNamespaceError as error:
            raise PilotIdentityRejected(str(error), slot) from error
        return campaign_namespace, slot

    def dependency_key_for_path(
        self, path: str
    ) -> Optional[tuple[str, int]]:
        """Return a dependent path key without reading its Dossier."""
        source_name = _safe_filename(path)
        if not _requires_dependent_identity(source_name):
            return None
        try:
            return self._dependent_binding_key(path, source_name)
        except PilotIdentityError:
            return None

    def _process_xml(
        self, path: str, snapshot: Optional[StableFileSnapshot] = None
    ) -> Optional[ProcessingReason]:
        parser = WoFFXMLParser()
        data, name = self._parser_input(path, snapshot)
        if parser.parse_bytes(data, name):
            real_pilot_id = self._merge_and_process_latest_mission(
                parser,
                PilotIdentityEvidence(PilotIdentityKind.UNRESOLVED),
            )
            return (
                None
                if real_pilot_id
                else ProcessingReason.PERSISTENCE_REJECTED
            )
        return ProcessingReason.PARSER_REJECTED

    def _process_text(
        self,
        path: str,
        fname: str,
        snapshot: Optional[StableFileSnapshot] = None,
        *,
        dependent_identity: Optional[PilotIdentityEvidence] = None,
        slot_epoch: Optional[int] = None,
    ) -> Optional[ProcessingReason]:
        data, name = self._parser_input(path, snapshot)
        if "dossier" in fname:
            parser = WoFFDossierParser()
            if parser.parse_bytes(data, name) and parser.pilot:
                identity = self._dossier_identity(snapshot, slot_epoch)
                real_pilot_id = self.campaign_engine.process_dossier_import(
                    pilot=parser.pilot,
                    decorations=parser.decorations,
                    wingmen=parser.wingmen,
                    identity=identity,
                )
                return (
                    None
                    if real_pilot_id
                    else ProcessingReason.PERSISTENCE_REJECTED
                )
            return ProcessingReason.PARSER_REJECTED

        if fname == "mission.log":
            parser = WoFFMissionLogParser()
            if parser.parse_bytes(data, name):
                real_pilot_id = self.db_manager.merge_and_write(
                    pilot=parser.pilot,
                    missions=[parser.mission] if parser.mission else [],
                    victories=[],
                    decorations=[],
                    identity=PilotIdentityEvidence(PilotIdentityKind.UNRESOLVED),
                )
                return (
                    None
                    if real_pilot_id
                    else ProcessingReason.PERSISTENCE_REJECTED
                )
            return ProcessingReason.PARSER_REJECTED

        # Ficheiros de piloto (Log, Claims, Squads)
        parser = WoFFPilotDataParser()
        parsed = parser.parse_bytes(data, name)
        if getattr(parser, "valid_empty", False) is True:
            # A verified zero-count source is present and valid. Acknowledge
            # its bytes without inferring occupancy or clearing prior history.
            return None
        if parsed and parser.pilot:
            persisted_pilot_id = self._merge_and_process_latest_mission(
                parser,
                (
                    dependent_identity
                    if dependent_identity is not None
                    else self._dependent_identity(path, name, slot_epoch)
                ),
            )
            return (
                None
                if persisted_pilot_id
                else ProcessingReason.PERSISTENCE_REJECTED
            )
        return ProcessingReason.PARSER_REJECTED


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
        self.processor = FileProcessor(
            db_manager,
            campaign_engine,
            discovery,
            config.stability_timeout_sec,
            config.stability_check_interval_sec,
            watch_roots=config.watch_paths,
        )
        self.scheduler = EventScheduler(
            self._execute_pipeline,
            max_workers=config.max_workers,
            max_pending_events=config.max_pending_events,
            retry_process=self._execute_retry_pipeline,
            persistence_retry_process=self._execute_persistence_retry_pipeline,
            dependency_retry_process=self._execute_dependency_retry_pipeline,
            dependency_key_for_event=self._dependency_key_for_event,
            vacancy_pending=self.processor.vacancy_pending,
        )
        self._startup_admission_timeout = config.stability_timeout_sec

    def on_modified(self, event):
        if not event.is_directory:
            self._handle(str(event.src_path), "modified")

    def on_created(self, event):
        if not event.is_directory:
            self._handle(str(event.src_path), "created")

    def on_deleted(self, event):
        if not event.is_directory and is_dossier_source(str(event.src_path)):
            self._handle(str(event.src_path), "deleted")

    def on_moved(self, event):
        if not event.is_directory:
            if is_dossier_source(str(event.src_path)):
                self._handle(str(event.src_path), "moved-away")
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

    def submit_initial_vacancy(self, path: str) -> bool:
        """Keep a proven negative inventory distinct from a positive snapshot."""
        return self.scheduler.submit(
            path, "initial-vacancy", admission_timeout=self._startup_admission_timeout
        )

    def wait_initial(self, paths: list[str], timeout: float) -> bool:
        """Wait until startup paths finish or retain a bounded dependency."""
        return self.scheduler.wait_for_settled_paths(paths, timeout)

    def startup_phase_timeout(self, paths: int | Sequence[str]) -> float:
        """Bound startup waits across snapshots and every persistence attempt."""
        if isinstance(paths, int):
            path_count = paths
            snapshot_count = paths
        else:
            phase_paths = list(paths)
            path_count = len(phase_paths)
            snapshot_count = path_count + sum(
                1
                for path in phase_paths
                if _requires_dependent_identity(path)
            )
        policy = self.scheduler.persistence_retry_policy
        retry_backoff = sum(
            policy.delay_after_failure(failure)
            for failure in range(1, policy.max_attempts)
        )
        persistence_per_path = (
            (policy.max_attempts * SQLITE_BUSY_TIMEOUT_SECONDS)
            + retry_backoff
        )
        return (
            self.config.stability_timeout_sec
            + (snapshot_count * self.config.stability_timeout_sec)
            + (path_count * persistence_per_path)
        )

    def _execute_pipeline(self, path: str, event_type: str):
        """Método executado na thread pool."""
        log.info("Detectado [%s]: %s", event_type, _safe_filename(path))
        return self.processor.process(path, event_type)

    def _execute_retry_pipeline(
        self, path: str, event_type: str, previous_outcome: Any
    ) -> ProcessingOutcome:
        """Process a coalesced event while suppressing an identical generation."""
        log.info("Detectado [%s]: %s", event_type, _safe_filename(path))
        return self.processor.process(path, event_type, previous_outcome)

    def _execute_persistence_retry_pipeline(
        self, path: str, event_type: str, previous_outcome: ProcessingOutcome
    ) -> ProcessingOutcome:
        """Replay retained verified input without reopening mutable source bytes."""
        log.info("A repetir persistência [%s]: %s", event_type, _safe_filename(path))
        return self.processor.replay(previous_outcome, event_type)

    def _execute_dependency_retry_pipeline(
        self, path: str, event_type: str, previous_outcome: ProcessingOutcome
    ) -> ProcessingOutcome:
        """Replay retained bytes after the matching Dossier is persisted."""
        log.info("A liberar dependência [%s]: %s", event_type, _safe_filename(path))
        return self.processor.replay_dependency(previous_outcome, event_type)

    def _dependency_key_for_event(
        self, path: str, _event_type: str
    ) -> Optional[tuple[str, int]]:
        """Resolve a dependent source binding before its worker starts."""
        return self.processor.dependency_key_for_path(path)

    def metrics(self):
        return self.scheduler.metrics()

    def shutdown(self):
        log.info("A aguardar conclusão das threads de processamento...")
        self.scheduler.shutdown()
