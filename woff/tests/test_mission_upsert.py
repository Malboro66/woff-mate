import logging
from typing import Any

import pytest

from ..database import DatabaseManager
from ..models import WoFFMission, WoFFPilot
from ..parsers.pilot_data_parser import WoFFPilotDataParser
from .identity_support import dossier_evidence


@pytest.fixture
def mission_db(tmp_path):
    manager = DatabaseManager(str(tmp_path / "mission-upsert.sqlite"))
    yield manager
    manager.close()


def _persist_pilot(manager: DatabaseManager) -> WoFFPilot:
    pilot = WoFFPilot(
        id="pilot-39",
        name="Mission Merge Pilot",
        source_file="Pilot1Dossier.txt",
    )
    assert manager.merge_and_write(
        pilot, [], [], [], identity=dossier_evidence(1, "mission-upsert")
    ) == pilot.id
    return pilot


def _mission(
    pilot: WoFFPilot,
    mission_id: str,
    source_file: str,
    **overrides,
) -> WoFFMission:
    values: dict[str, Any] = {
        "id": mission_id,
        "pilotId": pilot.id,
        "date": "1917-04-06",
        "time": "10:30",
        "missionType": "Patrol",
        "aircraft": "Sopwith Camel",
        "source_file": source_file,
    }
    values.update(overrides)
    return WoFFMission(**values)


def test_reimport_updates_result_without_replacing_stable_mission_id(mission_db):
    pilot = _persist_pilot(mission_db)
    original = _mission(
        pilot,
        "mission-stable",
        "Pilot1Log.txt",
        result="Completed",
    )
    assert mission_db.merge_and_write(None, [original], [], []) == pilot.id
    assert mission_db.save_diary_entry(
        pilot.id, original.id, original.date, "Original diary"
    )

    refreshed = _mission(
        pilot,
        "mission-provisional-refresh",
        "mission.log",
        result="Force-Landed (Friendly Lines)",
    )
    assert mission_db.merge_and_write(None, [refreshed], [], []) == pilot.id

    assert mission_db._get_conn().execute(
        "SELECT id, result FROM missions WHERE pilotId = ?",
        (pilot.id,),
    ).fetchall() == [("mission-stable", "Force-Landed (Friendly Lines)")]
    assert mission_db._get_conn().execute(
        "SELECT missionId FROM diary_entries WHERE pilotId = ?",
        (pilot.id,),
    ).fetchall() == [("mission-stable",)]
    assert mission_db._get_conn().execute("PRAGMA foreign_key_check").fetchall() == []
    assert mission_db._get_conn().execute("PRAGMA integrity_check").fetchall() == [
        ("ok",)
    ]


@pytest.mark.parametrize(
    ("legacy_type", "corrected_type", "source_file"),
    [
        ("Offensive Patrol (OP)", "Troop Support", "Pilot1Log.txt"),
        ("Offensive Patrol (OP)", "Cooperation Flight", "career.xml"),
        ("Bombing Raid (Tactical)", "Bombardment", "Pilot1Log.txt"),
        ("Close Air Support (CAS)", "Casualty Evacuation", "career.xml"),
        ("Ground Attack / Strafing", "Strafed Target", "Pilot1Log.txt"),
        ("Balloon Busting", "Ballooning Patrol", "career.xml"),
    ],
)
def test_replay_reconciles_every_legacy_substring_alias_without_duplicate(
    mission_db,
    legacy_type,
    corrected_type,
    source_file,
):
    pilot = _persist_pilot(mission_db)
    legacy = _mission(
        pilot,
        "mission-legacy-alias",
        source_file,
        missionType=legacy_type,
        result="Completed",
    )
    assert mission_db.merge_and_write(None, [legacy], [], []) == pilot.id
    assert mission_db.save_diary_entry(
        pilot.id, legacy.id, legacy.date, "Existing diary"
    )

    replay = _mission(
        pilot,
        "mission-corrected-replay",
        source_file,
        missionType=corrected_type,
        result="Force-Landed (Friendly Lines)",
    )
    assert mission_db.merge_and_write(None, [replay], [], []) == pilot.id

    assert mission_db._get_conn().execute(
        "SELECT id, missionType, result FROM missions WHERE pilotId=?",
        (pilot.id,),
    ).fetchall() == [
        (
            "mission-legacy-alias",
            corrected_type,
            "Force-Landed (Friendly Lines)",
        )
    ]
    assert mission_db._get_conn().execute(
        "SELECT missionId FROM diary_entries WHERE pilotId=?",
        (pilot.id,),
    ).fetchall() == [("mission-legacy-alias",)]


def test_pilotlog_replay_uses_raw_type_to_reconcile_legacy_alias_collision(
    mission_db,
):
    pilot = _persist_pilot(mission_db)
    legacy = _mission(
        pilot,
        "mission-legacy-overlap",
        "Pilot1Log.txt",
        missionType="Offensive Patrol (OP)",
        result="Completed",
    )
    assert mission_db.merge_and_write(None, [legacy], [], []) == pilot.id
    assert mission_db.save_diary_entry(
        pilot.id, legacy.id, legacy.date, "Existing diary"
    )

    parser = WoFFPilotDataParser()
    assert parser.parse_bytes(
        (
            "1\n"
            "6;4;1917;10;30;Arras;Filescamp;Troop Support Escort;"
            "Sopwith Camel;;45;100;Sopwith Camel;No. 56 Sqn;troops;"
            "Target;N50;E2;;Mission completed.\n"
        ),
        "Pilot1Log.txt",
    )
    assert len(parser.missions) == 1
    replay = parser.missions[0]
    assert replay.missionType == "Escort Duty"
    replay.pilotId = pilot.id

    assert mission_db.merge_and_write(None, [replay], [], []) == pilot.id

    assert mission_db._get_conn().execute(
        "SELECT id, missionType FROM missions WHERE pilotId=?",
        (pilot.id,),
    ).fetchall() == [("mission-legacy-overlap", "Escort Duty")]
    assert mission_db._get_conn().execute(
        "SELECT missionId FROM diary_entries WHERE pilotId=?",
        (pilot.id,),
    ).fetchall() == [("mission-legacy-overlap",)]


def test_legacy_false_op_is_not_rewritten_from_a_different_source(
    mission_db,
):
    pilot = _persist_pilot(mission_db)
    legitimate_op = _mission(
        pilot,
        "mission-legitimate-op",
        "mission.log",
        missionType="Offensive Patrol (OP)",
    )
    assert mission_db.merge_and_write(None, [legitimate_op], [], []) == pilot.id

    different_source = _mission(
        pilot,
        "mission-different-source",
        "Pilot1Log.txt",
        missionType="Troop Support",
    )
    assert mission_db.merge_and_write(
        None, [different_source], [], []
    ) == pilot.id

    assert mission_db._get_conn().execute(
        """
        SELECT id, missionType, source_file FROM missions
        WHERE pilotId=? ORDER BY id
        """,
        (pilot.id,),
    ).fetchall() == [
        ("mission-different-source", "Troop Support", "Pilot1Log.txt"),
        (
            "mission-legitimate-op",
            "Offensive Patrol (OP)",
            "mission.log",
        ),
    ]


def test_poorer_defaults_never_erase_richer_stored_values(mission_db, caplog):
    pilot = _persist_pilot(mission_db)
    authoritative = _mission(
        pilot,
        "mission-rich",
        "mission.log",
        duration="55",
        altitude="12000",
        sector="Arras",
        squadron="No. 56 Sqn",
        weather="Storm",
        enemyContacts=5,
        claimsCount=2,
        result="Force-Landed (Friendly Lines)",
        damageReceived=True,
        woundsReceived=True,
        notes="Detailed authoritative report",
    )
    assert mission_db.merge_and_write(None, [authoritative], [], []) == pilot.id

    poorer = _mission(
        pilot,
        "mission-poorer-reparse",
        "Pilot1Log.txt",
        weather="Unknown",
        result="Uneventful",
    )
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="WoFFWatch"):
        assert mission_db.merge_and_write(None, [poorer], [], []) == pilot.id

    assert mission_db._get_conn().execute(
        """
        SELECT id, duration, altitude, sector, squadron, weather,
               enemyContacts, claimsCount, result, damageReceived,
               woundsReceived, notes, source_file
        FROM missions WHERE pilotId = ?
        """,
        (pilot.id,),
    ).fetchone() == (
        "mission-rich",
        "55",
        "12000",
        "Arras",
        "No. 56 Sqn",
        "Storm",
        5,
        2,
        "Force-Landed (Friendly Lines)",
        1,
        1,
        "Detailed authoritative report",
        "mission.log",
    )
    assert "Mission merge outcomes: inserted=0 updated=0 unchanged=1" in caplog.messages


def test_source_precedence_enriches_then_rejects_a_lower_source_downgrade(
    mission_db,
):
    pilot = _persist_pilot(mission_db)
    pilot_log = _mission(
        pilot,
        "mission-pilot-log",
        "Pilot1Log.txt",
        result="Completed",
        notes="Pilot report",
    )
    assert mission_db.merge_and_write(None, [pilot_log], [], []) == pilot.id

    xml = _mission(
        pilot,
        "mission-xml-refresh",
        "campaign.xml",
        duration="50",
        altitude="10000",
        weather="Rain",
        enemyContacts=3,
        claimsCount=1,
        result="Aircraft Damaged (Returned)",
        damageReceived=True,
        woundsReceived=True,
        notes="XML report",
    )
    assert mission_db.merge_and_write(None, [xml], [], []) == pilot.id

    debrief = _mission(
        pilot,
        "mission-debrief-refresh",
        "mission.log",
        weather="Dynamic",
        result="Force-Landed (Friendly Lines)",
    )
    assert mission_db.merge_and_write(None, [debrief], [], []) == pilot.id

    lower_replay = _mission(
        pilot,
        "mission-lower-replay",
        "campaign.xml",
        duration="10",
        altitude="1000",
        weather="Clear",
        enemyContacts=1,
        claimsCount=0,
        result="Completed",
        notes="Lower-priority replay",
    )
    assert mission_db.merge_and_write(None, [lower_replay], [], []) == pilot.id

    assert mission_db._get_conn().execute(
        """
        SELECT id, duration, altitude, weather, enemyContacts, claimsCount,
               result, damageReceived, woundsReceived, notes, source_file
        FROM missions WHERE pilotId = ?
        """,
        (pilot.id,),
    ).fetchone() == (
        "mission-pilot-log",
        "50",
        "10000",
        "Dynamic",
        3,
        1,
        "Force-Landed (Friendly Lines)",
        1,
        1,
        "XML report",
        "mission.log",
    )


def test_batch_reports_inserted_updated_and_unchanged_separately(
    mission_db, caplog
):
    pilot = _persist_pilot(mission_db)
    existing_update = _mission(
        pilot,
        "mission-update",
        "Pilot1Log.txt",
        result="Completed",
    )
    existing_same = _mission(
        pilot,
        "mission-same",
        "Pilot1Log.txt",
        date="1917-04-07",
        result="Completed",
    )
    assert mission_db.merge_and_write(
        None, [existing_update, existing_same], [], []
    ) == pilot.id

    batch = [
        _mission(
            pilot,
            "mission-new",
            "Pilot1Log.txt",
            date="1917-04-08",
            result="Completed",
        ),
        _mission(
            pilot,
            "mission-update-refresh",
            "Pilot1Log.txt",
            result="Force-Landed (Friendly Lines)",
        ),
        _mission(
            pilot,
            "mission-same-replay",
            "Pilot1Log.txt",
            date="1917-04-07",
            result="Completed",
        ),
    ]
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="WoFFWatch"):
        assert mission_db.merge_and_write(None, batch, [], []) == pilot.id

    assert "Mission merge outcomes: inserted=1 updated=1 unchanged=1" in caplog.messages
    assert mission_db._get_conn().execute(
        "SELECT COUNT(*) FROM missions WHERE pilotId = ?", (pilot.id,)
    ).fetchone() == (3,)

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="WoFFWatch"):
        assert mission_db.merge_and_write(None, batch, [], []) == pilot.id
    assert "Mission merge outcomes: inserted=0 updated=0 unchanged=3" in caplog.messages
