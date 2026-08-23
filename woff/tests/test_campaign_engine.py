import unittest
import tempfile
import os
import sqlite3
import gc
from typing import Any
from unittest.mock import patch


from ..database import DatabaseManager
from ..campaign_engine import CampaignEngine
from ..models import WoFFPilot, WoFFMission
from .identity_support import dossier_evidence

class TestCampaignEngine(unittest.TestCase):
    # Anotações de tipo ao nível da classe
    db: DatabaseManager
    engine: CampaignEngine
    tmp_db: Any
    
    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_db.close()
        self.db = DatabaseManager(self.tmp_db.name)
        self.engine = CampaignEngine(self.db)
    
    def tearDown(self):
        # FIX: Ignorar o erro de tipo ao atribuir None, pois é intencional para o GC
        self.engine = None  # type: ignore[assignment]
        self.db = None      # type: ignore[assignment]
        gc.collect()
        
        for ext in ["", "-wal", "-shm"]:
            path = self.tmp_db.name + ext
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except PermissionError:
                    pass
    
    def test_process_mission_end_race_condition_mocked(self):
        """
        Testa a Race Condition de forma determinística.
        """
        pilot = WoFFPilot(
            name="Race Pilot", source_file="Pilot1Dossier.txt"
        )
        self.db.merge_and_write(
            pilot, [], [], [], identity=dossier_evidence(1)
        )
        
        with patch.object(self.db, 'get_mission_and_history', return_value=(None, None, [])):
            result = self.engine.process_mission_end(pilot.id, "M_RACE")
        
        self.assertIsNone(result)
        
        conn = sqlite3.connect(self.tmp_db.name)
        cursor = conn.execute("SELECT COUNT(*) FROM diary_entries")
        self.assertEqual(cursor.fetchone()[0], 0)
        
        cursor = conn.execute("SELECT COUNT(*) FROM pilot_rpg_stats")
        self.assertEqual(cursor.fetchone()[0], 0)
        conn.close()
    
    def test_process_mission_end_success(self):
        """Testa processamento completo de missão (RPG Stats e Diário)."""
        pilot = WoFFPilot(
            name="Test Pilot", source_file="Pilot1Dossier.txt"
        )
        mission = WoFFMission(id="M001", pilotId=pilot.id, date="1917-04-06", time="10:30", missionType="OP")
        self.db.merge_and_write(
            pilot, [mission], [], [], identity=dossier_evidence(1)
        )
        
        self.engine.process_mission_end(pilot.id, "M001")
        
        conn = sqlite3.connect(self.tmp_db.name)
        
        cursor = conn.execute("SELECT * FROM pilot_rpg_stats WHERE pilotId = ?", (pilot.id,))
        self.assertIsNotNone(cursor.fetchone())
        
        cursor = conn.execute("SELECT * FROM diary_entries WHERE missionId = ?", ("M001",))
        diary_row = cursor.fetchone()
        self.assertIsNotNone(diary_row)
        self.assertIn("1917-04-06", diary_row[4]) 
        
        conn.close()

    def _mission_fixture(self, suffix):
        pilot = WoFFPilot(
            id=f"P_{suffix}",
            name=f"Pilot {suffix}",
            source_file="Pilot1Dossier.txt",
        )
        mission = WoFFMission(
            id=f"M_{suffix}", pilotId=pilot.id, date="1917-05-10",
            time="09:00", missionType="Patrol"
        )
        self.assertEqual(
            self.db.merge_and_write(
                pilot, [mission], [], [], identity=dossier_evidence(1)
            ),
            pilot.id,
        )
        return pilot, mission

    def test_process_mission_end_narrative_failure_performs_no_writes(self):
        pilot, mission = self._mission_fixture("NARRATIVE_FAILURE")

        with patch(
            "woff.campaign_engine.narrative_generator.generate",
            side_effect=RuntimeError("narrative failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "narrative failure"):
                self.engine.process_mission_end(pilot.id, mission.id)

        conn = self.db._get_conn()
        self.assertIsNone(conn.execute(
            "SELECT 1 FROM pilot_rpg_stats WHERE pilotId = ?", (pilot.id,)
        ).fetchone())
        self.assertIsNone(conn.execute(
            "SELECT 1 FROM diary_entries WHERE missionId = ?", (mission.id,)
        ).fetchone())

    def test_process_mission_end_diary_failure_rolls_back_rpg_update(self):
        pilot, mission = self._mission_fixture("DIARY_FAILURE")

        with patch(
            "woff.campaign_engine.narrative_generator.generate",
            return_value="Generated before writing",
        ), patch.object(
            self.db, "save_diary_entry", side_effect=RuntimeError("diary failure")
        ), self.assertLogs("WoFFWatch", level="INFO") as captured:
            with self.assertRaisesRegex(RuntimeError, "diary failure"):
                self.engine.process_mission_end(pilot.id, mission.id)

        self.assertIsNone(self.db._get_conn().execute(
            "SELECT 1 FROM pilot_rpg_stats WHERE pilotId = ?", (pilot.id,)
        ).fetchone())
        messages = "\n".join(captured.output)
        for success_message in ("RPG Atualizado", "RPG Stats", "📝 Diário:"):
            self.assertNotIn(success_message, messages)

    def test_process_mission_end_success_commits_rpg_and_diary_together(self):
        pilot, mission = self._mission_fixture("ATOMIC_SUCCESS")
        transaction_state = []
        success_log_state = []
        update = self.db.update_pilot_rpg_stats
        save = self.db.save_diary_entry

        def observed_update(*args, **kwargs):
            transaction_state.append(("rpg", self.db._get_conn().in_transaction))
            return update(*args, **kwargs)

        def observed_save(*args, **kwargs):
            transaction_state.append(("diary", self.db._get_conn().in_transaction))
            return save(*args, **kwargs)

        def observed_log(message, *args, **kwargs):
            if "RPG Atualizado" in message:
                success_log_state.append(self.db._get_conn().in_transaction)

        with patch(
            "woff.campaign_engine.narrative_generator.generate",
            return_value="Atomic narrative",
        ), patch.object(
            self.db, "update_pilot_rpg_stats", side_effect=observed_update
        ), patch.object(
            self.db, "save_diary_entry", side_effect=observed_save
        ), patch("woff.campaign_engine.log.info", side_effect=observed_log):
            result = self.engine.process_mission_end(pilot.id, mission.id)

        self.assertEqual(
            (result, transaction_state),
            (True, [("rpg", True), ("diary", True)]),
        )
        self.assertEqual(success_log_state, [False])
        with sqlite3.connect(self.tmp_db.name) as observer:
            self.assertIsNotNone(observer.execute(
                "SELECT 1 FROM pilot_rpg_stats WHERE pilotId = ?", (pilot.id,)
            ).fetchone())
            self.assertEqual(observer.execute(
                "SELECT narrative FROM diary_entries WHERE missionId = ?", (mission.id,)
            ).fetchone(), ("Atomic narrative",))

    def test_process_mission_end_duplicate_diary_has_no_false_success(self):
        pilot, mission = self._mission_fixture("DUPLICATE")
        self.assertTrue(self.db.save_diary_entry(
            pilot.id, mission.id, mission.date, "Existing narrative"
        ))

        with patch(
            "woff.campaign_engine.narrative_generator.generate",
            return_value="Duplicate narrative",
        ), self.assertLogs("WoFFWatch", level="INFO") as captured:
            result = self.engine.process_mission_end(pilot.id, mission.id)

        self.assertFalse(result)
        messages = "\n".join(captured.output)
        for success_message in ("RPG Atualizado", "RPG Stats", "📝 Diário:"):
            self.assertNotIn(success_message, messages)
        self.assertEqual(self.db._get_conn().execute(
            "SELECT narrative FROM diary_entries WHERE missionId = ?", (mission.id,)
        ).fetchall(), [("Existing narrative",)])
    
    def test_process_life_events_promotion(self):
        """Testa deteção de promoção e geração de entrada de diário."""
        pilot = WoFFPilot(
            name="Promo Pilot",
            rank="Lieutenant",
            status="Active",
            source_file="Pilot1Dossier.txt",
        )
        self.db.merge_and_write(
            pilot, [], [], [], identity=dossier_evidence(1)
        )
        
        self.engine.process_life_events(
            pilot.id, "Active", "Captain", "Active", "Lieutenant",
            event_date="1917-06-01",
        )
        
        conn = sqlite3.connect(self.tmp_db.name)
        cursor = conn.execute("SELECT narrative FROM diary_entries WHERE pilotId = ?", (pilot.id,))
        row = cursor.fetchone()
        
        self.assertIsNotNone(row)
        narrative = row[0].lower()
        self.assertIn("promovido", narrative)
        self.assertIn("captain", narrative)
        
        conn.close()

    def test_life_event_without_a_game_date_is_not_persisted(self):
        pilot = WoFFPilot(
            name="No Date Pilot",
            rank="Lieutenant",
            status="Active",
            source_file="Pilot1Dossier.txt",
        )
        self.db.merge_and_write(
            pilot, [], [], [], identity=dossier_evidence(1)
        )

        result = self.engine.process_life_events(
            pilot.id, "Active", "Captain", "Active", "Lieutenant"
        )

        self.assertFalse(result)
        self.assertEqual(
            self.db._get_conn().execute(
                "SELECT COUNT(*) FROM diary_entries WHERE pilotId = ?",
                (pilot.id,),
            ).fetchone(),
            (0,),
        )

    def test_life_event_without_explicit_date_uses_campaign_calendar(self):
        pilot = WoFFPilot(
            name="Historical Date Pilot",
            rank="Lieutenant",
            status="Active",
            startDate="1917-04-06",
            source_file="Pilot1Dossier.txt",
        )
        self.db.merge_and_write(
            pilot, [], [], [], identity=dossier_evidence(1)
        )

        result = self.engine.process_life_events(
            pilot.id, "Active", "Captain", "Active", "Lieutenant"
        )

        self.assertTrue(result)
        self.assertEqual(
            self.db._get_conn().execute(
                "SELECT entry_date FROM diary_entries WHERE pilotId = ?",
                (pilot.id,),
            ).fetchone(),
            ("1917-04-06",),
        )

    def test_invalid_legacy_mission_does_not_create_derived_state(self):
        pilot = WoFFPilot(
            name="Legacy Date Pilot",
            source_file="Pilot1Dossier.txt",
        )
        self.db.merge_and_write(
            pilot, [], [], [], identity=dossier_evidence(1)
        )
        with self.db.transaction():
            self.db._get_conn().execute(
                """
                INSERT INTO missions
                    (id, pilotId, date, time, missionType, aircraft)
                VALUES ('legacy-invalid', ?, 'Tomorrow', '23:59', 'Patrol', 'Camel')
                """,
                (pilot.id,),
            )

        result = self.engine.process_mission_end(pilot.id, "legacy-invalid")

        self.assertFalse(result)
        self.assertEqual(
            self.db._get_conn().execute(
                "SELECT COUNT(*) FROM pilot_rpg_stats WHERE pilotId = ?",
                (pilot.id,),
            ).fetchone(),
            (0,),
        )
        self.assertEqual(
            self.db._get_conn().execute(
                "SELECT COUNT(*) FROM diary_entries WHERE pilotId = ?",
                (pilot.id,),
            ).fetchone(),
            (0,),
        )

    def test_life_event_for_duplicate_name_uses_explicit_target_id(self):
        first = WoFFPilot(
            id="same-name-a",
            name="Same Name",
            rank="Lieutenant",
            source_file="Pilot1Dossier.txt",
        )
        second = WoFFPilot(
            id="same-name-b",
            name="Same Name",
            rank="Lieutenant",
            source_file="Pilot2Dossier.txt",
        )
        self.db.merge_and_write(
            first, [], [], [], identity=dossier_evidence(1, "first")
        )
        self.db.merge_and_write(
            second, [], [], [], identity=dossier_evidence(2, "second")
        )

        self.engine.process_life_events(
            second.id,
            "Active",
            "Captain",
            "Active",
            "Lieutenant",
            event_date="1917-06-01",
        )

        conn = self.db._get_conn()
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM diary_entries WHERE pilotId=?",
                (first.id,),
            ).fetchone(),
            (0,),
        )
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM diary_entries WHERE pilotId=?",
                (second.id,),
            ).fetchone(),
            (1,),
        )

if __name__ == "__main__":
    unittest.main()
