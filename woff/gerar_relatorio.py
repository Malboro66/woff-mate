#!/usr/bin/env python3
"""Generate an extraction report from one explicitly selected configuration."""

from __future__ import annotations

import argparse
import logging
import os
import tempfile
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Optional, TextIO, cast

from .command_contract import ExitCode
from .config import InvalidConfigurationError, load_config
from .parsers.dossier_parser import WoFFDossierParser
from .parsers.mission_log_parser import WoFFMissionLogParser
from .parsers.pilot_data_parser import WoFFPilotDataParser

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("ReportGen")

OUTPUT_FILE = "woff_data_report.txt"
PILOT_DOSSIER_PATTERN = "pilot*dossier.txt"
PILOT_TEXT_PATTERNS = (
    "pilot*log.txt",
    "pilot*claims.txt",
    "pilot*squads.txt",
)
SUPPORTED_PILOT_PATTERNS = (PILOT_DOSSIER_PATTERN, *PILOT_TEXT_PATTERNS)


class ReportGenerationError(RuntimeError):
    """Raised when a selected source exists but cannot be parsed."""


def _display_value(value: object) -> object:
    """Preserve valid falsey values while labelling actually missing fields."""

    return "Vazio" if value is None or value == "" else value


def _write_report(report: TextIO, valid_paths: list[str]) -> None:
    pilot_files: list[str] = []
    mission_log_path: Optional[str] = None

    for path in valid_paths:
        pilot_files.extend(
            str(entry)
            for entry in Path(path).iterdir()
            if entry.is_file()
            and any(
                fnmatchcase(entry.name.lower(), pattern)
                for pattern in SUPPORTED_PILOT_PATTERNS
            )
        )
        potential_log = os.path.join(path, "mission.log")
        if os.path.isfile(potential_log):
            mission_log_path = potential_log

    report.write("═" * 60 + "\n")
    report.write("RELATÓRIO DE EXTRAÇÃO DE DADOS - WoFF BHaH II Watchdog\n")
    report.write("═" * 60 + "\n\n")

    for pilot_file in sorted(pilot_files):
        filename = os.path.basename(pilot_file).lower()

        if fnmatchcase(filename, PILOT_DOSSIER_PATTERN):
            report.write(
                f"📦 FONTE: {filename} (Ficheiro Binário Encriptado)\n"
            )
            report.write("-" * 60 + "\n")
            parser = WoFFDossierParser()
            if not parser.parse(pilot_file):
                raise ReportGenerationError(
                    f"Falha ao processar o dossier {filename}."
                )
            pilot = parser.pilot
            if pilot:
                data = [
                    ("Nome Completo", pilot.name, "Índices 4, 5"),
                    ("Nação", pilot.nation, "Mapeamento Dinâmico"),
                    ("Patente", pilot.rank, "Índice 3"),
                    ("Status RPG", pilot.status, "Mapeamento Dinâmico"),
                    ("Data de Nascimento", pilot.birthDate, "Mapeamento Dinâmico"),
                    ("Local de Nascimento", pilot.birthPlace, "Índice 92"),
                    ("Foto ID", pilot.photo, "Índice 100"),
                    ("Esquadrão Atual", pilot.squadron, "Índice 83"),
                    ("Aeronave Atual", pilot.aircraft, "Índice 84"),
                    ("Minutos de Voo", pilot.flminutes, "Índice 11"),
                    ("Nº Total de Missões", pilot.missions, "Índice 46"),
                    ("Vitórias Confirmadas", pilot.killsCount, "Índice 17"),
                    ("Skill", pilot.skill, "Índice 41"),
                ]
                for name, value, origin in data:
                    report.write(
                        f"  -> {name}: {_display_value(value)} "
                        f"(Origem: {origin})\n"
                    )
                if parser.decorations:
                    report.write("  -> Medalhas:\n")
                    for decoration in parser.decorations:
                        report.write(f"     - {decoration.name}\n")
                if parser.wingmen:
                    report.write("  -> Wingmen:\n")
                    for wingman in parser.wingmen:
                        report.write(
                            f"     - {wingman.rank} {wingman.fName} "
                            f"{wingman.sName}\n"
                        )
            report.write("\n")
            continue

        if any(fnmatchcase(filename, pattern) for pattern in PILOT_TEXT_PATTERNS):
            report.write(f"📦 FONTE: {filename} (Ficheiro Texto Delimitado)\n")
            report.write("-" * 60 + "\n")
            parser = WoFFPilotDataParser()
            parsed = parser.parse(pilot_file)
            if parser.has_rejected_records or (
                not parsed and not parser.valid_empty
            ):
                raise ReportGenerationError(
                    f"Falha ao processar o ficheiro de piloto {filename}."
                )
            if parser.pilot:
                report.write(f"  -> Esquadrão: {parser.pilot.squadron}\n")
                report.write(f"  -> Base: {parser.pilot.aerodrome}\n")
            report.write(f"  -> Missões extraídas: {len(parser.missions)}\n")
            report.write(f"  -> Vitórias extraídas: {len(parser.victories)}\n\n")

    if mission_log_path:
        report.write("🛫 FONTE: mission.log (Plano de Voo)\n")
        report.write("=" * 60 + "\n")
        parser = WoFFMissionLogParser()
        if not parser.parse(mission_log_path):
            raise ReportGenerationError("Falha ao processar mission.log.")
        mission = parser.mission
        if mission:
            report.write(f"  -> Data: {mission.date}\n")
            report.write(f"  -> Aeronave: {mission.aircraft}\n")
            if parser.pilot:
                report.write(f"  -> Esquadrão: {parser.pilot.squadron}\n")
            report.write(f"  -> Waypoints Extraídos: {len(parser.flight_plan)}\n")
            for waypoint in parser.flight_plan[:3]:
                report.write(
                    f"     -> {waypoint['type']} "
                    f"(Lat: {waypoint['lat']}, Lon: {waypoint['lon']})\n"
                )
        report.write("\n")

    report.write("═" * 60 + "\n")
    report.write("FIM DO RELATÓRIO\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera um relatório auditável dos ficheiros WoFF configurados."
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Caminho para config.json (padrão: config.json)",
    )
    args = parser.parse_args(argv)

    log.info("A iniciar geração de relatório...")
    try:
        config = load_config(args.config)
    except InvalidConfigurationError as error:
        log.error("Configuração inválida: %s", error)
        return int(ExitCode.USAGE_ERROR)

    valid_paths = [path for path in config.watch_paths if os.path.isdir(path)]
    if not valid_paths:
        log.error("Nenhum caminho válido encontrado na configuração selecionada.")
        return int(ExitCode.USAGE_ERROR)

    output_path = Path.cwd() / OUTPUT_FILE
    temporary_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{OUTPUT_FILE}.",
            suffix=".tmp",
            delete=False,
        ) as report:
            temporary_path = Path(report.name)
            _write_report(cast(TextIO, report), valid_paths)
            report.flush()
            os.fsync(report.fileno())
        os.replace(temporary_path, output_path)
    except Exception as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
        log.error("Falha ao gerar relatório: %s", error)
        return int(ExitCode.RUNTIME_ERROR)

    log.info("Relatório gerado com sucesso: %s", output_path.resolve())
    return int(ExitCode.SUCCESS)


if __name__ == "__main__":
    raise SystemExit(main())
