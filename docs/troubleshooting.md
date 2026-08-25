# Troubleshooting

Collect only the minimum sanitized evidence needed to diagnose a problem.

## Collect diagnostics in PowerShell

Run these commands from the project directory and review the output before sharing:

```powershell
woff-watchdog --version
python --version
Get-ComputerInfo -Property WindowsProductName, WindowsVersion, OsArchitecture
```

Include the exact failed command and smallest relevant error excerpt. Replace user names, installation directories, and local paths with neutral placeholders such as `<installation>`. Do not upload an entire log.

## Invalid configuration

WoFF Mate validates `config.json` before opening the database or starting file
watchers and worker threads. Strings and paths must not be blank, workers and
stability values must be positive, the stability interval must be less than its
timeout, and watched extensions must be a supported subset of `.xml`, `.txt`,
and `.log`. Extension filtering applies both to initial synchronization and to
runtime file events. Supported log levels are
`DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL` (case-insensitive).

Configured watch roots must be distinct and non-overlapping. Equivalent Windows
spellings of one root—such as drive-letter case, slash direction, or a Win32
extended-length prefix—resolve to one namespace and therefore must not be listed
twice. A `duplicate or overlapping campaign roots` error contains no local path;
remove the duplicate or nested entry from `watch_paths`.

An existing malformed or invalid configuration is never replaced or repaired
automatically. Auto-detection and defaults apply only when the file is missing.

## Filesystem event saturation

`max_pending_events` limits the total number of unique filesystem paths admitted
for processing. Each admitted path has at most one active execution and one
latest pending generation; repeated events for that path are coalesced. The
scheduler never waits for capacity. It emits a warning and increments its local
`rejected` metric when a new path arrives at capacity or after shutdown begins.

If `Filesystem event rejected: scheduler saturated` repeats, first verify that
processing is not blocked by an inaccessible file or database. Then increase
`max_pending_events` only within the machine's memory budget. The diagnostic
intentionally omits campaign content and local paths. During an orderly stop,
new work is rejected and already accepted work is drained before exit.

## Snapshot acquisition messages

Before parsing, WoFF Mate reads each watched file into an immutable snapshot and
verifies its size, identity, timestamps, and complete bytes. A final
`Snapshot rejected` warning reports one of these sanitized states:

- `timeout`: the file remained empty or could not produce two identical verified
  observations within the configured time budget;
- `inaccessible`: the file disappeared or Windows temporarily denied access,
  including sharing violations;
- `changed-generation`: the file was rewritten, truncated, or replaced while it
  was being observed.

Acquisition retries use deterministic exponential backoff. Both the number of
attempts and the sum of delays are bounded by `stability_timeout_sec`, starting
from `stability_check_interval_sec`; no separate retry queue is created. If these
warnings recur, prefer increasing the timeout for files that take longer to
finish. The interval controls the initial retry delay and must remain less than
the timeout.

Snapshot failures occur before parsing. XML syntax errors, missing mission-log
blocks, unsupported filenames, and other format diagnostics instead mean that a
stable snapshot was acquired but its format could not be parsed. Share only the
state and a synthetic reproduction—never campaign contents, personal paths, or
complete records.

## Common database messages

### Future schema

A **future schema** error means the database was created by a newer, incompatible application version. WoFF Mate rejects it before migration or backup. Do not edit its version or attempt a downgrade. Install a compatible newer application and keep the database unchanged.

### `database is locked`

Close WoFF Mate, SQLite viewers, backup programs, and every process that could have the database open, then retry. Do not delete SQLite sidecars or copy a live database. If it continues, preserve the files and report a sanitized excerpt.

### Migration and restoration

When upgrading a schema 3.2 database that already contains pilot-slot bindings,
configure exactly one watch root for the first schema 3.3 startup. Multiple roots
make the legacy owner unknowable, so WoFF Mate aborts and restores the database
instead of assigning careers speculatively. After the single-root migration and
successful reopen, additional distinct roots can be configured normally.

A validated backup was created when you see the following message. On Windows,
this does not include a directory-`fsync` guarantee and does not guarantee survival after sudden power loss:

```text
Backup de migração criado: <sanitized backup path>
```

When migration fails but automatic restoration succeeds, the original error is raised and recovery is confirmed by:

```text
Migração falhou. Restauração automática concluída a partir de: <sanitized backup path>
```

If restoration also fails, stop using the database. The named backup is preserved:

```text
Migração falhou e a restauração automática também falhou. Backup preservado em: <sanitized backup path>
```

If a recorded backup is missing, restoration fails and this dedicated message does not claim preservation:

```text
Migração falhou e o backup de migração registrado está indisponível em: <sanitized backup path>
```

Keep every backup and follow the offline procedure in [Database migrations and recovery](database-migrations.md).

## Report an unknown WoFF format safely

An **unknown WoFF format** does not establish whether an entire build is supported. Report field names, ordering, delimiters, encoding, and the smallest synthetic example that reproduces the issue. State the WoFF Mate version and whether it repeats. Replace identities and values with synthetic placeholders.

Never share:

- `config.json` or configuration values;
- SQLite databases, database contents, or migration backups;
- complete PilotLog records;
- pilot notes or mission narratives; or
- personal paths, user names, or other personal information.

See [Compatibility](compatibility.md) for the full safe-reporting contract.
