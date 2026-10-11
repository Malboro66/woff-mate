"""Toolkit-independent projection of verified copies using fresh parsers.

Only the immutable preview contract crosses this application boundary. Parser
buffers, names, source paths, digests and exceptions stay private and discarded.
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import logging
import re
import threading
from typing import Iterator
import xml.etree.ElementTree as ET

from .parsers.dossier_parser import WoFFDossierParser
from .parsers.mission_log_parser import WoFFMissionLogParser
from .parsers.pilot_data_parser import WoFFPilotDataParser
from .source_preview_inputs import CopyInputError, CopySource, VerifiedCopyInputs
from .source_preview_contracts import (
    DiagnosticPreview, DiagnosticStatus, MAX_INSPECTION_ROWS, MAX_TEXT,
    MissionLogPreview, PilotSquadsPreview, PreviewFailure, PreviewField,
    PreviewProvenance, PreviewRequest, PreviewSnapshot, RecordPolicy, RouteEntry,
    SourceSelection,
)
from .ui_contracts import FieldValue, ScreenState, UnavailableReason

_PARSER_LOCK = threading.Lock()
_INPUT_FAILURES = {
    "manifest": PreviewFailure.MANIFEST, "missing": PreviewFailure.MISSING,
    "unsafe": PreviewFailure.UNSAFE, "integrity": PreviewFailure.INTEGRITY,
    "limit": PreviewFailure.LIMIT, "unreadable": PreviewFailure.UNREADABLE,
}


class _Discard:
    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        pass


@contextlib.contextmanager
def _private_parser_output() -> Iterator[None]:
    # The standalone process has a single parser worker. Serialize process-local
    # stream/log suppression and restore the host's state for synthetic tests.
    with _PARSER_LOCK:
        previous = logging.root.manager.disable
        logger = logging.getLogger("WoFFWatch")
        disabled = logger.disabled
        try:
            logger.disabled = True
            logging.disable(logging.CRITICAL)
            with contextlib.redirect_stdout(_Discard()), contextlib.redirect_stderr(_Discard()):
                yield
        finally:
            logger.disabled = disabled
            logging.disable(previous)


def input_failure(error: CopyInputError) -> PreviewFailure:
    return _INPUT_FAILURES[error.code]


class PreviewSetupError(Exception):
    def __init__(self, failure: PreviewFailure) -> None:
        self.failure = failure
        super().__init__(failure.value)


def _field(value: str, supplied: bool = True) -> PreviewField:
    if not supplied:
        return PreviewField.unavailable()
    if type(value) is not str or len(value) > MAX_TEXT:
        raise CopyInputError("limit")
    return PreviewField.parsed(value)


def _mission_presence(data: bytes) -> tuple[ET.Element, ET.Element | None, ET.Element | None]:
    content = data.decode("utf-8", errors="replace")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", content, re.IGNORECASE):
        raise CopyInputError("limit")
    xml = re.search(r"<Mission>(.*?)</Mission>", content, re.DOTALL)
    if xml is None:
        raise ValueError("Unsupported mission")
    root = ET.fromstring("<Mission>" + xml.group(1) + "</Mission>")
    if sum(1 for _ in root.iter()) > 2000:
        raise CopyInputError("limit")
    params = root.find("Params")
    if params is None:
        raise ValueError("Unsupported mission")
    for formation in root.findall("AirFormation"):
        for unit in formation.findall("Unit"):
            if unit.get("IsPlayer") == "y":
                return params, formation, unit
    return params, None, None


class SourcePreviewService:
    def __init__(self, manifest: str) -> None:
        try:
            self._inputs = VerifiedCopyInputs(manifest)
        except CopyInputError as error:
            raise PreviewSetupError(input_failure(error)) from None
        self.selections = tuple(SourceSelection(self._inputs.dataset_id, source.alias, source.generation)
                                for source in self._inputs.sources)

    def query(self, request: PreviewRequest) -> PreviewSnapshot:
        if request.selection not in self.selections:
            return self._failed(request, PreviewFailure.UNSAFE)
        source = next(source for source in self._inputs.sources if source.alias == request.selection.alias)
        try:
            data = self._inputs.read(source)
            verified_at = datetime.now(timezone.utc)
            with _private_parser_output():
                if source.category == "PilotSquads":
                    payload = self._squads(source, data, request.selection)
                    policy = RecordPolicy.LAST_ACCEPTED
                elif source.category == "Mission.log":
                    payload = self._mission(source, data, request.selection)
                    policy = RecordPolicy.INDEPENDENT_MISSION
                else:
                    payload = self._diagnostic(source, data, request.selection)
                    policy = RecordPolicy.DIAGNOSTIC
            return PreviewSnapshot(request, ScreenState.READY, payload,
                                   PreviewProvenance(request.selection, verified_at, policy))
        except CopyInputError as error:
            return self._failed(request, input_failure(error))
        except Exception:
            # Deliberately do not format/log/serialize the exception or traceback.
            return self._failed(request, PreviewFailure.PARSER)

    @staticmethod
    def _failed(request: PreviewRequest, failure: PreviewFailure) -> PreviewSnapshot:
        state = ScreenState.MISSING if failure is PreviewFailure.MISSING else ScreenState.ERROR
        return PreviewSnapshot(request, state, failure=failure)

    @staticmethod
    def _squads(source: CopySource, data: bytes, selection: SourceSelection) -> PilotSquadsPreview:
        parser = WoFFPilotDataParser()
        if not parser.parse_bytes(data, source.basename) or parser.pilot is None:
            raise ValueError("Unsupported PilotSquads")
        pilot = parser.pilot
        return PilotSquadsPreview(selection, _field(pilot.squadron), _field(pilot.aircraft),
                                  _field(pilot.aerodrome), _field(pilot.sector),
                                  _field(pilot.startDate), _field(pilot.rank),
                                  parser.observed_records, parser.rejected_records, parser.is_complete)

    @staticmethod
    def _mission(source: CopySource, data: bytes, selection: SourceSelection) -> MissionLogPreview:
        params, formation, unit = _mission_presence(data)
        parser = WoFFMissionLogParser()
        if not parser.parse_bytes(data, source.basename) or parser.mission is None:
            raise ValueError("Unsupported Mission.log")
        mission = parser.mission
        if max(len(parser.squad_members), len(parser.flight_plan)) > MAX_INSPECTION_ROWS:
            raise CopyInputError("limit")
        if any(type(row) is not str or len(row) > MAX_TEXT for row in parser.squad_members):
            raise CopyInputError("limit")
        return MissionLogPreview(
            selection, _field(mission.date, "Date" in params.attrib),
            _field(mission.time, "Time" in params.attrib),
            _field(parser.pilot.squadron if parser.pilot else "",
                   formation is not None and "SquadName" in formation.attrib),
            _field(mission.aircraft, unit is not None and "Type" in unit.attrib),
            _field(mission.weather, "Weather" in params.attrib),
            _field(mission.result, bool(mission.result)),
            len(parser.squad_members), len(parser.flight_plan), tuple(parser.squad_members),
            tuple(RouteEntry(_field(row["type"]), _field(row["altitude"])) for row in parser.flight_plan),
        )

    @staticmethod
    def _diagnostic(source: CopySource, data: bytes, selection: SourceSelection) -> DiagnosticPreview:
        if source.category == "Dossier":
            dossier = WoFFDossierParser()
            admitted = dossier.parse_bytes(data, source.basename, require_verified_layout=True)
            return DiagnosticPreview(selection, DiagnosticStatus(dossier.validation_status.value),
                                     admitted, dossier.roster_complete, False,
                                     FieldValue.unavailable(UnavailableReason.NOT_SUPPLIED), 0, 0)
        claims = WoFFPilotDataParser()
        admitted = claims.parse_bytes(data, source.basename)
        declared = (FieldValue.known(claims.declared_records) if claims.declared_records is not None else
                    FieldValue[int].unavailable(UnavailableReason.NOT_SUPPLIED))
        return DiagnosticPreview(selection,
                                 DiagnosticStatus.CLAIMS_COMPLETE if claims.is_complete else DiagnosticStatus.CLAIMS_INCOMPLETE,
                                 admitted, claims.is_complete, claims.valid_empty, declared,
                                 claims.observed_records, claims.rejected_records)
