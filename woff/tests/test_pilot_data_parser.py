import unittest
from pathlib import Path
from unittest.mock import patch, mock_open


from ..parsers.pilot_data_parser import WoFFPilotDataParser

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

    def test_pilotlog_preserves_mission_text_with_embedded_short_aliases(self):
        mock_content = (
            "2\n"
            "6;4;1917;10;30;Arras;Filescamp;Troop Support;SE.5a;;45;100;"
            "SE.5a;No. 56 Sqn;troops;Target;N50;E2;;Mission completed.\n"
            "7;4;1917;11;30;Arras;Filescamp;Cooperation Flight;SE.5a;;45;100;"
            "SE.5a;No. 56 Sqn;troops;Target;N50;E2;;Mission completed.\n"
        )

        parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data=mock_content)):
            ok = parser.parse("Pilot1Log.txt")

        self.assertTrue(ok)
        self.assertEqual(
            [mission.missionType for mission in parser.missions],
            ["Troop Support", "Cooperation Flight"],
        )

    def test_pilotlog_preserves_raw_mission_type_for_legacy_replay(self):
        mock_content = (
            "1\n"
            "6;4;1917;10;30;Arras;Filescamp;Troop Support Escort;SE.5a;;"
            "45;100;SE.5a;No. 56 Sqn;troops;Target;N50;E2;;"
            "Mission completed.\n"
        )

        parser = WoFFPilotDataParser()
        self.assertTrue(parser.parse_bytes(mock_content, "Pilot1Log.txt"))

        self.assertEqual(parser.missions[0].missionType, "Escort Duty")
        self.assertEqual(
            parser.missions[0].rawMissionType,
            "Troop Support Escort",
        )
    

    def test_parse_log_extended_looking_fields_use_verified_layout(self):
        """Sem marcador externo, campos parecidos com flags continuam reservados/notas."""
        mock_content = "2\n"
        mock_content += "6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;SE.5a;No. 56 Sqn RFC;troops;Army Camp;N50*17;E2*42;Damaged;Wounded; Final Status: Crash landed wounded.;\n"
        mock_content += "7;4;1917;11;00;Arras;Filescamp;OP;SE.5a;;45;100;SE.5a;No. 56 Sqn RFC;troops;Army Camp;N50*17;E2*42;No;0; Final Status: Landed safely.;\n"

        parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data=mock_content)):
            ok = parser.parse("Pilot1Log.txt")

        self.assertTrue(ok)
        self.assertEqual(len(parser.missions), 2)
        self.assertFalse(parser.missions[0].damageReceived)
        self.assertFalse(parser.missions[0].woundsReceived)
        self.assertFalse(parser.missions[1].damageReceived)
        self.assertFalse(parser.missions[1].woundsReceived)

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

    def test_pilotclaims_preserves_unknown_victory_text(self):
        mock_content = (
            "1\n"
            "6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;1;"
            "Albatros D.III;Engine exploded;Albatros\n"
        )

        parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data=mock_content)):
            ok = parser.parse("Pilot1Claims.txt")

        self.assertTrue(ok)
        self.assertEqual(len(parser.victories), 1)
        self.assertEqual(parser.victories[0].victoryType, "Engine exploded")

    def test_full_width_claim_with_invalid_date_time_is_rejected(self):
        mock_content = (
            "1\n"
            "X;X;X;X;X;sector;a;b;plane;z;enemy;confirmed\n"
        )

        parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data=mock_content)):
            with self.assertLogs("WoFFWatch", level="WARNING"):
                ok = parser.parse("Pilot1Claims.txt")

        self.assertFalse(ok)
        self.assertEqual(parser.victories, [])
        self.assertEqual(parser.rejected_records, 1)
        self.assertFalse(parser.is_complete)

    def test_declared_count_mismatch_marks_log_and_claims_incomplete(self):
        sources = (
            (
                "Pilot1Log.txt",
                "2\n"
                "6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;"
                "SE.5a;No. 56 Sqn;troops;Target;N50;E2;;Mission completed.\n",
            ),
            (
                "Pilot1Claims.txt",
                "2\n"
                "6;4;1917;10;35;Arras;Filescamp;OP;SE.5a;1;"
                "Albatros D.III;Destroyed Confirmed;Albatros\n",
            ),
        )

        for filename, mock_content in sources:
            with self.subTest(filename=filename):
                parser = WoFFPilotDataParser()
                with patch("builtins.open", mock_open(read_data=mock_content)):
                    with self.assertLogs("WoFFWatch", level="WARNING"):
                        ok = parser.parse(filename)

                self.assertTrue(ok)
                self.assertEqual(parser.declared_records, 2)
                self.assertEqual(parser.observed_records, 1)
                self.assertFalse(parser.is_complete)
    
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

    def test_malformed_squads_record_is_rejected(self):
        parser = WoFFPilotDataParser()
        with patch("builtins.open", mock_open(read_data="malformed\n")):
            with self.assertLogs("WoFFWatch", level="WARNING"):
                ok = parser.parse("Pilot1Squads.txt")

        self.assertFalse(ok)
        self.assertIsNone(parser.pilot)
        self.assertEqual(parser.rejected_records, 1)
        self.assertFalse(parser.is_complete)
    
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

    def test_extended_looking_record_preserves_verified_interpretation(self):
        fields = VERIFIED_FIELDS[:18] + ["Damaged", "No", "one; two; three"]
        parser, ok = self.parse_content("1\n" + self.line(fields) + "\n")
        self.assertTrue(ok)
        self.assertEqual(parser.missions[0].notes, "No;one;two;three")
        self.assertFalse(parser.missions[0].damageReceived)
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

    def test_nonempty_reserved_values_are_independent_from_semicolon_notes(self):
        for reserved in ("reserved value", "Damaged", "Yes", "No", "Wounded"):
            with self.subTest(reserved=reserved):
                fields = VERIFIED_FIELDS.copy()
                fields[18] = reserved
                fields[19] = "Only; these;; are notes"
                parser, ok = self.parse_content("1\n" + self.line(fields, terminal=True) + "\n")
                self.assertTrue(ok)
                self.assertEqual(parser.missions[0].notes, "Only;these;;are notes")
                self.assertFalse(parser.missions[0].damageReceived)
                self.assertFalse(parser.missions[0].woundsReceived)

    def test_notes_are_limited_to_existing_maximum(self):
        fields = VERIFIED_FIELDS.copy()
        fields[19] = "n" * 501
        parser, _ = self.parse_content("1\n" + self.line(fields) + "\n")
        self.assertEqual(parser.missions[0].notes, "n" * 500)

    def test_extended_looking_record_is_preserved_and_later_record_recovers(self):
        ambiguous = VERIFIED_FIELDS[:18] + ["perhaps", "Wounded", "secret complete record text"]
        content = "2\n" + self.line(ambiguous) + "\n" + self.line() + "\n"
        parser, ok = self.parse_content(content)
        self.assertTrue(ok)
        self.assertEqual(len(parser.missions), 2)
        self.assertEqual(parser.missions[0].notes, "Wounded;secret complete record text")

    def test_malformed_record_log_is_safe_and_later_record_recovers(self):
        source_line = ";".join(["private complete source line"] + ["x"] * 21)
        with self.assertLogs("WoFFWatch", level="WARNING") as captured:
            parser, ok = self.parse_content("2\n" + source_line + "\n" + self.line() + "\n")
        self.assertTrue(ok)
        self.assertEqual(len(parser.missions), 1)
        logged = " ".join(captured.output)
        self.assertIn("source=Pilot1Log.txt", logged)
        self.assertIn("line=2", logged)
        self.assertIn("category=malformed", logged)
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

    def test_claim_confirmation_with_narrative_semicolons_is_ignored(self):
        claim = PILOT2_SAMPLE.splitlines()[3]
        for narrative in (
            "Sanitized claim;narrative.",
            "Sanitized;claim;narrative.",
        ):
            with self.subTest(narrative=narrative):
                claim_with_semicolons = claim.replace(
                    "Sanitized claim narrative.", narrative,
                )
                content = "2\n" + claim_with_semicolons + "\n" + self.line() + "\n"
                with self.assertNoLogs("WoFFWatch", level="WARNING"):
                    parser, ok = self.parse_content(content)
                self.assertTrue(ok)
                self.assertEqual(len(parser.missions), 1)
                self.assertEqual(parser.missions[0].notes, VERIFIED_FIELDS[19])

    def assert_truncated_claim_confirmation_is_rejected(self, field_count):
        claim_fields = PILOT2_SAMPLE.splitlines()[3].split(";")[:field_count]
        self.assertTrue(
            claim_fields[5].lower().startswith(
                "confirmation received of claim submitted on:"
            )
        )
        claim_fields[16] = "private claim text and narrative"
        if not claim_fields[-1]:
            claim_fields[-1] = "truncated field"
        content = "2\n" + self.line(claim_fields) + "\n" + self.line() + "\n"

        with self.assertLogs("WoFFWatch", level="WARNING") as captured:
            parser, ok = self.parse_content(content)

        self.assertTrue(ok)
        self.assertEqual(len(parser.missions), 1)
        self.assertEqual(parser.missions[0].notes, VERIFIED_FIELDS[19])
        logged = " ".join(captured.output)
        self.assertIn("source=Pilot1Log.txt", logged)
        self.assertIn("line=2", logged)
        self.assertIn("category=truncated-claim-confirmation", logged)
        self.assertIn(f"fields={field_count}", logged)
        self.assertIn("reason=claim confirmation has fewer than 26 fields", logged)
        self.assertNotIn("private claim text", logged)
        self.assertNotIn("narrative", logged)

    def test_truncated_claim_confirmation_with_21_fields_is_rejected(self):
        self.assert_truncated_claim_confirmation_is_rejected(21)

    def test_truncated_claim_confirmation_with_23_fields_is_rejected(self):
        self.assert_truncated_claim_confirmation_is_rejected(23)

    def test_truncated_claim_confirmation_with_25_fields_is_rejected(self):
        self.assert_truncated_claim_confirmation_is_rejected(25)

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

    def test_calendar_validation_covers_1915_and_1918_campaigns(self):
        campaign_1915 = VERIFIED_FIELDS.copy()
        campaign_1915[0:5] = ["20", "9", "1915", "9", "30"]
        campaign_1918 = VERIFIED_FIELDS.copy()
        campaign_1918[0:5] = ["11", "11", "1918", "10", "30"]
        impossible = VERIFIED_FIELDS.copy()
        impossible[0:5] = ["30", "2", "1917", "10", "30"]
        content = (
            "3\n" + self.line(campaign_1915) + "\n"
            + self.line(impossible) + "\n"
            + self.line(campaign_1918) + "\n"
        )

        with self.assertLogs("WoFFWatch", level="WARNING"):
            parser, ok = self.parse_content(content)

        self.assertTrue(ok)
        self.assertEqual(
            [(mission.date, mission.time) for mission in parser.missions],
            [("1915-09-20", "09:30"), ("1918-11-11", "10:30")],
        )

    def test_signed_date_and_time_components_remain_invalid(self):
        for index, field in enumerate(("day", "month", "year", "hour", "minute")):
            for sign in ("+", "-"):
                with self.subTest(field=field, sign=sign):
                    fields = VERIFIED_FIELDS.copy()
                    fields[index] = sign + fields[index]

                    with self.assertLogs("WoFFWatch", level="WARNING"):
                        parser, ok = self.parse_content(
                            "1\n" + self.line(fields) + "\n"
                        )

                    self.assertFalse(ok)
                    self.assertEqual(parser.missions, [])
                    self.assertEqual(parser.rejected_records, 1)

    def test_non_ascii_date_and_time_components_remain_invalid(self):
        ascii_to_full_width = str.maketrans("0123456789", "０１２３４５６７８９")

        for index, field in enumerate(("day", "month", "year", "hour", "minute")):
            with self.subTest(field=field):
                fields = VERIFIED_FIELDS.copy()
                fields[index] = fields[index].translate(ascii_to_full_width)

                with self.assertLogs("WoFFWatch", level="WARNING"):
                    parser, ok = self.parse_content("1\n" + self.line(fields) + "\n")

                self.assertFalse(ok)
                self.assertEqual(parser.missions, [])
                self.assertEqual(parser.rejected_records, 1)

    def test_inline_sanitized_samples_end_to_end(self):
        for filename, sample, count, physical_count in (
            ("Pilot1Log.txt", PILOT1_SAMPLE, 2, 2),
            ("Pilot2Log.txt", PILOT2_SAMPLE, 2, 3),
            ("Pilot3Log.txt", PILOT3_SAMPLE, 0, 0),
        ):
            with self.subTest(filename=filename):
                parser, _ = self.parse_content(sample, filename)
                self.assertEqual(len(parser.missions), count)
                self.assertEqual(parser.declared_records, physical_count)
                self.assertEqual(parser.observed_records, physical_count)
                self.assertTrue(parser.is_complete)


if __name__ == "__main__":
    unittest.main()
