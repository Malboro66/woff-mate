"""Live ingestion must reject parser-proven incomplete generations."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from ..campaign_engine import CampaignEngine
from ..config import WatchdogConfig
from ..database import DatabaseManager
from ..handler import FileProcessor
from ..ingestion.outcome import ProcessingOutcome, ProcessingReason, ProcessingStatus
from ..parsers.pilot_data_parser import WoFFPilotDataParser
from .test_dossier_parser import _encode_dossier


def _dossier() -> bytes:
    lines = ["Null"] * 105
    for index, value in {
        3: "Captain",
        4: "Alice",
        5: "Able",
        11: "60",
        16: "1",
        17: "1",
        41: "50",
        46: "2",
        52: "10",
        83: "No. 56 Squadron RFC",
        84: "SE.5a",
        88: "Filescamp",
        89: "Arras",
    }.items():
        lines[index] = value
    return _encode_dossier(lines, "Pilot1Dossier.txt")


def _log_record(day: int, note: str = "Synthetic mission.") -> str:
    return (
        f"{day};4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;"
        "SE.5a;No. 56 Squadron RFC;troops;Target;N50;E2;;"
        f"{note}\n"
    )


def _claim_record(day: int = 6) -> str:
    return (
        f"{day};4;1917;10;35;Arras;Filescamp;OP;SE.5a;1;"
        "Albatros D.III;Destroyed Confirmed;Albatros\n"
    )


def _squads_record() -> str:
    return (
        "6;4;1917;10;30;Flanders;Filescamp;No. 56 Squadron RFC;"
        "SE.5a;SE.5a;Enlisted, based at Filescamp, rank: Captain.;"
        "No. 56 Squadron\n"
    )


def _claim_confirmation() -> str:
    fields = [
        "6",
        "4",
        "1917",
        "10",
        "35",
        "Confirmation received of claim submitted on: 6/4/1917",
        *("synthetic" for _ in range(20)),
    ]
    return ";".join(fields) + "\n"


class LiveRuntime:
    def __init__(
        self, root: Path, database: DatabaseManager, processor: FileProcessor
    ) -> None:
        self.root = root
        self.database = database
        self.processor = processor

    def write(self, name: str, contents: str) -> Path:
        path = self.root / name
        path.write_text(contents, encoding="cp1252")
        return path

    def process(
        self,
        path: Path,
        previous: ProcessingOutcome | None = None,
    ) -> ProcessingOutcome:
        return self.processor.process(str(path), "modified", previous)

    def state(self) -> tuple[str, ...]:
        return tuple(self.database._get_conn().iterdump())

    def count(self, table: str) -> int:
        allowed = {"missions", "victories"}
        if table not in allowed:
            raise ValueError("unsupported test table")
        row = self.database._get_conn().execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()
        assert row is not None
        return int(row[0])


@pytest.fixture
def live_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[LiveRuntime]:
    root = tmp_path / "Synthetic campaign"
    root.mkdir()
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(tmp_path / "live.sqlite"),
        stability_timeout_sec=0.01,
        stability_check_interval_sec=0.001,
    )
    database = DatabaseManager(
        config.export_path, campaign_namespaces=config.campaign_namespaces
    )
    processor = FileProcessor(
        database,
        CampaignEngine(database),
        stability_timeout=config.stability_timeout_sec,
        stability_interval=config.stability_check_interval_sec,
        watch_roots=config.watch_paths,
    )
    dossier_path = root / "Pilot1Dossier.txt"
    dossier_path.write_bytes(_dossier())
    dossier_outcome = processor.process(str(dossier_path), "initial")
    assert dossier_outcome.status is ProcessingStatus.SUCCESS
    monkeypatch.setattr(
        "woff.campaign_engine.narrative_generator.generate",
        lambda *_args, **_kwargs: "Synthetic mission narrative.",
    )

    try:
        yield LiveRuntime(root, database, processor)
    finally:
        database.close()


def test_incomplete_log_is_rejected_before_any_persistent_mutation(
    live_runtime: LiveRuntime,
) -> None:
    source = live_runtime.write("Pilot1Log.txt", "1\n" + _log_record(5))
    assert live_runtime.process(source).status is ProcessingStatus.SUCCESS
    before = live_runtime.state()
    assert live_runtime.count("missions") == 1

    source.write_text(
        "2\n" + _log_record(6, "Private partial payload."),
        encoding="cp1252",
    )
    parser = WoFFPilotDataParser()
    assert parser.parse(str(source)) is True
    assert parser.declared_records == 2
    assert parser.observed_records == 1
    assert parser.is_complete is False

    outcome = live_runtime.process(source)

    assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
    assert outcome.reason is ProcessingReason.INCOMPLETE_SOURCE
    assert outcome.acknowledged_generation is None
    assert live_runtime.state() == before
    assert live_runtime.count("missions") == 1


@pytest.mark.parametrize(
    ("name", "contents"),
    [
        ("Pilot1Claims.txt", "2\n" + _claim_record()),
        ("Pilot1Squads.txt", _squads_record() + "malformed\n"),
    ],
    ids=("claims-count-mismatch", "squads-rejected-record"),
)
def test_every_pilot_parser_completeness_failure_uses_the_live_boundary(
    live_runtime: LiveRuntime,
    name: str,
    contents: str,
) -> None:
    source = live_runtime.write(name, contents)
    parser = WoFFPilotDataParser()
    assert parser.parse(str(source)) is True
    assert parser.is_complete is False
    before = live_runtime.state()

    outcome = live_runtime.process(source)

    assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
    assert outcome.reason is ProcessingReason.INCOMPLETE_SOURCE
    assert outcome.acknowledged_generation is None
    assert live_runtime.state() == before


def test_complete_log_and_supported_non_mission_record_still_process(
    live_runtime: LiveRuntime,
) -> None:
    source = live_runtime.write(
        "Pilot1Log.txt", "2\n" + _log_record(6) + _claim_confirmation()
    )
    parser = WoFFPilotDataParser()
    assert parser.parse(str(source)) is True
    assert parser.declared_records == parser.observed_records == 2
    assert parser.is_complete is True
    assert len(parser.missions) == 1

    outcome = live_runtime.process(source)

    assert outcome.status is ProcessingStatus.SUCCESS
    assert live_runtime.count("missions") == 1


def test_complete_claims_source_still_processes(live_runtime: LiveRuntime) -> None:
    source = live_runtime.write("Pilot1Claims.txt", "1\n" + _claim_record())

    outcome = live_runtime.process(source)

    assert outcome.status is ProcessingStatus.SUCCESS
    assert live_runtime.count("victories") == 1


@pytest.mark.parametrize("name", ("Pilot1Log.txt", "Pilot1Claims.txt"))
def test_valid_zero_record_generation_remains_acknowledged_without_mutation(
    live_runtime: LiveRuntime,
    name: str,
) -> None:
    source = live_runtime.write(name, "0\n")
    before = live_runtime.state()

    outcome = live_runtime.process(source)

    assert outcome.status is ProcessingStatus.SUCCESS
    assert outcome.reason is ProcessingReason.SUCCESS
    assert live_runtime.state() == before


def test_malformed_source_remains_distinct_from_proven_incomplete_source(
    live_runtime: LiveRuntime,
) -> None:
    source = live_runtime.write("Pilot1Log.txt", "\n")
    parser = WoFFPilotDataParser()
    assert parser.parse(str(source)) is False
    assert parser.is_complete is True
    assert parser.valid_empty is False

    outcome = live_runtime.process(source)

    assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
    assert outcome.reason is ProcessingReason.PARSER_REJECTED


def test_later_complete_generation_succeeds_and_replay_is_idempotent(
    live_runtime: LiveRuntime,
) -> None:
    source = live_runtime.write("Pilot1Log.txt", "2\n" + _log_record(6))
    incomplete = live_runtime.process(source)
    assert incomplete.reason is ProcessingReason.INCOMPLETE_SOURCE
    assert live_runtime.count("missions") == 0

    source.write_text("1\n" + _log_record(6), encoding="cp1252")
    complete = live_runtime.process(source, incomplete)
    assert complete.status is ProcessingStatus.SUCCESS
    assert live_runtime.count("missions") == 1
    persisted = live_runtime.state()

    replay = live_runtime.process(source, complete)

    assert replay.status is ProcessingStatus.UNCHANGED
    assert replay.generation == complete.generation
    assert live_runtime.state() == persisted
    assert live_runtime.count("missions") == 1


def test_incomplete_diagnostic_is_bounded_and_contains_no_private_data(
    live_runtime: LiveRuntime,
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = live_runtime.write(
        "Pilot1Log.txt",
        "2\n" + _log_record(6, "DO-NOT-LOG private campaign contents."),
    )
    caplog.clear()

    outcome = live_runtime.process(source)

    assert outcome.reason is ProcessingReason.INCOMPLETE_SOURCE
    messages = [record.getMessage() for record in caplog.records]
    assert any("category=incomplete-source" in message for message in messages)
    assert all(str(live_runtime.root) not in message for message in messages)
    assert all("DO-NOT-LOG" not in message for message in messages)
    assert all(len(message) <= 240 for message in messages)
