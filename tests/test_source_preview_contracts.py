"""Source identity, field evidence and deep immutability regressions."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from woff.source_preview_contracts import (
    FieldEvidence, MissionLogPreview, PreviewAuthority, PreviewFailure, PreviewField,
    PreviewProvenance, PreviewRequest, PreviewSnapshot, RecordPolicy, RouteEntry, SourceSelection,
)
from woff.ui_contracts import FieldValue, Freshness, RequestId, ScreenState, UnavailableReason


def selection(alias="M-01"):
    return SourceSelection(str(uuid4()), alias, str(uuid4()))


def payload(source):
    value = PreviewField.parsed("Fictional")
    return MissionLogPreview(source, value, value, value, value, value, value,
                             1, 1, ("Fictional entry",), (RouteEntry(value, value),))


def test_empty_and_unavailable_are_distinct_and_honest():
    empty = PreviewField.parsed("")
    unavailable = PreviewField.unavailable(UnavailableReason.UNSUPPORTED)
    assert empty.value == FieldValue.known("")
    assert empty.evidence is FieldEvidence.EMPTY
    assert "parser returned an empty value" in empty.display("Rank")
    assert unavailable.evidence is FieldEvidence.UNAVAILABLE
    assert unavailable.value.reason is UnavailableReason.UNSUPPORTED
    assert unavailable != empty
    with pytest.raises(ValueError):
        PreviewField(FieldValue.known(""), FieldEvidence.PARSED)
    with pytest.raises(ValueError):
        PreviewField.parsed("x" * 1001)
    with pytest.raises(ValueError):
        PreviewField(FieldValue.known(3), FieldEvidence.PARSED)


def test_mission_has_no_career_or_mission_identity():
    source = selection()
    mission = payload(source)
    assert mission.career_association == "UNVERIFIED"
    assert not hasattr(mission, "pilot_id") and not hasattr(mission, "mission_id")
    with pytest.raises(ValueError):
        replace(mission, career_association="VERIFIED")
    with pytest.raises(ValueError):
        replace(mission, selection=selection("S-01"))


@pytest.mark.parametrize("mutation", [
    {"formation_entries": ["Fictional entry"]}, {"route_entries": [{"kind": "Fictional"}]},
    {"formation_count": True}, {"waypoint_count": -1}, {"formation_entries": ({"mutable": []},)},
])
def test_nested_mutability_and_invalid_counts_rejected(mutation):
    with pytest.raises((TypeError, ValueError)):
        replace(payload(selection()), **mutation)


def test_frozen_payload_and_request_provenance_binding():
    source = selection()
    mission = payload(source)
    request = PreviewRequest(source, RequestId("request-1"))
    provenance = PreviewProvenance(source, datetime.now(timezone.utc), RecordPolicy.INDEPENDENT_MISSION)
    snapshot = PreviewSnapshot(request, ScreenState.READY, mission, provenance)
    assert snapshot.provenance is not None
    assert snapshot.provenance.authority is PreviewAuthority.LOCAL_VERIFIED_COPY
    assert snapshot.provenance.freshness is Freshness.UNKNOWN
    with pytest.raises(FrozenInstanceError):
        setattr(mission, "formation_count", 2)
    with pytest.raises((TypeError, ValueError)):
        replace(snapshot, payload=replace(mission, selection=selection()))
    with pytest.raises(ValueError):
        replace(snapshot, state=ScreenState.LOADING)
    with pytest.raises(ValueError):
        replace(provenance, freshness=Freshness.CURRENT)
    with pytest.raises(ValueError):
        replace(provenance, verified_at=datetime.now())
    failed = PreviewSnapshot(request, ScreenState.ERROR, failure=PreviewFailure.INTEGRITY)
    assert failed.payload is None and failed.provenance is None
    with pytest.raises(ValueError):
        replace(failed, payload=mission)


@pytest.mark.parametrize("alias", ["Pilot1", "career-01", "S-07", "M-02", "D-00"])
def test_only_closed_source_aliases_admitted(alias):
    with pytest.raises(ValueError):
        selection(alias)
