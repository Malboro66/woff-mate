import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from woff import __version__
from woff.config import UnsupportedConfigVersion, WatchdogConfig, load_config
from woff.database import (
    DatabaseManager,
    SCHEMA_TABLES,
    SchemaCompatibilityError,
    UnsupportedSchemaVersion,
)
from woff.version import CONFIG_VERSION, SCHEMA_VERSION


def _write_versioned_database(path: Path, version: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE pilots (
                id TEXT PRIMARY KEY, name TEXT UNIQUE, fName TEXT, sName TEXT,
                nation TEXT, rank TEXT, squadron TEXT, aircraft TEXT,
                aerodrome TEXT, sector TEXT, startDate TEXT, enlisted TEXT,
                status TEXT, notes TEXT, photo TEXT, birthDate TEXT,
                birthPlace TEXT, missions TEXT, flminutes TEXT,
                claimsCount TEXT, killsCount TEXT, skill TEXT,
                reputation TEXT, source_file TEXT, last_updated TEXT
            );
            CREATE TABLE missions (
                id TEXT PRIMARY KEY, pilotId TEXT, date TEXT, time TEXT,
                missionType TEXT, aircraft TEXT, duration TEXT, altitude TEXT,
                sector TEXT, squadron TEXT, weather TEXT, enemyContacts TEXT,
                claimsCount TEXT, result TEXT, damageReceived INTEGER,
                woundsReceived INTEGER, notes TEXT, source_file TEXT,
                UNIQUE(pilotId, date, time, missionType, aircraft),
                FOREIGN KEY(pilotId) REFERENCES pilots(id)
            );
            CREATE TABLE squad_members (
                id TEXT PRIMARY KEY, pilotId TEXT, rank TEXT, fName TEXT,
                sName TEXT, skill TEXT, morale TEXT, status TEXT,
                missions TEXT, flminutes TEXT, bio TEXT,
                UNIQUE(pilotId, fName, sName),
                FOREIGN KEY(pilotId) REFERENCES pilots(id)
            );
            """
        )
        conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (version,))


def _meta(path: Path) -> dict[str, str]:
    with sqlite3.connect(path) as conn:
        return dict(conn.execute("SELECT key, value FROM meta"))


def _dump(path: Path) -> str:
    with sqlite3.connect(path) as conn:
        return "\n".join(conn.iterdump())


def _mark_for_failed_certification(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE meta SET value='2.2' WHERE key='schema_version'")
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('app_version', 'legacy-app')"
    )


def test_legacy_config_ignores_schema_version_and_preserves_personal_values(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "watch_paths": ["personal/path"],
                "export_path": "personal.db",
                "export_schema_version": "2.2",
            }
        ),
        encoding="utf-8",
    )

    config = load_config(str(path))

    assert config.watch_paths == ["personal/path"]
    assert config.export_path == "personal.db"
    assert config.config_version == CONFIG_VERSION
    assert "export_schema_version" not in config.to_dict()
    assert "app_version" not in config.to_dict()


def test_current_config_has_own_version_and_no_database_or_app_version():
    config = WatchdogConfig(export_path="personal.db").to_dict()

    assert config["config_version"] == CONFIG_VERSION
    assert config["export_path"] == "personal.db"
    assert "export_schema_version" not in config
    assert "app_version" not in config


def test_future_config_is_rejected_instead_of_silently_normalized(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"config_version": "999"}), encoding="utf-8")

    with pytest.raises(UnsupportedConfigVersion, match="999"):
        load_config(str(path))


@pytest.mark.parametrize("invalid", ["2.0", 2.0, "text", "", "2"])
def test_invalid_and_future_config_version_formats_fail_closed(tmp_path, invalid):
    path = tmp_path / "config.json"
    original = json.dumps({"config_version": invalid, "export_path": "personal.db"})
    path.write_text(original, encoding="utf-8")

    with pytest.raises(UnsupportedConfigVersion):
        load_config(str(path))

    assert path.read_text(encoding="utf-8") == original


def test_new_database_gets_current_versions_and_reopens(tmp_path):
    path = tmp_path / "new.sqlite"

    manager = DatabaseManager(str(path))
    manager.close()
    reopened = DatabaseManager(str(path))
    reopened.close()

    assert _meta(path)["schema_version"] == SCHEMA_VERSION
    assert _meta(path)["app_version"] == __version__


def test_known_2_2_database_migrates_with_backup_and_reopens(tmp_path):
    path = tmp_path / "legacy.sqlite"
    _write_versioned_database(path, "2.2")

    manager = DatabaseManager(str(path))
    manager.close()
    reopened = DatabaseManager(str(path))
    reopened.close()

    assert _meta(path)["schema_version"] == SCHEMA_VERSION
    assert list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    with sqlite3.connect(path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(pilots)")}
        assert columns.issuperset(SCHEMA_TABLES["pilots"])
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("INSERT INTO pilots (id, name) VALUES ('p1', 'Pilot')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO pilots (id, name) VALUES ('p2', 'Pilot')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO missions (id, pilotId) VALUES ('m1', 'missing')")


def test_current_3_1_database_opens_normally(tmp_path):
    path = tmp_path / "current.sqlite"
    manager = DatabaseManager(str(path))
    manager.close()
    reopened = DatabaseManager(str(path))
    reopened.close()

    assert _meta(path)["schema_version"] == SCHEMA_VERSION
    assert not list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))


def test_future_database_is_rejected_without_any_changes(tmp_path, caplog):
    path = tmp_path / "future.sqlite"
    _write_versioned_database(path, "99.0")
    before = path.read_bytes()

    with pytest.raises(UnsupportedSchemaVersion, match="schema futuro 99.0"):
        DatabaseManager(str(path))

    assert path.read_bytes() == before
    assert _meta(path)["schema_version"] == "99.0"
    assert not list(tmp_path.glob("future.sqlite-*"))
    assert not (tmp_path / ".woff-migration-backups").exists()
    assert "Backup de migração criado:" not in caplog.text
    assert "Restauração automática" not in caplog.text


def test_future_schema_committed_in_wal_is_seen_and_files_are_unchanged(tmp_path):
    path = tmp_path / "future-wal.sqlite"
    writer = sqlite3.connect(path)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        writer.execute("INSERT INTO meta VALUES ('schema_version', '99.0')")
        writer.commit()
        files = [path, Path(f"{path}-wal")]
        before = {file: file.read_bytes() for file in files}

        with pytest.raises(UnsupportedSchemaVersion, match="99.0"):
            DatabaseManager(str(path))

        assert {file: file.read_bytes() for file in files} == before
        assert Path(f"{path}-shm").exists()
        assert not (tmp_path / ".woff-migration-backups").exists()
    finally:
        writer.close()


def test_schema_changed_after_pre_read_is_rejected_inside_transaction(tmp_path, monkeypatch):
    path = tmp_path / "race.sqlite"
    _write_versioned_database(path, "2.2")
    original_read = DatabaseManager._read_schema_version
    after_external_commit = {}

    def read_then_upgrade(self):
        version = original_read(self)
        with sqlite3.connect(path) as other:
            other.execute("UPDATE meta SET value='99.0' WHERE key='schema_version'")
        after_external_commit["database"] = path.read_bytes()
        return version

    monkeypatch.setattr(DatabaseManager, "_read_schema_version", read_then_upgrade)
    with pytest.raises(UnsupportedSchemaVersion, match="99.0"):
        DatabaseManager(str(path))

    assert path.read_bytes() == after_external_commit["database"]
    assert _meta(path)["schema_version"] == "99.0"
    assert not list(tmp_path.glob("race.sqlite-*"))
    assert not (tmp_path / ".woff-migration-backups").exists()


def test_nonempty_legacy_database_without_meta_is_backed_up_and_migrated(tmp_path):
    path = tmp_path / "no-meta.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE personal_data (value TEXT)")
        conn.execute("INSERT INTO personal_data VALUES ('preserve me')")

    manager = DatabaseManager(str(path))
    manager.close()

    assert _meta(path)["schema_version"] == SCHEMA_VERSION
    assert list((tmp_path / ".woff-migration-backups").glob("*.backup.sqlite"))
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT value FROM personal_data").fetchone() == ("preserve me",)


def test_unsupported_partial_2_2_schema_is_restored_without_certification(tmp_path):
    path = tmp_path / "partial.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO meta VALUES ('schema_version', '2.2');
            CREATE TABLE pilots (id TEXT PRIMARY KEY, name TEXT, missions TEXT);
            INSERT INTO pilots VALUES ('p1', 'Pilot', '3');
            """
        )
    before = _dump(path)

    with pytest.raises(SchemaCompatibilityError, match="missing column pilots.nation"):
        DatabaseManager(str(path))

    assert _dump(path) == before
    assert _meta(path)["schema_version"] == "2.2"


def test_schema_validation_failure_restores_original_database(tmp_path, monkeypatch):
    path = tmp_path / "validation-failure.sqlite"
    _write_versioned_database(path, "2.2")
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO pilots (id, name, missions) VALUES ('p1', 'Pilot', '4')")
    before = _dump(path)
    original_validation = DatabaseManager._validate_schema_contract

    def reject_schema(self, cursor):
        raise SchemaCompatibilityError("simulated certification failure")

    monkeypatch.setattr(DatabaseManager, "_validate_schema_contract", reject_schema)
    with pytest.raises(SchemaCompatibilityError, match="simulated certification failure"):
        DatabaseManager(str(path))

    assert _dump(path) == before
    assert _meta(path)["schema_version"] == "2.2"
    monkeypatch.setattr(DatabaseManager, "_validate_schema_contract", original_validation)
    reopened = DatabaseManager(str(path))
    reopened.close()
    assert _meta(path)["schema_version"] == SCHEMA_VERSION


def test_partial_pilots_name_index_cannot_replace_full_unique_constraint(tmp_path):
    path = tmp_path / "partial-pilots-unique.sqlite"
    manager = DatabaseManager(str(path))
    manager.close()
    with sqlite3.connect(path) as conn:
        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='pilots'"
        ).fetchone()[0]
        conn.execute("PRAGMA legacy_alter_table=ON")
        conn.execute("ALTER TABLE pilots RENAME TO pilots_old")
        conn.execute(table_sql.replace("name TEXT UNIQUE", "name TEXT"))
        conn.execute("DROP TABLE pilots_old")
        conn.execute(
            "CREATE UNIQUE INDEX partial_pilots_name ON pilots(name) "
            "WHERE name IS NOT NULL"
        )
        _mark_for_failed_certification(conn)
    before = _dump(path)

    with pytest.raises(SchemaCompatibilityError, match="missing UNIQUE pilots"):
        DatabaseManager(str(path))

    assert _dump(path) == before
    assert _meta(path)["schema_version"] == "2.2"
    assert _meta(path)["app_version"] == "legacy-app"


@pytest.mark.parametrize(
    ("index_sql", "error"),
    [
        (
            "CREATE UNIQUE INDEX idx_diary_unique_mission "
            "ON diary_entries(pilotId, missionId) WHERE pilotId IS NOT NULL",
            "wrong predicate",
        ),
        (
            "CREATE INDEX idx_diary_unique_mission "
            "ON diary_entries(pilotId, missionId) WHERE missionId IS NOT NULL",
            "missing required partial unique index",
        ),
    ],
)
def test_invalid_diary_index_is_rejected_and_restored(tmp_path, index_sql, error):
    path = tmp_path / "wrong-diary-predicate.sqlite"
    manager = DatabaseManager(str(path))
    manager.close()
    with sqlite3.connect(path) as conn:
        conn.execute("DROP INDEX idx_diary_unique_mission")
        conn.execute(index_sql)
        _mark_for_failed_certification(conn)
    before = _dump(path)

    with pytest.raises(SchemaCompatibilityError, match=error):
        DatabaseManager(str(path))

    assert _dump(path) == before
    assert _meta(path)["schema_version"] == "2.2"
    assert _meta(path)["app_version"] == "legacy-app"


@pytest.mark.parametrize(
    "keys",
    [
        "pilotId COLLATE NOCASE, missionId",
        "pilotId DESC, missionId",
        "missionId, pilotId",
        "pilotId",
        "pilotId, missionId, lower(pilotId)",
    ],
)
def test_noncanonical_diary_index_keys_are_rejected_and_restored(tmp_path, keys):
    path = tmp_path / "wrong-diary-keys.sqlite"
    manager = DatabaseManager(str(path))
    manager.close()
    with sqlite3.connect(path) as conn:
        conn.execute("DROP INDEX idx_diary_unique_mission")
        conn.execute(
            f"CREATE UNIQUE INDEX idx_diary_unique_mission "
            f"ON diary_entries({keys}) WHERE missionId IS NOT NULL"
        )
        _mark_for_failed_certification(conn)
    before = _dump(path)

    with pytest.raises(SchemaCompatibilityError, match="wrong key semantics"):
        DatabaseManager(str(path))

    assert _dump(path) == before
    assert _meta(path)["schema_version"] == "2.2"
    assert _meta(path)["app_version"] == "legacy-app"


def test_canonical_unique_constraints_and_quoted_diary_predicate_certify(tmp_path):
    path = tmp_path / "canonical-indexes.sqlite"
    manager = DatabaseManager(str(path))
    manager.close()
    with sqlite3.connect(path) as conn:
        conn.execute("DROP INDEX idx_diary_unique_mission")
        conn.execute(
            'CREATE UNIQUE INDEX idx_diary_unique_mission '
            'ON diary_entries('
            'pilotId COLLATE BINARY ASC, missionId COLLATE BINARY ASC'
            ') WHERE "missionId" IS NOT NULL'
        )

    reopened = DatabaseManager(str(path))
    reopened.close()
    assert _meta(path)["schema_version"] == SCHEMA_VERSION


def test_failed_migration_keeps_old_version_then_database_can_reopen(tmp_path, monkeypatch):
    path = tmp_path / "legacy.sqlite"
    _write_versioned_database(path, "2.2")
    original = DatabaseManager._migrate_numeric_column_types

    def fail_migration(self, cursor):
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(DatabaseManager, "_migrate_numeric_column_types", fail_migration)
    with pytest.raises(RuntimeError, match="simulated migration failure"):
        DatabaseManager(str(path))

    assert _meta(path)["schema_version"] == "2.2"
    monkeypatch.setattr(DatabaseManager, "_migrate_numeric_column_types", original)
    reopened = DatabaseManager(str(path))
    reopened.close()
    assert _meta(path)["schema_version"] == SCHEMA_VERSION


def test_init_failure_after_migration_restores_old_version_and_reopens(tmp_path, monkeypatch):
    path = tmp_path / "init-failure.sqlite"
    _write_versioned_database(path, "2.2")
    original_init = DatabaseManager._init_db

    def fail_after_init(self):
        original_init(self)
        raise RuntimeError("simulated init failure")

    monkeypatch.setattr(DatabaseManager, "_init_db", fail_after_init)
    with pytest.raises(RuntimeError, match="simulated init failure"):
        DatabaseManager(str(path))

    assert _meta(path)["schema_version"] == "2.2"
    monkeypatch.setattr(DatabaseManager, "_init_db", original_init)
    reopened = DatabaseManager(str(path))
    reopened.close()
    assert _meta(path)["schema_version"] == SCHEMA_VERSION


def test_package_cli_config_example_and_version_consumers_are_consistent():
    root = Path(__file__).parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "woff.woff_watchdog", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    example = json.loads((root / "config.example.json").read_text(encoding="utf-8"))
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    build_spec = (root / "build.spec").read_text(encoding="utf-8")

    assert result.stdout.strip().endswith(__version__)
    assert example["config_version"] == CONFIG_VERSION
    assert "app_version" not in example
    assert "export_schema_version" not in example
    assert 'version = {attr = "woff.version.__version__"}' in pyproject
    assert 'runpy.run_path(str(Path(SPECPATH) / "woff" / "version.py"))' in build_spec
    assert "from woff" not in build_spec


def test_compatibility_guide_documents_approved_support_contract():
    root = Path(__file__).parents[2]
    guide = (root / "docs" / "compatibility.md").read_text(encoding="utf-8")
    for status in ("Supported", "Automatically validated", "Verified by sanitized samples", "Unconfirmed"):
        assert status in guide
    assert "Windows 10 64-bit" in guide
    assert "Windows 11 64-bit" in guide
    assert "Python 3.10 through 3.14" in guide
    assert "Linux" in guide and "Python 3.10 and 3.14" in guide
    assert "windows-latest" in guide and "Python 3.10" in guide
    assert "WOFF BH&H II" in guide
    assert "sanitized samples and regression fixtures" in guide
    assert "exact WoFF build is unconfirmed" in guide


def test_compatibility_guide_defines_safe_report_contents_and_prohibited_data():
    root = Path(__file__).parents[2]
    guide = (root / "docs" / "compatibility.md").read_text(encoding="utf-8")
    for safe_item in ("Windows version and architecture", "Python version", "WoFF Mate version", "exact command", "sanitized error message", "sanitized input structure"):
        assert safe_item in guide
    for prohibited_item in ("config.json", "SQLite databases", "PilotLog records", "mission notes", "narratives", "personal paths"):
        assert prohibited_item in guide


def test_database_migration_guide_documents_versioning_backup_and_recovery_contract():
    root = Path(__file__).parents[2]
    guide = (root / "docs" / "database-migrations.md").read_text(encoding="utf-8")
    assert f"Current schema: `{SCHEMA_VERSION}`" in guide
    assert "MAJOR.MINOR" in guide
    assert "MINOR" in guide and "compatible automatic migrations" in guide
    assert "MAJOR" in guide and "manual intervention" in guide
    assert "same transaction" in guide and "future schema" in guide
    for action in ("DDL", "backup", "downgrade", "sidecar"):
        assert action in guide
    for item in (".woff-migration-backups/", "<database>.YYYYMMDDHHMMSS[.<counter>].backup.sqlite", "Connection.backup()", "PRAGMA integrity_check", "without overwriting", "never deletes migration backups automatically"):
        assert item in guide
    for message in ("Backup de migração criado:", "Migração falhou. Restauração automática concluída a partir de:", "Migração falhou e a restauração automática também falhou. Backup preservado em:"):
        assert message in guide
    assert "PowerShell" in guide and "C:\\WoFFMate\\data" in guide
    assert "Test-Path -LiteralPath $Backup -PathType Leaf" in guide
    assert "mode=ro" in guide and "uri=True" in guide
    assert "Close every WoFF Mate process" in guide
    for sidecar in ("-wal", "-shm", "-journal"):
        assert sidecar in guide
    assert "safety directory" in guide
    assert "restore the original files" in guide
    assert "successful reopening" in guide


def test_user_guides_exist_and_readme_links_to_each_guide():
    root = Path(__file__).parents[2]
    readme = (root / "README.md").read_text(encoding="utf-8")
    for name in ("compatibility.md", "database-migrations.md", "troubleshooting.md"):
        assert (root / "docs" / name).is_file()
        assert f"docs/{name}" in readme


def test_readme_and_guides_preserve_the_approved_compatibility_contract():
    root = Path(__file__).parents[2]
    readme = (root / "README.md").read_text(encoding="utf-8")
    compatibility = (root / "docs" / "compatibility.md").read_text(encoding="utf-8")
    migrations = (root / "docs" / "database-migrations.md").read_text(encoding="utf-8")
    assert "Python da versão 3.10 até a 3.14" in readme
    assert "Windows 10 de 64 bits" in readme and "Windows 11 de 64 bits" in readme
    assert "WOFF BH&H II" in readme and "amostras sanitizadas" in readme
    assert "versão exata do WoFF ainda não foi confirmada" in readme
    assert "Python 3.10 through 3.14" in compatibility
    assert f"Current schema: `{SCHEMA_VERSION}`" in migrations


def test_troubleshooting_guide_covers_safe_diagnostics_and_recovery_messages():
    root = Path(__file__).parents[2]
    guide = (root / "docs" / "troubleshooting.md").read_text(encoding="utf-8")
    for item in ("PowerShell", "woff-watchdog --version", "future schema", "database is locked", "Backup de migração criado:", "Migração falhou. Restauração automática concluída a partir de:", "Migração falhou e a restauração automática também falhou. Backup preservado em:", "unknown WoFF format"):
        assert item in guide
    for prohibited in ("config.json", "SQLite databases", "migration backups", "complete PilotLog records", "pilot notes", "mission narratives"):
        assert prohibited in guide


def test_documentation_examples_do_not_contain_personal_home_paths():
    root = Path(__file__).parents[2]
    documents = [root / "README.md", *sorted((root / "docs").glob("*.md"))]
    for document in documents:
        contents = document.read_text(encoding="utf-8")
        for personal_root in ("C:\\Users", "/Users/", "/home/", "/root/"):
            assert personal_root not in contents, f"{personal_root} in {document}"
