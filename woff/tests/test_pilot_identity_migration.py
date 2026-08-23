import sqlite3

import pytest

from ..database import DatabaseManager
from ..version import SCHEMA_VERSION


def _unique_index_columns(
    conn: sqlite3.Connection, table: str
) -> set[tuple[str, ...]]:
    result: set[tuple[str, ...]] = set()
    for row in conn.execute(f'PRAGMA index_list("{table}")'):
        if row[2]:
            result.add(
                tuple(
                    item[2]
                    for item in conn.execute(f'PRAGMA index_info("{row[1]}")')
                )
            )
    return result


def _downgrade_fixture_to_31(path) -> None:
    manager = DatabaseManager(str(path))
    manager.close()

    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DROP TABLE IF EXISTS pilot_slot_bindings")
        conn.execute("DROP INDEX IF EXISTS idx_pilots_name")
        conn.execute("DROP TABLE pilots")
        conn.execute(
            """
            CREATE TABLE pilots (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE,
                fName TEXT,
                sName TEXT,
                nation TEXT,
                rank TEXT,
                squadron TEXT,
                aircraft TEXT,
                aerodrome TEXT,
                sector TEXT,
                startDate TEXT,
                enlisted TEXT,
                status TEXT,
                notes TEXT,
                photo TEXT,
                birthDate TEXT,
                birthPlace TEXT,
                missions INTEGER,
                flminutes INTEGER,
                claimsCount INTEGER,
                killsCount INTEGER,
                skill INTEGER,
                reputation INTEGER,
                source_file TEXT,
                last_updated TEXT
            )
            """
        )
        conn.execute(
            "UPDATE meta SET value='3.1' WHERE key='schema_version'"
        )


def _seed_pilot(path, pilot_id: str, name: str, source_file: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO pilots (id, name, source_file) VALUES (?, ?, ?)",
            (pilot_id, name, source_file),
        )


def _seed_related_career(path, pilot_id: str, source_file: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "INSERT INTO pilots (id, name, source_file) VALUES (?, ?, ?)",
            (pilot_id, "Alice", source_file),
        )
        conn.execute(
            "INSERT INTO missions (id, pilotId) VALUES ('mission-a', ?)",
            (pilot_id,),
        )
        conn.execute(
            "INSERT INTO victories (id, pilotId) VALUES ('victory-a', ?)",
            (pilot_id,),
        )
        conn.execute(
            "INSERT INTO decorations (id, pilotId) VALUES ('decoration-a', ?)",
            (pilot_id,),
        )
        conn.execute(
            "INSERT INTO squad_members (id, pilotId) VALUES ('wingman-a', ?)",
            (pilot_id,),
        )
        conn.execute(
            "INSERT INTO pilot_rpg_stats (pilotId) VALUES (?)",
            (pilot_id,),
        )
        conn.execute(
            """
            INSERT INTO diary_entries (id, pilotId, missionId)
            VALUES ('diary-a', ?, 'mission-a')
            """,
            (pilot_id,),
        )


def _dump(path) -> str:
    with sqlite3.connect(path) as conn:
        return "\n".join(conn.iterdump())


def test_new_schema_allows_duplicate_names_and_has_slot_binding_contract(tmp_path):
    path = tmp_path / "identity.sqlite"
    manager = DatabaseManager(str(path))
    manager.close()

    with sqlite3.connect(path) as conn:
        assert SCHEMA_VERSION == "3.2"
        assert ("name",) not in _unique_index_columns(conn, "pilots")
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_pilots_name'"
        ).fetchone() == (1,)
        table_info = conn.execute(
            "PRAGMA table_info(pilot_slot_bindings)"
        ).fetchall()
        columns = {row[1]: row[2] for row in table_info}
        assert columns == {
            "slot": "INTEGER",
            "pilotId": "TEXT",
            "dossier_digest": "TEXT",
            "last_updated": "TEXT",
        }
        assert {row[1]: (row[3], row[5]) for row in table_info} == {
            "slot": (0, 1),
            "pilotId": (1, 0),
            "dossier_digest": (0, 0),
            "last_updated": (1, 0),
        }
        assert conn.execute(
            "PRAGMA foreign_key_list(pilot_slot_bindings)"
        ).fetchall()[0][2:5] == ("pilots", "pilotId", "id")
        binding_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='pilot_slot_bindings'"
        ).fetchone()[0]
        assert "CHECK(slot > 0)" in binding_sql


def test_schema_31_migration_preserves_ids_relationships_and_reopens(tmp_path):
    path = tmp_path / "legacy-31.sqlite"
    _downgrade_fixture_to_31(path)
    _seed_related_career(path, pilot_id="career-a", source_file="Pilot1Log.txt")

    manager = DatabaseManager(str(path))
    manager.close()
    reopened = DatabaseManager(str(path))
    reopened.close()

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT id FROM pilots").fetchall() == [("career-a",)]
        for table in (
            "missions",
            "victories",
            "decorations",
            "squad_members",
            "pilot_rpg_stats",
            "diary_entries",
        ):
            assert conn.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE pilotId=?',
                ("career-a",),
            ).fetchone() == (1,)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert conn.execute(
            "SELECT slot, pilotId, dossier_digest FROM pilot_slot_bindings"
        ).fetchall() == [(1, "career-a", None)]


def test_migration_leaves_ambiguous_legacy_slot_unbound_without_data_loss(tmp_path):
    path = tmp_path / "ambiguous.sqlite"
    _downgrade_fixture_to_31(path)
    _seed_pilot(path, "career-a", "Alice", "Pilot1Dossier.txt")
    _seed_pilot(path, "career-b", "Bob", "Pilot1Log.txt")

    manager = DatabaseManager(str(path))
    manager.close()

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT id FROM pilots ORDER BY id").fetchall() == [
            ("career-a",),
            ("career-b",),
        ]
        assert conn.execute("SELECT * FROM pilot_slot_bindings").fetchall() == []


def test_identity_schema_failure_restores_schema_31_backup(tmp_path, monkeypatch):
    path = tmp_path / "rollback.sqlite"
    _downgrade_fixture_to_31(path)
    _seed_related_career(path, "career-a", "Pilot1Dossier.txt")
    before = _dump(path)

    def fail_seed(self, cursor):
        raise RuntimeError("identity seed failed")

    monkeypatch.setattr(
        DatabaseManager,
        "_seed_unambiguous_slot_bindings",
        fail_seed,
        raising=False,
    )
    with pytest.raises(RuntimeError, match="identity seed failed"):
        DatabaseManager(str(path))

    assert _dump(path) == before
    assert list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
