import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from ..database import DatabaseManager
from ..identity import (
    PilotIdentityEvidence,
    PilotIdentityKind,
    PilotIdentityRejected,
)
from ..parsers.dossier_parser import WoFFDossierParser
from ..parsers.pilot_data_parser import WoFFPilotDataParser
from ..parsers.xml_parser import WoFFXMLParser
from .test_dossier_parser import _encode_dossier
from .identity_support import dependent_evidence, dossier_evidence


STAT_FIELDS = (
    "missions",
    "flminutes",
    "claimsCount",
    "killsCount",
    "skill",
    "reputation",
)
AUTHORITATIVE_STATS = (12, 845, 7, 5, 68, 420)


class TestPilotStatisticMerge(unittest.TestCase):
    db: DatabaseManager

    def setUp(self):
        tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_db.close()
        self.db_path = tmp_db.name
        self.db = DatabaseManager(self.db_path)
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()
        self.db = None  # type: ignore[assignment]
        gc.collect()
        for ext in ("", "-wal", "-shm", "-journal"):
            path = self.db_path + ext
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except PermissionError:
                    pass

    def _persist_dossier(self, stats=AUTHORITATIVE_STATS):
        lines = ["Null"] * 105
        values = {
            3: "Captain",
            4: "James",
            5: "Hartley",
            11: str(stats[1]),
            16: str(stats[2]),
            17: str(stats[3]),
            41: str(stats[4]),
            46: str(stats[0]),
            52: str(stats[5]),
            83: "No. 56 Sqn",
            84: "SE.5a",
            88: "Filescamp",
            89: "Arras",
        }
        for index, value in values.items():
            lines[index] = value

        parser = WoFFDossierParser()
        encoded = _encode_dossier(lines, "Pilot1Dossier.txt")
        with patch("builtins.open", mock_open(read_data=encoded)):
            self.assertTrue(parser.parse("Pilot1Dossier.txt"))
        self.assertIsNotNone(parser.pilot)
        assert parser.pilot is not None
        pilot = parser.pilot
        self.assertEqual(tuple(getattr(pilot, field) for field in STAT_FIELDS), stats)
        self.assertIsNotNone(
            self.db.merge_and_write(
                pilot, [], [], [], identity=dossier_evidence(1, "stats")
            )
        )

    def _pilot_row(self):
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT missions, flminutes, claimsCount, killsCount, skill, "
                "reputation, rank, squadron, aircraft, aerodrome, sector "
                "FROM pilots WHERE name = 'James Hartley'"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        assert row is not None
        return row

    def _write(self, filename: str, content: str) -> str:
        path = Path(self.tmp_dir.name) / filename
        path.write_text(content, encoding="cp1252")
        return str(path)

    def _merge_text_source(self, filename: str, content: str):
        path = self._write(filename, content)
        parser = WoFFPilotDataParser()
        self.assertTrue(parser.parse(path))
        self.assertIsNotNone(parser.pilot)
        assert parser.pilot is not None
        self.assertTrue(
            all(getattr(parser.pilot, field) is None for field in STAT_FIELDS)
        )
        self.assertEqual(
            self.db.merge_and_write(
                parser.pilot,
                parser.missions,
                parser.victories,
                [],
                identity=dependent_evidence(1, "stats"),
            ),
            self.db.resolve_pilot_id(
                parser.pilot.name, source_file=parser.pilot.source_file
            ),
        )
        return parser

    def test_partial_text_sources_preserve_dossier_statistics(self):
        self._persist_dossier()
        sources = (
            (
                "Pilot1Log.txt",
                "1\n6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;"
                "SE.5a;No. 56 Sqn;troops;Target;N50;E2;;Mission completed.\n",
            ),
            (
                "Pilot1Claims.txt",
                "1\n6;4;1917;10;35;Arras;Filescamp;OP;SE.5a;1;"
                "Albatros D.III;Destroyed Confirmed;Albatros\n",
            ),
            (
                "Pilot1Squads.txt",
                "7;4;1917;10;30;Flanders;New Base;No. 60 Sqn;Sopwith Camel;"
                "Camel;Transferred, rank: Major.;No. 60 Squadron\n",
            ),
        )

        for filename, content in sources:
            with self.subTest(filename=filename):
                self._merge_text_source(filename, content)
                self.assertEqual(self._pilot_row()[:6], AUTHORITATIVE_STATS)

        row = self._pilot_row()
        self.assertEqual(
            row[6:],
            ("Major", "No. 60 Sqn", "Sopwith Camel", "New Base", "Flanders"),
        )

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM missions").fetchone()[0], 1
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM victories").fetchone()[0], 1
            )
        finally:
            conn.close()

    def test_partial_xml_is_rejected_without_changing_dossier_state(self):
        self._persist_dossier()
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Campaign>
  <Pilot>
    <PilotName>James Hartley</PilotName>
    <Rank>Major</Rank>
    <Squadron>No. 60 Sqn</Squadron>
    <Aircraft>Sopwith Camel</Aircraft>
    <Aerodrome>Valheureux</Aerodrome>
    <Sector>Flanders</Sector>
  </Pilot>
</Campaign>
"""
        path = self._write("campaign.xml", xml)
        parser = WoFFXMLParser()
        self.assertTrue(parser.parse(path))
        assert parser.pilot is not None
        self.assertTrue(
            all(getattr(parser.pilot, field) is None for field in STAT_FIELDS)
        )

        unresolved = PilotIdentityEvidence(PilotIdentityKind.UNRESOLVED)
        for _ in range(2):
            with self.assertRaisesRegex(
                PilotIdentityRejected, "unsupported-identity-source"
            ):
                self.db.merge_and_write(
                    parser.pilot,
                    parser.missions,
                    parser.victories,
                    parser.decorations,
                    identity=unresolved,
                )

        row = self._pilot_row()
        self.assertEqual(row[:6], AUTHORITATIVE_STATS)
        self.assertEqual(
            row[6:],
            ("Captain", "No. 56 Sqn", "SE.5a", "Filescamp", "Arras"),
        )

    def test_authoritative_zero_overwrites_older_statistics(self):
        self._persist_dossier()
        self._persist_dossier((0, 0, 0, 0, 0, 0))
        self.assertEqual(self._pilot_row()[:6], (0, 0, 0, 0, 0, 0))

    def test_reprocessing_partial_sources_is_idempotent(self):
        self._persist_dossier()
        filename = "Pilot1Log.txt"
        content = (
            "1\n6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;SE.5a;"
            "No. 56 Sqn;troops;Target;N50;E2;;Mission completed.\n"
        )
        self._merge_text_source(filename, content)
        self._merge_text_source(filename, content)

        self.assertEqual(self._pilot_row()[:6], AUTHORITATIVE_STATS)
        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM missions").fetchone()[0], 1
            )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
