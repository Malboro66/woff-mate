#!/usr/bin/env python3
"""
Módulo de Configuração (config.py)
══════════════════════════════════════════════════════════════════
Responsável por definir, carregar e validar a configuração do 
WoFF Watchdog.

Utiliza Dataclasses para garantir um esquema rígido e seguro, 
evitando erros de KeyErrors caso o utilizador apague acidentalmente 
campos do ficheiro config.json.

Inclui Auto-Deteção do caminho do jogo via Registo do Windows.
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, List

from .version import CONFIG_VERSION

log = logging.getLogger("WoFFWatch")


class InvalidConfigurationError(ValueError):
    """Raised when an existing configuration cannot be used safely."""


class UnsupportedConfigVersion(InvalidConfigurationError):
    """Raised when a config was written by a newer, unsupported release."""


@dataclass
class WatchdogConfig:
    """Estrutura de configuração rigorosa do WoFF Watchdog."""
    watch_paths: List[str] = field(default_factory=list)
    export_path: str = "C:\\Users\\Public\\WoFFBase\\woff_data.db"
    watched_extensions: List[str] = field(default_factory=lambda: [".txt", ".xml", ".log"])
    stability_timeout_sec: float = 3.0
    stability_check_interval_sec: float = 0.15
    backup_export: bool = True
    discovery_log_path: str = "woff_discovery.log"
    log_level: str = "INFO"
    max_workers: int = 4
    config_version: str = CONFIG_VERSION

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate and normalize every public configuration field."""
        if not isinstance(self.watch_paths, list):
            raise InvalidConfigurationError("watch_paths must be a list")
        self._validate_strings(self.watch_paths, "watch_paths")
        for name in ("export_path", "discovery_log_path"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidConfigurationError(f"{name} must be a nonblank string")
        if not isinstance(self.watched_extensions, list) or not self.watched_extensions:
            raise InvalidConfigurationError("watched_extensions must be a nonempty list")
        self._validate_strings(self.watched_extensions, "watched_extensions")
        normalized_extensions = []
        for extension in self.watched_extensions:
            extension = extension.lower()
            if not extension.startswith(".") or len(extension) == 1 or not extension[1:].isalnum():
                raise InvalidConfigurationError("watched_extensions entries must be extensions such as '.xml'")
            if extension in normalized_extensions:
                raise InvalidConfigurationError("watched_extensions must not contain duplicates")
            normalized_extensions.append(extension)
        self.watched_extensions = normalized_extensions
        for name in ("stability_timeout_sec", "stability_check_interval_sec"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise InvalidConfigurationError(f"{name} must be a finite positive number")
        if self.stability_check_interval_sec >= self.stability_timeout_sec:
            raise InvalidConfigurationError("stability_check_interval_sec must be less than stability_timeout_sec")
        if not isinstance(self.backup_export, bool):
            raise InvalidConfigurationError("backup_export must be a Boolean")
        if isinstance(self.max_workers, bool) or not isinstance(self.max_workers, int) or self.max_workers <= 0:
            raise InvalidConfigurationError("max_workers must be a positive integer")
        if not isinstance(self.log_level, str) or not self.log_level.strip():
            raise InvalidConfigurationError("log_level must be a nonblank string")
        self.log_level = self.log_level.upper()
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise InvalidConfigurationError("log_level is not supported")
        if not isinstance(self.config_version, str) or self.config_version != CONFIG_VERSION:
            raise UnsupportedConfigVersion(f"Versão de configuração {self.config_version!r} inválida ou não suportada; esta aplicação requer {CONFIG_VERSION!r}.")

    @staticmethod
    def _validate_strings(values: List[str], name: str) -> None:
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise InvalidConfigurationError(f"{name} entries must be nonblank strings")

    @classmethod
    def from_dict(cls, d: Any) -> "WatchdogConfig":
        """Cria a configuração a partir de um dicionário, avisando sobre chaves inválidas."""
        if not isinstance(d, dict):
            raise InvalidConfigurationError("configuration root must be a JSON object")
        valid_keys = cls.__dataclass_fields__.keys()
        legacy_keys = {"export_schema_version", "app_version"}
        unknown_keys = [k for k in d.keys() if k not in valid_keys and k not in legacy_keys]
        
        if unknown_keys:
            log.warning(f"⚠ Chaves desconhecidas no config.json ignoradas: {unknown_keys}")
            log.warning("Verifica se há erros de digitação no ficheiro de configuração.")
            
        config_version = d.get("config_version", CONFIG_VERSION)
        if not isinstance(config_version, str) or config_version != CONFIG_VERSION:
            raise UnsupportedConfigVersion(
                f"Versão de configuração {config_version!r} inválida ou não suportada; "
                f"esta aplicação requer {CONFIG_VERSION!r}."
            )

        if "export_schema_version" in d:
            log.info("Campo legado 'export_schema_version' ignorado.")

        valid = {k: v for k, v in d.items() if k in valid_keys}
        valid["config_version"] = config_version
        return cls(**valid)

    def to_dict(self) -> dict:
        """Converte a configuração para dicionário (para guardar em JSON)."""
        return asdict(self)


def load_config(path: str) -> WatchdogConfig:
    """
    Carrega a configuração de um ficheiro JSON.
    Se o ficheiro não existir, tenta auto-detectar o caminho do jogo no Registo do Windows.
    Se estiver corrompido, avisa o utilizador e usa os valores padrão.
    """
    p = Path(path)
    
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = WatchdogConfig.from_dict(data)
            log.info(f"Configuração carregada: {path}")
            return cfg
        except (InvalidConfigurationError, UnsupportedConfigVersion):
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as e:
            raise InvalidConfigurationError(f"Erro ao ler config: {e}") from e
    else:
        log.info("config.json não encontrado. A tentar auto-deteção...")
        
    # Tenta Auto-Deteção via Registo do Windows
    try:
        from .win_registry import get_woff_install_path
        woff_path = get_woff_install_path()
        
        if woff_path:
            default_cfg = WatchdogConfig()
            base_path = Path(woff_path)
            
            # Configura os caminhos automaticamente
            pilots_path = base_path / "campaigns" / "CampaignData" / "Pilots"
            
            # Corrigido: Os Logs costumam estar uma pasta acima do caminho base do jogo
            logs_path = base_path.parent / "Logs"
            if not logs_path.exists():
                logs_path = base_path / "Logs"
            
            # Validação: Será que os caminhos realmente existem no disco?
            valid_pilots = pilots_path.exists()
            valid_logs = logs_path.exists()
            
            default_cfg.watch_paths = [str(pilots_path), str(logs_path)]
            default_cfg.export_path = str(Path.home() / "Documents" / "WoFFBase" / "woff_data.db")
            
            # Guarda o config para o utilizador poder editar no futuro
            with open(p, "w", encoding="utf-8") as f:
                json.dump(default_cfg.to_dict(), f, indent=2, ensure_ascii=False)
                
            # Feedback inteligente ao utilizador
            if valid_pilots and valid_logs:
                log.info(f"✓ Auto-deteção bem-sucedida! config.json criado em: {p}")
            else:
                log.warning("⚠ Auto-deteção encontrou o jogo no Registo, mas as pastas padrão não existem:")
                if not valid_pilots: log.warning(f"  -> Pilots não encontrado em: {pilots_path}")
                if not valid_logs: log.warning(f"  -> Logs não encontrado em: {logs_path}")
                log.warning("Por favor, edite o ficheiro config.json manualmente com os caminhos corretos.")
                
            return default_cfg
    except ImportError:
        log.warning("Módulo de registo não disponível. A usar valores padrão.")
    except Exception as e:
        log.error(f"Falha na auto-deteção: {e}")
        
    # Fallback final se a auto-deteção falhar
    log.warning("A usar valores padrão. Edita o config.json manualmente.")
    return WatchdogConfig()
