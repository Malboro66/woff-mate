#!/usr/bin/env python3
"""
Repositório de Wingmen (repositories/wingman.py)
══════════════════════════════════════════════════════════════════
Responsável por:
  - squad_members (queries)
  - wingmen_personalities (UPSERT)
  - wingmen_memory (INSERT)
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import sqlite3
import logging
from typing import Optional, List, Dict, Any

from ..identity import (
    WingmanIdentityResolutionError,
    WingmanIdentityResolutionKind,
    resolve_wingman_identity,
    wingman_identity_key,
)
from ..models import _uid, WoFFWingman
from .base import BaseRepository

log = logging.getLogger("WoFFWatch")

_MUTABLE_FIELDS = (
    "rank",
    "skill",
    "morale",
    "status",
    "missions",
    "flminutes",
    "bio",
)


class WingmanRepository(BaseRepository):
    """Repositório especializado em Wingmen AI."""

    @staticmethod
    def _row_to_wingman(row: sqlite3.Row | tuple) -> WoFFWingman:
        return WoFFWingman(
            id=str(row[0]),
            pilotId=str(row[1] or ""),
            rank=str(row[2] or ""),
            fName=str(row[3] or ""),
            sName=str(row[4] or ""),
            skill=int(row[5]) if row[5] is not None else 0,
            morale=int(row[6]) if row[6] is not None else 0,
            status=str(row[7] or ""),
            missions=int(row[8]) if row[8] is not None else 0,
            flminutes=int(row[9]) if row[9] is not None else 0,
            bio=str(row[10] or ""),
            birthDate=str(row[11] or ""),
            evidenceDate=str(row[12] or ""),
            evidenceLocation=str(row[13] or ""),
        )

    def _stored_wingmen(self, pilot_id: str) -> List[WoFFWingman]:
        rows = self._conn.execute(
            """
            SELECT id, pilotId, rank, fName, sName, skill, morale,
                   status, missions, flminutes, bio,
                   birthDate, evidenceDate, evidenceLocation
            FROM squad_members
            WHERE pilotId = ?
            ORDER BY id
            """,
            (pilot_id,),
        ).fetchall()
        return [self._row_to_wingman(row) for row in rows]

    @staticmethod
    def _authoritative_fields(wingman: WoFFWingman) -> tuple[str, ...]:
        if wingman.present_fields is None:
            return _MUTABLE_FIELDS
        return tuple(
            field for field in _MUTABLE_FIELDS if field in wingman.present_fields
        )

    def _insert_wingman(
        self,
        cursor: sqlite3.Cursor,
        pilot_id: str,
        wingman: WoFFWingman,
    ) -> int:
        authoritative = set(self._authoritative_fields(wingman))
        wingman.pilotId = pilot_id

        def value(field: str) -> object:
            return getattr(wingman, field) if field in authoritative else None

        cursor.execute(
            """
            INSERT INTO squad_members (
                id, pilotId, rank, fName, sName, skill, morale,
                status, missions, flminutes, bio,
                birthDate, evidenceDate, evidenceLocation
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                wingman.id,
                pilot_id,
                value("rank"),
                wingman.fName,
                wingman.sName,
                value("skill"),
                value("morale"),
                value("status"),
                value("missions"),
                value("flminutes"),
                value("bio"),
                wingman.birthDate or None,
                wingman.evidenceDate or None,
                wingman.evidenceLocation or None,
            ),
        )
        return cursor.rowcount

    def _update_wingman(
        self,
        cursor: sqlite3.Cursor,
        persistent_id: str,
        wingman: WoFFWingman,
    ) -> int:
        fields = self._authoritative_fields(wingman)
        if not fields:
            return 0
        assignments = ", ".join(f"{field} = ?" for field in fields)
        values = [getattr(wingman, field) for field in fields]
        cursor.execute(
            f"UPDATE squad_members SET {assignments} WHERE id = ?",
            (*values, persistent_id),
        )
        return cursor.rowcount

    def _upsert_programmatic(
        self,
        cursor: sqlite3.Cursor,
        pilot_id: str,
        wingman: WoFFWingman,
    ) -> int:
        row = cursor.execute(
            "SELECT pilotId FROM squad_members WHERE id = ?",
            (wingman.id,),
        ).fetchone()
        if row is None:
            return self._insert_wingman(cursor, pilot_id, wingman)
        if str(row[0] or "") != pilot_id:
            raise sqlite3.IntegrityError(
                "wingman ID already belongs to another persistent pilot"
            )
        wingman.pilotId = pilot_id
        return self._update_wingman(cursor, wingman.id, wingman)

    @staticmethod
    def _validate_incoming_dossier_batch(wingmen: List[WoFFWingman]) -> None:
        seen: set[tuple[str, str, str, str, str]] = set()
        for wingman in wingmen:
            if wingman.present_fields is None:
                continue
            key = wingman_identity_key(wingman)
            if key is None:
                continue
            if key in seen:
                raise WingmanIdentityResolutionError(
                    WingmanIdentityResolutionKind.AMBIGUOUS,
                    "duplicate-incoming-evidence",
                )
            seen.add(key)

    def upsert_wingmen_batch(
        self, pilot_id: str, wingmen: Optional[List[WoFFWingman]]
    ) -> int:
        """Persist wingmen without using display name or row order as identity."""
        if not wingmen:
            return 0

        self._validate_incoming_dossier_batch(wingmen)
        cursor = self._conn.cursor()
        stored = self._stored_wingmen(pilot_id)
        changed = 0

        for wingman in wingmen:
            wingman.pilotId = pilot_id

            # Programmatic/legacy callers that have no Dossier presence metadata
            # retain explicit ID semantics. They never fall back to name.
            if wingman.present_fields is None:
                changed += self._upsert_programmatic(cursor, pilot_id, wingman)
                if not any(candidate.id == wingman.id for candidate in stored):
                    stored.append(wingman)
                continue

            resolution = resolve_wingman_identity(wingman, stored)
            if resolution.kind is WingmanIdentityResolutionKind.MATCHED:
                assert resolution.wingman_id is not None
                wingman.id = resolution.wingman_id
                changed += self._update_wingman(
                    cursor, resolution.wingman_id, wingman
                )
                continue
            if resolution.kind is WingmanIdentityResolutionKind.NEW:
                changed += self._insert_wingman(cursor, pilot_id, wingman)
                stored.append(wingman)
                continue
            raise WingmanIdentityResolutionError(
                resolution.kind,
                resolution.reason,
            )

        return changed

    def get_wingmen_by_pilot(self, pilot_id: str) -> List[Dict[str, Any]]:
        """Busca os wingmen atuais de um piloto."""
        with self._lock:
            conn = self._conn
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT fName, sName, status FROM squad_members WHERE pilotId = ?",
                    (pilot_id,),
                ).fetchall()
                return [dict(r) for r in rows]
            except sqlite3.Error:
                log.exception("Erro ao buscar wingmen")
                return []
            finally:
                conn.row_factory = None

    def get_wingman_personality(self, wingman_id: str) -> Optional[Dict[str, Any]]:
        """Busca a personalidade 3P de um wingman."""
        with self._lock:
            conn = self._conn
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT * FROM wingmen_personalities WHERE wingmanId = ?",
                    (wingman_id,),
                ).fetchone()
                return dict(row) if row else None
            except sqlite3.Error:
                log.exception("Erro ao buscar personalidade")
                return None
            finally:
                conn.row_factory = None

    def save_wingman_personality(
        self, wingman_id: str, pilot_id: str, personality: Dict[str, Any]
    ) -> bool:
        """Guarda ou atualiza a personalidade 3P de um wingman."""
        try:
            with self._db.transaction():
                self._query(
                    """
                    INSERT INTO wingmen_personalities (
                        wingmanId, pilotId, aerial_skill, aggression, charisma,
                        intelligence, physicality, professionalism, personality_trait
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(wingmanId) DO UPDATE SET
                        aerial_skill=excluded.aerial_skill,
                        aggression=excluded.aggression,
                        charisma=excluded.charisma,
                        intelligence=excluded.intelligence,
                        physicality=excluded.physicality,
                        professionalism=excluded.professionalism,
                        personality_trait=excluded.personality_trait
                    """,
                    (
                        wingman_id,
                        pilot_id,
                        personality.get("aerial_skill", 50),
                        personality.get("aggression", 50),
                        personality.get("charisma", 50),
                        personality.get("intelligence", 50),
                        personality.get("physicality", 50),
                        personality.get("professionalism", 50),
                        personality.get("personality_trait", "Standard"),
                    ),
                )
                return True
        except sqlite3.Error:
            log.exception("Erro ao salvar personalidade")
            return False

    def save_wingman_memory(
        self,
        wingman_id: str,
        event_type: str,
        event_date: str,
        description: str,
        impact_morale: int = 0,
        impact_stress: int = 0,
    ) -> bool:
        """Regista um evento na memória do Wingman."""
        try:
            with self._db.transaction():
                self._query(
                    """
                    INSERT INTO wingmen_memory (
                        id, wingmanId, event_type, event_date, description,
                        impact_morale, impact_stress
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _uid(),
                        wingman_id,
                        event_type,
                        event_date,
                        description,
                        impact_morale,
                        impact_stress,
                    ),
                )
                return True
        except sqlite3.Error:
            log.exception("Erro ao salvar memória")
            return False
