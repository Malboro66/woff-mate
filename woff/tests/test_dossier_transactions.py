from __future__ import annotations

from hashlib import sha256
from unittest.mock import patch

import pytest

from ..campaign_namespace import campaign_namespace_for_root
from ..campaign_engine import CampaignEngine
from ..database import DatabaseManager
from ..handler import FileProcessor
from ..identity import PilotIdentityEvidence, PilotIdentityKind
from ..ingestion.outcome import ProcessingReason, ProcessingStatus
from ..parsers.dossier_parser import WoFFDossierParser
from .test_dossier_parser import _dossier_fixture, _encode_dossier


def _wingman(
    first_name: str,
    last_name: str,
    *,
    status: str = "In Service",
    rank: str = "Lieutenant",
) -> str:
    return (
        f"{rank};{first_name};{last_name};3;5;{status};0;0;0;0;0;6;"
        "1550;1500;9;2;8;8;1896;Reliable pilot.;75;21;651;1;"
        "19/7/1913;Arras;2;0;Null;Null;Null;Null;Null;Null;Null"
    )


def _dossier_bytes(
    *,
    rank: str = "Lieutenant",
    status: str = "Active",
    squadron: str = "No. 56 Squadron",
    decorations: tuple[str, ...] = ("Military Cross;1917-04-01",),
    wingmen: tuple[str, ...] = (_wingman("Arthur", "Able"),),
) -> bytes:
    lines = ["Null"] * 104
    values = {
        1: "Britain",
        3: rank,
        4: "James",
        5: "Hartley",
        6: "6",
        7: "4",
        8: "1917",
        11: "600",
        16: "3",
        17: "2",
        41: "60",
        46: "8",
        52: "400",
        60: status,
        83: squadron,
        84: "SE.5a",
        88: "Filescamp",
        89: "Arras",
    }
    for index, value in values.items():
        lines[index] = value
    for index, decoration in enumerate(decorations, start=19):
        lines[index] = decoration
    lines.extend(wingmen)
    return _encode_dossier(lines, "Pilot1Dossier.txt")


@pytest.fixture
def dossier_runtime(tmp_path):
    database = DatabaseManager(str(tmp_path / "dossier.sqlite"))
    processor = FileProcessor(
        database,
        CampaignEngine(database),
        stability_timeout=0.1,
        stability_interval=0.001,
    )
    dossier_path = tmp_path / "Pilot1Dossier.txt"
    yield database, processor, dossier_path
    database.close()


def _process(processor: FileProcessor, path, data: bytes, event_type: str):
    path.write_bytes(data)
    return processor.process(str(path), event_type).acknowledged_generation


def _stored_state(database: DatabaseManager):
    connection = database._get_conn()
    return {
        "pilot": connection.execute(
            """
            SELECT id, name, rank, status, squadron, missions, flminutes,
                   claimsCount, killsCount, skill, reputation, source_file
            FROM pilots ORDER BY id
            """
        ).fetchall(),
        "binding": connection.execute(
            "SELECT slot, pilotId, dossier_digest FROM pilot_slot_bindings"
        ).fetchall(),
        "roster_state": connection.execute(
            """
            SELECT key, value FROM meta
            WHERE key LIKE 'dossier_roster:%' ORDER BY key
            """
        ).fetchall(),
        "decorations": connection.execute(
            """
            SELECT pilotId, name, date, citation, source_file
            FROM decorations ORDER BY name
            """
        ).fetchall(),
        "wingmen": connection.execute(
            """
            SELECT pilotId, rank, fName, sName, status, skill, morale
            FROM squad_members ORDER BY fName, sName
            """
        ).fetchall(),
        "diary": connection.execute(
            """
            SELECT pilotId, missionId, entry_date, narrative
            FROM diary_entries ORDER BY narrative
            """
        ).fetchall(),
    }


def _semantic_state(database: DatabaseManager):
    connection = database._get_conn()
    return {
        "pilot": connection.execute(
            """
            SELECT name, rank, status, squadron, missions, flminutes,
                   claimsCount, killsCount, skill, reputation, source_file
            FROM pilots ORDER BY name
            """
        ).fetchall(),
        "decorations": connection.execute(
            "SELECT name, date, citation, source_file FROM decorations ORDER BY name"
        ).fetchall(),
        "wingmen": connection.execute(
            """
            SELECT rank, fName, sName, status, skill, morale
            FROM squad_members ORDER BY fName, sName
            """
        ).fetchall(),
        "diary": connection.execute(
            """
            SELECT missionId, entry_date, narrative
            FROM diary_entries ORDER BY narrative
            """
        ).fetchall(),
    }


def _changed_dossier() -> bytes:
    return _dossier_bytes(
        rank="Captain",
        status="Wounded",
        decorations=(
            "Military Cross;1917-04-01",
            "Distinguished Service Order;1917-05-01",
        ),
        wingmen=(
            _wingman("Arthur", "Able", status="Wounded"),
            _wingman("Robert", "Baker"),
        ),
    )


def test_identityless_dossier_never_reaches_merge_and_write(dossier_runtime):
    database, processor, dossier_path = dossier_runtime
    dossier_path.write_bytes(
        _encode_dossier(
            _dossier_fixture("long_corrupt_sanitized.txt"),
            dossier_path.name,
        )
    )

    with patch.object(
        database,
        "merge_and_write",
        wraps=database.merge_and_write,
    ) as merge_and_write:
        outcome = processor.process(str(dossier_path), "initial")

    assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
    assert outcome.reason is ProcessingReason.PARSER_REJECTED
    merge_and_write.assert_not_called()
    state = _stored_state(database)
    assert all(not rows for rows in state.values())


def test_ambiguous_partial_dossier_never_reaches_merge_and_write(
    dossier_runtime,
):
    database, processor, dossier_path = dossier_runtime
    wrong_slot_path = dossier_path.with_name("Pilot49Dossier.txt")
    wrong_slot_path.write_bytes(
        _encode_dossier(
            _dossier_fixture("short_ambiguous_sanitized.txt"),
            "Pilot1Dossier.txt",
        )
    )

    with patch.object(
        database,
        "merge_and_write",
        wraps=database.merge_and_write,
    ) as merge_and_write:
        outcome = processor.process(str(wrong_slot_path), "initial")

    assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
    assert outcome.reason is ProcessingReason.PARSER_REJECTED
    merge_and_write.assert_not_called()
    state = _stored_state(database)
    assert all(not rows for rows in state.values())


def test_partial_null_rank_preserves_stored_rank_and_diary(dossier_runtime):
    database, processor, dossier_path = dossier_runtime
    assert _process(
        processor,
        dossier_path,
        _dossier_bytes(rank="Captain"),
        "initial",
    ) is not None
    diary_before = _stored_state(database)["diary"]
    partial_lines = _dossier_fixture("short_valid_sanitized.txt")
    partial_lines[1] = "Britain"
    partial_lines[3] = "Null"
    partial_lines[4] = "James"
    partial_lines[5] = "Hartley"
    partial = _encode_dossier(
        partial_lines,
        dossier_path.name,
    )

    assert _process(
        processor,
        dossier_path,
        partial,
        "modified",
    ) is not None

    stored_rank = database._get_conn().execute(
        "SELECT rank FROM pilots"
    ).fetchone()
    assert stored_rank == ("Captain",)
    assert _stored_state(database)["diary"] == diary_before


@pytest.mark.parametrize("event_type", ["initial", "modified"])
def test_diary_rejection_rolls_back_pilot_decorations_and_roster(
    dossier_runtime, monkeypatch, event_type
):
    database, processor, dossier_path = dossier_runtime
    assert _process(
        processor, dossier_path, _dossier_bytes(), "initial"
    ) is not None
    before = _stored_state(database)
    save_diary_entry = database.save_diary_entry
    calls = 0

    def reject_second_entry(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            return False
        return save_diary_entry(*args, **kwargs)

    monkeypatch.setattr(database, "save_diary_entry", reject_second_entry)

    assert _process(
        processor, dossier_path, _changed_dossier(), event_type
    ) is None
    assert _stored_state(database) == before


@pytest.mark.parametrize(
    "boundary", ["pilot", "decorations", "roster", "roster-state"]
)
def test_core_write_failure_leaves_no_dossier_diary_entry(
    dossier_runtime, monkeypatch, boundary
):
    database, processor, dossier_path = dossier_runtime
    assert _process(
        processor, dossier_path, _dossier_bytes(), "initial"
    ) is not None
    before = _stored_state(database)

    if boundary == "pilot":
        target = database._pilots
        method = "upsert_pilot"
    elif boundary == "decorations":
        target = database._missions
        method = "upsert_mission"
    elif boundary == "roster":
        target = database._wingmen
        method = "upsert_wingmen_batch"
    else:
        target = database
        method = "save_dossier_roster_state"
    write = getattr(target, method)

    def fail_after_write(*args, **kwargs):
        write(*args, **kwargs)
        raise RuntimeError(f"forced {boundary} failure")

    monkeypatch.setattr(
        target,
        method,
        fail_after_write,
    )

    assert _process(
        processor, dossier_path, _changed_dossier(), "modified"
    ) is None
    assert _stored_state(database) == before


def test_retry_commits_once_and_same_digest_replay_performs_no_write(
    dossier_runtime, monkeypatch
):
    database, processor, dossier_path = dossier_runtime
    assert _process(
        processor, dossier_path, _dossier_bytes(), "initial"
    ) is not None
    before = _stored_state(database)
    changed = _changed_dossier()
    save_diary_entry = database.save_diary_entry

    monkeypatch.setattr(database, "save_diary_entry", lambda *_args, **_kwargs: False)
    assert _process(processor, dossier_path, changed, "modified") is None
    assert _stored_state(database) == before

    monkeypatch.setattr(database, "save_diary_entry", save_diary_entry)
    assert _process(processor, dossier_path, changed, "retry") is not None
    committed = _stored_state(database)
    assert committed["pilot"][0][2:5] == ("Captain", "Wounded", "No. 56 Squadron")
    assert len(committed["decorations"]) == 2
    assert len(committed["wingmen"]) == 2
    assert len(committed["diary"]) == 3

    control_directory = database.db_path.parent / "first-attempt"
    control_directory.mkdir()
    control_database = DatabaseManager(str(control_directory / "control.sqlite"))
    control_processor = FileProcessor(
        control_database,
        CampaignEngine(control_database),
        stability_timeout=0.1,
        stability_interval=0.001,
    )
    control_path = control_directory / "Pilot1Dossier.txt"
    try:
        assert _process(
            control_processor, control_path, _dossier_bytes(), "initial"
        ) is not None
        assert _process(
            control_processor, control_path, changed, "modified"
        ) is not None
        assert _semantic_state(database) == _semantic_state(control_database)
    finally:
        control_database.close()

    with patch.object(
        database, "merge_and_write", wraps=database.merge_and_write
    ) as merge_and_write:
        assert _process(processor, dossier_path, changed, "modified") is not None

    merge_and_write.assert_not_called()
    assert _stored_state(database) == committed


def test_diary_exception_propagates_without_leaving_partial_state(
    dossier_runtime, monkeypatch
):
    database, processor, dossier_path = dossier_runtime
    initial = _dossier_bytes()
    changed = _changed_dossier()
    assert _process(processor, dossier_path, initial, "initial") is not None
    before = _stored_state(database)

    parser = WoFFDossierParser()
    assert parser.parse_bytes(changed, "Pilot1Dossier.txt")
    assert parser.pilot is not None
    identity = PilotIdentityEvidence(
        PilotIdentityKind.DOSSIER,
        1,
        sha256(changed).hexdigest(),
        campaign_namespace_for_root(str(dossier_path.parent)),
    )
    save_diary_entry = database.save_diary_entry
    calls = 0

    class DiaryFailure(RuntimeError):
        pass

    def fail_second_entry(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise DiaryFailure("forced diary failure")
        return save_diary_entry(*args, **kwargs)

    monkeypatch.setattr(database, "save_diary_entry", fail_second_entry)

    with pytest.raises(DiaryFailure, match="forced diary failure"):
        processor.campaign_engine.process_dossier_import(
            pilot=parser.pilot,
            decorations=parser.decorations,
            wingmen=parser.wingmen,
            identity=identity,
        )

    assert _stored_state(database) == before


def test_dossier_reads_and_writes_use_one_caller_owned_transaction(
    dossier_runtime, monkeypatch
):
    database, processor, dossier_path = dossier_runtime
    assert _process(
        processor, dossier_path, _dossier_bytes(), "initial"
    ) is not None
    observed = []

    def observe(name, operation):
        def wrapped(*args, **kwargs):
            observed.append((name, database._get_conn().in_transaction))
            result = operation(*args, **kwargs)
            observed.append((name, database._get_conn().in_transaction))
            return result

        return wrapped

    monkeypatch.setattr(
        database,
        "load_dossier_state",
        observe("load", database.load_dossier_state),
    )
    monkeypatch.setattr(
        database,
        "merge_and_write",
        observe("merge", database.merge_and_write),
    )
    monkeypatch.setattr(
        database,
        "save_diary_entry",
        observe("diary", database.save_diary_entry),
    )
    monkeypatch.setattr(
        database,
        "save_dossier_roster_state",
        observe("roster-state", database.save_dossier_roster_state),
    )

    assert _process(
        processor, dossier_path, _changed_dossier(), "modified"
    ) is not None

    assert {name for name, _active in observed} == {
        "load", "merge", "roster-state", "diary"
    }
    assert all(active for _name, active in observed)
    assert not database._get_conn().in_transaction


def test_squadron_transfer_emits_no_false_roster_events_and_replay_is_idempotent(
    dossier_runtime
):
    database, processor, dossier_path = dossier_runtime
    old_dossier = _dossier_bytes(
        squadron="No. 56 Squadron",
        wingmen=(
            _wingman("Arthur", "Able"),
            _wingman("Robert", "Baker"),
        ),
    )
    transferred = _dossier_bytes(
        squadron="No. 60 Squadron",
        wingmen=(
            _wingman("Charles", "Clark"),
            _wingman("David", "Dover"),
        ),
    )
    transferred_update = _dossier_bytes(
        squadron="No. 60 Squadron",
        decorations=(
            "Military Cross;1917-04-01",
            "Distinguished Service Order;1917-05-01",
        ),
        wingmen=(
            _wingman("Charles", "Clark"),
            _wingman("David", "Dover"),
        ),
    )

    assert _process(processor, dossier_path, old_dossier, "initial") is not None
    assert _process(processor, dossier_path, transferred, "modified") is not None
    assert database._get_conn().execute(
        "SELECT COUNT(*) FROM diary_entries"
    ).fetchone() == (0,)
    assert _process(
        processor, dossier_path, transferred_update, "modified"
    ) is not None
    assert database._get_conn().execute(
        "SELECT COUNT(*) FROM diary_entries"
    ).fetchone() == (0,)

    with patch.object(
        database, "merge_and_write", wraps=database.merge_and_write
    ) as merge_and_write:
        assert _process(
            processor, dossier_path, transferred_update, "modified"
        ) is not None

    merge_and_write.assert_not_called()
    assert database._get_conn().execute(
        "SELECT COUNT(*) FROM diary_entries"
    ).fetchone() == (0,)


def test_same_squadron_roster_diff_commits_each_supported_event_once(
    dossier_runtime
):
    database, processor, dossier_path = dossier_runtime
    initial = _dossier_bytes(
        wingmen=(
            _wingman("Arthur", "Able"),
            _wingman("Robert", "Baker"),
            _wingman("Charles", "Clark"),
        )
    )
    changed = _dossier_bytes(
        wingmen=(
            _wingman("Arthur", "Able", status="KIA"),
            _wingman("Charles", "Clark", status="Wounded"),
            _wingman("David", "Dover"),
        )
    )

    assert _process(processor, dossier_path, initial, "initial") is not None
    assert _process(processor, dossier_path, changed, "modified") is not None

    narratives = [
        row[0]
        for row in database._get_conn().execute(
            "SELECT narrative FROM diary_entries ORDER BY narrative"
        ).fetchall()
    ]
    assert len(narratives) == 4
    assert any(
        "Arthur Able" in narrative and "abatido" in narrative
        for narrative in narratives
    )
    assert any(
        "Robert Baker" in narrative and "Perdi o contacto" in narrative
        for narrative in narratives
    )
    assert any(
        "Charles Clark" in narrative and "ferido" in narrative
        for narrative in narratives
    )
    assert any(
        "David Dover" in narrative and "novo elemento" in narrative
        for narrative in narratives
    )

    assert _process(processor, dossier_path, changed, "modified") is not None
    assert database._get_conn().execute(
        "SELECT COUNT(*) FROM diary_entries"
    ).fetchone() == (4,)
