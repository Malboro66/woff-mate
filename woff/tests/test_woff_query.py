"""Regression coverage for the public ``woff-query`` output contract."""

from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from ..command_contract import ExitCode
from ..database import DatabaseManager


REPOSITORY_ROOT = Path(__file__).parents[2]
QUERY_SCRIPT = REPOSITORY_ROOT / "woff_query.py"
EMPTY_DETAIL_CONTRACTS = (
    pytest.param(
        "--missions",
        (
            "pilot_id",
            "date",
            "time",
            "missionType",
            "aircraft",
            "result",
            "damageReceived",
            "woundsReceived",
        ),
        "Nenhuma missão encontrada",
        id="missions",
    ),
    pytest.param(
        "--diary",
        ("pilot_id", "entry_date", "narrative"),
        "Diário vazio.",
        id="diary",
    ),
    pytest.param(
        "--wingmen",
        ("pilot_id", "rank", "fName", "sName", "status", "skill", "bio"),
        "Nenhum wingman encontrado.",
        id="wingmen",
    ),
)


@pytest.fixture
def pilot_without_records_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "pilot-without-records.sqlite"
    database = DatabaseManager(str(database_path))
    database.close()

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO pilots (id, name, missions, killsCount)
            VALUES (?, ?, ?, ?)
            """,
            ("pilot-without-records", "Pilot Without Records", 0, 0),
        )

    return database_path


def _run_query(
    database_path: Path,
    *,
    selector_flag: str,
    selector_value: str,
    detail_flag: str,
    format_name: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [
            sys.executable,
            str(QUERY_SCRIPT),
            "--db",
            str(database_path),
            selector_flag,
            selector_value,
            detail_flag,
            "--format",
            format_name,
            "--no-color",
        ],
        cwd=database_path.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("selector_flag", "selector_value"),
    [
        pytest.param("--pilot-id", "unknown-pilot", id="stable-id"),
        pytest.param("--pilot", "Unknown Pilot", id="compatibility-name"),
    ],
)
@pytest.mark.parametrize("format_name", ["table", "json", "csv", "md"])
def test_unknown_pilot_fails_before_output_in_every_format(
    pilot_without_records_database: Path,
    format_name: str,
    selector_flag: str,
    selector_value: str,
) -> None:
    result = _run_query(
        pilot_without_records_database,
        selector_flag=selector_flag,
        selector_value=selector_value,
        detail_flag="--missions",
        format_name=format_name,
    )

    assert result.returncode == int(ExitCode.USAGE_ERROR)
    assert result.stdout == ""
    assert "not found" in result.stderr.lower()


@pytest.mark.parametrize(
    ("detail_flag", "headers", "_table_empty_message"),
    EMPTY_DETAIL_CONTRACTS,
)
@pytest.mark.parametrize("format_name", ["json", "csv", "md"])
def test_valid_pilot_without_records_preserves_machine_readable_empty_output(
    pilot_without_records_database: Path,
    format_name: str,
    detail_flag: str,
    headers: tuple[str, ...],
    _table_empty_message: str,
) -> None:
    result = _run_query(
        pilot_without_records_database,
        selector_flag="--pilot-id",
        selector_value="pilot-without-records",
        detail_flag=detail_flag,
        format_name=format_name,
    )

    assert result.returncode == int(ExitCode.SUCCESS)
    assert result.stderr == ""
    assert "Perfil do Piloto" not in result.stdout

    if format_name == "json":
        assert json.loads(result.stdout) == []
    elif format_name == "csv":
        assert list(csv.DictReader(io.StringIO(result.stdout))) == []
        assert result.stdout == f"{','.join(headers)}\n"
    else:
        assert result.stdout == (
            f"| {' | '.join(headers)} |\n"
            f"|{'---|' * len(headers)}\n"
        )


@pytest.mark.parametrize(
    ("detail_flag", "_headers", "table_empty_message"),
    EMPTY_DETAIL_CONTRACTS,
)
def test_valid_pilot_without_records_preserves_table_output(
    pilot_without_records_database: Path,
    detail_flag: str,
    _headers: tuple[str, ...],
    table_empty_message: str,
) -> None:
    result = _run_query(
        pilot_without_records_database,
        selector_flag="--pilot-id",
        selector_value="pilot-without-records",
        detail_flag=detail_flag,
        format_name="table",
    )

    assert result.returncode == int(ExitCode.SUCCESS)
    assert result.stderr == ""
    assert "Perfil do Piloto" in result.stdout
    assert table_empty_message in result.stdout
