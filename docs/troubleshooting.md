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

## Command exit status and output streams

`woff-watchdog`, `woff-query`, and `woff-report` expose stable process statuses:

- `0`: the requested operation completed successfully;
- `1`: parsing, SQLite, startup, report generation, or backup failed at runtime;
- `2`: the command input or configuration is invalid, or a required path or
  database is missing.

For `woff-query --format json|csv|md`, stdout contains only the selected data
format. Redirect stderr separately when automating the command. An empty result
is still a valid document: JSON emits `[]`, CSV emits its header, and Markdown
emits its header and separator. A selected pilot in a machine-readable format
must request exactly one of `--missions`, `--diary`, or `--wingmen`; use the
unselected form to list pilots and their stable IDs.

`woff-report` accepts `--config <path>`. If no configured watch root is a valid
directory, it exits with status `2` and does not create a report. A parse or
write failure exits with status `1`; the final report is replaced only after the
complete temporary artifact has been written successfully. Numeric zero and
Boolean false are preserved and are not labelled `Vazio`.

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

### Victory merge outcomes

`Victory merge outcomes` and `Decoration merge outcomes` report separate
`inserted`, `updated`, `unchanged`, and `unresolved` counts. An
`ambiguous-occurrence` warning means that a record from another source could
match more than one stored same-minute victory. WoFF Mate leaves the stable rows
unchanged instead of guessing. An `equal-authority-conflict` similarly preserves
the existing value until a higher-authority or same-source correction arrives.
`count-mismatch` means the mission's source claim count differs from the number
of currently associated victory rows; neither record is deleted or rewritten.
Report only the category and counters, never the claim text or database.

### Future schema

A **future schema** error means the database was created by a newer, incompatible application version. WoFF Mate rejects it before migration or backup. Do not edit its version or attempt a downgrade. Install a compatible newer application and keep the database unchanged.

### `database is locked`

The live ingestion path classifies verified SQLite busy, locked, locking-
protocol, and blocked-I/O results as transient persistence failures. It retains
at most one exact verified generation per already bounded scheduler path,
including the Dossier-backed identity used to route dependent pilot files. It
does not reopen mutable source bytes for a persistence replay.

Persistence retry is fixed and bounded: four total processing attempts with
0.1, 0.2, and 0.4 seconds of scheduler backoff. Each attempt uses the fixed
five-second SQLite busy timeout, so every individual lock wait is bounded and
the scheduler adds at most 0.7 seconds. Total processing time also depends on
the finite persistence work in the verified file. The latest newer event for
the same canonical path remains coalesced while the retained generation retries.
It runs only after the retained generation succeeds, exhausts its budget, or is
cancelled during shutdown. Replays remain subject to the existing natural-key
and transactional idempotence boundaries.

Startup reconciliation budgets each phase for every source snapshot, the
additional Dossier snapshot used by each dependent pilot file, all four SQLite
busy windows, the full 0.7 seconds of backoff, and a bounded phase margin. A
default five-second busy wait therefore cannot outlast a three-second
file-stability budget and silently cancel retained startup work.

The scheduler exposes separate `transient_failures`, `transient_retries`,
`successful_replays`, `permanent_rejections`, `saturated`, `retry_exhausted`,
`retry_shutdown`, and `superseded_retries` metrics. The last counter remains for
metric compatibility and stays zero because pending events no longer supersede
retained transient work. Parser, identity, snapshot, and other permanent
rejections do not enter the SQLite retry policy.

`Persistence retry exhausted` means all four attempts failed. Duplicate
notifications for the same unchanged generation do not start a fresh budget.
The final diagnostic contains only the source filename, sanitized SQLite
category, and attempt count. The active path is released, while its terminal
generation remains in a cache bounded by scheduler capacity. A late unchanged
notification is rejected without new persistence attempts. Changed bytes
receive their own bounded processing budget and replace the terminal marker if
they also exhaust retries.

During orderly shutdown, an active attempt finishes, each retained retry is
cancelled with a diagnostic, and an already accepted latest event receives one
drained attempt. If that event is also transient, it receives its own shutdown
diagnostic without starting backoff. The source remains recoverable on disk and
can be reconsidered by a later filesystem event or startup reconciliation.

If either final diagnostic recurs, close SQLite viewers, backup programs, and
every other writer before generating a new file event or restarting WoFF Mate.
Do not delete SQLite sidecars or copy a live database. Preserve the files and
report only a sanitized diagnostic excerpt.

### Migration and restoration

When upgrading a schema 3.2 database that already contains pilot-slot bindings,
configure exactly one watch root for the first current-schema startup. Multiple roots
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

### Optional export snapshot

When `backup_export` is `true` and the configured export database already
exists, watchdog startup creates a verified SQLite snapshot immediately before
normal campaign processing. The snapshot is stored beside the database as
`<database-name>.backup.sqlite`. A replacement becomes visible only after
`PRAGMA integrity_check` succeeds; a failed attempt preserves the previous
verified snapshot, removes its temporary file, reports the failure on stderr,
and exits with status `1`.

No optional snapshot is created when `backup_export` is `false` or when the
watchdog is creating its first database. These export snapshots do not replace
the mandatory, uniquely named backups used by schema migrations.

## Report an unknown WoFF format safely

An **unknown WoFF format** does not establish whether an entire build is supported. Report field names, ordering, delimiters, encoding, and the smallest synthetic example that reproduces the issue. State the WoFF Mate version and whether it repeats. Replace identities and values with synthetic placeholders.

Never share:

- `config.json` or configuration values;
- SQLite databases, database contents, or migration backups;
- complete PilotLog records;
- pilot notes or mission narratives; or
- personal paths, user names, or other personal information.

See [Compatibility](compatibility.md) for the full safe-reporting contract.
