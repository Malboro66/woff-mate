"""Issue #81 immutable presentation contracts, exercised with #80 fixtures only."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, cast

import pytest

from woff.nation import NationService
from woff.ui_contracts import (
    CancellationReason,
    CancellationRequest,
    Completeness,
    ContractVersion,
    DiaryEntryId,
    DiaryEntryView,
    FailureCode,
    FieldUnavailable,
    FieldValue,
    Freshness,
    FreshnessPolicyId,
    MissionId,
    MissionSelection,
    MissionSummary,
    MissionsQueryService,
    MissionsSnapshot,
    OperationsQueryService,
    OperationsSnapshot,
    PilotDossierQueryService,
    PilotDossierSnapshot,
    PilotId,
    PilotIdentityView,
    PilotSelection,
    PilotStatistics,
    QueryIntent,
    QueryRequest,
    RequestId,
    SanitizedFailure,
    ScreenState,
    SnapshotEnvelope,
    SnapshotReason,
    SourceAuthority,
    SquadronId,
    SquadronIdentityView,
    SquadronMemberId,
    SquadronMemberView,
    SquadronQueryService,
    SquadronSelection,
    SquadronSnapshot,
    SystemDiagnosticId,
    SystemDiagnosticCode,
    SystemDiagnosticView,
    SystemStatusQueryService,
    SystemStatusSnapshot,
    UnavailableReason,
    WarDiaryQueryService,
    WarDiarySnapshot,
    Warning,
    WarningCode,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "woff" / "tests" / "fixtures" / "ui_states" / "catalog.json"


def _fixtures() -> dict[str, dict[str, Any]]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {item["id"]: item for item in catalog["fixtures"]}


FIXTURES = _fixtures()


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _reason(value: str | None) -> SnapshotReason | None:
    return SnapshotReason(value) if value is not None else None


def _field_reason(value: str) -> UnavailableReason:
    return UnavailableReason(value)


def _envelope(fixture_id: str) -> SnapshotEnvelope:
    fixture = FIXTURES[fixture_id]
    observed = fixture["observed_at"]
    freshness_policy = FieldValue.unavailable(UnavailableReason.NOT_SUPPLIED)
    warnings = [Warning(WarningCode(item["code"])) for item in fixture["warnings"]]
    unavailable: list[FieldUnavailable] = []
    data = fixture["data"]
    if data:
        for field_name, field in data["fields"].items():
            if field["unavailable_reason"] is not None:
                unavailable.append(
                    FieldUnavailable(field_name, _field_reason(field["unavailable_reason"]))
                )
    failure = None
    if fixture["state"] == "error":
        failure = SanitizedFailure(FailureCode.QUERY_FAILED)
    return SnapshotEnvelope(
        state=ScreenState(fixture["state"]),
        reason=_reason(fixture["reason"]),
        observed_at=(
            FieldValue.known(_time(observed))
            if observed is not None
            else FieldValue.unavailable(UnavailableReason.UNKNOWN)
        ),
        freshness=Freshness(fixture["freshness"]),
        freshness_policy=freshness_policy,
        source_authority=SourceAuthority(fixture["source_authority"]),
        contract_version=ContractVersion(fixture["contract_version"]),
        completeness=(
            Completeness.PARTIAL
            if unavailable or Warning(WarningCode.PARTIAL_RECORD) in warnings
            else Completeness.COMPLETE
        ),
        warnings=cast(Any, warnings),
        unavailable_fields=cast(Any, unavailable),
        failure=failure,
    )


def _field(fixture_id: str, name: str) -> FieldValue[Any]:
    source = FIXTURES[fixture_id]["data"]["fields"][name]
    if source["unavailable_reason"] is not None:
        return FieldValue.unavailable(_field_reason(source["unavailable_reason"]))
    return FieldValue.known(source["value"])


def _pilot(fixture_id: str = "pilot-ready") -> PilotIdentityView:
    fixture = FIXTURES[fixture_id]
    fields = fixture["data"]["fields"]
    service = fields["service"]
    affiliation = (
        FieldValue.known(NationService(service["value"]).presentation())
        if service["unavailable_reason"] is None
        else FieldValue.unavailable(_field_reason(service["unavailable_reason"]))
    )
    return PilotIdentityView(
        pilot_id=PilotId(fixture["career_id"]),
        display_name=_field(fixture_id, "display_name"),
        source_slot=_field(fixture_id, "source_slot"),
        affiliation=affiliation,
        squadron_id=FieldValue.unavailable(UnavailableReason.NOT_SUPPLIED),
        squadron_label=_field(fixture_id, "squadron"),
        status=_field(fixture_id, "status"),
    )


def _statistics(fixture_id: str = "pilot-ready") -> PilotStatistics:
    return PilotStatistics(
        missions=_field(fixture_id, "missions"),
        flight_minutes=_field(fixture_id, "flight_minutes"),
        claims=_field(fixture_id, "claims"),
        confirmed_victories=_field(fixture_id, "confirmed_victories"),
        skill=_field(fixture_id, "skill"),
        reputation=_field(fixture_id, "reputation"),
    )


def _mission_records(fixture_id: str = "missions-ready") -> tuple[MissionSummary, ...]:
    fixture = FIXTURES[fixture_id]
    return tuple(
        MissionSummary(
            mission_id=MissionId(record["id"]),
            pilot_id=PilotId(record["career_id"]),
            occurred_at=FieldValue.known(_time(record["occurred_at"])),
            title=FieldValue.known(record["fields"]["title"]["value"]),
            result=FieldValue.known(record["fields"]["result"]["value"]),
            claims=FieldValue.known(record["fields"]["claims"]["value"]),
            confirmed_victories=FieldValue.known(
                record["fields"]["confirmed_victories"]["value"]
            ),
        )
        for record in fixture["data"]["records"]
    )


def test_public_contract_has_six_explicit_frozen_screen_snapshots() -> None:
    snapshots = (
        OperationsSnapshot,
        PilotDossierSnapshot,
        MissionsSnapshot,
        WarDiarySnapshot,
        SquadronSnapshot,
        SystemStatusSnapshot,
    )
    assert len(snapshots) == 6
    assert all(getattr(item, "__dataclass_params__").frozen for item in snapshots)


def test_shared_envelope_keeps_every_semantically_distinct_condition() -> None:
    cases = {
        "loading": (ScreenState.LOADING, Freshness.UNKNOWN, Completeness.COMPLETE),
        "pilot-ready": (ScreenState.READY, Freshness.CURRENT, Completeness.COMPLETE),
        "empty-records": (ScreenState.EMPTY, Freshness.CURRENT, Completeness.COMPLETE),
        "missing-career": (ScreenState.MISSING, Freshness.UNKNOWN, Completeness.COMPLETE),
        "unavailable-source-selected": (
            ScreenState.STALE_OR_UNAVAILABLE,
            Freshness.UNKNOWN,
            Completeness.COMPLETE,
        ),
        "pilot-stale": (
            ScreenState.STALE_OR_UNAVAILABLE,
            Freshness.STALE,
            Completeness.COMPLETE,
        ),
        "pilot-partial-conflict": (
            ScreenState.READY,
            Freshness.CURRENT,
            Completeness.PARTIAL,
        ),
        "error-query-selected": (ScreenState.ERROR, Freshness.UNKNOWN, Completeness.COMPLETE),
    }
    for fixture_id, expected in cases.items():
        envelope = _envelope(fixture_id)
        assert (envelope.state, envelope.freshness, envelope.completeness) == expected

    assert _envelope("missing-career").observed_at.reason is UnavailableReason.UNKNOWN
    assert _envelope("empty-records").state is not _envelope("missing-career").state
    assert _envelope("pilot-stale").freshness is not Freshness.UNKNOWN
    assert _envelope("error-query-selected").failure == SanitizedFailure(
        FailureCode.QUERY_FAILED
    )
    partial = _envelope("pilot-partial-conflict")
    assert partial.warnings == (
        Warning(WarningCode.PARTIAL_RECORD),
        Warning(WarningCode.SOURCE_CONFLICT),
    )
    assert tuple(item.message for item in partial.warnings) == tuple(
        item["message"] for item in FIXTURES["pilot-partial-conflict"]["warnings"]
    )
    assert partial.contract_version == ContractVersion("synthetic-ui-v1")
    assert partial.freshness_policy.reason is UnavailableReason.NOT_SUPPLIED


def test_envelope_defensively_copies_warnings_and_unavailable_fields() -> None:
    warnings = [Warning(WarningCode.PARTIAL_RECORD)]
    unavailable = [FieldUnavailable("pilot.status", UnavailableReason.UNKNOWN)]
    envelope = SnapshotEnvelope(
        state=ScreenState.READY,
        reason=None,
        observed_at=FieldValue.known(datetime(2026, 1, 1, tzinfo=timezone.utc)),
        freshness=Freshness.CURRENT,
        freshness_policy=FieldValue.known(FreshnessPolicyId("ui-default-v1")),
        source_authority=SourceAuthority.SYNTHETIC_RECORDS,
        contract_version=ContractVersion("synthetic-ui-v1"),
        completeness=Completeness.PARTIAL,
        warnings=cast(Any, warnings),
        unavailable_fields=cast(Any, unavailable),
        failure=None,
    )
    warnings.clear()
    unavailable.clear()
    assert envelope.warnings == (Warning(WarningCode.PARTIAL_RECORD),)
    assert envelope.unavailable_fields == (
        FieldUnavailable("pilot.status", UnavailableReason.UNKNOWN),
    )
    with pytest.raises(FrozenInstanceError):
        envelope.state = ScreenState.ERROR  # type: ignore[misc]
    with pytest.raises(AttributeError):
        envelope.warnings.append(Warning(WarningCode.QUERY_FAILED))  # type: ignore[attr-defined]


def test_field_values_make_known_zero_and_unavailable_distinct() -> None:
    known_zero = FieldValue.known(0)
    missing = FieldValue.unavailable(UnavailableReason.NOT_SUPPLIED)
    unknown = FieldValue.unavailable(UnavailableReason.UNKNOWN)
    assert known_zero.value == 0 and known_zero.reason is None
    assert missing.value is None and missing.reason is UnavailableReason.NOT_SUPPLIED
    assert unknown != missing
    with pytest.raises(ValueError):
        FieldValue(value=None, reason=None)
    with pytest.raises(ValueError):
        FieldValue(value="invented", reason=UnavailableReason.UNKNOWN)
    with pytest.raises(TypeError):
        FieldValue.known(cast(Any, ["mutable"]))


def test_error_metadata_cannot_mix_failure_kinds_or_observation_data() -> None:
    fixture = _envelope("error-query-selected")
    with pytest.raises(ValueError):
        SnapshotEnvelope(
            state=fixture.state,
            reason=fixture.reason,
            observed_at=fixture.observed_at,
            freshness=fixture.freshness,
            freshness_policy=fixture.freshness_policy,
            source_authority=fixture.source_authority,
            contract_version=fixture.contract_version,
            completeness=fixture.completeness,
            warnings=fixture.warnings,
            unavailable_fields=fixture.unavailable_fields,
            failure=SanitizedFailure(FailureCode.REQUEST_TIMEOUT),
        )
    with pytest.raises(ValueError):
        SnapshotEnvelope(
            state=fixture.state,
            reason=fixture.reason,
            observed_at=FieldValue.known(datetime(2026, 1, 1, tzinfo=timezone.utc)),
            freshness=Freshness.UNKNOWN,
            freshness_policy=fixture.freshness_policy,
            source_authority=fixture.source_authority,
            contract_version=fixture.contract_version,
            completeness=fixture.completeness,
            warnings=fixture.warnings,
            unavailable_fields=fixture.unavailable_fields,
            failure=fixture.failure,
        )


def test_stable_identity_is_explicit_and_never_derived_from_fixture_labels() -> None:
    careers = FIXTURES["careers-ready"]["data"]["records"]
    homonyms = [
        item
        for item in careers
        if item["fields"]["display_name"]["value"] == "Synthetic Pilot Aster"
    ]
    assert len(homonyms) == 2
    ids = {PilotId(item["id"]) for item in homonyms}
    assert len(ids) == 2
    with pytest.raises(ValueError):
        PilotId("Synthetic Pilot Aster")
    with pytest.raises((TypeError, ValueError)):
        PilotId(cast(Any, 2))

    missions = _mission_records()
    assert missions[0].mission_id != missions[1].mission_id
    assert missions[0].occurred_at == missions[1].occurred_at


def test_pilot_contract_consumes_canonical_nation_service_without_raw_evidence() -> None:
    pilot = _pilot()
    affiliation = pilot.affiliation.value
    assert affiliation is not None
    assert affiliation.nation_code is not None and affiliation.nation_code.value == "GB"
    assert affiliation.service_code is not None and affiliation.service_code.value == "RFC"
    assert affiliation.nation_label == "Britain"
    assert affiliation.service_label == "RFC"
    assert not hasattr(affiliation, "nation_raw")
    assert not hasattr(affiliation, "serviceOrNationLabel")

    conflict = _pilot("pilot-partial-conflict")
    assert conflict.affiliation.value is None
    assert conflict.affiliation.reason is UnavailableReason.SOURCE_CONFLICT


def test_fixture_backed_screen_values_are_frozen_and_nested_collections_are_tuples() -> None:
    pilot = _pilot()
    stats = _statistics()
    operations = OperationsSnapshot(
        _envelope("pilot-ready"), pilot, stats, cast(Any, [])
    )
    dossier = PilotDossierSnapshot(_envelope("pilot-ready"), pilot, stats)
    missions = MissionsSnapshot(
        _envelope("missions-ready"),
        pilot.pilot_id,
        cast(Any, list(_mission_records())),
        None,
    )

    diary_fixture = FIXTURES["diary-ready"]
    diary_entries = [
        DiaryEntryView(
            diary_entry_id=DiaryEntryId(record["id"]),
            pilot_id=PilotId(record["career_id"]),
            mission_id=FieldValue.known(MissionId(record["fields"]["mission_id"]["value"])),
            occurred_at=FieldValue.known(_time(record["occurred_at"])),
            narrative=FieldValue.known(record["fields"]["narrative"]["value"]),
        )
        for record in diary_fixture["data"]["records"]
    ]
    diary = WarDiarySnapshot(
        _envelope("diary-ready"), pilot.pilot_id, cast(Any, diary_entries)
    )

    squadron_fixture = FIXTURES["squadron-ready"]
    members = [
        SquadronMemberView(
            member_id=SquadronMemberId(record["id"]),
            pilot_id=PilotId(record["career_id"]),
            display_name=FieldValue.known(record["fields"]["display_name"]["value"]),
            role=FieldValue.known(record["fields"]["role"]["value"]),
            transfer_status=(
                FieldValue.known(record["fields"]["transfer_status"]["value"])
                if record["fields"]["transfer_status"]["unavailable_reason"] is None
                else FieldValue.unavailable(
                    _field_reason(record["fields"]["transfer_status"]["unavailable_reason"])
                )
            ),
        )
        for record in squadron_fixture["data"]["records"]
    ]
    squadron = SquadronSnapshot(
        _envelope("squadron-ready"),
        pilot.pilot_id,
        SquadronIdentityView(
            squadron_id=FieldValue.unavailable(UnavailableReason.NOT_SUPPLIED),
            display_name=_field("squadron-ready", "squadron"),
        ),
        cast(Any, members),
    )

    settings_record = FIXTURES["settings-ready"]["data"]["records"][0]
    settings = SystemStatusSnapshot(
        _envelope("settings-ready"),
        profile=_field("settings-ready", "profile"),
        diagnostics=cast(
            Any,
            [
                SystemDiagnosticView(
                    diagnostic_id=SystemDiagnosticId(settings_record["id"]),
                    observed_at=FieldValue.known(_time(settings_record["occurred_at"])),
                    code=SystemDiagnosticCode.NO_LIVE_SERVICE,
                )
            ],
        ),
    )
    assert settings.diagnostics[0].message == (
        settings_record["fields"]["diagnostic"]["value"]
    )

    assert operations.recent_missions == ()
    assert operations.envelope == _envelope("pilot-ready")
    assert dossier.pilot == pilot
    assert dossier.envelope == operations.envelope
    assert isinstance(missions.missions, tuple)
    assert isinstance(diary.entries, tuple)
    assert isinstance(squadron.members, tuple)
    assert isinstance(settings.diagnostics, tuple)
    diary_entries.clear()
    members.clear()
    assert len(diary.entries) == 2
    assert len(squadron.members) == 2
    with pytest.raises(FrozenInstanceError):
        missions.selected_mission_id = MissionId("synthetic-mission-01")  # type: ignore[misc]


def test_selected_mission_is_an_explicit_stable_id_not_list_position() -> None:
    fixture = FIXTURES["mission-detail-ready"]
    selected = MissionId(fixture["subject_id"])
    snapshot = MissionsSnapshot(
        _envelope("mission-detail-ready"),
        PilotId(fixture["career_id"]),
        _mission_records("mission-detail-ready"),
        selected,
    )
    assert snapshot.selected_mission_id == MissionId("synthetic-mission-02")
    assert snapshot.missions[1].mission_id == snapshot.selected_mission_id


def test_sanitized_failures_are_closed_and_discard_exception_details() -> None:
    secret = RuntimeError(
        r"SELECT * FROM pilots; cursor=<sqlite3.Cursor>; C:\Users\Private\campaign.sqlite"
    )
    failure = SanitizedFailure.from_exception(FailureCode.QUERY_FAILED, secret)
    rendered = repr(failure) + failure.message
    assert failure.retryable
    for forbidden in ("SELECT", "cursor", "sqlite3", "Users", "campaign.sqlite"):
        assert forbidden not in rendered
    assert failure.message == FIXTURES["error-query"]["warnings"][0]["message"]


def test_refresh_retry_timeout_and_cancellation_are_request_contracts() -> None:
    selection = MissionSelection(PilotId("synthetic-career-02"), None)
    initial = QueryRequest.initial(
        RequestId("request-initial"), selection, timedelta(seconds=5)
    )
    refresh = QueryRequest.refresh(
        RequestId("request-refresh"), selection, timedelta(seconds=5), initial.request_id
    )
    retry = QueryRequest.retry(
        RequestId("request-retry"), selection, timedelta(seconds=10), refresh.request_id
    )
    cancellation = CancellationRequest(
        initial.request_id, CancellationReason.REPLACED_REQUEST
    )
    assert refresh.intent is QueryIntent.REFRESH
    assert refresh.request_id != initial.request_id
    assert refresh.supersedes == initial.request_id
    assert retry.intent is QueryIntent.RETRY and retry.retry_of == refresh.request_id
    assert cancellation.request_id == initial.request_id
    with pytest.raises(ValueError):
        QueryRequest(
            request_id=RequestId("bad-refresh"),
            selection=selection,
            intent=QueryIntent.REFRESH,
            timeout=timedelta(seconds=5),
        )
    with pytest.raises(TypeError):
        QueryRequest.initial(
            RequestId("mutable-selection"), cast(Any, []), timedelta(seconds=5)
        )


def test_query_protocols_return_snapshots_without_direct_presentation_access() -> None:
    class FakeMissions:
        def __init__(self) -> None:
            self.requests: list[QueryRequest[MissionSelection]] = []
            self.cancellations: list[CancellationRequest] = []

        def request_snapshot(
            self, request: QueryRequest[MissionSelection]
        ) -> MissionsSnapshot:
            self.requests.append(request)
            return MissionsSnapshot(
                _envelope("missions-ready"),
                request.selection.pilot_id,
                _mission_records(),
                request.selection.mission_id,
            )

        def cancel(self, request: CancellationRequest) -> None:
            self.cancellations.append(request)

    service: MissionsQueryService = FakeMissions()
    request = QueryRequest.initial(
        RequestId("request-01"),
        MissionSelection(PilotId("synthetic-career-02"), None),
        timedelta(seconds=5),
    )
    snapshot = service.request_snapshot(request)
    service.cancel(CancellationRequest(request.request_id, CancellationReason.USER_NAVIGATED))
    assert snapshot.envelope == _envelope("missions-ready")
    assert cast(FakeMissions, service).requests == [request]
    assert cast(FakeMissions, service).cancellations[0].request_id == request.request_id

    protocols = (
        OperationsQueryService,
        PilotDossierQueryService,
        MissionsQueryService,
        WarDiaryQueryService,
        SquadronQueryService,
        SystemStatusQueryService,
    )
    assert len(protocols) == 6


def test_request_selection_contracts_use_stable_ids() -> None:
    pilot = PilotSelection(PilotId("synthetic-career-02"))
    mission = MissionSelection(pilot.pilot_id, MissionId("synthetic-mission-02"))
    squadron = SquadronSelection(
        pilot.pilot_id,
        SquadronId("synthetic-squadron-01"),
        SquadronMemberId("synthetic-wingman-02"),
    )
    assert mission.pilot_id == pilot.pilot_id
    assert squadron.pilot_id == pilot.pilot_id
    assert squadron.member_id != squadron.squadron_id


def test_contract_module_has_no_forbidden_runtime_or_toolkit_boundary_imports() -> None:
    path = ROOT / "woff" / "ui_contracts.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imports.isdisjoint(
        {
            "PySide6",
            "PyQt6",
            "sqlite3",
            "pathlib",
            "watchdog",
            "database",
            "repositories",
            "parsers",
        }
    )

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").casefold()
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").casefold()
    for qt_name in ("pyside2", "pyside6", "pyqt5", "pyqt6"):
        assert qt_name not in pyproject
        assert qt_name not in requirements
