from dataclasses import dataclass
import os
import threading
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from ..campaign_namespace import campaign_namespace_for_root
from ..handler import FileProcessor, FileStabilityGuard
from ..campaign_engine import CampaignEngine
from ..database import DatabaseManager
from ..ingestion.outcome import ProcessingReason, ProcessingStatus
from ..ingestion.scheduler import EventScheduler
from ..ingestion.snapshot import (
    FileGeneration,
    SnapshotFailure,
    SnapshotFailureKind,
    StableFileSnapshot,
    StableSnapshotReader,
)
from ..identity import (
    PilotIdentityEvidence,
    PilotIdentityKind,
    PilotIdentityUnavailable,
)
from ..models import WoFFMission, WoFFPilot, WoFFWingman
from ..narrative_generator import narrative_generator
from .identity_support import dossier_evidence


def _scheduler_metrics(**overrides):
    values = {
        "queued": 0,
        "active": 0,
        "coalesced": 0,
        "rejected": 0,
        "retried": 0,
        "saturated": 0,
        "shutdown_rejected": 0,
        "submission_failures": 0,
        "permanent_rejections": 0,
        "transient_failures": 0,
        "transient_retries": 0,
        "successful_replays": 0,
        "retry_pending": 0,
        "retry_exhausted": 0,
        "retry_shutdown": 0,
        "superseded_retries": 0,
    }
    values.update(overrides)
    return values


@dataclass
class FakeMetadata:
    st_size: int
    st_mtime_ns: int
    st_ctime_ns: int
    st_dev: int
    st_ino: int


class ScriptedFilesystem:
    def __init__(self, generations):
        self.generations = iter(generations)
        self.current = None
        self.stats = 0

    def stat(self, path):
        if self.current is None:
            self.current = next(self.generations)
        value = self.current
        if isinstance(value, BaseException):
            self.current = None
            raise value
        result = FakeMetadata(len(value[0]), value[1], value[1], 1, value[2])
        self.stats += 1
        if self.stats % 2 == 0:
            self.current = None
        return result

    def read(self, path):
        value = self.current
        assert value is not None
        if isinstance(value, BaseException):
            raise value
        return value[0]


def reader(fs, attempts=4):
    return StableSnapshotReader(
        timeout=attempts, interval=1, stat=fs.stat, read=fs.read, sleep=lambda _: None
    )


@pytest.mark.parametrize("generations", [
    [(b"AAAA", 1, 1), (b"BBBB", 2, 1), (b"BBBB", 2, 1)],  # same size rewrite
    [(b"AAAA", 1, 1), (b"AA", 2, 1), (b"AA", 2, 1)],      # truncate
    [(b"AAAA", 1, 1), (b"BBBB", 2, 2), (b"BBBB", 2, 2)],  # replace
])
def test_changed_generation_is_never_returned_until_reverified(generations):
    snapshot = reader(ScriptedFilesystem(generations)).acquire("Pilot1Log.txt")
    assert snapshot.data == generations[-1][0]
    assert snapshot.attempts == 3


def test_temporary_sharing_violation_retries_then_succeeds():
    fs = ScriptedFilesystem([PermissionError("sharing"), (b"ok", 2, 1), (b"ok", 2, 1)])
    snapshot = reader(fs).acquire("mission.log")
    assert snapshot.data == b"ok"
    assert snapshot.attempts == 3


@pytest.mark.parametrize("error, kind", [
    (FileNotFoundError(), SnapshotFailureKind.INACCESSIBLE),
    (PermissionError(), SnapshotFailureKind.INACCESSIBLE),
])
def test_disappearance_or_denial_exhaustion_has_one_final_state(error, kind):
    fs = ScriptedFilesystem([error, error, error])
    with pytest.raises(SnapshotFailure) as caught:
        reader(fs, attempts=3).acquire("private/Pilot1Log.txt")
    assert caught.value.kind is kind
    assert caught.value.attempts == 3
    assert "private" not in str(caught.value)


def test_continuous_generation_change_is_strictly_bounded():
    fs = ScriptedFilesystem([(b"x", i, i) for i in range(1, 5)])
    with pytest.raises(SnapshotFailure) as caught:
        reader(fs, attempts=4).acquire("Pilot1Log.txt")
    assert caught.value.kind is SnapshotFailureKind.CHANGED
    assert caught.value.attempts == 4


def test_retry_uses_exponential_backoff_with_bounded_total_delay():
    sleeps = []
    fs = ScriptedFilesystem([PermissionError()] * 6)
    snapshot_reader = StableSnapshotReader(
        timeout=5, interval=1, stat=fs.stat, read=fs.read, sleep=sleeps.append
    )
    with pytest.raises(SnapshotFailure):
        snapshot_reader.acquire("Pilot1Log.txt")
    assert sleeps == [1, 2, 2]
    assert sum(sleeps) == snapshot_reader.timeout
    assert snapshot_reader.max_attempts == 4


class IntraObservationRace:
    def __init__(self, observations):
        self.observations = iter(observations)
        self.observation = None
        self.after_read = False

    def stat(self, path):
        if self.observation is None:
            self.observation = next(self.observations)
            self.after_read = False
        metadata = self.observation[2 if self.after_read else 0]
        if self.after_read:
            self.observation = None
        return FakeMetadata(metadata[0], metadata[1], metadata[1], 1, metadata[2])

    def read(self, path):
        assert self.observation is not None
        self.after_read = True
        return self.observation[1]


@pytest.mark.parametrize("raced", [
    ((4, 1, 1), b"AA", (2, 2, 1)),       # truncate while reading
    ((4, 1, 1), b"BBBB", (4, 2, 2)),     # atomic replacement while reading
])
def test_intra_observation_race_is_discarded(raced):
    stable = ((2, 3, 3), b"ok", (2, 3, 3))
    fs = IntraObservationRace([raced, stable, stable])
    snapshot = StableSnapshotReader(
        timeout=4, interval=1, stat=fs.stat, read=fs.read, sleep=lambda _: None
    ).acquire("Pilot1Log.txt")
    assert snapshot.data == b"ok"
    assert snapshot.attempts == 3


def test_custom_reader_partial_bytes_are_rejected_even_with_unchanged_metadata():
    partial = ((4, 1, 1), b"AA", (4, 1, 1))
    fs = IntraObservationRace([partial, partial, partial])
    with pytest.raises(SnapshotFailure) as caught:
        StableSnapshotReader(
            timeout=3, interval=1, stat=fs.stat, read=fs.read, sleep=lambda _: None
        ).acquire("Pilot1Log.txt")
    assert caught.value.kind is SnapshotFailureKind.CHANGED


def test_processor_parses_exact_verified_bytes_after_source_changes(tmp_path, monkeypatch):
    path = tmp_path / "campaign.xml"
    verified = b"<Campaign><PilotName>Verified Pilot</PilotName></Campaign>"
    path.write_bytes(b"different later generation")
    snapshot = StableFileSnapshot(
        verified, str(path), path.name,
        FileGeneration(1, 1, len(verified), 1, 1, "d" * 64), 2,
    )
    received = []

    class Parser:
        pilot = None
        missions = []
        victories = []
        decorations = []

        def parse_bytes(self, data, name):
            received.append((data, name))
            return False

    monkeypatch.setattr("woff.handler.WoFFXMLParser", Parser)
    processor = FileProcessor(cast(Any, object()), cast(Any, object()))
    processor._process_xml(str(path), snapshot)
    assert received == [(verified, "campaign.xml")]


def test_unsupported_text_filename_never_reaches_snapshot_reader():
    processor = FileProcessor(cast(Any, object()), cast(Any, object()))
    processor.guard = cast(Any, MagicMock())

    outcome = processor.process(
        r"C:\Users\Alice\activation_key.txt", "created"
    )
    assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
    assert outcome.reason is ProcessingReason.UNSUPPORTED_SOURCE
    processor.guard.acquire.assert_not_called()


@pytest.mark.parametrize("event_type", ["initial", "modified"])
def test_dossier_side_effects_never_use_filesystem_timestamp(
    event_type, monkeypatch
):
    modified_ns = 1_493_596_200_000_000_000
    snapshot = StableFileSnapshot(
        b"verified", "Pilot1Dossier.txt", "Pilot1Dossier.txt",
        FileGeneration(1, 1, 8, modified_ns, modified_ns, "d" * 64), 2,
    )
    pilot = MagicMock(name="pilot")
    pilot.name = "Verified Pilot"
    pilot.status = "Active"
    pilot.rank = "Captain"
    pilot.startDate = "1917-04-01"

    class Parser:
        decorations = []
        wingmen = [MagicMock()]

        def __init__(self):
            self.pilot = pilot

        def parse_bytes(self, data, name):
            return True

    monkeypatch.setattr("woff.handler.WoFFDossierParser", Parser)
    database = MagicMock()
    engine = MagicMock()
    engine.process_dossier_import.return_value = "pilot-id"
    processor = FileProcessor(database, engine)
    processor.guard = MagicMock()
    processor.guard.acquire.return_value = snapshot

    outcome = processor.process("Pilot1Dossier.txt", event_type)
    assert outcome.status is ProcessingStatus.SUCCESS
    assert outcome.generation == snapshot.generation

    engine.process_dossier_import.assert_called_once()
    call = engine.process_dossier_import.call_args
    assert call.kwargs["pilot"] is pilot
    assert call.kwargs["decorations"] == Parser.decorations
    assert call.kwargs["wingmen"] == Parser.wingmen
    assert call.kwargs["identity"] == PilotIdentityEvidence(
        PilotIdentityKind.DOSSIER,
        1,
        "d" * 64,
        processor._campaign_namespaces.namespace_for(snapshot.path),
    )
    assert "event_date" not in call.kwargs


@pytest.mark.parametrize(("path", "parser_target"), [
    ("campaign.xml", "woff.handler.WoFFXMLParser"),
    ("Pilot1Dossier.txt", "woff.handler.WoFFDossierParser"),
    ("mission.log", "woff.handler.WoFFMissionLogParser"),
    ("Pilot1Log.txt", "woff.handler.WoFFPilotDataParser"),
    ("Pilot1Claims.txt", "woff.handler.WoFFPilotDataParser"),
    ("Pilot1Squads.txt", "woff.handler.WoFFPilotDataParser"),
])
def test_live_routing_supplies_verified_bytes_and_original_name(
    path, parser_target, monkeypatch
):
    received = []

    class Parser:
        pilot = None
        missions = []
        victories = []
        decorations = []

        def parse_bytes(self, data, name):
            received.append((data, name))
            return False

    monkeypatch.setattr(parser_target, Parser)
    processor = FileProcessor(cast(Any, object()), cast(Any, object()))
    snapshot = StableFileSnapshot(
        b"verified", path, path,
        FileGeneration(1, 1, 8, 1, 1, "d" * 64), 2,
    )
    if path.endswith(".xml"):
        processor._process_xml(path, snapshot)
    else:
        processor._process_text(path, path.lower(), snapshot)
    assert received == [(b"verified", path)]


def test_scheduler_releases_exhausted_snapshot_without_diagnostic_leak(caplog):
    personal_path = r"C:\Users\Alice\Campaigns\Pilot1Log.txt"
    filesystem = ScriptedFilesystem([PermissionError()] * 3)
    processor = FileProcessor(cast(Any, object()), cast(Any, object()))
    processor.guard = FileStabilityGuard(
        timeout=3, interval=1, stat=filesystem.stat, read=filesystem.read,
        sleep=lambda _: None,
    )
    scheduler = EventScheduler(processor.process, max_workers=1, max_pending_events=1)
    assert scheduler.submit(personal_path, "modified")
    scheduler.shutdown()

    metrics = scheduler.metrics()
    assert scheduler.admitted_paths == 0
    assert metrics == _scheduler_metrics(permanent_rejections=1)
    diagnostics = [r.getMessage() for r in caplog.records if "Snapshot rejected" in r.getMessage()]
    assert diagnostics == [
        "Snapshot rejected: source=Pilot1Log.txt state=inaccessible attempts=3"
    ]
    assert "Users" not in diagnostics[0]
    assert "Campaigns" not in diagnostics[0]


def test_active_acquisition_and_pending_event_persist_new_generation_once():
    generation_a = b"<Campaign><PilotName>Generation A</PilotName></Campaign>"
    generation_b = b"<Campaign><PilotName>Generation B</PilotName></Campaign>"
    blocked = threading.Event()
    resume = threading.Event()

    class MutableFilesystem:
        def __init__(self):
            self.data = generation_a
            self.version = 1
            self.reads = 0
            self.lock = threading.Lock()

        def stat(self, path):
            with self.lock:
                return FakeMetadata(
                    len(self.data), self.version, self.version, 1, self.version
                )

        def read(self, path):
            with self.lock:
                self.reads += 1
                should_block = self.reads == 2
            if should_block:
                blocked.set()
                assert resume.wait(2)
            with self.lock:
                return self.data

        def replace(self):
            with self.lock:
                self.data = generation_b
                self.version = 2

    filesystem = MutableFilesystem()
    database = cast(Any, MagicMock())
    database.merge_and_write.return_value = "pilot-id"
    processor = FileProcessor(database, cast(Any, object()))
    processor.guard = FileStabilityGuard(
        timeout=4, interval=1, stat=filesystem.stat, read=filesystem.read,
        sleep=lambda _: None,
    )
    scheduler = EventScheduler(
        processor.process,
        max_workers=1,
        max_pending_events=1,
        retry_process=lambda path, event, previous: processor.process(
            path, event, previous_generation=previous
        ),
    )

    path = r"C:\Campaign\campaign.xml"
    assert scheduler.submit(path, "created")
    assert blocked.wait(2)
    filesystem.replace()
    assert scheduler.submit(r"c:/campaign/CAMPAIGN.XML", "modified")
    resume.set()
    scheduler.shutdown()

    assert database.merge_and_write.call_count == 1
    assert database.merge_and_write.call_args.kwargs["pilot"].name == "Generation B"
    assert scheduler.admitted_paths == 0
    assert scheduler.metrics() == _scheduler_metrics(coalesced=1, retried=1)


def test_unresolved_identity_does_not_acknowledge_coalesced_generation(monkeypatch):
    path = r"C:\Campaign\Pilot1Log.txt"
    snapshot = StableFileSnapshot(
        b"verified", path, "Pilot1Log.txt",
        FileGeneration(1, 1, 8, 1, 1, "d" * 64), 2,
    )
    merge_started = threading.Event()
    dossier_ready = threading.Event()
    database = cast(Any, MagicMock())

    pilot = MagicMock()
    pilot.name = "Pilot 1"
    pilot.source_file = "Pilot1Log.txt"

    class Parser:
        def __init__(self):
            self.pilot = pilot
            self.missions = [MagicMock(date="1917-01-01", time="08:00", id="m1")]
            self.victories = [MagicMock()]

        def parse_bytes(self, data, name):
            return True

    first_merge = True

    def merge(**_kwargs):
        nonlocal first_merge
        if first_merge:
            first_merge = False
            merge_started.set()
            assert dossier_ready.wait(2)
            raise PilotIdentityUnavailable("missing-dossier-binding", 1)
        return "pilot-id"

    database.merge_and_write.side_effect = merge
    database.get_mission_id_by_natural_key.return_value = "m1"
    engine = cast(Any, MagicMock())
    engine.process_mission_end.return_value = True
    monkeypatch.setattr("woff.handler.WoFFPilotDataParser", Parser)
    processor = FileProcessor(database, engine)
    processor.guard = cast(Any, MagicMock())
    processor.guard.acquire.return_value = snapshot
    scheduler = EventScheduler(
        processor.process, max_workers=2, max_pending_events=2,
        retry_process=lambda submitted_path, event, previous: processor.process(
            submitted_path, event, previous_generation=previous
        ),
    )

    assert scheduler.submit(path, "modified")
    assert merge_started.wait(2)
    assert scheduler.submit(path.upper(), "initial")
    dossier_ready.set()
    scheduler.shutdown()

    assert database.merge_and_write.call_count == 2
    persisted = database.merge_and_write.call_args.kwargs
    assert persisted["pilot"] is pilot
    assert len(persisted["missions"]) == len(persisted["victories"]) == 1
    assert persisted["decorations"] == []
    assert processor.guard.acquire.call_count == 4
    assert scheduler.admitted_paths == 0
    assert scheduler.metrics()["retried"] == 1


@pytest.mark.parametrize(
    ("path", "parser_target"),
    [
        ("campaign.xml", "woff.handler.WoFFXMLParser"),
        ("Pilot1Dossier.txt", "woff.handler.WoFFDossierParser"),
        ("mission.log", "woff.handler.WoFFMissionLogParser"),
        ("Pilot1Log.txt", "woff.handler.WoFFPilotDataParser"),
        ("Pilot1Claims.txt", "woff.handler.WoFFPilotDataParser"),
        ("Pilot1Squads.txt", "woff.handler.WoFFPilotDataParser"),
    ],
)
def test_merge_rejection_never_acknowledges_any_ingestion_route(
    path, parser_target, monkeypatch
):
    pilot = MagicMock(name="pilot", source_file=path)

    class Parser:
        def __init__(self):
            self.pilot = pilot
            self.mission = MagicMock()
            self.missions = []
            self.victories = []
            self.decorations = []
            self.wingmen = []

        def parse_bytes(self, data, name):
            return True

    monkeypatch.setattr(parser_target, Parser)
    database = cast(Any, MagicMock())
    database.resolve_bound_dossier_id.return_value = None
    database.merge_and_write.return_value = None
    engine = cast(Any, MagicMock())
    if path == "Pilot1Dossier.txt":
        engine.process_dossier_import.return_value = None
    processor = FileProcessor(database, engine)
    snapshot = StableFileSnapshot(
        b"verified", path, path,
        FileGeneration(1, 1, 8, 1, 1, "d" * 64), 2,
    )
    processor.guard = cast(Any, MagicMock())
    processor.guard.acquire.return_value = snapshot

    outcome = processor.process(path, "initial")
    assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
    if path == "Pilot1Dossier.txt":
        engine.process_dossier_import.assert_called_once()
        database.merge_and_write.assert_not_called()
    else:
        database.merge_and_write.assert_called_once()


def test_merge_rejection_retries_same_generation_then_acknowledges_once(monkeypatch):
    path = r"C:\Campaign\Pilot1Log.txt"
    snapshot = StableFileSnapshot(
        b"verified", path, "Pilot1Log.txt",
        FileGeneration(1, 1, 8, 1, 1, "d" * 64), 2,
    )
    first_merge_started = threading.Event()
    allow_failure = threading.Event()
    database = cast(Any, MagicMock())
    merge_results = iter((None, "pilot-id"))

    pilot = MagicMock(name="pilot", source_file="Pilot1Log.txt")
    mission = MagicMock(date="1917-01-01", time="08:00", id="m1")

    class Parser:
        def __init__(self):
            self.pilot = pilot
            self.missions = [mission]
            self.victories = [MagicMock()]

        def parse_bytes(self, data, name):
            return True

    def merge(**_kwargs):
        result = next(merge_results)
        if result is None:
            first_merge_started.set()
            assert allow_failure.wait(2)
        return result

    database.merge_and_write.side_effect = merge
    database.get_mission_id_by_natural_key.return_value = "m1"
    engine = cast(Any, MagicMock())
    engine.process_mission_end.return_value = True
    monkeypatch.setattr("woff.handler.WoFFPilotDataParser", Parser)
    processor = FileProcessor(database, engine)
    processor.guard = cast(Any, MagicMock())
    processor.guard.acquire.return_value = snapshot
    scheduler = EventScheduler(
        processor.process, max_workers=2, max_pending_events=2,
        retry_process=lambda submitted_path, event, previous: processor.process(
            submitted_path, event, previous_generation=previous
        ),
    )

    assert scheduler.submit(path, "modified")
    assert first_merge_started.wait(2)
    assert scheduler.submit(path.upper(), "initial")
    allow_failure.set()
    scheduler.shutdown()

    assert database.merge_and_write.call_count == 2
    engine.process_mission_end.assert_called_once_with("pilot-id", "m1")
    assert scheduler.admitted_paths == 0
    assert scheduler.metrics() == _scheduler_metrics(
        coalesced=1, retried=1, permanent_rejections=1
    )


def test_explicit_derived_failure_does_not_acknowledge_generation(monkeypatch):
    path = "Pilot1Log.txt"
    pilot = MagicMock(name="pilot", source_file=path)
    mission = MagicMock(date="1917-01-01", time="08:00", id="m1")

    class Parser:
        def __init__(self):
            self.pilot = pilot
            self.missions = [mission]
            self.victories = []
            self.decorations = []

        def parse_bytes(self, data, name):
            return True

    monkeypatch.setattr("woff.handler.WoFFPilotDataParser", Parser)
    database = cast(Any, MagicMock())
    database.merge_and_write.return_value = "pilot-id"
    database.get_mission_id_by_natural_key.return_value = "m1"
    engine = cast(Any, MagicMock())
    engine.process_mission_end.return_value = False
    processor = FileProcessor(database, engine)
    processor.guard = cast(Any, MagicMock())
    processor.guard.acquire.return_value = StableFileSnapshot(
        b"verified", path, path,
        FileGeneration(1, 1, 8, 1, 1, "d" * 64), 2,
    )

    assert (
        processor.process(path, "initial").status
        is ProcessingStatus.PERMANENT_REJECTION
    )
    engine.process_mission_end.assert_called_once_with("pilot-id", "m1")


def test_dossier_rejection_rolls_back_derived_effects_and_retry_commits_once(
    tmp_path, monkeypatch
):
    database = DatabaseManager(str(tmp_path / "dossier-rollback.db"))
    pilot_id = "pilot-1"
    pilot_name = "Arthur Test"
    old_pilot = WoFFPilot(
        id=pilot_id, name=pilot_name, rank="Lieutenant", status="Active",
        startDate="1917-04-30",
        source_file="Pilot1Dossier.txt",
    )
    old_wingman = WoFFWingman(
        id="wingman-1", pilotId=pilot_id, rank="Sergeant",
        fName="William", sName="Test", status="Active",
    )
    assert database.merge_and_write(
        old_pilot,
        [],
        [],
        [],
        [old_wingman],
        identity=dossier_evidence(
            1,
            "rollback-old",
            campaign_namespace_for_root(str(tmp_path)),
        ),
    ) == pilot_id
    assert database.save_diary_entry(
        pilot_id, None, "1917-04-30", "existing diary entry"
    )

    new_pilot = WoFFPilot(
        id=pilot_id, name=pilot_name, rank="Captain", status="Wounded",
        startDate="1917-04-30",
        source_file="Pilot1Dossier.txt",
    )
    new_wingman = WoFFWingman(
        id="wingman-1", pilotId=pilot_id, rank="Sergeant",
        fName="William", sName="Test", status="KIA",
    )
    parser_calls = []

    class Parser:
        def __init__(self):
            self.pilot = new_pilot
            self.wingmen = [new_wingman]
            self.decorations = []

        def parse_bytes(self, data, name):
            parser_calls.append((data, name))
            return True

    monkeypatch.setattr("woff.handler.WoFFDossierParser", Parser)
    monkeypatch.setattr(
        narrative_generator, "generate_life_event",
        lambda *_args: "deterministic life event",
    )
    monkeypatch.setattr(
        narrative_generator, "generate_wingman_event",
        lambda *_args: "deterministic wingman event",
    )

    original_merge = database.merge_and_write
    merge_calls = 0

    def reject_once(*args, **kwargs):
        nonlocal merge_calls
        merge_calls += 1
        if merge_calls == 1:
            return None
        return original_merge(*args, **kwargs)

    monkeypatch.setattr(database, "merge_and_write", reject_once)
    path = str(tmp_path / "Pilot1Dossier.txt")
    generation = FileGeneration(
        1, 1, 8, 1_493_596_200_000_000_000, 1, "d" * 64
    )
    snapshot = StableFileSnapshot(
        b"verified", path, "Pilot1Dossier.txt", generation, 2,
    )
    processor = FileProcessor(database, CampaignEngine(database))
    processor.guard = cast(Any, MagicMock())
    processor.guard.acquire.return_value = snapshot

    def diary_rows():
        return database._get_conn().execute(
            "SELECT narrative FROM diary_entries WHERE pilotId = ? ORDER BY narrative",
            (pilot_id,),
        ).fetchall()

    try:
        assert (
            processor.process(path, "initial").status
            is ProcessingStatus.PERMANENT_REJECTION
        )
        assert database.get_pilot_state(pilot_name) == ("Active", "Lieutenant")
        assert database.get_wingmen_by_pilot(pilot_id) == [
            {"fName": "William", "sName": "Test", "status": "Active"}
        ]
        assert diary_rows() == [("existing diary entry",)]

        acknowledged = processor.process(path, "initial")
        assert acknowledged.status is ProcessingStatus.SUCCESS
        assert acknowledged.generation == generation
        assert database.get_pilot_state(pilot_name) == ("Wounded", "Captain")
        assert database.get_wingmen_by_pilot(pilot_id) == [
            {"fName": "William", "sName": "Test", "status": "KIA"}
        ]
        assert diary_rows() == [
            ("deterministic life event",),
            ("deterministic wingman event",),
            ("existing diary entry",),
        ]

        unchanged = processor.process(
            path, "modified", previous_generation=acknowledged
        )
        assert unchanged.status is ProcessingStatus.UNCHANGED
        assert unchanged.generation == generation
        assert merge_calls == 2
        assert len(parser_calls) == 2
        assert database.get_pilot_state(pilot_name) == ("Wounded", "Captain")
        assert database.get_wingmen_by_pilot(pilot_id) == [
            {"fName": "William", "sName": "Test", "status": "KIA"}
        ]
        assert diary_rows() == [
            ("deterministic life event",),
            ("deterministic wingman event",),
            ("existing diary entry",),
        ]
    finally:
        database.close()


def test_incoming_dossier_date_preserves_pre_merge_wingman_event(
    tmp_path, monkeypatch
):
    database = DatabaseManager(str(tmp_path / "dossier-first-date.db"))
    pilot_id = "pilot-first-date"
    pilot_name = "Arthur First Date"
    old_pilot = WoFFPilot(
        id=pilot_id, name=pilot_name, rank="Lieutenant", status="Active",
        source_file="Pilot1Dossier.txt",
    )
    old_wingman = WoFFWingman(
        id="wingman-first-date", pilotId=pilot_id, rank="Sergeant",
        fName="William", sName="First Date", status="Active",
    )
    assert database.merge_and_write(
        old_pilot,
        [],
        [],
        [],
        [old_wingman],
        identity=dossier_evidence(
            1,
            "first-date-old",
            campaign_namespace_for_root(str(tmp_path)),
        ),
    ) == pilot_id
    assert database.get_pilot_game_date(pilot_id) is None

    new_pilot = WoFFPilot(
        id=pilot_id, name=pilot_name, rank="Lieutenant", status="Active",
        startDate="1917-04-30", source_file="Pilot1Dossier.txt",
    )
    new_wingman = WoFFWingman(
        id="wingman-first-date", pilotId=pilot_id, rank="Sergeant",
        fName="William", sName="First Date", status="KIA",
    )

    class Parser:
        def __init__(self):
            self.pilot = new_pilot
            self.wingmen = [new_wingman]
            self.decorations = []

        def parse_bytes(self, data, name):
            return True

    monkeypatch.setattr("woff.handler.WoFFDossierParser", Parser)
    monkeypatch.setattr(
        narrative_generator, "generate_wingman_event",
        lambda *_args: "first dated wingman event",
    )

    path = str(tmp_path / "Pilot1Dossier.txt")
    generation = FileGeneration(
        1, 1, 8, 1_493_596_200_000_000_000, 1, "d" * 64
    )
    snapshot = StableFileSnapshot(
        b"verified", path, "Pilot1Dossier.txt", generation, 2,
    )
    processor = FileProcessor(database, CampaignEngine(database))
    processor.guard = cast(Any, MagicMock())
    processor.guard.acquire.return_value = snapshot

    try:
        outcome = processor.process(path, "initial")
        assert outcome.status is ProcessingStatus.SUCCESS
        assert outcome.generation == generation
        assert database.get_wingmen_by_pilot(pilot_id) == [
            {"fName": "William", "sName": "First Date", "status": "KIA"}
        ]
        assert database._get_conn().execute(
            """
            SELECT entry_date, narrative FROM diary_entries
            WHERE pilotId = ?
            """,
            (pilot_id,),
        ).fetchall() == [("1917-04-30", "first dated wingman event")]
    finally:
        database.close()


def test_mission_retry_uses_persisted_natural_identity_and_acknowledges_once(
    tmp_path, monkeypatch
):
    database = DatabaseManager(str(tmp_path / "pilot-log.db"))
    pilot = WoFFPilot(
        id="pilot-1", name="Mission Pilot", rank="Lieutenant",
        source_file="Pilot1Dossier.txt",
    )
    identity = PilotIdentityEvidence(
        PilotIdentityKind.DOSSIER,
        1,
        "d" * 64,
        campaign_namespace_for_root(str(tmp_path)),
    )
    assert database.merge_and_write(
        pilot, [], [], [], identity=identity
    ) == pilot.id
    partial_pilot = WoFFPilot(
        id="partial-pilot", name="Pilot 1", source_file="Pilot1Log.txt"
    )
    parser_ids = iter(("provisional-1", "provisional-2"))
    parsed_ids = []

    class Parser:
        def __init__(self):
            mission = WoFFMission(
                id=next(parser_ids), date="1917-05-01", time="08:00",
                missionType="Patrol", aircraft="Sopwith Camel",
                source_file="Pilot1Log.txt",
            )
            parsed_ids.append(mission.id)
            self.pilot = partial_pilot
            self.missions = [mission]
            self.victories = []
            self.decorations = []

        def parse_bytes(self, data, name):
            return True

    monkeypatch.setattr("woff.handler.WoFFPilotDataParser", Parser)
    real_engine = CampaignEngine(database)

    class RecoveringEngine:
        def __init__(self):
            self.calls = []

        def process_mission_end(self, pilot_id, mission_id):
            self.calls.append((pilot_id, mission_id))
            if len(self.calls) == 1:
                return None
            return real_engine.process_mission_end(pilot_id, mission_id)

    engine = RecoveringEngine()
    processor = FileProcessor(database, cast(Any, engine))
    path = str(tmp_path / "Pilot1Log.txt")
    generation = FileGeneration(1, 1, 8, 1, 1, "d" * 64)
    processor.guard = cast(Any, MagicMock())
    processor.guard.acquire.return_value = StableFileSnapshot(
        b"verified", path, os.path.basename(path), generation, 2,
    )
    try:
        first = processor.process(path, "created")
        assert first.status is ProcessingStatus.PERMANENT_REJECTION
        recovered = processor.process(path, "modified")
        assert recovered.status is ProcessingStatus.SUCCESS
        assert recovered.generation == generation
        persisted = database._get_conn().execute(
            "SELECT id FROM missions"
        ).fetchall()
        assert persisted == [("provisional-1",)]
        assert parsed_ids == ["provisional-1", "provisional-2"]
        assert engine.calls == [
            (pilot.id, "provisional-1"), (pilot.id, "provisional-1")
        ]
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM pilot_rpg_stats"
        ).fetchone() == (1,)
        assert database._get_conn().execute(
            "SELECT COUNT(*), MIN(missionId) FROM diary_entries"
        ).fetchone() == (1, "provisional-1")

        unchanged = processor.process(
            path, "modified", previous_generation=generation
        )
        assert unchanged.status is ProcessingStatus.UNCHANGED
        assert unchanged.generation == generation
        assert parsed_ids == ["provisional-1", "provisional-2"]
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM missions"
        ).fetchone() == (1,)
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM diary_entries"
        ).fetchone() == (1,)
    finally:
        database.close()


@pytest.mark.parametrize(
    ("seed_existing", "expected_old", "expected_narratives"),
    [
        (False, [], []),
        (True, [("Active", "Lieutenant")], [("promotion",)]),
    ],
)
def test_dossier_life_event_receives_original_optional_prior_state(
    seed_existing, expected_old, expected_narratives, tmp_path, monkeypatch
):
    database = DatabaseManager(str(tmp_path / f"prior-{seed_existing}.db"))
    pilot = WoFFPilot(
        id="pilot-1", name="State Pilot", rank="Captain", status="Active",
        startDate="1917-04-30",
        source_file="Pilot1Dossier.txt",
    )
    if seed_existing:
        old = WoFFPilot(
            id=pilot.id, name=pilot.name, rank="Lieutenant", status="Active",
            startDate="1917-04-30",
            source_file=pilot.source_file,
        )
        assert database.merge_and_write(
            old,
            [],
            [],
            [],
            identity=PilotIdentityEvidence(
                PilotIdentityKind.DOSSIER,
                1,
                "a" * 64,
                campaign_namespace_for_root(str(tmp_path)),
            ),
        ) == pilot.id

    class Parser:
        decorations = []
        wingmen = []

        def __init__(self):
            self.pilot = pilot

        def parse_bytes(self, data, name):
            return True

    captured = []

    def narrative(new_status, old_status, new_rank, old_rank):
        captured.append((old_status, old_rank))
        return "welcome" if old_status is None else "promotion"

    monkeypatch.setattr("woff.handler.WoFFDossierParser", Parser)
    monkeypatch.setattr(narrative_generator, "generate_life_event", narrative)
    processor = FileProcessor(database, CampaignEngine(database))
    path = str(tmp_path / "Pilot1Dossier.txt")
    processor.guard = cast(Any, MagicMock())
    processor.guard.acquire.return_value = StableFileSnapshot(
        b"verified", path, "Pilot1Dossier.txt",
        FileGeneration(1, 1, 8, 1, 1, "d" * 64), 2,
    )
    try:
        assert (
            processor.process(path, "initial").status
            is ProcessingStatus.SUCCESS
        )
        assert captured == expected_old
        assert database._get_conn().execute(
            "SELECT narrative FROM diary_entries"
        ).fetchall() == expected_narratives
    finally:
        database.close()
