import unittest
import os
from unittest.mock import patch, mock_open


from ..parsers.dossier_parser import WoFFDossierParser

def _encode_dossier(plaintext_lines: list, filename: str) -> bytes:
    """
    Helper de Teste: Aplica a camada de ofuscação (XOR + Hex + Contador)
    para simular um ficheiro Pilot{N}Dossier.txt real.
    """
    pName = filename.replace(".txt", "")
    
    # Replicar a geração de chave do WoFFDossierParser
    plainkey = "78CrztPRVzYQpYu90MnyW"
    soucet = sum(ord(c) for c in pName)
    sum_val = soucet % 128
    
    pos = sum_val % 10
    if pos == 0: pos = 9
    length = sum_val % 12
    if length == 0: length = 4
    
    prekey = "".join(plainkey[ind - 1] for ind in range(pos, pos + length))
    postkey = "".join(plainkey[lengt - 1] for lengt in range(length, length + pos))
    sp = chr(sum_val)
    key = prekey + sp + plainkey + postkey

    raw_data = bytearray()
    current_key = key
    
    for line in plaintext_lines:
        key_index = 0
        counter = 0x80  # Contador começa em 128 (0x80)
        
        for char in line:
            val = ord(char)
            k_char = ord(current_key[key_index])
            xor_val = val ^ k_char
            
            # Converter para Hex (maiúsculas, 2 dígitos)
            hex_str = f"{xor_val:02X}"
            raw_data.extend(hex_str.encode('ascii'))
            
            # Inserir byte contador
            raw_data.append(counter)
            
            # Manter contador entre 128 e 255 para o parser reconhecer como separador
            counter = 0x80 + ((counter - 0x80 + 1) % 128)
            
            key_index = (key_index + 1) % len(current_key)
            
        raw_data.extend(b"\r\n")
        current_key = current_key[::-1] # Inverter chave a cada linha
        
    return bytes(raw_data)


class TestWoFFDossierParser(unittest.TestCase):
    
    def setUp(self):
        self.parser = WoFFDossierParser()
        self.filename = "Pilot1Dossier.txt"
        
        # FIX: Usar "Null" em vez de "." para não confundir o parser de medalhas
        self.mock_lines = ["Null"] * 105 
        
        # Preencher os índices que o parser procura
        self.mock_lines[1] = "France"
        self.mock_lines[3] = "Capitaine"
        self.mock_lines[4] = "James"
        self.mock_lines[5] = "Hartley"
        self.mock_lines[6] = "20"
        self.mock_lines[7] = "9"
        self.mock_lines[8] = "1915"
        self.mock_lines[11] = "1520"  # flminutes
        self.mock_lines[12] = "11"
        self.mock_lines[13] = "11"
        self.mock_lines[14] = "1918"
        self.mock_lines[16] = "5"     # claims
        self.mock_lines[17] = "3"     # kills
        self.mock_lines[19] = "Medaille Militaire;1915-05-10"
        self.mock_lines[41] = "75"    # skill
        self.mock_lines[46] = "10"    # missions
        self.mock_lines[52] = "800"   # reputation
        self.mock_lines[83] = "Escadrille N 15"
        self.mock_lines[84] = "Nieuport_10C1"
        self.mock_lines[88] = "Savy"
        self.mock_lines[89] = "Flanders"
        self.mock_lines[92] = "Lyon"
        self.mock_lines[100] = "1"    # photo_id
        
        # Wingman na linha 104
        self.mock_lines[104] = "Lieutenant;John;Smith;3;5;In Service;0;0;0;0;0;6;1550;1500;9;2;8;8;1896;Reliable pilot.;75;21;651;1;19/7/1913;Chambery, Savoie, France;2;0;Medaille Militaire;Null;Null;Null;Null;Null;Null"

        self.encoded_data = _encode_dossier(self.mock_lines, self.filename)

    def test_parse_valid_dossier(self):
        """Testa decodificação de dossier com dados conhecidos."""
        with patch("builtins.open", mock_open(read_data=self.encoded_data)):
            ok = self.parser.parse(self.filename)
            
        self.assertTrue(ok)
        self.assertIsNotNone(self.parser.pilot)
        
        # Type narrowing para o Pyright compreender que não é None
        assert self.parser.pilot is not None
        
        self.assertEqual(self.parser.pilot.name, "James Hartley")
        self.assertEqual(self.parser.pilot.nation, "French")
        self.assertEqual(self.parser.pilot.photo, "1")
        self.assertEqual(self.parser.pilot.missions, 10)
        self.assertEqual(self.parser.pilot.claimsCount, 5)
        self.assertEqual(self.parser.pilot.killsCount, 3)
        self.assertEqual(self.parser.pilot.flminutes, 1520)
        self.assertEqual(self.parser.pilot.skill, 75)
        self.assertEqual(self.parser.pilot.reputation, 800)
        self.assertEqual(self.parser.pilot.startDate, "1915-09-20")
        self.assertEqual(self.parser.pilot.enlisted, "1918-11-11")

    def test_signed_reputation_is_not_silently_rewritten_to_zero(self):
        for raw, expected in ((" -1 ", -1), (" +5 ", 5)):
            with self.subTest(raw=raw):
                lines = self.mock_lines.copy()
                lines[52] = raw
                parser = WoFFDossierParser()

                self.assertTrue(
                    parser.parse_bytes(
                        _encode_dossier(lines, self.filename),
                        self.filename,
                    )
                )
                self.assertIsNotNone(parser.pilot)
                assert parser.pilot is not None
                self.assertEqual(parser.pilot.reputation, expected)

    def test_invalid_reputation_remains_missing_with_privacy_safe_diagnostic(self):
        lines = self.mock_lines.copy()
        lines[52] = "not-a-number"
        parser = WoFFDossierParser()

        with self.assertLogs("WoFFWatch", level="WARNING") as captured:
            self.assertTrue(
                parser.parse_bytes(
                    _encode_dossier(lines, self.filename),
                    self.filename,
                )
            )

        self.assertIsNotNone(parser.pilot)
        assert parser.pilot is not None
        self.assertIsNone(parser.pilot.reputation)
        logged = " ".join(captured.output)
        self.assertIn("source=Pilot1Dossier.txt", logged)
        self.assertIn("field=reputation", logged)
        self.assertIn("reason=invalid integer syntax", logged)
        self.assertNotIn(parser.pilot.name, logged)

    def test_unsigned_pilot_fields_reject_invalid_values_without_zero(self):
        fields = (
            (46, "missions"),
            (16, "claimsCount"),
            (17, "killsCount"),
            (11, "flminutes"),
            (41, "skill"),
        )

        invalid_values = (
            ("-1", "invalid integer syntax"),
            ("not-a-number", "invalid integer syntax"),
            ("9" * 5_000, "integer outside permitted range"),
        )

        for index, field in fields:
            for raw, reason in invalid_values:
                with self.subTest(field=field, raw=raw):
                    lines = self.mock_lines.copy()
                    lines[index] = raw
                    parser = WoFFDossierParser()

                    with self.assertLogs("WoFFWatch", level="WARNING") as captured:
                        self.assertTrue(
                            parser.parse_bytes(
                                _encode_dossier(lines, self.filename),
                                self.filename,
                            )
                        )

                    self.assertIsNotNone(parser.pilot)
                    assert parser.pilot is not None
                    self.assertIsNone(getattr(parser.pilot, field))
                    logged = " ".join(captured.output)
                    self.assertIn(f"field={field}", logged)
                    self.assertIn(f"reason={reason}", logged)

    def test_null_numeric_sentinel_remains_missing_without_warning(self):
        fields = (
            (46, "missions"),
            (16, "claimsCount"),
            (17, "killsCount"),
            (11, "flminutes"),
            (41, "skill"),
            (52, "reputation"),
        )

        for index, field in fields:
            with self.subTest(field=field):
                lines = self.mock_lines.copy()
                lines[index] = "Null"
                parser = WoFFDossierParser()

                with self.assertNoLogs("WoFFWatch", level="WARNING"):
                    self.assertTrue(
                        parser.parse_bytes(
                            _encode_dossier(lines, self.filename),
                            self.filename,
                        )
                    )

                self.assertIsNotNone(parser.pilot)
                assert parser.pilot is not None
                self.assertIsNone(getattr(parser.pilot, field))

    def test_explicit_zero_remains_authoritative_for_pilot_numeric_fields(self):
        lines = self.mock_lines.copy()
        for index in (46, 16, 17, 11, 41, 52):
            lines[index] = "0"
        parser = WoFFDossierParser()

        self.assertTrue(
            parser.parse_bytes(
                _encode_dossier(lines, self.filename),
                self.filename,
            )
        )

        self.assertIsNotNone(parser.pilot)
        assert parser.pilot is not None
        self.assertEqual(
            (
                parser.pilot.missions,
                parser.pilot.claimsCount,
                parser.pilot.killsCount,
                parser.pilot.flminutes,
                parser.pilot.skill,
                parser.pilot.reputation,
            ),
            (0, 0, 0, 0, 0, 0),
        )

    def test_dossier_integer_values_outside_sqlite_range_remain_missing(self):
        cases = (
            (46, "missions", str(1 << 63)),
            (52, "reputation", str(-(1 << 63) - 1)),
        )

        for index, field, raw in cases:
            with self.subTest(field=field):
                lines = self.mock_lines.copy()
                lines[index] = raw
                parser = WoFFDossierParser()

                with self.assertLogs("WoFFWatch", level="WARNING") as captured:
                    self.assertTrue(
                        parser.parse_bytes(
                            _encode_dossier(lines, self.filename),
                            self.filename,
                        )
                    )

                self.assertIsNotNone(parser.pilot)
                assert parser.pilot is not None
                self.assertIsNone(getattr(parser.pilot, field))
                self.assertIn(
                    "reason=integer outside permitted range",
                    " ".join(captured.output),
                )

    def test_parse_dossier_wrong_filename(self):
        """Testa que chave XOR errada não produz o piloto correto."""
        # Tentar ler com um nome de ficheiro diferente gera uma chave XOR diferente
        with patch("builtins.open", mock_open(read_data=self.encoded_data)):
            ok = self.parser.parse("WrongName.txt")
            
        # FIX: Com chave errada, ou falha completamente ou devolve dados corrompidos
        if ok and self.parser.pilot:
            # Type narrowing
            assert self.parser.pilot is not None
            self.assertNotEqual(self.parser.pilot.name, "James Hartley")
        else:
            self.assertFalse(ok) 

    def test_wingmen_extraction(self):
        """Testa extração de wingmen com patentes conhecidas."""
        with patch("builtins.open", mock_open(read_data=self.encoded_data)):
            self.parser.parse(self.filename)
            
        self.assertEqual(len(self.parser.wingmen), 1)
        w = self.parser.wingmen[0]
        self.assertEqual(w.rank, "Lieutenant")
        self.assertEqual(w.fName, "John")
        self.assertEqual(w.sName, "Smith")
        self.assertEqual(w.skill, 3)
        self.assertEqual(w.morale, 5)
        self.assertEqual(w.flminutes, 1550)
        self.assertEqual(w.status, "In Service")
        self.assertIn("Reliable pilot", w.bio)

    def test_wingman_invalid_numeric_fields_reject_the_record_without_zero(self):
        fields = (
            (3, "wingman.skill"),
            (4, "wingman.morale"),
            (12, "wingman.flminutes"),
        )

        for index, field in fields:
            for raw in ("-1", "not-a-number"):
                with self.subTest(field=field, raw=raw):
                    lines = self.mock_lines.copy()
                    wingman_parts = lines[104].split(";")
                    wingman_parts[index] = raw
                    lines[104] = ";".join(wingman_parts)
                    parser = WoFFDossierParser()

                    with self.assertLogs("WoFFWatch", level="WARNING") as captured:
                        self.assertTrue(
                            parser.parse_bytes(
                                _encode_dossier(lines, self.filename),
                                self.filename,
                            )
                        )

                    self.assertEqual(parser.wingmen, [])
                    logged = " ".join(captured.output)
                    self.assertIn(f"field={field}", logged)
                    self.assertIn("reason=invalid integer syntax", logged)
                    self.assertNotIn("John Smith", logged)

    def test_wingman_missing_optional_flight_minutes_preserve_the_record(self):
        for missing in ("absent", "empty", "Null"):
            with self.subTest(missing=missing):
                lines = self.mock_lines.copy()
                wingman_parts = lines[104].split(";")
                if missing == "absent":
                    wingman_parts = wingman_parts[:12]
                else:
                    wingman_parts[12] = missing if missing == "Null" else ""
                lines[104] = ";".join(wingman_parts)
                parser = WoFFDossierParser()

                with self.assertNoLogs("WoFFWatch", level="WARNING"):
                    self.assertTrue(
                        parser.parse_bytes(
                            _encode_dossier(lines, self.filename),
                            self.filename,
                        )
                    )

                self.assertEqual(len(parser.wingmen), 1)
                self.assertEqual(parser.wingmen[0].flminutes, 0)

    def test_non_ascii_photo_id_is_not_accepted_as_unsigned_input(self):
        lines = self.mock_lines.copy()
        lines[100] = "１２"
        parser = WoFFDossierParser()

        self.assertTrue(
            parser.parse_bytes(
                _encode_dossier(lines, self.filename),
                self.filename,
            )
        )

        self.assertIsNotNone(parser.pilot)
        assert parser.pilot is not None
        self.assertEqual(parser.pilot.photo, "")

    def test_decorations_extraction(self):
        """Testa extração de medalhas nos índices 19-26."""
        with patch("builtins.open", mock_open(read_data=self.encoded_data)):
            self.parser.parse(self.filename)
            
        self.assertEqual(len(self.parser.decorations), 1)
        d = self.parser.decorations[0]
        self.assertEqual(d.name, "Medaille Militaire")
        self.assertEqual(d.date, "1915-05-10")

    def test_impossible_dossier_dates_are_not_exposed_as_canonical_values(self):
        self.mock_lines[6] = "30"
        self.mock_lines[7] = "2"
        self.mock_lines[8] = "1917"
        self.mock_lines[19] = "Medaille Militaire;1917-02-30"
        encoded = _encode_dossier(self.mock_lines, self.filename)

        with patch("builtins.open", mock_open(read_data=encoded)):
            self.assertTrue(self.parser.parse(self.filename))

        self.assertIsNotNone(self.parser.pilot)
        assert self.parser.pilot is not None
        self.assertEqual(self.parser.pilot.startDate, "")
        self.assertEqual(self.parser.decorations[0].date, "")

if __name__ == "__main__":
    unittest.main()
