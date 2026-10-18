"""Issue #77: canonical nullability and default schema certification."""
import sqlite3

import pytest

from ..database import DatabaseManager, SchemaCompatibilityError


def _clean_database(tmp_path):
    db_path = tmp_path / "schema77.sqlite"
    db = DatabaseManager(str(db_path))
    db.close()
    return db_path


def _rebuild_empty_table(db_path, table, before, after):
    with sqlite3.connect(db_path) as conn:
        create_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        assert create_sql.count(before) == 1, (table, before, create_sql)
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(f'DROP TABLE "{table}"')
        conn.execute(create_sql.replace(before, after, 1))
        if table == "diary_entries":
            conn.execute(
                "CREATE UNIQUE INDEX idx_diary_unique_mission "
                "ON diary_entries(pilotId, missionId) WHERE missionId IS NOT NULL"
            )
        conn.commit()


@pytest.mark.parametrize(
    ("table", "before", "after", "message"),
    [
        ("diary_entries", "pilotId TEXT NOT NULL", "pilotId TEXT",
         "diary_entries.pilotId"),
        ("pilot_rpg_stats", "fatigue INTEGER DEFAULT 0",
         "fatigue INTEGER DEFAULT 9", "pilot_rpg_stats.fatigue"),
        ("wingmen_personalities", "aggression INTEGER DEFAULT 50",
         "aggression INTEGER DEFAULT 51", "wingmen_personalities.aggression"),
        ("wingmen_memory", "impact_stress INTEGER DEFAULT 0",
         "impact_stress INTEGER", "wingmen_memory.impact_stress"),
        ("pilots", "status TEXT", "status TEXT DEFAULT 'Active'", "pilots.status"),
    ],
)
def test_rejects_significant_schema_constraint_drift(
    tmp_path, table, before, after, message
):
    path = _clean_database(tmp_path)
    _rebuild_empty_table(path, table, before, after)
    with pytest.raises(SchemaCompatibilityError, match=message):
        DatabaseManager(str(path))


def test_accepts_equivalent_integer_default_spelling(tmp_path):
    path = _clean_database(tmp_path)
    _rebuild_empty_table(
        path, "pilot_rpg_stats",
        "fatigue INTEGER DEFAULT 0", "fatigue INTEGER DEFAULT (+0)"
    )
    db = DatabaseManager(str(path))
    db.close()


def test_rejects_weakened_constraint_without_advancing_schema_metadata(tmp_path):
    path = _clean_database(tmp_path)
    _rebuild_empty_table(
        path, "diary_entries", "pilotId TEXT NOT NULL", "pilotId TEXT"
    )
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE meta SET value='3.3' WHERE key='schema_version'"
        )
    with pytest.raises(SchemaCompatibilityError, match="diary_entries.pilotId"):
        DatabaseManager(str(path))
    with sqlite3.connect(path) as conn:
        value = conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0]
    assert value == "3.3"


def test_normal_canonical_schema_reopens(tmp_path):
    path = _clean_database(tmp_path)
    db = DatabaseManager(str(path))
    db.close()

@pytest.mark.parametrize(
    "replacement",
    ["fatigue INTEGER DEFAULT '0'", "fatigue INTEGER DEFAULT 0.0"],
)
def test_rejects_noninteger_defaults(replacement, tmp_path):
    path = _clean_database(tmp_path)
    _rebuild_empty_table(
        path, "pilot_rpg_stats", "fatigue INTEGER DEFAULT 0", replacement
    )
    with pytest.raises(SchemaCompatibilityError, match="pilot_rpg_stats.fatigue"):
        DatabaseManager(str(path))


def test_optional_nullable_source_field_remains_accepted(tmp_path):
    path = _clean_database(tmp_path)
    _rebuild_empty_table(
        path, "pilots", "notes TEXT", "notes TEXT DEFAULT NULL"
    )
    db = DatabaseManager(str(path))
    db.close()


def test_status_default_null_is_semantically_absent(tmp_path):
    path = _clean_database(tmp_path)
    _rebuild_empty_table(
        path, "pilots", "status TEXT", "status TEXT DEFAULT NULL"
    )
    db = DatabaseManager(str(path))
    db.close()
