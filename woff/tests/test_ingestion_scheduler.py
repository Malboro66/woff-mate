import threading
from unittest.mock import Mock

import pytest

from ..ingestion.scheduler import EventScheduler, canonical_windows_path


def _metrics(**overrides):
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
        "dependency_pending": 0,
        "dependency_deferred": 0,
        "dependency_replays": 0,
        "dependency_shutdown": 0,
        "dependency_expired": 0,
        "dependency_exhausted": 0,
        "dependency_saturated": 0,
        "dependency_retained_bytes": 0,
    }
    values.update(overrides)
    return values


def test_windows_aliases_share_one_latest_pending_generation():
    started = threading.Event()
    release = threading.Event()
    calls = []

    def process(path, event_type):
        calls.append((path, event_type))
        if len(calls) == 1:
            started.set()
            assert release.wait(2)

    scheduler = EventScheduler(process, max_workers=1, max_pending_events=2)
    assert scheduler.submit(r"C:\Campaign\Pilot.LOG", "created")
    assert started.wait(2)
    assert scheduler.submit(r"c:/campaign/pilot.log", "modified")
    assert scheduler.submit(r"\\?\C:\CAMPAIGN\pilot.log", "created")
    release.set()
    scheduler.shutdown()

    assert calls == [
        (r"C:\Campaign\Pilot.LOG", "created"),
        (r"\\?\C:\CAMPAIGN\pilot.log", "created"),
    ]
    assert scheduler.metrics() == _metrics(coalesced=2, retried=1)


def test_unc_and_extended_unc_aliases_have_the_same_identity():
    assert canonical_windows_path(r"\\server\share\Pilots\A.xml") == canonical_windows_path(
        r"\\?\UNC\SERVER\share/Pilots/A.XML"
    )


def test_unique_path_burst_is_bounded_and_saturation_is_visible(caplog):
    started = threading.Event()
    release = threading.Event()

    def process(path, event_type):
        started.set()
        assert release.wait(2)

    scheduler = EventScheduler(process, max_workers=1, max_pending_events=2)
    assert scheduler.submit("first.xml", "created")
    assert started.wait(2)
    assert scheduler.submit("second.xml", "created")
    assert not scheduler.submit("third.xml", "created")
    assert scheduler.metrics() == _metrics(
        queued=1, active=1, rejected=1, saturated=1
    )
    assert "saturated" in caplog.text.lower()
    release.set()
    scheduler.shutdown()
    assert scheduler.metrics()["queued"] == scheduler.metrics()["active"] == 0


class FailingExecutor:
    def submit(self, *args, **kwargs):
        raise RuntimeError("submit failed")

    def shutdown(self, wait=True):
        pass


def test_submit_failure_releases_admission_state():
    scheduler = EventScheduler(Mock(), 1, 1, executor=FailingExecutor())
    with pytest.raises(RuntimeError, match="submit failed"):
        scheduler.submit("pilot.xml", "created")
    assert scheduler.metrics()["queued"] == 0
    assert scheduler.metrics()["submission_failures"] == 1
    assert scheduler.admitted_paths == 0


def test_shutdown_rejects_new_work_and_drains_accepted_work():
    called = threading.Event()
    scheduler = EventScheduler(lambda *_: called.set(), 1, 1)
    assert scheduler.submit("pilot.xml", "created")
    scheduler.shutdown()
    assert called.is_set()
    assert not scheduler.submit("other.xml", "created")
    assert scheduler.metrics()["rejected"] == 1
    assert scheduler.metrics()["shutdown_rejected"] == 1


def test_bounded_startup_admission_waits_for_capacity_without_second_queue():
    first_started = threading.Event()
    release_first = threading.Event()
    calls = []

    def process(path, event_type):
        calls.append(path)
        if path == "Pilot1Dossier.txt":
            first_started.set()
            assert release_first.wait(2)

    scheduler = EventScheduler(process, max_workers=2, max_pending_events=1)
    assert scheduler.submit("Pilot1Dossier.txt", "initial")
    assert first_started.wait(2)

    admitted = []
    submitter = threading.Thread(
        target=lambda: admitted.append(
            scheduler.submit(
                "Pilot1Log.txt", "initial", admission_timeout=1.0
            )
        )
    )
    submitter.start()
    assert submitter.is_alive()
    release_first.set()
    submitter.join(2)
    scheduler.shutdown()

    assert admitted == [True]
    assert calls == ["Pilot1Dossier.txt", "Pilot1Log.txt"]


def test_startup_admission_timeout_is_bounded_and_diagnostic(caplog):
    started = threading.Event()
    release = threading.Event()
    scheduler = EventScheduler(
        lambda *_: (started.set(), release.wait(2)), 1, 1
    )
    assert scheduler.submit("Pilot1Dossier.txt", "initial")
    assert started.wait(2)
    assert not scheduler.submit(
        "Pilot2Dossier.txt", "initial", admission_timeout=0.01
    )
    assert "saturated" in caplog.text.lower()
    release.set()
    scheduler.shutdown()


def test_scheduler_does_not_depend_on_executor_private_internals():
    assert not any(name.startswith("_") for name in EventScheduler.executor_attributes_used)
