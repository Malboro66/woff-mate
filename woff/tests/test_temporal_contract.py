import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from ..database import DatabaseManager
from ..models import WoFFMission, WoFFPilot
from .identity_support import dossier_evidence


class TestCanonicalTemporalPersistence(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temporary.close()
        self.database_path = temporary.name
        self.db = DatabaseManager(self.database_path)

    def tearDown(self):
        self.db.close()
        for suffix in ("", "-wal", "-shm", "-journal"):
            path = self.database_path + suffix
            if os.path.exists(path):
                os.unlink(path)

    def _pilot(
        self, pilot_id: str = "temporal-pilot", start_date: str = ""
    ) -> WoFFPilot:
        pilot = WoFFPilot(
            id=pilot_id,
            name=f"Pilot {pilot_id}",
            startDate=start_date,
            source_file="Pilot1Dossier.txt",
        )
        self.assertEqual(
            self.db.merge_and_write(
                pilot, [], [], [], identity=dossier_evidence(1, pilot_id)
            ),
            pilot.id,
        )
        return pilot

    def test_write_boundary_canonicalizes_and_quarantines_invalid_rows(self):
        pilot = self._pilot()
        missions = [
            WoFFMission(
                id="valid", pilotId=pilot.id, date="6/4/1917", time="9:30",
                missionType="Patrol", aircraft="Camel",
            ),
            WoFFMission(
                id="invalid-date", pilotId=pilot.id,
                date="1917-02-30", time="10:30",
                missionType="Patrol", aircraft="Camel",
            ),
            WoFFMission(
                id="invalid-time", pilotId=pilot.id,
                date="1917-04-06", time="24:00",
                missionType="Escort", aircraft="Camel",
            ),
        ]

        with self.assertLogs("WoFFWatch", level="WARNING"):
            self.assertEqual(
                self.db.merge_and_write(None, missions, [], []),
                pilot.id,
            )

        rows = self.db._get_conn().execute(
            "SELECT id, date, time FROM missions WHERE pilotId = ? ORDER BY id",
            (pilot.id,),
        ).fetchall()
        self.assertEqual(rows, [("valid", "1917-04-06", "09:30")])

    def test_reimport_matches_equivalent_legacy_key_without_rewriting_it(self):
        pilot = self._pilot()
        with self.db.transaction():
            self.db._get_conn().execute(
                """
                INSERT INTO missions
                    (id, pilotId, date, time, missionType, aircraft)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy-existing", pilot.id, "6/4/1917", "9:30",
                    "Patrol", "Camel",
                ),
            )

        reimported = WoFFMission(
            id="canonical-reimport",
            pilotId=pilot.id,
            date="1917-04-06",
            time="09:30",
            missionType="Patrol",
            aircraft="Camel",
        )

        self.assertEqual(
            self.db.merge_and_write(None, [reimported], [], []),
            pilot.id,
        )
        self.assertEqual(
            self.db._get_conn().execute(
                """
                SELECT id, date, time FROM missions
                WHERE pilotId = ? ORDER BY id
                """,
                (pilot.id,),
            ).fetchall(),
            [("legacy-existing", "6/4/1917", "9:30")],
        )
        self.assertEqual(
            self.db.get_mission_id_by_natural_key(pilot.id, reimported),
            "legacy-existing",
        )

    def test_game_date_ignores_invalid_legacy_rows_and_never_invents_1917(self):
        no_date = self._pilot("no-date")
        with_start = self._pilot("with-start", "11/11/1918")

        self.assertIsNone(self.db.get_pilot_game_date(no_date.id))
        self.assertEqual(self.db.get_pilot_game_date(with_start.id), "1918-11-11")

        with self.db.transaction():
            self.db._get_conn().executemany(
                """
                INSERT INTO missions
                    (id, pilotId, date, time, missionType, aircraft)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "legacy-invalid", no_date.id, "Tomorrow", "23:59",
                        "Patrol", "Camel",
                    ),
                    ("legacy-1915", no_date.id, "20/09/1915", "9:30", "Patrol", "Camel"),
                    ("legacy-1918", no_date.id, "1918-11-11", "10:30", "Patrol", "Camel"),
                ],
            )

        self.assertEqual(self.db.get_pilot_game_date(no_date.id), "1918-11-11")

    def test_game_date_query_failure_returns_explicit_absence(self):
        pilot = self._pilot()

        with patch.object(
            self.db._pilots,
            "_fetch_all",
            side_effect=sqlite3.OperationalError("synthetic query failure"),
        ), self.assertLogs("WoFFWatch", level="ERROR"):
            self.assertIsNone(self.db.get_pilot_game_date(pilot.id))

    def test_history_is_canonical_newest_first_with_deterministic_ties(self):
        pilot = self._pilot()
        with self.db.transaction():
            self.db._get_conn().executemany(
                """
                INSERT INTO missions
                    (id, pilotId, date, time, missionType, aircraft)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("invalid", pilot.id, "Tomorrow", "23:59", "Patrol", "Camel"),
                    ("missing-time", pilot.id, "1918-11-11", "", "Escort", "Camel"),
                    (
                        "legacy-bad-time", pilot.id, "1918-11-11", "Later",
                        "Balloon", "Camel",
                    ),
                    ("morning", pilot.id, "11/11/1918", "9:30", "Patrol", "Camel"),
                    ("tie-patrol", pilot.id, "1918-11-11", "10:30", "Patrol", "Camel"),
                    ("tie-recon", pilot.id, "1918-11-11", "10:30", "Reconnaissance", "Camel"),
                    ("older", pilot.id, "1915-09-20", "14:00", "Patrol", "Camel"),
                ],
            )

        history = self.db._missions.get_missions_by_pilot(pilot.id)

        self.assertEqual(
            [mission["id"] for mission in history],
            [
                "tie-recon", "tie-patrol", "morning", "missing-time",
                "legacy-bad-time", "older",
            ],
        )
        self.assertEqual(history[2]["date"], "1918-11-11")
        self.assertEqual(history[2]["time"], "09:30")
        self.assertEqual(history[4]["time"], "")

        _, current, rpg_history = self.db.get_mission_and_history(
            pilot.id, "tie-patrol"
        )
        self.assertIsNotNone(current)
        self.assertEqual(
            [mission["id"] for mission in rpg_history],
            [
                "tie-recon", "tie-patrol", "morning", "missing-time",
                "legacy-bad-time", "older",
            ],
        )


if __name__ == "__main__":
    unittest.main()
