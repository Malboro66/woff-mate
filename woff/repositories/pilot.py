#!/usr/bin/env python3
"""Pilot persistence and stable career identity resolution."""

from __future__ import annotations

import logging
import ntpath
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..identity import (
    PilotIdentityAmbiguous,
    PilotIdentityEvidence,
    PilotIdentityKind,
    PilotIdentityRejected,
    PilotIdentityUnavailable,
    dossier_source_name,
    pilot_slot,
)
from ..models import WoFFMission, WoFFPilot, WoFFVictory
from ..normalization import normalize_date
from .base import BaseRepository
from .mission import canonicalized_mission_mapping

log = logging.getLogger("WoFFWatch")
_PLACEHOLDER_NAME = re.compile(r"^Pilot [1-9][0-9]*$")
_STATUS_WRITABLE_BY = frozenset({PilotIdentityKind.DOSSIER})


class PilotRepository(BaseRepository):
    """Repository specialized in one persistent WoFF career at a time."""

    def upsert_pilot(
        self,
        pilot: Optional[WoFFPilot],
        missions: List[WoFFMission],
        victories: List[WoFFVictory],
        identity: Optional[PilotIdentityEvidence] = None,
        related_pilot_ids: Optional[List[Optional[str]]] = None,
    ) -> str:
        """Persist a pilot only when its career identity is verified."""

        if pilot is None:
            ids = related_pilot_ids
            if ids is None:
                ids = [item.pilotId for item in [*missions, *victories]]
            return self._resolve_explicit_related_pilot(ids)
        if identity is None or identity.kind is PilotIdentityKind.UNRESOLVED:
            raise PilotIdentityRejected("unsupported-identity-source")
        if identity.kind is PilotIdentityKind.DOSSIER:
            return self._upsert_dossier_pilot(pilot, identity)
        return self._upsert_slot_dependent_pilot(pilot, identity)

    def _resolve_explicit_related_pilot(
        self, pilot_ids: List[Optional[str]]
    ) -> str:
        if not pilot_ids or any(
            not value or not value.strip() for value in pilot_ids
        ):
            raise PilotIdentityRejected("missing-explicit-pilot-id")
        distinct = {str(value) for value in pilot_ids}
        if len(distinct) != 1:
            raise PilotIdentityAmbiguous("mixed-explicit-pilot-ids")
        pilot_id = next(iter(distinct))
        row = self._conn.execute(
            "SELECT 1 FROM pilots WHERE id=?", (pilot_id,)
        ).fetchone()
        if row is None:
            raise PilotIdentityRejected("unknown-explicit-pilot-id")
        return pilot_id

    def _upsert_dossier_pilot(
        self, pilot: WoFFPilot, identity: PilotIdentityEvidence
    ) -> str:
        slot = self._validated_source_slot(pilot, identity, dossier=True)
        campaign_namespace = identity.campaign_namespace
        if campaign_namespace is None:
            raise PilotIdentityRejected("missing-campaign-namespace", slot)
        if not pilot.name.strip():
            raise PilotIdentityRejected("identityless-dossier", slot)

        cursor = self._conn.cursor()
        bound = cursor.execute(
            """
            SELECT p.id, p.name
            FROM pilot_slot_bindings AS binding
            JOIN pilots AS p ON p.id = binding.pilotId
            WHERE binding.campaign_namespace=? AND binding.slot=?
            """,
            (campaign_namespace, slot),
        ).fetchone()
        if bound is not None and str(bound[1]) == pilot.name:
            pilot_id = str(bound[0])
            self._update_pilot(
                pilot_id, pilot, identity.kind, preserve_name=False
            )
        elif bound is not None:
            pilot_id = pilot.id
            self._insert_pilot(pilot, identity.kind)
        else:
            # Legacy ownership is established only by migration-seeded bindings.
            # An unbound runtime namespace/slot always starts a new career.
            pilot_id = pilot.id
            self._insert_pilot(pilot, identity.kind)

        cursor.execute(
            """
            INSERT INTO pilot_slot_bindings (
                campaign_namespace, slot, pilotId,
                dossier_digest, last_updated
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(campaign_namespace, slot) DO UPDATE SET
                pilotId=excluded.pilotId,
                dossier_digest=excluded.dossier_digest,
                last_updated=excluded.last_updated
            """,
            (
                campaign_namespace,
                slot,
                pilot_id,
                identity.dossier_digest,
                pilot.last_updated or datetime.now().isoformat(),
            ),
        )
        log.info("  Pilot persisted from verified Dossier identity.")
        return pilot_id

    def _upsert_slot_dependent_pilot(
        self, pilot: WoFFPilot, identity: PilotIdentityEvidence
    ) -> str:
        slot = self._validated_source_slot(pilot, identity, dossier=False)
        campaign_namespace = identity.campaign_namespace
        if campaign_namespace is None:
            raise PilotIdentityRejected("missing-campaign-namespace", slot)
        row = self._conn.execute(
            """
            SELECT p.id, binding.dossier_digest
            FROM pilot_slot_bindings AS binding
            JOIN pilots AS p ON p.id = binding.pilotId
            WHERE binding.campaign_namespace=? AND binding.slot=?
            """,
            (campaign_namespace, slot),
        ).fetchone()
        if row is None or row[1] is None:
            raise PilotIdentityUnavailable("missing-dossier-binding", slot)
        if str(row[1]) != identity.dossier_digest:
            raise PilotIdentityUnavailable("stale-dossier-binding", slot)
        pilot_id = str(row[0])
        self._update_pilot(
            pilot_id, pilot, identity.kind, preserve_name=True
        )
        log.info("  Pilot updated from verified slot-dependent identity.")
        return pilot_id

    @staticmethod
    def _validated_source_slot(
        pilot: WoFFPilot,
        identity: PilotIdentityEvidence,
        *,
        dossier: bool,
    ) -> int:
        slot = identity.slot
        actual_slot = pilot_slot(pilot.source_file)
        if slot is None or actual_slot != slot:
            raise PilotIdentityRejected("invalid-slot-source", slot)
        source_name = ntpath.basename(pilot.source_file.replace("/", "\\"))
        is_dossier = source_name.lower() == dossier_source_name(slot).lower()
        if dossier != is_dossier:
            raise PilotIdentityRejected("identity-source-kind-mismatch", slot)
        return slot

    @staticmethod
    def _status_value(
        pilot: WoFFPilot, identity_kind: PilotIdentityKind
    ) -> Optional[str]:
        """Return status only for a source authorized to replace stored state."""
        if identity_kind not in _STATUS_WRITABLE_BY or pilot.status is None:
            return None
        value = pilot.status.strip()
        return value or None

    def _insert_pilot(
        self, pilot: WoFFPilot, identity_kind: PilotIdentityKind
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO pilots (
                id, name, fName, sName, nation, rank, squadron,
                aircraft, aerodrome, sector, startDate, enlisted,
                status, notes, photo, birthDate, birthPlace, missions,
                flminutes, claimsCount, killsCount, skill, reputation,
                source_file, last_updated
            ) VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                COALESCE(?, 0), COALESCE(?, 0), COALESCE(?, 0),
                COALESCE(?, 0), COALESCE(?, 0), COALESCE(?, 0),
                ?,?
            )
            """,
            (
                pilot.id,
                pilot.name,
                pilot.fName,
                pilot.sName,
                pilot.nation,
                pilot.rank,
                pilot.squadron,
                pilot.aircraft,
                pilot.aerodrome,
                pilot.sector,
                pilot.startDate,
                pilot.enlisted,
                self._status_value(pilot, identity_kind),
                pilot.notes,
                pilot.photo,
                pilot.birthDate,
                pilot.birthPlace,
                pilot.missions,
                pilot.flminutes,
                pilot.claimsCount,
                pilot.killsCount,
                pilot.skill,
                pilot.reputation,
                pilot.source_file,
                pilot.last_updated,
            ),
        )

    def _update_pilot(
        self,
        pilot_id: str,
        pilot: WoFFPilot,
        identity_kind: PilotIdentityKind,
        *,
        preserve_name: bool,
    ) -> None:
        name = "" if preserve_name else pilot.name
        status = self._status_value(pilot, identity_kind)
        self._conn.execute(
            """
            UPDATE pilots SET
                name=COALESCE(NULLIF(?, ''), name),
                fName=COALESCE(NULLIF(?, ''), fName),
                sName=COALESCE(NULLIF(?, ''), sName),
                nation=COALESCE(NULLIF(?, ''), nation),
                rank=COALESCE(NULLIF(?, ''), rank),
                squadron=COALESCE(NULLIF(?, ''), squadron),
                aircraft=COALESCE(NULLIF(?, ''), aircraft),
                aerodrome=COALESCE(NULLIF(?, ''), aerodrome),
                sector=COALESCE(NULLIF(?, ''), sector),
                startDate=COALESCE(NULLIF(?, ''), startDate),
                enlisted=COALESCE(NULLIF(?, ''), enlisted),
                status=COALESCE(?, status),
                notes=COALESCE(NULLIF(?, ''), notes),
                photo=COALESCE(NULLIF(?, ''), photo),
                birthDate=COALESCE(NULLIF(?, ''), birthDate),
                birthPlace=COALESCE(NULLIF(?, ''), birthPlace),
                missions=COALESCE(?, missions),
                flminutes=COALESCE(?, flminutes),
                claimsCount=COALESCE(?, claimsCount),
                killsCount=COALESCE(?, killsCount),
                skill=COALESCE(?, skill),
                reputation=COALESCE(?, reputation),
                source_file=COALESCE(NULLIF(?, ''), source_file),
                last_updated=?
            WHERE id=?
            """,
            (
                name,
                pilot.fName,
                pilot.sName,
                pilot.nation,
                pilot.rank,
                pilot.squadron,
                pilot.aircraft,
                pilot.aerodrome,
                pilot.sector,
                pilot.startDate,
                pilot.enlisted,
                status,
                pilot.notes,
                pilot.photo,
                pilot.birthDate,
                pilot.birthPlace,
                pilot.missions,
                pilot.flminutes,
                pilot.claimsCount,
                pilot.killsCount,
                pilot.skill,
                pilot.reputation,
                pilot.source_file,
                pilot.last_updated,
                pilot_id,
            ),
        )

    def get_pilot_state(self, pilot_name: str) -> Tuple[Optional[str], Optional[str]]:
        """Return state only when a display name identifies one career."""
        pilot_id = self.resolve_pilot_id(pilot_name)
        if pilot_id is None:
            return None, None
        return self.get_pilot_state_by_id(pilot_id)

    def get_pilot_state_by_id(
        self, pilot_id: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Return status and rank for one explicit persistent career ID."""
        with self._lock:
            try:
                row = self._fetch_one(
                    "SELECT status, rank FROM pilots WHERE id = ?", (pilot_id,)
                )
                return (row[0], row[1]) if row else (None, None)
            except sqlite3.Error:
                log.exception("Erro ao buscar estado do piloto por ID")
                return None, None

    def resolve_bound_dossier_id(
        self, name: str, campaign_namespace: str, slot: int
    ) -> Optional[str]:
        """Resolve a Dossier only when the current slot binding has that name."""
        with self._lock:
            row = self._fetch_one(
                """
                SELECT p.id
                FROM pilot_slot_bindings AS binding
                JOIN pilots AS p ON p.id = binding.pilotId
                WHERE binding.campaign_namespace=?
                  AND binding.slot=? AND p.name=?
                """,
                (campaign_namespace, slot, name),
            )
            return str(row[0]) if row else None

    def resolve_pilot_id(
        self,
        name: str,
        source_file: Optional[str] = None,
        campaign_namespace: Optional[str] = None,
    ) -> Optional[str]:
        """Resolve a unique name or a placeholder through the current binding."""
        with self._lock:
            try:
                if source_file and _PLACEHOLDER_NAME.fullmatch(name):
                    slot = pilot_slot(source_file)
                    if slot is None or campaign_namespace is None:
                        return None
                    row = self._fetch_one(
                        "SELECT pilotId FROM pilot_slot_bindings "
                        "WHERE campaign_namespace=? AND slot=?",
                        (campaign_namespace, slot),
                    )
                    return str(row[0]) if row else None

                rows = self._fetch_all(
                    "SELECT id FROM pilots WHERE name = ? LIMIT 2", (name,)
                )
                return str(rows[0][0]) if len(rows) == 1 else None
            except sqlite3.Error:
                log.exception("Erro ao resolver pilot_id")
                return None

    def get_pilot_id_by_name(self, pilot_name: str) -> Optional[str]:
        """Return an ID only when the display name is unambiguous."""
        return self.resolve_pilot_id(pilot_name)

    def get_pilot_game_date(self, pilot_id: str) -> Optional[str]:
        """Return the latest real game date, or ``None`` when none is known."""
        with self._lock:
            try:
                rows = self._fetch_all(
                    "SELECT date FROM missions WHERE pilotId = ?",
                    (pilot_id,),
                )
                valid_dates = [
                    canonical
                    for row in rows
                    if (canonical := normalize_date(str(row[0] or "")))
                ]
                if valid_dates:
                    return max(valid_dates)

                row = self._fetch_one(
                    "SELECT startDate FROM pilots WHERE id = ?", (pilot_id,)
                )
                if not row:
                    return None
                start_date = normalize_date(str(row[0] or ""))
                return start_date or None
            except sqlite3.Error:
                log.exception("Erro ao buscar data do jogo")
                return None

    def get_mission_and_history(
        self, pilot_identifier: str, mission_id: str
    ) -> Tuple[
        Optional[Dict[str, Any]],
        Optional[Dict[str, Any]],
        List[Dict[str, Any]],
    ]:
        """Return one career, one exact mission, and its recent history."""
        with self._lock:
            conn = self._conn
            conn.row_factory = sqlite3.Row
            try:
                pilot = conn.execute(
                    "SELECT * FROM pilots WHERE id = ?", (pilot_identifier,)
                ).fetchone()
                if pilot is None:
                    candidates = conn.execute(
                        "SELECT * FROM pilots WHERE name = ? LIMIT 2",
                        (pilot_identifier,),
                    ).fetchall()
                    if len(candidates) != 1:
                        return None, None, []
                    pilot = candidates[0]

                current_mission = conn.execute(
                    "SELECT * FROM missions WHERE id = ? AND pilotId = ?",
                    (mission_id, pilot["id"]),
                ).fetchone()
                if not current_mission:
                    return dict(pilot), None, []

                history_rows = conn.execute(
                    """
                    SELECT * FROM missions WHERE pilotId = ?
                    """,
                    (pilot["id"],),
                ).fetchall()

                current = dict(current_mission)
                canonical_current = canonicalized_mission_mapping(current)
                if canonical_current is not None:
                    current = canonical_current[1]

                ordered_history = []
                for mission in history_rows:
                    canonical = canonicalized_mission_mapping(dict(mission))
                    if canonical is not None:
                        ordered_history.append(canonical)
                ordered_history.sort(key=lambda item: item[0], reverse=True)
                return (
                    dict(pilot),
                    current,
                    [mission for _, mission in ordered_history[:10]],
                )
            except sqlite3.Error:
                log.exception("Erro ao buscar missão/histórico")
                return None, None, []
            finally:
                conn.row_factory = None
