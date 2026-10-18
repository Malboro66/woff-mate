#!/usr/bin/env python3
"""
Parser de Logs de Missão (parsers/mission_log_parser.py)
══════════════════════════════════════════════════════════════════
Extrai dados ricos do ficheiro de log gerado pelo WoFF durante o voo.
Lê o bloco XML <Mission> no início do ficheiro e o log textual no final.
══════════════════════════════════════════════════════════════════
"""

import os
import logging
import xml.etree.ElementTree as ET
from xml.parsers import expat
from typing import Optional, List, Dict, Any
from ..models import WoFFMission, WoFFPilot
from ..nation import normalize_nation_evidence
from ..normalization import (
    normalize_coordinates,
    normalize_date,
    normalize_time,
)

log = logging.getLogger("WoFFWatch")

class _MissionRootClosed(Exception):
    """Internal sentinel: stop Expat exactly after the XML document root."""


def _split_mission_document(content: str) -> tuple[str, str]:
    """Return real Mission XML and trailing debrief using Expat's element stack.

    Expat validates comments, CDATA, nested elements and root attributes. Its
    byte index points to the actual root end tag, not a lookalike in text.
    We stop at that event because the WoFF debrief is deliberately not XML.

    DTDs and custom/external entities are not part of the supported WoFF
    format and must be rejected before ElementTree materializes content.
    """
    document = content.encode("utf-8")
    # The legacy decoder has already converted source bytes to Unicode;
    # the normalized UTF-8 buffer must not be reinterpreted by an XML
    # declaration naming another source encoding.
    parser = expat.ParserCreate(encoding="utf-8")
    depth = 0
    root_end: Optional[int] = None

    def start_element(name: str, _attributes: Dict[str, str]) -> None:
        nonlocal depth
        if depth == 0 and name != "Mission":
            raise ValueError("expected Mission root element")
        depth += 1

    def end_element(_name: str) -> None:
        nonlocal depth, root_end
        depth -= 1
        if depth == 0:
            index = parser.CurrentByteIndex
            if document[index : index + 2] == b"</":
                # Expat has already established this as the real closing tag.
                # End tags contain no quoted attributes or embedded markup.
                terminator = document.find(b">", index)
                if terminator < 0:
                    raise ValueError("incomplete Mission closing tag")
                root_end = terminator + 1
            else:
                # Expat reports the end of a self-closing root after "/>".
                root_end = index
            raise _MissionRootClosed

    def reject_doctype(*_arguments: object) -> None:
        raise ValueError("DTD and entity declarations are not supported")

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.StartDoctypeDeclHandler = reject_doctype
    parser.EntityDeclHandler = reject_doctype
    parser.ExternalEntityRefHandler = reject_doctype

    try:
        parser.Parse(document, True)
    except _MissionRootClosed:
        pass

    if root_end is None:
        raise ValueError("incomplete Mission root")
    return document[:root_end].decode("utf-8"), document[root_end:].decode("utf-8")


class WoFFMissionLogParser:
    def __init__(self):
        self.mission: Optional[WoFFMission] = None
        self.pilot: Optional[WoFFPilot] = None
        self.briefing: str = ""
        self.debriefing: str = ""
        self.squad_members: List[str] = []
        # FIX: Atualizar a tipagem para aceitar dicionários (usado na Fase 3 para mapas)
        self.flight_plan: List[Dict[str, Any]] = []

    def parse(self, path: str) -> bool:
        log.info(f"[LOG] Analisando Log de Missão: {os.path.basename(path)}")
        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception as e:
            log.error(f"  Falha ao ler {path}: {e}")
            return False
        return self.parse_bytes(data, os.path.basename(path))

    def parse_bytes(self, data: bytes, source_name: str) -> bool:
        """Parse verified bytes without reopening their source path."""
        log.info(f"[LOG] Analisando snapshot: {source_name}")
        self.mission = None
        self.pilot = None
        self.briefing = ""
        self.debriefing = ""
        self.squad_members = []
        self.flight_plan = []
        content = data.decode("utf-8", errors="replace")

        # 1. Extract the validated root boundary, not a textual closing-tag
        # match that may appear inside a comment or CDATA section.
        try:
            xml_str, text_after_xml = _split_mission_document(content)
            root = ET.fromstring(xml_str)
        except (expat.ExpatError, ET.ParseError, ValueError) as error:
            log.error("  Invalid Mission XML document: %s", error)
            return False
        if root.tag != "Mission":
            log.warning("  Unsupported Mission XML root.")
            return False

        # 2. Extrair Parâmetros e Briefing
        params = root.find("Params")
        if params is None:
            log.warning("  Tag <Params> não encontrada no XML do log. Abortando parse.")
            return False
            
        date_str = params.get("Date", "")  # Formato confirmado: 9/20/1915
        time_str = params.get("Time", "")
        canonical_date = normalize_date(date_str, numeric_order="month-first")
        canonical_time = normalize_time(time_str)
        if not canonical_date:
            log.warning(
                "[LOG] Mission record rejected: source=%s category=invalid-date",
                os.path.basename(source_name),
            )
            return False
        if time_str.strip() and not canonical_time:
            log.warning(
                "[LOG] Mission record rejected: source=%s category=invalid-time",
                os.path.basename(source_name),
            )
            return False

        self.mission = WoFFMission(
            date=canonical_date,
            time=canonical_time,
            source_file=os.path.basename(source_name),
        )
        
        self.mission.weather = params.get("Weather", "Unknown").replace("OFFDynamicMissionWeather.xml", "Dynamic")

        overview = root.find("Overview")
        if overview is not None and overview.text:
            self.briefing = overview.text.strip()

        # 3. Encontrar a formação do jogador e membros do esquadrão
        # FIX: Inicializar player_unit como None para evitar 'possibly unbound'
        player_unit: Optional[ET.Element] = None
        for formation in root.findall("AirFormation"):
            for unit in formation.findall("Unit"):
                if unit.get("IsPlayer") == "y":
                    player_unit = unit
                    break

            # Se encontramos a unidade do jogador nesta formação
            if player_unit is not None:
                self.pilot = WoFFPilot()
                self.pilot.nation = normalize_nation_evidence(
                    formation.get("Country", "")
                )
                self.pilot.squadron = formation.get("SquadName", "")
                
                if self.mission:
                    self.mission.sector = self.pilot.squadron
                    self.mission.aircraft = player_unit.get("Type", "")
                    
                # Extrai membros do esquadrão (AI)
                for u in formation.findall("Unit"):
                    ac_type = u.get("Type", "")
                    fname = u.get("PilotFirstName", "")
                    lname = u.get("PilotLastName", "")
                    role = "Player" if u.get("IsPlayer") == "y" else "Wingman"
                    if fname:
                        self.squad_members.append(f"{role}: {fname} {lname} ({ac_type})")
                    else:
                        self.squad_members.append(f"{role}: [Player] ({ac_type})")
                    
                # Extrai Plano de Voo (Waypoints) com Coordenadas Decimais
                route = formation.find("Route")
                if route is not None:
                    for wp in route.findall("Waypoint"):
                        wp_type = wp.get("Type", "")
                        alt = wp.get("Alt", "0")
                        lat_raw = wp.get("Lat", "")
                        lon_raw = wp.get("Lon", "")
                        
                        # Converte as coordenadas para decimal
                        lat_dec = normalize_coordinates(lat_raw)
                        lon_dec = normalize_coordinates(lon_raw)
                        
                        # Guarda como dicionário para a Fase 3 (Mapas)
                        self.flight_plan.append({
                            "type": wp_type,
                            "altitude": alt,
                            "lat": lat_dec,
                            "lon": lon_dec,
                            "raw_lat": lat_raw,
                            "raw_lon": lon_raw
                        })
                break # Já processámos a formação do jogador, podemos sair do ciclo

        # 4. Extrair Debriefing do texto pós-XML
        
        if "forced landing on friendly field" in text_after_xml.lower():
            self.debriefing = "Forced landing on friendly field"
            if self.mission: self.mission.result = "Force-Landed (Friendly Lines)"
        elif "MissionEnded" in text_after_xml:
            self.debriefing = "Mission Ended Successfully"
            if self.mission: self.mission.result = "Completed"
            
        return True
