"""Required status regressions through the real Dossier processing boundary."""

import pytest

from ..ingestion.outcome import ProcessingReason, ProcessingStatus
from .test_dossier_transactions import _stored_state, dossier_runtime
from .test_roster_identity import _ids, _import, _member, _roster
from .test_wingman_review_regressions import _submit


@pytest.mark.parametrize("status", ["", "   ", "\t"])
@pytest.mark.parametrize("short", [False, True])
@pytest.mark.parametrize("candidate", [False, True])
def test_empty_required_status_rejects_before_reconciliation(
    dossier_runtime, status, short, candidate
):
    db, _, _ = dossier_runtime
    assert _import(dossier_runtime, [_member("a"), _member("b")])
    ids = _ids(db)
    assert db.save_wingman_personality(
        ids["Synthetic town a"],
        _roster(dossier_runtime).pilot_id,
        {"personality_trait": "Steady"},
    )
    assert db.save_wingman_memory(
        ids["Synthetic town a"], "mission", "1917-04-01", "Synthetic"
    )
    if candidate:
        assert _import(dossier_runtime, [_member("b")], generation=1)
        assert _roster(dossier_runtime).roster_candidate is not None
    before = list(db._get_conn().iterdump())
    malformed = _member("a").split(";")
    malformed[5] = status
    if short:
        malformed = malformed[:6]
    changed = _member("b", "Wounded").split(";")
    changed[3], changed[11], changed[12] = "8", "99", "999"
    for generation in (2, 3):
        outcome = _submit(
            dossier_runtime,
            [";".join(changed), ";".join(malformed)],
            generation=generation,
        )
        assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
        assert outcome.reason is ProcessingReason.PARSER_REJECTED
        assert outcome.acknowledged_generation is None and outcome.retry_input is None
        # Every table, including candidate/trusted metadata and binding/digest,
        # remains unchanged. This also checks no partial status/statistics writes.
        assert list(db._get_conn().iterdump()) == before
        assert _ids(db) == ids
        assert _stored_state(db)["diary"] == []
    assert _submit(
        dossier_runtime, [_member("b"), _member("a")], generation=4
    ).acknowledged_generation
    assert _ids(db) == ids
    assert _stored_state(db)["diary"] == []
    assert _roster(dossier_runtime).roster_candidate is None
    recovered = list(db._get_conn().iterdump())
    assert _submit(
        dossier_runtime, [_member("b"), _member("a")], generation=4
    ).acknowledged_generation
    assert list(db._get_conn().iterdump()) == recovered


@pytest.mark.parametrize(
    "status",
    [
        "In Service",
        "On Leave",
        "Active",
        "Wounded",
        "KIA",
        "Missing",
        "Prisoner",
        "Retired",
        "Uncatalogued source status",
    ],
)
def test_nonempty_source_status_keeps_existing_open_text_contract(
    dossier_runtime, status
):
    db, _, _ = dossier_runtime
    assert _submit(dossier_runtime, [_member("a", status)]).acknowledged_generation
    assert db.get_wingmen_by_pilot(_roster(dossier_runtime).pilot_id) == [
        {"fName": "John", "sName": "Smith", "status": status}
    ]


@pytest.mark.parametrize("token", ["Null", "null", "NULL", " nUlL "])
def test_explicit_missing_status_token_still_preserves_stored_status(
    dossier_runtime, token
):
    db, _, _ = dossier_runtime
    assert _import(dossier_runtime, [_member("a", "Wounded")])
    ids = _ids(db)
    assert _submit(
        dossier_runtime, [_member("a", token)], generation=1
    ).acknowledged_generation
    assert _ids(db) == ids
    assert db.get_wingmen_by_pilot(_roster(dossier_runtime).pilot_id) == [
        {"fName": "John", "sName": "Smith", "status": "Wounded"}
    ]
    assert _stored_state(db)["diary"] == []
