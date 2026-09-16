# Disposable #82 experiment archive

Only sanitized text is retained. These recipes are evidence, not application
modules. See the [report](../../pyside6-spike-82.md) for limits and decisions.
`SHA256SUMS` hashes the actual UTF-8/LF bytes and excludes itself.
`.gitattributes` preserves those bytes across Windows and Unix checkouts.
Runtime/build hashes in raw inventories describe the actual observed artifacts.

From the baseline checkout on Windows, create ignored scratch space and two
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
copies it to `relocation with spaces/package<python>`, verifies the copy, runs
the ordinary measurement from that different working directory, and emits
`relocated<python>.json` plus `relocation-provenance.json`. A nonzero exit or
failed check must be investigated. Do not run
other GUI probes concurrently with its keyboard audit. A fixture-only capture
can be produced with `shell.py --audit --capture` after creating `captures/`;
captures and local logs are not part of this textual archive.

For production isolation, from the repository root:

```powershell
py -3.10 -m venv build/issue82/production-env
build/issue82/production-env/Scripts/python.exe -m pip install . build wheel PyInstaller==6.22.0
build/issue82/production-env/Scripts/python.exe build/issue82/production_check.py
```

The production observer recreates its three known disposable output directories,
builds the unchanged wheel and `build.spec`, requires exactly one newly built
wheel, inventories both artifacts and runs only the executable's `--help`. It
imports no campaign inputs.
Run repository tests/Pyright in the ordinary Qt-free development environment.
The archived replay suite imports neither the experiment nor Qt.
The production `--help`, plugin and UIA observers fail closed on their expected
exit/diagnostic contracts; PyInstaller analysis notices remain a separately
archived, reviewed build-analysis surface.

Initial records preserve the 10-point/ampersand implementation and the
12-point width-check failure. `pre-teardown-fix-*` records are the subsequently
passing 12-point shell before its debug-logging teardown correction. Final
records describe the source pinned in `provenance.json` and `build-inventory.json`.
The historical `relocated*.json` bytes were not regenerated for this replay
correction. `relocation-provenance.json` records the later, explicit verification
that the retained source bundles and their retained path-with-spaces copies were
byte-for-byte equal to the archived build inventory and binds the historical
JSON observations by a line-ending-independent semantic digest.
The first debug probe's access-violation exit and the failed first UIA window
lookup are preserved separately. The retained final UIA result predates the
fail-closed recipe and has an unavailable process exit code; ordinary runs
separately established normal exit, while future UIA replays now require a
window, exposed elements and exit zero. No old experiment is a production
defect or an additional selected Qt line.

Missing Windows 11, clean machines, native DPI switching, cold-boot observations
and assistive-technology speech are explicit gaps, not passing configurations.
Temporary artifacts can be deleted after verifying resolved paths are inside
the issue's ignored build directories; they are not needed by the normal test
suite. Never remove unrelated worktrees, user files or campaign data.
