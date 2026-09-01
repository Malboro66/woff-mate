#!/usr/bin/env python3
"""
Motor de Campanha (campaign_engine.py)
══════════════════════════════════════════════════════════════════
Orquestra a Fase 2 e 3. Lê a Base de Dados, chama o RPGSystem e 
o NarrativeGenerator, e guarda os resultados.
══════════════════════════════════════════════════════════════════
"""
import logging
from typing import Dict, List, Literal, Optional, Tuple

from .database import DatabaseManager, DossierState
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
    def _wingman_events(
        old_map: Dict[str, str], new_map: Dict[str, str]
    ) -> List[Tuple[str, str]]:
        events: List[Tuple[str, str]] = []
        for name in sorted(old_map):
            old_status = old_map[name]
            if name in new_map:
                new_status = new_map[name]
                if old_status != new_status:
                    normalized = new_status.lower()
                    if "wound" in normalized or "hospital" in normalized:
                        events.append(("wounded", name))
                    elif "kia" in normalized or "dead" in normalized:
                        events.append(("kia", name))
            else:
                events.append(("missing", name))

        for name in sorted(new_map):
            if name not in old_map:
                events.append(("new", name))
        return events

    def _plan_dossier_diary_effects(
        self,
        stored: DossierState,
        pilot: WoFFPilot,
        wingmen: List[WoFFWingman],
    ) -> Tuple[List[Tuple[str, str]], bool, _RosterAction]:
        """Compute deterministic narratives before any Dossier write occurs."""
        effects: List[Tuple[str, str]] = []
        transfer = bool(
            stored.roster_squadron
            and pilot.squadron
            and stored.roster_squadron != pilot.squadron
        )
        roster_action: _RosterAction = "keep"
        roster_events: List[Tuple[str, str]] = []

        if transfer:
            roster_action = "baseline" if wingmen else "pending-baseline"
        elif wingmen:
            old_map = {
                f"{wingman.first_name} {wingman.last_name}".strip(): wingman.status
                for wingman in stored.wingmen
            }
            new_map = {
                f"{wingman.fName} {wingman.sName}".strip(): wingman.status
                for wingman in wingmen
            }
            all_events = self._wingman_events(old_map, new_map)

            if not pilot.squadron:
                roster_action = "pending-baseline"
                roster_events = [
                    event
                    for event in all_events
                    if event[0] in {"wounded", "kia"}
                ]
            elif stored.roster_baseline_pending or not stored.roster_squadron:
                roster_action = "baseline"
                roster_events = [
                    event
                    for event in all_events
                    if event[0] in {"wounded", "kia"}
                ]
            else:
                candidate = stored.roster_candidate
                candidate_map = (
                    {
                        f"{wingman.first_name} {wingman.last_name}".strip(): (
                            wingman.status
                        )
                        for wingman in candidate.wingmen
                    }
                    if candidate is not None
                    else {}
                )
                candidate_matches = bool(
                    candidate is not None
                    and candidate.squadron == pilot.squadron
                    and candidate_map == new_map
                )
                has_unconfirmed_absence = bool(old_map.keys() - new_map.keys())
                if has_unconfirmed_absence and not candidate_matches:
                    roster_action = "candidate"
                else:
                    roster_action = "baseline"
                    roster_events = all_events

        for event_type, name in roster_events:
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
            if pilot.squadron and wingmen
            else "pending-baseline"
            if pilot.squadron or wingmen
            else "keep"
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
                        (
                            effects,
                            transferred,
                            roster_action,
                        ) = self._plan_dossier_diary_effects(stored, pilot, wingmen)
                        event_date = self.db_manager.get_pilot_game_date(
                            stored.pilot_id
                        ) or normalize_date(pilot.startDate)
                        if effects and not event_date:
                            raise _DossierWriteRejected("missing-game-date")

                    real_pilot_id = self.db_manager.merge_and_write(
                        pilot=pilot,
                        missions=[],
                        victories=[],
                        decorations=decorations,
                        wingmen=wingmen,
                        identity=identity,
                    )
                    if not real_pilot_id:
                        raise _DossierWriteRejected("core-write")
                    if stored is not None and real_pilot_id != stored.pilot_id:
                        raise RuntimeError(
                            "Dossier identity changed inside one transaction"
                        )
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
                            wingmen,
                        )
                    elif roster_action in {"baseline", "pending-baseline"}:
                        self.db_manager.save_dossier_roster_state(
                            real_pilot_id,
                            pilot.squadron,
                            wingmen,
                            baseline_pending=(
                                roster_action == "pending-baseline"
                            ),
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
        self, pilot_id: str, new_wingmen: List[WoFFWingman],
        event_date: Optional[str] = None
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

        old_wingmen = self.db_manager.get_wingmen_by_pilot(pilot_id)

        old_map = {f"{w['fName']} {w['sName']}": w['status'] for w in old_wingmen}
        new_map = {f"{w.fName} {w.sName}": w.status for w in new_wingmen}

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

        for event_type, name in events:
            narrative = narrative_generator.generate_wingman_event(name, event_type)
            if narrative:
                self.db_manager.save_diary_entry(
                    pilot_id, None, today, narrative
                )
                log.info(
                    f"  📝 Evento de Wingman registado: {name} ({event_type})"
                )
        return True
