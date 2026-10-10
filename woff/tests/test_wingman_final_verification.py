"""Complete-roster domain and legacy diagnostic regressions for Issue #96."""

from .dossier_support import complete_roster_domain

import sqlite3

import pytest

from ..database import DatabaseManager
from ..ingestion.outcome import ProcessingReason, ProcessingStatus
from ..parsers.dossier_parser import WoFFDossierParser
from .test_dossier_transactions import _dossier_bytes, _stored_state
from .test_roster_identity import _ids, _import, _member, _roster
from .test_wingman_review_regressions import _submit
from . import test_wingman_identity_migration as migration


@pytest.mark.parametrize("candidate", [False, True])
@pytest.mark.parametrize(
    "malformed",
    [
        "Lieutenan;;Smith;3;5;In Service",
        "Lieutenan;John;Smith;oops;5;In Service",
        "Lieutenan;John;Smith;3;oops;In Service",
        "Lieutenan;John;;3;5;In Service",
        ";John;Smith;oops;5;In Service",
        "Lieutenan;???;;oops;bad;???",
        ";;;;;",
        "Lieutenant;John;Smith",
    ],
)
def test_short_malformed_occurrence_never_advances_absence(
    complete_roster_domain, candidate, malformed
):
    db, _, _ = complete_roster_domain
    assert _import(complete_roster_domain, [_member("a"), _member("b")])
    ids = _ids(db)
    assert len(ids) == 2
    assert db.save_wingman_personality(
        ids["Synthetic town a"],
        _roster(complete_roster_domain).pilot_id,
        {"personality_trait": "Steady"},
    )
    assert db.save_wingman_memory(
        ids["Synthetic town a"], "mission", "1917-04-01", "Synthetic"
    )
    if candidate:
        assert _import(complete_roster_domain, [_member("b")], generation=1)
        assert _roster(complete_roster_domain).roster_candidate is not None
    before = list(db._get_conn().iterdump())
    changed = _member("b", "Wounded").split(";")
    changed[3], changed[11], changed[12] = "8", "99", "999"
    for generation in (2, 3):
        outcome = _submit(
            complete_roster_domain, [";".join(changed), malformed], generation=generation
        )
        assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
        assert outcome.reason is ProcessingReason.PARSER_REJECTED
        assert outcome.acknowledged_generation is None and outcome.retry_input is None
        # Includes all rows, IDs, links, binding/digest, candidate/trusted metadata
        # and status/statistics: an expected rejection writes nothing at all.
        assert list(db._get_conn().iterdump()) == before
        assert _ids(db) == ids
        assert _stored_state(db)["diary"] == []
    assert _submit(
        complete_roster_domain, [_member("b"), _member("a")], generation=4
    ).acknowledged_generation
    assert _ids(db) == ids
    assert _stored_state(db)["diary"] == []
    assert _roster(complete_roster_domain).roster_candidate is None


@pytest.mark.parametrize(
    "record", ["Lieutenant;John;Smith;3;5;In Service", _member("a")]
)
def test_supported_short_and_long_forms_keep_nonroster_records_separate(
    complete_roster_domain, record
):
    db, processor, path = complete_roster_domain
    data = _dossier_bytes(
        # Six positional fields outside the roster region are not occurrences.
        decorations=("Synthetic;1917-04-01;one;two;three;four",),
        wingmen=(
            "Unrelated;data;with;four;fields",
            record,
            "Unrelated;prose;with;seven;separate;text;fields",
        ),
    )
    parser = WoFFDossierParser()
    assert parser.parse_bytes(data, path.name)
    assert len(parser.wingmen) == 1
    assert parser.wingmen[0].fName == "John"
    path.write_bytes(data)
    outcome = processor.process(str(path), "modified")
    if len(record.split(";")) == 6:
        # Recognition does not invent the absent independent identity evidence.
        assert outcome.reason is ProcessingReason.IDENTITY_REJECTED
        assert _ids(db) == {}
    else:
        assert outcome.acknowledged_generation
        assert len(_ids(db)) == 1


_TYPE_FORMS = [
    "VARCHAR /* note */ (12)",
    "VARCHAR/* note */(12)",
    "VARCHAR -- note\n(12)",
    "VARCHAR\n/* note */\n(12)",
    "CHAR /* note */ (12)",
    "VARCHAR (12)",
    "TEXT /* note */",
    "CLOB /* note */",
]


@pytest.mark.parametrize("column_type", _TYPE_FORMS)
@pytest.mark.parametrize("rollback", [False, True])
def test_numeric_type_trivia_migrates_without_losing_schema_or_relationships(
    tmp_path, monkeypatch, column_type, rollback
):
    ddl = migration._LEGACY_SQUAD_MEMBERS_DDL.replace(
        "missions INTEGER",
        f"missions {column_type} NOT NULL DEFAULT 0 CHECK(missions >= 0)",
    )
    monkeypatch.setattr(migration, "_LEGACY_SQUAD_MEMBERS_DDL", ddl)
    path = tmp_path / "type-trivia.sqlite"
    migration._legacy_database(path)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE INDEX custom_missions ON squad_members(missions)")
        conn.execute("CREATE TABLE custom_audit (member TEXT)")
        conn.execute(
            "CREATE TRIGGER custom_update AFTER UPDATE OF missions ON squad_members "
            "BEGIN INSERT INTO custom_audit VALUES (NEW.id); END"
        )
        before = list(conn.iterdump())
        links = [
            conn.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("wingmen_personalities", "wingmen_memory")
        ]
    conn.close()
    if rollback:
        original = DatabaseManager._migrate_numeric_column_types

        def fail_after_numeric_rewrite(self, cursor):
            original(self, cursor)
            assert (
                dict(
                    (r[1], r[2])
                    for r in cursor.execute("PRAGMA table_info(squad_members)")
                )["missions"]
                == "INTEGER"
            )
            raise RuntimeError("synthetic post-type-rewrite failure")

        monkeypatch.setattr(
            DatabaseManager, "_migrate_numeric_column_types", fail_after_numeric_rewrite
        )
        with pytest.raises(RuntimeError, match="synthetic post-type-rewrite failure"):
            DatabaseManager(str(path))
        with sqlite3.connect(path) as conn:
            assert list(conn.iterdump()) == before
            assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    else:
        db = DatabaseManager(str(path))
        conn = db._get_conn()
        assert (
            dict(
                (r[1], r[2]) for r in conn.execute("PRAGMA table_info(squad_members)")
            )["missions"]
            == "INTEGER"
        )
        assert conn.execute("SELECT id, missions FROM squad_members").fetchall() == [
            ("wingman-a", 12)
        ]
        assert [
            conn.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("wingmen_personalities", "wingmen_memory")
        ] == links
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='squad_members'"
        ).fetchone()[0]
        if "note" in column_type:
            assert ("-- note" if "--" in column_type else "/* note */") in sql
        assert "NOT NULL DEFAULT 0 CHECK(missions >= 0)" in sql
        for invalid in (None, -1):
            with pytest.raises(sqlite3.IntegrityError):
                with db.transaction():
                    conn.execute("UPDATE squad_members SET missions=?", (invalid,))
        with db.transaction():
            conn.execute("UPDATE squad_members SET missions=13")
        assert conn.execute("SELECT member FROM custom_audit").fetchall() == [
            ("wingman-a",)
        ]
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='custom_missions'"
        ).fetchone()
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        db.close()
    backups = list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as conn:
        assert list(conn.iterdump()) == before
    if not rollback:
        for _ in range(2):
            DatabaseManager(str(path)).close()
        assert (
            list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
            == backups
        )


@pytest.mark.parametrize("column_type", ["VARCHAR /* note */ (12)", "TEXT"])
@pytest.mark.parametrize(
    "tail",
    [
        " /* tail */ NOT NULL",
        " DEFAULT '/* literal */'",
        " CHECK(missions >= 0)",
        " REFERENCES other_table(id)",
        " UNIQUE",
        " CONSTRAINT named_key UNIQUE",
    ],
)
def test_type_boundary_keeps_column_constraints_outside_type(column_type, tail):
    db = DatabaseManager.__new__(DatabaseManager)
    definition = column_type + tail
    end = db._read_type_end(definition, 0)
    assert definition[:end] == column_type
    assert definition[end:] == tail
