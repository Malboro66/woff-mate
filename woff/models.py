#!/usr/bin/env python3
"""
Modelos de Dados (models.py)
══════════════════════════════════════════════════════════════════
"""

import hashlib
import ntpath
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

def _uid() -> str:
    return uuid.uuid4().hex[:12]


def stable_source_record_key(
    record_kind: str,
    source_name: str,
    source_position: int,
) -> str:
    """Return a privacy-safe identity for one stable source record position."""
    kind = str(record_kind or "").strip().casefold()
    filename = ntpath.basename(str(source_name or "").replace("/", "\\")).casefold()
    if not kind or not filename:
        raise ValueError("record kind and source filename are required")
    if (
        not isinstance(source_position, int)
        or isinstance(source_position, bool)
        or source_position < 1
    ):
        raise ValueError("source position must be a positive integer")
    source_payload = f"{kind}\0{filename}".encode("utf-8")
    source_digest = hashlib.sha256(source_payload).hexdigest()
    record_payload = source_payload + f"\0{source_position}".encode("ascii")
    record_digest = hashlib.sha256(record_payload).hexdigest()
    return f"source-v1:{source_digest}:{record_digest}"

@dataclass
class WoFFPilot:
    """Representa os dados de um piloto na campanha."""
    id:           str = field(default_factory=_uid)
    name:         str = ""
    fName:        str = ""
    sName:        str = ""
    nation:       str = ""
    rank:         str = ""
    squadron:     str = ""
    aircraft:     str = ""
    aerodrome:    str = ""
    sector:       str = ""
    startDate:    str = ""
    enlisted:     str = "" 
    # ``None`` means that this source did not provide pilot status.  A real
    # ``Active`` value remains distinct and writable when supplied by an
    # authoritative source.
    status:       Optional[str] = None
    notes:        str = ""
    photo:        str = ""
    
    # Estatísticas extraídas do Dossier
    birthDate:    str = ""
    birthPlace:   str = ""
    # ``None`` means that a partial source did not provide the statistic.
    # Integer zero remains an authoritative value supplied by the Dossier.
    missions:     Optional[int] = None
    flminutes:    Optional[int] = None
    claimsCount:  Optional[int] = None
    killsCount:   Optional[int] = None
    skill:        Optional[int] = None
    reputation:   Optional[int] = None
    
    source_file:  str = ""
    last_updated: str = ""

@dataclass
class WoFFMission:
    id:             str  = field(default_factory=_uid)
    pilotId:        str  = ""
    date:           str  = ""
    time:           str  = "" # ADICIONADO: Para deduplicação correta
    missionType:    str  = ""
    aircraft:       str  = ""
    duration:       str  = ""
    altitude:       str  = ""
    sector:         str  = ""
    squadron:       str  = ""
    weather:        str  = ""
    enemyContacts:  int  = 0
    claimsCount:    int  = 0
    result:         str  = ""
    damageReceived: bool = False
    woundsReceived: bool = False
    notes:          str  = ""
    source_file:    str  = ""
    # Transient source text used to reconcile identities produced by older
    # normalizers. It is intentionally not part of the database schema.
    rawMissionType: str  = ""

@dataclass
class WoFFVictory:
    id:          str  = field(default_factory=_uid)
    pilotId:     str  = ""
    date:        str  = ""
    time:        str  = ""
    missionId:   str  = ""
    enemyType:   str  = ""
    victoryType: str  = ""
    location:    str  = ""
    confirmed:   bool = False
    witnesses:   str  = ""
    notes:       str  = ""
    sector:      str  = ""
    aircraft:    str  = ""
    source_file: str  = ""
    source_record_key: str = ""

@dataclass
class WoFFDecoration:
    id:          str = field(default_factory=_uid)
    pilotId:     str = ""
    name:        str = ""
    date:        str = ""
    citation:    str = ""
    source_file: str = ""

@dataclass
class WoFFWingman:
    id:          str = field(default_factory=_uid)
    pilotId:     str = ""
    rank:        str = ""
    fName:       str = ""
    sName:       str = ""
    skill:       int = 0
    morale:      int = 0
    status:      str = "Active"
    missions:    int = 0
    flminutes:   int = 0
    bio:         str = ""
