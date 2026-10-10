"""Issue #96: synthetic Dossier generations retain homonymous identities."""

from __future__ import annotations

from .dossier_support import complete_roster_domain

import json

import pytest

from ..campaign_namespace import campaign_namespace_for_root
from .test_dossier_transactions import (
    _dossier_bytes,
    _process,
    _stored_state,
    _wingman,
)


def _member(label: str, status: str = "In Service") -> str:
    fields = _wingman("John", "Smith", status=status).split(";")
    # Distinct supported evidence; mutable fields and names deliberately coincide.
    n = {"a": 1, "b": 2, "c": 3}[label]
    fields[16:19] = [str(n), str(n), str(1890 + n)]
    fields[24:26] = [f"{n}/{n}/191{n}", f"Synthetic town {label}"]
    return ";".join(fields)


def _import(runtime, members, *, generation=0, squadron="No. 56 Squadron"):
    _, processor, path = runtime
    return _process(
        processor,
        path,
        _dossier_bytes(
            wingmen=tuple(members),
            squadron=squadron,
            decorations=(f"Synthetic Medal {generation};1917-04-01",),
        ),
        "modified",
    )


def _ids(db):
    return dict(
        db._get_conn()
        .execute("SELECT evidenceLocation, id FROM squad_members")
        .fetchall()
    )


def _roster(runtime):
    db, _, path = runtime
    with db.transaction():
        state = db.load_dossier_state(
            "James Hartley",
            campaign_namespace_for_root(str(path.parent)),
            1,
        )
    assert state is not None
    return state


@pytest.mark.parametrize("status,event", [("Wounded", "ferido"), ("KIA", "abatido")])
def test_homonym_status_changes_only_one_member(complete_roster_domain, status, event):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")]) is not None
    before = _ids(db)
    assert len(before) == 2
    assert _import(complete_roster_domain, [_member("a", status), _member("b")]) is not None
    assert _ids(db) == before
    diary = _stored_state(db)["diary"]
    assert len(diary) == 1
    assert event in diary[0][-1]


@pytest.fixture
def emitted_events(monkeypatch):
    from ..campaign_engine import CampaignEngine

    original = CampaignEngine._wingman_events
    events = []

    def observe(old, new):
        result = original(old, new)
        events.extend((kind, member.wingman_id) for kind, member in result)
        return result

    monkeypatch.setattr(CampaignEngine, "_wingman_events", staticmethod(observe))
    return events


def _payload(db):
    return json.loads(
        db._get_conn()
        .execute("SELECT value FROM meta WHERE key LIKE 'dossier_roster:%'")
        .fetchone()[0]
    )


def _set_payload(db, payload):
    with db.transaction() as conn:
        conn.execute(
            "UPDATE meta SET value = ? WHERE key LIKE 'dossier_roster:%'",
            (json.dumps(payload),),
        )


@pytest.mark.parametrize(
    "label,status,kind",
    [
        ("a", "Wounded", "wounded"),
        ("b", "Wounded", "wounded"),
        ("a", "KIA", "kia"),
        ("b", "KIA", "kia"),
    ],
)
def test_status_event_carries_only_changed_persistent_identity(
    complete_roster_domain,
    emitted_events,
    label,
    status,
    kind,
):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    ids = _ids(db)
    assert _import(
        complete_roster_domain,
        [
            _member("b", status if label == "b" else "In Service"),
            _member("a", status if label == "a" else "In Service"),
        ],
    )
    assert emitted_events == [(kind, ids[f"Synthetic town {label}"])]
    state = _roster(complete_roster_domain)
    assert {w.wingman_id for w in state.wingmen} == set(ids.values())
    assert {w.wingman_id: w.status for w in state.wingmen} == {
        ids[f"Synthetic town {key}"]: status if key == label else "In Service"
        for key in ("a", "b")
    }


def test_homonym_absence_needs_distinct_generation_confirmation_and_replays_once(
    complete_roster_domain,
    emitted_events,
):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    ids = _ids(db)
    assert _import(complete_roster_domain, [_member("a")], generation=1)
    assert not _stored_state(db)["diary"]
    candidate_state = _roster(complete_roster_domain)
    assert {w.wingman_id for w in candidate_state.wingmen} == set(ids.values())
    assert candidate_state.roster_candidate is not None
    assert [w.wingman_id for w in candidate_state.roster_candidate.wingmen] == [
        ids["Synthetic town a"]
    ]
    snapshot = _stored_state(db)
    # Replaying a digest cannot supply an independent confirmation.
    assert _import(complete_roster_domain, [_member("a")], generation=1)
    assert _stored_state(db) == snapshot
    emitted_events.clear()
    assert _import(complete_roster_domain, [_member("a")], generation=2)
    assert emitted_events == [("missing", ids["Synthetic town b"])]
    assert len(_stored_state(db)["diary"]) == 1
    assert "Perdi o contacto" in _stored_state(db)["diary"][0][-1]
    assert _roster(complete_roster_domain).roster_candidate is None
    committed = _stored_state(db)
    assert _import(complete_roster_domain, [_member("a")], generation=2)
    assert _stored_state(db) == committed
    # Even a later digest with the same roster cannot repeat disappearance.
    assert _import(complete_roster_domain, [_member("a")], generation=3)
    assert _stored_state(db)["diary"] == committed["diary"]
    assert _ids(db) == ids  # Historical rows are retained.


def test_third_homonym_arrival_and_order_changes_are_idempotent(
    complete_roster_domain,
    emitted_events,
):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    baseline = _payload(db)
    assert baseline["version"] == 2
    assert len(baseline["wingmen"]) == 2
    assert _import(complete_roster_domain, [_member("b"), _member("a")])
    assert _payload(db) == baseline
    assert emitted_events == []
    assert _import(complete_roster_domain, [_member("b"), _member("c"), _member("a")])
    ids = _ids(db)
    assert emitted_events == [("new", ids["Synthetic town c"])]
    assert len(_roster(complete_roster_domain).wingmen) == 3
    diary = _stored_state(db)["diary"]
    assert len(diary) == 1 and "novo elemento" in diary[0][-1]
    assert _import(complete_roster_domain, [_member("b"), _member("c"), _member("a")])
    assert _import(complete_roster_domain, [_member("a"), _member("b"), _member("c")])
    assert _ids(db) == ids
    assert _stored_state(db)["diary"] == diary


def test_same_name_candidate_does_not_confirm_different_identity(
    complete_roster_domain,
    emitted_events,
):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    ids = _ids(db)
    assert _import(complete_roster_domain, [_member("a")], generation=1)
    assert _import(complete_roster_domain, [_member("b")], generation=2)
    assert not _stored_state(db)["diary"]
    candidate = _roster(complete_roster_domain).roster_candidate
    assert candidate is not None
    assert [w.wingman_id for w in candidate.wingmen] == [ids["Synthetic town b"]]
    emitted_events.clear()
    assert _import(complete_roster_domain, [_member("b")], generation=3)
    assert emitted_events == [("missing", ids["Synthetic town a"])]
    assert len(_stored_state(db)["diary"]) == 1


def test_combined_homonym_replacement_confirms_missing_and_new_by_id(
    complete_roster_domain,
    emitted_events,
):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    ids = _ids(db)
    assert _import(complete_roster_domain, [_member("c"), _member("a")], generation=1)
    assert not _stored_state(db)["diary"]
    emitted_events.clear()
    assert _import(complete_roster_domain, [_member("a"), _member("c")], generation=2)
    assert emitted_events == [
        ("missing", ids["Synthetic town b"]),
        ("new", _ids(db)["Synthetic town c"]),
    ]
    assert len(_stored_state(db)["diary"]) == 2


@pytest.mark.parametrize("empty_transfer", [False, True])
def test_transfer_rebaselines_homonyms_without_false_events(
    complete_roster_domain,
    empty_transfer,
):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    # Exercise transfer while a same-squadron absence awaits confirmation.
    assert _import(complete_roster_domain, [_member("a")], generation=1)
    if empty_transfer:
        assert _import(complete_roster_domain, [], generation=2, squadron="No. 60 Squadron")
        assert _roster(complete_roster_domain).roster_baseline_pending
    assert _import(
        complete_roster_domain, [_member("c")], generation=3, squadron="No. 60 Squadron"
    )
    state = _roster(complete_roster_domain)
    assert state.roster_squadron == "No. 60 Squadron"
    assert not state.roster_baseline_pending
    assert state.roster_candidate is None
    assert [w.wingman_id for w in state.wingmen] == [_ids(db)["Synthetic town c"]]
    assert not _stored_state(db)["diary"]


@pytest.mark.parametrize("legacy_count", [1, 2])
@pytest.mark.parametrize("candidate", [False, True])
def test_trusted_legacy_names_never_resolve_homonyms(
    complete_roster_domain,
    legacy_count,
    candidate,
):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    payload = _payload(db)
    payload["version"] = 1
    payload["wingmen"] = [["John", "Smith", "In Service"]] * legacy_count
    if candidate:
        payload["candidate"] = {
            "squadron": payload["squadron"],
            "wingmen": payload["wingmen"][:1],
        }
    _set_payload(db, payload)
    state = _roster(complete_roster_domain)
    assert all(w.wingman_id is None for w in state.wingmen)
    before = _stored_state(db)
    assert _import(complete_roster_domain, [_member("a", "KIA")], generation=1) is None
    assert _stored_state(db) == before
    # Explicit transfer legitimately starts a different baseline, no legacy matching.
    assert _import(
        complete_roster_domain, [_member("c")], generation=2, squadron="No. 60 Squadron"
    )
    assert _payload(db)["version"] == 2
    assert not _stored_state(db)["diary"]


def test_legacy_empty_pending_baseline_upgrades_without_name_matching(complete_roster_domain):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    payload = _payload(db)
    payload.update(version=1, wingmen=[], baseline_pending=True)
    _set_payload(db, payload)
    assert _import(complete_roster_domain, [_member("b"), _member("a")], generation=1)
    assert _payload(db)["version"] == 2
    assert not _stored_state(db)["diary"]


@pytest.mark.parametrize(
    "corruption", ["duplicate", "unknown", "empty", "foreign", "candidate"]
)
def test_invalid_v2_identity_fails_without_mutation(complete_roster_domain, corruption):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    payload = _payload(db)
    if corruption == "duplicate":
        payload["wingmen"][1][0] = payload["wingmen"][0][0]
    elif corruption == "candidate":
        payload["candidate"] = {
            "squadron": payload["squadron"],
            "wingmen": [["unknown", "John", "Smith", "In Service"]],
        }
    else:
        if corruption == "foreign":
            with db.transaction() as conn:
                conn.execute("INSERT INTO pilots (id, name) VALUES ('other', 'Other')")
                conn.execute(
                    "INSERT INTO squad_members (id, pilotId) VALUES ('foreign', 'other')"
                )
        payload["wingmen"][0][0] = "" if corruption == "empty" else corruption
    _set_payload(db, payload)
    before = _stored_state(db)
    assert _import(complete_roster_domain, [_member("a", "Wounded"), _member("b")]) is None
    assert _stored_state(db) == before


def test_homonym_personality_memory_and_roster_ids_survive_reopen(complete_roster_domain):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    ids = _ids(db)
    pilot_id = _roster(complete_roster_domain).pilot_id
    for label in ("a", "b"):
        member_id = ids[f"Synthetic town {label}"]
        assert db.save_wingman_personality(
            member_id, pilot_id, {"personality_trait": label}
        )
        assert db.save_wingman_memory(member_id, "mission", "1917-04-01", label)
    assert _import(complete_roster_domain, [_member("b"), _member("a", "Wounded")])
    snapshot = _stored_state(db)
    db.close()
    assert _import(complete_roster_domain, [_member("b"), _member("a", "Wounded")])
    assert _stored_state(db) == snapshot
    assert _ids(db) == ids
    assert {w.wingman_id for w in _roster(complete_roster_domain).wingmen} == set(ids.values())
    conn = db._get_conn()
    assert dict(
        conn.execute("SELECT wingmanId, personality_trait FROM wingmen_personalities")
    ) == {ids[f"Synthetic town {label}"]: label for label in ("a", "b")}
    assert dict(conn.execute("SELECT wingmanId, description FROM wingmen_memory")) == {
        ids[f"Synthetic town {label}"]: label for label in ("a", "b")
    }
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_sparse_status_uses_effective_persisted_value(complete_roster_domain):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a", "Wounded"), _member("b")])
    fields = _member("a").split(";")
    fields[5] = "Null"  # Absent status must not erase the trusted wounded value.
    assert _import(complete_roster_domain, [";".join(fields), _member("b")], generation=1)
    ids = _ids(db)
    assert {w.wingman_id: w.status for w in _roster(complete_roster_domain).wingmen}[
        ids["Synthetic town a"]
    ] == "Wounded"
    assert _import(
        complete_roster_domain, [_member("a", "Wounded"), _member("b")], generation=2
    )
    assert not _stored_state(db)["diary"]


def test_two_homonyms_with_same_transition_each_produce_an_event(
    complete_roster_domain, emitted_events
):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    ids = _ids(db)
    assert _import(complete_roster_domain, [_member("a", "Wounded"), _member("b", "Wounded")])
    assert set(emitted_events) == {("wounded", member_id) for member_id in ids.values()}
    assert len(_stored_state(db)["diary"]) == 2
    assert _import(complete_roster_domain, [_member("b", "Wounded"), _member("a", "Wounded")])
    assert len(_stored_state(db)["diary"]) == 2


def test_ambiguous_homonym_input_rolls_back_events_and_trusted_roster(complete_roster_domain):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    before = _stored_state(db)
    sparse = _member("b").split(";")
    sparse[24] = "Null"
    assert _import(complete_roster_domain, [_member("a", "Wounded"), ";".join(sparse)]) is None
    assert _stored_state(db) == before


def test_compatibility_event_api_rejects_unresolved_dossier_ids(complete_roster_domain):
    from ..parsers.dossier_parser import WoFFDossierParser

    db, processor, path = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    parser = WoFFDossierParser()
    parser.parse_bytes(
        _dossier_bytes(wingmen=(_member("a", "Wounded"), _member("b"))), path.name
    )
    pilot_id = _roster(complete_roster_domain).pilot_id
    assert (
        processor.campaign_engine.process_wingmen_changes(pilot_id, parser.wingmen)
        is False
    )
    assert not _stored_state(db)["diary"]
