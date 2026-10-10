"""Required status regressions through the real Dossier processing boundary."""

from .dossier_support import complete_roster_domain

import pytest

from ..ingestion.outcome import ProcessingReason, ProcessingStatus
from .test_dossier_transactions import _stored_state
from .test_roster_identity import _ids, _import, _member, _roster
from .test_wingman_review_regressions import _submit


@pytest.mark.parametrize("status", ["", "   ", "\t"])
@pytest.mark.parametrize("short", [False, True])
@pytest.mark.parametrize("candidate", [False, True])
def test_empty_required_status_rejects_before_reconciliation(
    complete_roster_domain, status, short, candidate
):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    ids = _ids(db)
    assert db.save_wingman_personality(
        ids["Synthetic town a"],
        _roster(complete_roster_domain).pilot_id,
        {"personality_trait": "Steady"},
    )
    assert db.save_wingman_memory(
        ids["Synthetic town a"], "mission", "1917-04-01", "Synthetic"
    )
    if candidate:
        assert _import(complete_roster_domain, [_member("b")], generation=1)
        assert _roster(complete_roster_domain).roster_candidate is not None
    before = list(db._get_conn().iterdump())
    malformed = _member("a").split(";")
    malformed[5] = status
    if short:
        malformed = malformed[:6]
    changed = _member("b", "Wounded").split(";")
    changed[3], changed[11], changed[12] = "8", "99", "999"
    for generation in (2, 3):
        outcome = _submit(
            complete_roster_domain,
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
        complete_roster_domain, [_member("b"), _member("a")], generation=4
    ).acknowledged_generation
    assert _ids(db) == ids
    assert _stored_state(db)["diary"] == []
    assert _roster(complete_roster_domain).roster_candidate is None
    recovered = list(db._get_conn().iterdump())
    assert _submit(
        complete_roster_domain, [_member("b"), _member("a")], generation=4
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
    complete_roster_domain, status
):
    db, _, _ = complete_roster_domain
    assert _submit(complete_roster_domain, [_member("a", status)]).acknowledged_generation
    assert db.get_wingmen_by_pilot(_roster(complete_roster_domain).pilot_id) == [
        {"fName": "John", "sName": "Smith", "status": status}
    ]


@pytest.mark.parametrize("token", ["Null", "null", "NULL", " nUlL "])
def test_explicit_missing_status_token_still_preserves_stored_status(
    complete_roster_domain, token
):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a", "Wounded")])
    ids = _ids(db)
    assert _submit(
        complete_roster_domain, [_member("a", token)], generation=1
    ).acknowledged_generation
    assert _ids(db) == ids
    assert db.get_wingmen_by_pilot(_roster(complete_roster_domain).pilot_id) == [
        {"fName": "John", "sName": "Smith", "status": "Wounded"}
    ]
    assert _stored_state(db)["diary"] == []
