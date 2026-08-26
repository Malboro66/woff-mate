# Command-line contracts

WoFF Mate installs three public commands: `woff-watchdog`, `woff-query`, and
`woff-report`. Their process and stream behavior is part of the supported
automation interface.

## Exit statuses

| Status | Meaning |
|---|---|
| `0` | The requested operation completed successfully. |
| `1` | A parser, SQLite operation, startup component, report write, or export backup failed at runtime. |
| `2` | Input or configuration is invalid, or a required file, directory, or database is missing. |

Argument-parser errors also use status `2`. A fatal condition never returns
`0`. Human diagnostics go to stderr so a caller can redirect or parse stdout
independently.

## `woff-query`

The installed command and the repository-compatible `python woff_query.py`
launcher share one implementation. The query database is opened in SQLite
read-only mode and is never created as a side effect of a query.

Without a pilot selector, the command lists careers. Machine-readable lists
include `pilot_id` and the current slot when one is bound:

```powershell
woff-query --config config.json --format json
woff-query --db C:\WoFFMate\woff_data.db --format csv
```

With `--format json`, `csv`, or `md`, a selected career must request exactly one
detail collection:

```powershell
woff-query --pilot-id <stable-id> --missions --format json
woff-query --pilot-id <stable-id> --diary --format csv
woff-query --pilot-id <stable-id> --wingmen --format md
```

Empty successes preserve their selected format: JSON is `[]`, CSV contains its
header row, and Markdown contains its header and separator. No hint or
diagnostic is appended to structured stdout. The table format remains intended
for people and may show the profile, RPG state, and multiple requested detail
sections.

If an explicitly supplied database is missing, the command returns `2` without
creating it. An existing malformed configuration returns `2`; an invalid or
unreadable SQLite database returns `1`.

## `woff-watchdog`

Normal startup validates that at least one configured watch root is a directory
before creating the export database, discovery logger, scheduler, or observer.
Startup component failures return `1`.

`--parse-file` accepts campaign XML, `mission.log`, and the supported
`Pilot*Dossier.txt`, `Pilot*Log.txt`, `Pilot*Claims.txt`, and
`Pilot*Squads.txt` names. A missing or unsupported input returns `2`; a supported
file that its parser rejects returns `1`.

If `backup_export` is enabled and the export database already exists, startup
creates `<database-name>.backup.sqlite` with the SQLite online-backup API before
normal campaign processing. The replacement is published atomically only after
an integrity check. A backup failure preserves the previous verified sidecar
and aborts startup with status `1`. A first-time database and a configuration
with `backup_export: false` create no optional sidecar. Schema-migration backups
remain separate and mandatory.

## `woff-report`

Select configuration explicitly when it is not the working-directory default:

```powershell
woff-report --config C:\WoFFMate\config.json
```

The command requires at least one configured watch directory. It writes
`woff_data_report.txt` in the current directory through a temporary file and
publishes it only after complete generation. Missing watch roots return `2` and
produce no artifact; source parse and output-write failures return `1` and do
not publish a partial replacement. The report renders numeric zero and Boolean
false literally; only `None` and an empty string are labelled `Vazio`.
Recognized pilot log and claims files that declare zero records are valid and
render zero counts; malformed records still fail the complete report.
