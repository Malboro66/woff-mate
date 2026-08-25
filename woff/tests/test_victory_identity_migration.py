from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest

from ..database import DatabaseManager
from ..version import SCHEMA_VERSION


_LEGACY_VICTORIES_DDL = """
CREATE TABLE victories (
    id TEXT PRIMARY KEY,
    pilotId TEXT,
    date TEXT,
    time TEXT,
    missionId TEXT,
    enemyType TEXT,
    victoryType TEXT,
    location TEXT,
    confirmed INTEGER,
    witnesses TEXT,
    notes TEXT,
    sector TEXT,
    aircraft TEXT,
    source_file TEXT,
    UNIQUE(pilotId, date, time, enemyType),
    FOREIGN KEY(pilotId) REFERENCES pilots(id)
)
"""


def _create_schema_33_database(path) -> None:
    database = DatabaseManager(str(path))
    with database.transaction():
        connection = database._get_conn()
        connection.execute(
            "INSERT INTO pilots (id, name) VALUES ('pilot-a', 'Pilot A')"
        )
        connection.execute(
            """
            INSERT INTO missions (
                id, pilotId, date, time, missionType, aircraft, claimsCount
            ) VALUES (
                'mission-a', 'pilot-a', '1917-04-06', '10:00',
                'Patrol', 'SE.5a', 1
            )
            """
        )
        connection.execute(
            """
            INSERT INTO victories (
                id, pilotId, date, time, missionId, enemyType,
                victoryType, location, confirmed, witnesses, notes,
                sector, aircraft, source_file
            ) VALUES (
                'victory-a', 'pilot-a', '1917-04-06', '10:35',
                'mission-a', 'Albatros D.III', 'Destroyed', 'Arras',
                1, 'Wingman One', 'Sanitized note', 'Arras', 'SE.5a',
                'Pilot1Claims.txt'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO decorations (
                id, pilotId, name, date, citation, source_file
            ) VALUES (
                'decoration-a', 'pilot-a', 'Military Cross',
                '1917-04-15', 'Sanitized citation', 'career.xml'
            )
            """
        )
    database.close()

    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DROP TABLE victory_source_records")
        connection.execute("ALTER TABLE victories RENAME TO victories_current")
        connection.execute(_LEGACY_VICTORIES_DDL)
        columns = (
            "id, pilotId, date, time, missionId, enemyType, victoryType, "
            "location, confirmed, witnesses, notes, sector, aircraft, source_file"
        )
        connection.execute(
            f"INSERT INTO victories ({columns}) SELECT {columns} FROM victories_current"
        )
        connection.execute("DROP TABLE victories_current")
        connection.execute(
            "UPDATE meta SET value='3.3' WHERE key='schema_version'"
        )
        connection.commit()


def _stored_rows(path):
    with closing(sqlite3.connect(path)) as connection:
        return {
            "victories": connection.execute(
                """
                SELECT id, pilotId, date, time, missionId, enemyType,
                       victoryType, location, confirmed, witnesses, notes,
                       sector, aircraft, source_file
                FROM victories ORDER BY id
                """
            ).fetchall(),
            "decorations": connection.execute(
                """
                SELECT id, pilotId, name, date, citation, source_file
                FROM decorations ORDER BY id
                """
            ).fetchall(),
        }


def _has_legacy_unique(connection: sqlite3.Connection) -> bool:
    for index in connection.execute("PRAGMA index_list(victories)").fetchall():
        if not index[2]:
            continue
        columns = tuple(
            row[2]
            for row in connection.execute(
                f'PRAGMA index_info("{index[1]}")'
            ).fetchall()
        )
        if columns == ("pilotId", "date", "time", "enemyType"):
            return True
    return False


def test_schema_34_migrates_victory_identity_without_row_or_relationship_loss(
    tmp_path,
):
    path = tmp_path / "campaign.sqlite"
    _create_schema_33_database(path)
    before = _stored_rows(path)

    database = DatabaseManager(str(path))
    backup = database._migration_backup_path
    assert SCHEMA_VERSION == "3.4"
    assert backup is not None and backup.exists()
    assert _stored_rows(path) == before
    connection = database._get_conn()
    assert not _has_legacy_unique(connection)
    assert connection.execute(
        "SELECT COUNT(*) FROM victory_source_records"
    ).fetchone() == (0,)
    assert {
        row[1]: (row[2], row[3], row[5])
        for row in connection.execute(
            "PRAGMA table_info(victory_source_records)"
        ).fetchall()
    } == {
        "pilotId": ("TEXT", 1, 1),
        "source_record_key": ("TEXT", 1, 2),
        "victoryId": ("TEXT", 1, 0),
    }
    assert {
        (row[3], row[2], row[4])
        for row in connection.execute(
            "PRAGMA foreign_key_list(victory_source_records)"
        ).fetchall()
    } == {
        ("pilotId", "pilots", "id"),
        ("victoryId", "victories", "id"),
    }
    assert connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' "
        "AND name='idx_victory_source_records_victory'"
    ).fetchone() == (1,)
    victory_indexes = {
        str(row[1]): row
        for row in connection.execute("PRAGMA index_list(victories)").fetchall()
    }
    pilot_index = victory_indexes["idx_victories_pilot"]
    assert not pilot_index[2] and not pilot_index[4]
    assert tuple(
        str(row[2])
        for row in connection.execute(
            "PRAGMA index_info(idx_victories_pilot)"
        ).fetchall()
    ) == ("pilotId",)
    assert any(
        "USING INDEX idx_victories_pilot" in str(row[3])
        for row in connection.execute(
            "EXPLAIN QUERY PLAN SELECT id, date, time "
            "FROM victories WHERE pilotId=?",
            ("pilot-a",),
        ).fetchall()
    )
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    with database.transaction():
        connection.execute(
            """
            INSERT INTO victories (
                id, pilotId, date, time, missionId, enemyType
            ) VALUES (
                'victory-b', 'pilot-a', '1917-04-06', '10:35',
                'mission-a', 'Albatros D.III'
            )
            """
        )
    assert connection.execute(
        "SELECT id FROM victories ORDER BY id"
    ).fetchall() == [("victory-a",), ("victory-b",)]
    database.close()

    reopened = DatabaseManager(str(path))
    assert reopened._get_conn().execute(
        "SELECT value FROM meta WHERE key='schema_version'"
    ).fetchone() == ("3.4",)
    assert reopened._get_conn().execute(
        "PRAGMA foreign_key_check"
    ).fetchall() == []
    reopened.close()

    with closing(sqlite3.connect(backup)) as backup_connection:
        assert backup_connection.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone() == ("3.3",)
        assert _has_legacy_unique(backup_connection)


def test_schema_34_repairs_missing_victory_pilot_index_with_backup(tmp_path):
    path = tmp_path / "missing-pilot-index.sqlite"
    database = DatabaseManager(str(path))
    database.close()

    with closing(sqlite3.connect(path)) as connection:
        connection.execute("DROP INDEX idx_victories_pilot")
        connection.commit()

    repaired = DatabaseManager(str(path))
    backup = repaired._migration_backup_path
    assert backup is not None and backup.exists()
    assert repaired._get_conn().execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' "
        "AND name='idx_victories_pilot'"
    ).fetchone() == (1,)
    repaired.close()

    with closing(sqlite3.connect(backup)) as backup_connection:
        assert backup_connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' "
            "AND name='idx_victories_pilot'"
        ).fetchone() is None


def test_victory_identity_migration_failure_restores_verified_backup(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "rollback.sqlite"
    _create_schema_33_database(path)
    before = _stored_rows(path)
    original = DatabaseManager._migrate_victory_identity_schema

    def fail_after_rebuild(self, cursor):
        original(self, cursor)
        raise RuntimeError("forced victory identity migration failure")

    monkeypatch.setattr(
        DatabaseManager, "_migrate_victory_identity_schema", fail_after_rebuild
    )
    with pytest.raises(
        RuntimeError, match="forced victory identity migration failure"
    ):
        DatabaseManager(str(path))

    assert _stored_rows(path) == before
    with closing(sqlite3.connect(path)) as restored:
        assert restored.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone() == ("3.3",)
        assert _has_legacy_unique(restored)
        assert restored.execute("PRAGMA foreign_key_check").fetchall() == []
        assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    backups = list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    assert len(backups) == 1 and backups[0].exists()
    monkeypatch.setattr(
        DatabaseManager, "_migrate_victory_identity_schema", original
    )
    recovered = DatabaseManager(str(path))
    assert _stored_rows(path) == before
    recovered.close()
