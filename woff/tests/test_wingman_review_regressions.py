"""Production-path regressions for the seven Issue #96 review findings."""

from __future__ import annotations

import json
import sqlite3

import pytest

from ..campaign_engine import CampaignEngine
from ..campaign_namespace import campaign_namespace_for_root
from ..database import DatabaseManager
from ..handler import FileProcessor
from ..ingestion.outcome import ProcessingReason, ProcessingStatus
from .test_dossier_transactions import _dossier_bytes, _stored_state, dossier_runtime
from .test_roster_identity import _ids, _import, _member, _roster
from .test_wingman_identity_evidence import _parse_single_wingman
from .test_wingman_identity_migration import _legacy_database


def _field(member, index, value):
    fields = member.split(";")
    fields[index] = value
    return ";".join(fields)


def _submit(runtime, members, *, generation=1, squadron="No. 56 Squadron"):
    _, processor, path = runtime
    path.write_bytes(
        _dossier_bytes(
            wingmen=tuple(members),
            squadron=squadron,
            decorations=(f"Synthetic Medal {generation};1917-04-01",),
        )
    )
    return processor.process(str(path), "modified")


@pytest.mark.parametrize(
    "change,kind,reason",
    [
        ("rename", "conflicting", "contradictory-stable-evidence"),
        ("partial", "conflicting", "contradictory-stable-evidence"),
        ("missing", "ambiguous", "insufficient-evidence"),
        ("duplicate", "ambiguous", "duplicate-incoming-evidence"),
    ],
)
def test_expected_identity_rejection_is_atomic_and_sanitized(
    dossier_runtime,
    caplog,
    change,
    kind,
    reason,
):
    db, _, _ = dossier_runtime
    assert _import(dossier_runtime, [_member("a"), _member("b")])
    original_ids = _ids(db)
    member_id = original_ids["Synthetic town a"]
    assert db.save_wingman_personality(
        member_id, _roster(dossier_runtime).pilot_id, {"personality_trait": "Steady"}
    )
    assert db.save_wingman_memory(
        member_id, "mission", "1917-04-01", "Synthetic memory"
    )
    original = list(db._get_conn().iterdump())
    changed = {
        "rename": _field(_member("a"), 1, "Jonathan"),
        "partial": _field(_member("a"), 25, "Changed town"),
        "missing": _field(_member("a"), 24, "Null"),
        "duplicate": _member("a"),
    }[change]
    # The first member update and decoration change must also roll back.
    members = [_member("b", "Wounded"), changed]
    if change == "duplicate":
        members.append(changed)
    caplog.clear()
    outcome = _submit(dossier_runtime, members)
    assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
    assert outcome.reason is ProcessingReason.IDENTITY_REJECTED
    assert outcome.retry_input is None and outcome.acknowledged_generation is None
    assert list(db._get_conn().iterdump()) == original
    assert _ids(db) == original_ids
    assert _stored_state(db)["diary"] == []
    diagnostics = [
        record
        for record in caplog.records
        if "Wingman identity rejected" in record.message
    ]
    assert len(diagnostics) == 1
    assert f"category={kind}" in diagnostics[0].message
    assert f"reason={reason}" in diagnostics[0].message
    assert not any(record.exc_info for record in caplog.records)
    assert all(
        token not in diagnostics[0].message
        for token in ("John", "Smith", "Jonathan", "town", "1891")
    )
    assert _submit(dossier_runtime, members) == outcome
    assert list(db._get_conn().iterdump()) == original


@pytest.fixture
def migrated_runtime(tmp_path):
    path = tmp_path / "Pilot1Dossier.txt"
    database_path = tmp_path / "legacy.sqlite"
    _legacy_database(database_path)
    with sqlite3.connect(database_path) as conn:
        conn.execute(
            "UPDATE pilots SET name='James Hartley', rank='Lieutenant', status='Active', squadron='Old Squadron', startDate='1917-04-06'"
        )
        conn.execute(
            "INSERT INTO pilot_slot_bindings VALUES (?, 1, 'pilot-96', 'old-generation', '1917-04-06')",
            (campaign_namespace_for_root(str(tmp_path)),),
        )
        conn.execute(
            "INSERT INTO meta VALUES ('dossier_roster:pilot-96', ?)",
            (
                json.dumps(
                    {
                        "version": 1,
                        "squadron": "Old Squadron",
                        "baseline_pending": False,
                        "wingmen": [["John", "Smith", "In Service"]],
                        "candidate": None,
                    }
                ),
            ),
        )
    db = DatabaseManager(str(database_path))
    processor = FileProcessor(
        db, CampaignEngine(db), stability_timeout=0.1, stability_interval=0.001
    )
    yield db, processor, path
    db.close()


@pytest.mark.parametrize("empty_transfer", [False, True])
def test_transfer_bypasses_legacy_candidates_and_retains_history(
    migrated_runtime, empty_transfer
):
    db, _, _ = migrated_runtime
    original_row = (
        db._get_conn()
        .execute("SELECT * FROM squad_members WHERE id='wingman-a'")
        .fetchone()
    )
    relationships = [
        db._get_conn().execute(f"SELECT * FROM {table}").fetchall()
        for table in ("wingmen_personalities", "wingmen_memory")
    ]
    if empty_transfer:
        assert _submit(
            migrated_runtime, [], squadron="New Squadron"
        ).acknowledged_generation
        assert _roster(migrated_runtime).roster_baseline_pending
        db.close()
    assert _submit(
        migrated_runtime,
        [_member("a"), _member("b")],
        generation=2,
        squadron="New Squadron",
    ).acknowledged_generation
    state = _roster(migrated_runtime)
    assert state.roster_squadron == "New Squadron" and not state.roster_baseline_pending
    new_ids = {member.wingman_id for member in state.wingmen}
    assert len(new_ids) == 2 and "wingman-a" not in new_ids
    assert len(db.get_wingmen_by_pilot("pilot-96")) == 3
    assert _stored_state(db)["diary"] == []
    committed = list(db._get_conn().iterdump())
    db.close()
    assert _submit(
        migrated_runtime,
        [_member("a"), _member("b")],
        generation=2,
        squadron="New Squadron",
    ).acknowledged_generation
    assert list(db._get_conn().iterdump()) == committed
    # A later digest must not reintroduce the retired legacy candidate.
    assert _submit(
        migrated_runtime,
        [_member("b"), _member("a")],
        generation=3,
        squadron="New Squadron",
    ).acknowledged_generation
    assert {
        member.wingman_id for member in _roster(migrated_runtime).wingmen
    } == new_ids
    assert _stored_state(db)["diary"] == []
    assert _submit(
        migrated_runtime, [_member("a")], generation=4, squadron="New Squadron"
    ).acknowledged_generation
    assert _roster(migrated_runtime).roster_candidate is not None
    assert _submit(
        migrated_runtime, [_member("a")], generation=5, squadron="New Squadron"
    ).acknowledged_generation
    assert len(_stored_state(db)["diary"]) == 1
    assert "Perdi o contacto" in _stored_state(db)["diary"][0][-1]
    assert (
        db._get_conn()
        .execute("SELECT * FROM squad_members WHERE id='wingman-a'")
        .fetchone()
        == original_row
    )
    assert [
        db._get_conn().execute(f"SELECT * FROM {table}").fetchall()
        for table in ("wingmen_personalities", "wingmen_memory")
    ] == relationships
    assert db._get_conn().execute("PRAGMA foreign_key_check").fetchall() == []


def test_same_squad_legacy_candidate_remains_ambiguous(migrated_runtime, caplog):
    db, _, _ = migrated_runtime
    before = list(db._get_conn().iterdump())
    outcome = _submit(migrated_runtime, [_member("a")], squadron="Old Squadron")
    assert outcome.reason is ProcessingReason.IDENTITY_REJECTED
    assert "incomplete-existing-candidate" in caplog.text
    assert not any(record.exc_info for record in caplog.records)
    assert list(db._get_conn().iterdump()) == before


@pytest.mark.parametrize(
    "biography,present",
    [
        ("Keeps a notebook and enjoys quiet evenings.", True),
        ("  Keeps a notebook.  ", True),
        ("", True),
        ("Null", False),
        ("nUlL", False),
        (None, False),
    ],
)
def test_biography_field_presence_and_exact_value(biography, present):
    record = _member("a")
    if biography is None:
        record = ";".join(record.split(";")[:19])
    else:
        record = _field(record, 19, biography)
    member = _parse_single_wingman(record)
    assert member.present_fields is not None
    assert ("bio" in member.present_fields) is present
    assert member.bio == (biography if present else "")


@pytest.mark.parametrize(
    "biography,expected",
    [
        (
            "Keeps a notebook and enjoys quiet evenings.",
            "Keeps a notebook and enjoys quiet evenings.",
        ),
        ("", ""),
        ("Null", "Reliable pilot."),
        ("nUlL", "Reliable pilot."),
    ],
)
def test_biography_merge_and_replay(dossier_runtime, biography, expected):
    db, _, _ = dossier_runtime
    assert _import(dossier_runtime, [_member("a")])
    ids = _ids(db)
    updated = _field(_member("a"), 19, biography)
    assert _submit(dossier_runtime, [updated]).acknowledged_generation
    assert db._get_conn().execute("SELECT bio FROM squad_members").fetchone() == (
        expected,
    )
    assert _ids(db) == ids
    before = list(db._get_conn().iterdump())
    assert _submit(dossier_runtime, [updated]).acknowledged_generation
    assert list(db._get_conn().iterdump()) == before


@pytest.mark.parametrize("reverse", [False, True])
def test_name_collision_inside_first_batch_cannot_create_identities(
    dossier_runtime, reverse
):
    db, _, _ = dossier_runtime
    before = list(db._get_conn().iterdump())
    members = [_member("a"), _field(_member("a"), 1, "Jonathan")]
    outcome = _submit(dossier_runtime, list(reversed(members)) if reverse else members)
    assert outcome.reason is ProcessingReason.IDENTITY_REJECTED
    assert list(db._get_conn().iterdump()) == before


def test_transfer_does_not_bypass_partially_supported_evidence(migrated_runtime):
    db, _, _ = migrated_runtime
    with db.transaction() as conn:
        conn.execute("UPDATE squad_members SET birthDate='1891-01-01'")
    before = list(db._get_conn().iterdump())
    outcome = _submit(migrated_runtime, [_member("a")], squadron="New Squadron")
    assert outcome.reason is ProcessingReason.IDENTITY_REJECTED
    assert list(db._get_conn().iterdump()) == before


def test_transfer_retirement_rolls_back_with_diary_failure(
    migrated_runtime, monkeypatch
):
    db, processor, path = migrated_runtime
    before = list(db._get_conn().iterdump())
    monkeypatch.setattr(db, "save_diary_entry", lambda **kwargs: False)
    path.write_bytes(
        _dossier_bytes(rank="Captain", wingmen=(_member("a"),), squadron="New Squadron")
    )
    outcome = processor.process(str(path), "modified")
    assert outcome.reason is ProcessingReason.PERSISTENCE_REJECTED
    assert list(db._get_conn().iterdump()) == before


def test_structurally_absent_biography_and_identity_cannot_erase_data(dossier_runtime):
    db, _, _ = dossier_runtime
    assert _import(dossier_runtime, [_member("a")])
    before = list(db._get_conn().iterdump())
    outcome = _submit(dossier_runtime, [";".join(_member("a").split(";")[:19])])
    assert outcome.reason is ProcessingReason.IDENTITY_REJECTED
    assert list(db._get_conn().iterdump()) == before


def test_programming_errors_still_use_unexpected_error_boundary(
    dossier_runtime, monkeypatch, caplog
):
    _, processor, _ = dossier_runtime

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic programming error")

    monkeypatch.setattr(processor.campaign_engine, "process_dossier_import", fail)
    outcome = _submit(dossier_runtime, [_member("a")])
    assert outcome.reason is ProcessingReason.UNEXPECTED_ERROR
    assert any(record.exc_info for record in caplog.records)


@pytest.mark.parametrize(
    "retired", [["unknown"], ["wingman-a", "wingman-a"], "wingman-a"]
)
def test_invalid_retirement_metadata_fails_closed(migrated_runtime, retired):
    db, _, _ = migrated_runtime
    with db.transaction() as conn:
        key, value = conn.execute(
            "SELECT key, value FROM meta WHERE key LIKE 'dossier_roster:%'"
        ).fetchone()
        payload = json.loads(value)
        payload["retired_wingman_ids"] = retired
        conn.execute("UPDATE meta SET value=? WHERE key=?", (json.dumps(payload), key))
    before = list(db._get_conn().iterdump())
    outcome = _submit(migrated_runtime, [_member("a")], squadron="New Squadron")
    assert outcome.reason is ProcessingReason.SQLITE_PERMANENT
    assert list(db._get_conn().iterdump()) == before


def test_transfer_cannot_bypass_complete_name_evidence_conflict(dossier_runtime):
    db, _, _ = dossier_runtime
    assert _import(dossier_runtime, [_member("a")])
    before = list(db._get_conn().iterdump())
    outcome = _submit(
        dossier_runtime, [_field(_member("a"), 1, "Jonathan")], squadron="New Squadron"
    )
    assert outcome.reason is ProcessingReason.IDENTITY_REJECTED
    assert list(db._get_conn().iterdump()) == before
