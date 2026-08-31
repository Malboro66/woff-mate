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
    resolve_legacy_mission_substring_alias,
    resolve_victory_alias,
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
    updated_mission_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RecordMergeCounts:
    """Observable outcomes for victory or decoration source records."""

    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    unresolved: int = 0


_VICTORY_COLUMNS = (
    "id",
    "pilotId",
    "date",
    "time",
    "missionId",
    "enemyType",
    "victoryType",
    "location",
    "confirmed",
    "witnesses",
    "notes",
    "sector",
    "aircraft",
    "source_file",
)
_VICTORY_TEXT_FIELDS = (
    "date",
    "time",
    "enemyType",
    "victoryType",
    "location",
    "witnesses",
    "notes",
    "sector",
    "aircraft",
)
_VICTORY_MATCH_FIELDS = (
    "victoryType",
    "location",
    "witnesses",
    "notes",
    "sector",
    "aircraft",
)
_SOURCE_RECORD_KEY = re.compile(
    r"source-v1:([0-9a-f]{64}):[0-9a-f]{64}\Z"
)
_LEGACY_UNKNOWN_VICTORY_TYPE = "Out of Control (OOC)"


def record_source_priority(source_file: object) -> int:
    """Return authority shared by victory and decoration merge policies."""
    filename = ntpath.basename(str(source_file or "").replace("/", "\\")).lower()
    if filename == "mission.log":
        return 40
    if filename.endswith(".xml"):
        return 30
    if re.fullmatch(r"pilot\d+(?:claims|dossier)\.txt", filename):
        return 20
    return 0


def _same_source(left: object, right: object) -> bool:
    left_name = ntpath.basename(str(left or "").replace("/", "\\")).casefold()
    right_name = ntpath.basename(str(right or "").replace("/", "\\")).casefold()
    return bool(left_name) and left_name == right_name


def _source_identity_from_record_key(source_record_key: object) -> str:
    match = _SOURCE_RECORD_KEY.fullmatch(str(source_record_key or "").strip())
    return match.group(1) if match is not None else ""


def _victory_identity_key(
    raw_date: object,
    raw_time: object,
    enemy_type: object,
) -> Optional[Tuple[str, str, str]]:
    raw_date_value = str(raw_date or "").strip()
    raw_time_value = str(raw_time or "").strip()
    canonical_date = normalize_date(raw_date_value)
    canonical_time = normalize_time(raw_time_value)
    if raw_date_value and not canonical_date:
        return None
    if raw_time_value and not canonical_time:
        return None
    return canonical_date, canonical_time, str(enemy_type or "").strip()


def _victory_row(cursor: sqlite3.Cursor, victory_id: str) -> Optional[Dict[str, Any]]:
    row = cursor.execute(
        f"SELECT {', '.join(_VICTORY_COLUMNS)} FROM victories WHERE id=?",
        (victory_id,),
    ).fetchone()
    if row is None:
        return None
    return {field: value for field, value in zip(_VICTORY_COLUMNS, row)}


def _victory_match_score(
    stored: Dict[str, Any],
    incoming: WoFFVictory,
    *,
    allow_legacy_victory_type: bool = False,
) -> Optional[int]:
    """Return enrichment confidence, or ``None`` for distinct evidence."""
    stored_identity = _victory_identity_key(
        stored.get("date"), stored.get("time"), stored.get("enemyType")
    )
    incoming_identity = _victory_identity_key(
        incoming.date, incoming.time, incoming.enemyType
    )
    if stored_identity is None or incoming_identity is None:
        return None
    score = 0
    for stored_value, incoming_value in zip(
        stored_identity, incoming_identity
    ):
        if not stored_value or not incoming_value:
            continue
        if stored_value != incoming_value:
            return None
        score += 1
    stored_mission = str(stored.get("missionId") or "").strip()
    incoming_mission = str(incoming.missionId or "").strip()
    if stored_mission and incoming_mission and stored_mission != incoming_mission:
        return None
    if stored_mission and incoming_mission:
        score += 1
    for field in _VICTORY_MATCH_FIELDS:
        stored_value = str(stored.get(field) or "").strip()
        incoming_value = str(getattr(incoming, field) or "").strip()
        if not stored_value or not incoming_value:
            continue
        if stored_value != incoming_value:
            if field == "victoryType" and allow_legacy_victory_type:
                continue
            return None
        score += 1
    if bool(stored.get("confirmed")) and incoming.confirmed:
        score += 1
    return score if score > 0 else None


def _is_legacy_unknown_victory_replay(
    stored: Dict[str, Any],
    incoming: WoFFVictory,
    *,
    has_source_records: bool,
) -> bool:
    """Identify the narrow replay affected by the historical OOC fallback."""
    incoming_type = str(incoming.victoryType or "").strip()
    incoming_source_key = str(incoming.source_record_key or "").strip()
    return (
        _SOURCE_RECORD_KEY.fullmatch(incoming_source_key) is not None
        and str(stored.get("victoryType") or "").strip()
        == _LEGACY_UNKNOWN_VICTORY_TYPE
        and bool(incoming_type)
        and incoming_type != _LEGACY_UNKNOWN_VICTORY_TYPE
        and resolve_victory_alias(incoming_type) is None
        and _same_source(stored.get("source_file"), incoming.source_file)
        and not has_source_records
    )


def _victory_merge_updates(
    stored: Dict[str, Any], incoming: WoFFVictory
) -> Tuple[Dict[str, Any], bool]:
    """Return safe field updates and whether equal-authority data conflicted."""
    updates: Dict[str, Any] = {}
    conflict = False
    stored_source = str(stored.get("source_file") or "").strip()
    incoming_source = str(incoming.source_file or "").strip()
    stored_priority = record_source_priority(stored_source)
    incoming_priority = record_source_priority(incoming_source)

    for field in _VICTORY_TEXT_FIELDS:
        stored_value = str(stored.get(field) or "").strip()
        incoming_value = str(getattr(incoming, field) or "").strip()
        if not incoming_value or incoming_value == stored_value:
            continue
        if not stored_value:
            updates[field] = incoming_value
        elif (
            incoming_priority > stored_priority
            or _same_source(stored_source, incoming_source)
        ):
            updates[field] = incoming_value
        elif incoming_priority == stored_priority:
            conflict = True

    stored_mission = str(stored.get("missionId") or "").strip()
    incoming_mission = str(incoming.missionId or "").strip()
    if incoming_mission and not stored_mission:
        updates["missionId"] = incoming_mission
    elif (
        incoming_mission
        and stored_mission
        and incoming_mission != stored_mission
    ):
        conflict = True

    if incoming.confirmed and not bool(stored.get("confirmed")):
        updates["confirmed"] = 1
    if incoming_source and (
        not stored_source or incoming_priority > stored_priority
    ):
        updates["source_file"] = incoming_source
    return updates, conflict


def _decoration_merge_updates(
    stored: Dict[str, Any], incoming: WoFFDecoration
) -> Tuple[Dict[str, Any], bool]:
    updates: Dict[str, Any] = {}
    conflict = False
    stored_source = str(stored.get("source_file") or "").strip()
    incoming_source = str(incoming.source_file or "").strip()
    stored_priority = record_source_priority(stored_source)
    incoming_priority = record_source_priority(incoming_source)
    for field in ("date", "citation"):
        stored_value = str(stored.get(field) or "").strip()
        incoming_value = str(getattr(incoming, field) or "").strip()
        if not incoming_value or incoming_value == stored_value:
            continue
        if not stored_value:
            updates[field] = incoming_value
        elif (
            incoming_priority > stored_priority
            or _same_source(stored_source, incoming_source)
        ):
            updates[field] = incoming_value
        elif incoming_priority == stored_priority:
            conflict = True
    if incoming_source and (
        not stored_source or incoming_priority > stored_priority
    ):
        updates["source_file"] = incoming_source
    return updates, conflict


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


def _legacy_mission_alias_candidate(
    cursor: sqlite3.Cursor,
    pilot_id: str,
    incoming_identity: MissionIdentityKey,
    incoming_raw_type: object,
    incoming_source: object,
) -> Optional[str]:
    """Resolve one same-source row changed by the historical matcher."""
    raw_type = str(incoming_raw_type or "").strip() or incoming_identity[2]
    legacy_type = resolve_legacy_mission_substring_alias(raw_type)
    if legacy_type is None or legacy_type == incoming_identity[2]:
        return None
    legacy_identity = (
        incoming_identity[0],
        incoming_identity[1],
        legacy_type,
        incoming_identity[3],
    )
    candidates: List[str] = []
    for row in cursor.execute(
        """
        SELECT id, date, time, missionType, aircraft, source_file
        FROM missions
        WHERE pilotId=? AND missionType=? AND aircraft=?
        """,
        (pilot_id, legacy_type, incoming_identity[3]),
    ).fetchall():
        if mission_identity_key(row[1], row[2], row[3], row[4]) != legacy_identity:
            continue
        if not _same_source(row[5], incoming_source):
            continue
        candidates.append(str(row[0]))
    return candidates[0] if len(candidates) == 1 else None


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

    @staticmethod
    def _attach_victory_alias(
        cursor: sqlite3.Cursor,
        pilot_id: str,
        source_record_key: str,
        victory_id: str,
    ) -> None:
        if not source_record_key:
            return
        cursor.execute(
            """
            INSERT OR IGNORE INTO victory_source_records (
                pilotId, source_record_key, victoryId
            ) VALUES (?, ?, ?)
            """,
            (pilot_id, source_record_key, victory_id),
        )
        mapped = cursor.execute(
            """
            SELECT victoryId FROM victory_source_records
            WHERE pilotId=? AND source_record_key=?
            """,
            (pilot_id, source_record_key),
        ).fetchone()
        if mapped != (victory_id,):
            raise sqlite3.IntegrityError("victory source identity collision")

    @staticmethod
    def _resolve_victory_mission(
        cursor: sqlite3.Cursor,
        pilot_id: str,
        victory: WoFFVictory,
    ) -> Tuple[str, bool]:
        """Resolve only explicit or unambiguous positive-claim associations."""
        explicit = str(victory.missionId or "").strip()
        if explicit:
            owner = cursor.execute(
                "SELECT pilotId FROM missions WHERE id=?", (explicit,)
            ).fetchone()
            if owner != (pilot_id,):
                log.warning(
                    "Victory quarantined at write boundary: "
                    "category=invalid-parent-mission"
                )
                return "", True
            return explicit, False

        if not victory.date:
            return "", False
        candidates: List[Tuple[str, str]] = []
        for mission_id, raw_date, raw_time, raw_claims in cursor.execute(
            """
            SELECT id, date, time, claimsCount
            FROM missions WHERE pilotId=?
            """,
            (pilot_id,),
        ).fetchall():
            if int(raw_claims or 0) <= 0:
                continue
            canonical_date = normalize_date(str(raw_date or ""))
            if canonical_date != victory.date:
                continue
            raw_time_value = str(raw_time or "").strip()
            canonical_time = normalize_time(raw_time_value)
            if raw_time_value and not canonical_time:
                continue
            if victory.time and canonical_time and canonical_time > victory.time:
                continue
            candidates.append((str(mission_id), canonical_time))
        if len(candidates) == 1:
            return candidates[0][0], False
        if len(candidates) > 1:
            log.warning(
                "Victory association unresolved: category=ambiguous-mission"
            )
        return "", False

    @staticmethod
    def _select_victory_candidate(
        cursor: sqlite3.Cursor,
        pilot_id: str,
        incoming: WoFFVictory,
    ) -> Tuple[Optional[str], bool]:
        identity = _victory_identity_key(
            incoming.date, incoming.time, incoming.enemyType
        )
        if identity is None:
            return None, False
        compatible: List[Tuple[int, str]] = []
        for row in cursor.execute(
            f"SELECT {', '.join(_VICTORY_COLUMNS)} "
            "FROM victories WHERE pilotId=?",
            (pilot_id,),
        ).fetchall():
            stored = {
                field: value for field, value in zip(_VICTORY_COLUMNS, row)
            }
            incoming_source_identity = _source_identity_from_record_key(
                incoming.source_record_key
            )
            source_record_rows = cursor.execute(
                """
                SELECT source_record_key FROM victory_source_records
                WHERE victoryId=?
                """,
                (str(stored["id"]),),
            ).fetchall()
            stored_source_identities = {
                _source_identity_from_record_key(row[0])
                for row in source_record_rows
            }
            if (
                incoming_source_identity
                and incoming_source_identity in stored_source_identities
            ):
                # A new verified position in the same source is a distinct
                # occurrence even when every visible field is identical.
                continue
            score = _victory_match_score(
                stored,
                incoming,
                allow_legacy_victory_type=_is_legacy_unknown_victory_replay(
                    stored,
                    incoming,
                    has_source_records=bool(source_record_rows),
                ),
            )
            if score is not None:
                compatible.append((score, str(stored["id"])))
        if not compatible:
            return None, False
        best_score = max(score for score, _victory_id in compatible)
        winners = [
            victory_id
            for score, victory_id in compatible
            if score == best_score
        ]
        if len(winners) == 1:
            return winners[0], False
        return None, True

    @staticmethod
    def _log_claim_consistency(
        cursor: sqlite3.Cursor,
        mission_ids: set[str],
    ) -> None:
        for mission_id in mission_ids:
            row = cursor.execute(
                "SELECT claimsCount FROM missions WHERE id=?", (mission_id,)
            ).fetchone()
            if row is None:
                continue
            claims_count = int(row[0] or 0)
            associated = int(
                cursor.execute(
                    "SELECT COUNT(*) FROM victories WHERE missionId=?",
                    (mission_id,),
                ).fetchone()[0]
            )
            if claims_count > 0 and associated != claims_count:
                log.warning(
                    "Victory claim consistency: category=count-mismatch "
                    "claims=%d associated=%d",
                    claims_count,
                    associated,
                )

    def _merge_victory_records(
        self,
        cursor: sqlite3.Cursor,
        pilot_id: str,
        victories: List[WoFFVictory],
        mission_id_remap: Dict[str, str],
        rejected_mission_ids: set[str],
        changed_mission_ids: set[str],
    ) -> RecordMergeCounts:
        inserted = updated = unchanged = unresolved = 0
        associated_missions = set(changed_mission_ids)
        for victory in victories:
            victory.pilotId = pilot_id
            if victory.missionId and victory.missionId in rejected_mission_ids:
                log.warning(
                    "Victory quarantined at write boundary: "
                    "category=rejected-parent-mission"
                )
                unresolved += 1
                continue
            victory.missionId = mission_id_remap.get(
                victory.missionId, victory.missionId
            )
            raw_date = str(victory.date or "").strip()
            raw_time = str(victory.time or "").strip()
            identity = _victory_identity_key(
                raw_date, raw_time, victory.enemyType
            )
            if identity is None:
                category = (
                    "invalid-date"
                    if raw_date and not normalize_date(raw_date)
                    else "invalid-time"
                )
                log.warning(
                    "Victory quarantined at write boundary: category=%s",
                    category,
                )
                unresolved += 1
                continue
            victory.date, victory.time, victory.enemyType = identity
            if not str(victory.id or "").strip():
                log.warning(
                    "Victory quarantined at write boundary: category=missing-id"
                )
                unresolved += 1
                continue
            source_record_key = str(victory.source_record_key or "").strip()
            if source_record_key and not _SOURCE_RECORD_KEY.fullmatch(
                source_record_key
            ):
                log.warning(
                    "Victory quarantined at write boundary: "
                    "category=invalid-source-identity"
                )
                unresolved += 1
                continue

            # Validate an explicit parent before identity matching, but defer
            # inference until the stored occurrence (if any) is known.  A
            # replay that omits missionId must retain an existing relationship.
            if victory.missionId:
                resolved_mission, invalid_mission = self._resolve_victory_mission(
                    cursor, pilot_id, victory
                )
                if invalid_mission:
                    unresolved += 1
                    continue
                victory.missionId = resolved_mission

            target_id: Optional[str] = None
            if source_record_key:
                alias = cursor.execute(
                    """
                    SELECT victoryId FROM victory_source_records
                    WHERE pilotId=? AND source_record_key=?
                    """,
                    (pilot_id, source_record_key),
                ).fetchone()
                if alias is not None:
                    target_id = str(alias[0])

            id_row = _victory_row(cursor, str(victory.id))
            if target_id is None and id_row is not None:
                if str(id_row.get("pilotId") or "") != pilot_id:
                    log.warning(
                        "Victory merge unresolved: category=id-conflict"
                    )
                    unresolved += 1
                    continue
                target_id = str(victory.id)

            if target_id is None:
                target_id, ambiguous = self._select_victory_candidate(
                    cursor, pilot_id, victory
                )
                if ambiguous:
                    log.warning(
                        "Victory merge unresolved: "
                        "category=ambiguous-occurrence"
                    )
                    unresolved += 1
                    continue

            stored: Optional[Dict[str, Any]] = None
            if target_id is not None:
                stored = _victory_row(cursor, target_id)
                if stored is None or str(stored.get("pilotId") or "") != pilot_id:
                    raise sqlite3.IntegrityError(
                        "victory source identity points outside its pilot"
                    )
                stored_mission = str(stored.get("missionId") or "").strip()
                if not victory.missionId and stored_mission:
                    victory.missionId = stored_mission

            if not victory.missionId:
                resolved_mission, invalid_mission = self._resolve_victory_mission(
                    cursor, pilot_id, victory
                )
                if invalid_mission:
                    unresolved += 1
                    continue
                victory.missionId = resolved_mission
            if victory.missionId:
                associated_missions.add(victory.missionId)

            if stored is not None:
                if target_id is None:
                    raise sqlite3.IntegrityError(
                        "resolved victory identity disappeared"
                    )
                updates, conflict = _victory_merge_updates(stored, victory)
                if conflict:
                    log.warning(
                        "Victory merge unresolved: "
                        "category=equal-authority-conflict"
                    )
                    unresolved += 1
                    continue
                if updates:
                    assignments = ", ".join(
                        f"{field}=?" for field in updates
                    )
                    cursor.execute(
                        f"UPDATE victories SET {assignments} WHERE id=?",
                        (*updates.values(), target_id),
                    )
                    updated += 1
                else:
                    unchanged += 1
                self._attach_victory_alias(
                    cursor, pilot_id, source_record_key, target_id
                )
                continue

            cursor.execute(
                """
                INSERT INTO victories (
                    id, pilotId, date, time, missionId, enemyType, victoryType,
                    location, confirmed, witnesses, notes, sector, aircraft,
                    source_file
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    victory.id,
                    victory.pilotId,
                    victory.date,
                    victory.time,
                    victory.missionId,
                    victory.enemyType,
                    victory.victoryType,
                    victory.location,
                    victory.confirmed,
                    victory.witnesses,
                    victory.notes,
                    victory.sector,
                    victory.aircraft,
                    victory.source_file,
                ),
            )
            self._attach_victory_alias(
                cursor, pilot_id, source_record_key, str(victory.id)
            )
            inserted += 1

        self._log_claim_consistency(cursor, associated_missions)
        return RecordMergeCounts(inserted, updated, unchanged, unresolved)

    @staticmethod
    def _merge_decoration_records(
        cursor: sqlite3.Cursor,
        pilot_id: str,
        decorations: List[WoFFDecoration],
    ) -> RecordMergeCounts:
        inserted = updated = unchanged = unresolved = 0
        for decoration in decorations:
            decoration.pilotId = pilot_id
            decoration.id = str(decoration.id or "").strip()
            decoration.name = str(decoration.name or "").strip()
            raw_date = str(decoration.date or "").strip()
            if raw_date:
                decoration.date = normalize_date(raw_date)
                if not decoration.date:
                    log.warning(
                        "Decoration merge unresolved: category=invalid-date"
                    )
                    unresolved += 1
                    continue
            if not decoration.id or not decoration.name:
                log.warning(
                    "Decoration merge unresolved: category=missing-identity"
                )
                unresolved += 1
                continue

            id_row = cursor.execute(
                "SELECT pilotId, name FROM decorations WHERE id=?",
                (decoration.id,),
            ).fetchone()
            if id_row is not None and id_row != (pilot_id, decoration.name):
                log.warning(
                    "Decoration merge unresolved: category=id-conflict"
                )
                unresolved += 1
                continue
            row = cursor.execute(
                """
                SELECT id, date, citation, source_file
                FROM decorations WHERE pilotId=? AND name=?
                """,
                (pilot_id, decoration.name),
            ).fetchone()
            if row is None:
                cursor.execute(
                    """
                    INSERT INTO decorations (
                        id, pilotId, name, date, citation, source_file
                    ) VALUES (?,?,?,?,?,?)
                    """,
                    (
                        decoration.id,
                        pilot_id,
                        decoration.name,
                        decoration.date,
                        decoration.citation,
                        decoration.source_file,
                    ),
                )
                inserted += 1
                continue

            stored = {
                "id": row[0],
                "date": row[1],
                "citation": row[2],
                "source_file": row[3],
            }
            updates, conflict = _decoration_merge_updates(stored, decoration)
            if conflict:
                log.warning(
                    "Decoration merge unresolved: "
                    "category=equal-authority-conflict"
                )
                unresolved += 1
                continue
            if updates:
                assignments = ", ".join(f"{field}=?" for field in updates)
                cursor.execute(
                    f"UPDATE decorations SET {assignments} WHERE id=?",
                    (*updates.values(), str(row[0])),
                )
                updated += 1
            else:
                unchanged += 1
        return RecordMergeCounts(inserted, updated, unchanged, unresolved)

    def upsert_mission(
        self,
        pilot_id: str,
        missions: List[WoFFMission],
        victories: List[WoFFVictory],
        decorations: List[WoFFDecoration],
    ) -> Tuple[MissionMergeCounts, RecordMergeCounts, RecordMergeCounts]:
        """Merge missions, victories, and decorations for one pilot."""
        cursor = self._conn.cursor()
        identity_index: Optional[Dict[MissionIdentityKey, str]] = None
        mission_id_remap: Dict[str, str] = {}
        rejected_mission_ids: set[str] = set()
        changed_mission_ids: set[str] = set()
        updated_mission_ids: set[str] = set()
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
                    changed_mission_ids.add(stored_mission_id)
                    updated_mission_ids.add(stored_mission_id)
                else:
                    unchanged_m += 1
                continue
            legacy_mission_id = _legacy_mission_alias_candidate(
                cursor,
                pilot_id,
                identity,
                m.rawMissionType,
                m.source_file,
            )
            if legacy_mission_id is not None:
                if m.id and m.id != legacy_mission_id:
                    mission_id_remap[m.id] = legacy_mission_id
                cursor.execute(
                    "UPDATE missions SET missionType=? WHERE id=?",
                    (identity[2], legacy_mission_id),
                )
                _merge_existing_mission(cursor, legacy_mission_id, m)
                updated_m += 1
                changed_mission_ids.add(legacy_mission_id)
                updated_mission_ids.add(legacy_mission_id)
                identity_index = stored_mission_identity_index(cursor, pilot_id)
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
            changed_mission_ids.add(str(m.id))

        victory_counts = self._merge_victory_records(
            cursor,
            pilot_id,
            victories,
            mission_id_remap,
            rejected_mission_ids,
            changed_mission_ids,
        )
        decoration_counts = self._merge_decoration_records(
            cursor, pilot_id, decorations
        )

        return (
            MissionMergeCounts(
                inserted_m,
                updated_m,
                unchanged_m,
                frozenset(updated_mission_ids),
            ),
            victory_counts,
            decoration_counts,
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
