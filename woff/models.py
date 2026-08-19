#!/usr/bin/env python3
"""
Modelos de Dados (models.py)
══════════════════════════════════════════════════════════════════
"""

import uuid
from dataclasses import dataclass, field
from typing import List, Optional

def _uid() -> str:
    return uuid.uuid4().hex[:12]

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
    status:       str = "Active"
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
