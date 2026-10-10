#!/usr/bin/env python3
"""
Motor de Campanha (campaign_engine.py)
══════════════════════════════════════════════════════════════════
Orquestra a Fase 2 e 3. Lê a Base de Dados, chama o RPGSystem e 
o NarrativeGenerator, e guarda os resultados.
══════════════════════════════════════════════════════════════════
"""
import logging
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from .database import DatabaseManager, DossierState, DossierWingmanState
from .identity import PilotIdentityEvidence, PilotIdentityKind
from .rpg_system import rpg_system
from .narrative_generator import narrative_generator
from .models import WoFFDecoration, WoFFPilot, WoFFWingman
from .normalization import normalize_date

log = logging.getLogger("WoFFWatch")

_RosterAction = Literal["keep", "baseline", "pending-baseline", "candidate"]


class _DiaryWriteRejected(Exception):
    pass


class _DossierWriteRejected(Exception):
    pass


class CampaignEngine:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def process_mission_end(
        self,
        pilot_id: str,
        mission_id: str,
        *,
        replace_existing_diary: bool = False,
    ):
        log.info(f"[RPG] A processar fim de missão para o piloto {pilot_id}...")

        db_result = self.db_manager.get_mission_and_history(pilot_id, mission_id)

        if not db_result or not isinstance(db_result, tuple) or len(db_result) != 3:
            log.error(
                "DatabaseManager.get_mission_and_history retornou um formato inesperado. "
                "Abortando RPG."
            )
            return

        pilot_dict, current_mission, m_list = db_result

        if not pilot_dict or not current_mission:
            log.warning(
                f"Missão {mission_id} não encontrada na DB para o piloto {pilot_id}. "
                "A abortar processamento RPG."
            )
            return

        mission_date = normalize_date(str(current_mission.get("date", "")))
        if not mission_date:
            log.warning(
                "Mission-derived state rejected: category=invalid-game-date"
            )
            return False
        current_mission = dict(current_mission)
        current_mission["date"] = mission_date

        real_pilot_id = pilot_dict["id"]

        fatigue = rpg_system.calculate_fatigue(m_list)
        morale = rpg_system.calculate_morale(
            m_list, pilot_dict.get("status")
        )
        stress = rpg_system.calculate_stress(m_list)

        narrative = narrative_generator.generate(
            pilot_dict["name"], current_mission
        )
        if not narrative:
            return False

        entry_date = mission_date

        try:
            with self.db_manager.transaction():
                self.db_manager.update_pilot_rpg_stats(
                    real_pilot_id, fatigue, morale, stress
                )
                if not self.db_manager.save_diary_entry(
                    pilot_id=real_pilot_id,
                    mission_id=mission_id,
                    entry_date=entry_date,
                    narrative=narrative,
                    replace_existing=replace_existing_diary,
                ):
                    raise _DiaryWriteRejected
        except _DiaryWriteRejected:
            return False

        log.info(
            f"  ✓ RPG Atualizado: Fadiga={fatigue} | Moral={morale} | Stress={stress}"
        )
        return True

    @staticmethod
    def _roster_map(
        wingmen: Sequence[DossierWingmanState],
    ) -> Dict[str, DossierWingmanState]:
        members: Dict[str, DossierWingmanState] = {}
        for wingman in wingmen:
            if not wingman.wingman_id or wingman.wingman_id in members:
                raise _DossierWriteRejected("unresolved-roster-identity")
            members[wingman.wingman_id] = wingman
        return members

    @staticmethod
    def _wingman_events(
        old_map: Dict[str, DossierWingmanState],
        new_map: Dict[str, DossierWingmanState],
    ) -> List[Tuple[str, DossierWingmanState]]:
        events: List[Tuple[str, DossierWingmanState]] = []
        for member_id in sorted(old_map):
            previous = old_map[member_id]
            current = new_map.get(member_id)
            if current is not None:
                if previous.status != current.status:
                    normalized = current.status.lower()
                    if "wound" in normalized or "hospital" in normalized:
                        events.append(("wounded", current))
                    elif "kia" in normalized or "dead" in normalized:
                        events.append(("kia", current))
            else:
                events.append(("missing", previous))

        for member_id in sorted(new_map.keys() - old_map.keys()):
            events.append(("new", new_map[member_id]))
        return events

    @staticmethod
    def _is_roster_transfer(stored: DossierState, pilot: WoFFPilot) -> bool:
        # Roster metadata wins, including an explicitly unknown squadron.
        # Only databases without any roster metadata use the legacy pilot row.
        previous_squadron = stored.roster_squadron
        if not previous_squadron and not stored.roster_metadata_present:
            previous_squadron = stored.squadron
        return bool(
            previous_squadron
            and pilot.squadron
            and previous_squadron != pilot.squadron
        )

    def _plan_dossier_diary_effects(
        self,
        stored: DossierState,
        pilot: WoFFPilot,
        wingmen: Sequence[DossierWingmanState],
        *,
        roster_complete: bool = True,
    ) -> Tuple[List[Tuple[str, str]], bool, _RosterAction]:
        """Derive effects from resolved IDs before committing the Dossier transaction."""
        effects: List[Tuple[str, str]] = []
        transfer = self._is_roster_transfer(stored, pilot)
        roster_action: _RosterAction = "keep"
        roster_events: List[Tuple[str, DossierWingmanState]] = []

        if not roster_complete:
            # Detailed Dossier slots are only a subset of the active squadron.
            # Save a pending baseline; never infer new/missing/transfer events
            # from a difference between incomplete lists.
            roster_action = "pending-baseline"
        elif transfer:
            roster_action = "baseline" if wingmen else "pending-baseline"
        elif wingmen:
            # An untrusted legacy list has no comparison identity. Establish a
            # fresh baseline without attributing historical events to its names.
            # A trusted legacy baseline/candidate must instead fail closed.
            untrusted_legacy = (
                stored.roster_baseline_pending
                and not stored.roster_squadron
                and any(w.wingman_id is None for w in stored.wingmen)
            )
            old_map = self._roster_map(() if untrusted_legacy else stored.wingmen)
            new_map = self._roster_map(wingmen)
            all_events = self._wingman_events(old_map, new_map)

            if not pilot.squadron:
                roster_action = "pending-baseline"
                roster_events = [
                    event for event in all_events if event[0] in {"wounded", "kia"}
                ]
            elif stored.roster_baseline_pending or not stored.roster_squadron:
                roster_action = "baseline"
                roster_events = [
                    event for event in all_events if event[0] in {"wounded", "kia"}
                ]
            else:
                candidate = stored.roster_candidate
                candidate_map = (
                    self._roster_map(candidate.wingmen) if candidate is not None else {}
                )
                candidate_matches = bool(
                    candidate is not None
                    and candidate.squadron == pilot.squadron
                    and {key: value.status for key, value in candidate_map.items()}
                    == {key: value.status for key, value in new_map.items()}
                )
                has_unconfirmed_absence = bool(old_map.keys() - new_map.keys())
                if has_unconfirmed_absence and not candidate_matches:
                    roster_action = "candidate"
                else:
                    roster_action = "baseline"
                    roster_events = all_events

        for event_type, member in roster_events:
            name = f"{member.first_name} {member.last_name}".strip()
            narrative = narrative_generator.generate_wingman_event(name, event_type)
            if narrative:
                effects.append((f"wingman:{event_type}", narrative))

        status_changed = (
            pilot.status is not None
            and stored.status is not None
            and stored.status != pilot.status
        )
        rank_changed = bool(pilot.rank) and (stored.rank or "") != pilot.rank
        if status_changed or rank_changed:
            event_status = pilot.status if status_changed else stored.status
            narrative = narrative_generator.generate_life_event(
                event_status,
                stored.status,
                pilot.rank,
                stored.rank,
            )
            if narrative:
                effects.append(("life", narrative))
        return effects, transfer, roster_action

    def process_dossier_import(
        self,
        pilot: WoFFPilot,
        decorations: List[WoFFDecoration],
        wingmen: List[WoFFWingman],
        identity: PilotIdentityEvidence,
        *,
        roster_complete: bool = True,
    ) -> Optional[str]:
        """Persist one Dossier generation and all derived diary effects atomically."""
        if (
            identity.kind is not PilotIdentityKind.DOSSIER
            or identity.slot is None
            or identity.campaign_namespace is None
        ):
            raise ValueError("Dossier import requires verified Dossier identity")

        effects: List[Tuple[str, str]] = []
        transferred = False
        replayed = False
        roster_action: _RosterAction = (
            "baseline"
            if roster_complete and pilot.squadron and wingmen
            else "pending-baseline" if pilot.squadron or wingmen else "keep"
        )
        real_pilot_id: Optional[str] = None
        try:
            with self.db_manager.transaction():
                stored = self.db_manager.load_dossier_state(
                    pilot.name,
                    identity.campaign_namespace,
                    identity.slot,
                )
                if (
                    stored is not None
                    and stored.dossier_digest == identity.dossier_digest
                ):
                    real_pilot_id = stored.pilot_id
                    replayed = True
                else:
                    event_date: Optional[str] = None
                    if stored is not None:
                        event_date = self.db_manager.get_pilot_game_date(
                            stored.pilot_id
                        ) or normalize_date(pilot.startDate)

                    retired_ids = stored.retired_wingman_ids if stored else frozenset()
                    if (
                        roster_complete
                        and stored is not None
                        and self._is_roster_transfer(stored, pilot)
                    ):
                        # An explicit boundary retires only evidence-less historical
                        # candidates, never their rows or personality/memory links.
                        # Persist the scope even when the new baseline is pending.
                        retired_ids |= self.db_manager.identityless_wingman_ids(
                            stored.pilot_id
                        )
                    real_pilot_id = self.db_manager.merge_and_write(
                        pilot=pilot,
                        missions=[],
                        victories=[],
                        decorations=decorations,
                        wingmen=wingmen,
                        identity=identity,
                        retired_wingman_ids=retired_ids,
                    )
                    if not real_pilot_id:
                        raise _DossierWriteRejected("core-write")
                    if stored is not None and real_pilot_id != stored.pilot_id:
                        raise RuntimeError(
                            "Dossier identity changed inside one transaction"
                        )
                    resolved_roster = self.db_manager.load_resolved_dossier_roster(
                        real_pilot_id, wingmen
                    )
                    if stored is not None:
                        effects, transferred, roster_action = (
                            self._plan_dossier_diary_effects(
                                stored, pilot, resolved_roster,
                                roster_complete=roster_complete,
                            )
                        )
                        if effects and not event_date:
                            raise _DossierWriteRejected("missing-game-date")
                    if roster_action == "candidate":
                        if stored is None:
                            raise RuntimeError(
                                "Roster candidate requires persisted trusted state"
                            )
                        self.db_manager.save_dossier_roster_candidate(
                            real_pilot_id,
                            stored.roster_squadron,
                            stored.wingmen,
                            pilot.squadron,
                            resolved_roster,
                            retired_wingman_ids=retired_ids,
                        )
                    elif roster_action in {"baseline", "pending-baseline"}:
                        self.db_manager.save_dossier_roster_state(
                            real_pilot_id,
                            pilot.squadron,
                            resolved_roster,
                            baseline_pending=(roster_action == "pending-baseline"),
                            retired_wingman_ids=retired_ids,
                        )

                    for _category, narrative in effects:
                        if not self.db_manager.save_diary_entry(
                            pilot_id=real_pilot_id,
                            mission_id=None,
                            entry_date=event_date or "",
                            narrative=narrative,
                        ):
                            raise _DossierWriteRejected("diary-write")
        except _DossierWriteRejected as error:
            log.warning("Dossier import rejected: category=%s", error)
            return None

        if real_pilot_id is None:
            return None
        if replayed:
            log.info("Dossier generation already applied for verified career.")
            return real_pilot_id
        if transferred:
            log.info(
                "Dossier squadron transfer persisted without roster absence events."
            )
        if effects:
            log.info(
                "Dossier import committed with %d derived diary event(s).",
                len(effects),
            )
        return real_pilot_id

    def process_life_events(
        self, pilot_id: str, new_status: Optional[str], new_rank: str,
        old_status: Optional[str], old_rank: Optional[str],
        event_date: Optional[str] = None
    ):
        """Chamado quando o Dossier é atualizado. Verifica mudanças de status/rank."""
        narrative = narrative_generator.generate_life_event(
            new_status, old_status, new_rank, old_rank
        )

        if not narrative:
            return

        log.info("[RPG] Evento de vida detetado para carreira verificada.")

        today = (
            normalize_date(event_date)
            if event_date is not None
            else self.db_manager.get_pilot_game_date(pilot_id)
        )
        if not today:
            log.warning("Life event rejected: category=missing-game-date")
            return False

        saved = self.db_manager.save_diary_entry(
            pilot_id=pilot_id,
            mission_id=None,
            entry_date=today,
            narrative=narrative
        )
        if not saved:
            return False
        log.info("  📝 Diário de Bordo atualizado com Evento de Vida.")
        return True

    def process_wingmen_changes(
        self,
        pilot_id: str,
        new_wingmen: List[WoFFWingman],
        event_date: Optional[str] = None,
    ):
        """
        Compara os wingmen recém-extraídos com os guardados na DB.
        Gera entradas de diário para mortes, ferimentos e chegadas.
        """
        log.info("[RPG] A verificar mudanças nos wingmen da carreira verificada...")

        if not new_wingmen:
            log.warning(
                "  Lista de wingmen vazia. Abortando comparação para evitar "
                "falsos positivos."
            )
            return

        # Parsed Dossier IDs are generation-local until the atomic import
        # resolves them. This compatibility entry point accepts explicit IDs only.
        if any(
            w.present_fields is not None or w.pilotId != pilot_id for w in new_wingmen
        ):
            log.warning("Wingman events rejected: category=unresolved-roster-identity")
            return False
        old_wingmen = self.db_manager.get_wingmen_with_identity_by_pilot(pilot_id)
        try:
            old_map = self._roster_map(
                tuple(
                    DossierWingmanState(
                        str(w["fName"] or ""),
                        str(w["sName"] or ""),
                        str(w["status"] or ""),
                        wingman_id=str(w["id"]),
                    )
                    for w in old_wingmen
                )
            )
            new_map = self._roster_map(
                tuple(
                    DossierWingmanState(w.fName, w.sName, w.status, wingman_id=w.id)
                    for w in new_wingmen
                )
            )
        except _DossierWriteRejected:
            return False
        events = self._wingman_events(old_map, new_map)

        if not events:
            return True

        today = (
            normalize_date(event_date)
            if event_date is not None
            else self.db_manager.get_pilot_game_date(pilot_id)
        )
        if not today:
            log.warning("Wingman events rejected: category=missing-game-date")
            return False

        for event_type, member in events:
            name = f"{member.first_name} {member.last_name}".strip()
            narrative = narrative_generator.generate_wingman_event(name, event_type)
            if narrative:
                self.db_manager.save_diary_entry(pilot_id, None, today, narrative)
                log.info(f"  📝 Evento de Wingman registado: {name} ({event_type})")
        return True
