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

def get_db_path():
    config_path = "config.json"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg.get("export_path", "woff_data.db")
    return "woff_data.db"

def export_diary_to_file(conn, pilot_name: str, filepath: str):
    cursor = conn.execute("""
        SELECT d.id, d.entry_date, d.narrative
        FROM diary_entries d
        JOIN pilots p ON d.pilotId = p.id
        WHERE p.name = ?
        ORDER BY d.entry_date ASC
    """, (pilot_name,))
    entries = cursor.fetchall()
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"DIÁRIO DE BORDO DE {pilot_name.upper()}\n")
        f.write("INSTRUÇÕES: Edite o texto livremente. Para APAGAR uma entrada, apague o bloco inteiro (incluindo as linhas === ID === e DATA). Guarde e feche o ficheiro para aplicar as alterações.\n")
        f.write("=" * 60 + "\n")
        for entry in entries:
            f.write(f"=== ID: {entry['id']} ===\n")
            f.write(f"DATA: {entry['entry_date']}\n")
            f.write(f"{entry['narrative']}\n")
            f.write("=" * 60 + "\n")

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
        imported_entries.append((entry_id, entry_date, narrative))

    imported_ids = {entry[0] for entry in imported_entries if entry[2]}
    cursor = conn.cursor()
    owners = []
    transaction_started = False
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

        existing_ids = {row[0] for row in owners} if imported_ids else set()
        for entry_id, entry_date, narrative in imported_entries:
            if not narrative:
                continue
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
        conn.commit()
    except Exception:
        if transaction_started:
            conn.rollback()
        raise

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

def main():
    ap = argparse.ArgumentParser(description="WoFF Journal Editor - Editar o Diário de Bordo")
    ap.add_argument("--pilot", required=True, help="Nome do piloto")
    ap.add_argument("--db", default=None, help="Caminho direto para a base de dados SQLite")
    args = ap.parse_args()

    db_path = args.db if args.db else get_db_path()
    if not os.path.exists(db_path):
        print(f"[ERRO] Base de dados não encontrada: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Verificar se o piloto existe
    cursor = conn.execute("SELECT id FROM pilots WHERE name = ?", (args.pilot,))
    pilot = cursor.fetchone()
    if not pilot:
        print(f"[ERRO] Piloto '{args.pilot}' não encontrado.")
        sys.exit(1)

    # Criar ficheiro temporário
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp_path = tmp.name

    try:
        print(f"A exportar diário de {args.pilot} para {tmp_path}...")
        export_diary_to_file(conn, args.pilot, tmp_path)
        
        print("A abrir o editor de texto...")
        open_editor(tmp_path)
        
        print("A importar alterações do ficheiro...")
        import_diary_from_file(conn, tmp_path, pilot["id"])
        print("✓ Diário atualizado com sucesso na Base de Dados!")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        conn.close()

if __name__ == "__main__":
    main()
