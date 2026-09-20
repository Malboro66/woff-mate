# Disposable #82 experiment archive

Only sanitized text is retained. These recipes are evidence, not application
modules. See the [report](../../pyside6-spike-82.md) for limits and decisions.
`SHA256SUMS` hashes the actual UTF-8/LF bytes and excludes itself.
`.gitattributes` preserves those bytes across Windows and Unix checkouts.
Runtime/build hashes in raw inventories describe the actual observed artifacts.

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
Neither unavailable native bundles nor native UIA execution can be regenerated
in the current Linux session. Those acceptance items remain pending.

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
