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
    ) -> Tuple[int, int, int]:
        """Insere missões, vitórias e condecorações associadas ao piloto."""
        cursor = self._conn.cursor()
        added_m = 0
        for m in missions:
            raw_time = str(m.time or "").strip()
            canonical_date = normalize_date(m.date)
            canonical_time = normalize_time(raw_time)
            if not canonical_date:
                log.warning("Mission quarantined at write boundary: category=invalid-date")
                continue
            if raw_time and not canonical_time:
                log.warning("Mission quarantined at write boundary: category=invalid-time")
                continue
            m.date = canonical_date
            m.time = canonical_time
            m.pilotId = pilot_id
            cursor.execute("""
                INSERT OR IGNORE INTO missions (
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
            added_m += cursor.rowcount

        added_v = 0
        for v in victories:
            v.pilotId = pilot_id
            cursor.execute("""
                INSERT OR IGNORE INTO victories (
                    id, pilotId, date, time, missionId, enemyType, victoryType,
                    location, confirmed, witnesses, notes, sector, aircraft,
                    source_file
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                v.id, v.pilotId, v.date, v.time, v.missionId, v.enemyType,
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

        return added_m, added_v, added_d

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
        raw_time = str(mission.time or "").strip()
        canonical_date = normalize_date(mission.date)
        canonical_time = normalize_time(raw_time)
        if not canonical_date or (raw_time and not canonical_time):
            return None
        with self._lock:
            row = self._fetch_one(
                """SELECT id FROM missions
                   WHERE pilotId = ? AND date = ? AND time = ?
                     AND missionType = ? AND aircraft = ?""",
                (
                    pilot_id, canonical_date, canonical_time,
                    mission.missionType, mission.aircraft,
                ),
            )
            return str(row[0]) if row else None

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
