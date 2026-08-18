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

An existing malformed or invalid configuration is never replaced or repaired
automatically. Auto-detection and defaults apply only when the file is missing.

## Common database messages

### Future schema

A **future schema** error means the database was created by a newer, incompatible application version. WoFF Mate rejects it before migration or backup. Do not edit its version or attempt a downgrade. Install a compatible newer application and keep the database unchanged.

### `database is locked`

Close WoFF Mate, SQLite viewers, backup programs, and every process that could have the database open, then retry. Do not delete SQLite sidecars or copy a live database. If it continues, preserve the files and report a sanitized excerpt.

### Migration and restoration

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
