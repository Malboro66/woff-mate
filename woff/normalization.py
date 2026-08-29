#!/usr/bin/env python3
"""
Módulo de Normalização (normalization.py)
══════════════════════════════════════════════════════════════════
Contém as funções de lógica para limpar, padronizar e normalizar 
dados extraídos dos ficheiros XML e TXT do WoFF BHaH II.

As tabelas de mapeamento e expressões regulares estão importadas 
do módulo maps.py, garantindo uma separação clara entre dados 
estáticos e lógica de processamento.
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, time
from typing import Iterable, Literal, Optional, Tuple

# Importar as tabelas estáticas e regex do maps.py
from .maps import (
    NATION_MAP, MISSION_TYPE_MAP, STATUS_PATTERNS, WOUND_RE, SEVERE_RE,
    VICTORY_TYPE_MAP, MONTHS_MAP
)

log = logging.getLogger("WoFFWatch")


def _match_token_alias(raw: str, mapping: dict) -> Optional[str]:
    """Return a mapped value only for an explicit token or phrase alias."""
    normalized = raw.casefold()
    for keys, value in mapping.items():
        aliases = keys if isinstance(keys, tuple) else (keys,)
        for alias in aliases:
            pattern = rf"(?<!\w){re.escape(alias.casefold())}(?!\w)"
            if re.search(pattern, normalized):
                return value
    return None


def resolve_nation_alias(raw: str) -> Optional[str]:
    """Return the canonical nation for an exact known alias."""
    value = raw.strip() if raw else ""
    if not value:
        return None
    return NATION_MAP.get(value.casefold())


def normalize_nation(raw: str) -> str:
    value = raw.strip() if raw else ""
    return resolve_nation_alias(value) or value


def normalize_mission_type(raw: str) -> str:
    value = raw.strip() if raw else ""
    return _match_token_alias(value, MISSION_TYPE_MAP) or value


def normalize_status(
    raw: Optional[str], root: Optional[ET.Element] = None
) -> Optional[str]:
    """Normalize an explicit status or preserve its absence as ``None``."""
    if not raw or not raw.strip():
        return None
    value = raw.strip()
    
    for pattern, status in STATUS_PATTERNS:
        if pattern.search(value):
            return status
            
    if WOUND_RE.search(value):
        severity = ""
        if root is not None:
            sev_elem = root.find(".//WoundSeverity")
            if sev_elem is None:
                sev_elem = root.find(".//Severity")
            # Corrigido: evita o DeprecationWarning do Python 3.14
            if sev_elem is not None and sev_elem.text:
                severity = sev_elem.text.lower()
        if SEVERE_RE.search(severity):
            return "Seriously Wounded"
        return "Lightly Wounded"
        
    return None


def normalize_victory_type(raw: str) -> str:
    value = raw.strip() if raw else ""
    return _match_token_alias(value, VICTORY_TYPE_MAP) or value


def _calendar_date(year: str | int, month: str | int, day: str | int) -> str:
    """Return an ISO date only when the components form a real calendar day."""
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except (OverflowError, TypeError, ValueError):
        return ""


def normalize_date(
    raw: str | None,
    *,
    numeric_order: Literal["day-first", "month-first"] = "day-first",
) -> str:
    """Normalize a supported real date to ``YYYY-MM-DD``.

    Missing, unrecognized, and impossible values all return the explicit absent
    representation ``""``. Numeric day-first input remains the default;
    source-specific parsers can select month-first interpretation explicitly.
    The selected source contract is strict, so an invalid value is never
    reinterpreted under a different locale order.
    """
    value = str(raw or "").strip()
    if not value:
        return ""

    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if match:
        return _calendar_date(*match.groups())

    match = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", value)
    if match:
        first, second, year = match.groups()
        candidate = (
            (year, second, first)
            if numeric_order == "day-first"
            else (year, first, second)
        )
        return _calendar_date(*candidate)

    match = re.fullmatch(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", value)
    if match:
        year, month, day = match.groups()
        return _calendar_date(year, month, day)

    lowered = value.lower()
    for name, month in sorted(MONTHS_MAP.items(), key=lambda item: -len(item[0])):
        if not re.search(rf"(?<!\w){re.escape(name)}(?!\w)", lowered):
            continue
        numbers = [int(number) for number in re.findall(r"\d+", value)]
        year = next((number for number in numbers if 1000 <= number <= 9999), None)
        day = next((number for number in numbers if 1 <= number <= 31), None)
        if year is not None and day is not None:
            canonical = _calendar_date(year, month, day)
            if canonical:
                return canonical

    log.debug("Date value rejected by canonical temporal contract")
    return ""


def normalize_time(raw: str | None) -> str:
    """Normalize a supported clock time to ``HH:MM`` or return absence.

    Both ``H:MM`` and the WoFF-style ``HhMM`` form are accepted. Calendar-free
    values such as ``24:00`` are rejected rather than persisted as raw text.
    """
    value = str(raw or "").strip()
    if not value:
        return ""
    match = re.fullmatch(r"(\d{1,2})\s*(?::|[hH])\s*(\d{1,2})", value)
    if not match:
        return ""
    try:
        parsed = time(int(match.group(1)), int(match.group(2)))
    except ValueError:
        return ""
    return parsed.strftime("%H:%M")


MissionOrderKey = Tuple[str, int, str, Tuple[str, ...]]


def canonical_mission_order_key(
    raw_date: object,
    raw_time: object = "",
    tie_breaker: Iterable[object] = (),
) -> Optional[MissionOrderKey]:
    """Return a comparable key for a mission or ``None`` for an invalid date.

    Known canonical times sort after missing or malformed legacy times on the
    same date. Callers append stable semantic fields as the final tie-breaker so
    equal timestamps never depend on source or database row order.
    """
    canonical_date = normalize_date(str(raw_date or ""))
    if not canonical_date:
        return None
    canonical_time = normalize_time(str(raw_time or ""))
    stable_tie = tuple(str(value or "") for value in tie_breaker)
    return canonical_date, int(bool(canonical_time)), canonical_time, stable_tie

# ──────────────────────────────────────────────────────────────
# CONVERSÃO DE COORDENADAS (Para mapas na Fase 3)
# ──────────────────────────────────────────────────────────────

def normalize_coordinates(raw: str) -> Optional[float]:
    """
    Converte o formato de coordenadas do WoFF (ex: N50*23'34.6102") 
    para graus decimais (ex: 50.3928339), ideal para APIs de mapas.
    Suporta N, S, E, W.
    """
    if not raw:
        return None
        
    raw = raw.strip().upper()
    
    # Regex para extrair Direção, Graus, Minutos e Segundos
    # Exemplo de match: N50*23'34.6102" ou E2*36'50.609
    match = re.match(r"^([NSEW])(\d{1,3})\*(\d{1,2})'(\d{1,2}(?:\.\d+)?)[\"\u201d]?$", raw)
    if not match:
        log.debug(f"Coordenada não reconhecida: '{raw}'")
        return None
        
    direction, deg_str, min_str, sec_str = match.groups()
    
    try:
        degrees = float(deg_str)
        minutes = float(min_str)
        seconds = float(sec_str)
        
        # Fórmula de conversão DMS para Decimal
        decimal_degrees = degrees + (minutes / 60.0) + (seconds / 3600.0)
        
        # Sul e Oeste são negativos
        if direction in ('S', 'W'):
            decimal_degrees *= -1
            
        return round(decimal_degrees, 6) # Precisão de 6 casas é suficiente para mapas
        
    except ValueError as e:
        log.warning(f"Erro ao converter coordenada '{raw}': {e}")
        return None
