"""Issue #81 immutable presentation contracts, exercised with #80 fixtures only."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
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
    MissionOrderPolicy,
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
MISSION_ORDER = MissionOrderPolicy.NEWEST_FIRST_STABLE_ID


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


def _diary_records() -> tuple[DiaryEntryView, ...]:
    fixture = FIXTURES["diary-ready"]
    return tuple(
        DiaryEntryView(
            diary_entry_id=DiaryEntryId(record["id"]),
            pilot_id=PilotId(record["career_id"]),
            mission_id=FieldValue.known(MissionId(record["fields"]["mission_id"]["value"])),
            occurred_at=FieldValue.known(_time(record["occurred_at"])),
            narrative=FieldValue.known(record["fields"]["narrative"]["value"]),
        )
        for record in fixture["data"]["records"]
    )


def _squadron_members() -> tuple[SquadronMemberView, ...]:
    fixture = FIXTURES["squadron-ready"]
    return tuple(
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
        for record in fixture["data"]["records"]
    )


def _system_diagnostics() -> tuple[SystemDiagnosticView, ...]:
    record = FIXTURES["settings-ready"]["data"]["records"][0]
    return (
        SystemDiagnosticView(
            diagnostic_id=SystemDiagnosticId(record["id"]),
            observed_at=FieldValue.known(_time(record["occurred_at"])),
            code=SystemDiagnosticCode.NO_LIVE_SERVICE,
        ),
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
        _envelope("pilot-ready"), pilot.pilot_id, pilot, stats, cast(Any, []), MISSION_ORDER
    )
    dossier = PilotDossierSnapshot(_envelope("pilot-ready"), pilot.pilot_id, pilot, stats)
    missions = MissionsSnapshot(
        _envelope("missions-ready"),
        pilot.pilot_id,
        cast(Any, list(_mission_records())),
        None,
        MISSION_ORDER,
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
        None,
        SquadronIdentityView(
            squadron_id=FieldValue.unavailable(UnavailableReason.NOT_SUPPLIED),
            display_name=_field("squadron-ready", "squadron"),
        ),
        cast(Any, members),
        None,
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
    assert operations.envelope.state is ScreenState.READY
    assert operations.envelope.completeness is Completeness.PARTIAL
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
        MISSION_ORDER,
    )
    assert snapshot.selected_mission_id == MissionId("synthetic-mission-02")
    assert snapshot.missions[1].mission_id == snapshot.selected_mission_id


def test_child_records_cannot_cross_their_snapshot_owner_context() -> None:
    pilot = _pilot()
    missions = _mission_records()
    foreign_mission = replace(missions[0], pilot_id=PilotId("synthetic-career-foreign"))
    with pytest.raises(ValueError, match="owner"):
        MissionsSnapshot(
            _envelope("missions-ready"),
            pilot.pilot_id,
            (foreign_mission,),
            None,
            MISSION_ORDER,
        )
    with pytest.raises(ValueError, match="owner"):
        OperationsSnapshot(
            _envelope("pilot-ready"),
            pilot.pilot_id,
            pilot,
            _statistics(),
            (foreign_mission,),
            MISSION_ORDER,
        )

    foreign_diary = replace(
        _diary_records()[0], pilot_id=PilotId("synthetic-career-foreign")
    )
    with pytest.raises(ValueError, match="owner"):
        WarDiarySnapshot(_envelope("diary-ready"), pilot.pilot_id, (foreign_diary,))

    foreign_member = replace(
        _squadron_members()[0], pilot_id=PilotId("synthetic-career-foreign")
    )
    with pytest.raises(ValueError, match="owner"):
        SquadronSnapshot(
            _envelope("squadron-ready"),
            pilot.pilot_id,
            None,
            None,
            (foreign_member,),
            None,
        )

    foreign_pilot = replace(pilot, pilot_id=PilotId("synthetic-career-foreign"))
    with pytest.raises(ValueError, match="owner"):
        OperationsSnapshot(
            _envelope("pilot-ready"),
            pilot.pilot_id,
            foreign_pilot,
            _statistics(),
            (),
            MISSION_ORDER,
        )
    with pytest.raises(ValueError, match="owner"):
        PilotDossierSnapshot(
            _envelope("pilot-ready"), pilot.pilot_id, foreign_pilot, _statistics()
        )


def test_career_selection_is_independent_of_optional_payload_during_transitions() -> None:
    selected = PilotId(FIXTURES["loading-selected"]["career_id"])
    operations = OperationsSnapshot(
        _envelope("loading-selected"), selected, None, None, (), MISSION_ORDER
    )
    dossier = PilotDossierSnapshot(
        _envelope("error-query-selected"), selected, None, None
    )
    assert operations.pilot_id == selected
    assert dossier.pilot_id == selected
    assert operations.pilot is None and dossier.pilot is None

    unavailable = PilotDossierSnapshot(
        _envelope("unavailable-source-selected"), selected, None, None
    )
    assert unavailable.pilot_id == selected

    with pytest.raises(ValueError, match="stable pilot context"):
        PilotDossierSnapshot(_envelope("pilot-ready"), None, None, _statistics())

    unselected = OperationsSnapshot(
        _envelope("missing-career"), None, None, None, (), MISSION_ORDER
    )
    assert unselected.pilot_id is None


def test_selected_detail_ids_survive_payload_free_transitions() -> None:
    pilot_id = PilotId(FIXTURES["loading-selected"]["career_id"])
    mission_id = MissionId(FIXTURES["mission-detail-ready"]["subject_id"])
    mission = MissionsSnapshot(
        _envelope("loading-selected"), pilot_id, (), mission_id, MISSION_ORDER
    )
    assert mission.selected_mission_id == mission_id

    member_id = _squadron_members()[1].member_id
    squadron_id = SquadronId("synthetic-squadron-01")
    squadron = SquadronSnapshot(
        _envelope("unavailable-source-selected"),
        pilot_id,
        squadron_id,
        None,
        (),
        member_id,
    )
    assert squadron.selected_member_id == member_id
    assert squadron.selected_squadron_id == squadron_id


def test_selected_detail_ids_must_resolve_when_authoritative_payload_is_usable() -> None:
    pilot_id = PilotId(FIXTURES["missions-ready"]["career_id"])
    with pytest.raises(ValueError, match="selected mission"):
        MissionsSnapshot(
            _envelope("missions-ready"),
            pilot_id,
            _mission_records(),
            MissionId("synthetic-mission-not-present"),
            MISSION_ORDER,
        )
    with pytest.raises(ValueError, match="selected member"):
        SquadronSnapshot(
            _envelope("squadron-ready"),
            pilot_id,
            None,
            None,
            _squadron_members(),
            SquadronMemberId("synthetic-member-not-present"),
        )
    with pytest.raises(ValueError, match="squadron payload owner"):
        SquadronSnapshot(
            _envelope("squadron-ready"),
            pilot_id,
            SquadronId("synthetic-squadron-other"),
            SquadronIdentityView(
                squadron_id=FieldValue.known(SquadronId("synthetic-squadron-01")),
                display_name=FieldValue.known("Synthetic Squadron Cedar"),
            ),
            _squadron_members(),
            None,
        )


def test_expired_snapshot_and_freshness_semantics_are_cross_field_coherent() -> None:
    expired = _envelope("pilot-stale")
    with pytest.raises(ValueError, match="expired"):
        replace(expired, freshness=Freshness.CURRENT)
    with pytest.raises(ValueError, match="authority"):
        replace(expired, source_authority=SourceAuthority.UNRESOLVED)
    with pytest.raises(ValueError, match="stale"):
        replace(_envelope("pilot-ready"), freshness=Freshness.STALE)
    with pytest.raises(ValueError, match="observation"):
        replace(
            expired,
            observed_at=FieldValue.unavailable(UnavailableReason.UNKNOWN),
        )
    with pytest.raises(ValueError, match="unknown freshness"):
        replace(
            _envelope("unavailable-source-selected"),
            observed_at=FieldValue.known(datetime(2026, 1, 1, tzinfo=timezone.utc)),
            freshness=Freshness.CURRENT,
        )


def test_nested_unavailable_fields_are_authoritative_for_completeness() -> None:
    partial_pilot = _pilot("pilot-partial-conflict")
    source_envelope = _envelope("pilot-partial-conflict")
    snapshot = PilotDossierSnapshot(
        source_envelope,
        partial_pilot.pilot_id,
        partial_pilot,
        _statistics("pilot-partial-conflict"),
    )
    assert snapshot.envelope.completeness is Completeness.PARTIAL
    assert FieldUnavailable(
        "pilot.affiliation", UnavailableReason.SOURCE_CONFLICT
    ) in snapshot.envelope.unavailable_fields
    assert snapshot.envelope.observed_at == source_envelope.observed_at
    assert snapshot.envelope.source_authority is source_envelope.source_authority
    assert snapshot.envelope.contract_version == source_envelope.contract_version
    assert snapshot.envelope.warnings == source_envelope.warnings


def test_nested_collection_gaps_drive_completeness_across_every_screen_contract() -> None:
    pilot = _pilot()
    mission = replace(
        _mission_records()[0], title=FieldValue.unavailable(UnavailableReason.UNKNOWN)
    )
    diary = replace(
        _diary_records()[0],
        narrative=FieldValue.unavailable(UnavailableReason.TRUNCATED),
    )
    member = replace(
        _squadron_members()[0],
        transfer_status=FieldValue.unavailable(UnavailableReason.UNKNOWN),
    )
    snapshots = (
        OperationsSnapshot(
            _envelope("pilot-ready"),
            pilot.pilot_id,
            pilot,
            _statistics(),
            (mission,),
            MISSION_ORDER,
        ),
        MissionsSnapshot(
            _envelope("missions-ready"),
            pilot.pilot_id,
            (mission,),
            None,
            MISSION_ORDER,
        ),
        WarDiarySnapshot(
            _envelope("diary-ready"), pilot.pilot_id, (diary,)
        ),
        SquadronSnapshot(
            _envelope("squadron-ready"),
            pilot.pilot_id,
            None,
            None,
            (member,),
            None,
        ),
        SystemStatusSnapshot(
            _envelope("pilot-ready"),
            FieldValue.unavailable(UnavailableReason.NOT_SUPPLIED),
            (),
        ),
    )
    expected_paths = (
        "recent_missions.title",
        "missions.title",
        "entries.narrative",
        "members.transfer_status",
        "profile",
    )
    for snapshot, expected_path in zip(snapshots, expected_paths):
        assert snapshot.envelope.completeness is Completeness.PARTIAL
        assert expected_path in {
            item.field for item in snapshot.envelope.unavailable_fields
        }


@pytest.mark.parametrize("fixture_id", ["pilot-ready", "empty-records"])
@pytest.mark.parametrize(
    "authority",
    [
        SourceAuthority.UNRESOLVED,
        SourceAuthority.APPLICATION_QUERY,
        SourceAuthority.SYNTHETIC_QUERY,
    ],
)
def test_successful_snapshots_reject_non_data_authority(
    fixture_id: str, authority: SourceAuthority
) -> None:
    with pytest.raises(ValueError, match="authority"):
        replace(_envelope(fixture_id), source_authority=authority)


def test_retained_payload_rejects_unresolved_authority() -> None:
    pilot = _pilot()
    envelope = replace(
        _envelope("unavailable-source-selected"),
        source_authority=SourceAuthority.UNRESOLVED,
    )
    with pytest.raises(ValueError, match="authority"):
        PilotDossierSnapshot(envelope, pilot.pilot_id, pilot, _statistics())


def test_mission_collections_have_deterministic_ordering_and_stable_ties() -> None:
    pilot_id = PilotId(FIXTURES["missions-ready"]["career_id"])
    reversed_records = tuple(reversed(_mission_records()))
    snapshot = MissionsSnapshot(
        _envelope("missions-ready"), pilot_id, reversed_records, None, MISSION_ORDER
    )
    assert tuple(item.mission_id.value for item in snapshot.missions) == (
        "synthetic-mission-01",
        "synthetic-mission-02",
    )
    assert snapshot.mission_order_policy.value == "newest-first-stable-id"

    later = replace(
        reversed_records[0],
        mission_id=MissionId("synthetic-mission-00-later"),
        occurred_at=FieldValue.known(
            cast(datetime, reversed_records[0].occurred_at.value) + timedelta(days=1)
        ),
    )
    operations = OperationsSnapshot(
        _envelope("pilot-ready"),
        pilot_id,
        None,
        None,
        (later, *reversed_records),
        MISSION_ORDER,
    )
    assert tuple(item.mission_id.value for item in operations.recent_missions) == (
        "synthetic-mission-00-later",
        "synthetic-mission-01",
        "synthetic-mission-02",
    )

    unavailable_b = replace(
        reversed_records[0],
        mission_id=MissionId("synthetic-mission-unavailable-b"),
        occurred_at=FieldValue.unavailable(UnavailableReason.UNKNOWN),
    )
    with pytest.raises(ValueError, match="known event time"):
        MissionsSnapshot(
            _envelope("missions-ready"),
            pilot_id,
            (unavailable_b, reversed_records[0]),
            None,
            MISSION_ORDER,
        )


@pytest.mark.parametrize(
    "collection_name",
    ["operations missions", "missions", "diary entries", "squadron members", "diagnostics"],
)
def test_every_identifiable_snapshot_collection_rejects_duplicate_ids(
    collection_name: str,
) -> None:
    pilot = _pilot()
    if collection_name == "operations missions":
        item = _mission_records()[0]
        build = lambda: OperationsSnapshot(  # noqa: E731
            _envelope("pilot-ready"),
            pilot.pilot_id,
            pilot,
            _statistics(),
            (item, item),
            MISSION_ORDER,
        )
    elif collection_name == "missions":
        item = _mission_records()[0]
        build = lambda: MissionsSnapshot(  # noqa: E731
            _envelope("missions-ready"),
            pilot.pilot_id,
            (item, item),
            None,
            MISSION_ORDER,
        )
    elif collection_name == "diary entries":
        item = _diary_records()[0]
        build = lambda: WarDiarySnapshot(  # noqa: E731
            _envelope("diary-ready"), pilot.pilot_id, (item, item)
        )
    elif collection_name == "squadron members":
        item = _squadron_members()[0]
        build = lambda: SquadronSnapshot(  # noqa: E731
            _envelope("squadron-ready"),
            pilot.pilot_id,
            None,
            None,
            (item, item),
            None,
        )
    else:
        item = _system_diagnostics()[0]
        build = lambda: SystemStatusSnapshot(  # noqa: E731
            _envelope("settings-ready"),
            _field("settings-ready", "profile"),
            (item, item),
        )
    with pytest.raises(ValueError, match="duplicate"):
        build()


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
                MISSION_ORDER,
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
