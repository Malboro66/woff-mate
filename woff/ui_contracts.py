"""Immutable, toolkit-independent contracts for the future read-only UI.

This module is the presentation/application boundary.  It deliberately contains
only copied values and protocols: storage, ingestion and platform objects cannot
cross it.  Live query implementations are outside Issue #81.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timedelta
from enum import Enum
import re
from typing import Generic, Iterable, Optional, Protocol, Tuple, Type, TypeVar

from .nation import NationServicePresentation


T = TypeVar("T")
SelectionT = TypeVar("SelectionT")
U = TypeVar("U")


class ScreenState(str, Enum):
    """The six mutually exclusive screen states established by Issue #80."""

    LOADING = "loading"
    READY = "ready"
    EMPTY = "empty"
    MISSING = "missing"
    STALE_OR_UNAVAILABLE = "stale/unavailable"
    ERROR = "error"


class Freshness(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    UNKNOWN = "unknown"


class Completeness(str, Enum):
    """Content completeness is independent from the shared screen state."""

    COMPLETE = "complete"
    PARTIAL = "partial"


class SnapshotReason(str, Enum):
    REQUEST_PENDING = "request_pending"
    CAREER_NOT_SELECTED = "career_not_selected"
    SOURCE_MISSING = "source_missing"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_TRUNCATED = "source_truncated"
    SOURCE_UNSUPPORTED = "source_unsupported"
    SOURCE_UNREADABLE = "source_unreadable"
    SNAPSHOT_EXPIRED = "snapshot_expired"
    QUERY_FAILED = "query_failed"
    REQUEST_TIMEOUT = "request_timeout"
    REQUEST_CANCELLED = "request_cancelled"


class UnavailableReason(str, Enum):
    UNKNOWN = "unknown"
    NOT_SUPPLIED = "not_supplied"
    SOURCE_CONFLICT = "source_conflict"
    REDACTED = "redacted"
    UNSUPPORTED = "unsupported"
    UNREADABLE = "unreadable"
    TRUNCATED = "truncated"


class SourceAuthority(str, Enum):
    """Closed authorities; no file, parser or repository identity is exposed."""

    APPLICATION_RECORDS = "application-records"
    APPLICATION_DERIVED = "application-derived"
    APPLICATION_SETTINGS = "application-settings"
    SYNTHETIC_RECORDS = "synthetic-records"
    SYNTHETIC_DERIVED = "synthetic-derived"
    SYNTHETIC_SETTINGS = "synthetic-settings"
    SYNTHETIC_QUERY = "synthetic-query"
    UNRESOLVED = "unresolved"


class WarningCode(str, Enum):
    PARTIAL_RECORD = "partial_record"
    SOURCE_CONFLICT = "source_conflict"
    REDACTED_FIELDS = "redacted_fields"
    SNAPSHOT_EXPIRED = "snapshot_expired"
    SOURCE_UNAVAILABLE = "source_unavailable"
    FRESHNESS_UNKNOWN = "freshness_unknown"
    SOURCE_TRUNCATED = "source_truncated"
    SOURCE_UNREADABLE = "source_unreadable"
    SOURCE_UNSUPPORTED = "source_unsupported"
    QUERY_FAILED = "query_failed"
    REQUEST_TIMEOUT = "request_timeout"
    REQUEST_CANCELLED = "request_cancelled"


_WARNING_MESSAGES = {
    WarningCode.PARTIAL_RECORD: "Some fields are unavailable; known values remain visible.",
    WarningCode.SOURCE_CONFLICT: (
        "Sources disagree. The affected value is unavailable; no winner is inferred."
    ),
    WarningCode.REDACTED_FIELDS: "Installation details are hidden in this synthetic example.",
    WarningCode.SNAPSHOT_EXPIRED: (
        "This snapshot is old. Its observation time is shown; it is not current."
    ),
    WarningCode.SOURCE_UNAVAILABLE: "The source cannot currently provide this view.",
    WarningCode.FRESHNESS_UNKNOWN: "The snapshot freshness is unknown.",
    WarningCode.SOURCE_TRUNCATED: "The source is incomplete; unvalidated values are unavailable.",
    WarningCode.SOURCE_UNREADABLE: "The source could not be read safely.",
    WarningCode.SOURCE_UNSUPPORTED: "The source format is not supported.",
    WarningCode.QUERY_FAILED: (
        "The view could not be loaded. Retry the view or open Data & System Status."
    ),
    WarningCode.REQUEST_TIMEOUT: "The view request timed out. Retry the view.",
    WarningCode.REQUEST_CANCELLED: "The view request was cancelled.",
}


@dataclass(frozen=True)
class Warning:
    """A closed warning code with repository-owned safe display text."""

    code: WarningCode

    @property
    def message(self) -> str:
        return _WARNING_MESSAGES[self.code]


class FailureCode(str, Enum):
    QUERY_FAILED = "query_failed"
    REQUEST_TIMEOUT = "request_timeout"
    REQUEST_CANCELLED = "request_cancelled"


_FAILURE_MESSAGES = {
    FailureCode.QUERY_FAILED: _WARNING_MESSAGES[WarningCode.QUERY_FAILED],
    FailureCode.REQUEST_TIMEOUT: _WARNING_MESSAGES[WarningCode.REQUEST_TIMEOUT],
    FailureCode.REQUEST_CANCELLED: _WARNING_MESSAGES[WarningCode.REQUEST_CANCELLED],
}


@dataclass(frozen=True)
class SanitizedFailure:
    """Failure information whose text is fixed and cannot contain exception data."""

    code: FailureCode

    @property
    def message(self) -> str:
        return _FAILURE_MESSAGES[self.code]

    @property
    def retryable(self) -> bool:
        return self.code in {FailureCode.QUERY_FAILED, FailureCode.REQUEST_TIMEOUT}

    @classmethod
    def from_exception(
        cls, code: FailureCode, exception: BaseException
    ) -> "SanitizedFailure":
        """Translate a failure without retaining, formatting or exposing it."""

        del exception
        return cls(code)


def _is_deeply_immutable(value: object) -> bool:
    if value is None or isinstance(
        value, (str, bytes, int, float, bool, datetime, timedelta, Enum)
    ):
        return True
    if isinstance(value, tuple):
        return all(_is_deeply_immutable(item) for item in value)
    if isinstance(value, frozenset):
        return all(_is_deeply_immutable(item) for item in value)
    if is_dataclass(value) and not isinstance(value, type):
        params = getattr(type(value), "__dataclass_params__", None)
        return bool(params and params.frozen) and all(
            _is_deeply_immutable(getattr(value, item.name)) for item in fields(value)
        )
    return False


def _copied_immutable_tuple(
    values: Iterable[U], expected_type: Type[U], label: str
) -> Tuple[U, ...]:
    copied = tuple(values)
    if not all(
        isinstance(item, expected_type) and _is_deeply_immutable(item)
        for item in copied
    ):
        raise TypeError(f"{label} must contain only immutable contract values")
    return copied


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CONTRACT_IDENTIFIER = re.compile(r"^[a-z][a-z0-9.-]{0,63}$")
_FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")


@dataclass(frozen=True)
class _StableIdentifier:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or _IDENTIFIER.fullmatch(self.value) is None:
            raise ValueError("stable identifiers must be explicit opaque tokens")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class PilotId(_StableIdentifier):
    """Persistent pilot/career ID; never a name, source slot or list position."""


@dataclass(frozen=True)
class MissionId(_StableIdentifier):
    pass


@dataclass(frozen=True)
class DiaryEntryId(_StableIdentifier):
    pass


@dataclass(frozen=True)
class SquadronId(_StableIdentifier):
    pass


@dataclass(frozen=True)
class SquadronMemberId(_StableIdentifier):
    pass


@dataclass(frozen=True)
class SystemDiagnosticId(_StableIdentifier):
    pass


@dataclass(frozen=True)
class RequestId(_StableIdentifier):
    pass


@dataclass(frozen=True)
class ContractVersion:
    value: str

    def __post_init__(self) -> None:
        if _CONTRACT_IDENTIFIER.fullmatch(self.value) is None:
            raise ValueError("contract version must be a stable lowercase identifier")


@dataclass(frozen=True)
class FreshnessPolicyId:
    value: str

    def __post_init__(self) -> None:
        if _CONTRACT_IDENTIFIER.fullmatch(self.value) is None:
            raise ValueError("freshness policy must be a stable lowercase identifier")


@dataclass(frozen=True)
class FieldValue(Generic[T]):
    """A known value or an explicit reason why no value is available."""

    value: Optional[T]
    reason: Optional[UnavailableReason]

    def __post_init__(self) -> None:
        if (self.value is None) == (self.reason is None):
            raise ValueError("field value requires exactly one of value or unavailable reason")
        if self.value is not None and not _is_deeply_immutable(self.value):
            raise TypeError("presentation field values must be deeply immutable")

    @classmethod
    def known(cls, value: T) -> "FieldValue[T]":
        if value is None:
            raise ValueError("known field value cannot be null")
        return cls(value=value, reason=None)

    @classmethod
    def unavailable(cls, reason: UnavailableReason) -> "FieldValue[T]":
        return cls(value=None, reason=reason)


@dataclass(frozen=True)
class FieldUnavailable:
    field: str
    reason: UnavailableReason

    def __post_init__(self) -> None:
        if _FIELD_NAME.fullmatch(self.field) is None:
            raise ValueError("unavailable field must use a stable dotted field name")


@dataclass(frozen=True)
class SnapshotEnvelope:
    """Metadata shared unchanged by every screen-specific snapshot."""

    state: ScreenState
    reason: Optional[SnapshotReason]
    observed_at: FieldValue[datetime]
    freshness: Freshness
    freshness_policy: FieldValue[FreshnessPolicyId]
    source_authority: SourceAuthority
    contract_version: ContractVersion
    completeness: Completeness
    warnings: Tuple[Warning, ...]
    unavailable_fields: Tuple[FieldUnavailable, ...]
    failure: Optional[SanitizedFailure]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "warnings",
            _copied_immutable_tuple(self.warnings, Warning, "warnings"),
        )
        object.__setattr__(
            self,
            "unavailable_fields",
            _copied_immutable_tuple(
                self.unavailable_fields, FieldUnavailable, "unavailable fields"
            ),
        )
        if self.observed_at.value is not None:
            value = self.observed_at.value
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("observation time must be timezone-aware")
        if self.state is ScreenState.ERROR and self.failure is None:
            raise ValueError("error snapshots require a sanitized failure")
        if self.state is not ScreenState.ERROR and self.failure is not None:
            raise ValueError("only error snapshots may carry a failure")
        if self.completeness is Completeness.COMPLETE and self.unavailable_fields:
            raise ValueError("field unavailability requires partial completeness")
        allowed_reasons = {
            ScreenState.LOADING: {SnapshotReason.REQUEST_PENDING},
            ScreenState.READY: {None},
            ScreenState.EMPTY: {None},
            ScreenState.MISSING: {
                SnapshotReason.CAREER_NOT_SELECTED,
                SnapshotReason.SOURCE_MISSING,
            },
            ScreenState.STALE_OR_UNAVAILABLE: {
                SnapshotReason.SOURCE_UNAVAILABLE,
                SnapshotReason.SOURCE_TRUNCATED,
                SnapshotReason.SOURCE_UNSUPPORTED,
                SnapshotReason.SOURCE_UNREADABLE,
                SnapshotReason.SNAPSHOT_EXPIRED,
            },
            ScreenState.ERROR: {
                SnapshotReason.QUERY_FAILED,
                SnapshotReason.REQUEST_TIMEOUT,
                SnapshotReason.REQUEST_CANCELLED,
            },
        }
        if self.reason not in allowed_reasons[self.state]:
            raise ValueError("snapshot reason does not match its screen state")
        failure_for_reason = {
            SnapshotReason.QUERY_FAILED: FailureCode.QUERY_FAILED,
            SnapshotReason.REQUEST_TIMEOUT: FailureCode.REQUEST_TIMEOUT,
            SnapshotReason.REQUEST_CANCELLED: FailureCode.REQUEST_CANCELLED,
        }
        expected_failure = (
            failure_for_reason.get(self.reason) if self.reason is not None else None
        )
        if self.failure is not None and self.failure.code is not expected_failure:
            raise ValueError("sanitized failure does not match the snapshot reason")
        if self.freshness in {Freshness.CURRENT, Freshness.STALE}:
            if self.observed_at.value is None:
                raise ValueError("current and stale snapshots require an observation time")
        if self.state in {ScreenState.LOADING, ScreenState.MISSING, ScreenState.ERROR}:
            if self.observed_at.value is not None:
                raise ValueError("transient, missing and error states have no observation")


@dataclass(frozen=True)
class PilotIdentityView:
    pilot_id: PilotId
    display_name: FieldValue[str]
    source_slot: FieldValue[int]
    affiliation: FieldValue[NationServicePresentation]
    squadron_id: FieldValue[SquadronId]
    squadron_label: FieldValue[str]
    status: FieldValue[str]


@dataclass(frozen=True)
class PilotStatistics:
    missions: FieldValue[int]
    flight_minutes: FieldValue[int]
    claims: FieldValue[int]
    confirmed_victories: FieldValue[int]
    skill: FieldValue[int]
    reputation: FieldValue[int]


@dataclass(frozen=True)
class MissionSummary:
    mission_id: MissionId
    pilot_id: PilotId
    occurred_at: FieldValue[datetime]
    title: FieldValue[str]
    result: FieldValue[str]
    claims: FieldValue[int]
    confirmed_victories: FieldValue[int]


@dataclass(frozen=True)
class DiaryEntryView:
    diary_entry_id: DiaryEntryId
    pilot_id: PilotId
    mission_id: FieldValue[MissionId]
    occurred_at: FieldValue[datetime]
    narrative: FieldValue[str]


@dataclass(frozen=True)
class SquadronIdentityView:
    squadron_id: FieldValue[SquadronId]
    display_name: FieldValue[str]


@dataclass(frozen=True)
class SquadronMemberView:
    member_id: SquadronMemberId
    pilot_id: PilotId
    display_name: FieldValue[str]
    role: FieldValue[str]
    transfer_status: FieldValue[str]


@dataclass(frozen=True)
class SystemDiagnosticView:
    diagnostic_id: SystemDiagnosticId
    observed_at: FieldValue[datetime]
    code: "SystemDiagnosticCode"

    @property
    def message(self) -> str:
        return _SYSTEM_DIAGNOSTIC_MESSAGES[self.code]


class SystemDiagnosticCode(str, Enum):
    NO_LIVE_SERVICE = "no_live_service"


_SYSTEM_DIAGNOSTIC_MESSAGES = {
    SystemDiagnosticCode.NO_LIVE_SERVICE: (
        "Synthetic diagnostic: no live service is connected."
    )
}


@dataclass(frozen=True)
class OperationsSnapshot:
    """Dashboard/Operations (`OPR-01`) read model."""

    envelope: SnapshotEnvelope
    pilot: Optional[PilotIdentityView]
    statistics: Optional[PilotStatistics]
    recent_missions: Tuple[MissionSummary, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "recent_missions",
            _copied_immutable_tuple(
                self.recent_missions, MissionSummary, "recent missions"
            ),
        )


@dataclass(frozen=True)
class PilotDossierSnapshot:
    """Pilot Dossier (`DOS-01`) read model."""

    envelope: SnapshotEnvelope
    pilot: Optional[PilotIdentityView]
    statistics: Optional[PilotStatistics]


@dataclass(frozen=True)
class MissionsSnapshot:
    """Mission list/detail (`MIS-01/02`) read model."""

    envelope: SnapshotEnvelope
    pilot_id: Optional[PilotId]
    missions: Tuple[MissionSummary, ...]
    selected_mission_id: Optional[MissionId]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "missions",
            _copied_immutable_tuple(self.missions, MissionSummary, "missions"),
        )
        if self.selected_mission_id is not None and not any(
            mission.mission_id == self.selected_mission_id for mission in self.missions
        ):
            raise ValueError("selected mission must resolve by stable ID in the snapshot")


@dataclass(frozen=True)
class WarDiarySnapshot:
    """War Diary (`JRN-01`) read model."""

    envelope: SnapshotEnvelope
    pilot_id: Optional[PilotId]
    entries: Tuple[DiaryEntryView, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "entries",
            _copied_immutable_tuple(self.entries, DiaryEntryView, "diary entries"),
        )


@dataclass(frozen=True)
class SquadronSnapshot:
    """Squadron list/detail (`SQD-01/02`) read model."""

    envelope: SnapshotEnvelope
    pilot_id: Optional[PilotId]
    squadron: Optional[SquadronIdentityView]
    members: Tuple[SquadronMemberView, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "members",
            _copied_immutable_tuple(self.members, SquadronMemberView, "squadron members"),
        )


@dataclass(frozen=True)
class SystemStatusSnapshot:
    """Settings/Data & System Status (`SYS-01`) read model; no mutation API."""

    envelope: SnapshotEnvelope
    profile: FieldValue[str]
    diagnostics: Tuple[SystemDiagnosticView, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "diagnostics",
            _copied_immutable_tuple(
                self.diagnostics, SystemDiagnosticView, "system diagnostics"
            ),
        )


@dataclass(frozen=True)
class PilotSelection:
    pilot_id: PilotId


@dataclass(frozen=True)
class MissionSelection:
    pilot_id: PilotId
    mission_id: Optional[MissionId]


@dataclass(frozen=True)
class SquadronSelection:
    pilot_id: PilotId
    squadron_id: Optional[SquadronId]
    member_id: Optional[SquadronMemberId]


class QueryIntent(str, Enum):
    INITIAL = "initial"
    REFRESH = "refresh"
    RETRY = "retry"


@dataclass(frozen=True)
class QueryRequest(Generic[SelectionT]):
    """One bounded snapshot request; refresh/retry always have new request IDs."""

    request_id: RequestId
    selection: SelectionT
    intent: QueryIntent
    timeout: timedelta
    supersedes: Optional[RequestId] = None
    retry_of: Optional[RequestId] = None

    def __post_init__(self) -> None:
        if not _is_deeply_immutable(self.selection):
            raise TypeError("query selection must be deeply immutable")
        if self.timeout <= timedelta(0):
            raise ValueError("query timeout must be positive")
        if self.intent is QueryIntent.INITIAL:
            valid = self.supersedes is None and self.retry_of is None
        elif self.intent is QueryIntent.REFRESH:
            valid = self.supersedes is not None and self.retry_of is None
        else:
            valid = self.retry_of is not None and self.supersedes is None
        if not valid:
            raise ValueError("query request linkage does not match its intent")
        linked = self.supersedes or self.retry_of
        if linked == self.request_id:
            raise ValueError("refresh and retry require a new request ID")

    @classmethod
    def initial(
        cls,
        request_id: RequestId,
        selection: SelectionT,
        timeout: timedelta,
    ) -> "QueryRequest[SelectionT]":
        return cls(request_id, selection, QueryIntent.INITIAL, timeout)

    @classmethod
    def refresh(
        cls,
        request_id: RequestId,
        selection: SelectionT,
        timeout: timedelta,
        supersedes: RequestId,
    ) -> "QueryRequest[SelectionT]":
        return cls(
            request_id,
            selection,
            QueryIntent.REFRESH,
            timeout,
            supersedes=supersedes,
        )

    @classmethod
    def retry(
        cls,
        request_id: RequestId,
        selection: SelectionT,
        timeout: timedelta,
        retry_of: RequestId,
    ) -> "QueryRequest[SelectionT]":
        return cls(
            request_id,
            selection,
            QueryIntent.RETRY,
            timeout,
            retry_of=retry_of,
        )


class CancellationReason(str, Enum):
    USER_NAVIGATED = "user_navigated"
    REPLACED_REQUEST = "replaced_request"
    APPLICATION_SHUTDOWN = "application_shutdown"


@dataclass(frozen=True)
class CancellationRequest:
    request_id: RequestId
    reason: CancellationReason


class OperationsQueryService(Protocol):
    def request_snapshot(
        self, request: QueryRequest[PilotSelection]
    ) -> OperationsSnapshot: ...

    def cancel(self, request: CancellationRequest) -> None: ...


class PilotDossierQueryService(Protocol):
    def request_snapshot(
        self, request: QueryRequest[PilotSelection]
    ) -> PilotDossierSnapshot: ...

    def cancel(self, request: CancellationRequest) -> None: ...


class MissionsQueryService(Protocol):
    def request_snapshot(
        self, request: QueryRequest[MissionSelection]
    ) -> MissionsSnapshot: ...

    def cancel(self, request: CancellationRequest) -> None: ...


class WarDiaryQueryService(Protocol):
    def request_snapshot(
        self, request: QueryRequest[PilotSelection]
    ) -> WarDiarySnapshot: ...

    def cancel(self, request: CancellationRequest) -> None: ...


class SquadronQueryService(Protocol):
    def request_snapshot(
        self, request: QueryRequest[SquadronSelection]
    ) -> SquadronSnapshot: ...

    def cancel(self, request: CancellationRequest) -> None: ...


class SystemStatusQueryService(Protocol):
    def request_snapshot(self, request: QueryRequest[None]) -> SystemStatusSnapshot: ...

    def cancel(self, request: CancellationRequest) -> None: ...
