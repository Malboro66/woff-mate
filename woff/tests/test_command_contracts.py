"""Command-level contracts for the public WoFF Mate entry points."""

from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from ..config import WatchdogConfig
from ..database import DatabaseManager
from .. import woff_watchdog
from ..woff_watchdog import WoFFWatchdog
from .test_dossier_parser import _encode_dossier


REPOSITORY_ROOT = Path(__file__).parents[2]

VALID_PILOT_LOG_RECORD = (
    "6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;"
    "SE.5a;No. 56 Sqn;troops;Target;N50;E2;;Mission completed.\n"
)
VALID_PILOT_CLAIM_RECORD = (
    "6;4;1917;10;35;Arras;Filescamp;OP;SE.5a;1;"
    "Albatros D.III;Destroyed Confirmed;Albatros\n"
)
INCOMPLETE_PILOT_SOURCES = (
    (
        "Pilot1Claims.txt",
        "1\nX;X;X;X;X;sector;a;b;plane;z;enemy;confirmed\n",
    ),
    ("Pilot1Log.txt", "2\n" + VALID_PILOT_LOG_RECORD),
    ("Pilot1Claims.txt", "2\n" + VALID_PILOT_CLAIM_RECORD),
    ("Pilot1Squads.txt", "malformed\n"),
)


def _run(
    command: list[str | Path],
    *,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _console_script(name: str) -> Path:
    scripts = Path(sys.executable).parent
    candidates = [scripts / name, scripts / f"{name}.exe", scripts / f"{name}-script.py"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise AssertionError(f"installed console script is missing: {name}")


def _run_query(tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return _run(
        [sys.executable, str(REPOSITORY_ROOT / "woff_query.py"), *arguments],
        cwd=tmp_path,
    )


def _write_config(
    path: Path,
    *,
    watch_paths: list[Path],
    export_path: Path,
    backup_export: bool = False,
) -> None:
    config = WatchdogConfig(
        watch_paths=[str(item) for item in watch_paths],
        export_path=str(export_path),
        backup_export=backup_export,
    )
    path.write_text(json.dumps(config.to_dict()), encoding="utf-8")


def _empty_database(path: Path) -> None:
    database = DatabaseManager(str(path))
    database.close()


@pytest.mark.parametrize("format_name", ["json", "csv", "md"])
def test_empty_query_output_preserves_the_selected_format(
    tmp_path: Path,
    format_name: str,
) -> None:
    database = tmp_path / "empty.sqlite"
    _empty_database(database)

    result = _run_query(
        tmp_path,
        "--db",
        str(database),
        "--format",
        format_name,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    if format_name == "json":
        assert json.loads(result.stdout) == []
    elif format_name == "csv":
        rows = list(csv.DictReader(io.StringIO(result.stdout)))
        assert rows == []
        assert result.stdout.startswith("pilot_id,slot,name,")
    else:
        lines = result.stdout.splitlines()
        assert len(lines) == 2
        assert lines[0].startswith("| pilot_id | slot | name |")
        assert set(lines[1]) <= {"|", "-"}


def test_populated_json_query_is_one_document_without_a_human_hint(
    tmp_path: Path,
) -> None:
    database = tmp_path / "pilot.sqlite"
    _empty_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO pilots (id, name, missions, killsCount) VALUES (?, ?, ?, ?)",
            ("pilot-1", "Synthetic Pilot", 0, 0),
        )

    result = _run_query(tmp_path, "--db", str(database), "--format", "json")

    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout) == [
        {
            "pilot_id": "pilot-1",
            "slot": None,
            "name": "Synthetic Pilot",
            "rank": None,
            "squadron": None,
            "status": None,
            "missions": 0,
            "killsCount": 0,
        }
    ]
    assert "Para ver detalhes" not in result.stdout


def test_missing_database_is_a_usage_failure_on_stderr_without_creation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "missing.sqlite"

    result = _run_query(tmp_path, "--db", str(database), "--format", "json")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "Base de dados" in result.stderr
    assert not database.exists()


def test_sqlite_failure_is_a_runtime_failure_on_stderr(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corrupt.sqlite"
    database.write_text("not a sqlite database", encoding="utf-8")

    result = _run_query(tmp_path, "--db", str(database), "--format", "json")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "ERRO SQL" in result.stderr


def test_existing_malformed_query_config_is_not_silently_ignored(
    tmp_path: Path,
) -> None:
    config = tmp_path / "broken.json"
    config.write_text("{broken", encoding="utf-8")

    result = _run_query(tmp_path, "--config", str(config), "--format", "json")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "config" in result.stderr.lower()


@pytest.mark.parametrize("command", ["woff-watchdog", "woff-report"])
def test_malformed_config_is_a_usage_failure_for_installed_commands(
    tmp_path: Path,
    command: str,
) -> None:
    config = tmp_path / "broken.json"
    config.write_text("{broken", encoding="utf-8")

    result = _run(
        [_console_script(command), "--config", str(config)],
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "config" in result.stderr.lower()
    assert not (tmp_path / "woff_data_report.txt").exists()


@pytest.mark.parametrize(
    "arguments",
    [
        ("--pilot-id", "pilot-1", "--format", "json"),
        (
            "--pilot-id",
            "pilot-1",
            "--missions",
            "--diary",
            "--format",
            "json",
        ),
    ],
)
def test_ambiguous_machine_readable_query_modes_fail_before_stdout(
    tmp_path: Path,
    arguments: tuple[str, ...],
) -> None:
    database = tmp_path / "pilot.sqlite"
    _empty_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO pilots (id, name) VALUES (?, ?)",
            ("pilot-1", "Synthetic Pilot"),
        )

    result = _run_query(tmp_path, "--db", str(database), *arguments)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "exactly one" in result.stderr.lower()


def test_all_three_public_commands_have_installed_console_scripts(
    tmp_path: Path,
) -> None:
    database = tmp_path / "empty.sqlite"
    _empty_database(database)

    for command in ("woff-query", "woff-watchdog", "woff-report"):
        assert _console_script(command).is_file()

    result = _run(
        [_console_script("woff-query"), "--db", str(database), "--format", "json"],
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == []


def test_watchdog_banner_supports_legacy_windows_console_encoding() -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")

    woff_watchdog._print_banner(stream)
    stream.flush()

    rendered = buffer.getvalue().decode("cp1252")
    assert "WoFF BHaH II" in rendered
    assert "Watchdog" in rendered


@pytest.mark.parametrize(
    ("filename", "contents", "expected_status"),
    [
        ("missing.xml", None, 2),
        ("unsupported.bin", b"synthetic", 2),
        ("invalid.xml", b"<broken", 1),
    ],
)
def test_parse_file_failures_return_stable_nonzero_statuses(
    tmp_path: Path,
    filename: str,
    contents: bytes | None,
    expected_status: int,
) -> None:
    target = tmp_path / filename
    if contents is not None:
        target.write_bytes(contents)
    config = tmp_path / "parse-config.json"
    _write_config(
        config,
        watch_paths=[],
        export_path=tmp_path / "unused.sqlite",
    )

    result = _run(
        [
            _console_script("woff-watchdog"),
            "--config",
            str(config),
            "--parse-file",
            str(target),
        ],
        cwd=tmp_path,
    )

    assert result.returncode == expected_status
    assert "ERROR" in result.stderr


@pytest.mark.parametrize("filename", ["Pilot1Log.txt", "Pilot1Claims.txt"])
def test_parse_file_accepts_valid_zero_record_pilot_files(
    tmp_path: Path,
    filename: str,
) -> None:
    target = tmp_path / filename
    target.write_text("0\n", encoding="cp1252")
    config = tmp_path / "parse-config.json"
    _write_config(
        config,
        watch_paths=[],
        export_path=tmp_path / "unused.sqlite",
    )

    result = _run(
        [
            _console_script("woff-watchdog"),
            "--config",
            str(config),
            "--parse-file",
            str(target),
        ],
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "Missões extraídas do log: 0" in result.stderr
    assert "Vitórias extraídas: 0" in result.stderr


@pytest.mark.parametrize(
    ("filename", "contents"),
    INCOMPLETE_PILOT_SOURCES,
    ids=(
        "full-width-malformed-claim",
        "truncated-log-count",
        "truncated-claims-count",
        "malformed-squads",
    ),
)
def test_parse_file_rejects_structurally_incomplete_pilot_sources(
    tmp_path: Path,
    filename: str,
    contents: str,
) -> None:
    target = tmp_path / filename
    target.write_text(contents, encoding="cp1252")
    config = tmp_path / "parse-config.json"
    _write_config(
        config,
        watch_paths=[],
        export_path=tmp_path / "unused.sqlite",
    )

    result = _run(
        [
            _console_script("woff-watchdog"),
            "--config",
            str(config),
            "--parse-file",
            str(target),
        ],
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_invalid_watch_paths_fail_before_database_creation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "must-not-exist.sqlite"
    config = tmp_path / "invalid-watch.json"
    _write_config(
        config,
        watch_paths=[tmp_path / "missing-root"],
        export_path=database,
    )

    result = _run(
        [_console_script("woff-watchdog"), "--config", str(config)],
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "Nenhum caminho válido" in result.stderr
    assert not database.exists()


def test_report_uses_selected_config_and_renders_zero_as_zero(
    tmp_path: Path,
) -> None:
    lines = ["Null"] * 105
    lines[1] = "Britain"
    lines[3] = "Captain"
    lines[4] = "Zero"
    lines[5] = "Pilot"
    lines[6:9] = ["1", "1", "1917"]
    lines[11] = "0"
    lines[16] = "0"
    lines[17] = "0"
    lines[41] = "0"
    lines[46] = "0"
    lines[52] = "0"
    lines[83] = "Synthetic Squadron"
    lines[84] = "Synthetic Aircraft"
    lines[92] = "Synthetic Place"
    lines[100] = "0"
    dossier = tmp_path / "Pilot1Dossier.txt"
    dossier.write_bytes(_encode_dossier(lines, dossier.name))

    config = tmp_path / "selected.json"
    _write_config(
        config,
        watch_paths=[tmp_path],
        export_path=tmp_path / "unused.sqlite",
    )

    result = _run(
        [_console_script("woff-report"), "--config", str(config)],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    report = (tmp_path / "woff_data_report.txt").read_text(encoding="utf-8")
    assert "Nº Total de Missões: 0" in report
    assert "Vitórias Confirmadas: 0" in report
    assert "Skill: 0" in report
    assert "Nº Total de Missões: Vazio" not in report


@pytest.mark.parametrize("filename", ["Pilot1Log.txt", "Pilot1Claims.txt"])
def test_report_accepts_valid_zero_record_pilot_files(
    tmp_path: Path,
    filename: str,
) -> None:
    (tmp_path / filename).write_text("0\n", encoding="cp1252")
    config = tmp_path / "selected.json"
    _write_config(
        config,
        watch_paths=[tmp_path],
        export_path=tmp_path / "unused.sqlite",
    )

    result = _run(
        [_console_script("woff-report"), "--config", str(config)],
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    report = (tmp_path / "woff_data_report.txt").read_text(encoding="utf-8")
    assert f"FONTE: {filename.lower()}" in report
    assert "Missões extraídas: 0" in report
    assert "Vitórias extraídas: 0" in report


@pytest.mark.parametrize("filename", ["Pilot1Log.txt", "Pilot1Claims.txt"])
def test_report_rejects_malformed_zero_record_pilot_files(
    tmp_path: Path,
    filename: str,
) -> None:
    (tmp_path / filename).write_text("0\nmalformed record\n", encoding="cp1252")
    config = tmp_path / "selected.json"
    _write_config(
        config,
        watch_paths=[tmp_path],
        export_path=tmp_path / "unused.sqlite",
    )

    result = _run(
        [_console_script("woff-report"), "--config", str(config)],
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert "Falha ao processar" in result.stderr
    assert not (tmp_path / "woff_data_report.txt").exists()


@pytest.mark.parametrize(
    ("filename", "contents"),
    [
        (
            "Pilot1Log.txt",
            "2\n"
            "6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;"
            "SE.5a;No. 56 Sqn;troops;Target;N50;E2;;Mission completed.\n"
            "malformed record\n",
        ),
        (
            "Pilot1Claims.txt",
            "2\n"
            "6;4;1917;10;35;Arras;Filescamp;OP;SE.5a;1;"
            "Albatros D.III;Destroyed Confirmed;Albatros\n"
            "malformed record\n",
        ),
    ],
)
def test_report_rejects_partially_parsed_pilot_files(
    tmp_path: Path,
    filename: str,
    contents: str,
) -> None:
    (tmp_path / filename).write_text(contents, encoding="cp1252")
    config = tmp_path / "selected.json"
    _write_config(
        config,
        watch_paths=[tmp_path],
        export_path=tmp_path / "unused.sqlite",
    )

    result = _run(
        [_console_script("woff-report"), "--config", str(config)],
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert "Falha ao processar" in result.stderr
    assert not (tmp_path / "woff_data_report.txt").exists()


@pytest.mark.parametrize(
    ("filename", "contents"),
    INCOMPLETE_PILOT_SOURCES,
    ids=(
        "full-width-malformed-claim",
        "truncated-log-count",
        "truncated-claims-count",
        "malformed-squads",
    ),
)
def test_report_rejects_structurally_incomplete_pilot_sources(
    tmp_path: Path,
    filename: str,
    contents: str,
) -> None:
    (tmp_path / filename).write_text(contents, encoding="cp1252")
    config = tmp_path / "selected.json"
    _write_config(
        config,
        watch_paths=[tmp_path],
        export_path=tmp_path / "unused.sqlite",
    )

    result = _run(
        [_console_script("woff-report"), "--config", str(config)],
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert "Falha ao processar" in result.stderr
    assert not (tmp_path / "woff_data_report.txt").exists()


def test_report_ignores_unsupported_pilot_entries(tmp_path: Path) -> None:
    (tmp_path / "Pilot1Prologue.txt").write_text(
        "unsupported pilot entry", encoding="cp1252"
    )
    (tmp_path / "Pilot1Log.txt.bak").write_text(
        "unsupported backup", encoding="cp1252"
    )
    (tmp_path / "Pilot1Claims.txt").mkdir()
    config = tmp_path / "selected.json"
    _write_config(
        config,
        watch_paths=[tmp_path],
        export_path=tmp_path / "unused.sqlite",
    )

    result = _run(
        [_console_script("woff-report"), "--config", str(config)],
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    report = (tmp_path / "woff_data_report.txt").read_text(encoding="utf-8")
    assert "pilot1prologue.txt" not in report.lower()
    assert "pilot1log.txt.bak" not in report.lower()
    assert "pilot1claims.txt" not in report.lower()


def test_report_without_valid_paths_fails_without_an_artifact(
    tmp_path: Path,
) -> None:
    config = tmp_path / "missing-paths.json"
    _write_config(
        config,
        watch_paths=[tmp_path / "missing-root"],
        export_path=tmp_path / "unused.sqlite",
    )

    result = _run(
        [_console_script("woff-report"), "--config", str(config)],
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "Nenhum caminho válido" in result.stderr
    assert not (tmp_path / "woff_data_report.txt").exists()


def test_report_failure_preserves_the_previous_complete_artifact(
    tmp_path: Path,
) -> None:
    (tmp_path / "Pilot1Dossier.txt").write_bytes(b"invalid dossier")
    previous_report = tmp_path / "woff_data_report.txt"
    previous_report.write_text("previous complete report", encoding="utf-8")
    config = tmp_path / "selected.json"
    _write_config(
        config,
        watch_paths=[tmp_path],
        export_path=tmp_path / "unused.sqlite",
    )

    result = _run(
        [_console_script("woff-report"), "--config", str(config)],
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "ERROR" in result.stderr
    assert previous_report.read_text(encoding="utf-8") == "previous complete report"
    assert list(tmp_path.glob(".woff_data_report.txt.*.tmp")) == []


def test_backup_export_creates_a_verified_preprocessing_snapshot(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "campaign.sqlite"
    database = DatabaseManager(str(database_path))
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO pilots (id, name) VALUES (?, ?)",
            ("pilot-before-start", "Pre-start Pilot"),
        )
    database.close()

    config = WatchdogConfig(
        watch_paths=[str(tmp_path)],
        export_path=str(database_path),
        backup_export=True,
    )
    watchdog = WoFFWatchdog(config)
    try:
        backup_path = database_path.with_name(f"{database_path.name}.backup.sqlite")
        assert backup_path.is_file()
        with sqlite3.connect(backup_path) as backup:
            assert backup.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert backup.execute(
                "SELECT name FROM pilots WHERE id = ?", ("pilot-before-start",)
            ).fetchone() == ("Pre-start Pilot",)
    finally:
        watchdog.stop()


def test_disabled_backup_export_creates_no_snapshot(tmp_path: Path) -> None:
    database_path = tmp_path / "campaign.sqlite"
    _empty_database(database_path)
    config = WatchdogConfig(
        watch_paths=[str(tmp_path)],
        export_path=str(database_path),
        backup_export=False,
    )

    watchdog = WoFFWatchdog(config)
    try:
        assert not database_path.with_name(
            f"{database_path.name}.backup.sqlite"
        ).exists()
    finally:
        watchdog.stop()


def test_first_start_with_backup_enabled_creates_no_empty_snapshot(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "first-start.sqlite"
    config = WatchdogConfig(
        watch_paths=[str(tmp_path)],
        export_path=str(database_path),
        backup_export=True,
    )

    watchdog = WoFFWatchdog(config)
    try:
        assert database_path.is_file()
        assert not database_path.with_name(
            f"{database_path.name}.backup.sqlite"
        ).exists()
    finally:
        watchdog.stop()


def test_export_backup_failure_aborts_before_observer_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    database_path = tmp_path / "existing.sqlite"
    _empty_database(database_path)
    config_path = tmp_path / "selected.json"
    _write_config(
        config_path,
        watch_paths=[tmp_path],
        export_path=database_path,
        backup_export=True,
    )

    def fail_backup(_database: DatabaseManager) -> Path:
        raise sqlite3.OperationalError("synthetic export backup failure")

    observer = Mock()
    monkeypatch.setattr(DatabaseManager, "create_export_backup", fail_backup)
    monkeypatch.setattr(woff_watchdog, "Observer", observer)

    status = woff_watchdog.main(["--config", str(config_path)])

    assert status == 1
    assert "synthetic export backup failure" in caplog.text
    observer.assert_not_called()


def test_failed_export_backup_preserves_the_previous_verified_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "campaign.sqlite"
    database = DatabaseManager(str(database_path))
    backup_path = database_path.with_name(f"{database_path.name}.backup.sqlite")
    backup_path.write_bytes(b"previous verified backup")

    def fail_backup(
        _source: sqlite3.Connection,
        _destination: sqlite3.Connection,
    ) -> None:
        raise sqlite3.OperationalError("synthetic backup failure")

    monkeypatch.setattr(database, "_run_sqlite_backup", fail_backup)
    try:
        with pytest.raises(sqlite3.OperationalError, match="synthetic backup failure"):
            database.create_export_backup()
        assert backup_path.read_bytes() == b"previous verified backup"
        assert list(tmp_path.glob(".*export-backup*")) == []
    finally:
        database.close()


def test_export_backup_fsync_uses_a_write_capable_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "campaign.sqlite"
    database = DatabaseManager(str(database_path))
    real_open = os.open
    temporary_access_modes: list[int] = []

    def tracking_open(path: os.PathLike[str] | str, flags: int, *args: int) -> int:
        if "export-backup" in Path(path).name:
            temporary_access_modes.append(flags & os.O_ACCMODE)
        return real_open(path, flags, *args)

    monkeypatch.setattr(os, "open", tracking_open)
    try:
        database.create_export_backup()
        assert os.O_RDWR in temporary_access_modes
    finally:
        database.close()


def test_export_backup_keeps_the_previous_canonical_snapshot_until_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "campaign.sqlite"
    database = DatabaseManager(str(database_path))
    backup_path = database_path.with_name(f"{database_path.name}.backup.sqlite")
    previous_snapshot = b"previous verified backup"
    backup_path.write_bytes(previous_snapshot)
    real_replace = os.replace
    canonical_was_present: list[bool] = []

    def tracking_replace(
        source: os.PathLike[str] | str,
        destination: os.PathLike[str] | str,
    ) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            destination_path == backup_path
            and "export-backup" in source_path.name
        ):
            canonical_was_present.append(
                backup_path.is_file()
                and backup_path.read_bytes() == previous_snapshot
            )
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", tracking_replace)
    try:
        database.create_export_backup()
        assert canonical_was_present == [True]
    finally:
        database.close()


def test_directory_sync_failure_restores_the_previous_export_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "campaign.sqlite"
    database = DatabaseManager(str(database_path))
    backup_path = database_path.with_name(f"{database_path.name}.backup.sqlite")
    previous_snapshot = b"previous verified backup"
    backup_path.write_bytes(previous_snapshot)
    real_fsync_directory = database._fsync_directory
    failure_injected = False

    def fail_after_publication(path: Path) -> None:
        nonlocal failure_injected
        if (
            not failure_injected
            and backup_path.is_file()
            and backup_path.read_bytes() != previous_snapshot
        ):
            failure_injected = True
            raise OSError("synthetic directory fsync failure")
        real_fsync_directory(path)

    monkeypatch.setattr(database, "_fsync_directory", fail_after_publication)
    try:
        with pytest.raises(OSError, match="synthetic directory fsync failure"):
            database.create_export_backup()
        assert failure_injected
        assert backup_path.read_bytes() == previous_snapshot
        assert list(tmp_path.glob(".*export-backup*")) == []
    finally:
        database.close()


def test_successful_export_backup_removes_the_rollback_sidecar(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "campaign.sqlite"
    database = DatabaseManager(str(database_path))
    backup_path = database_path.with_name(f"{database_path.name}.backup.sqlite")
    backup_path.write_bytes(b"previous verified backup")

    try:
        database.create_export_backup()
        with sqlite3.connect(backup_path) as backup:
            assert backup.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert list(tmp_path.glob(".*export-backup*")) == []
    finally:
        database.close()
