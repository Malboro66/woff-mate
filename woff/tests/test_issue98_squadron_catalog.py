"""Synthetic regression coverage for Issue #98 catalog-generation preservation."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

import pytest

from ..ingestion.snapshot import StableSnapshotReader, SnapshotFailure, SnapshotFailureKind
from ..squadron_cataloger import catalog_squadrons


def _seed(db: Path, squad: str = "Esc 15", raw: str = "DEADBEEF") -> None:
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS squadrons (id TEXT PRIMARY KEY, "
            "name TEXT, raw_data TEXT, source_file TEXT)"
        )
        conn.execute(
            "INSERT INTO squadrons VALUES (?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET raw_data=excluded.raw_data",
            (squad, squad, raw, squad + ".txt"),
        )


def _rows(db: Path) -> list[tuple[str, str, str]]:
    with sqlite3.connect(db) as conn:
        return conn.execute(
            "SELECT id, raw_data, source_file FROM squadrons ORDER BY id"
        ).fetchall()


def _reader(*, read=None) -> StableSnapshotReader:
    return StableSnapshotReader(
        timeout=0.001,
        interval=0.001,
        sleep=lambda _duration: None,
        read=read,
    )


def _catalog(scratchpad: Path, db: Path, *, reader=None) -> None:
    catalog_squadrons(str(scratchpad), str(db), reader=reader or _reader())


@pytest.fixture
def sample(tmp_path):
    scratchpad = tmp_path / "Scratchpad"
    scratchpad.mkdir()
    database = tmp_path / "catalog.db"
    _seed(database)
    return scratchpad, database


@pytest.mark.parametrize(
    ("encoded", "diagnostic"),
    [
        (b"", "empty"),
        (b"41|", "truncated"),
        (b"???|", "unsupported"),
        (b"100|41|", "unsupported"),
    ],
)
def test_invalid_generation_never_overwrites_last_known_good(
    sample, encoded: bytes, diagnostic: str, caplog
):
    folder, db = sample
    (folder / "Esc 15.txt").write_bytes(encoded)
    with caplog.at_level(logging.WARNING):
        _catalog(folder, db)
    assert _rows(db) == [("Esc 15", "DEADBEEF", "Esc 15.txt")]
    assert diagnostic in caplog.text
    assert str(folder) not in caplog.text
    assert "DEADBEEF" not in caplog.text


@pytest.mark.parametrize("failure_kind", [SnapshotFailureKind.CHANGED, SnapshotFailureKind.INACCESSIBLE])
def test_snapshot_failure_preserves_existing_data(sample, failure_kind, caplog):
    folder, db = sample
    (folder / "Esc 15.txt").write_bytes(b"41|42|")

    class FailingReader:
        def acquire(self, _path):
            raise SnapshotFailure(failure_kind, 2)

    with caplog.at_level(logging.WARNING):
        _catalog(folder, db, reader=FailingReader())
    assert _rows(db) == [("Esc 15", "DEADBEEF", "Esc 15.txt")]
    assert "snapshot-" + failure_kind.value in caplog.text


def test_same_size_mutation_during_observation_does_not_commit(sample):
    folder, db = sample
    source = folder / "Esc 15.txt"
    source.write_bytes(b"41|42|")

    def mutate_during_read(path: str) -> bytes:
        observed = Path(path).read_bytes()
        changed = b"43|44|" if observed == b"41|42|" else b"41|42|"
        Path(path).write_bytes(changed)
        before = os.stat(path)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        return observed

    _catalog(folder, db, reader=_reader(read=mutate_during_read))
    assert _rows(db) == [("Esc 15", "DEADBEEF", "Esc 15.txt")]


def test_truncate_during_observation_does_not_commit(sample):
    folder, db = sample
    source = folder / "Esc 15.txt"
    source.write_bytes(b"41|42|")

    def truncate_during_read(path: str) -> bytes:
        observed = Path(path).read_bytes()
        Path(path).write_bytes(observed[:-1])
        return observed

    _catalog(folder, db, reader=_reader(read=truncate_during_read))
    assert _rows(db) == [("Esc 15", "DEADBEEF", "Esc 15.txt")]


def test_stable_generation_upserts_and_replay_does_not_rewrite_row(sample):
    folder, db = sample
    (folder / "Esc 15.txt").write_bytes(b"41|42|43|44|")
    _catalog(folder, db)
    assert _rows(db) == [("Esc 15", "41424344", "Esc 15.txt")]
    with sqlite3.connect(db) as conn:
        first_rowid = conn.execute("SELECT rowid FROM squadrons").fetchone()[0]
        conn.execute("CREATE TABLE audit (counter INTEGER NOT NULL)")
        conn.execute("INSERT INTO audit VALUES (0)")
        conn.execute(
            "CREATE TRIGGER squadron_update AFTER UPDATE ON squadrons "
            "BEGIN UPDATE audit SET counter=counter+1; END"
        )
    _catalog(folder, db)
    assert _rows(db) == [("Esc 15", "41424344", "Esc 15.txt")]
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT rowid FROM squadrons").fetchone()[0] == first_rowid
        assert conn.execute("SELECT counter FROM audit").fetchone() == (0,)


def test_stable_shorter_generation_cannot_replace_retained_payload(sample, caplog):
    folder, db = sample
    (folder / "Esc 15.txt").write_bytes(b"41|42|")
    with caplog.at_level(logging.WARNING):
        _catalog(folder, db)
    assert _rows(db) == [("Esc 15", "DEADBEEF", "Esc 15.txt")]
    assert "shorter-than-stored" in caplog.text
    assert str(folder) not in caplog.text
    assert "DEADBEEF" not in caplog.text


def test_shorter_generation_aborts_entire_batch_before_writes(sample, caplog):
    folder, db = sample
    (folder / "Esc 15.txt").write_bytes(b"41|42|")
    (folder / "Esc 16.txt").write_bytes(b"43|44|45|46|")
    with caplog.at_level(logging.WARNING):
        _catalog(folder, db)
    assert _rows(db) == [("Esc 15", "DEADBEEF", "Esc 15.txt")]
    assert caplog.text.count("batch rejected") == 1
    assert "shorter-than-stored" in caplog.text


def test_later_shorter_member_rejects_earlier_valid_member(sample, caplog):
    folder, db = sample
    _seed(db, squad="Esc 16")
    (folder / "Esc 15.txt").write_bytes(b"41|42|43|44|")
    (folder / "Esc 16.txt").write_bytes(b"45|46|")
    with caplog.at_level(logging.WARNING):
        _catalog(folder, db)
    assert _rows(db) == [
        ("Esc 15", "DEADBEEF", "Esc 15.txt"),
        ("Esc 16", "DEADBEEF", "Esc 16.txt"),
    ]
    assert caplog.text.count("batch rejected") == 1
    assert "shorter-than-stored" in caplog.text


def test_unknown_existing_storage_type_is_preserved(sample, caplog):
    folder, db = sample
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE squadrons SET raw_data = ?", (b"\xde\xad",))
    (folder / "Esc 15.txt").write_bytes(b"41|42|43|44|")
    with caplog.at_level(logging.WARNING):
        _catalog(folder, db)
    assert _rows(db) == [("Esc 15", b"\xde\xad", "Esc 15.txt")]
    assert "unsupported-stored" in caplog.text


def test_equal_or_larger_stable_generation_can_replace_retained_payload(sample):
    folder, db = sample
    source = folder / "Esc 15.txt"
    source.write_bytes(b"41|42|43|44|")
    _catalog(folder, db)
    assert _rows(db) == [("Esc 15", "41424344", "Esc 15.txt")]
    source.write_bytes(b"41|42|43|44|45|")
    _catalog(folder, db)
    assert _rows(db) == [("Esc 15", "4142434445", "Esc 15.txt")]


def test_batch_invalid_member_aborts_all_replacements(sample, caplog):
    folder, db = sample
    (folder / "Esc 15.txt").write_bytes(b"41|42|")
    (folder / "Esc 16.txt").write_bytes(b"")
    with caplog.at_level(logging.WARNING):
        _catalog(folder, db)
    assert _rows(db) == [("Esc 15", "DEADBEEF", "Esc 15.txt")]
    assert caplog.text.count("batch rejected") == 1


def test_batch_sql_failure_rolls_back_all_changes(sample, caplog):
    folder, db = sample
    (folder / "Esc 15.txt").write_bytes(b"41|42|43|44|")
    (folder / "Esc 16.txt").write_bytes(b"43|44|")
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TRIGGER reject_second BEFORE INSERT ON squadrons "
            "WHEN NEW.id = 'Esc 16' "
            "BEGIN SELECT RAISE(ABORT, 'artificial regression failure'); END"
        )
    with caplog.at_level(logging.ERROR):
        _catalog(folder, db)
    assert _rows(db) == [("Esc 15", "DEADBEEF", "Esc 15.txt")]
    assert "sqlite-write" in caplog.text
    assert "artificial regression failure" not in caplog.text


def test_empty_directory_is_not_a_delete_signal(sample):
    folder, db = sample
    _catalog(folder, db)
    assert _rows(db) == [("Esc 15", "DEADBEEF", "Esc 15.txt")]


def test_multiple_valid_members_commit_as_one_batch(sample):
    folder, db = sample
    (folder / "Esc 15.txt").write_bytes(b"41|42|43|44|")
    (folder / "Esc 16.txt").write_bytes(b"43|44|")
    _catalog(folder, db)
    assert _rows(db) == [
        ("Esc 15", "41424344", "Esc 15.txt"),
        ("Esc 16", "4344", "Esc 16.txt"),
    ]


def test_non_regular_source_rejects_whole_batch(sample, monkeypatch, caplog):
    folder, db = sample
    (folder / "Esc 15.txt").write_bytes(b"41|42|")
    (folder / "Esc 16.txt").mkdir()
    with caplog.at_level(logging.WARNING):
        _catalog(folder, db)
    assert _rows(db) == [("Esc 15", "DEADBEEF", "Esc 15.txt")]
    assert "unsupported-file" in caplog.text
