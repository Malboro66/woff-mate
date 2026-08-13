"""Regression tests for journal editor behavior."""

import sqlite3

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
            ('alice-1', 'alice', NULL, '1917-01-01', 'Alice original'),
            ('bob-1', 'bob', NULL, '1917-01-02', 'Bob original');
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
        "SELECT id, pilotId, entry_date, narrative FROM diary_entries ORDER BY id"
    )]


def test_open_editor_rejects_missing_windows_startfile():
    with (
        patch.object(woff_editor.platform, "system", return_value="Windows"),
        patch.object(woff_editor.os, "startfile", None, create=True),
        pytest.raises(RuntimeError, match="os.startfile não está disponível"),
    ):
        woff_editor.open_editor("journal.txt")


def test_import_changes_only_selected_pilots_diary(diary_db, tmp_path):
    path = _write_diary(tmp_path, [("bob-1", "1917-02-02", "Bob edited")])

    woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == [
        ("alice-1", "alice", "1917-01-01", "Alice original"),
        ("bob-1", "bob", "1917-02-02", "Bob edited"),
    ]


def test_empty_import_clears_only_selected_pilots_diary(diary_db, tmp_path):
    path = _write_diary(tmp_path, [])

    woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == [
        ("alice-1", "alice", "1917-01-01", "Alice original")
    ]


def test_new_entry_uses_selected_pilot_and_repeated_import_is_stable(
    diary_db, tmp_path
):
    path = _write_diary(tmp_path, [("bob-new", "1917-03-03", "New entry")])

    woff_editor.import_diary_from_file(diary_db, path, "bob")
    woff_editor.import_diary_from_file(diary_db, path, "bob")

    assert _entries(diary_db) == [
        ("alice-1", "alice", "1917-01-01", "Alice original"),
        ("bob-new", "bob", "1917-03-03", "New entry"),
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
