#!/usr/bin/env python3
"""
Parser de Dados do Piloto (parsers/pilot_data_parser.py)
══════════════════════════════════════════════════════════════════
"""
import os, re, logging
from typing import List, Optional
from ..models import (
    WoFFMission,
    WoFFPilot,
    WoFFVictory,
    stable_source_record_key,
)
from ..normalization import (
    normalize_date,
    normalize_mission_type,
    normalize_time,
    normalize_victory_type,
)

log = logging.getLogger("WoFFWatch")

class WoFFPilotDataParser:
    def __init__(self):
        self.pilot: Optional[WoFFPilot] = None
        self.missions: List[WoFFMission] = []
        self.victories: List[WoFFVictory] = []
        self.valid_empty = False
        self.rejected_records = 0

    @property
    def has_rejected_records(self) -> bool:
        """Report whether any candidate record was rejected in the last parse."""

        return self.rejected_records > 0

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
    def _has_claim_confirmation_signature(parts: List[str]) -> bool:
        return len(parts) > 5 and parts[5].lower().startswith(
            "confirmation received of claim submitted on:"
        )

    @staticmethod
    def _declares_zero_records(lines: List[str]) -> bool:
        for raw_line in lines:
            marker = raw_line.strip()
            if marker:
                return marker.isdigit() and int(marker) == 0
        return False

    @staticmethod
    def _validated_date_time(parts: List[str]) -> tuple[str, str]:
        day = parts[0].replace("/", "").strip()
        month = parts[1].replace("/", "").strip()
        year = parts[2].strip()
        hour = parts[3].lower().removesuffix("h").strip()
        minute = parts[4].strip()
        if not all(value.isdigit() for value in (day, month, year, hour, minute)):
            raise ValueError("date or time contains a non-numeric component")
        canonical_date = normalize_date(f"{day}/{month}/{year}")
        canonical_time = normalize_time(f"{hour}:{minute}")
        if not canonical_date or not canonical_time:
            raise ValueError("date or time is outside the calendar contract")
        return canonical_date, canonical_time

    @staticmethod
    def _log_rejected(path: str, line_number: int, category: str,
                      field_count: int, reason: str) -> None:
        log.warning(
            "[TXT] PilotLog record rejected: source=%s line=%d "
            "category=%s fields=%d reason=%s",
            os.path.basename(path), line_number, category, field_count, reason,
        )

    def parse(self, path: str) -> bool:
        self.valid_empty = False
        self.rejected_records = 0
        try:
            with open(path, "rb") as source:
                data = source.read()
        except Exception as e:
            log.error(f"  Falha ao ler {path}: {e}")
            return False
        return self.parse_bytes(data, os.path.basename(path))

    def parse_bytes(self, data: bytes | str, source_name: str) -> bool:
        """Parse verified bytes without reopening their source path."""
        self.valid_empty = False
        self.rejected_records = 0
        fname = os.path.basename(source_name).lower()
        if "dossier" in fname: return False

        pilot_match = re.match(r"(pilot\d+)", fname, re.I)
        if not pilot_match: return False
        
        pilot_name = pilot_match.group(1).replace("pilot", "Pilot ")
        
        content = data.decode("cp1252", errors="replace") if isinstance(data, bytes) else data
        lines = content.splitlines(keepends=True)
        if "squads" in fname: return self._parse_squads(lines, source_name, pilot_name)
        elif "log" in fname: return self._parse_log(lines, source_name, pilot_name)
        elif "claims" in fname: return self._parse_claims(lines, source_name, pilot_name)
        return False

    def _parse_squads(self, lines: List[str], path: str, pilot_name: str) -> bool:
        log.info(f"[TXT] Analisando Esquadrões: {os.path.basename(path)}")
        try:
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

    def _parse_log(self, lines: List[str], path: str, pilot_name: str) -> bool:
        log.info(f"[TXT] Analisando Log de Missões: {os.path.basename(path)}")
        try:
            declared_zero = self._declares_zero_records(lines)
            saw_zero_header = False
            for line_number, raw_line in enumerate(lines, start=1):
                line = raw_line.rstrip("\r\n")
                if not line.strip() or line.strip().isdigit():
                    continue
                parts = self._normalized_fields(line)
                if self._is_zero_mission_header(parts):
                    saw_zero_header = True
                    continue
                if self._has_claim_confirmation_signature(parts):
                    if len(parts) < 26:
                        self.rejected_records += 1
                        self._log_rejected(
                            path, line_number, "truncated-claim-confirmation",
                            len(parts),
                            "claim confirmation has fewer than 26 fields",
                        )
                    continue

                if len(parts) < 20:
                    self.rejected_records += 1
                    self._log_rejected(
                        path, line_number, "incomplete", len(parts),
                        "unsupported logical field count",
                    )
                    continue

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
                    m.damageReceived = False
                    m.woundsReceived = False
                    m.notes = ";".join(parts[19:])[:500]
                    notes_lower = m.notes.lower()
                    m.result = "Shot Down — KIA" if "killed" in notes_lower else "Crash Landing — Survived" if "crash" in notes_lower else "Completed"
                    self.missions.append(m)
                except (ValueError, IndexError) as exc:
                    self.rejected_records += 1
                    self._log_rejected(
                        path, line_number, "malformed", len(parts), str(exc),
                    )
            
            # FIX: Criar placeholder pilot se não existir para que o handler e DB o possam usar
            if not self.pilot:
                self.pilot = WoFFPilot(name=pilot_name, source_file=os.path.basename(path))

            self.valid_empty = (
                not self.missions
                and not self.has_rejected_records
                and (declared_zero or saw_zero_header)
            )
            return bool(self.missions)
        except Exception as e:
            log.error(f"  Falha ao ler {path}: {e}"); return False

    def _parse_claims(self, lines: List[str], path: str, pilot_name: str) -> bool:
        log.info(f"[TXT] Analisando Vitórias (Claims): {os.path.basename(path)}")
        try:
            declared_zero = self._declares_zero_records(lines)
            for line_number, line in enumerate(lines[1:], start=2):
                line = line.strip()
                if not line: continue
                parts = [part.strip() for part in line.split(";")]
                if len(parts) >= 12:
                    v = WoFFVictory()
                    v.source_file = os.path.basename(path)
                    v.source_record_key = stable_source_record_key(
                        "victory", path, line_number
                    )
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
                else:
                    self.rejected_records += 1
                    log.warning(
                        "[TXT] PilotClaims record rejected: source=%s "
                        "line=%d fields=%d reason=incomplete record",
                        os.path.basename(path), line_number, len(parts),
                    )

            # FIX: Criar placeholder pilot se não existir
            if not self.pilot:
                self.pilot = WoFFPilot(name=pilot_name, source_file=os.path.basename(path))

            self.valid_empty = (
                not self.victories
                and declared_zero
                and not self.has_rejected_records
            )
            return bool(self.victories)
        except Exception as e:
            log.error(f"  Falha ao ler {path}: {e}"); return False
