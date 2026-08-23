# Database migrations and recovery

This guide describes the existing migration safeguards and an offline manual recovery procedure.

## Schema compatibility

Current schema: `3.2`, sourced from `woff.version.SCHEMA_VERSION`.

Schema versions use `MAJOR.MINOR`:

- schema versions identify stored database formats;
- future schema versions are rejected;
- an automatic migration is supported only when the installed application has a compatible migration path and the resulting schema passes certification;
- `2.2` to `3.2` and `3.1` to `3.2` are tested historical migration paths; and
- the **MAJOR** component alone does not determine whether migration is automatic.

The application persists the new schema version in the same transaction as the schema and data changes. A database declaring a future schema is rejected before application DDL, a migration backup, or any downgrade. During the read-only compatibility probe, SQLite may open or create WAL coordination sidecars such as `-shm`; this is SQLite coordination rather than application DDL or migration. Use a compatible newer version instead.

## Schema 3.2 career identity migration

Schema 3.2 removes the uniqueness constraint from `pilots.name`. A display name
is presentation data and may belong to more than one career. The migration
rebuilds the table without changing existing pilot IDs, then preserves the
foreign-key ownership of missions, victories, decorations, squad members, RPG
state, and diary entries. A non-unique `idx_pilots_name` remains available for
lookup.

The new `pilot_slot_bindings` table records one current `pilotId` for each
positive WoFF pilot slot together with the verified Dossier digest. Migration
seeds a binding only when legacy source filenames identify exactly one pilot for
that slot. Ambiguous slots remain unbound. Every migrated binding starts with a
NULL digest and therefore rejects `Log`, `Claims`, and `Squads` writes until a
stable `Pilot{N}Dossier.txt` snapshot refreshes it.

A Dossier whose display name changes in an already bound slot creates a new
career and rotates only the current binding. The prior pilot row, relationships,
RPG state, and diary remain attached to the prior ID. A matching-name Dossier in
the same slot is currently treated as a replay of the bound career; distinguishing
a same-name replacement in that same slot requires sanitized longitudinal WOFF
fixtures and is tracked separately with `needs-real-fixture`.

Live XML and `Mission.log` ingestion cannot establish a supported career
identity and performs no persistent write. Slot-dependent files require both a
current binding and an exact match with the stable sibling Dossier digest.

The 3.1-to-3.2 transformation uses the same pre-migration SQLite backup and
transactional rollback procedure described below. Certification requires
`PRAGMA foreign_key_check` to return no rows, `PRAGMA integrity_check` to return
`ok`, and the migrated database to reopen under the current schema contract.
The migration backup is retained after both successful migration and recovery.

## Automatic migration protection

Before changing a supported existing database, WoFF Mate creates a consistent SQLite backup under `.woff-migration-backups/`, beside the active database. Its filename follows `<database>.YYYYMMDDHHMMSS[.<counter>].backup.sqlite`; for example, `.woff-migration-backups/woff.sqlite.20260812120000.backup.sqlite`. A numeric counter is added on collision, ensuring unique names without overwriting an earlier backup.

The backup uses SQLite `Connection.backup()`, not a live-file copy. The success message is emitted only after `Connection.backup()` completes, `PRAGMA integrity_check` succeeds, and both SQLite connections close. Directory synchronization is requested through `_fsync_directory()` only on platforms supported by that implementation. Windows does not receive the same directory-`fsync` guarantee. The message confirms a validated backup; it does not guarantee that the file will survive a sudden power loss.

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

If a recorded backup disappears before restoration, restoration fails without claiming that the backup was preserved:

```text
Migração falhou e o backup de migração registrado está indisponível em: <sanitized backup path>
```

## Offline manual restoration on Windows

Use this only after automatic recovery failed or under support guidance. These neutral PowerShell examples use `C:\WoFFMate\data\woff.sqlite`.

1. **Close every WoFF Mate process**, terminal, watchdog, and SQLite viewer. Restoration must be offline.
2. Create a uniquely named safety directory and preserve the active database plus SQLite `-wal`, `-shm`, and `-journal` files:

   ```powershell
   $ErrorActionPreference = 'Stop'
   $Data = 'C:\WoFFMate\data'
   $Database = Join-Path $Data 'woff.sqlite'
   $Safety = Join-Path $Data ('recovery-safety-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
   if (-not (Test-Path -LiteralPath $Database -PathType Leaf)) {
     throw 'Active database not found'
   }
   New-Item -ItemType Directory -Path $Safety -ErrorAction Stop | Out-Null
   $Sources = @($Database, "$Database-wal", "$Database-shm", "$Database-journal") |
     Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
   foreach ($Source in $Sources) {
     Copy-Item -LiteralPath $Source -Destination $Safety -ErrorAction Stop
     $Destination = Join-Path $Safety (Split-Path -Leaf $Source)
     if (-not (Test-Path -LiteralPath $Destination -PathType Leaf)) {
       throw "Safety copy missing: $Destination"
     }
     if ((Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash -ne
         (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash) {
       throw "Safety copy hash mismatch: $Destination"
     }
   }
   ```

3. Restore the preserved backup into a uniquely named temporary database in the same directory as the active database. The Python command opens and validates the backup source first through an absolute, read-only URI, keeps that source connection open throughout restoration, and validates the temporary database. Both `PRAGMA integrity_check` calls must return exactly `ok`, and `PRAGMA foreign_key_check` must return no rows. It exits nonzero if opening, copying, or validation fails, without opening or changing the active database or its sidecars:

   ```powershell
   $Backup = Join-Path $Data '.woff-migration-backups\woff.sqlite.20260812120000.backup.sqlite'
   $Staging = Join-Path $Data ('.woff-restore-' + [guid]::NewGuid().ToString('N') + '.sqlite')
   $RestoreScript = @'
   import sqlite3, sys
   from pathlib import Path

   source_uri = Path(sys.argv[1]).resolve().as_uri() + '?mode=ro'
   source = sqlite3.connect(source_uri, uri=True)
   try:
       if source.execute('PRAGMA integrity_check').fetchone() != ('ok',):
           raise RuntimeError('Migration backup integrity check failed')
       staging = sqlite3.connect(sys.argv[2])
       try:
           source.backup(staging)
           integrity = staging.execute('PRAGMA integrity_check').fetchone()
           foreign_keys = staging.execute('PRAGMA foreign_key_check').fetchall()
           if integrity != ('ok',) or foreign_keys != []:
               raise RuntimeError('Staging database validation failed')
       finally:
           staging.close()
   finally:
       source.close()
   '@
   python -c $RestoreScript $Backup $Staging
   if ($LASTEXITCODE -ne 0) {
     if (Test-Path -LiteralPath $Staging -PathType Leaf) {
       Remove-Item -LiteralPath $Staging -ErrorAction Stop
     }
     throw 'Backup staging or validation failed; active database was not changed'
   }
   ```

4. Only after the safety copy and staging validation succeed, remove the offline active database and sidecars, then move the validated staging database into place:

   ```powershell
   @($Database, "$Database-wal", "$Database-shm", "$Database-journal") |
     Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
     ForEach-Object { Remove-Item -LiteralPath $_ -ErrorAction Stop }
   Move-Item -LiteralPath $Staging -Destination $Database -ErrorAction Stop
   ```

5. Validate the installed database again through an absolute, read-only URI. The command cannot create a missing database and exits nonzero if the database is missing, unreadable, invalid, or does not return exactly `ok` with no foreign-key rows:

   ```powershell
   if (-not (Test-Path -LiteralPath $Database -PathType Leaf)) {
     throw 'Installed database not found'
   }
   $ValidationScript = @'
   import sqlite3, sys
   from pathlib import Path

   database_uri = Path(sys.argv[1]).resolve().as_uri() + '?mode=ro'
   database = sqlite3.connect(database_uri, uri=True)
   try:
       integrity = database.execute('PRAGMA integrity_check').fetchone()
       foreign_keys = database.execute('PRAGMA foreign_key_check').fetchall()
       if integrity != ('ok',) or foreign_keys != []:
           raise RuntimeError('Installed database validation failed')
   finally:
       database.close()
   '@
   python -c $ValidationScript $Database
   if ($LASTEXITCODE -ne 0) {
     throw 'Installed database validation failed'
   }
   ```

6. Reopen WoFF Mate and verify the expected campaign information. Keep both the migration backup and safety copy until validation and successful reopening are complete.

If any recovery step fails, close every process again, preserve the failed result separately, and restore the original files (database, WAL, SHM, and journal) from the safety directory. Keep both the backup and safety copy until recovery and reopening succeed.
