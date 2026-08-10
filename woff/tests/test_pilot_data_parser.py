import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open


from ..parsers.pilot_data_parser import WoFFPilotDataParser
from ..parsers.xml_parser import WoFFXMLParser
from ..rpg_system import RPGSystem

class TestWoFFPilotDataParser(unittest.TestCase):
    
    def test_parse_log_file(self):
        """Testa parsing de ficheiro de log de missões."""
        # A primeira linha é o contador de registos (ignorada pelo parser)
        # O parser precisa de pelo menos 14 colunas (índice 13 = Esquadrão)
        mock_content = "1\n"
        mock_content += "6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;SE.5a;No. 56 Sqn RFC;troops;Army Camp;N50*17;E2*42;;; Final Status: Landed safely.;\n"
        
        parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data=mock_content)):
            ok = parser.parse("Pilot1Log.txt")
        
        self.assertTrue(ok)
        self.assertEqual(len(parser.missions), 1)
        
        m = parser.missions[0]
        self.assertEqual(m.date, "1917-04-06")
        self.assertEqual(m.time, "10:30")  # Testa a extração da hora!
        self.assertEqual(m.sector, "Arras")
        self.assertEqual(m.aircraft, "SE.5a")
        self.assertEqual(m.squadron, "No. 56 Sqn RFC")
    

    def test_parse_log_populates_wounds_and_damage_flags(self):
        """PilotLog.txt deve popular explicitamente dano e ferimentos."""
        mock_content = "2\n"
        mock_content += "6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;SE.5a;No. 56 Sqn RFC;troops;Army Camp;N50*17;E2*42;Damaged;Wounded; Final Status: Crash landed wounded.;\n"
        mock_content += "7;4;1917;11;00;Arras;Filescamp;OP;SE.5a;;45;100;SE.5a;No. 56 Sqn RFC;troops;Army Camp;N50*17;E2*42;No;0; Final Status: Landed safely.;\n"

        parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data=mock_content)):
            ok = parser.parse("Pilot1Log.txt")

        self.assertTrue(ok)
        self.assertEqual(len(parser.missions), 2)
        self.assertTrue(parser.missions[0].damageReceived)
        self.assertTrue(parser.missions[0].woundsReceived)
        self.assertFalse(parser.missions[1].damageReceived)
        self.assertFalse(parser.missions[1].woundsReceived)

    def test_parse_log_damage_wounds_match_xml_boolean_semantics(self):
        """TXT e XML devem produzir os mesmos booleanos para missão equivalente."""
        mock_content = "1\n"
        mock_content += "6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;SE.5a;No. 56 Sqn RFC;troops;Army Camp;N50*17;E2*42;Yes;1; Final Status: Returned damaged and wounded.;\n"

        txt_parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data=mock_content)):
            self.assertTrue(txt_parser.parse("Pilot1Log.txt"))

        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Campaign>
  <Pilot><PilotName>Test Pilot</PilotName><Status>Active</Status></Pilot>
  <Missions>
    <Mission>
      <Date>1917-04-06</Date><Time>10:30</Time><Type>OP</Type>
      <Aircraft>SE.5a</Aircraft><Damage>Yes</Damage><Wounds>1</Wounds>
    </Mission>
  </Missions>
</Campaign>
"""
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as f:
            f.write(xml)
            xml_path = f.name
        try:
            xml_parser = WoFFXMLParser()
            self.assertTrue(xml_parser.parse(xml_path))
        finally:
            os.unlink(xml_path)

        self.assertEqual(
            txt_parser.missions[0].damageReceived,
            xml_parser.missions[0].damageReceived,
        )
        self.assertEqual(
            txt_parser.missions[0].woundsReceived,
            xml_parser.missions[0].woundsReceived,
        )

    def test_parse_log_flags_feed_fatigue_calculation(self):
        """Ferimento e dano vindos do TXT devem impactar fadiga downstream."""
        mock_content = "1\n"
        mock_content += "6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;SE.5a;No. 56 Sqn RFC;troops;Army Camp;N50*17;E2*42;1;Wounded; Final Status: Crash landed wounded.;\n"

        parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data=mock_content)):
            self.assertTrue(parser.parse("Pilot1Log.txt"))

        mission = parser.missions[0]
        rng = Mock()
        rng.random.return_value = 1.0
        fatigue = RPGSystem(rng=rng).calculate_fatigue([mission.__dict__])

        self.assertEqual(fatigue, 30)

    def test_parse_claims_file(self):
        """Testa parsing de ficheiro de vitórias (Claims) e confirmação."""
        # Usar 2 registos para testar vitória confirmada e não confirmada
        mock_content = "2\n"
        # 1: Destruído em chamas (não contém "confirmed" -> False)
        mock_content += "6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;1;Albatros D.III;Destroyed in flames;Albatros\n"
        # 2: Forçado a aterrar (contém "Confirmed" -> True)
        mock_content += "7;4;1917;12;00;Arras;Filescamp;OP;SE.5a;1;DFW C.V;Forced to land Confirmed;DFW\n"
        
        parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data=mock_content)):
            ok = parser.parse("Pilot1Claims.txt")
            
        self.assertTrue(ok)
        self.assertEqual(len(parser.victories), 2)
        
        # Vitória 1 (Não confirmada)
        v1 = parser.victories[0]
        self.assertEqual(v1.date, "1917-04-06")
        self.assertEqual(v1.time, "10:30")
        self.assertEqual(v1.enemyType, "Albatros D.III")
        self.assertEqual(v1.victoryType, "Destroyed — In Flames") # Normalizado pelo maps.py
        # FIX: "Destroyed in flames" não contém a palavra "confirmed"
        self.assertFalse(v1.confirmed) 
        
        # Vitória 2 (Confirmada)
        v2 = parser.victories[1]
        self.assertEqual(v2.date, "1917-04-07")
        self.assertEqual(v2.time, "12:00")
        self.assertEqual(v2.enemyType, "DFW C.V")
        self.assertEqual(v2.victoryType, "Forced to Land") # Normalizado
        self.assertTrue(v2.confirmed) # Contém "Confirmed"
    
    def test_parse_squads_file(self):
        """Testa parsing de histórico de esquadrões."""
        # Sem cabeçalho, o parser lê a última linha
        mock_content = "6;4;1917;10;30;Flanders;Filescamp;No. 56 Sqn RFC;SE.5a;SE.5a;Enlisted, based at Filescamp, rank: Captain.;No. 56 Squadron\n"
        
        parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data=mock_content)):
            ok = parser.parse("Pilot1Squads.txt")
            
        self.assertTrue(ok)
        self.assertIsNotNone(parser.pilot)
        
        # Type narrowing para o Pyright compreender que não é None
        assert parser.pilot is not None
        p = parser.pilot
        
        self.assertEqual(p.squadron, "No. 56 Sqn RFC")
        self.assertEqual(p.aircraft, "SE.5a")
        self.assertEqual(p.aerodrome, "Filescamp")
        self.assertEqual(p.sector, "Flanders")
        # Testa a extração da patente via Regex na coluna 10
        self.assertEqual(p.rank, "Captain")
    
    def test_pilot_id_placeholder(self):
        """Testa que pilot.name é um placeholder ('Pilot 1') antes do Dossier ser lido."""
        mock_content = "1\n6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;SE.5a;No. 56 Sqn RFC;\n"
        
        parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data=mock_content)):
            parser.parse("Pilot1Log.txt")
            
        self.assertIsNotNone(parser.pilot)
        
        # Type narrowing para o Pyright compreender que não é None
        assert parser.pilot is not None
        
        # O parser extrai o ID do nome do ficheiro e formata como "Pilot 1"
        self.assertEqual(parser.pilot.name, "Pilot 1")
        # O database.py deverá resolver este "Pilot 1" para o UUID real usando GLOB no source_file

VERIFIED_FIELDS = [
    "6/", "4/", "1917", "10h", "30", "Flanders", "SampleBase",
    "Patrol", "SE.5a", "", "45", "100", "SE5a", "Sample Squadron",
    "troops", "Sample Target", "N50*00'00.0000", "E2*00'00.0000", "",
    "Final Status: Mission completed.",
]

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "pilotlog"
PILOT1_SAMPLE = (FIXTURE_DIR / "pilot1_sanitized.txt").read_text(encoding="utf-8")
PILOT2_SAMPLE = (FIXTURE_DIR / "pilot2_sanitized.txt").read_text(encoding="utf-8")
PILOT3_SAMPLE = (FIXTURE_DIR / "pilot3_sanitized.txt").read_text(encoding="utf-8")


class TestPilotLogRecordClassification(unittest.TestCase):
    def parse_content(self, content, filename="Pilot1Log.txt"):
        parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data=content)):
            result = parser.parse(filename)
        return parser, result

    @staticmethod
    def line(fields=None, terminal=False):
        value = ";".join(fields or VERIFIED_FIELDS)
        return value + (";" if terminal else "")

    def test_verified_layout_with_and_without_terminal_semicolon(self):
        for terminal in (False, True):
            with self.subTest(terminal=terminal):
                parser, ok = self.parse_content("1\n" + self.line(terminal=terminal) + "\n")
                self.assertTrue(ok)
                self.assertEqual(len(parser.missions), 1)
                mission = parser.missions[0]
                self.assertEqual(mission.notes, VERIFIED_FIELDS[19])
                self.assertFalse(mission.damageReceived)
                self.assertFalse(mission.woundsReceived)

    def test_verified_notes_with_semicolon_are_imported(self):
        fields = VERIFIED_FIELDS.copy()
        fields[19] = "Final Status: landed; aircraft recovered."
        parser, ok = self.parse_content("1\n" + self.line(fields) + "\n")
        self.assertTrue(ok)
        self.assertEqual(len(parser.missions), 1)
        self.assertEqual(
            parser.missions[0].notes,
            "Final Status: landed;aircraft recovered.",
        )

    def test_verified_notes_preserve_multiple_semicolons_and_terminal_delimiter(self):
        fields = VERIFIED_FIELDS.copy()
        fields[19] = "First; second; third"
        parser, ok = self.parse_content("1\n" + self.line(fields, terminal=True) + "\n")
        self.assertTrue(ok)
        self.assertEqual(parser.missions[0].notes, "First;second;third")

    def test_verified_boolean_looking_note_prefixes_are_notes(self):
        for prefix in ("No", "Yes", "False", "Wounded"):
            with self.subTest(prefix=prefix):
                fields = VERIFIED_FIELDS.copy()
                fields[19] = prefix + "; this is still the mission report"
                parser, ok = self.parse_content("1\n" + self.line(fields) + "\n")
                self.assertTrue(ok)
                mission = parser.missions[0]
                self.assertEqual(mission.notes, prefix + ";this is still the mission report")
                self.assertFalse(mission.damageReceived)
                self.assertFalse(mission.woundsReceived)

    def test_extended_notes_preserve_semicolons(self):
        fields = VERIFIED_FIELDS[:18] + ["Damaged", "No", "one; two; three"]
        parser, ok = self.parse_content("1\n" + self.line(fields) + "\n")
        self.assertTrue(ok)
        self.assertEqual(parser.missions[0].notes, "one;two;three")
        self.assertTrue(parser.missions[0].damageReceived)
        self.assertFalse(parser.missions[0].woundsReceived)

    def test_result_terms_after_semicolon_keep_precedence(self):
        for notes, expected in (
            ("Forced down; crash on landing", "Crash Landing — Survived"),
            ("Aircraft crashed; pilot killed", "Shot Down — KIA"),
        ):
            with self.subTest(notes=notes):
                fields = VERIFIED_FIELDS.copy()
                fields[19] = notes
                parser, ok = self.parse_content("1\n" + self.line(fields) + "\n")
                self.assertTrue(ok)
                self.assertEqual(parser.missions[0].result, expected)

    def test_notes_limit_is_applied_after_semicolon_reconstruction(self):
        fields = VERIFIED_FIELDS.copy()
        fields[19] = ("a" * 300) + "; " + ("b" * 300)
        parser, ok = self.parse_content("1\n" + self.line(fields) + "\n")
        self.assertTrue(ok)
        self.assertEqual(len(parser.missions[0].notes), 500)
        self.assertIn(";", parser.missions[0].notes)

    def test_reserved_index_is_independent_from_notes(self):
        fields = VERIFIED_FIELDS.copy()
        fields[18] = "reserved value"
        fields[19] = "Only these are notes"
        parser, _ = self.parse_content("1\n" + self.line(fields) + "\n")
        self.assertEqual(parser.missions[0].notes, "Only these are notes")
        self.assertFalse(parser.missions[0].woundsReceived)

    def test_notes_are_limited_to_existing_maximum(self):
        fields = VERIFIED_FIELDS.copy()
        fields[19] = "n" * 501
        parser, _ = self.parse_content("1\n" + self.line(fields) + "\n")
        self.assertEqual(parser.missions[0].notes, "n" * 500)

    def test_extended_layout_independent_flags_and_terminal_semicolon(self):
        for terminal in (False, True):
            fields = VERIFIED_FIELDS[:18] + ["Damaged", "No", "extended notes"]
            parser, ok = self.parse_content("1\n" + self.line(fields, terminal) + "\n")
            self.assertTrue(ok)
            self.assertTrue(parser.missions[0].damageReceived)
            self.assertFalse(parser.missions[0].woundsReceived)
            self.assertEqual(parser.missions[0].notes, "extended notes")

    def test_damage_and_wounds_are_independent(self):
        for damage, wounds, expected in (("Yes", "0", (True, False)), ("No", "Wounded", (False, True))):
            with self.subTest(damage=damage, wounds=wounds):
                fields = VERIFIED_FIELDS[:18] + [damage, wounds, "notes"]
                parser, _ = self.parse_content("1\n" + self.line(fields) + "\n")
                self.assertEqual((parser.missions[0].damageReceived, parser.missions[0].woundsReceived), expected)

    def test_all_strict_boolean_tokens_case_and_whitespace(self):
        false_tokens = ("", "0", "No", "False", "None", "Undamaged")
        true_tokens = ("1", "Yes", "True", "Damage", "Damaged", "Wound", "Wounded", "Injured")
        for token in false_tokens:
            with self.subTest(token=token):
                self.assertFalse(WoFFPilotDataParser._bool_field("  " + token.swapcase() + "  "))
        for token in true_tokens:
            with self.subTest(token=token):
                self.assertTrue(WoFFPilotDataParser._bool_field("  " + token.swapcase() + "  "))
        self.assertIsNone(WoFFPilotDataParser._bool_field("unexpected narrative"))

    def test_ambiguous_extended_record_is_skipped(self):
        ambiguous = VERIFIED_FIELDS[:18] + ["perhaps", "Wounded", "secret complete record text"]
        content = "2\n" + self.line(ambiguous) + "\n" + self.line() + "\n"
        with self.assertLogs("WoFFWatch", level="WARNING") as captured:
            parser, ok = self.parse_content(content)
        self.assertTrue(ok)
        self.assertEqual(len(parser.missions), 1)
        logged = " ".join(captured.output)
        self.assertIn("Pilot1Log.txt", logged)
        self.assertIn("line=2", logged)
        self.assertIn("fields=21", logged)
        self.assertNotIn("secret complete record text", logged)

    def test_unknown_record_log_is_safe_and_identifies_the_record(self):
        source_line = ";".join(["private complete source line"] + ["x"] * 21)
        with self.assertLogs("WoFFWatch", level="WARNING") as captured:
            parser, _ = self.parse_content("1\n" + source_line + "\n")
        self.assertEqual(parser.missions, [])
        logged = " ".join(captured.output)
        self.assertIn("source=Pilot1Log.txt", logged)
        self.assertIn("line=2", logged)
        self.assertIn("category=unknown", logged)
        self.assertIn("fields=22", logged)
        self.assertNotIn(source_line, logged)
        self.assertNotIn("private complete source line", logged)

    def test_result_classification_precedence(self):
        cases = (
            ("The pilot was KILLED.", "Shot Down — KIA"),
            ("A CRASH occurred.", "Crash Landing — Survived"),
            ("Crash; pilot killed".replace(";", ","), "Shot Down — KIA"),
            ("Aircraft Destroyed", "Completed"),
            ("Routine landing", "Completed"),
        )
        for notes, expected in cases:
            with self.subTest(notes=notes):
                fields = VERIFIED_FIELDS.copy(); fields[19] = notes
                parser, _ = self.parse_content("1\n" + self.line(fields) + "\n")
                mission = parser.missions[0]
                self.assertEqual(mission.result, expected)
                if notes == "Aircraft Destroyed":
                    self.assertFalse(mission.damageReceived); self.assertFalse(mission.woundsReceived)

    def test_claim_confirmation_is_not_a_mission_and_later_mission_survives(self):
        claim = PILOT2_SAMPLE.splitlines()[3]
        content = "3\n" + self.line() + "\n" + claim + "\n" + self.line() + "\n"
        parser, ok = self.parse_content(content)
        self.assertTrue(ok)
        self.assertEqual(len(parser.missions), 2)

    def test_zero_counter_and_header_are_ignored(self):
        parser, ok = self.parse_content(PILOT3_SAMPLE, "Pilot3Log.txt")
        self.assertFalse(ok)
        self.assertEqual(parser.missions, [])

    def test_incomplete_unsupported_and_malformed_records_do_not_stop_processing(self):
        malformed_date = VERIFIED_FIELDS.copy(); malformed_date[0] = "not-a-day"
        malformed_time = VERIFIED_FIELDS.copy(); malformed_time[3] = "not-an-hour"
        content = "5\nshort;record\n" + ";".join(["x"] * 22) + "\n" + self.line(malformed_date) + "\n" + self.line(malformed_time) + "\n" + self.line() + "\n"
        with self.assertLogs("WoFFWatch", level="WARNING"):
            parser, ok = self.parse_content(content)
        self.assertTrue(ok)
        self.assertEqual(len(parser.missions), 1)

    def test_inline_sanitized_samples_end_to_end(self):
        for filename, sample, count in (("Pilot1Log.txt", PILOT1_SAMPLE, 2), ("Pilot2Log.txt", PILOT2_SAMPLE, 2), ("Pilot3Log.txt", PILOT3_SAMPLE, 0)):
            with self.subTest(filename=filename):
                parser, _ = self.parse_content(sample, filename)
                self.assertEqual(len(parser.missions), count)


if __name__ == "__main__":
    unittest.main()
