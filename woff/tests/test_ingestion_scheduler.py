import threading
from unittest.mock import Mock

import pytest

from ..ingestion.scheduler import EventScheduler, canonical_windows_path


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
    assert scheduler.metrics() == {
        "queued": 0, "active": 0, "coalesced": 2, "rejected": 0, "retried": 1,
    }


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
    assert scheduler.metrics() == {
        "queued": 1, "active": 1, "coalesced": 0, "rejected": 1, "retried": 0,
    }
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
    assert scheduler.admitted_paths == 0


def test_shutdown_rejects_new_work_and_drains_accepted_work():
    called = threading.Event()
    scheduler = EventScheduler(lambda *_: called.set(), 1, 1)
    assert scheduler.submit("pilot.xml", "created")
    scheduler.shutdown()
    assert called.is_set()
    assert not scheduler.submit("other.xml", "created")
    assert scheduler.metrics()["rejected"] == 1


def test_scheduler_does_not_depend_on_executor_private_internals():
    assert not any(name.startswith("_") for name in EventScheduler.executor_attributes_used)
