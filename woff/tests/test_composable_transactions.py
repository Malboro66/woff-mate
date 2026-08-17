import sqlite3

import pytest

from ..database import DatabaseManager, TransactionRollbackError
from ..models import WoFFMission, WoFFPilot, WoFFWingman


class BodyError(RuntimeError):
    pass


class CommitError(RuntimeError):
    pass


class RollbackError(RuntimeError):
    pass


class FailingConnection:
    def __init__(self, connection, *, commit_error=None, rollback_error=None):
        self.connection = connection
        self.commit_error = commit_error
        self.rollback_error = rollback_error
        self.closed = False

    def execute(self, *args, **kwargs):
        return self.connection.execute(*args, **kwargs)

    def commit(self):
        if self.commit_error is not None:
            raise self.commit_error
        return self.connection.commit()

    def rollback(self):
        if self.rollback_error is not None:
            raise self.rollback_error
        return self.connection.rollback()

    def close(self):
        self.closed = True
        return self.connection.close()


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(str(tmp_path / "composable.sqlite"))
    yield manager
    manager.close()


@pytest.fixture
def pilot(db):
    value = WoFFPilot(id="pilot-34", name="Issue 34 Pilot")
    assert db.merge_and_write(value, [], [], []) == value.id
    return value


def test_rpg_and_diary_writes_roll_back_together(db, pilot):
    connection = db._get_conn()

    with pytest.raises(RuntimeError, match="write boundary"):
        with db.transaction():
            db.update_pilot_rpg_stats(pilot.id, 20, 70, 10)
            assert db.save_diary_entry(
                pilot.id, None, "1917-05-01", "Pending diary"
            )
            raise RuntimeError("write boundary")

    assert connection.execute(
        "SELECT 1 FROM pilot_rpg_stats WHERE pilotId = ?", (pilot.id,)
    ).fetchone() is None
    assert connection.execute(
        "SELECT 1 FROM diary_entries WHERE pilotId = ?", (pilot.id,)
    ).fetchone() is None


def test_caller_can_commit_multiple_writes_as_one_transaction(db, pilot):
    connection = db._get_conn()

    with db.transaction():
        db.update_pilot_rpg_stats(pilot.id, 30, 60, 15)
        assert db.save_diary_entry(
            pilot.id, None, "1917-05-02", "Joint commit"
        )
        assert connection.in_transaction
        with sqlite3.connect(db.db_path) as observer:
            assert observer.execute(
                "SELECT 1 FROM pilot_rpg_stats WHERE pilotId = ?", (pilot.id,)
            ).fetchone() is None

    with sqlite3.connect(db.db_path) as observer:
        assert observer.execute(
            "SELECT fatigue, morale, stress FROM pilot_rpg_stats WHERE pilotId = ?",
            (pilot.id,),
        ).fetchone() == (30, 60, 15)
        assert observer.execute(
            "SELECT narrative FROM diary_entries WHERE pilotId = ?", (pilot.id,)
        ).fetchone() == ("Joint commit",)


def test_duplicate_diary_result_does_not_rollback_other_pending_work(db, pilot):
    connection = db._get_conn()
    mission_id = "duplicate-mission-34"
    mission = WoFFMission(id=mission_id, pilotId=pilot.id, date="1917-05-03")
    assert db.merge_and_write(pilot, [mission], [], []) == pilot.id

    with db.transaction():
        assert db.save_diary_entry(
            pilot.id, mission_id, "1917-05-03", "Original"
        )
        assert not db.save_diary_entry(
            pilot.id, mission_id, "1917-05-03", "Duplicate"
        )
        assert connection.in_transaction

    assert connection.execute(
        "SELECT narrative FROM diary_entries WHERE pilotId = ? AND missionId = ?",
        (pilot.id, mission_id),
    ).fetchall() == [("Original",)]


def test_non_duplicate_diary_integrity_error_propagates_and_rolls_back(db, pilot):
    connection = db._get_conn()

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        with db.transaction():
            db.update_pilot_rpg_stats(pilot.id, 35, 65, 12)
            db.save_diary_entry(
                pilot.id, "missing-mission", "1917-05-03", "Invalid reference"
            )

    assert connection.execute(
        "SELECT 1 FROM pilot_rpg_stats WHERE pilotId = ?", (pilot.id,)
    ).fetchone() is None
    assert connection.execute(
        "SELECT 1 FROM diary_entries WHERE pilotId = ?", (pilot.id,)
    ).fetchone() is None


def test_caught_nested_write_failure_raises_when_outer_scope_rolls_back(db, pilot):
    connection = db._get_conn()

    with pytest.raises(TransactionRollbackError, match="rollback-only"):
        with db.transaction():
            db.update_pilot_rpg_stats(pilot.id, 45, 55, 22)
            assert not db.save_wingman_personality(
                "missing-wingman", pilot.id, {"aggression": 75}
            )

    assert connection.execute(
        "SELECT 1 FROM pilot_rpg_stats WHERE pilotId = ?", (pilot.id,)
    ).fetchone() is None
    assert connection.execute(
        "SELECT 1 FROM wingmen_personalities WHERE wingmanId = ?",
        ("missing-wingman",),
    ).fetchone() is None


def test_body_exception_stays_primary_when_rollback_fails(db, caplog):
    body_error = BodyError("body failed")
    rollback_error = RollbackError("rollback failed")
    connection = FailingConnection(db._get_conn(), rollback_error=rollback_error)
    db._local.conn = connection

    with pytest.raises(BodyError) as raised:
        with db.transaction():
            raise body_error

    assert raised.value is body_error
    assert "Rollback failed while preserving transaction exception" in caplog.text
    assert any(
        record.exc_info is not None and record.exc_info[1] is rollback_error
        for record in caplog.records
    )
    assert db._local.transaction_depth == 0
    assert db._local.transaction_rollback_only is False
    assert db._local.conn is None
    assert connection.closed


def test_commit_exception_stays_primary_when_rollback_succeeds(db):
    commit_error = CommitError("commit failed")
    connection = FailingConnection(db._get_conn(), commit_error=commit_error)
    db._local.conn = connection

    with pytest.raises(CommitError) as raised:
        with db.transaction():
            pass

    assert raised.value is commit_error
    assert db._local.transaction_depth == 0
    assert db._local.transaction_rollback_only is False


def test_commit_exception_stays_primary_when_recovery_rollback_fails(db, caplog):
    commit_error = CommitError("commit failed")
    rollback_error = RollbackError("rollback failed")
    connection = FailingConnection(
        db._get_conn(), commit_error=commit_error, rollback_error=rollback_error
    )
    db._local.conn = connection

    with pytest.raises(CommitError) as raised:
        with db.transaction():
            pass

    assert raised.value is commit_error
    assert "Rollback failed after commit failure" in caplog.text
    assert any(
        record.exc_info is not None and record.exc_info[1] is rollback_error
        for record in caplog.records
    )
    assert db._local.transaction_depth == 0
    assert db._local.transaction_rollback_only is False
    assert db._local.conn is None
    assert connection.closed


def test_rollback_only_rollback_failure_escapes_without_replacement(db):
    nested_error = BodyError("nested failure")
    rollback_error = RollbackError("rollback failed")
    connection = FailingConnection(db._get_conn(), rollback_error=rollback_error)
    db._local.conn = connection

    with pytest.raises(RollbackError) as raised:
        with db.transaction():
            try:
                with db.transaction():
                    raise nested_error
            except BodyError:
                pass

    assert raised.value is rollback_error
    assert db._local.transaction_depth == 0
    assert db._local.transaction_rollback_only is False
    assert db._local.conn is None
    assert connection.closed


def test_wingman_personality_and_memory_roll_back_atomically(db, pilot):
    wingman = WoFFWingman(
        id="wingman-34", fName="Ada", sName="Cole", pilotId=pilot.id
    )
    assert db.merge_and_write(pilot, [], [], [], [wingman]) == pilot.id
    connection = db._get_conn()

    with pytest.raises(RuntimeError, match="wingman boundary"):
        with db.transaction():
            assert db.save_wingman_personality(
                wingman.id, pilot.id, {"aerial_skill": 81}
            )
            assert db.save_wingman_memory(
                wingman.id, "combat", "1917-05-04", "Pending memory"
            )
            raise RuntimeError("wingman boundary")

    assert db.get_wingman_personality(wingman.id) is None
    assert connection.execute(
        "SELECT 1 FROM wingmen_memory WHERE wingmanId = ?", (wingman.id,)
    ).fetchone() is None


def test_autonomous_rpg_and_diary_operations_still_commit(db, pilot):
    db.update_pilot_rpg_stats(pilot.id, 40, 50, 20)
    assert db.save_diary_entry(pilot.id, None, "1917-05-05", "Autonomous")

    with sqlite3.connect(db.db_path) as observer:
        assert observer.execute(
            "SELECT fatigue FROM pilot_rpg_stats WHERE pilotId = ?", (pilot.id,)
        ).fetchone() == (40,)
        assert observer.execute(
            "SELECT narrative FROM diary_entries WHERE pilotId = ?", (pilot.id,)
        ).fetchone() == ("Autonomous",)


def test_autonomous_wingman_operations_still_commit(db, pilot):
    wingman = WoFFWingman(
        id="wingman-autonomous-34", fName="Sam", sName="Gray", pilotId=pilot.id
    )
    assert db.merge_and_write(pilot, [], [], [], [wingman]) == pilot.id

    assert db.save_wingman_personality(wingman.id, pilot.id, {"aggression": 62})
    assert db.save_wingman_memory(
        wingman.id, "leave", "1917-05-06", "Autonomous memory"
    )

    with sqlite3.connect(db.db_path) as observer:
        assert observer.execute(
            "SELECT aggression FROM wingmen_personalities WHERE wingmanId = ?",
            (wingman.id,),
        ).fetchone() == (62,)
        assert observer.execute(
            "SELECT description FROM wingmen_memory WHERE wingmanId = ?",
            (wingman.id,),
        ).fetchone() == ("Autonomous memory",)
