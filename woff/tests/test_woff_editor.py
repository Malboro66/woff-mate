"""Regression tests for journal editor behavior."""

import sqlite3
from pathlib import Path

from unittest.mock import patch

import pytest

import woff_editor


@pytest.fixture
def diary_db(tmp_path):
    conn = sqlite3.connect(tmp_path / "diary.sqlite")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE pilots (id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE diary_entries (
            id TEXT PRIMARY KEY,
            pilotId TEXT NOT NULL,
            missionId TEXT,
            entry_date TEXT,
            narrative TEXT
        );
        INSERT INTO pilots VALUES ('alice', 'Alice'), ('bob', 'Bob');
        INSERT INTO diary_entries VALUES
            ('alice-1', 'alice', 'alice-mission', '1917-01-01', 'Alice original'),
            ('bob-1', 'bob', 'bob-mission', '1917-01-02', 'Bob original');
        """
    )
    conn.commit()
    yield conn
    conn.close()


def _write_diary(tmp_path, entries):
    path = tmp_path / "diary.txt"
    blocks = ["DIÁRIO DE BORDO", "=" * 60]
    for entry_id, entry_date, narrative in entries:
        blocks.extend(
            [
                f"\n=== ID: {entry_id} ===\nDATA: {entry_date}\n{narrative}\n",
                "=" * 60,
            ]
        )
    path.write_text("".join(blocks), encoding="utf-8")
    return path


def _entries(conn):
    return [tuple(row) for row in conn.execute(
        "SELECT id, pilotId, missionId, entry_date, narrative "
        "FROM diary_entries ORDER BY id"
    )]


def _backup_paths(tmp_path):
    return sorted((tmp_path / ".woff-diary-backups").glob("*.backup.sqlite"))


def _backup_entries(path):
    with sqlite3.connect(path) as backup:
        return _entries(backup)


def test_open_editor_rejects_missing_windows_startfile():
    with (
        patch.object(woff_editor.platform, "system", return_value="Windows"),
        patch.object(woff_editor.os, "startfile", None, create=True),
        pytest.raises(RuntimeError, match="os.startfile não está disponível"),
    ):
        woff_editor.open_editor("journal.txt")


def test_exported_instructions_define_blank_narratives_as_invalid(
    diary_db, tmp_path
):
    path = tmp_path / "exported-diary.txt"

    woff_editor.export_diary_to_file(diary_db, "bob", str(path))

    instructions = path.read_text(encoding="utf-8").lower()
    assert "narrativa vazia" in instructions
    assert "bloco inteiro" in instructions


def test_import_changes_only_selected_pilots_diary(diary_db, tmp_path):
    before = _entries(diary_db)
    path = _write_diary(tmp_path, [("bob-1", "1917-02-02", "Bob edited")])

    backup_path = woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == [
        ("alice-1", "alice", "alice-mission", "1917-01-01", "Alice original"),
        ("bob-1", "bob", "bob-mission", "1917-02-02", "Bob edited"),
    ]
    assert Path(backup_path).exists()
    assert _backup_paths(tmp_path) == [Path(backup_path)]
    assert _backup_entries(backup_path) == before
    with sqlite3.connect(backup_path) as backup:
        assert backup.execute("SELECT id, name FROM pilots ORDER BY id").fetchall() == [
            ("alice", "Alice"),
            ("bob", "Bob"),
        ]


def test_empty_import_clears_only_selected_pilots_diary(diary_db, tmp_path):
    before = _entries(diary_db)
    path = _write_diary(tmp_path, [])

    woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == [
        ("alice-1", "alice", "alice-mission", "1917-01-01", "Alice original")
    ]
    assert _backup_entries(_backup_paths(tmp_path)[0]) == before


def test_backups_in_same_second_are_unique_and_not_overwritten(diary_db, tmp_path):
    first_before = _entries(diary_db)
    first = woff_editor.import_diary_from_file(
        diary_db, _write_diary(tmp_path, [("bob-1", "1917-02-02", "First")]), "bob"
    )
    second_before = _entries(diary_db)
    second = woff_editor.import_diary_from_file(
        diary_db, _write_diary(tmp_path, [("bob-1", "1917-03-03", "Second")]), "bob"
    )

    assert first != second
    assert _backup_entries(first) == first_before
    assert _backup_entries(second) == second_before


def test_backup_source_is_opened_read_only(diary_db, tmp_path, monkeypatch):
    real_connect = sqlite3.connect
    calls = []

    def recording_connect(database, *args, **kwargs):
        calls.append((database, kwargs.copy()))
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(woff_editor.sqlite3, "connect", recording_connect)
    woff_editor.import_diary_from_file(
        diary_db, _write_diary(tmp_path, [("bob-1", "1917-02-02", "Edited")]), "bob"
    )

    assert any(
        str(database).startswith("file:")
        and str(database).endswith("?mode=ro")
        and kwargs.get("uri") is True
        for database, kwargs in calls
    )


def test_backup_failure_rolls_back_and_removes_incomplete_file(
    diary_db, tmp_path, monkeypatch
):
    before = _entries(diary_db)

    def fail_backup(source, destination):
        destination.execute("CREATE TABLE incomplete (value TEXT)")
        destination.commit()
        raise sqlite3.OperationalError("simulated backup failure")

    monkeypatch.setattr(woff_editor, "_copy_database_backup", fail_backup)
    path = _write_diary(tmp_path, [("bob-1", "1917-02-02", "Edited")])

    with pytest.raises(RuntimeError, match="backup.*failed"):
        woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == before
    assert _backup_paths(tmp_path) == []


def test_failed_backup_integrity_check_prevents_import(
    diary_db, tmp_path, monkeypatch
):
    before = _entries(diary_db)
    monkeypatch.setattr(woff_editor, "_backup_integrity_check", lambda conn: ("bad",))
    path = _write_diary(tmp_path, [("bob-1", "1917-02-02", "Edited")])

    with pytest.raises(RuntimeError, match="integrity check"):
        woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == before
    assert _backup_paths(tmp_path) == []


def test_commit_failure_retains_verified_backup_and_rolls_back_import(
    diary_db, tmp_path, monkeypatch, capsys
):
    before = _entries(diary_db)
    path = _write_diary(tmp_path, [("bob-1", "1917-02-02", "Edited")])

    def fail_commit(conn):
        raise sqlite3.OperationalError("simulated commit failure")

    monkeypatch.setattr(woff_editor, "_commit_import", fail_commit)

    with pytest.raises(RuntimeError, match="commit failed") as error:
        woff_editor.import_diary_from_file(diary_db, path, "bob")

    backups = _backup_paths(tmp_path)
    assert len(backups) == 1
    assert str(backups[0]) in str(error.value)
    assert _backup_entries(backups[0]) == before
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute("SELECT id, name FROM pilots ORDER BY id").fetchall() == [
            ("alice", "Alice"),
            ("bob", "Bob"),
        ]
    assert _entries(diary_db) == before
    assert diary_db.in_transaction is False
    assert "sucesso" not in capsys.readouterr().out


def test_new_entry_uses_selected_pilot_and_repeated_import_is_stable(
    diary_db, tmp_path
):
    path = _write_diary(tmp_path, [("bob-new", "1917-03-03", "New entry")])

    woff_editor.import_diary_from_file(diary_db, path, "bob")
    woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == [
        ("alice-1", "alice", "alice-mission", "1917-01-01", "Alice original"),
        ("bob-new", "bob", None, "1917-03-03", "New entry"),
    ]


def test_cross_pilot_entry_id_rejects_entire_import(diary_db, tmp_path):
    before = _entries(diary_db)
    path = _write_diary(
        tmp_path,
        [
            ("bob-new", "1917-03-03", "Would be inserted"),
            ("alice-1", "1917-04-04", "Must not overwrite Alice"),
        ],
    )

    with pytest.raises(ValueError, match="alice-1.*selected pilot"):
        woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == before
    assert _backup_paths(tmp_path) == []


def test_failure_after_write_rolls_back_complete_import(diary_db, tmp_path):
    before = _entries(diary_db)
    diary_db.execute(
        """
        CREATE TRIGGER fail_bob_delete BEFORE DELETE ON diary_entries
        WHEN OLD.pilotId = 'bob'
        BEGIN SELECT RAISE(FAIL, 'simulated deletion failure'); END
        """
    )
    diary_db.commit()
    path = _write_diary(tmp_path, [("bob-new", "1917-03-03", "Written first")])

    with pytest.raises(sqlite3.IntegrityError, match="simulated deletion failure"):
        woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == before


def test_active_caller_transaction_is_rejected_without_rollback(diary_db, tmp_path):
    diary_db.execute("INSERT INTO pilots VALUES (?, ?)", ("pending", "Pending"))
    path = _write_diary(tmp_path, [("bob-1", "1917-02-02", "Bob edited")])

    with pytest.raises(ValueError, match="active transaction"):
        woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert diary_db.in_transaction is True
    assert diary_db.execute(
        "SELECT name FROM pilots WHERE id = ?", ("pending",)
    ).fetchone()[0] == "Pending"
    assert _backup_paths(tmp_path) == []


@pytest.mark.parametrize(
    "block, error",
    [
        ("=== ID: bob-1 ===\nNarrative", "DATA"),
        ("=== ID: bob-1 ===\nDATA:   \nNarrative", "DATA"),
        ("DATA: 1917-01-01\nNarrative", "ID"),
        ("=== ID:   ===\nDATA: 1917-01-01\nNarrative", "ID"),
    ],
)
def test_malformed_block_is_rejected_without_changes(diary_db, tmp_path, block, error):
    before = _entries(diary_db)
    path = tmp_path / "malformed.txt"
    path.write_text("HEADER" + "=" * 60 + "\n" + block + "\n" + "=" * 60)

    with pytest.raises(ValueError, match=error):
        woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == before
    assert _backup_paths(tmp_path) == []


def test_malformed_block_after_valid_block_rejects_before_writes(diary_db, tmp_path):
    before = _entries(diary_db)
    path = tmp_path / "partially-valid.txt"
    separator = "=" * 60
    path.write_text(
        f"HEADER{separator}\n=== ID: bob-1 ===\nDATA: 1917-02-02\nEdited"
        f"\n{separator}\n=== ID: bob-new ===\nMissing date\n{separator}"
    )

    with pytest.raises(ValueError, match="DATA"):
        woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == before


@pytest.mark.parametrize("entry_id", ["bob-1", "bob-new"])
def test_duplicate_ids_are_rejected_without_changes(diary_db, tmp_path, entry_id):
    before = _entries(diary_db)
    path = _write_diary(
        tmp_path,
        [(entry_id, "1917-03-03", "First"), (entry_id, "1917-04-04", "Second")],
    )

    with pytest.raises(ValueError, match="Duplicate.*" + entry_id):
        woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == before


@pytest.mark.parametrize("narrative", ["", "   ", "\n\t"])
def test_retained_block_with_blank_narrative_is_rejected_without_changes(
    diary_db, tmp_path, narrative
):
    before = _entries(diary_db)
    path = _write_diary(tmp_path, [("bob-1", "1917-01-02", narrative)])

    with pytest.raises(ValueError, match="bob-1.*empty narrative"):
        woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == before
    assert diary_db.in_transaction is False
    assert _backup_paths(tmp_path) == []


def test_empty_narrative_foreign_id_is_rejected(diary_db, tmp_path):
    before = _entries(diary_db)
    path = _write_diary(tmp_path, [("alice-1", "1917-01-01", "")])

    with pytest.raises(ValueError, match="alice-1.*empty narrative"):
        woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == before
    assert diary_db.in_transaction is False
    assert _backup_paths(tmp_path) == []


def test_structural_markers_in_multiline_narrative_remain_text(diary_db, tmp_path):
    narrative = "First line\nDATA: narrative marker\n=== ID: narrative marker ==="
    path = _write_diary(tmp_path, [("bob-1", "1917-02-02", narrative)])

    woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == [
        ("alice-1", "alice", "alice-mission", "1917-01-01", "Alice original"),
        ("bob-1", "bob", "bob-mission", "1917-02-02", narrative),
    ]


def test_stale_selected_pilot_is_rejected_without_orphan_rows(tmp_path):
    db_path = tmp_path / "stale.sqlite"
    importer = sqlite3.connect(db_path)
    importer.row_factory = sqlite3.Row
    importer.executescript(
        """
        CREATE TABLE pilots (id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE diary_entries (
            id TEXT PRIMARY KEY, pilotId TEXT NOT NULL, missionId TEXT,
            entry_date TEXT, narrative TEXT
        );
        INSERT INTO pilots VALUES ('alice', 'Alice'), ('bob', 'Bob');
        INSERT INTO diary_entries VALUES
            ('alice-1', 'alice', 'alice-mission', '1917-01-01', 'Alice original');
        """
    )
    importer.commit()
    cached_id = importer.execute(
        "SELECT id FROM pilots WHERE name = ?", ("Bob",)
    ).fetchone()[0]
    with sqlite3.connect(db_path) as other:
        other.execute("DELETE FROM pilots WHERE id = ?", (cached_id,))
    path = _write_diary(tmp_path, [("bob-new", "1917-03-03", "New entry")])
    before = _entries(importer)

    with pytest.raises(ValueError, match="Selected pilot.*no longer exists"):
        woff_editor.import_diary_from_file(importer, path, cached_id)

    assert _entries(importer) == before
    assert importer.execute(
        "SELECT COUNT(*) FROM diary_entries WHERE pilotId = ?", (cached_id,)
    ).fetchone()[0] == 0
    assert _backup_paths(tmp_path) == []
    importer.close()


def test_main_reports_blank_narrative_as_invalid_without_success(
    diary_db, tmp_path, monkeypatch, capsys
):
    before = _entries(diary_db)
    separator = "=" * 60

    def clear_narrative(filepath):
        Path(filepath).write_text(
            "DIÁRIO DE BORDO DE BOB\n"
            "CARREIRA ID: bob\n"
            f"{separator}\n"
            "=== ID: bob-1 ===\n"
            "DATA: 1917-01-02\n"
            "   \n"
            f"{separator}\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(woff_editor, "open_editor", clear_narrative)

    status = woff_editor.main(
        ["--db", str(tmp_path / "diary.sqlite"), "--pilot-id", "bob"]
    )
    streams = capsys.readouterr()

    assert status == 2
    assert "sucesso" not in streams.out
    assert "bob-1" in streams.err
    assert "empty narrative" in streams.err
    assert _entries(diary_db) == before
    assert _backup_paths(tmp_path) == []
