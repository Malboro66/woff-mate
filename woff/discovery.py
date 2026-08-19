#!/usr/bin/env python3
"""
Módulo de Descoberta (discovery.py)
══════════════════════════════════════════════════════════════════
Responsável por registar ficheiros detetados pelo watchdog.

O conteúdo bruto só é registado para nomes de ficheiro WoFF explicitamente
aprovados. Ficheiros desconhecidos recebem apenas metadados, mesmo quando usam
uma extensão de texto suportada.

Usado no modo --discover para ajudar a conhecer a estrutura real dos
ficheiros gerados pelo WoFF antes de refinar os parsers.

Procedimento de utilização:
  1. Executar: python woff_watchdog.py --discover
  2. Jogar uma missão completa no WoFF
  3. Analisar o ficheiro 'woff_discovery.log' para ver os ficheiros gerados
  4. Atualizar os parsers com base no que for encontrado
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Pattern

log = logging.getLogger("WoFFWatch")


# Raw preview is opt-in by known WoFF-generated filename, never by extension
# alone. Unknown files are metadata-only so discovery cannot accidentally copy
# activation/license material or unrelated local text into its log.
PREVIEW_ALLOWED_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"^mission\.log$", re.IGNORECASE),
    re.compile(r"^pilot\d+(?:log|claims|squads|dossier)\.txt$", re.IGNORECASE),
)


def is_preview_allowed(path: str | Path) -> bool:
    """Return True only for explicitly approved WoFF-generated filenames."""
    name = Path(path).name
    return any(pattern.fullmatch(name) for pattern in PREVIEW_ALLOWED_PATTERNS)


class DiscoveryLogger:
    """Regista eventos WoFF e previews somente para ficheiros aprovados."""

    PREVIEW_LIMIT = 12_000  # bytes máximos a registar por ficheiro

    def __init__(self, log_path: str):
        self.log_path = Path(log_path)

        # Escreve o cabeçalho da sessão de descoberta
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'═'*60}\n")
            f.write(f"SESSÃO DE DESCOBERTA — {datetime.now().isoformat()}\n")
            f.write(f"{'═'*60}\n")

        log.info(f"Modo descoberta ativo — log: {self.log_path}")

    def log_file(self, path: str, event_type: str):
        """Regista metadados e, quando permitido, preview local do conteúdo."""
        try:
            p = Path(path)
            size = p.stat().st_size if p.exists() else 0
            ext = p.suffix.lower()

            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now().isoformat()}] Evento: {event_type.upper()}\n")
                f.write(f"Ficheiro: {path}\n")
                f.write(f"Tamanho: {size} bytes | Extensão: {ext}\n")

                if size > 0 and size < 1_000_000 and is_preview_allowed(p):
                    try:
                        with open(p, "r", encoding="utf-8", errors="replace") as src:
                            content = src.read(self.PREVIEW_LIMIT)
                        f.write(
                            f"{'─'*40} Conteúdo "
                            f"({min(size, self.PREVIEW_LIMIT)}/{size}B) {'─'*10}\n"
                        )
                        f.write(content)
                        f.write(f"\n{'─'*60}\n")
                    except Exception as e:
                        f.write(f"Erro ao ler conteúdo: {e}\n")
                elif size >= 1_000_000:
                    f.write("[Ficheiro muito grande — sem preview]\n")
                elif size > 0:
                    f.write("[Preview bloqueado pela política de privacidade]\n")
                else:
                    f.write("[Ficheiro vazio — sem preview]\n")

            log.info(f"[DISCOVER] {event_type}: {p.name} ({size}B)")

        except Exception as e:
            log.error(f"Erro no discovery log: {e}")
