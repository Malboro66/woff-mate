#!/usr/bin/env python3
"""
WoFF Journal Editor
══════════════════════════════════════════════════════════════════
Ferramenta que permite ao utilizador editar o seu Diário de Bordo.
Exporta o diário para um ficheiro de texto, abre o editor padrão,
e importa as alterações de volta para a Base de Dados.
══════════════════════════════════════════════════════════════════
"""
import os
import sys
import sqlite3
import json
import subprocess
import platform
import tempfile
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

from woff.career_selection import CareerResolutionError, resolve_career

def get_db_path():
    config_path = "config.json"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("export_path", "woff_data.db")
    return "woff_data.db"

def export_diary_to_file(conn, pilot_id: str, filepath: str):
    pilot = conn.execute(
        "SELECT name FROM pilots WHERE id = ?",
        (pilot_id,),
    ).fetchone()
    if pilot is None:
        raise ValueError(f"Selected pilot {pilot_id} no longer exists")
    pilot_name = str(pilot[0])
    cursor = conn.execute("""
        SELECT d.id, d.entry_date, d.narrative
        FROM diary_entries d
        WHERE d.pilotId = ?
        ORDER BY d.entry_date ASC
    """, (pilot_id,))
    entries = cursor.fetchall()
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"DIÁRIO DE BORDO DE {pilot_name.upper()}\n")
        f.write(f"CARREIRA ID: {pilot_id}\n")
        f.write(
            "INSTRUÇÕES: Edite o texto livremente. Uma narrativa vazia ou "
            "contendo apenas espaços invalida a importação e não altera a Base "
            "de Dados. Para APAGAR uma entrada, apague o bloco inteiro "
            "(incluindo as linhas === ID === e DATA). Guarde e feche o ficheiro "
            "para aplicar as alterações.\n"
        )
        f.write("=" * 60 + "\n")
        for entry in entries:
            f.write(f"=== ID: {entry['id']} ===\n")
            f.write(f"DATA: {entry['entry_date']}\n")
            f.write(f"{entry['narrative']}\n")
            f.write("=" * 60 + "\n")


def _database_path(conn) -> Path:
    for _, name, filename in conn.execute("PRAGMA database_list"):
        if name == "main" and filename:
            return Path(filename).resolve()
    raise RuntimeError("Diary backup requires a file-backed SQLite database")


def _reserve_backup_path(database_path: Path) -> Path:
    backup_dir = database_path.parent / ".woff-diary-backups"
    backup_dir.mkdir(mode=0o700, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    counter = 0
    while True:
        suffix = "" if counter == 0 else f".{counter}"
        candidate = backup_dir / (
            f"{database_path.name}.{timestamp}{suffix}.backup.sqlite"
        )
        try:
            descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            counter += 1
            continue
        try:
            os.close(descriptor)
        except Exception:
            candidate.unlink(missing_ok=True)
            raise
        return candidate


def _copy_database_backup(source, destination):
    source.backup(destination)


def _backup_integrity_check(conn):
    return conn.execute("PRAGMA integrity_check").fetchone()


def _commit_import(conn):
    conn.commit()


def _create_pre_import_backup(conn) -> Path:
    database_path = _database_path(conn)
    backup_path = None
    source = None
    destination = None
    try:
        backup_path = _reserve_backup_path(database_path)
        source_uri = database_path.as_uri() + "?mode=ro"
        source = sqlite3.connect(source_uri, uri=True)
        destination = sqlite3.connect(backup_path)
        _copy_database_backup(source, destination)
        if _backup_integrity_check(destination) != ("ok",):
            raise RuntimeError("Diary backup integrity check failed")
        destination.close()
        destination = None
        source.close()
        source = None
        return backup_path
    except Exception as exc:
        close_error = None
        for backup_conn in (destination, source):
            if backup_conn is not None:
                try:
                    backup_conn.close()
                except Exception as error:
                    close_error = error
        if backup_path is not None:
            try:
                backup_path.unlink(missing_ok=True)
            except Exception as error:
                raise RuntimeError(
                    f"Diary backup failed and incomplete backup could not be removed: {error}"
                ) from exc
        failure = close_error if close_error is not None else exc
        raise RuntimeError(f"Diary backup failed: {failure}") from exc

def import_diary_from_file(conn, filepath: str, pilot_id: str):
    """Replace one pilot's diary using a transaction owned by this function.

    The supplied connection must not have an active transaction. This function
    starts, commits, or rolls back its complete import transaction itself.
    """
    if conn.in_transaction:
        raise ValueError("Diary import requires a connection without an active transaction")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    imported_entries = []
    parsed_ids = set()
    blocks = content.split("=" * 60)[1:] # Ignora o cabeçalho inicial
    for block_number, block in enumerate(blocks, start=1):
        block = block.strip()
        if not block:
            continue

        lines = block.split("\n")
        id_line = lines[0]
        if not id_line.startswith("=== ID:") or not id_line.endswith("==="):
            raise ValueError(f"Diary block {block_number} is missing a valid ID field")
        entry_id = id_line[len("=== ID:"):-len("===")].strip()
        if not entry_id:
            raise ValueError(f"Diary block {block_number} has an empty ID field")
        if len(lines) < 2 or not lines[1].startswith("DATA:"):
            raise ValueError(f"Diary block {block_number} is missing a DATA field")
        entry_date = lines[1][len("DATA:"):].strip()
        if not entry_date:
            raise ValueError(f"Diary block {block_number} has an empty DATA field")
        if entry_id in parsed_ids:
            raise ValueError(f"Duplicate diary entry ID: {entry_id}")
        parsed_ids.add(entry_id)
        narrative = "\n".join(lines[2:]).strip()
        if not narrative:
            raise ValueError(
                f"Diary entry {entry_id} has an empty narrative. "
                "Remove the entire block to delete the entry."
            )
        imported_entries.append((entry_id, entry_date, narrative))

    imported_ids = set(parsed_ids)
    cursor = conn.cursor()
    owners = []
    transaction_started = False
    backup_path = None
    try:
        cursor.execute("BEGIN IMMEDIATE")
        transaction_started = True

        pilot_exists = cursor.execute(
            "SELECT 1 FROM pilots WHERE id = ?",
            (pilot_id,),
        ).fetchone()
        if pilot_exists is None:
            raise ValueError(f"Selected pilot {pilot_id} no longer exists")

        if parsed_ids:
            placeholders = ",".join("?" for _ in parsed_ids)
            owners = cursor.execute(
                f"SELECT id, pilotId FROM diary_entries WHERE id IN ({placeholders})",
                tuple(parsed_ids),
            ).fetchall()
            foreign_ids = [row[0] for row in owners if row[1] != pilot_id]
            if foreign_ids:
                raise ValueError(
                    f"Diary entry ID {foreign_ids[0]} does not belong to the selected pilot"
                )

        existing_ids = {row[0] for row in owners}
        for entry_id, entry_date, narrative in imported_entries:
            if entry_id in existing_ids:
                cursor.execute(
                    """
                    UPDATE diary_entries
                    SET entry_date = ?, narrative = ?
                    WHERE id = ? AND pilotId = ?
                    """,
                    (entry_date, narrative, entry_id, pilot_id),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO diary_entries
                        (id, pilotId, missionId, entry_date, narrative)
                    VALUES (?, ?, NULL, ?, ?)
                    """,
                    (entry_id, pilot_id, entry_date, narrative),
                )

        if imported_ids:
            placeholders = ",".join("?" for _ in imported_ids)
            cursor.execute(
                f"DELETE FROM diary_entries WHERE pilotId = ? AND id NOT IN ({placeholders})",
                (pilot_id, *imported_ids),
            )
        else:
            cursor.execute(
                "DELETE FROM diary_entries WHERE pilotId = ?",
                (pilot_id,),
            )
        backup_path = _create_pre_import_backup(conn)
    except Exception:
        if transaction_started:
            conn.rollback()
        raise
    try:
        _commit_import(conn)
    except Exception as commit_error:
        try:
            conn.rollback()
        except Exception as rollback_error:
            raise RuntimeError(
                f"Diary commit failed: {commit_error}; rollback also failed: "
                f"{rollback_error}. Verified backup retained at {backup_path}"
            ) from commit_error
        raise RuntimeError(
            f"Diary commit failed: {commit_error}. "
            f"Verified backup retained at {backup_path}"
        ) from commit_error
    return str(backup_path)

def open_editor(filepath: str):
    system = platform.system()
    if system == "Windows":
        startfile = getattr(os, "startfile", None)
        if not callable(startfile):
            raise RuntimeError("os.startfile não está disponível nesta instalação do Windows")
        startfile(filepath)
    elif system == "Darwin": # macOS
        subprocess.call(["open", filepath])
    else: # Linux
        subprocess.call(["xdg-open", filepath])
    
    input(f"\nPressione ENTER quando terminar de editar e guardar o ficheiro...")

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="WoFF Journal Editor - Editar o Diário de Bordo")
    selector = ap.add_mutually_exclusive_group(required=True)
    selector.add_argument("--pilot", help="Nome do piloto (deve ser único)")
    selector.add_argument("--pilot-id", help="ID persistente da carreira")
    ap.add_argument("--db", default=None, help="Caminho direto para a base de dados SQLite")
    args = ap.parse_args(argv)

    db_path = args.db if args.db else get_db_path()
    if not os.path.exists(db_path):
        print(f"[ERRO] Base de dados não encontrada: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tmp_path = None
    try:
        try:
            career = resolve_career(
                conn,
                pilot_id=args.pilot_id,
                pilot_name=args.pilot,
            )
        except CareerResolutionError as error:
            print(f"[ERRO] {error}", file=sys.stderr)
            return 2

        with tempfile.NamedTemporaryFile(
            mode="w+", suffix=".txt", delete=False, encoding="utf-8"
        ) as tmp:
            tmp_path = tmp.name

        print(
            f"A exportar diário de {career.name} "
            f"[{career.pilot_id}] para {tmp_path}..."
        )
        export_diary_to_file(conn, career.pilot_id, tmp_path)
        
        print("A abrir o editor de texto...")
        open_editor(tmp_path)
        
        print("A importar alterações do ficheiro...")
        try:
            backup_path = import_diary_from_file(conn, tmp_path, career.pilot_id)
        except ValueError as error:
            print(f"[ERRO] {error}", file=sys.stderr)
            return 2
        print(f"✓ Backup pré-importação guardado em: {backup_path}")
        print("✓ Diário atualizado com sucesso na Base de Dados!")
        return 0
    finally:
        if tmp_path is not None and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        conn.close()

if __name__ == "__main__":
    raise SystemExit(main())
