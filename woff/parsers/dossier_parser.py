#!/usr/bin/env python3
r"""
Parser de Dossier Binário (parsers/dossier_parser.py)
══════════════════════════════════════════════════════════════════
Faz a leitura e desencriptação do ficheiro Pilot{N}Dossier.txt.
Implementação baseada na engenharia reversa do código Java do 
Pilot Log Editor (JJJ65).

O WoFF ofusca este ficheiro com:
1. Pares hexadecimais intercalados com bytes de contador.
2. Cifra XOR usando uma chave gerada pelo nome do ficheiro.
3. Chave invertida a cada linha.
══════════════════════════════════════════════════════════════════
"""

import ntpath
import logging
from dataclasses import replace
from datetime import datetime
from enum import Enum
from typing import Optional, List
from ..models import WoFFPilot, WoFFWingman, WoFFDecoration
# FIX: Importa as funções de normalização para aplicar aos dados do Dossier.
from ..normalization import normalize_date, resolve_nation_alias
from .numeric import (
    SIGNED_SQLITE_INTEGER,
    UNSIGNED_SQLITE_INTEGER,
    IntegerPolicy,
    InvalidIntegerError,
    parse_integer,
)

log = logging.getLogger("WoFFWatch")

_DOSSIER_MISSING_TOKENS = frozenset({"null"})
_DOSSIER_LAYOUT = "fixed-index-v1"
_DOSSIER_REQUIRED_LAST_INDEX = 5
_DOSSIER_CURRENT_FIXED_LAST_INDEX = 100
_DOSSIER_NAME_SEPARATORS = frozenset({" ", "-", "'", "’", "."})
# Sanitized evidence confirms only reputation as signed-capable. Counts,
# flight minutes, skill, and morale remain nonnegative until new samples prove
# a broader domain.
_DOSSIER_SIGNED_INTEGER = replace(
    SIGNED_SQLITE_INTEGER,
    missing_tokens=_DOSSIER_MISSING_TOKENS,
)
_DOSSIER_UNSIGNED_INTEGER = replace(
    UNSIGNED_SQLITE_INTEGER,
    missing_tokens=_DOSSIER_MISSING_TOKENS,
)


class DossierValidationStatus(str, Enum):
    UNPARSED = "unparsed"
    SUPPORTED_FULL = "supported-full"
    SUPPORTED_PARTIAL = "supported-partial"
    TRUNCATED = "truncated"
    UNSUPPORTED_LAYOUT = "unsupported-layout"
    DECRYPTION_FAILED = "decryption-failed"


class WoFFDossierParser:
    def __init__(self):
        self.pilot: Optional[WoFFPilot] = None
        self.raw_strings: List[str] = []
        self.wingmen: List[WoFFWingman] = []
        self.decorations: List[WoFFDecoration] = []
        self.validation_status = DossierValidationStatus.UNPARSED

    def _reset_parse_state(self) -> None:
        self.pilot = None
        self.raw_strings = []
        self.wingmen = []
        self.decorations = []
        self.validation_status = DossierValidationStatus.UNPARSED

    def _reject(
        self,
        status: DossierValidationStatus,
        source_name: str,
        record_count: int,
    ) -> bool:
        self.validation_status = status
        log.warning(
            "[BIN] Dossier rejected: source=%s category=%s "
            "layout=%s records=%d",
            source_name,
            status.value,
            _DOSSIER_LAYOUT,
            record_count,
        )
        return False

    def _create_key(self, pName: str) -> str:
        """Gera a chave de cifra exatamente como o jogo faz (createkey)."""
        plainkey = "78CrztPRVzYQpYu90MnyW"
        
        soucet = sum(ord(c) for c in pName)
        sum_val = soucet % 128
        
        pos = sum_val % 10
        if pos == 0: pos = 9
        
        length = sum_val % 12
        if length == 0: length = 4
        
        prekey = ""
        ind = pos
        for _ in range(length):
            prekey += plainkey[ind - 1]
            ind += 1
            
        postkey = ""
        in_val = pos
        lengt = length
        for _ in range(in_val):
            postkey += plainkey[lengt - 1]
            lengt += 1
            
        sp = chr(sum_val)
        return prekey + sp + plainkey + postkey

    def parse(self, path: str) -> bool:
        self._reset_parse_state()
        source_name = ntpath.basename(path)
        log.info(f"[BIN] Analisando Dossier: {source_name}")
        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception as e:
            log.error(f"  Falha ao ler {path}: {e}")
            return False
        return self.parse_bytes(data, source_name)

    def parse_bytes(self, data: bytes, source_name: str) -> bool:
        """Decode verified bytes, retaining the filename-derived cipher key."""
        self._reset_parse_state()
        raw_lines = data.splitlines(keepends=True)
        fname = ntpath.basename(source_name)
        pName = fname.replace(".txt", "")
        current_key = self._create_key(pName)
        
        player_data = []

        for raw_line in raw_lines:
            line = raw_line.decode("cp1252", errors="replace").strip()
            if not line:
                continue
                
            decoded_line = ""
            hex_buffer = ""
            key_index = 0
            
            for char in line:
                code = ord(char)
                if code > 71:  # Byte de contador/separador
                    if hex_buffer:
                        if len(hex_buffer) < 2:
                            hex_buffer = "0" + hex_buffer
                        try:
                            val = int(hex_buffer, 16)
                            key_char = ord(current_key[key_index])
                            fin_val = val ^ key_char  # Cifra XOR
                            decoded_line += chr(fin_val)
                        except ValueError:
                            pass
                        
                        key_index += 1
                        if key_index == len(current_key):
                            key_index = 0
                        hex_buffer = ""
                elif code != 32:
                    hex_buffer += char
                    
            current_key = current_key[::-1]
            player_data.append(decoded_line.strip())

        if not any(player_data):
            return self._reject(
                DossierValidationStatus.DECRYPTION_FAILED,
                fname,
                len(player_data),
            )

        if any(
            "\ufffd" in value
            or not all(character.isprintable() for character in value)
            for value in player_data
        ):
            return self._reject(
                DossierValidationStatus.DECRYPTION_FAILED,
                fname,
                len(player_data),
            )

        if len(player_data) > _DOSSIER_REQUIRED_LAST_INDEX:
            first_name = player_data[4].strip()
            last_name = player_data[5].strip()
            if any(
                not all(
                    character.isalpha()
                    or character.isdigit()
                    or character in _DOSSIER_NAME_SEPARATORS
                    for character in value
                )
                for value in (first_name, last_name)
            ):
                return self._reject(
                    DossierValidationStatus.DECRYPTION_FAILED,
                    fname,
                    len(player_data),
                )
            if any(
                not value
                or value.casefold() in _DOSSIER_MISSING_TOKENS
                or not any(character.isalpha() for character in value)
                or not all(
                    character.isalpha()
                    or character in _DOSSIER_NAME_SEPARATORS
                    for character in value
                )
                for value in (first_name, last_name)
            ):
                return self._reject(
                    DossierValidationStatus.UNSUPPORTED_LAYOUT,
                    fname,
                    len(player_data),
                )

            self.pilot = WoFFPilot()
            self.pilot.source_file = fname
            self.pilot.last_updated = datetime.now().isoformat()
            
            def safe_get(idx):
                value = (
                    player_data[idx]
                    if len(player_data) > idx and player_data[idx]
                    else ""
                )
                if value.casefold() in _DOSSIER_MISSING_TOKENS:
                    return ""
                return value

            def parse_pilot_integer(
                idx: int, field: str, policy: IntegerPolicy
            ) -> Optional[int]:
                try:
                    return parse_integer(safe_get(idx), policy=policy)
                except InvalidIntegerError as exc:
                    log.warning(
                        "[BIN] Numeric field rejected: source=%s field=%s reason=%s",
                        fname,
                        field,
                        exc,
                    )
                    return None
            
            # 1. Índices fixos para estatísticas (confirmados no Java)
            self.pilot.fName = first_name
            self.pilot.sName = last_name
            self.pilot.name = f"{self.pilot.fName} {self.pilot.sName}".strip()
            self.pilot.rank = safe_get(3)
            self.pilot.squadron = safe_get(83)
            self.pilot.aircraft = safe_get(84)
            self.pilot.aerodrome = safe_get(88)
            self.pilot.sector = safe_get(89)
            self.pilot.missions = parse_pilot_integer(
                46, "missions", _DOSSIER_UNSIGNED_INTEGER
            )
            self.pilot.claimsCount = parse_pilot_integer(
                16, "claimsCount", _DOSSIER_UNSIGNED_INTEGER
            )
            self.pilot.killsCount = parse_pilot_integer(
                17, "killsCount", _DOSSIER_UNSIGNED_INTEGER
            )
            self.pilot.flminutes = parse_pilot_integer(
                11, "flminutes", _DOSSIER_UNSIGNED_INTEGER
            )
            self.pilot.skill = parse_pilot_integer(
                41, "skill", _DOSSIER_UNSIGNED_INTEGER
            )
            self.pilot.reputation = parse_pilot_integer(
                52, "reputation", _DOSSIER_SIGNED_INTEGER
            )
            self.pilot.birthPlace = safe_get(92)
            
            # Extração do ID da Foto centralizada (Índice 100)
            photo_id = safe_get(100)
            if photo_id and photo_id.isascii() and photo_id.isdigit():
                self.pilot.photo = photo_id
            
            # Datas (Campanha e Alistamento)
            d, m, y = safe_get(6), safe_get(7), safe_get(8)
            if d and m and y:
                self.pilot.startDate = normalize_date(f"{d}/{m}/{y}")
            
            d, m, y = safe_get(12), safe_get(13), safe_get(14)
            if d and m and y:
                self.pilot.enlisted = normalize_date(f"{d}/{m}/{y}")
            
            # 2. Heurísticas Dinâmicas com 'break' (para não capturar valores errados)
            for s in player_data:
                s_clean = s.strip()
                if not s_clean:
                    continue
                
                canonical_nation = resolve_nation_alias(s_clean)
                if not self.pilot.nation and canonical_nation is not None:
                    self.pilot.nation = canonical_nation
                    continue
                if self.pilot.status is None and s_clean in (
                    "Active", "In Service", "Wounded", "KIA", "Leave",
                    "Prisoner", "Dead", "Retired",
                ):
                    self.pilot.status = s_clean
                    continue
                # FIX: Aplica normalize_date() para converter "11/09/1896" -> "1896-09-11".
                if not self.pilot.birthDate and "/" in s_clean and len(s_clean) == 10 and s_clean[2] == "/" and s_clean[5] == "/":
                    self.pilot.birthDate = normalize_date(s_clean)
                    continue
                if not self.pilot.notes and ("joined" in s_clean.lower() or "enlisted" in s_clean.lower()):
                    self.pilot.notes = s_clean
                    continue
            
            self.raw_strings = player_data
            
            # 3. Extrair Membros do Esquadrão (AI Wingmen)
            self.wingmen = []
            
            # FIX: Lista de patentes expandida para cobrir Britânicos, Franceses e Alemães
            wingmen_ranks = [
                # British (RFC/RNAS/RAF)
                "Lieutenant", "2nd Lieutenant", "Captain", "Major", "Colonel", 
                "Flight Lieutenant", "Flight Sergeant", "Sergeant", "Corporal", 
                "Private", "Air Mechanic",
                # French
                "Capitaine", "Sous-Lieutenant", "Adjudant", "Sergent", "Caporal", 
                "Maréchal-des-logis", "Brigadier",
                # German
                "Hauptmann", "Oberleutnant", "Leutnant", "Rittmeister", 
                "Vizefeldwebel", "Feldwebel", "Unteroffizier", "Gefreiter"
            ]
            
            for s in player_data:
                s_clean = s.strip()
                if ";" in s_clean and len(s_clean) > 20 and any(s_clean.startswith(rank) for rank in wingmen_ranks):
                    parts = [p.strip() for p in s_clean.split(";")]
                    if len(parts) >= 6:
                        wingman_numeric: dict[str, int] = {}
                        numeric_field = "unknown"
                        try:
                            for index, numeric_field in (
                                (3, "skill"),
                                (4, "morale"),
                            ):
                                raw_value = parts[index] if len(parts) > index else None
                                parsed_value = parse_integer(
                                    raw_value, policy=_DOSSIER_UNSIGNED_INTEGER
                                )
                                if parsed_value is None:
                                    raise InvalidIntegerError("missing integer value")
                                wingman_numeric[numeric_field] = parsed_value

                            numeric_field = "flminutes"
                            parsed_flight_minutes = parse_integer(
                                parts[12] if len(parts) > 12 else None,
                                policy=_DOSSIER_UNSIGNED_INTEGER,
                            )
                            if parsed_flight_minutes is not None:
                                wingman_numeric[numeric_field] = parsed_flight_minutes
                        except InvalidIntegerError as exc:
                            log.warning(
                                "[BIN] Numeric field rejected: source=%s "
                                "field=wingman.%s reason=%s",
                                fname,
                                numeric_field,
                                exc,
                            )
                            continue

                        w = WoFFWingman()
                        w.rank = parts[0]
                        w.fName = parts[1]
                        w.sName = parts[2]
                        w.skill = wingman_numeric["skill"]
                        w.morale = wingman_numeric["morale"]
                        w.status = parts[5] if len(parts) > 5 else "Active"
                        
                        for part in parts:
                            if "pilot" in part.lower() or "observer" in part.lower() or "outlook" in part.lower():
                                w.bio = part
                                break
                        
                        if "flminutes" in wingman_numeric:
                            w.flminutes = wingman_numeric["flminutes"]
                            
                        self.wingmen.append(w)

            # 4. Extrair Medalhas Recebidas (Índices 19 a 26)
            self.decorations = []
            for i in range(19, 27):
                medal_str = safe_get(i)
                if medal_str and medal_str.lower() != "null":
                    parts = medal_str.split(";")
                    medal_name = parts[0].strip()
                    if medal_name:
                        d = WoFFDecoration()
                        d.name = medal_name
                        d.date = normalize_date(parts[1]) if len(parts) > 1 else ""
                        d.source_file = fname
                        self.decorations.append(d)
            
            self.validation_status = (
                DossierValidationStatus.SUPPORTED_FULL
                if len(player_data) > _DOSSIER_CURRENT_FIXED_LAST_INDEX
                else DossierValidationStatus.SUPPORTED_PARTIAL
            )
            log.info(
                "[BIN] Dossier accepted: source=%s category=%s "
                "layout=%s records=%d",
                fname,
                self.validation_status.value,
                _DOSSIER_LAYOUT,
                len(player_data),
            )
            return True
            
        return self._reject(
            DossierValidationStatus.TRUNCATED,
            fname,
            len(player_data),
        )
