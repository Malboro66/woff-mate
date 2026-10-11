"""Source-only, deeply immutable values for the bounded R0.3 experiment.

Aliases identify copies, never careers. No paths, digests or domain objects
belong in these presentation contracts. The #81 career contracts are unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Union
from uuid import UUID

from .ui_contracts import FieldValue, Freshness, RequestId, ScreenState, UnavailableReason

ALIASES = tuple(f"S-{i:02d}" for i in range(1, 7)) + ("M-01",) + tuple(
    f"{family}-{i:02d}" for family in ("D", "C") for i in range(1, 7)
)
MAX_TEXT = 1000
MAX_INSPECTION_ROWS = 100


def _immutable(value: object) -> bool:
    if value is None or isinstance(value, (str, int, bool, datetime, Enum)):
        return True
    if isinstance(value, tuple):
        return all(_immutable(item) for item in value)
    if is_dataclass(value) and not isinstance(value, type):
        params = getattr(type(value), "__dataclass_params__", None)
        return bool(params and params.frozen) and all(
            _immutable(getattr(value, field.name)) for field in fields(value)
        )
    return False


class _Frozen:
    def __post_init__(self) -> None:
        if not _immutable(self):
            raise TypeError("Preview values must be deeply immutable")


def _count(value: object) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("Preview counts must be nonnegative integers")


class FieldEvidence(str, Enum):
    PARSED = "parsed-source-value"
    EMPTY = "parser-returned-empty"
    UNAVAILABLE = "unavailable"


class PreviewFailure(str, Enum):
    MANIFEST = "invalid-manifest"
    MISSING = "missing-copy"
    UNSAFE = "unsafe-copy"
    INTEGRITY = "integrity-failure"
    LIMIT = "unsupported-size-or-output"
    UNREADABLE = "unreadable-copy"
    PARSER = "parser-failure"
    CANCELLED = "cancelled"

    @property
    def message(self) -> str:
        return {
            self.MANIFEST: "The explicit manifest does not satisfy the verified-copy contract.",
            self.MISSING: "The selected immutable copy is missing. No source data is displayed.",
            self.UNSAFE: "The selected input does not satisfy the private-copy safety boundary.",
            self.INTEGRITY: "Copy integrity failed or changed during reading. No source data is displayed.",
            self.LIMIT: "The source exceeds the supported file or presentation limits.",
            self.UNREADABLE: "The selected immutable copy could not be read safely.",
            self.PARSER: "The current parser could not produce a supported preview.",
            self.CANCELLED: "The preview request was cancelled.",
        }[self]


class PreviewAuthority(str, Enum):
    LOCAL_VERIFIED_COPY = "local-verified-copy"


class RecordPolicy(str, Enum):
    LAST_ACCEPTED = "Last accepted physical record in file order; not complete career history"
    INDEPENDENT_MISSION = "Independent player formation and route; career association UNVERIFIED"
    DIAGNOSTIC = "Diagnostic-only observation; no verified cross-source career association"


class DiagnosticStatus(str, Enum):
    INVALID_ROSTER = "invalid-roster"
    UNSUPPORTED_LAYOUT = "unsupported-layout"
    DECRYPTION_FAILED = "decryption-failed"
    TRUNCATED = "truncated"
    SUPPORTED_FULL = "supported-full"
    SUPPORTED_PARTIAL = "supported-partial"
    UNPARSED = "unparsed"
    CLAIMS_INCOMPLETE = "claims-incomplete"
    CLAIMS_COMPLETE = "claims-complete"


@dataclass(frozen=True)
class SourceSelection(_Frozen):
    dataset_id: str
    alias: str
    generation: str

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.alias not in ALIASES:
            raise ValueError("Unknown source alias")
        for value in (self.dataset_id, self.generation):
            if type(value) is not str or str(UUID(value)) != value:
                raise ValueError("Source identity requires opaque UUID tokens")


@dataclass(frozen=True)
class PreviewRequest(_Frozen):
    selection: SourceSelection
    request_id: RequestId

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.selection, SourceSelection) or not isinstance(self.request_id, RequestId):
            raise TypeError("A preview request requires source and request identity")


@dataclass(frozen=True)
class PreviewField(_Frozen):
    value: FieldValue[str]
    evidence: FieldEvidence

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.value, FieldValue) or not isinstance(self.evidence, FieldEvidence):
            raise TypeError("A preview field requires closed evidence")
        text = self.value.value
        if text is not None and (type(text) is not str or len(text) > MAX_TEXT):
            raise ValueError("Unsupported preview text")
        expected = (FieldEvidence.UNAVAILABLE if text is None else
                    FieldEvidence.EMPTY if text == "" else FieldEvidence.PARSED)
        if self.evidence is not expected:
            raise ValueError("Field evidence does not match the parser value")
        if text is None and not isinstance(self.value.reason, UnavailableReason):
            raise TypeError("Unavailable fields require a closed reason")

    @classmethod
    def parsed(cls, value: str) -> PreviewField:
        return cls(FieldValue.known(value), FieldEvidence.EMPTY if value == "" else FieldEvidence.PARSED)

    @classmethod
    def unavailable(cls, reason: UnavailableReason = UnavailableReason.NOT_SUPPLIED) -> PreviewField:
        return cls(FieldValue.unavailable(reason), FieldEvidence.UNAVAILABLE)

    def display(self, label: str) -> str:
        if self.evidence is FieldEvidence.EMPTY:
            return f"{label} unavailable — parser returned an empty value"
        if self.evidence is FieldEvidence.UNAVAILABLE:
            assert self.value.reason is not None
            return f"{label} unavailable — {self.value.reason.value.replace('_', ' ')}"
        return self.value.value or ""


@dataclass(frozen=True)
class PreviewProvenance(_Frozen):
    selection: SourceSelection
    verified_at: datetime
    policy: RecordPolicy
    authority: PreviewAuthority = PreviewAuthority.LOCAL_VERIFIED_COPY
    freshness: Freshness = Freshness.UNKNOWN
    contract_version: str = "source-preview-v1"

    @property
    def parser_projection(self) -> str:
        return {"S": "WoFFPilotDataParser / PilotSquads", "M": "WoFFMissionLogParser",
                "D": "WoFFDossierParser / authoritative admission", "C": "WoFFPilotDataParser / PilotClaims"}[self.selection.alias[0]]

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.selection, SourceSelection) or not isinstance(self.verified_at, datetime):
            raise TypeError("Preview provenance requires a source and verification observation")
        if self.verified_at.utcoffset() is None or not isinstance(self.policy, RecordPolicy):
            raise ValueError("Verification time must be aware and policy closed")
        if (self.authority is not PreviewAuthority.LOCAL_VERIFIED_COPY or
                self.freshness is not Freshness.UNKNOWN or self.contract_version != "source-preview-v1"):
            raise ValueError("A verified copy does not establish live freshness or application persistence")


@dataclass(frozen=True)
class PilotSquadsPreview(_Frozen):
    selection: SourceSelection
    squadron: PreviewField
    aircraft: PreviewField
    aerodrome: PreviewField
    sector: PreviewField
    source_record_date: PreviewField
    rank: PreviewField
    observed_records: int
    rejected_records: int
    is_complete: bool

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.selection, SourceSelection) or not self.selection.alias.startswith("S-"):
            raise ValueError("PilotSquads requires its own source identity")
        for name in ("squadron", "aircraft", "aerodrome", "sector", "source_record_date", "rank"):
            if not isinstance(getattr(self, name), PreviewField):
                raise TypeError("PilotSquads fields must be immutable string projections")
        _count(self.observed_records)
        _count(self.rejected_records)
        if type(self.is_complete) is not bool or self.rejected_records > self.observed_records:
            raise ValueError("Invalid source completeness")


@dataclass(frozen=True)
class RouteEntry(_Frozen):
    kind: PreviewField
    altitude: PreviewField

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.kind, PreviewField) or not isinstance(self.altitude, PreviewField):
            raise TypeError("Route rows require copied fields")


@dataclass(frozen=True)
class MissionLogPreview(_Frozen):
    selection: SourceSelection
    date: PreviewField
    time: PreviewField
    squadron: PreviewField
    aircraft: PreviewField
    weather: PreviewField
    result: PreviewField
    formation_count: int
    waypoint_count: int
    formation_entries: tuple[str, ...]
    route_entries: tuple[RouteEntry, ...]
    career_association: str = "UNVERIFIED"

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.selection, SourceSelection) or self.selection.alias != "M-01":
            raise ValueError("Mission.log requires independent M-01 identity")
        for name in ("date", "time", "squadron", "aircraft", "weather", "result"):
            if not isinstance(getattr(self, name), PreviewField):
                raise TypeError("Mission fields must be copied values")
        _count(self.formation_count)
        _count(self.waypoint_count)
        if (self.career_association != "UNVERIFIED" or
                type(self.formation_entries) is not tuple or type(self.route_entries) is not tuple or
                len(self.formation_entries) != self.formation_count or len(self.route_entries) != self.waypoint_count or
                max(self.formation_count, self.waypoint_count) > MAX_INSPECTION_ROWS):
            raise ValueError("Unsupported mission inspection or association")
        if not all(type(row) is str and len(row) <= MAX_TEXT for row in self.formation_entries):
            raise TypeError("Formation entries require bounded copied strings")
        if not all(isinstance(row, RouteEntry) for row in self.route_entries):
            raise TypeError("Route entries require immutable rows")


@dataclass(frozen=True)
class DiagnosticPreview(_Frozen):
    selection: SourceSelection
    status: DiagnosticStatus
    admitted: bool
    is_complete: bool
    valid_empty: bool
    declared_records: FieldValue[int]
    observed_records: int
    rejected_records: int

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.selection, SourceSelection) or self.selection.alias[:1] not in ("D", "C"):
            raise ValueError("Diagnostics require an independent D/C source")
        if not isinstance(self.status, DiagnosticStatus) or not all(
                type(value) is bool for value in (self.admitted, self.is_complete, self.valid_empty)):
            raise TypeError("Diagnostics require closed status and exact booleans")
        if not isinstance(self.declared_records, FieldValue):
            raise TypeError("Declared count requires availability")
        if self.declared_records.value is not None:
            _count(self.declared_records.value)
        elif not isinstance(self.declared_records.reason, UnavailableReason):
            raise TypeError("Unavailable declared count requires a closed reason")
        _count(self.observed_records)
        _count(self.rejected_records)


PreviewPayload = Union[PilotSquadsPreview, MissionLogPreview, DiagnosticPreview]


@dataclass(frozen=True)
class PreviewSnapshot(_Frozen):
    request: PreviewRequest
    state: ScreenState
    payload: Optional[PreviewPayload] = None
    provenance: Optional[PreviewProvenance] = None
    failure: Optional[PreviewFailure] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.request, PreviewRequest) or not isinstance(self.state, ScreenState):
            raise TypeError("Snapshot requires request identity and closed state")
        if self.state is ScreenState.READY:
            if not isinstance(self.payload, (PilotSquadsPreview, MissionLogPreview, DiagnosticPreview)):
                raise TypeError("Ready preview requires an immutable payload")
            if not isinstance(self.provenance, PreviewProvenance) or self.failure is not None:
                raise ValueError("Ready preview requires verified provenance")
            if self.payload.selection != self.request.selection or self.provenance.selection != self.request.selection:
                raise ValueError("Cross-source provenance is forbidden")
        elif self.payload is not None or self.provenance is not None:
            raise ValueError("Loading and failed previews cannot retain source data")
        if self.state is ScreenState.LOADING:
            if self.failure is not None:
                raise ValueError("Loading cannot carry failure")
        elif self.state is not ScreenState.READY and not isinstance(self.failure, PreviewFailure):
            raise ValueError("Failed preview requires a sanitized failure")
