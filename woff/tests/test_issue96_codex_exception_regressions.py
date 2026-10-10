"""Issue #96: targeted regressions for the one-time Codex review P1 findings.

Synthetic Dossiers only. Source names, structured positions and database
relationships are tested without committing any real WoFF career content.
"""

from __future__ import annotations

from .dossier_support import CompleteRosterDomainHarness

import json

from ..campaign_engine import CampaignEngine
from ..campaign_namespace import campaign_namespace_for_root
from ..handler import FileProcessor
from ..parsers.dossier_parser import DossierValidationStatus, WoFFDossierParser
from .test_dossier_parser import _encode_dossier
from .test_dossier_transactions import _dossier_bytes, dossier_runtime
from .test_issue96_observed_partial_roster import _member, _physical_lines


def _observed(*, second: bool = True, day: int = 10) -> bytes:
    lines = _physical_lines(second_pilot=second, day=day)
    # Align the synthetic owner/squadron with the established complete fixture.
    lines[3] = "Lieutenant"
    lines[4:6] = ["James", "Hartley"]
    lines[60] = "Active"
    lines[63] = _member("Flight Lieutenant", "Alex", "Able", kills=7)
    lines[83] = "No. 56 Squadron"
    return _encode_dossier(lines, "Pilot1Dossier.txt")


def _complete(*, second: bool = True) -> bytes:
    members = [_member("Flight Lieutenant", "Alex", "Able", kills=7)]
    if second:
        members.append(_member("Flight Lieutenant", "Blair", "Baker", kills=3))
    members.append(_member("2nd Lieutenant", "Casey", "Clark", observer=True))
    return _dossier_bytes(wingmen=tuple(members))


def _apply(runtime, data: bytes):
    _, processor, path = runtime
    path.write_bytes(data)
    return processor.process(str(path), "modified")


def _apply_complete(runtime, data: bytes):
    """Stipulated historical census through the real engine domain interface."""
    db, processor, path = runtime
    path.write_bytes(data)
    harness = CompleteRosterDomainHarness(db, processor.campaign_engine, stability_timeout=0.1, stability_interval=0.001)
    return harness.process(str(path), "modified")


def _state(runtime):
    db, _, path = runtime
    with db.transaction():
        state = db.load_dossier_state(
            "James Hartley", campaign_namespace_for_root(str(path.parent)), 1
        )
    assert state is not None
    return state


def _member_ids(db, pilot_id):
    return dict(db._get_conn().execute(
        "SELECT fName, id FROM squad_members WHERE pilotId = ?",
        (pilot_id,),
    ).fetchall())


def test_wrong_161_field_marker_is_rejected_not_upgraded_to_complete():
    for invalid_marker in ("159", "161", "Null", ""):
        lines = _physical_lines()
        lines[0] = invalid_marker
        parser = WoFFDossierParser()
        assert not parser.parse_bytes(
            _encode_dossier(lines, "Pilot1Dossier.txt"), "Pilot1Dossier.txt"
        )
        assert parser.validation_status is DossierValidationStatus.UNSUPPORTED_LAYOUT
        assert parser.wingmen == []


def test_bad_161_marker_keeps_database_exactly_unchanged(dossier_runtime):
    db, _, _ = dossier_runtime
    assert _apply(dossier_runtime, _observed()).acknowledged_generation
    before = list(db._get_conn().iterdump())
    lines = _physical_lines()
    lines[0] = "159"
    outcome = _apply(
        dossier_runtime,
        _encode_dossier(lines, "Pilot1Dossier.txt"),
    )
    assert outcome.acknowledged_generation is None
    assert list(db._get_conn().iterdump()) == before


def test_partial_observation_preserves_complete_baseline_and_history(
    dossier_runtime,
):
    db, _, _ = dossier_runtime
    assert _apply_complete(dossier_runtime, _complete()).acknowledged_generation
    before = _state(dossier_runtime)
    assert not before.roster_baseline_pending
    assert before.roster_candidate is None
    initial_ids = _member_ids(db, before.pilot_id)
    assert set(initial_ids) == {"Alex", "Blair", "Casey"}
    assert db.save_wingman_personality(
        initial_ids["Blair"], before.pilot_id, {"personality_trait": "Steady"}
    )
    assert db.save_wingman_memory(
        initial_ids["Blair"], "mission", "1917-04-01", "Synthetic memory"
    )
    roster_before = db._get_conn().execute(
        "SELECT value FROM meta WHERE key=?", ("dossier_roster:" + before.pilot_id,)
    ).fetchone()[0]
    assert _apply(dossier_runtime, _observed(second=False)).acknowledged_generation
    partial = _state(dossier_runtime)
    assert not partial.roster_baseline_pending
    assert partial.roster_candidate is None
    assert {w.wingman_id for w in partial.wingmen} == set(initial_ids.values())
    assert db._get_conn().execute(
        "SELECT value FROM meta WHERE key=?", ("dossier_roster:" + before.pilot_id,)
    ).fetchone()[0] == roster_before
    assert _member_ids(db, before.pilot_id) == initial_ids
    assert db.get_wingman_personality(initial_ids["Blair"]) is not None
    assert db._get_conn().execute(
        "SELECT wingmanId FROM wingmen_memory WHERE wingmanId=?",
        (initial_ids["Blair"],),
    ).fetchone() == (initial_ids["Blair"],)

    # Full[A,B,C] -> partial[A,C] -> full[A,C] -> full[A,B,C].
    # The partial observation must not turn B's reappearance into "new".
    assert _apply_complete(dossier_runtime, _complete(second=False)).acknowledged_generation
    candidate = _state(dossier_runtime)
    assert candidate.roster_candidate is not None
    assert _apply_complete(dossier_runtime, _complete(second=True)).acknowledged_generation
    after = _state(dossier_runtime)
    assert after.roster_candidate is None
    assert _member_ids(db, after.pilot_id) == initial_ids
    assert db._get_conn().execute(
        "SELECT COUNT(*) FROM diary_entries WHERE pilotId=?",
        (after.pilot_id,),
    ).fetchone()[0] == 0
    assert db._get_conn().execute("PRAGMA foreign_key_check").fetchall() == []
    assert db._get_conn().execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_same_digest_legacy_partial_upgrades_atomically_and_replays(
    dossier_runtime,
):
    db, _, path = dossier_runtime
    raw = _observed()
    assert _apply(dossier_runtime, raw).acknowledged_generation
    old = _state(dossier_runtime)
    old_ids = _member_ids(db, old.pilot_id)
    assert set(old_ids) == {"Alex", "Blair", "Casey"}
    assert db.save_wingman_personality(
        old_ids["Alex"], old.pilot_id, {"personality_trait": "Steady"}
    )
    assert db.save_wingman_memory(
        old_ids["Alex"], "mission", "1915-11-10", "Historical memory"
    )
    with db.transaction() as connection:
        # Exact-digest legacy 'complete' metadata and identity-less rows.
        # No database dump or WoFF file is changed outside this synthetic test.
        connection.execute(
            "DELETE FROM meta WHERE key = ?",
            ("dossier_partial_digest:" + old.pilot_id,),
        )
        connection.execute(
            "INSERT OR REPLACE INTO meta (key,value) VALUES (?,?)",
            (
                "dossier_roster:" + old.pilot_id,
                json.dumps({
                    "version": 1,
                    "squadron": "No. 56 Squadron",
                    "baseline_pending": False,
                    "wingmen": [
                        [name, surname, "In Service"] for name, surname in
                        (("Alex", "Able"), ("Blair", "Baker"), ("Casey", "Clark"))
                    ],
                    "candidate": None,
                }),
            ),
        )
        connection.execute(
            "UPDATE squad_members SET birthDate=NULL, evidenceDate=NULL, "
            "evidenceLocation=NULL WHERE pilotId=?",
            (old.pilot_id,),
        )
    migrated = _state(dossier_runtime)
    assert migrated.roster_format_version == 1
    assert not migrated.roster_baseline_pending
    # Reopen the processing boundary while keeping same source hash and bytes.
    processor = FileProcessor(
        db, CampaignEngine(db), stability_timeout=0.1, stability_interval=0.001
    )
    path.write_bytes(raw)
    first = processor.process(str(path), "modified")
    assert first.acknowledged_generation is not None
    upgraded = _state(dossier_runtime)
    assert upgraded.roster_baseline_pending
    assert upgraded.roster_candidate is None
    assert upgraded.roster_format_version == 2
    assert upgraded.retired_wingman_ids == set(old_ids.values())
    new_ids = _member_ids(db, old.pilot_id)
    # Multiple rows may share display names; query all IDs for owner.
    all_ids = {
        member_id for (member_id,) in db._get_conn().execute(
            "SELECT id FROM squad_members WHERE pilotId=?", (old.pilot_id,)
        )
    }
    assert set(old_ids.values()) <= all_ids
    assert len(all_ids) == 6
    assert db.get_wingman_personality(old_ids["Alex"]) is not None
    assert db._get_conn().execute(
        "SELECT wingmanId FROM wingmen_memory WHERE wingmanId=?",
        (old_ids["Alex"],),
    ).fetchone() == (old_ids["Alex"],)
    original_upgraded = list(db._get_conn().iterdump())
    second = processor.process(str(path), "modified")
    assert second.acknowledged_generation is not None
    assert list(db._get_conn().iterdump()) == original_upgraded
    assert _apply(dossier_runtime, _observed(day=11)).acknowledged_generation
    assert _state(dossier_runtime).roster_baseline_pending
    assert db._get_conn().execute("PRAGMA foreign_key_check").fetchall() == []
    assert db._get_conn().execute("PRAGMA integrity_check").fetchone() == ("ok",)
