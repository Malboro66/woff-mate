from __future__ import annotations

from ..database import DatabaseManager
from ..models import (
    WoFFDecoration,
    WoFFMission,
    WoFFPilot,
    WoFFVictory,
    stable_source_record_key,
)
from ..parsers.pilot_data_parser import WoFFPilotDataParser
from ..parsers.xml_parser import WoFFXMLParser
from .identity_support import dossier_evidence


def _persist_pilot(database: DatabaseManager) -> WoFFPilot:
    pilot = WoFFPilot(
        id="merge-pilot",
        name="Merge Test Pilot",
        source_file="Pilot1Dossier.txt",
    )
    assert database.merge_and_write(
        pilot,
        [],
        [],
        [],
        identity=dossier_evidence(1, pilot.id),
    ) == pilot.id
    return pilot


def _persist_competing_claim_missions(
    database: DatabaseManager,
    pilot: WoFFPilot,
) -> tuple[WoFFMission, WoFFMission]:
    stored_parent = WoFFMission(
        id="mission-stored-parent",
        pilotId=pilot.id,
        date="1917-04-06",
        time="09:00",
        missionType="Patrol",
        aircraft="SE.5a",
        claimsCount=0,
        source_file="mission.log",
    )
    inference_candidate = WoFFMission(
        id="mission-inference-candidate",
        pilotId=pilot.id,
        date="1917-04-06",
        time="09:30",
        missionType="Escort",
        aircraft="SE.5a",
        claimsCount=1,
        source_file="mission.log",
    )
    assert database.merge_and_write(
        None, [stored_parent, inference_candidate], [], []
    ) == pilot.id
    return stored_parent, inference_candidate


def test_distinct_same_minute_victories_survive_and_replay_is_idempotent(
    tmp_path,
):
    database = DatabaseManager(str(tmp_path / "victories.sqlite"))
    try:
        pilot = _persist_pilot(database)
        victories = [
            WoFFVictory(
                id="victory-a",
                pilotId=pilot.id,
                date="1917-04-06",
                time="10:35",
                enemyType="Albatros D.III",
                location="north of Arras",
                source_file="Pilot1Claims.txt",
                source_record_key=stable_source_record_key(
                    "victory", "Pilot1Claims.txt", 2
                ),
            ),
            WoFFVictory(
                id="victory-b",
                pilotId=pilot.id,
                date="1917-04-06",
                time="10:35",
                enemyType="Albatros D.III",
                location="south of Arras",
                source_file="Pilot1Claims.txt",
                source_record_key=stable_source_record_key(
                    "victory", "Pilot1Claims.txt", 3
                ),
            ),
        ]

        assert database.merge_and_write(None, [], victories, []) == pilot.id
        assert database._get_conn().execute(
            "SELECT id FROM victories WHERE pilotId=? ORDER BY id",
            (pilot.id,),
        ).fetchall() == [("victory-a",), ("victory-b",)]

        assert database.merge_and_write(None, [], victories, []) == pilot.id
        assert database._get_conn().execute(
            "SELECT id FROM victories WHERE pilotId=? ORDER BY id",
            (pilot.id,),
        ).fetchall() == [("victory-a",), ("victory-b",)]
    finally:
        database.close()


def test_claims_parser_identity_keeps_identical_occurrences_and_replay_stable(
    tmp_path,
    caplog,
):
    database = DatabaseManager(str(tmp_path / "claims.sqlite"))
    try:
        pilot = _persist_pilot(database)
        claims = (
            "header\n"
            "6;4;1917;10h;35;Arras;x;x;SE.5a;x;Albatros D.III;confirmed\n"
            "6;4;1917;10h;35;Arras;x;x;SE.5a;x;Albatros D.III;confirmed\n"
        ).encode("cp1252")

        first = WoFFPilotDataParser()
        assert first.parse_bytes(claims, "Pilot1Claims.txt")
        assert len(first.victories) == 2
        first_keys = [victory.source_record_key for victory in first.victories]
        assert first_keys[0] != first_keys[1]
        assert all(key.startswith("source-v1:") for key in first_keys)
        assert all("pilot1" not in key for key in first_keys)
        for victory in first.victories:
            victory.pilotId = pilot.id

        caplog.set_level("INFO", logger="WoFFWatch")
        assert database.merge_and_write(None, [], first.victories, []) == pilot.id
        assert "Victory merge outcomes: inserted=2 updated=0 unchanged=0 unresolved=0" in caplog.messages

        replay = WoFFPilotDataParser()
        assert replay.parse_bytes(claims, "Pilot1Claims.txt")
        assert [victory.source_record_key for victory in replay.victories] == first_keys
        for victory in replay.victories:
            victory.pilotId = pilot.id
        caplog.clear()
        assert database.merge_and_write(None, [], replay.victories, []) == pilot.id
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM victories WHERE pilotId=?", (pilot.id,)
        ).fetchone() == (2,)
        assert "Victory merge outcomes: inserted=0 updated=0 unchanged=2 unresolved=0" in caplog.messages
    finally:
        database.close()


def test_xml_source_positions_are_distinct_stable_and_privacy_safe():
    xml = b"""<Campaign>
      <Pilot><PilotName>Synthetic Pilot</PilotName></Pilot>
      <Victories>
        <Victory><Date>1917-04-06</Date><Time>10:35</Time><EnemyType>Albatros D.III</EnemyType></Victory>
        <Victory><Date>1917-04-06</Date><Time>10:35</Time><EnemyType>Albatros D.III</EnemyType></Victory>
      </Victories>
      <Decorations><Decoration><Name>Military Cross</Name></Decoration></Decorations>
    </Campaign>"""
    first = WoFFXMLParser()
    replay = WoFFXMLParser()

    assert first.parse_bytes(xml, "SyntheticCareer.xml")
    assert replay.parse_bytes(xml, "SyntheticCareer.xml")
    keys = [victory.source_record_key for victory in first.victories]
    assert len(keys) == len(set(keys)) == 2
    assert keys == [victory.source_record_key for victory in replay.victories]
    assert all(key.startswith("source-v1:") for key in keys)
    assert all("syntheticcareer" not in key for key in keys)
    assert {victory.source_file for victory in first.victories} == {
        "SyntheticCareer.xml"
    }
    assert {decoration.source_file for decoration in first.decorations} == {
        "SyntheticCareer.xml"
    }


def test_xml_mixed_victory_tags_preserve_document_order_and_existing_alias(
    tmp_path,
):
    initial_xml = b"""<Campaign>
      <Pilot><PilotName>Synthetic Pilot</PilotName></Pilot>
      <Victories>
        <Claim><Date>1917-04-06</Date><EnemyType>Albatros A</EnemyType></Claim>
      </Victories>
    </Campaign>"""
    expanded_xml = b"""<Campaign>
      <Pilot><PilotName>Synthetic Pilot</PilotName></Pilot>
      <Victories>
        <Claim><Date>1917-04-06</Date><EnemyType>Albatros A</EnemyType></Claim>
        <Victory><Date>1917-04-07</Date><EnemyType>Albatros B</EnemyType></Victory>
      </Victories>
    </Campaign>"""
    initial = WoFFXMLParser()
    expanded = WoFFXMLParser()

    assert initial.parse_bytes(initial_xml, "SyntheticCareer.xml")
    assert expanded.parse_bytes(expanded_xml, "SyntheticCareer.xml")
    assert [victory.enemyType for victory in expanded.victories] == [
        "Albatros A",
        "Albatros B",
    ]
    assert (
        expanded.victories[0].source_record_key
        == initial.victories[0].source_record_key
    )

    database = DatabaseManager(str(tmp_path / "xml-document-order.sqlite"))
    try:
        pilot = _persist_pilot(database)
        stable_id = initial.victories[0].id
        for victory in initial.victories:
            victory.pilotId = pilot.id
        assert database.merge_and_write(
            None, [], initial.victories, []
        ) == pilot.id

        for victory in expanded.victories:
            victory.pilotId = pilot.id
        assert database.merge_and_write(
            None, [], expanded.victories, []
        ) == pilot.id
        rows = database._get_conn().execute(
            "SELECT id, enemyType FROM victories ORDER BY date"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0] == (stable_id, "Albatros A")
        assert rows[1][1] == "Albatros B"
    finally:
        database.close()


def test_richer_victory_preserves_id_and_stable_mission_relationship(
    tmp_path,
    caplog,
):
    database = DatabaseManager(str(tmp_path / "victory-enrichment.sqlite"))
    try:
        pilot = _persist_pilot(database)
        mission = WoFFMission(
            id="mission-stable",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:00",
            missionType="Patrol",
            aircraft="SE.5a",
            claimsCount=1,
            source_file="Pilot1Log.txt",
        )
        poor = WoFFVictory(
            id="victory-stable",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            enemyType="Albatros D.III",
            source_file="Pilot1Claims.txt",
            source_record_key=stable_source_record_key(
                "victory", "Pilot1Claims.txt", 2
            ),
        )
        assert database.merge_and_write(None, [mission], [poor], []) == pilot.id

        rich = WoFFVictory(
            id="replacement-import-id",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            enemyType="Albatros D.III",
            victoryType="Destroyed",
            location="north of Arras",
            confirmed=True,
            witnesses="Wingman One",
            notes="Synthetic sanitized evidence.",
            source_file="career.xml",
            source_record_key=stable_source_record_key(
                "victory", "career.xml", 1
            ),
        )
        caplog.set_level("INFO", logger="WoFFWatch")
        caplog.clear()
        assert database.merge_and_write(None, [], [rich], []) == pilot.id
        assert database._get_conn().execute(
            """
            SELECT id, missionId, victoryType, location, confirmed,
                   witnesses, notes, source_file
            FROM victories
            """
        ).fetchall() == [
            (
                "victory-stable",
                "mission-stable",
                "Destroyed",
                "north of Arras",
                1,
                "Wingman One",
                "Synthetic sanitized evidence.",
                "career.xml",
            )
        ]
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM victory_source_records WHERE victoryId=?",
            ("victory-stable",),
        ).fetchone() == (2,)
        assert "Victory merge outcomes: inserted=0 updated=1 unchanged=0 unresolved=0" in caplog.messages

        caplog.clear()
        assert database.merge_and_write(None, [], [poor], []) == pilot.id
        assert database._get_conn().execute(
            "SELECT id, missionId, location, witnesses, source_file FROM victories"
        ).fetchall() == [
            (
                "victory-stable",
                "mission-stable",
                "north of Arras",
                "Wingman One",
                "career.xml",
            )
        ]
        assert "Victory merge outcomes: inserted=0 updated=0 unchanged=1 unresolved=0" in caplog.messages
    finally:
        database.close()


def test_replay_reconciles_legacy_unknown_victory_without_duplicate(
    tmp_path,
):
    database = DatabaseManager(str(tmp_path / "legacy-unknown-victory.sqlite"))
    try:
        pilot = _persist_pilot(database)
        legacy = WoFFVictory(
            id="victory-legacy-ooc",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            enemyType="Albatros D.III",
            victoryType="Out of Control (OOC)",
            source_file="Pilot1Claims.txt",
        )
        assert database.merge_and_write(None, [], [legacy], []) == pilot.id
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM victory_source_records"
        ).fetchone() == (0,)

        replay = WoFFVictory(
            id="victory-corrected-replay",
            pilotId=pilot.id,
            date=legacy.date,
            time=legacy.time,
            enemyType=legacy.enemyType,
            victoryType="Engine exploded",
            source_file=legacy.source_file,
            source_record_key=stable_source_record_key(
                "victory", legacy.source_file, 2
            ),
        )
        assert database.merge_and_write(None, [], [replay], []) == pilot.id

        assert database._get_conn().execute(
            "SELECT id, victoryType FROM victories WHERE pilotId=?",
            (pilot.id,),
        ).fetchall() == [("victory-legacy-ooc", "Engine exploded")]
        assert database._get_conn().execute(
            """
            SELECT victoryId FROM victory_source_records
            WHERE pilotId=? AND source_record_key=?
            """,
            (pilot.id, replay.source_record_key),
        ).fetchall() == [("victory-legacy-ooc",)]
    finally:
        database.close()


def test_legacy_ooc_is_not_rewritten_from_a_different_source(tmp_path):
    database = DatabaseManager(str(tmp_path / "legacy-ooc-source-gate.sqlite"))
    try:
        pilot = _persist_pilot(database)
        legacy = WoFFVictory(
            id="victory-legitimate-ooc",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            enemyType="Albatros D.III",
            victoryType="Out of Control (OOC)",
            source_file="Pilot1Claims.txt",
        )
        replay = WoFFVictory(
            id="victory-other-source",
            pilotId=pilot.id,
            date=legacy.date,
            time=legacy.time,
            enemyType=legacy.enemyType,
            victoryType="Engine exploded",
            source_file="Pilot2Claims.txt",
            source_record_key=stable_source_record_key(
                "victory", "Pilot2Claims.txt", 2
            ),
        )

        assert database.merge_and_write(None, [], [legacy], []) == pilot.id
        assert database.merge_and_write(None, [], [replay], []) == pilot.id

        assert database._get_conn().execute(
            """
            SELECT id, victoryType, source_file FROM victories
            WHERE pilotId=? ORDER BY id
            """,
            (pilot.id,),
        ).fetchall() == [
            (
                "victory-legitimate-ooc",
                "Out of Control (OOC)",
                "Pilot1Claims.txt",
            ),
            (
                "victory-other-source",
                "Engine exploded",
                "Pilot2Claims.txt",
            ),
        ]
    finally:
        database.close()


def test_legacy_ooc_is_not_rewritten_by_a_known_victory_type(tmp_path):
    database = DatabaseManager(str(tmp_path / "legacy-ooc-type-gate.sqlite"))
    try:
        pilot = _persist_pilot(database)
        legacy = WoFFVictory(
            id="victory-legitimate-ooc",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            enemyType="Albatros D.III",
            victoryType="Out of Control (OOC)",
            source_file="Pilot1Claims.txt",
        )
        known_type = WoFFVictory(
            id="victory-known-type",
            pilotId=pilot.id,
            date=legacy.date,
            time=legacy.time,
            enemyType=legacy.enemyType,
            victoryType="Destroyed — In Flames",
            source_file=legacy.source_file,
            source_record_key=stable_source_record_key(
                "victory", legacy.source_file, 2
            ),
        )

        assert database.merge_and_write(None, [], [legacy], []) == pilot.id
        assert database.merge_and_write(None, [], [known_type], []) == pilot.id

        assert database._get_conn().execute(
            "SELECT id, victoryType FROM victories WHERE pilotId=? ORDER BY id",
            (pilot.id,),
        ).fetchall() == [
            ("victory-known-type", "Destroyed — In Flames"),
            ("victory-legitimate-ooc", "Out of Control (OOC)"),
        ]
    finally:
        database.close()


def test_legacy_ooc_is_not_rewritten_without_a_stable_source_key(tmp_path):
    database = DatabaseManager(str(tmp_path / "legacy-ooc-key-gate.sqlite"))
    try:
        pilot = _persist_pilot(database)
        legacy = WoFFVictory(
            id="victory-legitimate-ooc",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            enemyType="Albatros D.III",
            victoryType="Out of Control (OOC)",
            source_file="Pilot1Claims.txt",
        )
        untraceable = WoFFVictory(
            id="victory-without-source-key",
            pilotId=pilot.id,
            date=legacy.date,
            time=legacy.time,
            enemyType=legacy.enemyType,
            victoryType="Engine exploded",
            source_file=legacy.source_file,
        )

        assert database.merge_and_write(None, [], [legacy], []) == pilot.id
        assert database.merge_and_write(
            None, [], [untraceable], []
        ) == pilot.id

        assert database._get_conn().execute(
            "SELECT id, victoryType FROM victories WHERE pilotId=? ORDER BY id",
            (pilot.id,),
        ).fetchall() == [
            ("victory-legitimate-ooc", "Out of Control (OOC)"),
            ("victory-without-source-key", "Engine exploded"),
        ]
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM victory_source_records"
        ).fetchone() == (0,)
    finally:
        database.close()


def test_aliased_replay_without_mission_preserves_stored_relationship(
    tmp_path,
    caplog,
):
    database = DatabaseManager(str(tmp_path / "aliased-parent.sqlite"))
    try:
        pilot = _persist_pilot(database)
        stored_parent, _inference_candidate = _persist_competing_claim_missions(
            database, pilot
        )
        source_key = stable_source_record_key(
            "victory", "Pilot1Claims.txt", 2
        )
        stored = WoFFVictory(
            id="victory-stable",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            missionId=stored_parent.id,
            enemyType="Albatros D.III",
            source_file="Pilot1Claims.txt",
            source_record_key=source_key,
        )
        assert database.merge_and_write(None, [], [stored], []) == pilot.id

        replay = WoFFVictory(
            id="replay-import-id",
            pilotId=pilot.id,
            date=stored.date,
            time=stored.time,
            enemyType=stored.enemyType,
            source_file=stored.source_file,
            source_record_key=source_key,
        )
        caplog.set_level("INFO", logger="WoFFWatch")
        caplog.clear()
        assert database.merge_and_write(None, [], [replay], []) == pilot.id
        assert database._get_conn().execute(
            "SELECT id, missionId FROM victories"
        ).fetchall() == [(stored.id, stored_parent.id)]
        assert (
            "Victory merge outcomes: inserted=0 updated=0 "
            "unchanged=1 unresolved=0"
        ) in caplog.messages
    finally:
        database.close()


def test_migrated_replay_without_alias_preserves_stored_relationship(
    tmp_path,
):
    database = DatabaseManager(str(tmp_path / "migrated-parent.sqlite"))
    try:
        pilot = _persist_pilot(database)
        stored_parent, _inference_candidate = _persist_competing_claim_missions(
            database, pilot
        )
        stored = WoFFVictory(
            id="victory-migrated",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            missionId=stored_parent.id,
            enemyType="Albatros D.III",
            source_file="Pilot1Claims.txt",
        )
        assert database.merge_and_write(None, [], [stored], []) == pilot.id

        source_key = stable_source_record_key(
            "victory", "Pilot1Claims.txt", 2
        )
        replay = WoFFVictory(
            id="replay-import-id",
            pilotId=pilot.id,
            date=stored.date,
            time=stored.time,
            enemyType=stored.enemyType,
            source_file=stored.source_file,
            source_record_key=source_key,
        )
        assert database.merge_and_write(None, [], [replay], []) == pilot.id
        assert database._get_conn().execute(
            "SELECT id, missionId FROM victories"
        ).fetchall() == [(stored.id, stored_parent.id)]
        assert database._get_conn().execute(
            "SELECT victoryId FROM victory_source_records "
            "WHERE pilotId=? AND source_record_key=?",
            (pilot.id, source_key),
        ).fetchone() == (stored.id,)
    finally:
        database.close()


def test_claim_count_policy_associates_only_unambiguous_positive_claim_mission(
    tmp_path,
):
    database = DatabaseManager(str(tmp_path / "claim-policy.sqlite"))
    try:
        pilot = _persist_pilot(database)
        mission = WoFFMission(
            id="mission-stable",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:00",
            missionType="Patrol",
            aircraft="SE.5a",
            claimsCount=2,
        )
        victories = [
            WoFFVictory(
                id=f"victory-{position}",
                pilotId=pilot.id,
                date="1917-04-06",
                time="10:35",
                enemyType="Albatros D.III",
                source_file="Pilot1Claims.txt",
                source_record_key=stable_source_record_key(
                    "victory", "Pilot1Claims.txt", position
                ),
            )
            for position in (2, 3)
        ]
        assert database.merge_and_write(
            None, [mission], victories, []
        ) == pilot.id
        assert database._get_conn().execute(
            """
            SELECT missions.id, missions.claimsCount, COUNT(victories.id)
            FROM missions
            LEFT JOIN victories ON victories.missionId=missions.id
            WHERE missions.id=? GROUP BY missions.id, missions.claimsCount
            """,
            (mission.id,),
        ).fetchall() == [("mission-stable", 2, 2)]
    finally:
        database.close()


def test_mission_only_claim_count_update_logs_mismatch(tmp_path, caplog):
    database = DatabaseManager(str(tmp_path / "mission-only-claims.sqlite"))
    try:
        pilot = _persist_pilot(database)
        mission = WoFFMission(
            id="mission-stable",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:00",
            missionType="Patrol",
            aircraft="SE.5a",
            claimsCount=1,
            source_file="mission.log",
        )
        victory = WoFFVictory(
            id="victory-stable",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            missionId=mission.id,
            enemyType="Albatros D.III",
            source_file="Pilot1Claims.txt",
            source_record_key=stable_source_record_key(
                "victory", "Pilot1Claims.txt", 2
            ),
        )
        assert database.merge_and_write(
            None, [mission], [victory], []
        ) == pilot.id

        refreshed = WoFFMission(
            id=mission.id,
            pilotId=pilot.id,
            date=mission.date,
            time=mission.time,
            missionType=mission.missionType,
            aircraft=mission.aircraft,
            claimsCount=2,
            source_file="mission.log",
        )
        caplog.set_level("WARNING", logger="WoFFWatch")
        caplog.clear()
        assert database.merge_and_write(None, [refreshed], [], []) == pilot.id
        assert database._get_conn().execute(
            """
            SELECT missions.claimsCount, COUNT(victories.id)
            FROM missions
            LEFT JOIN victories ON victories.missionId=missions.id
            WHERE missions.id=?
            GROUP BY missions.id, missions.claimsCount
            """,
            (mission.id,),
        ).fetchone() == (2, 1)
        assert (
            "Victory claim consistency: category=count-mismatch "
            "claims=2 associated=1"
        ) in caplog.messages
    finally:
        database.close()


def test_new_same_source_position_stays_distinct_after_cross_source_enrichment(
    tmp_path,
):
    database = DatabaseManager(str(tmp_path / "post-enrichment.sqlite"))
    try:
        pilot = _persist_pilot(database)
        first = WoFFVictory(
            id="victory-first",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            enemyType="Albatros D.III",
            source_file="Pilot1Claims.txt",
            source_record_key=stable_source_record_key(
                "victory", "Pilot1Claims.txt", 2
            ),
        )
        rich = WoFFVictory(
            id="xml-import",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            enemyType="Albatros D.III",
            location="north of Arras",
            source_file="career.xml",
            source_record_key=stable_source_record_key(
                "victory", "career.xml", 1
            ),
        )
        second = WoFFVictory(
            id="victory-second",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            enemyType="Albatros D.III",
            source_file="Pilot1Claims.txt",
            source_record_key=stable_source_record_key(
                "victory", "Pilot1Claims.txt", 3
            ),
        )

        assert database.merge_and_write(None, [], [first], []) == pilot.id
        assert database.merge_and_write(None, [], [rich], []) == pilot.id
        assert database.merge_and_write(None, [], [second], []) == pilot.id
        assert database._get_conn().execute(
            "SELECT id, location FROM victories ORDER BY id"
        ).fetchall() == [
            ("victory-first", "north of Arras"),
            ("victory-second", ""),
        ]
    finally:
        database.close()


def test_cross_source_enrichment_can_fill_missing_victory_date_and_time(
    tmp_path,
):
    database = DatabaseManager(str(tmp_path / "partial-victory.sqlite"))
    try:
        pilot = _persist_pilot(database)
        partial = WoFFVictory(
            id="victory-stable",
            pilotId=pilot.id,
            enemyType="Albatros D.III",
            source_file="Pilot1Claims.txt",
            source_record_key=stable_source_record_key(
                "victory", "Pilot1Claims.txt", 2
            ),
        )
        enriched = WoFFVictory(
            id="xml-import",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            enemyType="Albatros D.III",
            location="north of Arras",
            source_file="career.xml",
            source_record_key=stable_source_record_key(
                "victory", "career.xml", 1
            ),
        )

        assert database.merge_and_write(None, [], [partial], []) == pilot.id
        assert database.merge_and_write(None, [], [enriched], []) == pilot.id
        assert database._get_conn().execute(
            "SELECT id, date, time, location FROM victories"
        ).fetchall() == [
            ("victory-stable", "1917-04-06", "10:35", "north of Arras")
        ]
    finally:
        database.close()


def test_ambiguous_cross_source_replay_is_observable_and_not_duplicated(
    tmp_path,
    caplog,
):
    database = DatabaseManager(str(tmp_path / "ambiguous.sqlite"))
    try:
        pilot = _persist_pilot(database)
        stored = [
            WoFFVictory(
                id=f"stored-{position}",
                pilotId=pilot.id,
                date="1917-04-06",
                time="10:35",
                enemyType="Albatros D.III",
                source_file="Pilot1Claims.txt",
                source_record_key=stable_source_record_key(
                    "victory", "Pilot1Claims.txt", position
                ),
            )
            for position in (2, 3)
        ]
        assert database.merge_and_write(None, [], stored, []) == pilot.id
        ambiguous = WoFFVictory(
            id="ambiguous-import",
            pilotId=pilot.id,
            date="1917-04-06",
            time="10:35",
            enemyType="Albatros D.III",
            source_file="career.xml",
            source_record_key=stable_source_record_key(
                "victory", "career.xml", 1
            ),
        )

        caplog.set_level("INFO", logger="WoFFWatch")
        caplog.clear()
        assert database.merge_and_write(None, [], [ambiguous], []) == pilot.id
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM victories"
        ).fetchone() == (2,)
        assert "Victory merge unresolved: category=ambiguous-occurrence" in caplog.messages
        assert "Victory merge outcomes: inserted=0 updated=0 unchanged=0 unresolved=1" in caplog.messages
    finally:
        database.close()


def test_richer_decoration_enriches_stable_row_and_poorer_replay_preserves_it(
    tmp_path,
):
    database = DatabaseManager(str(tmp_path / "decorations.sqlite"))
    try:
        pilot = _persist_pilot(database)
        poor = WoFFDecoration(
            id="decoration-stable",
            pilotId=pilot.id,
            name="Military Cross",
            source_file="Pilot1Dossier.txt",
        )
        rich = WoFFDecoration(
            id="decoration-import-id",
            pilotId=pilot.id,
            name="Military Cross",
            date="1917-04-15",
            citation="For leadership over Arras.",
            source_file="career.xml",
        )

        assert database.merge_and_write(None, [], [], [poor]) == pilot.id
        assert database.merge_and_write(None, [], [], [rich]) == pilot.id
        assert database._get_conn().execute(
            "SELECT id, date, citation, source_file FROM decorations"
        ).fetchall() == [
            (
                "decoration-stable",
                "1917-04-15",
                "For leadership over Arras.",
                "career.xml",
            )
        ]

        assert database.merge_and_write(None, [], [], [poor]) == pilot.id
        assert database._get_conn().execute(
            "SELECT id, date, citation, source_file FROM decorations"
        ).fetchall() == [
            (
                "decoration-stable",
                "1917-04-15",
                "For leadership over Arras.",
                "career.xml",
            )
        ]
    finally:
        database.close()
