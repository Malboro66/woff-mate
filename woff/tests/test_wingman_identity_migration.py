from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ..database import DatabaseManager
from ..version import SCHEMA_VERSION


_LEGACY_SQUAD_MEMBERS_DDL = """
CREATE TABLE squad_members (
    id TEXT PRIMARY KEY,
    pilotId TEXT,
    rank TEXT,
    fName TEXT,
    sName TEXT,
    skill INTEGER,
    morale INTEGER,
    status TEXT,
    missions INTEGER,
    flminutes INTEGER,
    bio TEXT,
    UNIQUE(pilotId, fName, sName),
    FOREIGN KEY(pilotId) REFERENCES pilots(id)
)
"""


def _legacy_database(path: Path) -> None:
    db = DatabaseManager(str(path))
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO pilots (id, name) VALUES (?, ?)",
            ("pilot-96", "Synthetic Pilot"),
        )
    db.close()

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DROP INDEX IF EXISTS idx_squad_members_pilot")
        conn.execute("DROP TABLE squad_members")
        conn.execute(_LEGACY_SQUAD_MEMBERS_DDL)
        conn.execute(
            """
            INSERT INTO squad_members (
                id, pilotId, rank, fName, sName, skill, morale,
                status, missions, flminutes, bio
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "wingman-a",
                "pilot-96",
                "Lieutenant",
                "John",
                "Smith",
                4,
                5,
                "In Service",
                12,
                720,
                "Reliable pilot.",
            ),
        )
        conn.execute(
            """
            INSERT INTO wingmen_personalities (
                wingmanId, pilotId, aerial_skill, aggression, charisma,
                intelligence, physicality, professionalism, personality_trait
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            ("wingman-a", "pilot-96", 70, 50, 45, 65, 55, 80, "Steady"),
        )
        conn.execute(
            """
            INSERT INTO wingmen_memory (
                id, wingmanId, event_type, event_date, description,
                impact_morale, impact_stress
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                "memory-a",
                "wingman-a",
                "mission",
                "1916-01-01",
                "Synthetic event",
                1,
                0,
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        conn.commit()
    finally:
        conn.close()


def _unique_columns(conn: sqlite3.Connection, table: str) -> set[tuple[str, ...]]:
    result: set[tuple[str, ...]] = set()
    for index in conn.execute(f"PRAGMA index_list({table})").fetchall():
        if not index[2]:
            continue
        result.add(
            tuple(
                str(row[2])
                for row in conn.execute(
                    f"PRAGMA index_info({index[1]})"
                ).fetchall()
            )
        )
    return result


def test_wingman_identity_migration_preserves_ids_relationships_and_reopens(
    tmp_path: Path,
) -> None:
    path = tmp_path / "wingman-identity.sqlite"
    _legacy_database(path)

    migrated = DatabaseManager(str(path))
    migrated.close()

    conn = sqlite3.connect(path)
    try:
        columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(squad_members)")
        }
        assert {"birthDate", "evidenceDate", "evidenceLocation"}.issubset(columns)
        assert ("pilotId", "fName", "sName") not in _unique_columns(
            conn, "squad_members"
        )
        assert conn.execute(
            "SELECT birthDate, evidenceDate, evidenceLocation FROM squad_members "
            "WHERE id='wingman-a'"
        ).fetchone() == (None, None, None)
        assert conn.execute(
            "SELECT wingmanId FROM wingmen_personalities"
        ).fetchall() == [("wingman-a",)]
        assert conn.execute(
            "SELECT wingmanId FROM wingmen_memory"
        ).fetchall() == [("wingman-a",)]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)

        conn.execute(
            """
            INSERT INTO squad_members (
                id, pilotId, fName, sName, birthDate,
                evidenceDate, evidenceLocation
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                "wingman-b",
                "pilot-96",
                "John",
                "Smith",
                "1895-07-25",
                "1914-06-10",
                "Privas",
            ),
        )
        conn.commit()
        assert conn.execute(
            "SELECT COUNT(*) FROM squad_members WHERE pilotId=? AND fName=? AND sName=?",
            ("pilot-96", "John", "Smith"),
        ).fetchone() == (2,)
    finally:
        conn.close()

    reopened = DatabaseManager(str(path))
    reopened.close()
    backups = list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    assert backups


def test_wingman_identity_migration_failure_restores_original_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "wingman-rollback.sqlite"
    _legacy_database(path)

    before = sqlite3.connect(path).iterdump()
    before_dump = "\n".join(before)

    original = DatabaseManager._migrate_wingman_identity_schema

    def fail_after_migration(self, cursor):
        original(self, cursor)
        raise RuntimeError("synthetic migration failure")

    monkeypatch.setattr(
        DatabaseManager,
        "_migrate_wingman_identity_schema",
        fail_after_migration,
    )

    with pytest.raises(RuntimeError, match="synthetic migration failure"):
        DatabaseManager(str(path))

    after_conn = sqlite3.connect(path)
    try:
        after_dump = "\n".join(after_conn.iterdump())
        assert after_dump == before_dump
        assert ("pilotId", "fName", "sName") in _unique_columns(
            after_conn, "squad_members"
        )
        assert after_conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    finally:
        after_conn.close()

    backups = list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    assert backups
