#!/usr/bin/env python3
"""
Gestor de Base de Dados (database.py)
══════════════════════════════════════════════════════════════════
Responsável por armazenar e gerir os dados extraídos dos ficheiros
do WoFF BHaH II usando SQLite.

Inclui tabelas para dados do jogo (Pilotos, Missões, etc.), 
tabelas para a camada de RPG (Estados, Diário) e tabelas para 
o Sistema 3P (Personalidades e Memória de Wingmen).
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Any, Dict, NoReturn, Sequence, Tuple

from .campaign_namespace import (
    LEGACY_CAMPAIGN_NAMESPACE,
    is_campaign_namespace,
)
from .identity import PilotIdentityError, PilotIdentityEvidence, pilot_slot
from .models import WoFFPilot, WoFFMission, WoFFVictory, WoFFDecoration, WoFFWingman
from .repositories import PilotRepository, MissionRepository, RpgRepository, WingmanRepository
from .version import SCHEMA_VERSION, __version__

log = logging.getLogger("WoFFWatch")
_DOSSIER_ROSTER_META_PREFIX = "dossier_roster:"


class UnsupportedSchemaVersion(RuntimeError):
    """Raised before opening a database created by a newer schema."""


class SchemaCompatibilityError(RuntimeError):
    """Raised when a database layout cannot be safely certified or migrated."""


class MigrationBackupUnavailableError(RuntimeError):
    """Raised when a recorded migration backup disappears before restoration."""


class TransactionRollbackError(RuntimeError):
    """Raised when caught nested failure makes an outer transaction rollback-only."""


@dataclass(frozen=True)
class DossierWingmanState:
    """Roster fields needed to derive one Dossier generation's diary effects."""

    first_name: str
    last_name: str
    status: str


@dataclass(frozen=True)
class DossierState:
    """One consistent persisted view used by the Dossier application service."""

    pilot_id: str
    status: Optional[str]
    rank: Optional[str]
    squadron: str
    dossier_digest: Optional[str]
    wingmen: Tuple[DossierWingmanState, ...]


def _version_tuple(version: str) -> Tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError as exc:
        raise UnsupportedSchemaVersion(
            f"Versão de schema SQLite inválida: {version!r}."
        ) from exc

# ── Whitelist de migrações schema (proteção contra SQL Injection) ──
ALLOWED_MIGRATIONS: Dict[str, Dict[str, str]] = {
    "pilots": {
        "fName": "TEXT", "sName": "TEXT", "photo": "TEXT", "birthDate": "TEXT",
        "birthPlace": "TEXT", "missions": "INTEGER", "flminutes": "INTEGER",
        "claimsCount": "INTEGER", "killsCount": "INTEGER", "skill": "INTEGER", "reputation": "INTEGER",
        "enlisted": "TEXT"
    },
    "missions": {
        "time": "TEXT", "squadron": "TEXT", "enemyContacts": "INTEGER",
        "claimsCount": "INTEGER"
    },
    "squad_members": {
        "skill": "INTEGER", "morale": "INTEGER", "missions": "INTEGER",
        "flminutes": "INTEGER"
    },
    "victories": {
        "sector": "TEXT", "aircraft": "TEXT"
    }
}

# Canonical schema 3.3 contract. SQLite integrity checks cannot detect missing
# application columns or constraints, so certification verifies these explicitly.
SCHEMA_TABLES: Dict[str, Dict[str, str]] = {
    "meta": {"key": "TEXT", "value": "TEXT"},
    "pilots": {"id": "TEXT", "name": "TEXT", "fName": "TEXT", "sName": "TEXT", "nation": "TEXT", "rank": "TEXT", "squadron": "TEXT", "aircraft": "TEXT", "aerodrome": "TEXT", "sector": "TEXT", "startDate": "TEXT", "enlisted": "TEXT", "status": "TEXT", "notes": "TEXT", "photo": "TEXT", "birthDate": "TEXT", "birthPlace": "TEXT", "missions": "INTEGER", "flminutes": "INTEGER", "claimsCount": "INTEGER", "killsCount": "INTEGER", "skill": "INTEGER", "reputation": "INTEGER", "source_file": "TEXT", "last_updated": "TEXT"},
    "pilot_slot_bindings": {"campaign_namespace": "TEXT", "slot": "INTEGER", "pilotId": "TEXT", "dossier_digest": "TEXT", "last_updated": "TEXT"},
    "missions": {"id": "TEXT", "pilotId": "TEXT", "date": "TEXT", "time": "TEXT", "missionType": "TEXT", "aircraft": "TEXT", "duration": "TEXT", "altitude": "TEXT", "sector": "TEXT", "squadron": "TEXT", "weather": "TEXT", "enemyContacts": "INTEGER", "claimsCount": "INTEGER", "result": "TEXT", "damageReceived": "INTEGER", "woundsReceived": "INTEGER", "notes": "TEXT", "source_file": "TEXT"},
    "victories": {"id": "TEXT", "pilotId": "TEXT", "date": "TEXT", "time": "TEXT", "missionId": "TEXT", "enemyType": "TEXT", "victoryType": "TEXT", "location": "TEXT", "confirmed": "INTEGER", "witnesses": "TEXT", "notes": "TEXT", "sector": "TEXT", "aircraft": "TEXT", "source_file": "TEXT"},
    "decorations": {"id": "TEXT", "pilotId": "TEXT", "name": "TEXT", "date": "TEXT", "citation": "TEXT", "source_file": "TEXT"},
    "squad_members": {"id": "TEXT", "pilotId": "TEXT", "rank": "TEXT", "fName": "TEXT", "sName": "TEXT", "skill": "INTEGER", "morale": "INTEGER", "status": "TEXT", "missions": "INTEGER", "flminutes": "INTEGER", "bio": "TEXT"},
    "medals_catalog": {"id": "TEXT", "country": "TEXT", "name": "TEXT", "filename": "TEXT"},
    "squadrons": {"id": "TEXT", "name": "TEXT", "raw_data": "TEXT", "source_file": "TEXT"},
    "pilot_rpg_stats": {"pilotId": "TEXT", "fatigue": "INTEGER", "morale": "INTEGER", "stress": "INTEGER", "last_updated": "TEXT"},
    "diary_entries": {"id": "TEXT", "pilotId": "TEXT", "missionId": "TEXT", "entry_date": "TEXT", "narrative": "TEXT"},
    "wingmen_personalities": {"wingmanId": "TEXT", "pilotId": "TEXT", "aerial_skill": "INTEGER", "aggression": "INTEGER", "charisma": "INTEGER", "intelligence": "INTEGER", "physicality": "INTEGER", "professionalism": "INTEGER", "personality_trait": "TEXT"},
    "wingmen_memory": {"id": "TEXT", "wingmanId": "TEXT", "event_type": "TEXT", "event_date": "TEXT", "description": "TEXT", "impact_morale": "INTEGER", "impact_stress": "INTEGER"},
}

SCHEMA_PRIMARY_KEYS: Dict[str, Tuple[str, ...]] = {
    table: (
        ("pilotId",)
        if table == "pilot_rpg_stats"
        else ("wingmanId",)
        if table == "wingmen_personalities"
        else ("key",)
        if table == "meta"
        else ("campaign_namespace", "slot")
        if table == "pilot_slot_bindings"
        else ("id",)
    )
    for table in SCHEMA_TABLES
}
SCHEMA_UNIQUES = {
    "missions": [("pilotId", "date", "time", "missionType", "aircraft")],
    "victories": [("pilotId", "date", "time", "enemyType")],
    "decorations": [("pilotId", "name")],
    "squad_members": [("pilotId", "fName", "sName")],
    "medals_catalog": [("country", "name")],
}
SCHEMA_FOREIGN_KEYS = {
    "pilot_slot_bindings": {("pilotId", "pilots", "id")},
    "missions": {("pilotId", "pilots", "id")},
    "victories": {("pilotId", "pilots", "id")},
    "decorations": {("pilotId", "pilots", "id")},
    "squad_members": {("pilotId", "pilots", "id")},
    "pilot_rpg_stats": {("pilotId", "pilots", "id")},
    "diary_entries": {("pilotId", "pilots", "id"), ("missionId", "missions", "id")},
    "wingmen_personalities": {("wingmanId", "squad_members", "id")},
    "wingmen_memory": {("wingmanId", "squad_members", "id")},
}


class DatabaseManager:
    def __init__(
        self,
        db_path: str,
        *,
        campaign_namespaces: Optional[Sequence[str]] = None,
    ):
        self.db_path = Path(db_path)
        self.schema_version = SCHEMA_VERSION
        self._configured_campaign_namespaces = tuple(campaign_namespaces or ())
        invalid_namespace = any(
            not is_campaign_namespace(namespace)
            for namespace in self._configured_campaign_namespaces
        )
        if (
            invalid_namespace
            or len(self._configured_campaign_namespaces)
            != len(set(self._configured_campaign_namespaces))
        ):
            raise ValueError("campaign_namespaces must contain unique root identifiers")
        self._lock = threading.RLock()
        self._local = threading.local()

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            self._migration_backup_path: Optional[Path] = None
            stored_version = self._read_schema_version()
            if stored_version is not None and _version_tuple(stored_version) > _version_tuple(SCHEMA_VERSION):
                raise UnsupportedSchemaVersion(
                    f"Banco usa schema futuro {stored_version}; "
                    f"esta aplicação suporta até {SCHEMA_VERSION}."
                )

            try:
                self._migrate_schema()
            except Exception:
                try:
                    self._restore_migration_backup()
                except Exception as restore_error:
                    if self._migration_backup_path is not None:
                        if not isinstance(restore_error, MigrationBackupUnavailableError):
                            log.error(
                                "Migração falhou e a restauração automática também falhou. "
                                "Backup preservado em: %s",
                                self._migration_backup_path,
                            )
                    raise
                raise

        self._pilots = PilotRepository(self)
        self._missions = MissionRepository(self)
        self._rpg = RpgRepository(self)
        self._wingmen = WingmanRepository(self)

    def _read_schema_version(self) -> Optional[str]:
        """Read schema metadata without creating or changing the database."""
        if not self.db_path.exists():
            return None
        uri = f"{self.db_path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            try:
                has_meta = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'"
                ).fetchone()
                if not has_meta:
                    return None
                row = conn.execute(
                    "SELECT value FROM meta WHERE key='schema_version'"
                ).fetchone()
                return str(row[0]) if row is not None else None
            except sqlite3.OperationalError:
                # A stale/crashed journal may require recovery, which a read-only
                # probe cannot perform. The transactional validation below remains
                # authoritative and will run before any application DDL.
                return None
        finally:
            conn.close()

    # ── Thread-Local Connection Pooling ──
    def _open_conn(self) -> sqlite3.Connection:
        """Cria uma conexão SQLite com todas as opções exigidas pelo gestor."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _get_conn(self) -> sqlite3.Connection:
        """Devolve a conexão da thread atual, recriando-a se tiver sido fechada."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._open_conn()
            return self._local.conn

        try:
            self._local.conn.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            self._local.conn = self._open_conn()

        return self._local.conn

    @contextmanager
    def transaction(self):
        """Run a composable transaction on the current thread's connection."""
        with self._lock:
            conn = self._get_conn()
            depth = getattr(self._local, "transaction_depth", 0)
            outermost = depth == 0
            if outermost:
                conn.execute("BEGIN")
                self._local.transaction_rollback_only = False
            self._local.transaction_depth = depth + 1
            exception_propagating = False
            try:
                yield conn
            except Exception:
                exception_propagating = True
                self._local.transaction_rollback_only = True
                raise
            finally:
                self._local.transaction_depth = depth
                if outermost:
                    try:
                        if self._local.transaction_rollback_only:
                            try:
                                conn.rollback()
                            except Exception:
                                self._discard_failed_connection(conn)
                                if exception_propagating:
                                    log.exception(
                                        "Rollback failed while preserving "
                                        "transaction exception"
                                    )
                                else:
                                    raise
                            if not exception_propagating:
                                raise TransactionRollbackError(
                                    "Transaction rolled back after a nested failure "
                                    "marked it rollback-only"
                                )
                        else:
                            try:
                                conn.commit()
                            except Exception:
                                try:
                                    conn.rollback()
                                except Exception:
                                    log.exception("Rollback failed after commit failure")
                                    self._discard_failed_connection(conn)
                                raise
                    finally:
                        self._local.transaction_rollback_only = False

    def _discard_failed_connection(self, conn: sqlite3.Connection) -> None:
        """Discard a connection whose transactional state is uncertain."""
        if getattr(self._local, "conn", None) is conn:
            self._local.conn = None
        try:
            conn.close()
        except Exception:
            log.exception("Failed to close connection after rollback failure")

    def close(self) -> None:
        """Fecha a conexão da thread atual. Chamar no shutdown."""
        if hasattr(self._local, 'conn') and self._local.conn:
            try:
                self._local.conn.close()
            finally:
                self._local.conn = None

    def _init_db(self):
        """Cria as tabelas se não existirem."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
            )

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pilots (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    fName TEXT,
                    sName TEXT,
                    nation TEXT,
                    rank TEXT,
                    squadron TEXT,
                    aircraft TEXT,
                    aerodrome TEXT,
                    sector TEXT,
                    startDate TEXT,
                    enlisted TEXT,
                    status TEXT,
                    notes TEXT,
                    photo TEXT,
                    birthDate TEXT,
                    birthPlace TEXT,
                    missions INTEGER,
                    flminutes INTEGER,
                    claimsCount INTEGER,
                    killsCount INTEGER,
                    skill INTEGER,
                    reputation INTEGER,
                    source_file TEXT,
                    last_updated TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pilots_name ON pilots(name)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pilot_slot_bindings (
                    campaign_namespace TEXT NOT NULL
                        CHECK(length(campaign_namespace) > 0),
                    slot INTEGER NOT NULL CHECK(slot > 0),
                    pilotId TEXT NOT NULL,
                    dossier_digest TEXT,
                    last_updated TEXT NOT NULL,
                    PRIMARY KEY(campaign_namespace, slot),
                    FOREIGN KEY(pilotId) REFERENCES pilots(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY,
                    pilotId TEXT,
                    date TEXT,
                    time TEXT,
                    missionType TEXT,
                    aircraft TEXT,
                    duration TEXT,
                    altitude TEXT,
                    sector TEXT,
                    squadron TEXT,
                    weather TEXT,
                    enemyContacts INTEGER,
                    claimsCount INTEGER,
                    result TEXT,
                    damageReceived INTEGER,
                    woundsReceived INTEGER,
                    notes TEXT,
                    source_file TEXT,
                    UNIQUE(pilotId, date, time, missionType, aircraft),
                    FOREIGN KEY(pilotId) REFERENCES pilots(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS victories (
                    id TEXT PRIMARY KEY,
                    pilotId TEXT,
                    date TEXT,
                    time TEXT,
                    missionId TEXT,
                    enemyType TEXT,
                    victoryType TEXT,
                    location TEXT,
                    confirmed INTEGER,
                    witnesses TEXT,
                    notes TEXT,
                    sector TEXT,
                    aircraft TEXT,
                    source_file TEXT,
                    UNIQUE(pilotId, date, time, enemyType),
                    FOREIGN KEY(pilotId) REFERENCES pilots(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS decorations (
                    id TEXT PRIMARY KEY, pilotId TEXT, name TEXT, date TEXT,
                    citation TEXT, source_file TEXT,
                    UNIQUE(pilotId, name), FOREIGN KEY(pilotId) REFERENCES pilots(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS squad_members (
                    id TEXT PRIMARY KEY, pilotId TEXT, rank TEXT, fName TEXT,
                    sName TEXT, skill INTEGER, morale INTEGER, status TEXT, missions INTEGER,
                    flminutes INTEGER, bio TEXT,
                    UNIQUE(pilotId, fName, sName),
                    FOREIGN KEY(pilotId) REFERENCES pilots(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS medals_catalog (
                    id TEXT PRIMARY KEY, country TEXT, name TEXT, filename TEXT,
                    UNIQUE(country, name)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS squadrons (
                    id TEXT PRIMARY KEY, name TEXT, raw_data TEXT, source_file TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pilot_rpg_stats (
                    pilotId TEXT PRIMARY KEY, fatigue INTEGER DEFAULT 0,
                    morale INTEGER DEFAULT 75, stress INTEGER DEFAULT 0,
                    last_updated TEXT,
                    FOREIGN KEY(pilotId) REFERENCES pilots(id)
                )
            """)

            # FIX: UNIQUE parcial para permitir múltiplos eventos de vida (missionId=NULL)
            # mas bloquear missões duplicadas no diário.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS diary_entries (
                    id TEXT PRIMARY KEY,
                    pilotId TEXT NOT NULL,
                    missionId TEXT,
                    entry_date TEXT,
                    narrative TEXT,
                    FOREIGN KEY(pilotId) REFERENCES pilots(id),
                    FOREIGN KEY(missionId) REFERENCES missions(id)
                )
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_diary_unique_mission
                ON diary_entries(pilotId, missionId)
                WHERE missionId IS NOT NULL
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wingmen_personalities (
                    wingmanId TEXT PRIMARY KEY, pilotId TEXT,
                    aerial_skill INTEGER DEFAULT 50, aggression INTEGER DEFAULT 50,
                    charisma INTEGER DEFAULT 50, intelligence INTEGER DEFAULT 50,
                    physicality INTEGER DEFAULT 50, professionalism INTEGER DEFAULT 50,
                    personality_trait TEXT,
                    FOREIGN KEY(wingmanId) REFERENCES squad_members(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wingmen_memory (
                    id TEXT PRIMARY KEY, wingmanId TEXT, event_type TEXT,
                    event_date TEXT, description TEXT, impact_morale INTEGER DEFAULT 0,
                    impact_stress INTEGER DEFAULT 0,
                    FOREIGN KEY(wingmanId) REFERENCES squad_members(id)
                )
            """)

            log.info(f"Base de dados SQLite pronta: {self.db_path}")
        except Exception:
            log.exception("Erro ao inicializar base de dados")
            raise
        # Nota: não fechamos conn aqui — thread-local permanece aberta

    def _existing_database_has_pending_migration(self) -> bool:
        if not self.db_path.exists():
            return False
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            for table, cols in ALLOWED_MIGRATIONS.items():
                cursor.execute(f"PRAGMA table_info({table})")
                info = cursor.fetchall()
                existing_columns = {row[1] for row in info}
                if existing_columns and any(col not in existing_columns for col in cols):
                    return True
            return self._has_numeric_column_type_migration(
                cursor
            ) or self._has_pilot_identity_schema_migration(
                cursor
            ) or self._has_campaign_namespace_schema_migration(
                cursor
            ) or self._has_legacy_namespace_reconciliation(cursor)
        finally:
            conn.close()

    def _backup_existing_database(self) -> Path:
        """Cria backup SQLite consistente via Connection.backup sem sobrescrever."""
        backup_dir = self.db_path.parent / ".woff-migration-backups"
        backup_dir.mkdir(exist_ok=True)
        stem = self.db_path.name
        timestamp = time.strftime("%Y%m%d%H%M%S")
        counter = 0
        while True:
            suffix = f".{counter}" if counter else ""
            backup_path = backup_dir / f"{stem}.{timestamp}{suffix}.backup.sqlite"
            try:
                fd = os.open(backup_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                break
            except FileExistsError:
                counter += 1

        source: Optional[sqlite3.Connection] = None
        dest: Optional[sqlite3.Connection] = None
        try:
            source = sqlite3.connect(self.db_path)
            dest = sqlite3.connect(backup_path)
            self._run_sqlite_backup(source, dest)
            if dest.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise sqlite3.DatabaseError("integrity_check failed for migration backup")
        except Exception:
            if dest is not None:
                dest.close()
            if source is not None:
                source.close()
            try:
                backup_path.unlink()
            except FileNotFoundError:
                pass
            raise
        else:
            dest.close()
            source.close()
        self._fsync_directory(backup_dir)
        log.info("Backup de migração criado: %s", backup_path)
        return backup_path

    def _run_sqlite_backup(self, source: sqlite3.Connection, dest: sqlite3.Connection) -> None:
        source.backup(dest)

    def _restore_migration_backup(self) -> None:
        """Restaura backup via API SQLite sem mover arquivos de conexões abertas."""
        backup_path = getattr(self, "_migration_backup_path", None)
        if backup_path is None:
            return
        if not backup_path.exists():
            self._raise_migration_backup_unavailable(backup_path)

        self.close()
        source_uri = f"{backup_path.resolve().as_uri()}?mode=ro"
        try:
            source = sqlite3.connect(source_uri, uri=True)
        except sqlite3.Error as exc:
            self._raise_migration_backup_unavailable(backup_path, exc)
        dest = sqlite3.connect(self.db_path, timeout=0)
        try:
            mode = dest.execute("PRAGMA locking_mode=EXCLUSIVE").fetchone()
            if mode is None or str(mode[0]).lower() != "exclusive":
                raise sqlite3.OperationalError("could not enable exclusive locking for restore")
            dest.execute("BEGIN EXCLUSIVE")
            dest.rollback()
            self._run_sqlite_backup(source, dest)
            if dest.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise sqlite3.DatabaseError("integrity_check failed after restoring migration backup")
        finally:
            dest.close()
            source.close()
        self._fsync_directory(self.db_path.parent)
        log.error(
            "Migração falhou. Restauração automática concluída a partir de: %s",
            backup_path,
        )

    @staticmethod
    def _raise_migration_backup_unavailable(
        backup_path: Path, cause: Optional[BaseException] = None
    ) -> NoReturn:
        message = (
            "Migração falhou e o backup de migração registrado está indisponível em: "
            f"{backup_path}"
        )
        log.error(message)
        error = MigrationBackupUnavailableError(message)
        if cause is None:
            raise error
        raise error from cause

    def _unique_sidecar_path(self, path: Path, label: str) -> Path:
        counter = 0
        while True:
            suffix = f".{counter}" if counter else ""
            candidate = path.with_name(f".{path.name}.{label}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        if os.name == "nt":
            return
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _migrate_schema(self):
        """
        Aplica migrações à Base de Dados se ela for de uma versão antiga.

        Riscos mitigados: o fluxo antigo desativava foreign_keys, reconstruía tabelas
        com ``CAST`` silencioso (``'abc'`` virava ``0``), descartava índices externos
        à definição da tabela e gravava ``schema_version`` no mesmo bloco que podia
        deixar uma reconstrução parcialmente aplicada. Agora a reconstrução ocorre
        dentro de transação explícita, com backup prévio, validação de inteiros,
        recriação de índices definidos pelo utilizador e verificação final por
        ``foreign_key_check`` e ``integrity_check``.

        Política para valores numéricos inválidos: NULL e string vazia são
        preservados como NULL; inteiros válidos, incluindo negativos e espaços
        em volta, são convertidos; qualquer outro valor aborta a migração com
        ValueError para não converter nem descartar dados silenciosamente.
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            try:
                cursor = conn.cursor()
                conn.create_function("woff_safe_int", 1, self._parse_sqlite_integer)
                try:
                    cursor.execute("PRAGMA foreign_keys=OFF")
                    cursor.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError as exc:
                    raise sqlite3.OperationalError(
                        "Cannot run schema migration because another process is writing to the database"
                    ) from exc

                def table_columns(table: str) -> set[str]:
                    cursor.execute(f"PRAGMA table_info({table})")
                    return {row[1] for row in cursor.fetchall()}

                def column_exists(table: str, col: str) -> bool:
                    return col in table_columns(table)

                has_meta = cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'"
                ).fetchone()
                binding_existed_before = cursor.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type='table' AND name='pilot_slot_bindings'"
                ).fetchone() is not None
                stored_version = (
                    cursor.execute(
                        "SELECT value FROM meta WHERE key='schema_version'"
                    ).fetchone()
                    if has_meta
                    else None
                )
                if (
                    stored_version is not None
                    and _version_tuple(str(stored_version[0])) > _version_tuple(SCHEMA_VERSION)
                ):
                    raise UnsupportedSchemaVersion(
                        f"Banco usa schema futuro {stored_version[0]}; "
                        f"esta aplicação suporta até {SCHEMA_VERSION}."
                    )

                user_objects = cursor.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
                ).fetchone()
                pending_migration = (
                    user_objects is not None
                    and (stored_version is None or str(stored_version[0]) != SCHEMA_VERSION)
                )
                for table, cols in ALLOWED_MIGRATIONS.items():
                    existing_columns = table_columns(table)
                    if existing_columns:
                        for col in cols:
                            pending_migration = pending_migration or col not in existing_columns
                pending_migration = pending_migration or self._has_numeric_column_type_migration(cursor)
                pending_migration = (
                    pending_migration
                    or self._has_pilot_identity_schema_migration(cursor)
                )
                pending_migration = (
                    pending_migration
                    or self._has_campaign_namespace_schema_migration(cursor)
                    or self._has_legacy_namespace_reconciliation(cursor)
                )
                if pending_migration and self._migration_backup_path is None:
                    self._migration_backup_path = self._backup_existing_database()

                cursor.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")

                for table, cols in ALLOWED_MIGRATIONS.items():
                    existing_columns = table_columns(table)
                    if not existing_columns:
                        continue
                    for col, typ in cols.items():
                        if col not in existing_columns:
                            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
                            log.info(f"  [Migração] Coluna '{col}' adicionada a '{table}'.")
                            existing_columns.add(col)

                self._migrate_numeric_column_types(cursor)
                self._migrate_pilot_identity_schema(cursor)
                self._migrate_campaign_namespace_schema(cursor)

                # Initialization is part of this same transaction: a failure in
                # any CREATE rolls back migrations and leaves old metadata intact.
                self._local.conn = conn
                self._init_db()
                if not binding_existed_before:
                    self._seed_unambiguous_slot_bindings(cursor)
                self._reconcile_legacy_campaign_namespace(cursor)

                if table_columns("diary_entries"):
                    cursor.execute("""
                        CREATE UNIQUE INDEX IF NOT EXISTS idx_diary_unique_mission
                        ON diary_entries(pilotId, missionId)
                        WHERE missionId IS NOT NULL
                    """)

                if cursor.execute("PRAGMA foreign_key_check").fetchall():
                    raise sqlite3.IntegrityError("foreign_key_check failed after migration")
                if cursor.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise sqlite3.DatabaseError("integrity_check failed after migration")

                self._validate_schema_contract(cursor)

                cursor.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
                    (self.schema_version,)
                )
                cursor.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES ('app_version', ?)",
                    (__version__,),
                )
                conn.commit()
            except Exception:
                log.exception("Erro na migração de schema")
                conn.rollback()
                raise
            finally:
                if getattr(self._local, "conn", None) is conn:
                    self._local.conn = None
                conn.close()

    def _validate_schema_contract(self, cursor: sqlite3.Cursor) -> None:
        """Certify the complete application schema, not only SQLite integrity."""
        errors: List[str] = []
        for table, required_columns in SCHEMA_TABLES.items():
            info = cursor.execute(
                f"PRAGMA table_info({self._quote_identifier(table)})"
            ).fetchall()
            if not info:
                errors.append(f"missing table {table}")
                continue
            actual = {str(row[1]): str(row[2]).upper() for row in info}
            for column, expected_type in required_columns.items():
                if column not in actual:
                    errors.append(f"missing column {table}.{column}")
                elif actual[column] != expected_type:
                    errors.append(
                        f"wrong type {table}.{column}: {actual[column] or '<none>'}, "
                        f"expected {expected_type}"
                    )

            primary_key = tuple(
                row[1] for row in sorted(info, key=lambda item: item[5]) if row[5]
            )
            expected_pk = SCHEMA_PRIMARY_KEYS[table]
            if primary_key != expected_pk:
                errors.append(
                    f"wrong primary key {table}: {primary_key}, expected {expected_pk}"
                )

            indexes = cursor.execute(
                f"PRAGMA index_list({self._quote_identifier(table)})"
            ).fetchall()
            all_unique_columns = {
                tuple(
                    row[2]
                    for row in cursor.execute(
                        f"PRAGMA index_info({self._quote_identifier(str(index[1]))})"
                    ).fetchall()
                )
                for index in indexes
                if index[2]
            }
            required_unique_columns = {
                tuple(
                    row[2]
                    for row in cursor.execute(
                        f"PRAGMA index_info({self._quote_identifier(str(index[1]))})"
                    ).fetchall()
                )
                for index in indexes
                # A table UNIQUE constraint is represented by a non-partial
                # index whose origin is ``u``. A user-created (origin ``c``)
                # partial index is not an equivalent schema constraint.
                if index[2] and index[3] == "u" and not index[4]
            }
            for unique in SCHEMA_UNIQUES.get(table, []):
                if unique not in required_unique_columns:
                    errors.append(f"missing UNIQUE {table}{unique}")
            if table == "pilots" and ("name",) in all_unique_columns:
                errors.append("forbidden UNIQUE pilots('name',)")
            if (
                table == "pilot_slot_bindings"
                and ("slot",) in all_unique_columns
            ):
                errors.append("forbidden global UNIQUE pilot_slot_bindings('slot',)")

            foreign_keys = {
                (str(row[3]), str(row[2]), str(row[4]))
                for row in cursor.execute(
                    f"PRAGMA foreign_key_list({self._quote_identifier(table)})"
                ).fetchall()
            }
            for foreign_key in SCHEMA_FOREIGN_KEYS.get(table, set()):
                if foreign_key not in foreign_keys:
                    errors.append(f"missing foreign key {table}{foreign_key}")

        pilots_indexes = cursor.execute("PRAGMA index_list(pilots)").fetchall()
        pilots_name_index = next(
            (row for row in pilots_indexes if row[1] == "idx_pilots_name"), None
        )
        if pilots_name_index is None or pilots_name_index[2] or pilots_name_index[4]:
            errors.append("missing canonical non-unique index idx_pilots_name")
        else:
            name_index_columns = tuple(
                str(row[2])
                for row in cursor.execute(
                    "PRAGMA index_info(idx_pilots_name)"
                ).fetchall()
            )
            if name_index_columns != ("name",):
                errors.append("wrong key semantics for index idx_pilots_name")

        binding_info = {
            str(row[1]): row
            for row in cursor.execute(
                "PRAGMA table_info(pilot_slot_bindings)"
            ).fetchall()
        }
        for required_not_null in (
            "campaign_namespace",
            "slot",
            "pilotId",
            "last_updated",
        ):
            if required_not_null in binding_info and not binding_info[required_not_null][3]:
                errors.append(
                    f"missing NOT NULL pilot_slot_bindings.{required_not_null}"
                )
        binding_sql_row = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='pilot_slot_bindings'"
        ).fetchone()
        binding_sql = (
            str(binding_sql_row[0])
            if binding_sql_row is not None and binding_sql_row[0]
            else ""
        )
        if re.search(
            r"CHECK\s*\(\s*[\"`\[]?slot[\"`\]]?\s*>\s*0\s*\)",
            binding_sql,
            flags=re.IGNORECASE,
        ) is None:
            errors.append("missing positive slot check pilot_slot_bindings.slot")
        if re.search(
            r"CHECK\s*\(\s*length\s*\(\s*[\"`\[]?campaign_namespace"
            r"[\"`\]]?\s*\)\s*>\s*0\s*\)",
            binding_sql,
            flags=re.IGNORECASE,
        ) is None:
            errors.append(
                "missing nonblank namespace check "
                "pilot_slot_bindings.campaign_namespace"
            )
        invalid_namespaces = [
            str(row[0])
            for row in cursor.execute(
                "SELECT DISTINCT campaign_namespace "
                "FROM pilot_slot_bindings"
            ).fetchall()
            if not is_campaign_namespace(row[0], allow_legacy=True)
        ]
        if invalid_namespaces:
            errors.append("unsupported pilot-slot campaign namespace value")

        diary_indexes = cursor.execute("PRAGMA index_list(diary_entries)").fetchall()
        diary_index = next(
            (row for row in diary_indexes if row[1] == "idx_diary_unique_mission"),
            None,
        )
        if diary_index is None or not diary_index[2] or not diary_index[4]:
            errors.append("missing required partial unique index idx_diary_unique_mission")
        elif tuple(
            (str(row[2]), int(row[3]), str(row[4]).upper())
            for row in cursor.execute(
                "PRAGMA index_xinfo(idx_diary_unique_mission)"
            ).fetchall()
            if row[5] == 1
        ) != (
            ("pilotId", 0, "BINARY"),
            ("missionId", 0, "BINARY"),
        ):
            errors.append("wrong key semantics for index idx_diary_unique_mission")
        else:
            index_sql_row = cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' "
                "AND name='idx_diary_unique_mission'"
            ).fetchone()
            index_sql = str(index_sql_row[0]) if index_sql_row and index_sql_row[0] else ""
            if not self._has_canonical_diary_index_predicate(index_sql):
                errors.append("wrong predicate for index idx_diary_unique_mission")

        if errors:
            raise SchemaCompatibilityError(
                f"Database layout is incompatible with schema {SCHEMA_VERSION}: "
                + "; ".join(errors)
            )

    def _has_canonical_diary_index_predicate(self, sql: str) -> bool:
        """Match the complete canonical WHERE expression with quoted identifiers."""
        where_match = re.search(r"\bWHERE\b", sql, flags=re.IGNORECASE)
        if where_match is None:
            return False
        predicate = sql[where_match.end():].strip()
        try:
            identifier, end = self._read_identifier(predicate, 0)
        except ValueError:
            return False
        remainder = predicate[end:]
        return identifier.lower() == "missionid" and bool(
            re.fullmatch(r"\s+IS\s+NOT\s+NULL\s*", remainder, flags=re.IGNORECASE)
        )

    def _numeric_columns(self) -> Dict[str, set[str]]:
        return {
            "pilots": {"missions", "flminutes", "claimsCount", "killsCount", "skill", "reputation"},
            "missions": {"enemyContacts", "claimsCount"},
            "squad_members": {"skill", "morale", "missions", "flminutes"},
        }

    def _has_numeric_column_type_migration(self, cursor: sqlite3.Cursor) -> bool:
        for table, columns in self._numeric_columns().items():
            cursor.execute(f"PRAGMA table_info({table})")
            info = cursor.fetchall()
            if any(row[1] in columns and row[2].upper() != "INTEGER" for row in info):
                return True
        return False

    def _migrate_numeric_column_types(self, cursor: sqlite3.Cursor) -> None:
        """Reconstrói tabelas antigas com colunas numéricas TEXT de forma segura."""
        for table, columns in self._numeric_columns().items():
            cursor.execute(f"PRAGMA table_info({table})")
            info = cursor.fetchall()
            if not info:
                continue
            text_numeric = [row[1] for row in info if row[1] in columns and row[2].upper() != "INTEGER"]
            if not text_numeric:
                continue

            self._validate_integer_values(cursor, table, text_numeric)
            dependent_sql = self._dependent_sql_for_table(cursor, table)
            new_table = self._unique_temp_table_name(cursor, table)
            self._create_rebuild_table_from_schema(cursor, table, new_table, text_numeric)
            self._validate_rebuild_schema(cursor, table, new_table, text_numeric)

            old_cols = [row[1] for row in info]
            cursor.execute(f"PRAGMA table_info({new_table})")
            new_cols = [row[1] for row in cursor.fetchall()]
            common_cols = [col for col in new_cols if col in old_cols]
            select_exprs = [
                self._integer_select_expression(col) if col in columns else self._quote_identifier(col)
                for col in common_cols
            ]
            column_list = ", ".join(self._quote_identifier(col) for col in common_cols)
            cursor.execute(
                f"INSERT INTO {self._quote_identifier(new_table)} ({column_list}) "
                f"SELECT {', '.join(select_exprs)} FROM {self._quote_identifier(table)}"
            )
            cursor.execute(f"DROP TABLE {self._quote_identifier(table)}")
            cursor.execute(
                f"ALTER TABLE {self._quote_identifier(new_table)} "
                f"RENAME TO {self._quote_identifier(table)}"
            )
            for sql in dependent_sql:
                cursor.execute(sql)
            log.info(
                f"  [Migração] Tabela '{table}' convertida para colunas numéricas INTEGER: "
                f"{', '.join(text_numeric)}."
            )

    def _pilot_name_unique_indexes(
        self, cursor: sqlite3.Cursor, table: str = "pilots"
    ) -> List[Tuple[str, Optional[str]]]:
        """Return every unique index whose only key is the display name."""

        indexes: List[Tuple[str, Optional[str]]] = []
        for row in cursor.execute(
            f"PRAGMA index_list({self._quote_identifier(table)})"
        ).fetchall():
            if not row[2]:
                continue
            index_name = str(row[1])
            columns = tuple(
                str(item[2])
                for item in cursor.execute(
                    f"PRAGMA index_info({self._quote_identifier(index_name)})"
                ).fetchall()
            )
            if columns != ("name",):
                continue
            sql_row = cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,),
            ).fetchone()
            indexes.append(
                (index_name, str(sql_row[0]) if sql_row and sql_row[0] else None)
            )
        return indexes

    def _has_pilot_identity_schema_migration(
        self, cursor: sqlite3.Cursor
    ) -> bool:
        pilots = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pilots'"
        ).fetchone()
        if pilots is None:
            return False
        if self._pilot_name_unique_indexes(cursor):
            return True
        binding = cursor.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='pilot_slot_bindings'"
        ).fetchone()
        if binding is None:
            return True
        index = cursor.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='index' AND name='idx_pilots_name'"
        ).fetchone()
        return index is None

    def _has_campaign_namespace_schema_migration(
        self, cursor: sqlite3.Cursor
    ) -> bool:
        binding = cursor.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='pilot_slot_bindings'"
        ).fetchone()
        if binding is None:
            return False
        info = cursor.execute(
            "PRAGMA table_info(pilot_slot_bindings)"
        ).fetchall()
        columns = {str(row[1]) for row in info}
        primary_key = tuple(
            str(row[1]) for row in sorted(info, key=lambda item: item[5]) if row[5]
        )
        return (
            "campaign_namespace" not in columns
            or primary_key != ("campaign_namespace", "slot")
        )

    def _has_legacy_namespace_reconciliation(
        self, cursor: sqlite3.Cursor
    ) -> bool:
        if not self._configured_campaign_namespaces:
            return False
        columns = {
            str(row[1])
            for row in cursor.execute(
                "PRAGMA table_info(pilot_slot_bindings)"
            ).fetchall()
        }
        if "campaign_namespace" not in columns:
            return False
        return cursor.execute(
            "SELECT 1 FROM pilot_slot_bindings "
            "WHERE campaign_namespace=? LIMIT 1",
            (LEGACY_CAMPAIGN_NAMESPACE,),
        ).fetchone() is not None

    @staticmethod
    def _create_namespaced_binding_table(
        cursor: sqlite3.Cursor, table_name: str
    ) -> None:
        quoted = DatabaseManager._quote_identifier(table_name)
        cursor.execute(
            f"""
            CREATE TABLE {quoted} (
                campaign_namespace TEXT NOT NULL
                    CHECK(length(campaign_namespace) > 0),
                slot INTEGER NOT NULL CHECK(slot > 0),
                pilotId TEXT NOT NULL,
                dossier_digest TEXT,
                last_updated TEXT NOT NULL,
                PRIMARY KEY(campaign_namespace, slot),
                FOREIGN KEY(pilotId) REFERENCES pilots(id)
            )
            """
        )

    def _legacy_campaign_namespace(self, *, has_bindings: bool) -> str:
        if has_bindings and len(self._configured_campaign_namespaces) > 1:
            raise SchemaCompatibilityError(
                "Legacy pilot-slot bindings cannot be assigned across multiple "
                "campaign namespaces"
            )
        if len(self._configured_campaign_namespaces) == 1:
            return self._configured_campaign_namespaces[0]
        return LEGACY_CAMPAIGN_NAMESPACE

    def _migrate_campaign_namespace_schema(
        self, cursor: sqlite3.Cursor
    ) -> None:
        """Replace the global slot key with ``(campaign_namespace, slot)``."""

        if not self._has_campaign_namespace_schema_migration(cursor):
            return
        info = cursor.execute(
            "PRAGMA table_info(pilot_slot_bindings)"
        ).fetchall()
        columns = {str(row[1]) for row in info}
        required = {"slot", "pilotId", "dossier_digest", "last_updated"}
        if not required.issubset(columns):
            raise SchemaCompatibilityError(
                "Cannot migrate an incomplete pilot-slot binding table"
            )
        count = int(
            cursor.execute(
                "SELECT COUNT(*) FROM pilot_slot_bindings"
            ).fetchone()[0]
        )
        has_namespace = "campaign_namespace" in columns
        if has_namespace:
            namespaces = {
                str(row[0])
                for row in cursor.execute(
                    "SELECT DISTINCT campaign_namespace "
                    "FROM pilot_slot_bindings"
                ).fetchall()
            }
            if any(
                not is_campaign_namespace(namespace, allow_legacy=True)
                for namespace in namespaces
            ):
                raise SchemaCompatibilityError(
                    "Pilot-slot bindings contain an unsupported campaign namespace"
                )
        target_namespace = self._legacy_campaign_namespace(
            has_bindings=bool(count) and not has_namespace
        )
        dependent_sql = self._dependent_sql_for_table(
            cursor, "pilot_slot_bindings"
        )
        new_table = self._unique_temp_table_name(
            cursor, "pilot_slot_bindings"
        )
        self._create_namespaced_binding_table(cursor, new_table)
        if has_namespace:
            cursor.execute(
                f"""
                INSERT INTO {self._quote_identifier(new_table)} (
                    campaign_namespace, slot, pilotId,
                    dossier_digest, last_updated
                )
                SELECT campaign_namespace, slot, pilotId,
                       dossier_digest, last_updated
                FROM pilot_slot_bindings
                """
            )
        else:
            cursor.execute(
                f"""
                INSERT INTO {self._quote_identifier(new_table)} (
                    campaign_namespace, slot, pilotId,
                    dossier_digest, last_updated
                )
                SELECT ?, slot, pilotId, dossier_digest, last_updated
                FROM pilot_slot_bindings
                """,
                (target_namespace,),
            )
        cursor.execute("DROP TABLE pilot_slot_bindings")
        cursor.execute(
            f"ALTER TABLE {self._quote_identifier(new_table)} "
            "RENAME TO pilot_slot_bindings"
        )
        for sql in dependent_sql:
            cursor.execute(sql)
        log.info(
            "  [Migração] Bindings de slot separados por namespace de campanha."
        )

    def _reconcile_legacy_campaign_namespace(
        self, cursor: sqlite3.Cursor
    ) -> None:
        """Assign a reserved legacy binding only when one root is configured."""

        if not self._has_legacy_namespace_reconciliation(cursor):
            return
        if len(self._configured_campaign_namespaces) != 1:
            raise SchemaCompatibilityError(
                "Legacy pilot-slot bindings are ambiguous across configured roots"
            )
        target = self._configured_campaign_namespaces[0]
        conflict = cursor.execute(
            """
            SELECT 1
            FROM pilot_slot_bindings AS legacy
            JOIN pilot_slot_bindings AS current
              ON current.slot = legacy.slot
             AND current.campaign_namespace = ?
            WHERE legacy.campaign_namespace = ?
            LIMIT 1
            """,
            (target, LEGACY_CAMPAIGN_NAMESPACE),
        ).fetchone()
        if conflict is not None:
            raise SchemaCompatibilityError(
                "Legacy pilot-slot bindings conflict with the configured namespace"
            )
        cursor.execute(
            "UPDATE pilot_slot_bindings SET campaign_namespace=? "
            "WHERE campaign_namespace=?",
            (target, LEGACY_CAMPAIGN_NAMESPACE),
        )
        log.info(
            "  [Migração] Namespace legado associado à única raiz configurada."
        )

    def _migrate_pilot_identity_schema(self, cursor: sqlite3.Cursor) -> None:
        """Remove display-name uniqueness without changing IDs or relationships."""

        forbidden_indexes = self._pilot_name_unique_indexes(cursor)
        if not forbidden_indexes:
            return

        original_row = cursor.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='pilots' AND sql IS NOT NULL"
        ).fetchone()
        if original_row is None:
            raise SchemaCompatibilityError(
                "Cannot migrate pilot identity without canonical pilots DDL"
            )

        dependent_sql = self._dependent_sql_for_table(cursor, "pilots")
        forbidden_sql = {
            sql for _name, sql in forbidden_indexes if sql is not None
        }
        compatible_sql = [sql for sql in dependent_sql if sql not in forbidden_sql]
        new_table = self._unique_temp_table_name(cursor, "pilots")
        rewritten = self._rewrite_pilot_identity_table_sql(
            str(original_row[0]), "pilots", new_table
        )
        cursor.execute(rewritten)
        if self._pilot_name_unique_indexes(cursor, new_table):
            raise SchemaCompatibilityError(
                "Pilot identity migration retained a forbidden UNIQUE(name)"
            )

        old_columns = [
            str(row[1])
            for row in cursor.execute("PRAGMA table_info(pilots)").fetchall()
        ]
        new_columns = [
            str(row[1])
            for row in cursor.execute(
                f"PRAGMA table_info({self._quote_identifier(new_table)})"
            ).fetchall()
        ]
        if new_columns != old_columns:
            raise SchemaCompatibilityError(
                "Pilot identity migration changed the pilots column contract"
            )
        columns = ", ".join(self._quote_identifier(column) for column in old_columns)
        cursor.execute(
            f"INSERT INTO {self._quote_identifier(new_table)} ({columns}) "
            f"SELECT {columns} FROM pilots"
        )
        cursor.execute("DROP TABLE pilots")
        cursor.execute(
            f"ALTER TABLE {self._quote_identifier(new_table)} RENAME TO pilots"
        )
        for sql in compatible_sql:
            cursor.execute(sql)
        log.info(
            "  [Migração] Unicidade de nome removida; IDs de carreira preservados."
        )

    def _rewrite_pilot_identity_table_sql(
        self, sql: str, table: str, new_table: str
    ) -> str:
        """Rewrite only the pilots display-name UNIQUE constraint."""

        self._reject_unsupported_sql_comments(sql)
        prefix_end = self._create_table_name_end(sql)
        open_paren = sql.find("(", prefix_end)
        if open_paren == -1:
            raise ValueError(
                f"Unsupported CREATE TABLE format for {table}: missing column list"
            )
        close_paren = self._matching_paren(sql, open_paren)
        definitions = self._split_top_level_csv(sql[open_paren + 1 : close_paren])
        rewritten: List[str] = []
        removed = False
        for definition in definitions:
            column_name = self._definition_column_name(definition)
            if column_name == "name":
                value, count = re.subn(
                    r"\s+UNIQUE(?:\s+ON\s+CONFLICT\s+"
                    r"(?:ROLLBACK|ABORT|FAIL|IGNORE|REPLACE))?",
                    "",
                    definition,
                    count=1,
                    flags=re.IGNORECASE,
                )
                rewritten.append(value)
                removed = removed or count == 1
                continue
            normalized = re.sub(r'[\s"`\[\]]+', "", definition).upper()
            if re.fullmatch(
                r"(?:CONSTRAINT[A-Z_][A-Z0-9_]*)?UNIQUE\(NAME\)"
                r"(?:ONCONFLICT(?:ROLLBACK|ABORT|FAIL|IGNORE|REPLACE))?",
                normalized,
            ):
                removed = True
                continue
            rewritten.append(definition)
        if not removed:
            # A unique index created outside the table still requires a rebuild
            # so dependent objects are recreated without that incompatible index.
            rewritten = definitions
        suffix = sql[close_paren + 1 :]
        return (
            f"CREATE TABLE {self._quote_identifier(new_table)} ("
            + ",".join(rewritten)
            + ")"
            + suffix
        )

    def _seed_unambiguous_slot_bindings(self, cursor: sqlite3.Cursor) -> None:
        """Seed pre-binding databases only when one namespace is knowable."""

        groups: Dict[int, set[str]] = {}
        pilot_columns = {
            str(row[1])
            for row in cursor.execute("PRAGMA table_info(pilots)").fetchall()
        }
        if not {"id", "source_file"}.issubset(pilot_columns):
            return
        rows = cursor.execute(
            "SELECT id, source_file FROM pilots "
            "WHERE source_file IS NOT NULL AND TRIM(source_file) != ''"
        ).fetchall()
        for pilot_id, source_file in rows:
            slot = pilot_slot(str(source_file))
            if slot is not None:
                groups.setdefault(slot, set()).add(str(pilot_id))
        unambiguous = {
            slot: next(iter(pilot_ids))
            for slot, pilot_ids in groups.items()
            if len(pilot_ids) == 1
        }
        campaign_namespace = self._legacy_campaign_namespace(
            has_bindings=bool(groups)
        )
        last_updated = datetime.now().isoformat()
        for slot, pilot_id in unambiguous.items():
            cursor.execute(
                """
                INSERT OR IGNORE INTO pilot_slot_bindings (
                    campaign_namespace, slot, pilotId,
                    dossier_digest, last_updated
                ) VALUES (?, ?, ?, NULL, ?)
                """,
                (campaign_namespace, slot, pilot_id, last_updated),
            )


    def _unique_temp_table_name(self, cursor: sqlite3.Cursor, table: str) -> str:
        counter = 0
        while True:
            name = f"__woff_migration_{table}_{os.getpid()}_{time.time_ns()}_{counter}"
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE name = ? UNION ALL "
                "SELECT 1 FROM sqlite_temp_master WHERE name = ?",
                (name, name),
            )
            if cursor.fetchone() is None:
                return name
            counter += 1

    def _create_rebuild_table_from_schema(
        self, cursor: sqlite3.Cursor, table: str, new_table: str, numeric_columns: List[str]
    ) -> None:
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ? AND sql IS NOT NULL",
            (table,),
        )
        row = cursor.fetchone()
        if row is None:
            self._create_table(cursor, table, new_table)
            return
        sql = self._rewrite_create_table_sql(row[0], table, new_table, numeric_columns)
        cursor.execute(sql)

    def _rewrite_create_table_sql(
        self, sql: str, table: str, new_table: str, numeric_columns: List[str]
    ) -> str:
        self._reject_unsupported_sql_comments(sql)
        prefix_end = self._create_table_name_end(sql)
        open_paren = sql.find("(", prefix_end)
        if open_paren == -1:
            raise ValueError(f"Unsupported CREATE TABLE format for {table}: missing column list")
        close_paren = self._matching_paren(sql, open_paren)
        definitions = self._split_top_level_csv(sql[open_paren + 1:close_paren])
        numeric_set = set(numeric_columns)
        rewritten_defs: List[str] = []
        migrated: set[str] = set()
        for definition in definitions:
            column_name = self._definition_column_name(definition)
            if column_name in numeric_set:
                rewritten_defs.append(self._rewrite_numeric_column_definition(definition, column_name))
                migrated.add(column_name)
            else:
                rewritten_defs.append(definition)
        missing = numeric_set - migrated
        if missing:
            raise ValueError(f"Unsupported CREATE TABLE format for {table}: missing columns {sorted(missing)}")
        suffix = sql[close_paren + 1:]
        return f"CREATE TABLE {self._quote_identifier(new_table)} (" + ",".join(rewritten_defs) + ")" + suffix

    @staticmethod
    def _reject_unsupported_sql_comments(sql: str) -> None:
        if "--" in sql or "/*" in sql or "*/" in sql:
            raise ValueError("Unsupported CREATE TABLE format: SQL comments are not supported")

    def _create_table_name_end(self, sql: str) -> int:
        match = re.match(
            r"\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?",
            sql,
            flags=re.IGNORECASE,
        )
        if match is None:
            raise ValueError("Unsupported CREATE TABLE format")
        index = match.end()
        _, index = self._read_identifier(sql, index)
        return index

    def _matching_paren(self, sql: str, open_paren: int) -> int:
        depth = 0
        quote: Optional[str] = None
        index = open_paren
        while index < len(sql):
            char = sql[index]
            if quote:
                if char == quote:
                    if index + 1 < len(sql) and sql[index + 1] == quote and quote in {"'", '"'}:
                        index += 2
                        continue
                    quote = None
            elif char in {"'", '"', '`'}:
                quote = char
            elif char == "[":
                quote = "]"
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return index
            index += 1
        raise ValueError("Unsupported CREATE TABLE format: unbalanced parentheses")

    def _split_top_level_csv(self, text: str) -> List[str]:
        parts: List[str] = []
        start = 0
        depth = 0
        quote: Optional[str] = None
        index = 0
        while index < len(text):
            char = text[index]
            if quote:
                if char == quote:
                    if index + 1 < len(text) and text[index + 1] == quote and quote in {"'", '"'}:
                        index += 2
                        continue
                    quote = None
            elif char in {"'", '"', '`'}:
                quote = char
            elif char == "[":
                quote = "]"
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                parts.append(text[start:index])
                start = index + 1
            index += 1
        parts.append(text[start:])
        return parts

    def _definition_column_name(self, definition: str) -> Optional[str]:
        stripped = definition.lstrip()
        keyword = stripped.split(None, 1)[0].upper() if stripped.split(None, 1) else ""
        if keyword in {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "EXCLUDE"}:
            return None
        try:
            name, _ = self._read_identifier(stripped, 0)
        except ValueError as exc:
            if "escaped delimiters" in str(exc):
                raise
            return None
        return name

    def _rewrite_numeric_column_definition(self, definition: str, column_name: str) -> str:
        leading_len = len(definition) - len(definition.lstrip())
        _, after_name = self._read_identifier(definition, leading_len)
        type_start = self._skip_space(definition, after_name)
        type_end = self._read_type_end(definition, type_start)
        column_type = definition[type_start:type_end]
        if not self._is_supported_text_type(column_type):
            raise ValueError(
                f"Unsupported numeric column type for {column_name}: {column_type!r}"
            )
        return definition[:type_start] + "INTEGER" + definition[type_end:]

    def _read_identifier(self, text: str, index: int) -> Tuple[str, int]:
        index = self._skip_space(text, index)
        if index >= len(text):
            raise ValueError("missing identifier")
        quote = text[index]
        closing = {"\"": "\"", "'": "'", "`": "`", "[": "]"}.get(quote)
        if closing:
            current = index + 1
            chars: List[str] = []
            while current < len(text):
                if text[current] == closing:
                    if current + 1 < len(text) and text[current + 1] == closing:
                        raise ValueError("Unsupported identifier: escaped delimiters are not supported")
                    return "".join(chars), current + 1
                chars.append(text[current])
                current += 1
            raise ValueError("unterminated quoted identifier")
        match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", text[index:])
        if match is None:
            raise ValueError("unsupported identifier")
        return match.group(0), index + len(match.group(0))

    @staticmethod
    def _skip_space(text: str, index: int) -> int:
        while index < len(text) and text[index].isspace():
            index += 1
        return index

    def _read_type_end(self, text: str, index: int) -> int:
        index = self._skip_space(text, index)
        if index >= len(text):
            raise ValueError("missing column type")
        depth = 0
        end = index
        while end < len(text):
            char = text[end]
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and (char.isspace() or char == ","):
                break
            end += 1
        return end

    @staticmethod
    def _is_supported_text_type(column_type: str) -> bool:
        normalized = re.sub(r"\s+", "", column_type.upper())
        return normalized in {"TEXT", "CLOB"} or bool(
            re.fullmatch(r"(?:VAR)?CHAR\(\d+\)", normalized)
        )

    def _validate_rebuild_schema(
        self, cursor: sqlite3.Cursor, table: str, new_table: str, numeric_columns: List[str]
    ) -> None:
        cursor.execute(f"PRAGMA table_info({new_table})")
        new_info = {row[1]: row for row in cursor.fetchall()}
        for column in numeric_columns:
            if new_info.get(column, (None, None, ""))[2].upper() != "INTEGER":
                raise sqlite3.DatabaseError(
                    f"Rebuilt table {table}.{column} does not have INTEGER type"
                )

        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        )
        original_sql = cursor.fetchone()[0]
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (new_table,),
        )
        rebuilt_sql = cursor.fetchone()[0]
        expected_sql = self._rewrite_create_table_sql(original_sql, table, new_table, numeric_columns)
        if self._normalize_sql(expected_sql) != self._normalize_sql(rebuilt_sql):
            raise sqlite3.DatabaseError(f"Rebuilt table {table} did not preserve schema")
        for column in numeric_columns:
            original_tail = self._column_definition_tail(original_sql, column)
            rebuilt_tail = self._column_definition_tail(rebuilt_sql, column)
            if self._normalize_sql(original_tail) != self._normalize_sql(rebuilt_tail):
                raise sqlite3.DatabaseError(
                    f"Rebuilt table {table}.{column} did not preserve column constraints"
                )

    def _column_definition_tail(self, sql: str, column: str) -> str:
        prefix_end = self._create_table_name_end(sql)
        open_paren = sql.find("(", prefix_end)
        close_paren = self._matching_paren(sql, open_paren)
        definitions = self._split_top_level_csv(sql[open_paren + 1:close_paren])
        for definition in definitions:
            if self._definition_column_name(definition) == column:
                leading_len = len(definition) - len(definition.lstrip())
                _, after_name = self._read_identifier(definition, leading_len)
                type_start = self._skip_space(definition, after_name)
                type_end = self._read_type_end(definition, type_start)
                return definition[type_end:]
        raise ValueError(f"missing column definition for {column}")

    @staticmethod
    def _normalize_sql(sql: str) -> str:
        return re.sub(r"\s+", " ", sql.strip()).upper()

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    @classmethod
    def _integer_select_expression(cls, column: str) -> str:
        quoted = cls._quote_identifier(column)
        return (
            f"CASE WHEN {quoted} IS NULL OR TRIM({quoted}) = '' THEN NULL "
            f"ELSE woff_safe_int({quoted}) END AS {quoted}"
        )

    @staticmethod
    def _parse_sqlite_integer(value: object) -> Optional[int]:
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return None
        if not re.fullmatch(r"[+-]?[0-9]+", text):
            raise ValueError(f"invalid integer literal: {value!r}")
        integer = int(text, 10)
        if integer < -(2 ** 63) or integer > 2 ** 63 - 1:
            raise OverflowError(f"integer literal outside signed 64-bit range: {value!r}")
        return integer

    def _validate_integer_values(
        self, cursor: sqlite3.Cursor, table: str, columns: List[str]
    ) -> None:
        invalid: List[str] = []
        for column in columns:
            quoted = self._quote_identifier(column)
            cursor.execute(
                f"SELECT id, {quoted} FROM {self._quote_identifier(table)} "
                f"WHERE {quoted} IS NOT NULL AND TRIM({quoted}) != ''"
            )
            for row_id, value in cursor.fetchall():
                try:
                    self._parse_sqlite_integer(value)
                except (OverflowError, ValueError) as exc:
                    invalid.append(f"{table}.{column} id={row_id!r} value={value!r} ({exc})")
        if invalid:
            raise ValueError("Invalid integer values found during migration: " + "; ".join(invalid))

    def _dependent_sql_for_table(self, cursor: sqlite3.Cursor, table: str) -> List[str]:
        cursor.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL AND type = 'view' "
            "ORDER BY name"
        )
        view_rows = cursor.fetchall()
        view_names = [row[0] for row in view_rows]

        cursor.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL AND type IN ('index', 'trigger') "
            "ORDER BY CASE type WHEN 'index' THEN 0 ELSE 1 END, name"
        )
        object_rows = cursor.fetchall()
        table_objects = [row for row in object_rows if row[2] == table]
        view_triggers = [row for row in object_rows if row[2] in view_names]

        for name in view_names:
            cursor.execute(f"DROP VIEW IF EXISTS {self._quote_identifier(name)}")

        return (
            [row[1] for row in view_rows]
            + [row[3] for row in table_objects if row[0] == "index"]
            + [row[3] for row in table_objects if row[0] == "trigger"]
            + [row[3] for row in view_triggers]
        )

    def _create_table(self, cursor: sqlite3.Cursor, table: str, table_name: Optional[str] = None) -> None:
        statements = {
            "pilots": """
                CREATE TABLE pilots (
                    id TEXT PRIMARY KEY, name TEXT, fName TEXT, sName TEXT,
                    nation TEXT, rank TEXT, squadron TEXT, aircraft TEXT,
                    aerodrome TEXT, sector TEXT, startDate TEXT, enlisted TEXT,
                    status TEXT, notes TEXT, photo TEXT, birthDate TEXT,
                    birthPlace TEXT, missions INTEGER, flminutes INTEGER,
                    claimsCount INTEGER, killsCount INTEGER, skill INTEGER,
                    reputation INTEGER, source_file TEXT, last_updated TEXT
                )
            """,
            "missions": """
                CREATE TABLE missions (
                    id TEXT PRIMARY KEY, pilotId TEXT, date TEXT, time TEXT,
                    missionType TEXT, aircraft TEXT, duration TEXT, altitude TEXT,
                    sector TEXT, squadron TEXT, weather TEXT, enemyContacts INTEGER,
                    claimsCount INTEGER, result TEXT, damageReceived INTEGER,
                    woundsReceived INTEGER, notes TEXT, source_file TEXT,
                    UNIQUE(pilotId, date, time, missionType, aircraft),
                    FOREIGN KEY(pilotId) REFERENCES pilots(id)
                )
            """,
            "squad_members": """
                CREATE TABLE squad_members (
                    id TEXT PRIMARY KEY, pilotId TEXT, rank TEXT, fName TEXT,
                    sName TEXT, skill INTEGER, morale INTEGER, status TEXT,
                    missions INTEGER, flminutes INTEGER, bio TEXT,
                    UNIQUE(pilotId, fName, sName),
                    FOREIGN KEY(pilotId) REFERENCES pilots(id)
                )
            """,
        }
        target_name = self._quote_identifier(table_name or table)
        statement = statements[table].replace(f"CREATE TABLE {table}", f"CREATE TABLE {target_name}", 1)
        cursor.execute(statement)

    def get_pilot_state(self, pilot_name: str) -> Tuple[Optional[str], Optional[str]]:
        return self._pilots.get_pilot_state(pilot_name)

    def get_pilot_state_by_id(
        self, pilot_id: str
    ) -> Tuple[Optional[str], Optional[str]]:
        return self._pilots.get_pilot_state_by_id(pilot_id)

    def resolve_bound_dossier_id(
        self, name: str, campaign_namespace: str, slot: int
    ) -> Optional[str]:
        return self._pilots.resolve_bound_dossier_id(
            name, campaign_namespace, slot
        )

    def load_dossier_state(
        self, name: str, campaign_namespace: str, slot: int
    ) -> Optional[DossierState]:
        """Load pilot, binding, and roster state inside a caller-owned transaction."""
        with self._lock:
            connection = self._get_conn()
            if not connection.in_transaction:
                raise RuntimeError(
                    "Dossier state requires a caller-owned transaction"
                )
            pilot = connection.execute(
                """
                SELECT p.id, p.status, p.rank, p.squadron,
                       binding.dossier_digest
                FROM pilot_slot_bindings AS binding
                JOIN pilots AS p ON p.id = binding.pilotId
                WHERE binding.campaign_namespace = ?
                  AND binding.slot = ? AND p.name = ?
                """,
                (campaign_namespace, slot, name),
            ).fetchone()
            if pilot is None:
                return None

            roster = connection.execute(
                "SELECT value FROM meta WHERE key = ?",
                (f"{_DOSSIER_ROSTER_META_PREFIX}{pilot[0]}",),
            ).fetchone()
            if roster is None:
                wingmen = [
                    tuple(str(value or "") for value in row)
                    for row in connection.execute(
                        """
                        SELECT fName, sName, status
                        FROM squad_members
                        WHERE pilotId = ?
                        ORDER BY fName COLLATE NOCASE, sName COLLATE NOCASE, id
                        """,
                        (pilot[0],),
                    ).fetchall()
                ]
            else:
                try:
                    decoded = json.loads(str(roster[0]))
                    valid = isinstance(decoded, list) and all(
                        isinstance(item, list)
                        and len(item) == 3
                        and all(isinstance(value, str) for value in item)
                        for item in decoded
                    )
                    if not valid:
                        raise ValueError("invalid roster payload")
                    wingmen = [tuple(item) for item in decoded]
                except (TypeError, ValueError, json.JSONDecodeError) as error:
                    raise sqlite3.DatabaseError(
                        "Invalid persisted Dossier roster state"
                    ) from error
            return DossierState(
                pilot_id=str(pilot[0]),
                status=str(pilot[1]) if pilot[1] is not None else None,
                rank=str(pilot[2]) if pilot[2] is not None else None,
                squadron=str(pilot[3] or ""),
                dossier_digest=(
                    str(pilot[4]) if pilot[4] is not None else None
                ),
                wingmen=tuple(
                    DossierWingmanState(
                        first_name=str(row[0] or ""),
                        last_name=str(row[1] or ""),
                        status=str(row[2] or ""),
                    )
                    for row in wingmen
                ),
            )

    def save_dossier_roster_state(
        self, pilot_id: str, wingmen: List[WoFFWingman]
    ) -> None:
        """Record the current roster without retiring historical wingman rows."""
        if not wingmen:
            return
        with self._lock:
            connection = self._get_conn()
            if not connection.in_transaction:
                raise RuntimeError(
                    "Dossier roster state requires a caller-owned transaction"
                )
            roster = sorted(
                [[wingman.fName, wingman.sName, wingman.status] for wingman in wingmen],
                key=lambda item: (item[0].casefold(), item[1].casefold()),
            )
            connection.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (
                    f"{_DOSSIER_ROSTER_META_PREFIX}{pilot_id}",
                    json.dumps(roster, ensure_ascii=True, separators=(",", ":")),
                ),
            )

    def resolve_pilot_id(
        self,
        name: str,
        source_file: Optional[str] = None,
        campaign_namespace: Optional[str] = None,
    ) -> Optional[str]:
        return self._pilots.resolve_pilot_id(
            name, source_file, campaign_namespace
        )

    def merge_and_write(
        self,
        pilot: Optional[WoFFPilot],
        missions: List[WoFFMission],
        victories: List[WoFFVictory],
        decorations: List[WoFFDecoration],
        wingmen: Optional[List[WoFFWingman]] = None,
        *,
        identity: Optional[PilotIdentityEvidence] = None,
    ) -> Optional[str]:
        """Faz o merge dos novos dados na base de dados SQLite. Retorna o pilot_id ou None."""
        try:
            with self.transaction():
                related = [*missions, *victories, *decorations, *(wingmen or [])]
                related_pilot_ids = [item.pilotId for item in related]
                pilot_id = self._pilots.upsert_pilot(
                    pilot,
                    missions,
                    victories,
                    identity,
                    related_pilot_ids,
                )
                if not pilot_id:
                    return None
                mission_counts, added_v, added_d = self._missions.upsert_mission(
                    pilot_id, missions, victories, decorations
                )
                added_w = self._wingmen.upsert_wingmen_batch(pilot_id, wingmen)
                if missions:
                    log.info(
                        "Mission merge outcomes: inserted=%d updated=%d unchanged=%d",
                        mission_counts.inserted,
                        mission_counts.updated,
                        mission_counts.unchanged,
                    )
                if added_v or added_d or added_w:
                    log.info(
                        f"  + {added_v} vitórias, {added_d} condecorações, "
                        f"{added_w} wingmen inseridos."
                    )
                self._get_conn().execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_updated', ?)",
                    (datetime.now().isoformat(),)
                )
                return pilot_id
        except sqlite3.IntegrityError as e:
            log.error(f"Erro de integridade na base de dados: {e}")
            return None
        except PilotIdentityError:
            # The application boundary emits one sanitized identity diagnostic.
            # Do not duplicate it here with a traceback.
            raise
        except Exception:
            log.exception("Erro ao escrever na base de dados")
            raise

    def get_pilot_id_by_name(self, pilot_name: str) -> Optional[str]:
        return self._pilots.get_pilot_id_by_name(pilot_name)

    def get_wingmen_by_pilot(self, pilot_id: str) -> List[dict]:
        return self._wingmen.get_wingmen_by_pilot(pilot_id)

    def get_mission_and_history(
        self, pilot_identifier: str, mission_id: str
    ) -> Tuple[Optional[dict], Optional[dict], List[dict]]:
        return self._pilots.get_mission_and_history(pilot_identifier, mission_id)

    def get_mission_id_by_natural_key(
        self, pilot_id: str, mission: WoFFMission
    ) -> Optional[str]:
        """Return the persisted ID selected by the mission natural key."""
        return self._missions.get_id_by_natural_key(pilot_id, mission)

    def get_pilot_game_date(self, pilot_id: str) -> Optional[str]:
        return self._pilots.get_pilot_game_date(pilot_id)

    def update_pilot_rpg_stats(
        self, pilot_id: str, fatigue: int, morale: int, stress: int
    ) -> None:
        return self._rpg.update_pilot_rpg_stats(pilot_id, fatigue, morale, stress)

    def save_diary_entry(
        self, pilot_id: str, mission_id: Optional[str], entry_date: str, narrative: str
    ) -> bool:
        return self._rpg.save_diary_entry(pilot_id, mission_id, entry_date, narrative)

    def get_wingman_personality(self, wingman_id: str) -> Optional[dict]:
        return self._wingmen.get_wingman_personality(wingman_id)

    def save_wingman_personality(
        self, wingman_id: str, pilot_id: str, personality: dict
    ) -> bool:
        return self._wingmen.save_wingman_personality(wingman_id, pilot_id, personality)

    def save_wingman_memory(
        self, wingman_id: str, event_type: str, event_date: str,
        description: str, impact_morale: int = 0, impact_stress: int = 0
    ) -> bool:
        return self._wingmen.save_wingman_memory(
            wingman_id, event_type, event_date, description, impact_morale, impact_stress
        )
