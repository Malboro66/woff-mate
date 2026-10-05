from __future__ import annotations

from pathlib import Path

import pytest

from ..database import DatabaseManager
from ..identity import WingmanIdentityResolutionError, WingmanIdentityResolutionKind
from ..models import WoFFWingman


def _dossier_wingman(
    wingman_id: str,
    *,
    birth_date: str,
    evidence_date: str,
    location: str,
    rank: str = "Lieutenant",
    status: str = "In Service",
    skill: int = 4,
    morale: int = 5,
    missions: int = 12,
    flminutes: int = 720,
    bio: str = "Reliable pilot.",
    present_fields: frozenset[str] | None = None,
) -> WoFFWingman:
    return WoFFWingman(
        id=wingman_id,
        rank=rank,
        fName="John",
        sName="Smith",
        skill=skill,
        morale=morale,
        status=status,
        missions=missions,
        flminutes=flminutes,
        bio=bio,
        birthDate=birth_date,
        evidenceDate=evidence_date,
        evidenceLocation=location,
        present_fields=(
            present_fields
            if present_fields is not None
            else frozenset(
                {
                    "rank",
                    "skill",
                    "morale",
                    "status",
                    "missions",
                    "flminutes",
                    "bio",
                }
            )
        ),
    )


def _db(tmp_path: Path) -> DatabaseManager:
    db = DatabaseManager(str(tmp_path / "wingmen.sqlite"))
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO pilots (id, name) VALUES (?, ?)",
            ("pilot-96", "Synthetic Pilot"),
        )
    return db


def _rows(db: DatabaseManager):
    return db._get_conn().execute(
        """
        SELECT id, rank, fName, sName, skill, morale, status,
               missions, flminutes, bio, birthDate, evidenceDate,
               evidenceLocation
        FROM squad_members
        WHERE pilotId = ?
        ORDER BY id
        """,
        ("pilot-96",),
    ).fetchall()


def test_same_name_members_remain_distinct_and_replay_keeps_ids(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    first = _dossier_wingman(
        "wingman-a",
        birth_date="1896-08-08",
        evidence_date="1913-07-19",
        location="Arras",
    )
    second = _dossier_wingman(
        "wingman-b",
        birth_date="1895-07-25",
        evidence_date="1914-06-10",
        location="Privas",
    )
    with db.transaction():
        db._wingmen.upsert_wingmen_batch("pilot-96", [first, second])

    assert [row[0] for row in _rows(db)] == ["wingman-a", "wingman-b"]

    replay_a = _dossier_wingman(
        "generated-a",
        birth_date="1896-08-08",
        evidence_date="1913-07-19",
        location="Arras",
        rank="Captain",
        missions=22,
    )
    replay_b = _dossier_wingman(
        "generated-b",
        birth_date="1895-07-25",
        evidence_date="1914-06-10",
        location="Privas",
        status="On Leave",
        missions=19,
    )
    with db.transaction():
        db._wingmen.upsert_wingmen_batch("pilot-96", [replay_b, replay_a])

    assert replay_a.id == "wingman-a"
    assert replay_b.id == "wingman-b"
    assert [row[0] for row in _rows(db)] == ["wingman-a", "wingman-b"]


def test_sparse_replay_preserves_rich_values_but_explicit_zero_and_empty_write(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    original = _dossier_wingman(
        "wingman-a",
        birth_date="1896-08-08",
        evidence_date="1913-07-19",
        location="Arras",
        rank="Captain",
        status="In Service",
        skill=5,
        morale=4,
        missions=22,
        flminutes=8420,
        bio="Experienced observer and pilot.",
    )
    with db.transaction():
        db._wingmen.upsert_wingmen_batch("pilot-96", [original])

    sparse = _dossier_wingman(
        "generated-sparse",
        birth_date="1896-08-08",
        evidence_date="1913-07-19",
        location="Arras",
        rank="",
        status="On Leave",
        skill=0,
        morale=0,
        missions=0,
        flminutes=0,
        bio="",
        present_fields=frozenset({"status"}),
    )
    with db.transaction():
        db._wingmen.upsert_wingmen_batch("pilot-96", [sparse])

    row = _rows(db)[0]
    assert row[0] == "wingman-a"
    assert row[1] == "Captain"
    assert row[4] == 5
    assert row[5] == 4
    assert row[6] == "On Leave"
    assert row[7] == 22
    assert row[8] == 8420
    assert row[9] == "Experienced observer and pilot."

    explicit = _dossier_wingman(
        "generated-explicit",
        birth_date="1896-08-08",
        evidence_date="1913-07-19",
        location="Arras",
        status="",
        missions=0,
        flminutes=0,
        present_fields=frozenset({"status", "missions", "flminutes"}),
    )
    with db.transaction():
        db._wingmen.upsert_wingmen_batch("pilot-96", [explicit])

    row = _rows(db)[0]
    assert row[6] == ""
    assert row[7] == 0
    assert row[8] == 0
    assert row[1] == "Captain"
    assert row[9] == "Experienced observer and pilot."


def test_matched_replay_preserves_personality_and_memory_relationships(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    original = _dossier_wingman(
        "wingman-a",
        birth_date="1896-08-08",
        evidence_date="1913-07-19",
        location="Arras",
    )
    with db.transaction():
        db._wingmen.upsert_wingmen_batch("pilot-96", [original])
    assert db.save_wingman_personality(
        "wingman-a", "pilot-96", {"personality_trait": "Steady"}
    )
    assert db.save_wingman_memory(
        "wingman-a", "mission", "1916-01-01", "Synthetic event"
    )

    replay = _dossier_wingman(
        "generated-new-id",
        birth_date="1896-08-08",
        evidence_date="1913-07-19",
        location="Arras",
        status="On Leave",
    )
    with db.transaction():
        db._wingmen.upsert_wingmen_batch("pilot-96", [replay])

    assert replay.id == "wingman-a"
    assert db._get_conn().execute(
        "SELECT wingmanId FROM wingmen_personalities"
    ).fetchall() == [("wingman-a",)]
    assert db._get_conn().execute(
        "SELECT wingmanId FROM wingmen_memory"
    ).fetchall() == [("wingman-a",)]
    assert db._get_conn().execute("PRAGMA foreign_key_check").fetchall() == []


def test_ambiguous_legacy_same_name_fails_closed_without_mutation(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO squad_members (
                id, pilotId, rank, fName, sName, skill, morale, status,
                missions, flminutes, bio
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "legacy-a",
                "pilot-96",
                "Lieutenant",
                "John",
                "Smith",
                4,
                5,
                "In Service",
                12,
                720,
                "Legacy rich record",
            ),
        )

    incoming = _dossier_wingman(
        "incoming",
        birth_date="1896-08-08",
        evidence_date="1913-07-19",
        location="Arras",
        rank="Captain",
    )
    before = _rows(db)
    with pytest.raises(WingmanIdentityResolutionError) as exc:
        with db.transaction():
            db._wingmen.upsert_wingmen_batch("pilot-96", [incoming])

    assert exc.value.kind is WingmanIdentityResolutionKind.AMBIGUOUS
    assert exc.value.reason == "incomplete-existing-candidate"
    assert _rows(db) == before


def test_duplicate_incoming_identity_evidence_aborts_entire_batch(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    first = _dossier_wingman(
        "incoming-a",
        birth_date="1896-08-08",
        evidence_date="1913-07-19",
        location="Arras",
    )
    duplicate = _dossier_wingman(
        "incoming-b",
        birth_date="1896-08-08",
        evidence_date="1913-07-19",
        location="Arras",
    )

    with pytest.raises(WingmanIdentityResolutionError) as exc:
        with db.transaction():
            db._wingmen.upsert_wingmen_batch("pilot-96", [first, duplicate])

    assert exc.value.kind is WingmanIdentityResolutionKind.AMBIGUOUS
    assert exc.value.reason == "duplicate-incoming-evidence"
    assert _rows(db) == []
