"""Synthetic production regressions for the fourth directed Issue #96 review."""

from __future__ import annotations

import sqlite3

import pytest

from ..database import DatabaseManager, SchemaCompatibilityError
from ..ingestion.outcome import ProcessingReason, ProcessingStatus
from .test_dossier_transactions import _dossier_bytes, _stored_state, dossier_runtime
from .test_roster_identity import _ids, _import, _member, _roster
from .test_wingman_review_regressions import _field, _submit
from . import test_wingman_identity_migration as migration


@pytest.mark.parametrize("rank", ["Lieutenan", "", "Air Commodore", "Lieutenant???"])
@pytest.mark.parametrize("candidate", [False, True])
def test_invalid_rank_cannot_become_absence(dossier_runtime, rank, candidate):
    db, _, _ = dossier_runtime
    assert _import(dossier_runtime, [_member("a"), _member("b")])
    ids = _ids(db)
    assert len(ids) == 2
    assert db.save_wingman_personality(
        ids["Synthetic town a"],
        _roster(dossier_runtime).pilot_id,
        {"personality_trait": "Steady"},
    )
    assert db.save_wingman_memory(
        ids["Synthetic town a"], "mission", "1917-04-01", "Synthetic"
    )
    if candidate:
        assert _import(dossier_runtime, [_member("b")], generation=1)
        assert _roster(dossier_runtime).roster_candidate is not None
    before = list(db._get_conn().iterdump())
    for generation in (2, 3):
        outcome = _submit(
            dossier_runtime,
            [_member("b", "Wounded"), _field(_member("a"), 0, rank)],
            generation=generation,
        )
        assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
        assert outcome.reason is ProcessingReason.PARSER_REJECTED
        assert outcome.acknowledged_generation is None and outcome.retry_input is None
        assert list(db._get_conn().iterdump()) == before
        assert _ids(db) == ids
        assert _stored_state(db)["diary"] == []
    assert _submit(
        dossier_runtime, [_member("b"), _member("a")], generation=4
    ).acknowledged_generation
    assert _ids(db) == ids and _stored_state(db)["diary"] == []


@pytest.mark.parametrize(
    "rank",
    ["Lieutenant", "Adjutant", "Sous Lieutenant", "Sous-Lieutenant", "Oberleutnant"],
)
def test_supported_rank_and_unrelated_semicolon_rows(dossier_runtime, rank):
    db, processor, path = dossier_runtime
    path.write_bytes(
        _dossier_bytes(
            decorations=("Captain;1917-04-01",),
            wingmen=(_field(_member("a"), 0, rank), "Unrelated;data;with;four;fields"),
        )
    )
    assert processor.process(str(path), "modified").acknowledged_generation
    assert len(_ids(db)) == 1


def test_legacy_query_has_exact_shape_and_rich_query_is_separate(dossier_runtime):
    db, _, _ = dossier_runtime
    assert _import(dossier_runtime, [_member("a"), _member("b")])
    pilot_id = _roster(dossier_runtime).pilot_id
    expected = [{"fName": "John", "sName": "Smith", "status": "In Service"}] * 2
    assert db.get_wingmen_by_pilot(pilot_id) == expected
    assert db._wingmen.get_wingmen_by_pilot(pilot_id) == expected
    rich = db.get_wingmen_with_identity_by_pilot(pilot_id)
    assert {row["id"] for row in rich} == set(_ids(db).values())
    assert all(set(row) == {"id", "fName", "sName", "status"} for row in rich)
    assert {w.wingman_id for w in _roster(dossier_runtime).wingmen} == {
        row["id"] for row in rich
    }


@pytest.mark.parametrize(
    "constraint",
    [
        'CONSTRAINT "legacy""key" UNIQUE(pilotId, fName, sName)',
        "CONSTRAINT `legacy``key` UNIQUE(pilotId, fName, sName)",
        "CONSTRAINT 'legacy''key' UNIQUE(pilotId, fName, sName)",
        "/* before (, */ UNIQUE(pilotId, fName, sName)",
        "UNIQUE(pilotId, /* middle ), */ fName, sName)",
        "-- legacy identity (,\n UNIQUE(pilotId, fName, sName)",
        'CONSTRAINT /* name */ "legacy""/*key" UNIQUE /* key */ (fName, sName, pilotId COLLATE /* rule */ BINARY DESC)',
    ],
)
@pytest.mark.parametrize("rollback", [False, True])
def test_sqlite_lexical_variants_migrate_and_preserve_extensions(
    tmp_path, monkeypatch, constraint, rollback
):
    ddl = migration._LEGACY_SQUAD_MEMBERS_DDL.replace(
        "UNIQUE(pilotId, fName, sName)", constraint
    )
    # Keep quote/comment punctuation outside the removed definition too.
    if "/*" in constraint or "--" in constraint:
        ddl = ddl.replace(
            "    rank TEXT,",
            """    /* retained (, comment */ rank TEXT,
    "custom/*,)--" TEXT DEFAULT '-- literal /*, )',
    """,
        )
    else:
        ddl = ddl.replace("    rank TEXT,", '    rank TEXT, "custom""column" TEXT,')
    ddl = ddl.replace(
        "    FOREIGN KEY(pilotId)",
        '    CONSTRAINT "keep" UNIQUE(pilotId, rank), CHECK(skill >= 0),\n    FOREIGN KEY(pilotId)',
    )
    ddl = ddl.replace(
        "CREATE TABLE squad_members (",
        "CREATE TABLE /* prefix ( */ squad_members /* body , */ (",
    )
    monkeypatch.setattr(migration, "_LEGACY_SQUAD_MEMBERS_DDL", ddl)
    path = tmp_path / "lexical.sqlite"
    migration._legacy_database(path)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE INDEX custom_rank ON squad_members(rank)")
        conn.execute("CREATE TABLE custom_audit (member TEXT)")
        conn.execute(
            "CREATE TRIGGER custom_update AFTER UPDATE OF rank ON squad_members BEGIN INSERT INTO custom_audit VALUES (NEW.id); END"
        )
        before = list(conn.iterdump())
        links = [
            conn.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("wingmen_personalities", "wingmen_memory")
        ]
    conn.close()
    original = DatabaseManager._migrate_wingman_identity_schema
    if rollback:

        def fail(self, cursor):
            original(self, cursor)
            raise RuntimeError("synthetic lexical migration failure")

        monkeypatch.setattr(DatabaseManager, "_migrate_wingman_identity_schema", fail)
        with pytest.raises(RuntimeError, match="synthetic lexical migration failure"):
            DatabaseManager(str(path))
        with sqlite3.connect(path) as conn:
            assert list(conn.iterdump()) == before
            assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    else:
        db = DatabaseManager(str(path))
        conn = db._get_conn()
        assert conn.execute("SELECT id FROM squad_members").fetchall() == [
            ("wingman-a",)
        ]
        assert [
            conn.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("wingmen_personalities", "wingmen_memory")
        ] == links
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='squad_members'"
        ).fetchone()[0]
        # SQLite itself normalizes away comments before the table name.
        assert "/* body , */" in sql
        if "/*" in constraint or "--" in constraint:
            assert "/* retained (, comment */" in sql
            assert '"custom/*,)--"' in sql and "'-- literal /*, )'" in sql
        with db.transaction():
            conn.execute(
                "INSERT INTO squad_members(id,pilotId,fName,sName,rank) VALUES ('b','pilot-96','John','Smith','Captain')"
            )
            conn.execute("UPDATE squad_members SET rank='Major' WHERE id='wingman-a'")
        assert conn.execute("SELECT member FROM custom_audit").fetchall() == [
            ("wingman-a",)
        ]
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='custom_rank'"
        ).fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction():
                conn.execute("UPDATE squad_members SET skill=-1")
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction():
                conn.execute(
                    "UPDATE squad_members SET rank='Captain' WHERE id='wingman-a'"
                )
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        db.close()
    backups = list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as conn:
        assert list(conn.iterdump()) == before
    if not rollback:
        for _ in range(2):
            db = DatabaseManager(str(path))
            assert len(db.get_wingmen_by_pilot("pilot-96")) == 2
            db.close()
        assert (
            list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
            == backups
        )


@pytest.mark.parametrize("kind", ["index", "table", "view"])
@pytest.mark.parametrize("schema", ["3.4", "3.5"])
def test_reserved_squad_name_collision_preserves_foreign_object(tmp_path, kind, schema):
    path = tmp_path / "collision.sqlite"
    migration._legacy_database(path)
    if schema == "3.5":
        DatabaseManager(str(path)).close()
    with sqlite3.connect(path) as conn:
        conn.execute("DROP INDEX IF EXISTS idx_squad_members_pilot")
        conn.execute("CREATE TABLE extension_table (value TEXT)")
        conn.execute("INSERT INTO extension_table VALUES ('retain')")
        if kind == "index":
            conn.execute(
                "CREATE INDEX idx_squad_members_pilot ON extension_table(value)"
            )
        elif kind == "table":
            conn.execute("CREATE TABLE idx_squad_members_pilot (value TEXT)")
        else:
            conn.execute(
                "CREATE VIEW idx_squad_members_pilot AS SELECT value FROM extension_table"
            )
        before = list(conn.iterdump())
    conn.close()
    backups = list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    for _ in range(2):
        with pytest.raises(
            SchemaCompatibilityError, match="Reserved squad index name collision"
        ):
            DatabaseManager(str(path))
        with sqlite3.connect(path) as conn:
            assert list(conn.iterdump()) == before
            assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        conn.close()
        assert (
            list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
            == backups
        )


@pytest.mark.parametrize(
    "quoted,logical",
    [
        ('"a""b"', 'a"b'),
        ("`a``b`", "a`b"),
        ("'a''b'", "a'b"),
        ('[a"b]', 'a"b'),
    ],
)
def test_sqlite_identifier_escaping_matches_sqlite(tmp_path, quoted, logical):
    db = DatabaseManager(str(tmp_path / "tokens.sqlite"))
    assert db._read_identifier(quoted + " tail", 0) == (logical, len(quoted))
    conn = db._get_conn()
    with db.transaction():
        conn.execute(f"CREATE TABLE extension ({quoted} TEXT)")
        conn.execute(f"CREATE INDEX {quoted} ON extension({quoted})")
    assert conn.execute("PRAGMA table_info(extension)").fetchone()[1] == logical
    assert db._index_key_semantics(conn.cursor(), logical) == ((logical, 0, "BINARY"),)
    # SQLite bracket quoting closes at the first ], unlike SQL Server escaping.
    assert db._read_identifier("[a]]b]", 0) == ("a", 3)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("CREATE TABLE invalid_brackets ([a]]b] TEXT)")
    db.close()


@pytest.mark.parametrize(
    "name_definition",
    [
        """name TEXT, CONSTRAINT "name""key" UNIQUE /* key */ (name)""",
        """name TEXT /* UNIQUE in comment */ UNIQUE""",
        """name TEXT DEFAULT ' UNIQUE stays literal' CONSTRAINT `name``key` UNIQUE ON /* conflict */ CONFLICT ABORT""",
    ],
)
def test_shared_lexer_preserves_numeric_and_pilot_migrations(tmp_path, name_definition):
    from .test_pilot_identity_migration import _downgrade_fixture_to_31

    path = tmp_path / "pilot-lexical.sqlite"
    _downgrade_fixture_to_31(path)
    with sqlite3.connect(path) as conn:
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='pilots'"
        ).fetchone()[0]
        ddl = ddl.replace("name TEXT UNIQUE,", name_definition + ",")
        # Table constraints must follow all columns.
        if ", CONSTRAINT" in name_definition:
            constraint = name_definition.split(", ", 1)[1]
            ddl = ddl.replace(name_definition, "name TEXT")
            end = ddl.rfind(")")
            ddl = ddl[:end] + ", " + constraint + ddl[end:]
        ddl = ddl.replace(
            "missions INTEGER",
            "-- retained numeric comment (,\n missions VARCHAR(/* type comment */ 12)",
        )
        ddl = ddl.replace(
            "last_updated TEXT",
            """last_updated TEXT, "custom""/*col" TEXT DEFAULT '-- literal )' """,
        )
        conn.execute("DROP TABLE pilots")
        conn.execute(ddl)
        conn.execute(
            "INSERT INTO pilots(id,name,missions) VALUES ('p','Synthetic','5')"
        )
    conn.close()
    db = DatabaseManager(str(path))
    conn = db._get_conn()
    assert conn.execute(
        'SELECT id, missions, "custom""/*col" FROM pilots'
    ).fetchall() == [("p", 5, "-- literal )")]
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='pilots'").fetchone()[
        0
    ]
    assert "-- retained numeric comment (," in sql
    with db.transaction():
        conn.execute("INSERT INTO pilots(id,name) VALUES ('p2','Synthetic')")
    assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()
    backup = list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    assert len(backup) == 1
    for _ in range(2):
        DatabaseManager(str(path)).close()
    assert (
        list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite")) == backup
    )


@pytest.mark.parametrize("index", [1, 2])
@pytest.mark.parametrize("name", ["", "Null", "???"])
def test_malformed_required_name_rejects_recognized_occurrence(
    dossier_runtime, index, name
):
    db, _, _ = dossier_runtime
    assert _import(dossier_runtime, [_member("a"), _member("b")])
    before = list(db._get_conn().iterdump())
    outcome = _submit(
        dossier_runtime, [_member("b"), _field(_member("a"), index, name)]
    )
    assert outcome.reason is ProcessingReason.PARSER_REJECTED
    assert list(db._get_conn().iterdump()) == before


def test_full_roster_shape_does_not_depend_on_valid_required_values(dossier_runtime):
    db, _, _ = dossier_runtime
    assert _import(dossier_runtime, [_member("a"), _member("b")])
    before = list(db._get_conn().iterdump())
    malformed = _member("a").split(";")
    for index in range(13):
        malformed[index] = "bad"
    for generation in (1, 2):
        outcome = _submit(
            dossier_runtime, [_member("b"), ";".join(malformed)], generation=generation
        )
        assert outcome.reason is ProcessingReason.PARSER_REJECTED
        assert list(db._get_conn().iterdump()) == before
