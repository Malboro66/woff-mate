#!/usr/bin/env python3
"""
Parser de Dados do Piloto (parsers/pilot_data_parser.py)
══════════════════════════════════════════════════════════════════
"""
import os, re, logging
from datetime import datetime
from typing import List, Optional
from ..models import WoFFPilot, WoFFMission, WoFFVictory
from ..normalization import normalize_mission_type, normalize_victory_type, normalize_date

log = logging.getLogger("WoFFWatch")

class WoFFPilotDataParser:
    def __init__(self):
        self.pilot: Optional[WoFFPilot] = None
        self.missions: List[WoFFMission] = []
        self.victories: List[WoFFVictory] = []

    @staticmethod
    def _bool_field(raw: str) -> Optional[bool]:
        """Convert only the explicitly supported PilotLog flag tokens."""
        value = str(raw or "").strip().lower()
        false_values = ("", "0", "false", "no", "none", "undamaged")
        true_values = (
            "1", "true", "yes", "damaged", "damage",
            "wounded", "wound", "injured",
        )
        if value in false_values:
            return False
        if value in true_values:
            return True
        return None

    @staticmethod
    def _normalized_fields(line: str) -> List[str]:
        """Split a record while preserving internal empty fields.

        A terminal semicolon creates exactly one synthetic empty field.  Remove
        that field only; an empty field immediately before it remains intact.
        """
        parts = [part.strip() for part in line.split(";")]
        if parts and parts[-1] == "":
            parts.pop()
        return parts

    @staticmethod
    def _is_zero_mission_header(parts: List[str]) -> bool:
        expected = ("day", "month", "year", "hour", "minute")
        return len(parts) == 10 and tuple(value.lower() for value in parts[:5]) == expected

    @staticmethod
    def _is_claim_confirmation(parts: List[str]) -> bool:
        return (
            len(parts) == 26
            and len(parts) > 5
            and parts[5].lower().startswith("confirmation received of claim submitted on:")
        )

    @staticmethod
    def _validated_date_time(parts: List[str]) -> tuple[str, str]:
        day = parts[0].replace("/", "").strip()
        month = parts[1].replace("/", "").strip()
        year = parts[2].strip()
        hour = parts[3].lower().removesuffix("h").strip()
        minute = parts[4].strip()
        if not all(value.isdigit() for value in (day, month, year, hour, minute)):
            raise ValueError("date or time contains a non-numeric component")
        parsed = datetime(int(year), int(month), int(day), int(hour), int(minute))
        return parsed.strftime("%Y-%m-%d"), parsed.strftime("%H:%M")

    @staticmethod
    def _log_rejected(path: str, line_number: int, category: str,
                      field_count: int, reason: str) -> None:
        log.warning(
            "[TXT] PilotLog record rejected: source=%s line=%d "
            "category=%s fields=%d reason=%s",
            os.path.basename(path), line_number, category, field_count, reason,
        )

    def parse(self, path: str) -> bool:
        fname = os.path.basename(path).lower()
        if "dossier" in fname: return False

        pilot_match = re.match(r"(pilot\d+)", fname, re.I)
        if not pilot_match: return False
        
        pilot_name = pilot_match.group(1).replace("pilot", "Pilot ")
        
        if "squads" in fname: return self._parse_squads(path, pilot_name)
        elif "log" in fname: return self._parse_log(path, pilot_name)
        elif "claims" in fname: return self._parse_claims(path, pilot_name)
        return False

    def _parse_squads(self, path: str, pilot_name: str) -> bool:
        log.info(f"[TXT] Analisando Esquadrões: {os.path.basename(path)}")
        try:
            with open(path, "r", encoding="cp1252", errors="replace") as f: lines = f.readlines()
            if not lines: return False
            p = WoFFPilot()
            p.name = pilot_name
            p.source_file = os.path.basename(path)
            parts = [part.strip() for part in lines[-1].strip().split(";")]
            if len(parts) >= 12:
                p.squadron = parts[7]; p.aircraft = parts[8]; p.aerodrome = parts[6]; p.sector = parts[5]
                rank_match = re.search(r"rank:\s*([^\.]+)", parts[10], re.I)
                if rank_match: p.rank = rank_match.group(1).strip()
                p.startDate = normalize_date(f"{parts[0].replace('/','')}/{parts[1].replace('/','')}/{parts[2]}")
            self.pilot = p
            return True
        except Exception as e:
            log.error(f"  Falha ao ler {path}: {e}"); return False

    def _parse_log(self, path: str, pilot_name: str) -> bool:
        log.info(f"[TXT] Analisando Log de Missões: {os.path.basename(path)}")
        try:
            with open(path, "r", encoding="cp1252", errors="replace") as f: lines = f.readlines()
            for line_number, raw_line in enumerate(lines, start=1):
                line = raw_line.rstrip("\r\n")
                if not line.strip() or line.strip().isdigit():
                    continue
                parts = self._normalized_fields(line)
                if self._is_zero_mission_header(parts):
                    continue
                if self._is_claim_confirmation(parts):
                    continue

                if len(parts) not in (20, 21):
                    category = "incomplete" if len(parts) < 20 else "unknown"
                    self._log_rejected(
                        path, line_number, category, len(parts),
                        "unsupported logical field count",
                    )
                    continue

                damage = False
                wounds = False
                notes_index = 19
                if len(parts) == 21:
                    damage_flag = self._bool_field(parts[18])
                    wounds_flag = self._bool_field(parts[19])
                    if damage_flag is None or wounds_flag is None:
                        self._log_rejected(
                            path, line_number, "extended", len(parts),
                            "damage or wound flag is not a recognized token",
                        )
                        continue
                    damage = damage_flag
                    wounds = wounds_flag
                    notes_index = 20

                try:
                    mission_date, mission_time = self._validated_date_time(parts)
                    m = WoFFMission()
                    m.source_file = os.path.basename(path)
                    m.pilotId = pilot_name
                    m.date = mission_date
                    m.time = mission_time
                    m.sector = parts[5]
                    m.aircraft = parts[8]
                    m.missionType = normalize_mission_type(parts[7])
                    m.duration = parts[10]
                    m.squadron = parts[13]
                    m.damageReceived = damage
                    m.woundsReceived = wounds
                    m.notes = parts[notes_index][:500]
                    notes_lower = m.notes.lower()
                    m.result = "Shot Down — KIA" if "killed" in notes_lower else "Crash Landing — Survived" if "crash" in notes_lower else "Completed"
                    self.missions.append(m)
                except (ValueError, IndexError) as exc:
                    self._log_rejected(
                        path, line_number, "malformed", len(parts), str(exc),
                    )
            
            # FIX: Criar placeholder pilot se não existir para que o handler e DB o possam usar
            if not self.pilot:
                self.pilot = WoFFPilot(name=pilot_name, source_file=os.path.basename(path))
                
            return bool(self.missions)
        except Exception as e:
            log.error(f"  Falha ao ler {path}: {e}"); return False

    def _parse_claims(self, path: str, pilot_name: str) -> bool:
        log.info(f"[TXT] Analisando Vitórias (Claims): {os.path.basename(path)}")
        try:
            with open(path, "r", encoding="cp1252", errors="replace") as f: lines = f.readlines()
            for line in lines[1:]:
                line = line.strip()
                if not line: continue
                parts = [part.strip() for part in line.split(";")]
                if len(parts) >= 12:
                    v = WoFFVictory()
                    v.source_file = os.path.basename(path)
                    v.pilotId = pilot_name
                    v.date = normalize_date(f"{parts[0]}/{parts[1]}/{parts[2]}")
                    v.time = f"{parts[3].replace('h','').zfill(2)}:{parts[4].zfill(2)}"
                    v.sector = parts[5]
                    v.aircraft = parts[8]
                    v.enemyType = parts[10]
                    v.victoryType = normalize_victory_type(parts[11])
                    v.confirmed = "confirmed" in parts[11].lower()
                    if len(parts) > 20: v.witnesses = f"{parts[18]} - {parts[19]} {parts[20]}".strip()
                    self.victories.append(v)
                    
            # FIX: Criar placeholder pilot se não existir
            if not self.pilot:
                self.pilot = WoFFPilot(name=pilot_name, source_file=os.path.basename(path))
                
            return bool(self.victories)
        except Exception as e:
            log.error(f"  Falha ao ler {path}: {e}"); return False
