# Database migrations and recovery

This guide describes the existing migration safeguards and an offline manual recovery procedure.

## Schema compatibility

Current schema: `3.5`, sourced from `woff.version.SCHEMA_VERSION`.

Schema versions use `MAJOR.MINOR`:

- schema versions identify stored database formats;
- future schema versions are rejected;
- an automatic migration is supported only when the installed application has a compatible migration path and the resulting schema passes certification;
- `2.2` to `3.2` and `3.1` to `3.2` remain tested historical migration paths;
- `2.2`, `3.1`, `3.2`, `3.3`, and `3.4` to `3.5` are tested current migration paths; and
- the **MAJOR** component alone does not determine whether migration is automatic.

The application persists the new schema version in the same transaction as the schema and data changes. A database declaring a future schema is rejected before application DDL, a migration backup, or any downgrade. During the read-only compatibility probe, SQLite may open or create WAL coordination sidecars such as `-shm`; this is SQLite coordination rather than application DDL or migration. Use a compatible newer version instead.

## Issue #96 wingman identity and roster state

Schema **3.5** advances the previous **3.4** contract for the incompatible
wingman layout. A binary supporting only 3.4 rejects a 3.5 database through the
future-schema guard, before DDL or writes; the application release version is
unchanged. The migration removes `UNIQUE(pilotId, fName, sName)` in any column
order (including equivalent non-partial unique indexes), adds
nullable `birthDate`, `evidenceDate`, and `evidenceLocation` reconciliation
evidence, and creates the non-unique, non-partial `idx_squad_members_pilot`
index keyed exactly on `pilotId`. A malformed reserved index schedules a
backed-up transactional repair even when the database already declares 3.5.
Layout certification checks both index semantics and removal of name uniqueness.
It preserves every existing `squad_members.id`, column value, compatible
index/trigger, and personality/memory foreign key. Legacy evidence remains
NULL; migration never invents identities or deduplicates historical rows.
The 3.4-to-3.5 change creates a consistent SQLite backup before modification;
transactional rollback, integrity/FK certification, and reopen remain mandatory.
Use the retained backup for recovery; do not downgrade by rebuilding
name uniqueness over the migrated data.

Dossier roster metadata now uses payload version 2. Each trusted or candidate
member is `[wingman_id, first_name, last_name, status]`, sorted by persistent ID
for serialization. IDs must be nonempty, unique within each roster, and owned
by the same pilot. Names are presentation only. The importer loads the previous
snapshot, merges/reconciles the incoming members, then reads this generation's
resolved IDs and effective stored statuses before deriving events. All these
operations, the binding digest, roster state, and diary writes share one
transaction. A missing source status therefore cannot erase a trusted status
or cause a duplicate transition when that status reappears.

Comparison, candidate confirmation, and wounded/KIA/missing/new derivation use
persistent IDs. Disappearances still require a matching roster in a different
Dossier generation. Replaying the same digest cannot confirm a candidate or
repeat diary events. Transfers establish a fresh baseline (or a pending one
when the roster is absent), retaining historical member rows and relationships.

Legacy list and version-1 payloads remain readable with unknown member IDs.
No name-based upgrade is attempted, even when a name currently looks unique:
a historical occurrence cannot be proven from that name. A trusted legacy
baseline without IDs rejects same-squadron comparison and rolls back the
incoming generation, preserving its previous snapshot and diary. An explicit
squadron transfer may establish a fresh resolved baseline without comparing
legacy members. Before reconciliation, that explicit boundary records the
persistent IDs of historical rows with wholly absent personal evidence in the
version-2 payload's optional `retired_wingman_ids` list. These rows are excluded
from subsequent candidate searches, including across a pending baseline,
candidate confirmation, and reopen. No row or relationship is removed, no name
is used to infer continuity, and partially populated evidence is not bypassed.
Absent retirement metadata defaults to an empty set; IDs must remain unique,
owned by the career, evidence-less, and outside the active/candidate roster.
An old untrusted list, or an empty pending baseline, can also
establish a new baseline without attributing historical events by name. Invalid
version-2 IDs (including duplicates or another pilot's IDs) reject the import.
Resolving a blocked trusted legacy baseline requires independent identity
evidence; automatic historical repair is outside this slice.

The compatibility `process_wingmen_changes` entry point accepts programmatic
persistent IDs only. Parsed Dossier members must use the atomic Dossier importer
so generation-local IDs cannot become comparison keys before reconciliation.

## Schema 3.4 victory occurrence migration

Issue #136 retains this schema unchanged. `pilots.nation` is the recoverable
source evidence; `NationService` derives the closed playable nation, separate
service and known/missing/unsupported state on read. Existing rows are not
rewritten, and no migration backup is created for this semantic interpretation.
Legacy compatibility, transaction rollback and reopen are tested. See
[the nation/service storage decision](architecture/nation-service.md).

Schema 3.4 removes the lossy victory uniqueness rule on
`(pilotId, date, time, enemyType)`. Those values describe a visible claim but
cannot identify one occurrence: two valid claims may share every value in that
tuple. The replacement `victory_source_records` table maps a privacy-safe,
versioned source-position digest to one stable victory ID. A second verified
position in the same source therefore remains a distinct row, while replaying
the same position resolves the existing row. Compatible records from another
source may become aliases of that row only when the match is unambiguous;
ambiguous records are left unchanged and reported as unresolved instead of
being guessed or silently discarded.

The canonical non-unique `idx_victories_pilot` index keeps first-import and
cross-source candidate lookups bounded to one pilot after the legacy composite
index is removed. New databases create it directly; migration detects and
repairs its absence after taking a backup, and schema certification verifies
its non-unique `pilotId` key semantics.

Existing victory IDs, pilot ownership, mission associations, and every victory
column are copied unchanged during the table rebuild. Existing rows begin with
no fabricated source alias. Their first deterministic replay may attach a
verified alias when exactly one compatible row exists. Decoration rows are not
rebuilt: their stable `(pilotId, name)` row is enriched in place under the same
non-destructive source-authority policy.

The 3.3-to-3.4 transformation is performed inside one migration transaction
after a validated SQLite backup. Failure rolls back and restores that backup.
Success requires `PRAGMA foreign_key_check`, `PRAGMA integrity_check`, complete
schema certification, and a successful close and reopen. The retained backup
continues to use the recovery procedure below.

## Schema 3.3 campaign namespace migration

Schema 3.3 replaces the global `pilot_slot_bindings.slot` primary key with the
composite key `(campaign_namespace, slot)`. A slot is now reusable across
configured campaign roots without allowing one root to replace another root's
active binding. Dossier, Log, Claims, and Squads processing carries the same
namespace to the persistence boundary, so a dependent file can resolve only the
career bound inside its own root.

The namespace is `root-v1:` plus the SHA-256 digest of the canonical configured
root. Canonicalization uses Windows path identity rules for drive-letter case,
separator aliases, `.`/`..`, UNC paths, and Win32 extended-length spellings.
The database and diagnostics retain only the versioned digest, never the raw
configured path. Duplicate or overlapping configured roots are rejected before
database or worker startup because a file would not have one unambiguous owner.

Existing 3.2 bindings require an explicit legacy decision:

- with exactly one configured root, every legacy binding is assigned to that
  root's namespace;
- with more than one configured root and any legacy binding, migration aborts
  and restores the verified backup instead of guessing ownership;
- when no root context is available, bindings use the documented reserved
  namespace `legacy-v3.2`; a later startup may assign it to exactly one
  configured root, while multi-root startup still aborts safely.

Pilot IDs and every existing mission, victory, decoration, squad member, RPG
state, and diary relationship remain unchanged. The 3.2-to-3.3 rebuild uses the
pre-migration SQLite backup and one transaction, then requires
`PRAGMA foreign_key_check`, `PRAGMA integrity_check`, schema certification, and
a successful reopen. The migration backup is retained after success or recovery.

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

Legacy career recovery is confined to those migration-seeded bindings. During
normal Dossier processing, an unbound `(campaign_namespace, slot)` always keeps
the incoming career ID; it never searches globally by display name and slot.
This prevents an unbound career retired in one campaign namespace from being
claimed by another namespace while preserving IDs and relationships whenever
migration established unambiguous ownership.

A Dossier whose display name changes in an already bound slot creates a new
career and rotates only the current binding. The prior pilot row, relationships,
RPG state, and diary remain attached to the prior ID. A matching-name Dossier in
the same slot is treated as a replay only while that binding remains current.
Confirmed vacancy releases the binding, so even a same-name arrival starts a new
career. Distinguishing replacement without an observed vacancy requires
sanitized longitudinal WOFF fixtures and remains tracked separately in #87
with `needs-real-fixture`.

Live XML and `Mission.log` ingestion cannot establish a supported career
identity and performs no persistent write. Slot-dependent files require both a
current binding and an exact match with the stable sibling Dossier digest.

The 3.1-to-3.2 transformation uses the same pre-migration SQLite backup and
transactional rollback procedure described below. Certification requires
`PRAGMA foreign_key_check` to return no rows, `PRAGMA integrity_check` to return
`ok`, and the migrated database to reopen under the current schema contract.
The migration backup is retained after both successful migration and recovery.

## Pilot-slot vacancy without a schema migration

Issue #122 keeps schema 3.4 unchanged. After a complete, stable absence
observation, one transaction compares the exact observed binding, deletes only
that `(campaign_namespace, slot)` binding, and advances its lifecycle counter in
the existing `meta` table under
`pilot_slot_vacancy:<campaign_namespace>:<slot>`. Missing counters mean zero.
This counter is not a pilot ID or military status; it prevents already retained
pre-vacancy snapshots from writing into a later career in the same slot.

The pilot, career namespace ownership, missions, victories, decorations, RPG,
diary, and squadron history are not rewritten or deleted. Existing databases
need no reseeding, DDL, or version change. A failed transaction rolls back both
the binding release and counter increment; a committed boundary survives reopen.
`woff/tests/test_pilot_vacancy.py` enforces rollback, historical preservation,
same-name reuse, reopen, integrity, and foreign-key checks. Normal export-backup
configuration remains applicable; this operation does not alter WoFF files.

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
