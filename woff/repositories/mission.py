#!/usr/bin/env python3
"""
Repositório de Missões (repositories/mission.py)
══════════════════════════════════════════════════════════════════
Responsável por queries e operações específicas da entidade WoFFMission.
Nota: O INSERT em massa de missões permanece no DatabaseManager (Unit of Work)
porque é coordenado dentro de uma transação cross-entidade.
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

from dataclasses import dataclass
import ntpath
import re
import sqlite3
import logging
from typing import List, Dict, Any, Optional, Tuple

from ..models import WoFFMission, WoFFVictory, WoFFDecoration
from ..normalization import (
    MissionOrderKey,
    canonical_mission_order_key,
    normalize_date,
    normalize_time,
)

from .base import BaseRepository

log = logging.getLogger("WoFFWatch")

MissionIdentityKey = Tuple[str, str, str, str]


@dataclass(frozen=True)
class MissionMergeCounts:
    """Observable outcomes for every valid incoming mission record."""

    inserted: int = 0
    updated: int = 0
    unchanged: int = 0


_MISSION_TEXT_FIELDS = (
    "duration",
    "altitude",
    "sector",
    "squadron",
    "weather",
    "result",
    "notes",
)
_MISSION_INTEGER_FIELDS = ("enemyContacts", "claimsCount")
_MISSION_BOOLEAN_FIELDS = ("damageReceived", "woundsReceived")
_DEFAULT_TEXT_VALUES = {
    "weather": frozenset({"unknown"}),
    "result": frozenset({"uneventful"}),
}


def mission_source_priority(source_file: object) -> int:
    """Return the documented row-level authority of a mission source.

    The live ``mission.log`` debrief is authoritative over exported XML, which
    is authoritative over the historical PilotLog. Unknown sources remain
    mergeable but cannot overwrite a known, richer source.
    """
    filename = ntpath.basename(str(source_file or "").replace("/", "\\")).lower()
    if filename == "mission.log":
        return 30
    if filename.endswith(".xml"):
        return 20
    if re.fullmatch(r"pilot\d+log\.txt", filename):
        return 10
    return 0


def _is_default_text(field: str, value: object) -> bool:
    return str(value or "").strip().casefold() in _DEFAULT_TEXT_VALUES.get(
        field, frozenset()
    )


def _mission_merge_updates(
    stored: Dict[str, Any], incoming: WoFFMission
) -> Dict[str, Any]:
    """Select non-destructive mutable-field updates for a stable mission row."""
    updates: Dict[str, Any] = {}
    stored_priority = mission_source_priority(stored.get("source_file"))
    incoming_priority = mission_source_priority(incoming.source_file)
    incoming_is_authoritative = incoming_priority >= stored_priority

    for field in _MISSION_TEXT_FIELDS:
        stored_value = str(stored.get(field) or "").strip()
        incoming_value = str(getattr(incoming, field) or "").strip()
        if not incoming_value or incoming_value == stored_value:
            continue
        if not stored_value:
            updates[field] = incoming_value
            continue
        if _is_default_text(field, stored_value) and not _is_default_text(
            field, incoming_value
        ):
            updates[field] = incoming_value
            continue
        if _is_default_text(field, incoming_value) and not _is_default_text(
            field, stored_value
        ):
            continue
        if incoming_is_authoritative:
            updates[field] = incoming_value

    for field in _MISSION_INTEGER_FIELDS:
        stored_value = int(stored.get(field) or 0)
        incoming_value = int(getattr(incoming, field) or 0)
        if incoming_value == stored_value:
            continue
        if stored_value <= 0 < incoming_value:
            updates[field] = incoming_value
        elif incoming_value > 0 and incoming_is_authoritative:
            updates[field] = incoming_value

    for field in _MISSION_BOOLEAN_FIELDS:
        stored_value = bool(stored.get(field))
        incoming_value = bool(getattr(incoming, field))
        if incoming_value and not stored_value:
            updates[field] = 1

    stored_source = str(stored.get("source_file") or "").strip()
    incoming_source = str(incoming.source_file or "").strip()
    if incoming_source and (
        not stored_source or incoming_priority > stored_priority
    ):
        updates["source_file"] = incoming_source

    return updates


def _merge_existing_mission(
    cursor: sqlite3.Cursor, stored_mission_id: str, incoming: WoFFMission
) -> bool:
    mutable_fields = (
        *_MISSION_TEXT_FIELDS,
        *_MISSION_INTEGER_FIELDS,
        *_MISSION_BOOLEAN_FIELDS,
        "source_file",
    )
    row = cursor.execute(
        f"SELECT {', '.join(mutable_fields)} FROM missions WHERE id = ?",
        (stored_mission_id,),
    ).fetchone()
    if row is None:
        raise sqlite3.IntegrityError("stable mission identity disappeared")
    stored: Dict[str, Any] = {
        field: value for field, value in zip(mutable_fields, row)
    }
    updates = _mission_merge_updates(stored, incoming)
    if not updates:
        return False
    assignments = ", ".join(f"{field} = ?" for field in updates)
    cursor.execute(
        f"UPDATE missions SET {assignments} WHERE id = ?",
        (*updates.values(), stored_mission_id),
    )
    return True


def mission_identity_key(
    raw_date: object,
    raw_time: object,
    mission_type: object,
    aircraft: object,
) -> Optional[MissionIdentityKey]:
    """Return the schema identity after strict in-memory canonicalization."""
    canonical_date = normalize_date(str(raw_date or ""))
    raw_time_value = str(raw_time or "").strip()
    canonical_time = normalize_time(raw_time_value)
    if not canonical_date or (raw_time_value and not canonical_time):
        return None
    return (
        canonical_date,
        canonical_time,
        str(mission_type or ""),
        str(aircraft or ""),
    )


def stored_mission_identity_index(
    cursor: sqlite3.Cursor, pilot_id: str
) -> Dict[MissionIdentityKey, str]:
    """Index valid stored identities without changing legacy database rows.

    Exact canonical storage wins when equivalent duplicates already exist;
    otherwise the stable row ID breaks the tie deterministically.
    """
    choices: Dict[MissionIdentityKey, Tuple[Tuple[int, str], str]] = {}
    rows = cursor.execute(
        """
        SELECT id, date, time, missionType, aircraft
        FROM missions WHERE pilotId = ?
        """,
        (pilot_id,),
    ).fetchall()
    for row in rows:
        identity = mission_identity_key(row[1], row[2], row[3], row[4])
        if identity is None:
            continue
        row_id = str(row[0] or "")
        stored_date = str(row[1] or "").strip()
        stored_time = str(row[2] or "").strip()
        exact_canonical = stored_date == identity[0] and stored_time == identity[1]
        rank = (0 if exact_canonical else 1, row_id)
        previous = choices.get(identity)
        if previous is None or rank < previous[0]:
            choices[identity] = (rank, row_id)
    return {identity: choice[1] for identity, choice in choices.items()}


def mission_mapping_order_key(mission: Dict[str, Any]) -> Optional[MissionOrderKey]:
    """Return the shared deterministic order for a persisted mission mapping."""
    return canonical_mission_order_key(
        mission.get("date"),
        mission.get("time"),
        (
            mission.get("missionType"),
            mission.get("aircraft"),
            mission.get("sector"),
            mission.get("source_file"),
            mission.get("id"),
        ),
    )


def canonicalized_mission_mapping(
    mission: Dict[str, Any],
) -> Optional[Tuple[MissionOrderKey, Dict[str, Any]]]:
    """Canonicalize a readable legacy row without modifying the database."""
    order_key = mission_mapping_order_key(mission)
    if order_key is None:
        return None
    canonical = dict(mission)
    canonical["date"] = order_key[0]
    canonical["time"] = order_key[2]
    return order_key, canonical


class MissionRepository(BaseRepository):
    """Repositório especializado na entidade WoFFMission."""

    def upsert_mission(
        self,
        pilot_id: str,
        missions: List[WoFFMission],
        victories: List[WoFFVictory],
        decorations: List[WoFFDecoration],
    ) -> Tuple[MissionMergeCounts, int, int]:
        """Merge missions and insert victories/decorations for one pilot."""
        cursor = self._conn.cursor()
        identity_index: Optional[Dict[MissionIdentityKey, str]] = None
        mission_id_remap: Dict[str, str] = {}
        rejected_mission_ids: set[str] = set()
        inserted_m = 0
        updated_m = 0
        unchanged_m = 0
        for m in missions:
            raw_time = str(m.time or "").strip()
            canonical_date = normalize_date(m.date)
            if not canonical_date:
                if m.id:
                    rejected_mission_ids.add(m.id)
                log.warning("Mission quarantined at write boundary: category=invalid-date")
                continue
            canonical_time = normalize_time(raw_time)
            if raw_time and not canonical_time:
                if m.id:
                    rejected_mission_ids.add(m.id)
                log.warning("Mission quarantined at write boundary: category=invalid-time")
                continue
            identity = (
                canonical_date,
                canonical_time,
                str(m.missionType or ""),
                str(m.aircraft or ""),
            )
            m.date = canonical_date
            m.time = canonical_time
            m.pilotId = pilot_id
            if identity_index is None:
                identity_index = stored_mission_identity_index(cursor, pilot_id)
            stored_mission_id = identity_index.get(identity)
            if stored_mission_id is not None:
                if m.id and m.id != stored_mission_id:
                    mission_id_remap[m.id] = stored_mission_id
                if _merge_existing_mission(cursor, stored_mission_id, m):
                    updated_m += 1
                else:
                    unchanged_m += 1
                continue
            if m.id and cursor.execute(
                "SELECT 1 FROM missions WHERE id = ?", (m.id,)
            ).fetchone() is not None:
                rejected_mission_ids.add(m.id)
                log.warning(
                    "Mission quarantined at write boundary: category=id-conflict"
                )
                continue
            cursor.execute("""
                INSERT INTO missions (
                    id, pilotId, date, time, missionType, aircraft, duration,
                    altitude, sector, squadron, weather, enemyContacts,
                    claimsCount, result, damageReceived, woundsReceived, notes,
                    source_file
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                m.id, m.pilotId, m.date, m.time, m.missionType, m.aircraft,
                m.duration, m.altitude, m.sector, m.squadron, m.weather,
                m.enemyContacts, m.claimsCount, m.result,
                m.damageReceived, m.woundsReceived, m.notes,
                m.source_file
            ))
            inserted_m += 1
            identity_index[identity] = m.id

        added_v = 0
        for v in victories:
            v.pilotId = pilot_id
            if v.missionId and v.missionId in rejected_mission_ids:
                log.warning(
                    "Victory quarantined at write boundary: "
                    "category=rejected-parent-mission"
                )
                continue
            mission_id = mission_id_remap.get(v.missionId, v.missionId)
            cursor.execute("""
                INSERT OR IGNORE INTO victories (
                    id, pilotId, date, time, missionId, enemyType, victoryType,
                    location, confirmed, witnesses, notes, sector, aircraft,
                    source_file
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                v.id, v.pilotId, v.date, v.time, mission_id, v.enemyType,
                v.victoryType, v.location, v.confirmed, v.witnesses,
                v.notes, v.sector, v.aircraft, v.source_file
            ))
            added_v += cursor.rowcount

        added_d = 0
        for d in decorations:
            d.pilotId = pilot_id
            cursor.execute("""
                INSERT OR IGNORE INTO decorations (
                    id, pilotId, name, date, citation, source_file
                ) VALUES (?,?,?,?,?,?)
            """, (d.id, d.pilotId, d.name, d.date, d.citation, d.source_file))
            added_d += cursor.rowcount

        return (
            MissionMergeCounts(inserted_m, updated_m, unchanged_m),
            added_v,
            added_d,
        )

    def get_missions_by_pilot(
        self, pilot_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Busca as últimas missões de um piloto."""
        with self._lock:
            conn = self._conn
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT * FROM missions WHERE pilotId = ?",
                    (pilot_id,),
                ).fetchall()
                ordered = []
                for row in rows:
                    canonical = canonicalized_mission_mapping(dict(row))
                    if canonical is not None:
                        ordered.append(canonical)
                ordered.sort(key=lambda item: item[0], reverse=True)
                return [mission for _, mission in ordered[:max(0, limit)]]
            except sqlite3.Error:
                log.exception("Erro ao buscar missões")
                return []
            finally:
                conn.row_factory = None

    def get_id_by_natural_key(
        self, pilot_id: str, mission: WoFFMission
    ) -> Optional[str]:
        """Resolve the stored ID for the schema's mission natural identity."""
        identity = mission_identity_key(
            mission.date, mission.time, mission.missionType, mission.aircraft
        )
        if identity is None:
            return None
        with self._lock:
            return stored_mission_identity_index(
                self._conn.cursor(), pilot_id
            ).get(identity)

    def count_by_pilot(self, pilot_id: str) -> int:
        """Conta missões de um piloto."""
        with self._lock:
            try:
                row = self._fetch_one(
                    "SELECT COUNT(*) FROM missions WHERE pilotId = ?",
                    (pilot_id,),
                )
                return row[0] if row else 0
            except sqlite3.Error:
                log.exception("Erro ao contar missões")
                return 0
