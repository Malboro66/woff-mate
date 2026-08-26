#!/usr/bin/env python3
"""
WoFF BHaH II Watchdog v3.2
══════════════════════════════════════════════════════════════════
Monitoriza os ficheiros de campanha do Wings over Flanders Fields:
Between Heaven and Hell II e exporta dados de missões e pilotos
em SQLite compatível com a aplicação WoFFBase.

Melhorias v3.2 (Correção de Integração):
- RPG e Diário de Missão agora usam o pilot_id real (resolve "Pilot 1").
- Eventos de Vida e Wingmen usam a data do jogo (imersão histórica).
- Wingmen: aborta comparação se lista vazia (evita spam "missing").
- Dossier: normaliza nação e datas de nascimento.
- Sincronização inicial usa resolve_pilot_id com source_file para garantir
  resolução correta de placeholders "Pilot X" → UUID real.

Modos de uso:
  Normal:       python -m woff.woff_watchdog
  Debug:        python -m woff.woff_watchdog --parse-file "caminho/para/ficheiro.txt"
  Descoberta:   python -m woff.woff_watchdog --discover
  Ajuda:        python -m woff.woff_watchdog --help
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os
import sys
import glob
import argparse
import logging
import threading
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional, List, Any, TextIO

# ──────────────────────────────────────────────────────────────
# VERIFICAÇÃO DE DEPENDÊNCIAS E MÓDULOS
# ──────────────────────────────────────────────────────────────
try:
    from watchdog.observers import Observer
except ImportError:
    print(
        "\n[ERRO] Falha ao carregar a biblioteca 'watchdog'.\n"
        "Para corrigir, executa no terminal:\n"
        "  pip install watchdog\n",
        file=sys.stderr,
    )
    sys.exit(1)
except Exception as e:
    print(
        f"\n[ERRO] Ocorreu um erro inesperado: {type(e).__name__} - {e}\n"
        "Verifica a tua instalação do Python e do pacote 'watchdog'.",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from .campaign_namespace import (
        campaign_namespace_for_root,
        campaign_namespace_label,
    )
    from .command_contract import ExitCode
    from .config import InvalidConfigurationError, WatchdogConfig, load_config
    from .handler import WoFFEventHandler
    from .database import DatabaseManager
    from .discovery import DiscoveryLogger
    from .medal_cataloger import catalog_medals
    from .squadron_cataloger import catalog_squadrons
    from .campaign_engine import CampaignEngine
    from .version import __version__

    # Importar os Parsers para a ferramenta de debug e leitura inicial
    from .parsers.xml_parser import WoFFXMLParser
    from .parsers.mission_log_parser import WoFFMissionLogParser
    from .parsers.pilot_data_parser import WoFFPilotDataParser
    from .parsers.dossier_parser import WoFFDossierParser
except ImportError as e:
    print(
        f"\n[ERRO] Falha ao carregar módulos internos: {type(e).__name__} - {e}\n"
        "Certifica-te que todos os ficheiros do projeto estão na pasta correta.\n"
        "Se o problema persistir, reinstala as dependências:\n"
        "  pip install watchdog pywin32\n",
        file=sys.stderr,
    )
    sys.exit(1)
except Exception as e:
    print(
        f"\n[ERRO] Ocorreu um erro ao carregar os módulos: {type(e).__name__} - {e}",
        file=sys.stderr,
    )
    sys.exit(1)

# ──────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────
LOG_FORMAT = "[%(asctime)s] %(levelname)-8s  %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%H:%M:%S")
log = logging.getLogger("WoFFWatch")


# ──────────────────────────────────────────────────────────────
# ORQUESTRADOR PRINCIPAL
# ──────────────────────────────────────────────────────────────

class WoFFWatchdog:
    """
    Classe principal que gere o ciclo de vida do watchdog.
    """

    def __init__(
        self, config: WatchdogConfig, discovery: bool = False, pilot_id: str = ""
    ):
        config.validate()
        self.config = config
        export_existed = Path(config.export_path).is_file()
        self.db_manager = DatabaseManager(
            config.export_path, campaign_namespaces=config.campaign_namespaces
        )
        try:
            if config.backup_export and export_existed:
                self.db_manager.create_export_backup()
        except Exception:
            self.db_manager.close()
            raise
        self.discovery = (
            DiscoveryLogger(config.discovery_log_path) if discovery else None
        )
        self.pilot_id = pilot_id
        self.observers: List[Any] = []
        self._handler: Optional[WoFFEventHandler] = None
        self._stop_event = threading.Event()

    def start(self) -> bool:
        """Inicia a monitorização das pastas configuradas e cataloga dados estáticos do jogo."""
        paths = self.config.watch_paths
        valid = [p for p in paths if os.path.isdir(p)]
        missing = [p for p in paths if not os.path.isdir(p)]

        for p in valid:
            log.info(
                "  ✓ Monitorizar namespace: %s",
                campaign_namespace_label(campaign_namespace_for_root(p)),
            )
        for p in missing:
            log.warning(
                "  ✗ Namespace não encontrado: %s",
                campaign_namespace_label(campaign_namespace_for_root(p)),
            )

        if not valid:
            log.error(
                "\nNenhum caminho válido encontrado!\n"
                "Edita o config.json com os caminhos correctos.\n"
            )
            self.db_manager.close()
            return False

        # Establish live observation before cataloging or baseline reconciliation,
        # so changes during startup enter the same bounded/coalesced scheduler.
        try:
            self.campaign_engine = CampaignEngine(self.db_manager)
            self._handler = WoFFEventHandler(
                self.config, self.db_manager, self.campaign_engine, self.discovery
            )
            for path in valid:
                obs = Observer()
                obs.schedule(self._handler, path, recursive=True)
                self.observers.append(obs)
                obs.start()

        # Procurar as pastas 'Medals' e 'Scratchpad' em todos os caminhos válidos
            medals_path = None
            scratchpad_path = None
            for path in valid:
                if not medals_path and os.path.exists(os.path.join(path, "Medals")):
                    medals_path = os.path.join(path, "Medals")
                if not medals_path and os.path.exists(
                    os.path.join(os.path.dirname(path), "Medals")
                ):
                    medals_path = os.path.join(os.path.dirname(path), "Medals")

                if not scratchpad_path and os.path.exists(
                    os.path.join(path, "Scratchpad")
                ):
                    scratchpad_path = os.path.join(path, "Scratchpad")
                if not scratchpad_path and os.path.exists(
                    os.path.join(os.path.dirname(path), "Scratchpad")
                ):
                    scratchpad_path = os.path.join(os.path.dirname(path), "Scratchpad")

            if medals_path:
                catalog_medals(medals_path, self.config.export_path)
            if scratchpad_path:
                catalog_squadrons(scratchpad_path, self.config.export_path)

        # ──────────────────────────────────────────────────────────────
        # SINCRONIZAÇÃO INICIAL DE TODOS OS PILOTOS
        # ──────────────────────────────────────────────────────────────
            file_patterns = []
            if ".txt" in self.config.watched_extensions:
                log.info("A sincronizar dados iniciais dos pilotos...")
                file_patterns = [
                    "Pilot*Dossier.txt",
                    "Pilot*Log.txt",
                    "Pilot*Claims.txt",
                    "Pilot*Squads.txt",
                ]

            for file_pattern in file_patterns:
                phase_files = []
                for path in valid:
                    phase_files.extend(glob.glob(os.path.join(path, file_pattern)))
                for file_path in phase_files:
                    if not self._handler.submit_initial(file_path):
                        raise RuntimeError(
                            "bounded startup admission failed for "
                            f"{os.path.basename(file_path)}"
                        )
                if phase_files:
                    phase_timeout = self._handler.startup_phase_timeout(
                        len(phase_files)
                    )
                    if not self._handler.wait_initial(
                        phase_files, phase_timeout
                    ):
                        raise RuntimeError(
                            "bounded startup reconciliation failed for "
                            f"{file_pattern}"
                        )
        except Exception:
            self._cleanup(suppress_errors=True)
            raise

        log.info(f"\nWatchdog activo — {len(valid)} caminho(s) em monitorização")
        log.info(f"Base de Dados: {self.config.export_path}")
        if self.discovery:
            log.info(f"Discovery log: {self.config.discovery_log_path}")
        log.info("Pressiona Ctrl+C para parar.\n")
        return True

    def run_forever(self):
        """Mantém o programa a correr até ser interrompido (Ctrl+C)."""
        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        """Encerra todos os observers e threads de forma graciosa."""
        log.info("A parar watchdog...")
        self._cleanup(suppress_errors=False)
        log.info("Watchdog parado.")

    def _cleanup(self, *, suppress_errors: bool) -> None:
        """Release every owned resource, optionally preserving a startup error."""
        self._stop_event.set()
        cleanup_actions = (
            *(lambda obs=obs: obs.stop() for obs in self.observers),
            *(lambda obs=obs: obs.join(timeout=5) for obs in self.observers),
            *(() if self._handler is None else (self._handler.shutdown,)),
            self.db_manager.close,
        )
        first_error = None
        for action in cleanup_actions:
            try:
                action()
            except Exception as error:
                log.exception("Watchdog resource cleanup failed")
                if first_error is None:
                    first_error = error
        if first_error is not None and not suppress_errors:
            raise first_error


# ──────────────────────────────────────────────────────────────
# MODO DEBUG --parse-file
# ──────────────────────────────────────────────────────────────

def run_parse_file(file_path: str) -> int:
    """Parse one supported file and return a stable process-level status."""
    sep = "═" * 60
    log.info(f"\n{sep}")
    log.info(f"🎯 MODO DEBUG --parse-file: {file_path}")
    log.info(sep)

    if not os.path.isfile(file_path):
        log.error(f"Ficheiro não encontrado: {file_path}")
        return int(ExitCode.USAGE_ERROR)

    ext = os.path.splitext(file_path)[1].lower()
    fname = os.path.basename(file_path).lower()

    if ext == ".xml":
        parser = WoFFXMLParser()
        if not parser.parse(file_path):
            log.error("Parser não encontrou dados válidos.")
            return int(ExitCode.RUNTIME_ERROR)
        log.info(f"Piloto: {parser.pilot.name if parser.pilot else 'N/A'}")
        log.info(
            f"Missões: {len(parser.missions)} | "
            f"Vitórias: {len(parser.victories)}"
        )
        return int(ExitCode.SUCCESS)

    if ext == ".txt" and fnmatch(fname, "pilot*dossier.txt"):
        log.info("\n--- 🗄️ A DESOFUSCAR DOSSIER BINÁRIO ---")
        parser = WoFFDossierParser()
        if not parser.parse(file_path):
            log.error("Parser não encontrou dados válidos.")
            return int(ExitCode.RUNTIME_ERROR)
        if parser.pilot:
            log.info("\n--- 🧑‍✈️ DADOS DO PILOTO ---")
            log.info(f"Nome: {parser.pilot.name}")
            log.info(
                f"Patente: {parser.pilot.rank} | Nação: {parser.pilot.nation}"
            )
            log.info(
                f"Esquadrão: {parser.pilot.squadron} | "
                f"Base: {parser.pilot.aerodrome}"
            )
            log.info(
                f"Status: {parser.pilot.status} | Skill: {parser.pilot.skill}"
            )
            log.info(
                f"Missões: {parser.pilot.missions} | "
                f"Minutos Voo: {parser.pilot.flminutes}"
            )
            log.info(
                f"Vitórias: {parser.pilot.killsCount} | "
                f"Reputação: {parser.pilot.reputation}"
            )
            log.info(
                f"Data Nasc.: {parser.pilot.birthDate} "
                f"({parser.pilot.birthPlace})"
            )
            log.info(f"Foto ID: {parser.pilot.photo}")
            log.info(f"Biografia: {parser.pilot.notes[:150]}...")
        if parser.decorations:
            log.info("\n--- 🎖️ MEDALHAS RECEBIDAS ---")
            for decoration in parser.decorations:
                log.info(f"  -> {decoration.name} ({decoration.date})")
        if parser.wingmen:
            log.info("\n--- 👥 MEMBROS DO ESQUADRÃO (AI) ---")
            for wingman in parser.wingmen:
                log.info(
                    f"  -> {wingman.rank} {wingman.fName} {wingman.sName} "
                    f"(Skill: {wingman.skill}, Status: {wingman.status})"
                )
                if wingman.bio:
                    log.info(f"     Bio: {wingman.bio[:80]}...")
        return int(ExitCode.SUCCESS)

    if ext == ".log" and fname == "mission.log":
        parser = WoFFMissionLogParser()
        if not parser.parse(file_path):
            log.error("Parser não encontrou dados válidos.")
            return int(ExitCode.RUNTIME_ERROR)
        log.info("\n--- 📜 BRIEFING DA MISSÃO ---")
        log.info(parser.briefing[:300] + "..." if len(parser.briefing) > 300 else parser.briefing)
        log.info("\n--- 🛩️ DADOS DA MISSÃO ---")
        mission = parser.mission
        if mission:
            log.info(f"Data: {mission.date} | Tempo: {mission.weather}")
            log.info(f"Aeronave do Jogador: {mission.aircraft}")
            if parser.pilot:
                log.info(
                    f"Esquadrão: {parser.pilot.squadron} "
                    f"({parser.pilot.nation})"
                )
        log.info("\n--- 👥 MEMBROS DO ESQUADRÃO (Flight) ---")
        for member in parser.squad_members:
            log.info(member)
        log.info("\n--- 🗺️ PLANO DE VOO ---")
        for waypoint in parser.flight_plan:
            log.info(
                f"  -> {waypoint['type']} | Alt: {waypoint['altitude']}m | "
                f"Lat: {waypoint['lat']} | Lon: {waypoint['lon']}"
            )
        log.info("\n--- 📝 DEBRIEFING ---")
        log.info(parser.debriefing or "Sem debriefing textual encontrado.")
        return int(ExitCode.SUCCESS)

    pilot_patterns = ("pilot*log.txt", "pilot*claims.txt", "pilot*squads.txt")
    if ext == ".txt" and any(fnmatch(fname, pattern) for pattern in pilot_patterns):
        parser = WoFFPilotDataParser()
        parsed = parser.parse(file_path)
        if not parser.is_complete or (
            not parsed and not parser.valid_empty
        ):
            log.error("Parser não encontrou dados válidos.")
            return int(ExitCode.RUNTIME_ERROR)
        if parser.pilot:
            log.info("\n--- 🧑‍✈️ DADOS DO PILOTO ---")
            log.info(f"Nome (ID): {parser.pilot.name}")
            log.info(f"Esquadrão: {parser.pilot.squadron}")
            log.info(f"Aeronave Atual: {parser.pilot.aircraft}")
            log.info(f"Base: {parser.pilot.aerodrome}")
            log.info(f"Patente: {parser.pilot.rank}")
        log.info(f"\nMissões extraídas do log: {len(parser.missions)}")
        for mission in parser.missions[:3]:
            log.info(
                f"  -> [{mission.date}] {mission.missionType} ({mission.aircraft})"
            )
        log.info(f"\nVitórias extraídas: {len(parser.victories)}")
        for victory in parser.victories[:3]:
            log.info(
                f"  -> [{victory.date}] {victory.enemyType} ({victory.victoryType})"
            )
        return int(ExitCode.SUCCESS)

    log.error(f"Ficheiro não suportado para parse: {os.path.basename(file_path)}")
    return int(ExitCode.USAGE_ERROR)


# ──────────────────────────────────────────────────────────────
# PONTO DE ENTRADA
# ──────────────────────────────────────────────────────────────

BANNER = r"""
╔════════════════════════════════════════════════════════════╗
║      ✈  WoFF BHaH II — Watchdog  v{version:<19}✈     ║
║   Wings over Flanders Fields · SQLite Companion Sync       ║
╚════════════════════════════════════════════════════════════╝
""".format(version=__version__)


def _print_banner(stream: Optional[TextIO] = None) -> None:
    """Write the banner without failing on legacy Windows console encodings."""
    destination = stream if stream is not None else sys.stdout
    encoding = getattr(destination, "encoding", None) or "utf-8"
    try:
        printable_banner = BANNER.encode(encoding, errors="replace").decode(encoding)
    except LookupError:
        printable_banner = BANNER.encode("ascii", errors="replace").decode("ascii")
    print(printable_banner, file=destination)


def main(argv: Optional[List[str]] = None) -> int:
    """Ponto de entrada da aplicação."""
    ap = argparse.ArgumentParser(
        description="WoFF BHaH II Watchdog — sincroniza campanha com WoFFBase",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Exemplos:
  python -m woff.woff_watchdog                            Monitorização normal
  python -m woff.woff_watchdog --parse-file "A:\\...\\Pilot1Dossier.txt"  Testa um ficheiro
  python -m woff.woff_watchdog --discover                 Regista todos os ficheiros detectados
  python -m woff.woff_watchdog --verbose                  Log detalhado (DEBUG)
""",
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument(
        "--config",
        default="config.json",
        help="Caminho para config.json (padrão: config.json)",
    )
    ap.add_argument(
        "--discover",
        action="store_true",
        help="Modo descoberta: regista todos os ficheiros detectados",
    )
    ap.add_argument(
        "--parse-file",
        default="",
        help="Testa a extração de um ficheiro específico sem iniciar o watchdog",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="Log detalhado (DEBUG)",
    )
    args = ap.parse_args(argv)

    _print_banner()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        cfg = load_config(args.config)
    except InvalidConfigurationError as error:
        log.error("Configuração inválida: %s", error)
        return int(ExitCode.USAGE_ERROR)
    logging.getLogger().setLevel(
        logging.DEBUG if args.verbose else getattr(logging, cfg.log_level)
    )

    # Modo Debug de ficheiro único
    if args.parse_file:
        try:
            return run_parse_file(args.parse_file)
        except Exception as error:
            log.error("Falha ao processar ficheiro: %s", error)
            return int(ExitCode.RUNTIME_ERROR)

    if not any(os.path.isdir(path) for path in cfg.watch_paths):
        log.error(
            "\nNenhum caminho válido encontrado!\n"
            "Edita o config.json com os caminhos correctos.\n"
        )
        return int(ExitCode.USAGE_ERROR)

    # Inicializa o orquestrador
    try:
        dog = WoFFWatchdog(cfg, discovery=args.discover, pilot_id="")
        if not dog.start():
            return int(ExitCode.RUNTIME_ERROR)
        dog.run_forever()
    except Exception as error:
        log.error("Falha ao iniciar ou executar o watchdog: %s", error)
        return int(ExitCode.RUNTIME_ERROR)
    return int(ExitCode.SUCCESS)


if __name__ == "__main__":
    raise SystemExit(main())
