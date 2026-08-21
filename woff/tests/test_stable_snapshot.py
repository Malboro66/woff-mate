from dataclasses import dataclass
import threading
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from ..handler import FileProcessor, FileStabilityGuard
from ..ingestion.scheduler import EventScheduler
from ..ingestion.snapshot import (
    FileGeneration,
    SnapshotFailure,
    SnapshotFailureKind,
    StableFileSnapshot,
    StableSnapshotReader,
)


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
        FileGeneration(1, 1, len(verified), 1, 1, "digest"), 2,
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
        FileGeneration(1, 1, 8, 1, 1, "digest"), 2,
    )
    if path.endswith(".xml"):
        processor._process_xml(path, snapshot)
    else:
        processor._process_text(path, path.lower(), snapshot)
    assert received == [(b"verified", path)]


def test_scheduler_releases_exhausted_snapshot_without_diagnostic_leak(caplog):
    personal_path = r"C:\Users\Alice\Campaigns\private-Pilot1Log.txt"
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
    assert metrics == {
        "queued": 0, "active": 0, "coalesced": 0, "rejected": 0, "retried": 0,
    }
    diagnostics = [r.getMessage() for r in caplog.records if "Snapshot rejected" in r.getMessage()]
    assert diagnostics == [
        "Snapshot rejected: source=private-Pilot1Log.txt state=inaccessible attempts=3"
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
    assert scheduler.metrics() == {
        "queued": 0, "active": 0, "coalesced": 1, "rejected": 0, "retried": 1,
    }
