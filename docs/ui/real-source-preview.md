# Experimental immutable-source desktop preview (#187)

R0.3 adds an independent PySide6 window with source-only values from explicitly
selected, previously acquired copies. The maintainer authorized Option A of the
private R0.3 integration plan. This is an experimental diagnostic capability.
The toolkit ADR was accepted on 2026-10-05, but Product Gates remain
unapproved, production P1 is unauthorized and R1/Gate A remains blocked. Synthetic P0 is unchanged.

From the dedicated source checkout, use the existing approved isolated
environment (CPython 3.10.11, PySide6/Qt/shiboken6 6.11.2). The environment must
contain exactly PySide6; alternative installed or importable bindings and
version drift are rejected. No dependency installation or bundle is required
for this task. Ordinary installation remains Qt-free: the desktop package,
like P0, is excluded from the base wheel; the toolkit is still an optional extra.

```powershell
Set-Location 'D:\PROGRAMAS\Off_Mate\.codex-worktrees\issue-187'
$previewPython = 'D:\PROGRAMAS\Off_Mate\.venv\Scripts\python.exe'
$previewManifest = Join-Path $env:LOCALAPPDATA 'Temp\WoFF_Mate_R0_20261010\manifest.private.json'
& $previewPython -B -m woff.source_preview_desktop --manifest $previewManifest
```

Use `python.exe` to retain visible startup errors. Omit `QT_QPA_PLATFORM` for
physical Windows; an inherited `offscreen` setting prevents a native window.
There is no default manifest, recent-file store, directory discovery or fallback.
A missing or invalid manifest opens a payload-free HOLD/error window. Close it
and supply the intended existing manifest explicitly. Never recapture originals
as recovery for this preview. Temp cleanup can invalidate the local demonstration.

The legacy R0 manifest is a **list**, without a schema version. Required entries
retain `alias`, `category`, `copied_input`, `basename`, `actual_source`,
`sha256_before`, `sha256_after`, `copy_sha256`, `stable_acquisition`,
`copy_integrity`, `basename_preserved` and `readable`. The three digest fields
must agree; the four capture flags must be exact `true`. Other entries are
ignored as inputs. Duplicate aliases/JSON keys, missing required sources,
invalid categories/digests and filenames are rejected. Copies must be beneath
the selected manifest's `inputs` directory and retain their exact basenames.
Original locations provide lexical capture-root exclusion only: they are never
opened, resolved or enumerated. Private filenames, paths and digests stay inside
the reader/application boundary.

Each selected source is freshly read twice, read-only, and verified against the
captured hash. Component reparse points/symlinks, hardlinks, traversal,
UNC/device paths, alternate streams, substitution/replacement, changing
metadata/bytes and unsupported sizes fail safely. Descriptor and path metadata
are each compared within their own observation; ctime views are not conflated.
On Windows, reparse-point handles and directory handles that deny delete sharing
protect the path components during acquisition; the file handle denies write
and delete sharing for each observation. POSIX uses `O_NOFOLLOW` plus metadata
and hash checks. Native fictional tests exercise junction substitution and the
Windows write/parent-replacement denial, without changing any source permissions.
No permissions, attributes or input bytes are changed. Limits are 512 KiB for
the manifest, 64 manifest entries, 2 MiB per source, 16 MiB for the 19-source
dataset, 10,000 physical lines, 2,000 mission XML nodes, 1,000 characters per
display field and 100 formation/route entries. Exceeding a limit clears data
and reports unsupported input/output; there is no silent truncation.

The native window contains three sections:

- **PilotSquads:** S-01 through S-06 are copy selections, not verified pilots.
  Squadron, aircraft, aerodrome, sector, source-record date and rank are copied
  from fresh production parsers. The record policy is the last accepted physical
  record in file order; the date does not establish whole-career history. Empty
  rank explicitly says the parser returned an empty value. Partial source
  records are qualified independently of available fields.
- **Independent Mission.log:** M-01 is source-global with **Career association:
  UNVERIFIED**. Squadron comes from `parser.pilot.squadron`, normalized date/time
  remain strings, and absent source attributes are unavailable rather than
  parser fallback evidence. Formation and route counts are exact current parser
  output. A collapsed local disclosure shows parser formation labels and route
  type/altitude, without maps, raw coordinates, mission prose or export.
- **Admission diagnostics:** all six Dossiers use fresh parsers with
  `require_verified_layout=True`. Only closed current status is displayed; no
  rejected roster data crosses the boundary. Claims retain declared, observed,
  rejected, completeness and valid-empty semantics. Number matching between
  D/C/S aliases is diagnostic grouping only. Historical failure explanations are
  omitted because this preview does not authenticate their source/revision pair.

The always-visible qualification is **Immutable local copies — no live
updates**. Hash equality proves acquired-generation consistency, not current
game synchronization, game correctness or application persistence. Provenance
reports the source, aware verification observation and record policy. Game
freshness is UNKNOWN. There is no SQLite, production ingestion package,
watchdog, registry/config, network, telemetry, activation-key access or export.
Parser output/logging is discarded in a serialized process-local privacy scope;
unexpected exceptions become fixed closed failure messages.

The service has no Qt dependency. One background worker handles bounded input
I/O and parsing. At most one pending PilotSquads request is retained; rapid
selections supersede it. Selection clears the prior snapshot/fields immediately.
Responses must match dataset, source, opaque generation and latest request ID.
Changing S cannot change M's identity or imply career ownership. Independent
sources load once per window; no files are monitored or automatically reloaded.
Closing disables/clears the UI, cancels pending work and waits asynchronously for
the current bounded parse before destruction. Reopening creates a fresh session.

Automated validation uses entirely fabricated temporary datasets. The optional
Qt CI lane exercises source clearing, late-response rejection, keyboard/focus,
native plain-text rendering and close/reopen. A subprocess audit rejects source
writes, original/database access, SQLite/ingestion/watchdog imports and network
events. Graph ownership is additive: contracts consume safe #81 primitives,
the copy reader belongs to ingestion ownership outside its package, the service
has independent application ownership and widgets import only contracts. No
P0/runtime/parser/schema/ADR change is required.

The only package metadata delta is exclusion of the new experimental desktop
package. Historical #177 adoption tests authenticate `pyproject.toml` from the
exact R0.3 base and require the current file to equal it plus exactly those two
exclusions; every other metadata byte remains checked, including dependencies.
An injected dependency change must fail. All raw #177 archives remain unchanged
and retain their original revision/execution identity. They are not evidence
for the new preview. Current synthetic P0 smoke/tests are run independently.

For local validation:

```powershell
& $previewPython -B -m pytest tests/test_source_preview_contracts.py tests/test_source_preview_service.py tests/test_source_preview_desktop.py -q
& $previewPython -B scripts/validate_project_graph.py
& $previewPython -B -m pytest -q
& $previewPython -B -m pyright --venvpath 'D:\PROGRAMAS\Off_Mate'
git diff --check
```

Offscreen widget checks do not prove that the maintainer saw a window. Physical
acceptance is separate: open all six S selections, compare available fields with
the private parser/game evidence, inspect S-05's empty rank, verify M remains
independent with current formation/waypoint counts, inspect all D/C statuses,
use Tab/Shift+Tab/arrows/Space, resize, then close/reopen. Verify appropriate
physical scaling on the maintainer's display. Record only aliases, field names
and match/mismatch/availability outcomes in shareable evidence. Do not capture
or upload screenshots with real identities. Previous R0.2 game confirmation is
historical evidence, not a new Qt attestation or Mission.log ownership proof.

The maintainer explicitly confirmed in the follow-up for PR #188 that the
actual R0.3 PySide6 window opens on Windows and displays correct real-source
data at reviewed head `58fdcfcd5cd9d5bfcbda05907724dda5deb060ea`.
This is a human observation for that revision only; it supplies no screenshots,
scaling-profile measurements or external Computer Use evidence. It is not
automatically transferred to a later head. The follow-up ctypes typing correction
guards only the two Windows native entrypoints before platform-specific imports;
Windows access modes, locking, reparse/share protection, audit and cleanup remain
unchanged. Validation on the corrected revision is recorded separately in the PR.

Native Python 3.14/#184 certification is separate; hosted or 3.10 success does
not waive failures there. No #183/#185/#186 parser remediation is included.
Review, CI, any future Codex Review and explicit human merge authorization
remain separate controls. This implementation stops at one **Draft PR**; it
does not mark Ready, close the issue, merge or advance any gate or milestone.
