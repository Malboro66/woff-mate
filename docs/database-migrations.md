# Database migrations and recovery

This guide describes the existing migration safeguards and an offline manual recovery procedure.

## Schema compatibility

Current schema: `3.1`, sourced from `woff.version.SCHEMA_VERSION`.

Schema versions use `MAJOR.MINOR`:

- increment **MINOR** for compatible automatic migrations;
- increment **MAJOR** for incompatible changes that require manual intervention.

The application persists the new schema version in the same transaction as the schema and data changes. A database declaring a future schema is rejected before application DDL, a migration backup, any downgrade, or creation of an application sidecar. Use a compatible newer version instead.

## Automatic migration protection

Before changing a supported existing database, WoFF Mate creates a consistent SQLite backup under `.woff-migration-backups/`, beside the active database. Its filename follows `<database>.YYYYMMDDHHMMSS[.<counter>].backup.sqlite`; for example, `.woff-migration-backups/woff.sqlite.20260812120000.backup.sqlite`. A numeric counter is added on collision, ensuring unique names without overwriting an earlier backup.

The backup uses SQLite `Connection.backup()`, not a live-file copy. WoFF Mate verifies `PRAGMA integrity_check`, closes both connections, and synchronizes the directory before reporting:

```text
Backup de migração criado: <sanitized backup path>
```

WoFF Mate never deletes migration backups automatically. All valid backups remain until manual removal, including after successful or failed restoration.

If migration fails and automatic restoration succeeds, the original migration error is raised after:

```text
Migração falhou. Restauração automática concluída a partir de: <sanitized backup path>
```

If both migration and restoration fail, the restoration error remains visible and the backup remains available:

```text
Migração falhou e a restauração automática também falhou. Backup preservado em: <sanitized backup path>
```

## Offline manual restoration on Windows

Use this only after automatic recovery failed or under support guidance. These neutral PowerShell examples use `C:\WoFFMate\data\woff.sqlite`.

1. **Close every WoFF Mate process**, terminal, watchdog, and SQLite viewer. Restoration must be offline.
2. Create a uniquely named safety directory and preserve the active database plus SQLite `-wal`, `-shm`, and `-journal` files:

   ```powershell
   $Data = 'C:\WoFFMate\data'
   $Database = Join-Path $Data 'woff.sqlite'
   $Safety = Join-Path $Data ('recovery-safety-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
   New-Item -ItemType Directory -Path $Safety | Out-Null
   @($Database, "$Database-wal", "$Database-shm", "$Database-journal") |
     Where-Object { Test-Path $_ } | Copy-Item -Destination $Safety
   ```

3. Select and validate a preserved backup before replacing anything. The check must print `ok`:

   ```powershell
   $Backup = Join-Path $Data '.woff-migration-backups\woff.sqlite.20260812120000.backup.sqlite'
   if (-not (Test-Path -LiteralPath $Backup -PathType Leaf)) {
     throw 'Migration backup not found'
   }
   python -c "import sqlite3,sys; from pathlib import Path; u=Path(sys.argv[1]).resolve().as_uri()+'?mode=ro'; c=sqlite3.connect(u,uri=True); print(c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()" $Backup
   ```

4. Only after the safety copy and validation, remove the offline database and sidecars, then restore through SQLite's backup API:

   ```powershell
   @($Database, "$Database-wal", "$Database-shm", "$Database-journal") |
     Where-Object { Test-Path $_ } | Remove-Item
   python -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" $Backup $Database
   ```

5. Validate the restored database. The results must be `ok` and no foreign-key rows:

   ```powershell
   python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print(c.execute('PRAGMA foreign_key_check').fetchall()); c.close()" $Database
   ```

6. Reopen WoFF Mate and verify the expected campaign information. Keep both the migration backup and safety copy until validation and successful reopening are complete.

If any recovery step fails, close every process again, preserve the failed result separately, and restore the original files (database, WAL, SHM, and journal) from the safety directory. Keep both the backup and safety copy until recovery and reopening succeed.
