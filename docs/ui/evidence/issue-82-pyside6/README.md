# Disposable #82 experiment archive

Only sanitized text is retained. These recipes are evidence, not application
modules. See the [report](../../pyside6-spike-82.md) for limits and decisions.
`SHA256SUMS` hashes the actual UTF-8/LF bytes and excludes itself.
`.gitattributes` preserves those bytes across Windows and Unix checkouts.
Runtime/build hashes in raw inventories describe the actual observed artifacts.

## Evidence generations

- **Immutable historical baseline:** the 36 JSON files named in
  `evidence-status.json/historical_payload_sha256`, measured against `0c8a3d3`
  and archived at `a632e61`. Their bytes and the shell remain unchanged.
  Historical UIA, production and relocation limitations remain in force.
- **Prior regenerated Linux production validation:**
  `production-isolation-linux-0684805.json` preserves the former current result
  byte-for-byte: commit `0684805`, Python 3.12.14, explicit clean stderr and raw
  Qt classification, with the disclosed filename-only spec adaptation. This
  remains valid production-isolation replay, without native Windows acceptance.
- **Current native Windows 10 validation:** the 24 `current-windows10-*.json`
  files and `production-isolation-current.json` record external execution at
  commit `181741488803aeb0399477ba89fab0004ea5662f`, source tree
  `ae33516f5e739478f8a41a3062bb9bd012f42207`. Windows 10 Pro 10.0.19045,
  build 19045 x64, is a developer host, not a clean or agreed representative
  machine. PySide6/Qt 6.11.2 executed on Python 3.10.11, 3.12.8, 3.13.1 and
  3.14.7. Python 3.11 was not executed.

Governance main is now `e5b97b950b2dc3196c62b2ac6ed3a54f2c929ce7`
(PR #167). The [post-merge branch validation](../../pyside6-spike-82.md#post-governance-merge-validation-2026-09-22)
is separate from these raw Windows observations at `1817414`; synchronization
does not regenerate or relabel their source revision. Retained production UI
requires R2, applicable ADR adoption gates and applicable Product Gates.
Opening a Draft PR does not establish integrated delivery.

Current strict replay covers 72 measurement rows: 12 source smoke observations
(three per executed Python) and 60 source/packaged observations, including the
scaling audit, on 3.10/3.14 only. All exits are zero, stderr/stdout flags are
explicitly false, Qt messages are empty and shell checks pass. The ordered Qt
scale overrides are 1, 1.25, 1.5 and 2. Nine plugin observations (three source,
six packaged) discover `qwindows.dll` and pass the current diagnostic contract.

Six additional relocated observations and two canonical provenance records
authenticate the current build inventory and current result JSON. The original
sidecar result names remain `relocated310.json` / `relocated314.json`; replay
resolves them with the `current-windows10-` archive prefix. Canonical hashes use
parsed JSON, sorted keys and compact separators, preserving array order. They
are distinct from `SHA256SUMS`, which hashes exact file bytes. The native
copy-and-verify procedure authenticated relocated inventories on the same host;
the archive retains sidecars, not the executable bundles. It cannot repair
historical timing attribution or establish clean-machine portability.

The corrected UIA observer now passes on Windows 10: window found, 12 elements,
exit zero, explicit clean stderr/stdout and zero Qt messages.
`announcements_verified` remains false. Current production isolation is native
Windows/Python 3.10.11 using the unchanged production spec: build exits 0/0,
help exit 0, explicit empty stderr, 52 wheel and 57 executable entries, no Qt
distributions and no forbidden artifact entries.

The archive stays flat: `current-windows10-*` separates current external
observations from historical basenames. Text was normalized to UTF-8/LF before
archiving; received current bytes are preserved during reconciliation. The
status record lists exact current filenames and SHA-256 hashes. Deterministic
tests replay the current contracts with `historical=False`, authenticate
provenance independently, pin historical and prior Linux bytes, and scan decoded
JSON for private/local paths and identity fields. Raw diagnostics stay local.
After evidence edits, regenerate `SHA256SUMS` for every direct child except
itself, using basenames in lexicographic order and exact LF-preserved bytes.

Windows 11, a clean representative machine, Python 3.11, packaged 3.12/3.13
coverage if required by the criterion, native DPI settings/transitions,
Narrator/NVDA speech, true cold startup and final licensing/distribution
confirmation remain pending. Recommendation: **Conditional Go**; Issue #82
remains incomplete, the ADR Proposed and Product Gates A/B unapproved.

## Reproduction recipes

Historical commands below used the recorded baseline. For a new measurement,
use a clean current checkout and external temporary scratch; substitute that
absolute scratch path for `build/issue82` throughout. Create two
isolated environments (regular CPython 3.10 and 3.14 required):

```powershell
New-Item -ItemType Directory -Force build/issue82
py -3.10 -m venv build/issue82/py310
py -3.14 -m venv build/issue82/py314
build/issue82/py310/Scripts/python.exe -m pip install PySide6==6.11.2 PyInstaller==6.22.0 pyinstaller-hooks-contrib==2026.7 psutil==7.2.2
build/issue82/py314/Scripts/python.exe -m pip install PySide6==6.11.2 PyInstaller==6.22.0 pyinstaller-hooks-contrib==2026.7 psutil==7.2.2
python -I -S scripts/validate_ui_fixtures.py
Copy-Item woff/tests/fixtures/ui_states/catalog.json build/issue82/catalog.json
```

Copy the `.py.txt` recipes in this directory to matching `.py` names in
`build/issue82` (and `uia.ps1.txt` to `uia.ps1`). Do not copy them into `woff`.
From `build/issue82`:

```powershell
py310/Scripts/python.exe metadata.py
py314/Scripts/python.exe metadata.py
py310/Scripts/python.exe metadata.py --pypi
py310/Scripts/python.exe run.py
py310/Scripts/python.exe relocate.py
py310/Scripts/python.exe plugin_probe.py --source
py310/Scripts/python.exe plugin_probe.py
./uia.ps1
```

The metadata probe's `--pypi` mode is the only network consumer; it is an
external compatibility observer, never imported or bundled in the shell.
`run.py` builds from `shell.py` with stock hooks and executes 60 sequential
processes. `relocate.py` verifies each source bundle against `build-inventory.json`,
authenticates any retained `relocation with spaces/package<python>` before use,
preserves a mismatched destination, and verifies a fresh copy if absent. It runs
ordinary measurement in a new `observation-*` directory under the path with
spaces, writing new `relocated<python>.json` and `relocation-provenance.json` there.
No retained bundle or historical observation is replaced. A nonzero exit or
failed check must be investigated. Do not run
other GUI probes concurrently with its keyboard audit. A fixture-only capture
can be produced with `shell.py --audit --capture` after creating `captures/`;
captures and local logs are not part of this textual archive.

For production isolation, use a separate Qt-free environment and the revised
observer copied alongside `evidence_contract.py` outside the worktree:

```powershell
py -3.10 -m venv <external-temp>/production-env
<external-temp>/production-env/Scripts/python.exe -m pip install watchdog build wheel setuptools PyInstaller==6.22.3 pyinstaller-hooks-contrib==2026.7
<external-temp>/production-env/Scripts/python.exe <external-temp>/production_check.py --repository <clean-checkout> --scratch <external-temp>/production-results
```

On Linux use the venv's `bin/python` spelling and explicit
`--linux-executable-suffix`. The unchanged Windows spec first failed on Linux
because EXE and COLLECT share a suffix-less name. This flag changes only the
executable filename in an external copy; the result records the variant/hash.
It is not an unchanged-spec or native Windows build claim. The observer copies committed
production build inputs into a unique external directory, builds the unchanged
wheel and `build.spec`, requires exactly one new wheel, inspects raw Qt/binding
artifacts in wheel, collected files and embedded executable inventory, and runs
only `--help`. It records actual platform, Python, tool versions, source/input
hashes and explicit stderr evidence. The Linux result is not Windows acceptance.
Logs and builds stay external; copy only the reviewed sanitized result.

Run repository tests/Pyright in the ordinary Qt-free development environment.
The archived replay suite imports neither the experiment nor Qt.
The production `--help`, plugin and UIA observers fail closed on their expected
exit/diagnostic contracts; PyInstaller analysis notices remain a separately
archived, reviewed build-analysis surface.

Initial records preserve the 10-point/ampersand implementation and the
12-point width-check failure. `pre-teardown-fix-*` records are the subsequently
passing 12-point shell before its debug-logging teardown correction. Final
records describe the source pinned in `provenance.json` and `build-inventory.json`.
All historical JSON bytes remain unchanged. See `evidence-status.json` for
explicit limits: old production evidence lacks stderr/raw-Qt proof, old UIA
lacks exit/diagnostic proof, and the old relocation sidecar cannot authenticate
the bundles behind the historical timings. Its prior retained-artifact claim is
superseded because the earlier recipe deleted destinations before inventory.
Those historical records remain limited even though the separate current
Windows generation now supplies authenticated same-host relocation and corrected
UIA exposure. The earlier Linux session could not execute those Windows probes.

The revised UIA observer invokes the standard-library evidence helper after
recording window observations. It reads actual redirected stderr and the shell's
captured Qt messages, rejects missing/malformed evidence and unexpected output,
and uses no stderr allowlist. Raw output remains local. The plugin debug probe's
narrow library-unload allowlist is separate and is not inherited by UIA.

New measurement and summary recipes require explicit stdout classification too.
Historical `final-*` records lack that field: `summarize.py --historical` is an
explicit limited replay of their recorded invariants, never current validation.
The exact old recipes remain recoverable at commit `a632e61`; revised recipes
cannot retroactively authenticate an older run.

The shell remains byte-identical and imports neither `woff` nor Qt alternatives.
Its final contract reference is `docs/ui/application-contracts.md` and the single
implementation `woff/ui_contracts.py`, integrated through #166. No fixture/query
adapter, copied contract or production widget is added by these observers.

Missing Windows 11, clean machines, native DPI switching, cold-boot observations
and assistive-technology speech are explicit gaps, not passing configurations.
Temporary artifacts can be deleted after verifying resolved paths are inside
the issue's ignored build directories; they are not needed by the normal test
suite. Never remove unrelated worktrees, user files or campaign data.
