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


def _legacy_database(
    path: Path,
    unique_key: str = "pilotId, fName, sName",
    *,
    constraint_name: str = "",
) -> None:
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
        conn.execute(
            _LEGACY_SQUAD_MEMBERS_DDL.replace(
                "pilotId, fName, sName", unique_key
            ).replace(
                "    UNIQUE(",
                (
                    f"    CONSTRAINT {constraint_name} UNIQUE("
                    if constraint_name
                    else "    UNIQUE("
                ),
            )
        )
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
            ("3.4",),
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


@pytest.mark.parametrize(
    "constraint_name",
    [
        "",
        "legacy_key",
        '"legacy-key"',
        "`legacy-key`",
        "[legacy-key]",
        '"legacy,key (96): evidence"',
    ],
)
@pytest.mark.parametrize(
    "unique_key",
    [
        "pilotId, fName, sName",
        "fName, sName, pilotId",
        "sName, pilotId, fName",
        '"sName" DESC, [pilotId] ASC, `fName`',
        "pilotId COLLATE BINARY, fName, sName",
        "fName, sName, pilotId COLLATE BINARY",
        "pilotId COLLATE BINARY ASC, fName, sName",
        '"fName", [sName], `pilotId` COLLATE "BINARY" DESC',
        "pilotId COLLATE NOCASE, fName, sName",
        "pilotId, fName COLLATE RTRIM DESC, sName",
    ],
)
def test_wingman_identity_migration_preserves_ids_relationships_and_reopens(
    tmp_path: Path,
    unique_key: str,
    constraint_name: str,
) -> None:
    path = tmp_path / "wingman-identity.sqlite"
    _legacy_database(path, unique_key, constraint_name=constraint_name)

    migrated = DatabaseManager(str(path))
    migrated.close()

    conn = sqlite3.connect(path)
    try:
        columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(squad_members)")
        }
        assert SCHEMA_VERSION == "3.5"
        assert conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone() == (SCHEMA_VERSION,)
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

    backups = list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute("SELECT id FROM squad_members").fetchall() == [
            ("wingman-a",)
        ]
        assert backup.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert backup.execute("PRAGMA foreign_key_check").fetchall() == []
    for _ in range(2):
        reopened = DatabaseManager(str(path))
        assert len(reopened.get_wingmen_by_pilot("pilot-96")) == 2
        reopened.close()
    assert (
        list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite")) == backups
    )


@pytest.mark.parametrize(
    "unique_key",
    [
        "pilotId, fName, sName",
        "pilotId COLLATE BINARY DESC, fName, sName",
    ],
)
@pytest.mark.parametrize("constraint_name", ["", '"legacy-key"'])
def test_wingman_identity_migration_failure_restores_original_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    constraint_name: str,
    unique_key: str,
) -> None:
    path = tmp_path / "wingman-rollback.sqlite"
    _legacy_database(path, unique_key, constraint_name=constraint_name)

    before_conn = sqlite3.connect(path)
    try:
        before_dump = "\n".join(before_conn.iterdump())
    finally:
        before_conn.close()

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
        assert after_conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        after_conn.close()

    backups = list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    assert backups


@pytest.mark.parametrize(
    "unique_key",
    [
        "pilotId, fName, sName",
        "pilotId COLLATE BINARY, fName, sName",
    ],
)
@pytest.mark.parametrize("malformed_index", [False, True])
def test_wingman_migration_preserves_extensions_and_verified_backup(
    tmp_path: Path,
    malformed_index: bool,
    unique_key: str,
) -> None:
    path = tmp_path / "wingman-extensions.sqlite"
    _legacy_database(path, unique_key)
    with sqlite3.connect(path) as conn:
        if malformed_index:
            conn.execute("CREATE UNIQUE INDEX idx_squad_members_pilot ON squad_members(rank)")
        conn.execute("ALTER TABLE squad_members ADD COLUMN custom_note TEXT")
        conn.execute("UPDATE squad_members SET custom_note = 'Retain this value'")
        conn.execute("CREATE INDEX custom_wingman_rank ON squad_members(rank)")
        conn.execute("CREATE TABLE custom_wingman_audit (member_id TEXT)")
        conn.execute("""
            CREATE TRIGGER custom_wingman_update AFTER UPDATE OF rank ON squad_members
            BEGIN INSERT INTO custom_wingman_audit VALUES (NEW.id); END
        """)
        original_rows = conn.execute("SELECT * FROM squad_members").fetchall()
    migrated = DatabaseManager(str(path))
    conn = migrated._get_conn()
    assert conn.execute("SELECT id, custom_note FROM squad_members").fetchall() == [
        ("wingman-a", "Retain this value")
    ]
    assert conn.execute(
        "SELECT name FROM sqlite_master WHERE name = 'custom_wingman_rank'"
    ).fetchone()
    with migrated.transaction():
        conn.execute("UPDATE squad_members SET rank = 'Captain' WHERE id = 'wingman-a'")
    assert conn.execute("SELECT member_id FROM custom_wingman_audit").fetchall() == [
        ("wingman-a",)
    ]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    migrated.close()
    backup = next((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    with sqlite3.connect(backup) as conn:
        assert conn.execute("SELECT * FROM squad_members").fetchall() == original_rows
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert ("pilotId", "fName", "sName") in _unique_columns(conn, "squad_members")
    reopened = DatabaseManager(str(path))
    assert reopened._get_conn().execute(
        "SELECT custom_note FROM squad_members"
    ).fetchone() == ("Retain this value",)
    reopened.close()


@pytest.mark.parametrize(
    "definition",
    [
        "ON squad_members(pilotId)",
        "ON squad_members(pilotId COLLATE NOCASE)",
        "ON squad_members(pilotId DESC)",
        "ON squad_members(pilotId COLLATE NOCASE DESC)",
        "ON squad_members(lower(pilotId))",
        "ON squad_members(rank)",
        "ON squad_members(sName, pilotId)",
        "ON squad_members(pilotId, sName)",
        "UNIQUE ON squad_members(pilotId)",
        "ON squad_members(pilotId) WHERE status = 'In Service'",
    ],
)
def test_reserved_squad_index_is_certified_and_repaired(tmp_path, definition):
    path = tmp_path / "index.sqlite"
    db = DatabaseManager(str(path))
    db.close()
    unique = definition.startswith("UNIQUE ")
    tail = definition.removeprefix("UNIQUE ")
    with sqlite3.connect(path) as conn:
        conn.execute("DROP INDEX idx_squad_members_pilot")
        conn.execute(
            f"CREATE {'UNIQUE ' if unique else ''}INDEX idx_squad_members_pilot {tail}"
        )
    repaired = DatabaseManager(str(path))
    conn = repaired._get_conn()
    index = next(
        row
        for row in conn.execute("PRAGMA index_list(squad_members)")
        if row[1] == "idx_squad_members_pilot"
    )
    assert not index[2] and not index[4]
    assert [
        row[2] for row in conn.execute("PRAGMA index_info(idx_squad_members_pilot)")
    ] == ["pilotId"]
    assert [
        (row[2], row[3], row[4].upper())
        for row in conn.execute("PRAGMA index_xinfo(idx_squad_members_pilot)")
        if row[5]
    ] == [("pilotId", 0, "BINARY")]
    assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    repaired.close()
    backups = list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    assert bool(backups) == (definition != "ON squad_members(pilotId)")
    reopened = DatabaseManager(str(path))
    reopened.close()
    assert (
        list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite")) == backups
    )


def test_previous_binary_rejects_wingman_schema_without_modification(
    tmp_path, monkeypatch
):
    from .. import database

    path = tmp_path / "future.sqlite"
    db = DatabaseManager(str(path))
    db.close()
    with sqlite3.connect(path) as conn:
        before = list(conn.iterdump())
    monkeypatch.setattr(database, "SCHEMA_VERSION", "3.4")
    with pytest.raises(database.UnsupportedSchemaVersion, match="schema futuro 3.5"):

        DatabaseManager(str(path))
    with sqlite3.connect(path) as conn:
        assert list(conn.iterdump()) == before
    assert not list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))


@pytest.mark.parametrize(
    "unique_key", ["fName, sName, pilotId", "sName, pilotId, fName"]
)
def test_reordered_standalone_name_unique_is_removed(tmp_path, unique_key):
    path = tmp_path / "standalone.sqlite"
    db = DatabaseManager(str(path))
    db.close()
    with sqlite3.connect(path) as conn:
        conn.execute(
            f"CREATE UNIQUE INDEX legacy_name_key ON squad_members({unique_key})"
        )
    migrated = DatabaseManager(str(path))
    conn = migrated._get_conn()
    assert (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='legacy_name_key'"
        ).fetchone()
        is None
    )
    with migrated.transaction():
        conn.execute("INSERT INTO pilots(id, name) VALUES ('pilot', 'Synthetic')")
        conn.executemany(
            "INSERT INTO squad_members(id, pilotId, fName, sName) VALUES (?, 'pilot', 'John', 'Smith')",
            [("a",), ("b",)],
        )
    assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    migrated.close()
    reopened = DatabaseManager(str(path))
    assert len(reopened.get_wingmen_by_pilot("pilot")) == 2
    reopened.close()
    assert list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))


def test_unrelated_unique_superset_and_partial_indexes_are_preserved(tmp_path):
    path = tmp_path / "custom.sqlite"
    _legacy_database(path, "sName, pilotId, fName")
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE UNIQUE INDEX custom_superset ON squad_members(pilotId, fName, sName, rank)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX custom_partial ON squad_members(pilotId, fName, sName) WHERE rank='Custom'"
        )
        indexes = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE name IN ('custom_superset', 'custom_partial') ORDER BY name"
        ).fetchall()
    db = DatabaseManager(str(path))
    assert (
        db._get_conn()
        .execute(
            "SELECT name, sql FROM sqlite_master WHERE name IN ('custom_superset', 'custom_partial') ORDER BY name"
        )
        .fetchall()
        == indexes
    )
    db.close()
    reopened = DatabaseManager(str(path))
    reopened.close()


@pytest.mark.parametrize(
    "index_definition",
    [
        "CREATE UNIQUE INDEX idx_squad_members_pilot ON squad_members(rank)",
        "CREATE INDEX idx_squad_members_pilot ON squad_members(pilotId COLLATE NOCASE DESC)",
    ],
)
def test_index_repair_failure_restores_backup_transactionally(
    tmp_path, monkeypatch, index_definition
):
    path = tmp_path / "index-rollback.sqlite"
    db = DatabaseManager(str(path))
    db.close()
    with sqlite3.connect(path) as conn:
        conn.execute("DROP INDEX idx_squad_members_pilot")
        conn.execute(index_definition)
        before = list(conn.iterdump())
    original = DatabaseManager._migrate_wingman_identity_schema

    def fail_after_repair(self, cursor):
        original(self, cursor)
        raise RuntimeError("synthetic index repair failure")

    monkeypatch.setattr(
        DatabaseManager, "_migrate_wingman_identity_schema", fail_after_repair
    )
    with pytest.raises(RuntimeError, match="synthetic index repair failure"):
        DatabaseManager(str(path))
    with sqlite3.connect(path) as conn:
        assert list(conn.iterdump()) == before
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    backup = next((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    with sqlite3.connect(backup) as conn:
        assert list(conn.iterdump()) == before


def test_quoted_legacy_key_removal_preserves_unrelated_constraints(
    tmp_path, monkeypatch
):
    from . import test_wingman_identity_migration as fixtures

    monkeypatch.setattr(
        fixtures,
        "_LEGACY_SQUAD_MEMBERS_DDL",
        _LEGACY_SQUAD_MEMBERS_DDL.replace(
            "    FOREIGN KEY(pilotId)",
            '    CONSTRAINT "keep-key (96)" UNIQUE(pilotId, rank),\n'
            "    CHECK(skill >= 0),\n    FOREIGN KEY(pilotId)",
        ),
    )
    path = tmp_path / "constraints.sqlite"
    _legacy_database(
        path,
        "fName, sName, pilotId COLLATE BINARY DESC",
        constraint_name='"legacy-key"',
    )
    db = DatabaseManager(str(path))
    conn = db._get_conn()
    assert ("pilotId", "rank") in _unique_columns(conn, "squad_members")
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction():
            conn.execute(
                "INSERT INTO squad_members(id, pilotId, rank) VALUES ('duplicate-rank', 'pilot-96', 'Lieutenant')"
            )
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction():
            conn.execute("UPDATE squad_members SET skill=-1")
    assert conn.execute("SELECT id, skill FROM squad_members").fetchall() == [
        ("wingman-a", 4)
    ]
    assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()
    reopened = DatabaseManager(str(path))
    assert ("pilotId", "rank") in _unique_columns(reopened._get_conn(), "squad_members")
    reopened.close()


@pytest.mark.parametrize("index_present", [False, True])
@pytest.mark.parametrize("fail_after_repair", [False, True])
def test_canonical_index_over_historical_nocase_column(
    tmp_path, monkeypatch, index_present, fail_after_repair
):
    from . import test_wingman_identity_migration as fixtures

    monkeypatch.setattr(
        fixtures,
        "_LEGACY_SQUAD_MEMBERS_DDL",
        _LEGACY_SQUAD_MEMBERS_DDL.replace(
            "pilotId TEXT,", "pilotId TEXT COLLATE NOCASE,"
        ),
    )
    path = tmp_path / "column-collation.sqlite"
    _legacy_database(path)
    with sqlite3.connect(path) as conn:
        if index_present:
            conn.execute(
                "CREATE INDEX idx_squad_members_pilot ON squad_members(pilotId)"
            )
        before = list(conn.iterdump())
        relationships = [
            conn.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("wingmen_personalities", "wingmen_memory")
        ]
    conn.close()
    original = DatabaseManager._migrate_wingman_identity_schema

    def fail(self, cursor):
        original(self, cursor)
        assert self._has_canonical_squad_index(cursor)
        raise RuntimeError("synthetic post-index failure")

    if fail_after_repair:
        monkeypatch.setattr(DatabaseManager, "_migrate_wingman_identity_schema", fail)
        with pytest.raises(RuntimeError, match="synthetic post-index failure"):
            DatabaseManager(str(path))
        with sqlite3.connect(path) as conn:
            assert list(conn.iterdump()) == before
            assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    else:
        db = DatabaseManager(str(path))
        conn = db._get_conn()
        assert (
            "pilotId TEXT COLLATE NOCASE"
            in conn.execute(
                "SELECT sql FROM sqlite_master WHERE name='squad_members'"
            ).fetchone()[0]
        )
        assert [
            (row[2], row[3], row[4].upper())
            for row in conn.execute("PRAGMA index_xinfo(idx_squad_members_pilot)")
            if row[5]
        ] == [("pilotId", 0, "BINARY")]
        assert len(db.get_wingmen_by_pilot("pilot-96")) == 1
        assert conn.execute(
            "SELECT id FROM squad_members WHERE pilotId='PILOT-96'"
        ).fetchall() == [("wingman-a",)]
        assert [
            conn.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("wingmen_personalities", "wingmen_memory")
        ] == relationships
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        db.close()
    backups = list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as conn:
        assert list(conn.iterdump()) == before
    if not fail_after_repair:
        for _ in range(2):
            db = DatabaseManager(str(path))
            assert db._has_canonical_squad_index(db._get_conn().cursor())
            db.close()
        assert (
            list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
            == backups
        )


def test_unknown_name_key_collation_fails_closed_without_mutation(tmp_path):
    from ..database import SchemaCompatibilityError

    path = tmp_path / "unknown-collation.sqlite"
    db = DatabaseManager(str(path))
    db.close()
    with sqlite3.connect(path) as conn:
        conn.create_collation(
            "CUSTOM", lambda left, right: (left > right) - (left < right)
        )
        conn.execute(
            "CREATE UNIQUE INDEX custom_name_key ON squad_members(pilotId COLLATE CUSTOM, fName, sName)"
        )
        before = list(conn.iterdump())
    for _ in range(2):
        with pytest.raises(
            SchemaCompatibilityError,
            match="Unsupported collation on wingman name UNIQUE key",
        ):
            DatabaseManager(str(path))
    with sqlite3.connect(path) as conn:
        conn.create_collation(
            "CUSTOM", lambda left, right: (left > right) - (left < right)
        )
        assert list(conn.iterdump()) == before
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
