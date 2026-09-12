import sqlite3

import pytest

from ..database import DatabaseManager, TransactionRollbackError
from .test_composable_transactions import FailingConnection, RollbackError


INTERRUPTION_TYPES = (KeyboardInterrupt, SystemExit)


def _durable_meta_rows(db_path, *keys):
    placeholders = ", ".join("?" for _ in keys)
    with sqlite3.connect(db_path) as reopened:
        rows = reopened.execute(
            f"SELECT key, value FROM meta WHERE key IN ({placeholders}) ORDER BY key",
            keys,
        ).fetchall()
        assert reopened.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert reopened.execute("PRAGMA foreign_key_check").fetchall() == []
        return rows


@pytest.mark.parametrize("interruption_type", INTERRUPTION_TYPES)
def test_outer_transaction_rolls_back_process_level_interruption(
    tmp_path, interruption_type
):
    db_path = tmp_path / f"outer-{interruption_type.__name__}.sqlite"
    db = DatabaseManager(str(db_path))
    interruption = interruption_type("outer transaction interrupted")

    with pytest.raises(interruption_type) as raised:
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?)",
                ("interrupted-outer", interruption_type.__name__),
            )
            raise interruption

    assert raised.value is interruption
    db.close()
    assert _durable_meta_rows(db_path, "interrupted-outer") == []


@pytest.mark.parametrize("interruption_type", INTERRUPTION_TYPES)
def test_nested_transaction_rolls_back_process_level_interruption(
    tmp_path, interruption_type
):
    db_path = tmp_path / f"nested-{interruption_type.__name__}.sqlite"
    db = DatabaseManager(str(db_path))
    interruption = interruption_type("nested transaction interrupted")

    with pytest.raises(interruption_type) as raised:
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?)",
                ("outer-write", interruption_type.__name__),
            )
            with db.transaction() as nested_connection:
                nested_connection.execute(
                    "INSERT INTO meta(key, value) VALUES (?, ?)",
                    ("nested-write", interruption_type.__name__),
                )
                raise interruption

    assert raised.value is interruption
    db.close()
    assert _durable_meta_rows(db_path, "outer-write", "nested-write") == []


@pytest.mark.parametrize("interruption_type", INTERRUPTION_TYPES)
def test_caught_nested_interruption_marks_outer_transaction_rollback_only(
    tmp_path, interruption_type
):
    db_path = tmp_path / f"nested-caught-{interruption_type.__name__}.sqlite"
    db = DatabaseManager(str(db_path))
    interruption = interruption_type("caught nested interruption")

    with pytest.raises(TransactionRollbackError, match="rollback-only"):
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?)",
                ("outer-write", interruption_type.__name__),
            )
            try:
                with db.transaction() as nested_connection:
                    nested_connection.execute(
                        "INSERT INTO meta(key, value) VALUES (?, ?)",
                        ("nested-write", interruption_type.__name__),
                    )
                    raise interruption
            except interruption_type as raised:
                assert raised is interruption

    db.close()
    assert _durable_meta_rows(db_path, "outer-write", "nested-write") == []


@pytest.mark.parametrize("interruption_type", INTERRUPTION_TYPES)
def test_interruption_stays_primary_when_rollback_fails(
    tmp_path, caplog, interruption_type
):
    db = DatabaseManager(str(tmp_path / "rollback-failure.sqlite"))
    interruption = interruption_type("transaction interrupted")
    rollback_error = RollbackError("rollback failed")
    connection = FailingConnection(db._get_conn(), rollback_error=rollback_error)
    db._local.conn = connection

    with pytest.raises(interruption_type) as raised:
        with db.transaction():
            raise interruption

    assert raised.value is interruption
    assert "Rollback failed while preserving transaction exception" in caplog.text
    assert any(
        record.exc_info is not None and record.exc_info[1] is rollback_error
        for record in caplog.records
    )
    assert db._local.transaction_depth == 0
    assert db._local.transaction_rollback_only is False
    assert db._local.conn is None
    assert connection.closed
    db.close()


@pytest.mark.parametrize("interruption_type", INTERRUPTION_TYPES)
def test_transaction_state_is_reusable_after_interruption(tmp_path, interruption_type):
    db_path = tmp_path / f"reusable-{interruption_type.__name__}.sqlite"
    db = DatabaseManager(str(db_path))
    interruption = interruption_type("transaction interrupted")

    with pytest.raises(interruption_type):
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?)",
                ("rolled-back", interruption_type.__name__),
            )
            raise interruption

    assert db._local.transaction_depth == 0
    assert db._local.transaction_rollback_only is False

    with db.transaction() as connection:
        connection.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            ("committed-after-interruption", interruption_type.__name__),
        )

    db.close()
    assert _durable_meta_rows(
        db_path, "rolled-back", "committed-after-interruption"
    ) == [("committed-after-interruption", interruption_type.__name__)]
