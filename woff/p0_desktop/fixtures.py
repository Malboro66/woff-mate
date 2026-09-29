"""Closed #80 catalog to #81 immutable values for the experimental P0 process.

The catalog is bundled only by the P0 spec. No live service or path selection exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Optional, Union

from ..nation import NationService
from ..ui_contracts import (
    Completeness, ContractVersion, DiaryEntryId, DiaryEntryView, FailureCode,
    FieldUnavailable, FieldValue, Freshness, MissionId, MissionOrderPolicy,
    MissionSummary, MissionsSnapshot, OperationsSnapshot, PilotDossierSnapshot,
    PilotId, PilotIdentityView, PilotStatistics, SanitizedFailure, ScreenState,
    SnapshotEnvelope, SnapshotReason, SourceAuthority, SquadronIdentityView,
    SquadronMemberId, SquadronMemberView, SquadronSnapshot, SystemDiagnosticCode,
    SystemDiagnosticId, SystemDiagnosticView, SystemStatusSnapshot,
    UnavailableReason, WarDiarySnapshot, Warning, WarningCode,
)

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
CATALOG = ROOT / "woff/tests/fixtures/ui_states/catalog.json"

SCREENS = (
    ("OPR-01", "Operations", "operations"),
    ("DOS-01", "Pilot Dossier", "pilot_dossier"),
    ("MIS-01", "Missions", "missions"),
    ("SQD-01", "Squadron", "squadron"),
    ("JRN-01", "War Diary", "war_diary"),
    ("RPT-01", "Reports", "reports"),
    ("SYS-01", "Data & System Status", "system_status"),
)
READY = {
    "OPR-01": "pilot-ready", "DOS-01": "pilot-ready",
    "MIS-01": "missions-ready", "SQD-01": "squadron-ready",
    "JRN-01": "diary-ready", "RPT-01": "reports-ready",
    "SYS-01": "settings-ready",
}
STATE_CASES = {
    "ready": READY,
    "loading": {**dict.fromkeys(READY, "loading-selected"), "SYS-01": "loading"},
    "empty": {**dict.fromkeys(READY, "empty-records"), "SYS-01": "empty-global"},
    "missing": {**dict.fromkeys(READY, "missing-source-selected"), "SYS-01": "missing-source"},
    "stale/unavailable": {**dict.fromkeys(READY, "unavailable-source-selected"), "SYS-01": "unavailable-source"},
    "error": {**dict.fromkeys(READY, "error-query-selected"), "SYS-01": "error-query"},
}


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _field(source: dict) -> FieldValue:
    reason = source["unavailable_reason"]
    if reason is not None:
        return FieldValue.unavailable(UnavailableReason(reason))
    return FieldValue.known(source["value"])


def _envelope(case: dict) -> SnapshotEnvelope:
    data = case["data"]
    gaps = tuple(FieldUnavailable(k, UnavailableReason(v["unavailable_reason"]))
                 for k, v in (data["fields"] if data else {}).items()
                 if v["unavailable_reason"] is not None)
    return SnapshotEnvelope(
        state=ScreenState(case["state"]),
        reason=SnapshotReason(case["reason"]) if case["reason"] else None,
        observed_at=(FieldValue.known(_time(case["observed_at"])) if case["observed_at"]
                     else FieldValue.unavailable(UnavailableReason.UNKNOWN)),
        freshness=Freshness(case["freshness"]),
        freshness_policy=FieldValue.unavailable(UnavailableReason.NOT_SUPPLIED),
        source_authority=SourceAuthority(case["source_authority"]),
        contract_version=ContractVersion(case["contract_version"]),
        completeness=Completeness.PARTIAL if gaps else Completeness.COMPLETE,
        warnings=tuple(Warning(WarningCode(w["code"])) for w in case["warnings"]),
        unavailable_fields=gaps,
        failure=SanitizedFailure(FailureCode.QUERY_FAILED) if case["state"] == "error" else None,
    )


@dataclass(frozen=True)
class CareerOption:
    pilot_id: PilotId
    display_name: FieldValue[str]
    source_slot: FieldValue[int]
    service: FieldValue[str]
    squadron: FieldValue[str]


@dataclass(frozen=True)
class ReportSummary:
    report_id: str  # P0-only fixture record, no report contract exists in #81.
    pilot_id: PilotId
    title: FieldValue[str]
    summary: FieldValue[str]


@dataclass(frozen=True)
class ReportsView:
    envelope: SnapshotEnvelope
    pilot_id: Optional[PilotId]
    reports: tuple[ReportSummary, ...]

    def __post_init__(self) -> None:
        if any(report.pilot_id != self.pilot_id for report in self.reports):
            raise ValueError("Cross-career report payload")
        if len({report.report_id for report in self.reports}) != len(self.reports):
            raise ValueError("Duplicate report identity")
        if self.envelope.state is ScreenState.READY and not self.reports:
            raise ValueError("Ready reports require a report")
        if self.envelope.state is ScreenState.EMPTY and self.reports:
            raise ValueError("Empty reports cannot carry a report")
        if self.envelope.state in {ScreenState.LOADING, ScreenState.MISSING,
                                   ScreenState.ERROR} and self.reports:
            raise ValueError("Payload-free reports cannot carry a report")


Snapshot = Union[OperationsSnapshot, PilotDossierSnapshot, MissionsSnapshot,
                 SquadronSnapshot, WarDiarySnapshot, ReportsView, SystemStatusSnapshot]


class FixturePresentation:
    """Single deterministic read-only catalog; output is frozen presentation data."""

    def __init__(self) -> None:
        with CATALOG.open(encoding="utf-8") as stream:
            catalog = json.load(stream)
        if catalog["catalog_version"] != 1 or len(catalog["fixtures"]) != 30:
            raise ValueError("Unexpected P0 fixture catalog")
        self._cases = {case["id"]: case for case in catalog["fixtures"]}
        records = self._cases["careers-ready"]["data"]["records"]
        self.careers = tuple(
            CareerOption(PilotId(r["career_id"]), *(_field(r["fields"][key])
                         for key in ("display_name", "source_slot", "service", "squadron")))
            for r in records
        )

    def case_id(self, screen: str, career_id: Optional[PilotId], state: str = "ready") -> str:
        if screen not in READY or state not in STATE_CASES:
            raise ValueError("Unknown P0 screen or shared state")
        if screen == "SYS-01":
            return STATE_CASES[state][screen]
        if career_id is None:
            return "missing-career"
        if career_id not in {option.pilot_id for option in self.careers}:
            raise ValueError("Career is outside the synthetic catalog")
        # The second homonym has selector identity only; never borrow career 02 data.
        if career_id != self.careers[0].pilot_id:
            return "missing-source-selected"  # synthesized below with the selected ID
        case_id = STATE_CASES[state][screen]
        if screen not in self._cases[case_id]["screens"]:
            raise ValueError("Fixture does not target the selected screen")
        return case_id

    def snapshot(self, screen: str, career_id: Optional[PilotId],
                 state: str = "ready") -> tuple[str, Snapshot]:
        case_id = self.case_id(screen, career_id, state)
        case = self._cases[case_id]
        # No payload is copied to career 03. Its source-missing envelope preserves
        # that explicit selection, using the canonical fixture's safe vocabulary.
        if career_id is not None and career_id == self.careers[1].pilot_id and screen != "SYS-01":
            case = {**case, "career_id": career_id.value}
        owner = PilotId(case["career_id"]) if case["career_id"] else None
        envelope = _envelope(case)
        data = case["data"]
        fields = data["fields"] if data else {}
        records = data["records"] if data else []
        if screen in {"OPR-01", "DOS-01"}:
            pilot = stats = None
            if data and data["collection"] is None:
                if owner is None:
                    raise ValueError("Pilot payload requires career identity")
                service = fields["service"]
                affiliation = (FieldValue.known(NationService(service["value"]).presentation())
                               if service["unavailable_reason"] is None
                               else FieldValue.unavailable(UnavailableReason(service["unavailable_reason"])))
                pilot = PilotIdentityView(owner, _field(fields["display_name"]),
                                          _field(fields["source_slot"]), affiliation,
                                          FieldValue.unavailable(UnavailableReason.NOT_SUPPLIED),
                                          _field(fields["squadron"]), _field(fields["status"]))
                stats = PilotStatistics(*(_field(fields[k]) for k in (
                    "missions", "flight_minutes", "claims", "confirmed_victories", "skill", "reputation")))
            if screen == "OPR-01":
                result: Snapshot = OperationsSnapshot(envelope, owner, pilot, stats, (),
                                                       MissionOrderPolicy.NEWEST_FIRST_STABLE_ID)
            else:
                result = PilotDossierSnapshot(envelope, owner, pilot, stats)
        elif screen == "MIS-01":
            missions = tuple(MissionSummary(MissionId(r["id"]), PilotId(r["career_id"]),
                FieldValue.known(_time(r["occurred_at"])),
                *(_field(r["fields"][key]) for key in ("title", "result", "claims", "confirmed_victories")))
                for r in records)
            result = MissionsSnapshot(envelope, owner, missions, None,
                                      MissionOrderPolicy.NEWEST_FIRST_STABLE_ID)
        elif screen == "SQD-01":
            members = tuple(SquadronMemberView(SquadronMemberId(r["id"]), PilotId(r["career_id"]),
                *(_field(r["fields"][key]) for key in ("display_name", "role", "transfer_status")))
                for r in records)
            squadron = (SquadronIdentityView(FieldValue.unavailable(UnavailableReason.NOT_SUPPLIED),
                                              _field(fields["squadron"])) if "squadron" in fields else None)
            result = SquadronSnapshot(envelope, owner, None, squadron, members, None)
        elif screen == "JRN-01":
            entries = tuple(DiaryEntryView(DiaryEntryId(r["id"]), PilotId(r["career_id"]),
                FieldValue.known(MissionId(r["fields"]["mission_id"]["value"])),
                FieldValue.known(_time(r["occurred_at"])), _field(r["fields"]["narrative"]))
                for r in records)
            result = WarDiarySnapshot(envelope, owner, entries)
        elif screen == "RPT-01":
            result = ReportsView(envelope, owner, tuple(ReportSummary(r["id"], PilotId(r["career_id"]),
                _field(r["fields"]["title"]), _field(r["fields"]["narrative"])) for r in records))
        else:
            diagnostics = tuple(SystemDiagnosticView(SystemDiagnosticId(r["id"]),
                FieldValue.known(_time(r["occurred_at"])), SystemDiagnosticCode.NO_LIVE_SERVICE)
                for r in records)
            result = SystemStatusSnapshot(envelope, _field(fields["profile"]) if fields else None,
                                          diagnostics)
        return case_id, result
