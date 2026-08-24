"""Regression coverage for stable career selection in public commands."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import woff_editor
import woff_query


@pytest.fixture
def same_name_database(tmp_path: Path) -> Path:
    database = tmp_path / "same-name.sqlite"
    with sqlite3.connect(database) as conn:
        conn.executescript(
            """
            CREATE TABLE pilots (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                nation TEXT,
                rank TEXT,
                squadron TEXT,
                aircraft TEXT,
                aerodrome TEXT,
                sector TEXT,
                status TEXT,
                birthDate TEXT,
                birthPlace TEXT,
                photo TEXT,
                missions INTEGER,
                flminutes INTEGER,
                killsCount INTEGER,
                claimsCount INTEGER,
                skill INTEGER,
                reputation INTEGER
            );
            CREATE TABLE pilot_slot_bindings (
                slot INTEGER PRIMARY KEY,
                pilotId TEXT NOT NULL
            );
            CREATE TABLE pilot_rpg_stats (
                pilotId TEXT PRIMARY KEY,
                fatigue INTEGER,
                morale INTEGER,
                stress INTEGER,
                last_updated TEXT
            );
            CREATE TABLE missions (
                id TEXT PRIMARY KEY,
                pilotId TEXT NOT NULL,
                date TEXT,
                time TEXT,
                missionType TEXT,
                aircraft TEXT,
                result TEXT,
                damageReceived INTEGER,
                woundsReceived INTEGER
            );
            CREATE TABLE diary_entries (
                id TEXT PRIMARY KEY,
                pilotId TEXT NOT NULL,
                missionId TEXT,
                entry_date TEXT,
                narrative TEXT
            );
            CREATE TABLE squad_members (
                id TEXT PRIMARY KEY,
                pilotId TEXT NOT NULL,
                rank TEXT,
                fName TEXT,
                sName TEXT,
                status TEXT,
                skill INTEGER,
                bio TEXT
            );

            INSERT INTO pilots VALUES
                ('career-a', 'Alex Smith', 'A', 'Captain A', 'A Squadron',
                 'A Aircraft', 'A Field', 'A Sector', 'Active', '1890-01-01',
                 'A Place', 'a.png', 11, 111, 1, 2, 51, 101),
                ('career-b', 'Alex Smith', 'B', 'Major B', 'B Squadron',
                 'B Aircraft', 'B Field', 'B Sector', 'Active', '1891-01-01',
                 'B Place', 'b.png', 22, 222, 3, 4, 62, 202),
                ('career-unique', 'Blake Unique', 'U', 'Captain U',
                 'U Squadron', 'U Aircraft', 'U Field', 'U Sector', 'Active',
                 '1892-01-01', 'U Place', 'u.png', 33, 333, 5, 6, 73, 303);

            INSERT INTO pilot_slot_bindings VALUES
                (2, 'career-a'), (1, 'career-b'), (3, 'career-unique');
            INSERT INTO pilot_rpg_stats VALUES
                ('career-a', 11, 12, 13, 'A-updated'),
                ('career-b', 81, 82, 83, 'B-updated'),
                ('career-unique', 31, 32, 33, 'U-updated');
            INSERT INTO missions VALUES
                ('mission-a', 'career-a', '1917-01-01', '08:00',
                 'A-only mission', 'A Aircraft', 'A result', 0, 0),
                ('mission-b', 'career-b', '1917-01-02', '09:00',
                 'B-only mission', 'B Aircraft', 'B result', 0, 0);
            INSERT INTO diary_entries VALUES
                ('diary-a', 'career-a', 'mission-a', '1917-01-01',
                 'A-only diary'),
                ('diary-b', 'career-b', 'mission-b', '1917-01-02',
                 'B-only diary');
            INSERT INTO squad_members VALUES
                ('wingman-a', 'career-a', 'Lt', 'A-only', 'Wingman',
                 'In Service', 51, 'A biography'),
                ('wingman-b', 'career-b', 'Lt', 'B-only', 'Wingman',
                 'In Service', 61, 'B biography');
            """
        )
    return database


def _query(
    database: Path,
    capsys: pytest.CaptureFixture[str],
    *arguments: str,
) -> tuple[int, str, str]:
    status = woff_query.main(
        ["--db", str(database), "--no-color", *arguments]
    )
    streams = capsys.readouterr()
    return status, streams.out, streams.err


def test_table_details_and_rpg_use_the_explicit_career_id(
    same_name_database: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    status, stdout, stderr = _query(
        same_name_database, capsys, "--pilot-id", "career-a"
    )

    assert status == 0
    assert stderr == ""
    assert "career-a" in stdout
    assert "Captain A" in stdout
    assert "11/100" in stdout
    assert "career-b" not in stdout
    assert "Major B" not in stdout
    assert "81/100" not in stdout


@pytest.mark.parametrize(
    "flag, own_marker, foreign_marker",
    [
        ("--missions", "A-only mission", "B-only mission"),
        ("--diary", "A-only diary", "B-only diary"),
        ("--wingmen", "A-only", "B-only"),
    ],
)
@pytest.mark.parametrize("format_name", ["table", "json", "csv", "md"])
def test_every_query_format_isolates_rows_by_explicit_career_id(
    same_name_database: Path,
    capsys: pytest.CaptureFixture[str],
    flag: str,
    own_marker: str,
    foreign_marker: str,
    format_name: str,
) -> None:
    status, stdout, stderr = _query(
        same_name_database,
        capsys,
        "--pilot-id",
        "career-a",
        flag,
        "--format",
        format_name,
    )

    assert status == 0
    assert stderr == ""
    assert own_marker in stdout
    assert foreign_marker not in stdout
    assert "career-a" in stdout
    assert "career-b" not in stdout

    if format_name == "json":
        assert {row["pilot_id"] for row in json.loads(stdout)} == {"career-a"}
    elif format_name == "csv":
        assert {
            row["pilot_id"] for row in csv.DictReader(io.StringIO(stdout))
        } == {"career-a"}
    elif format_name == "md":
        assert "pilot_id" in stdout.splitlines()[0]


def test_machine_readable_pilot_list_exposes_stable_ids_and_slots(
    same_name_database: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with sqlite3.connect(same_name_database) as conn:
        conn.row_factory = sqlite3.Row
        woff_query.list_pilots(
            conn,
            woff_query.Colors(enabled=False),
            SimpleNamespace(format="json"),
        )

    rows = json.loads(capsys.readouterr().out)
    same_name_rows = [row for row in rows if row["name"] == "Alex Smith"]
    assert [(row["pilot_id"], row["slot"]) for row in same_name_rows] == [
        ("career-b", 1),
        ("career-a", 2),
    ]


def test_ambiguous_query_name_fails_with_deterministic_sanitized_candidates(
    same_name_database: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    status, stdout, stderr = _query(
        same_name_database, capsys, "--pilot", "Alex Smith", "--missions"
    )

    assert status != 0
    assert stdout == ""
    assert "--pilot-id" in stderr
    assert stderr.index("pilot_id=career-b slot=1") < stderr.index(
        "pilot_id=career-a slot=2"
    )
    assert "Captain A" not in stderr
    assert "Major B" not in stderr
    assert "A-only mission" not in stderr
    assert "B-only mission" not in stderr


def test_unique_name_remains_a_compatible_query_selector(
    same_name_database: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    status, stdout, stderr = _query(
        same_name_database, capsys, "--pilot", "Blake Unique"
    )

    assert status == 0
    assert stderr == ""
    assert "career-unique" in stdout
    assert "Captain U" in stdout


def test_editor_export_uses_only_the_explicit_career_id(
    same_name_database: Path,
    tmp_path: Path,
) -> None:
    export_path = tmp_path / "export.txt"
    with sqlite3.connect(same_name_database) as conn:
        conn.row_factory = sqlite3.Row
        woff_editor.export_diary_to_file(conn, "career-a", str(export_path))

    exported = export_path.read_text(encoding="utf-8")
    assert "CARREIRA ID: career-a" in exported
    assert "diary-a" in exported
    assert "A-only diary" in exported
    assert "diary-b" not in exported
    assert "B-only diary" not in exported


def test_ambiguous_editor_name_fails_before_export_or_mutation(
    same_name_database: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export = Mock()
    open_editor = Mock()
    import_diary = Mock(return_value="backup.sqlite")
    monkeypatch.setattr(woff_editor, "export_diary_to_file", export)
    monkeypatch.setattr(woff_editor, "open_editor", open_editor)
    monkeypatch.setattr(woff_editor, "import_diary_from_file", import_diary)

    status = woff_editor.main(
        ["--db", str(same_name_database), "--pilot", "Alex Smith"]
    )
    streams = capsys.readouterr()

    assert status != 0
    assert streams.out == ""
    assert "--pilot-id" in streams.err
    assert streams.err.index("pilot_id=career-b slot=1") < streams.err.index(
        "pilot_id=career-a slot=2"
    )
    export.assert_not_called()
    open_editor.assert_not_called()
    import_diary.assert_not_called()


@pytest.mark.parametrize(
    "selector, expected_id",
    [
        (("--pilot-id", "career-a"), "career-a"),
        (("--pilot", "Blake Unique"), "career-unique"),
    ],
)
def test_editor_resolves_once_then_passes_one_explicit_id_through_the_session(
    same_name_database: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    selector: tuple[str, str],
    expected_id: str,
) -> None:
    exported_ids: list[str] = []
    imported_ids: list[str] = []

    def export(conn: sqlite3.Connection, pilot_id: str, filepath: str) -> None:
        exported_ids.append(pilot_id)
        Path(filepath).write_text("DIARY", encoding="utf-8")

    def import_diary(
        conn: sqlite3.Connection, filepath: str, pilot_id: str
    ) -> str:
        imported_ids.append(pilot_id)
        return "backup.sqlite"

    monkeypatch.setattr(woff_editor, "export_diary_to_file", export)
    monkeypatch.setattr(woff_editor, "open_editor", lambda filepath: None)
    monkeypatch.setattr(woff_editor, "import_diary_from_file", import_diary)

    status = woff_editor.main(
        ["--db", str(same_name_database), *selector]
    )

    assert status == 0
    assert exported_ids == [expected_id]
    assert imported_ids == [expected_id]
    assert expected_id in capsys.readouterr().out
