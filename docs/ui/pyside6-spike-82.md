# Issue #82: PySide6 / Qt Widgets feasibility evidence

Measured: 2026-09-13/14; final validation: 2026-09-15.
Recommendation: **Conditional Go for further investigation**.
Production adoption and distribution remain blocked. This report evaluates the
criteria, including explicit evidence gaps; it does **not** claim completion of
#82, acceptance of either spike eval, Product Gates A/B, or the toolkit ADR.

## Baseline, authority and Q0

Repository: `Malboro66/woff-mate`. Branch: `codex/issue-82-pyside6-spike`.
Exact current-main baseline fetched before implementation:
`0c8a3d3c8afd4a9addae1cd5902faa79aa4f7445`. The evidence revision is the Git
commit containing this report and its checksummed archive, not a production UI
revision. [Provenance](evidence/issue-82-pyside6/provenance.json) binds the
baseline, fixture digest, environment and experiment recipe.
During finalization, main advanced to #136/PR #164 (`143226d`); those production
changes are not part of this baseline or its measurements. The synthetic #80
catalog is unchanged. #81 and formal #82 completion remain separate work.

Q0 inspected current #82, closed #79/#80, open #81, related issue search
(`repo:Malboro66/woff-mate PySide6`), PR #128, and matching Git history. #56/PR
#68 (`3552a42`) supplied the proposal; #79/PR #124 (`2d3e269`) supplied the
approved V2 reference; #80/PR #128 (`47bbfcb3010245ca11cdf779864c2a798194b183`)
supplied the 30-case catalog. None supplied measured native Qt feasibility.
The current tree had no spike report/harness or retained Python UI contract.
`python -I -S scripts/validate_ui_fixtures.py` passed all 30 synthetic cases.
`git ls-tree -r --name-only HEAD` and `git log --all --oneline --grep='spike\|#82'`
confirmed the missing experiment. This is preventive evidence work, not a
reproduced application defect. The archive replay tests initially produced
seven missing-evidence failures and one passing isolation check.

The production dependency in `pyproject.toml` is **watchdog>=3.0**;
`requirements.txt` additionally lists pytest, PyYAML and psutil for development.
The optional `windows` extra is pywin32. No Qt binding was required. Package
discovery includes `woff*` but excludes its tests; `build.spec` starts the
watchdog entry point, with no data collection or spike entry point.

The current V2 names supersede historical Dashboard/Pilot/Diary labels:
Operations, Pilot Dossier, Missions, Squadron, War Diary, Reports, plus the
separate Data & System Status footer. The archived #79 Audit 4 is the current
visual reference; stale unchecked text in closed #79 does not reopen it.
Only Operations is fixture-backed here; other destinations are inert navigation
placeholders. #81 remains open and the project graph requires it before formal
#82 completion. The authorized disposable exploration does not satisfy that
dependency or define #81's contracts.

## Candidate and environment matrix

**PySide6 / Qt / shiboken6 6.11.2**, regular CPython x64, was selected because
the publisher's `Requires-Python: >=3.10,<3.15` and `cp310-abi3-win_amd64` wheels
cover the project's whole Python range, while Qt 6.11 documents Windows 10
1809+ and Windows 11 support. This is an eligible current release line, not a
permanent pin. The wheels contain matching Qt libraries.
[PySide6 6.11.2](https://pypi.org/project/PySide6/6.11.2/),
[Qt 6.11 Windows support](https://doc.qt.io/qt-6/windows.html).

All four distributions (PySide6, Essentials, Addons, shiboken6) were checked
against each interpreter's wheel tags and Python requirement using live PyPI
JSON. [Wheel evidence](evidence/issue-82-pyside6/wheel-metadata.json) records
filenames, upload dates, byte counts, SHA-256 and authoritative metadata URLs.
This verifies artifact compatibility metadata, not execution of absent Python
versions. Free-threaded Python, ARM64 and 32-bit Windows were not tested.

| Python | Windows x64 wheel eligibility | Windows 10 source / packaged smoke | Windows 11 |
|---|---|---|---|
| 3.10 | Verified authoritative metadata | Verified locally, 3.10.11 | Not executed |
| 3.11 | Verified authoritative metadata | Not executed; interpreter unavailable locally | Not executed |
| 3.12 | Verified authoritative metadata | Not executed; interpreter unavailable locally | Not executed |
| 3.13 | Verified authoritative metadata | Not executed; interpreter unavailable locally | Not executed |
| 3.14 | Verified authoritative metadata | Verified locally, 3.14.3 | Not executed |

Local environment: Windows 10 x64 build 19045; 6 physical / 12 logical CPU
cores; 16,526,876,672 bytes RAM; 2560×1080 primary display, native DPR 1. This
is a development workstation, not a clean or agreed reference machine. No
machine identifier, user path or campaign input is archived. PyInstaller
6.22.0, hooks-contrib 2026.7 and psutil 7.2.2 were used. Complete isolated
environment versions are in `inventory10.json` and `inventory14.json`.

## Reproduction and measurement method

The [archive README](evidence/issue-82-pyside6/README.md) gives commands.
Executable copies lived only in ignored `build/issue82`; `.py.txt` / `.ps1.txt`
files are textual experiment recipes, never production modules or release
inputs. Each Qt environment contains exactly one binding. The separate
production packaging environment contains none.

The shell reads only a byte-identical copy of #80's catalog. Operations uses
`pilot-ready`, `loading-selected`, `empty-records`, `error-query-selected`.
Every state visibly carries Synthetic, fixture ID and canonical state. Retry
is a timer-driven fixture transition (error → loading → ready), without a
service. There is no SQL/SQLite, WoFF file, parser, repository, watchdog,
launcher, session, network service or configuration integration.

The parent starts a new process using `perf_counter`, and the child's first
completed QWidget paint handler emits a timestamp from that shared Windows
clock. Launch-to-paint includes interpreter/bootloader startup, imports and
fixture loading. It is a reproducible **first-paint proxy**, not measured
on-screen photon latency. Qt import time measures the in-script
`PySide6/QtCore/QtGui/QtWidgets` import interval. Frozen runtime hooks can import
Qt before script entry, so frozen import figures are not comparable to source
imports; end-to-end frozen launch time remains the useful measure.

Memory is the process RSS/working set and private committed bytes roughly
three seconds after showing the window, before interaction checks. It includes
the small psutil observer and test-capable shell; it is not a long soak or
whole-system delta. MB means **1,000,000 bytes** throughout. Dependency footprint
sums installed files listed by the four distribution RECORDs; it excludes
Python, build tools and download caches. Artifact size sums every onedir file,
without compression, UPX, signing or an installer.

Final series: three source and three packaged restarts on each installed
Python (12 runs), then three interaction runs per Python/build/scale combination
(48 runs). Runs are sequential. The initial run in each series has uncontrolled
OS cache state; later runs are warm process restarts. No reboot, standby-list
purge or certified cold-machine run occurred. An installation and small
repository checks overlapped portions of development measurements; this is not
a controlled idle-lab benchmark. Budgets have not been relaxed.

Raw results: `final-source310.json`, `final-source314.json`,
`final-packaged310.json`, `final-packaged314.json`, and their `-audit.json`
companions. Earlier measurements and failures are retained under `preliminary-`
and `pre-teardown-fix-` names. They are superseded experiment revisions, not
silently discarded outliers. [Summary](evidence/issue-82-pyside6/summary.json)
is derived from the final raw samples.

## Budgets and observed behavior

<!-- measurement-summary -->
Dedicated startup series, three runs per row; import is the median, memory
columns are maxima. All first runs have uncontrolled cache state.

| Configuration | Launch-to-paint samples (s) | Qt import (s) | RSS (MB) | Private (MB) | Artifact (MB) |
|---|---|---:|---:|---:|---:|
| Python 3.10 source | 0.467 / 0.459 / 0.448 | 0.110 | 67.20 | 34.28 | — |
| Python 3.14 source | 0.479 / 0.461 / 0.467 | 0.119 | 71.91 | 38.45 | — |
| Python 3.10 packaged | 0.552 / 0.431 / 0.428 | 0.008* | 66.24 | 31.36 | 110.08 |
| Python 3.14 packaged | 0.550 / 0.456 / 0.464 | 0.010* | 71.12 | 36.77 | 116.83 |

*Frozen import excludes work already performed by bootloader/runtime hooks.
The full unpackaged PySide6/shiboken distribution footprint was 678.92 MB on
3.10 and 679.10 MB on 3.14. There was no dependency-footprint budget. The 48
interaction runs separately confirm startup and idle-memory observations at
each scale; they are not pooled into the dedicated timing table. Across all
60 final runs, the largest working set was 77.11 MB and the longest startup
was 0.598 s.
<!-- /measurement-summary -->

| Investigation target | Evaluation |
|---|---|
| Cold first window ≤3.0 s | **Not verified.** Initial uncontrolled source starts were 5.427 s (3.10) and 4.657 s (3.14); these exceed the target as proxies but are not certified cold tests. |
| Warm first window ≤1.5 s | Final series passes locally. Preliminary second starts were 2.538 s and 2.526 s; startup variability remains a blocker to a product guarantee. |
| Idle memory ≤200 MB | Final sampled working sets and private bytes pass locally; no soak/clean-machine claim. |
| Packaged artifact ≤250 MB | Both complete onedir artifacts pass, without trimming plugins or compressing the directory. |
| No missing-plugin, mixed-binding or unhandled startup warning | Final ordinary runs pass. The diagnostic-only teardown failure and its correction are recorded below. |

No replacement budget is proposed: repeat cold/reference-machine measurements
before deciding whether the original budget is achievable.

## PyInstaller, paths and distribution findings

`run.py.txt` builds two onedir console executables with stock hooks, `--noupx`,
one fixture file, and explicit exclusion of PyQt5, PyQt6 and PySide2. Console
mode provides the measurement channel; a production windowed executable,
onefile extraction cost, installer and signing were not tested. The source and
frozen runs remove inherited Qt/QML/Python overrides; the child PATH contains
only Windows System32. Both artifacts render with Qt's `windows` platform
plugin on the build host. This proves local plugin discovery, not operation on
a clean machine with no preinstalled runtimes. Windows 11 and clean-machine
acceptance remain unmet.

An additional relocation probe copies both complete bundles to a directory
containing spaces and runs each three times from a different working directory,
again with only System32 on PATH. Both render and exit successfully; these are
same-host relocation checks, not clean-machine evidence. The first relocated
launch exceeded five seconds, reinforcing the unresolved startup variability.
Raw `relocated310.json` and `relocated314.json` preserve every historical sample.
The archived `relocate.py.txt` now provides the omitted deterministic replay:
it verifies the source inventory, copies and re-verifies the relocated bundle,
runs the same measurement, and binds artifact/source/result identities in
`relocation-provenance.json`. That provenance is a post-review verification of
the retained artifacts; the historical timing observations were not regenerated.

[Build inventory](evidence/issue-82-pyside6/build-inventory.json) lists every
relative file, size and SHA-256. Stock hooks collected Core, Gui, Widgets, Test,
Network, OpenGL, Svg, Pdf, Qml, QmlMeta, QmlModels, QmlWorkerScript, Quick and
VirtualKeyboard libraries, shiboken/PySide bridges, Python and VC runtimes,
software OpenGL, image-format, platform, style, TLS, network-information,
input-context and generic plugins. Bundled Network/QML libraries do not mean
the shell integrates a network service or QML screen.

No runtime Qt plugin failure appeared in the ordinary final runs. Explicit
`QT_DEBUG_PLUGINS=1` probes discovered qwindows and loaded it plus the Windows
style plugin; sanitized diagnostics retain DLL basenames and warning counts.
The first debug probes rendered and produced a result, then exited with
`0xC0000005`. Removing the Python Qt message handler before interpreter
finalization eliminated that observed failure. This supports a callback-lifetime
explanation, not a proven upstream Qt defect. The final source, builds and
measurement series were regenerated after the correction; the original failed
probe remains archived. Library discovery debug messages are not warnings.
The final debug probe passed three times per packaged Python configuration.
PyInstaller's static analysis also emitted missing-module notices for platform
conditionals (for example pwd/grp/posix), and `collections.abc` on 3.14. These
are recorded in `build-analysis-notices.json`; no matching import failure
occurred in the executed shell. This does not prove unexercised modules work.

The standard bundle contained **no license/notice files** and included
**Qt Virtual Keyboard**, which is GPLv3/commercial rather than LGPL. The
repository's MIT license does not settle distribution rights for this collected
module. The current bundle must not be treated as an approved LGPL-only
deliverable. A future distribution must remove unneeded components with a
verified build policy or explicitly approve a compatible licensing route.
[Qt Virtual Keyboard licensing](https://doc.qt.io/qt-6/qtvirtualkeyboard-index.html).
Qt PDF has LGPLv3/GPLv2/commercial options and its own third-party review surface.
[Qt PDF licensing](https://doc.qt.io/qt-6/qtpdf-index.html).

## Scaling, keyboard and accessibility

The `windows` backend rendered at measured DPR 1, 1.25, 1.5 and 2 using
`QT_SCALE_FACTOR`. Logical window sizes were 960×680, 960×680, 960×640 and
960×465, respectively; the effective display shrank from 2560×1080 to
1280×540. This is Qt's documented test override on a real Windows desktop,
**not** a Windows Settings DPI change, multi-monitor migration, or certification
of fractional OS scaling. [Qt high-DPI testing](https://doc.qt.io/qt-6/highdpi.html).

All 48 final interaction runs perform 55 checks each (2,640 observations):
forward/reverse Tab order, keyboard activation of six destinations plus system
status, destination heading focus, keyboard retry through loading to ready,
and geometry/accessibility checks for the four fixture states. Rectangles stay
within the window, button labels fit with focus-padding allowance and wrapped
labels have sufficient height. No inaccessible control, clipping or
scale-specific startup failure was detected in this bounded layout. This is
not an audit of a complete production screen or all possible text lengths.

The ampersand in Data & System Status initially became a mnemonic and the
footer lacked the test's focus-padding allowance. Escaping it as `&&` and
reserving explicit label width corrected the disposable shell. Font size is
12-point Segoe UI. Qt-captured synthetic images were visually inspected during
development: readable text and a visible bright focus border; only textual
observations are archived. No manual human Windows walkthrough is claimed.
Full V2 two-edge focus styling and semantic heading treatment remain future
design validation; this minimal shell uses a single border and a focusable
StaticText heading excluded from sequential Tab traversal.

Qt interfaces expose Button, ComboBox and StaticText roles with names. A
separate **Windows UI Automation** probe of the error-state window exposes
12 elements, including all seven navigation buttons, state selector, safe
diagnostic and Retry view, with expected Button/ComboBox/Text roles and no
offscreen elements. The first probe could not find the window through the venv
redirector process; using the shell's explicitly emitted HWND fixed discovery.
The HWND and process IDs are not archived. The probe's process exit code is
unavailable (`null`); normal measurement runs separately verify exit status.
The corrected archived replay now refreshes and requires the process exit code,
window discovery and a nonempty exposed-element set, while preserving this
historical result unchanged.
[Native exposure result](evidence/issue-82-pyside6/uia.json).

UIA exposure and Qt NameChanged events do not establish spoken announcements.
Narrator/NVDA, Windows high contrast, screen-reader retry announcements and
manual keyboard-only completion remain **not verified**. Qt documents native
accessibility support, but vendor capability is not application acceptance.
[Qt accessibility](https://doc.qt.io/qt-6/accessible.html).

## Licensing checklist for any later adoption

This is an engineering checklist, not final legal approval.

| Distribution action | Current evidence / remaining action |
|---|---|
| Select licensing route per shipped module | PySide6 offers LGPL/GPL/commercial alternatives. Inventory every library/plugin; resolve Virtual Keyboard's GPL/commercial terms before distributing. |
| Prominent attribution and license texts | Add Qt/PySide/shiboken notices and LGPLv3/GPLv3 texts as applicable, with application documentation/About access. Stock experiment bundle has none. |
| Corresponding source | Supply exact corresponding library source, changes and build information, or a legally sufficient offer/access mechanism. A generic homepage link is not an established compliance mechanism. |
| Replacement/relinking | Preserve compatible library replacement and users' modification/debugging rights; provide necessary installation information and test replacement in the frozen layout. Dynamic DLLs alone do not prove compliance. |
| Terms and channels | Review EULA/store/signing/update restrictions so they do not defeat granted rights; approve the actual distribution mechanism. |
| Third-party notices | Audit Python, VC runtime, OpenSSL/libcrypto, software OpenGL and all embedded Qt third-party components, including image/font/compression/PDF dependencies; produce a version-specific SBOM and notices. |
| Provenance and maintenance | Pin artifacts/hashes; retain source provenance and security-update responsibility; recheck the Windows 10 lifecycle before upgrading Qt. |

The obligations concerning notices, source availability, replacement and
distribution restrictions follow Qt's published LGPL guidance.
[Qt LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations).
Qt's third-party inventory and SBOM documentation cover components actually
shipped, including embedded code; a DLL list alone is insufficient.
[Qt third-party code](https://doc.qt.io/qt-6/licenses-used-in-qt.html),
[Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html).
PyInstaller explicitly disallows multiple Qt bindings in one build; the
experiment additionally checks installed distributions and bundle filenames.
[PyInstaller Qt hooks](https://pyinstaller.org/en/stable/hooks-config.html#qt).

## Acceptance accounting and remaining blockers

| #82 criterion group | Evidence / disposition |
|---|---|
| One binding; selected line/rationale | Verified in both isolated Qt environments; production remains Qt-free. |
| Wheel/smoke matrix | All five wheel rows evaluated; two locally executed, three runtime gaps explicitly recorded. |
| Windows 10 and 11; clean packaged render | Windows 10 developer host passed; Windows 11 and clean-machine runs **unmet**. |
| Reproducible import/startup/memory/footprint/package results | Recipes and raw samples supplied; true cold baseline **unmet**. |
| Four scaling values | Qt override runs passed; native Windows DPI changes **unmet**. |
| Keyboard, focus, names, roles, announcements | Automated Qt/UIA evidence supplied; speech and manual Windows validation **unmet**. |
| #80-only fixture shell, no live integrations | Verified by fixture digest, source inspection and imported-module observations. |
| No mandatory Qt dependency or shipped spike artifact | Unchanged production dependencies/spec; separate Qt-free wheel/executable build and inventory checks. |
| Licensing notices/actions | Identified, with actual GPL/commercial component and missing-notice blockers. No distribution clearance. |
| Report recommendation; ADR Proposed | Conditional Go for further investigation; ADR and all Product Gates remain unapproved. |

Before production adoption: complete #81 and the formal #82/P0/R2 sequence;
run Python 3.11–3.13 smoke and representative Windows 10/11 clean-machine
coverage; establish repeatable cold/warm budgets on an agreed baseline;
validate OS-native scaling and screen-reader/keyboard flows; resolve the exact
licensed bundle, notices, source and replacement mechanism; approve an optional
UI dependency policy, the ADR and applicable Product Gates. Qt 6.12 is the last
line documented to support Windows 10, so future release selection needs an
explicit lifecycle decision. No gate or budget is changed here.

## Validation and cleanup

<!-- validation-summary -->
Validation used the existing Qt-free Python 3.10.11 development environment.
In the following commands, `python`/`pyright` resolve to that environment;
`<external-temp>` is a writable directory outside this issue checkout.

| Command / check | Final result |
|---|---|
| `python -m pytest -q --basetemp=<external-temp> --tb=short` | **1,320 passed, 1 skipped, 175 subtests passed**, 199.92 s. Skip: Windows symlink privilege unavailable. |
| `python -m pytest tests/test_ui_spike_evidence.py woff/tests/test_architecture_contracts.py -q --basetemp=<external-temp> --tb=short` | **136 passed** (10 spike replay checks and 126 architecture checks). |
| `python -I -S scripts/validate_ui_fixtures.py` | 30 synthetic fixtures / six shared states valid. |
| `python scripts/validate_project_graph.py` | Passed; graph unchanged. |
| `pyright --venvpath <development-venv-parent>` | Zero errors, zero warnings. |
| `production-env/Scripts/python.exe production_check.py` from the documented locations | Wheel, unchanged PyInstaller production build, dependency/artifact inventories and executable `--help` passed. |
| `git diff --check` and `git diff --cached --check` | Passed. |
| Staged-file inventory / source diff review / archive hashes | Only 51 scoped documentation, textual evidence, test and LF-policy files; no binary, environment, runtime data or release artifact staged. |

Initial focused tests encountered the sandbox's inaccessible default pytest
temporary directory. A temporary directory inside the checkout then violated
an existing test that deliberately requires an external path. A writable
workspace directory outside the issue checkout resolved both without changing
test behavior. The first full run exposed the existing evidence inventory's
fixed 18-file count. Extending it to 62 (18 prior plus 44 new text payloads)
and preserving raw LF bytes in `.gitattributes` kept the original protection;
the final full rerun above passed. No existing test was weakened or removed.
<!-- /validation-summary -->

Production wheel discovery and the unchanged `build.spec` were exercised in a
third isolated, Qt-free environment. The built watchdog executable returned
zero for `--help`; wheel and executable inventories contain neither Qt nor
spike recipes/fixtures. [Production isolation](evidence/issue-82-pyside6/production-isolation.json).
No campaign/configuration file or schema was modified. All environments,
executables, intermediate specs, local diagnostic logs and images remain under
ignored build directories; only sanitized text is staged. Root-worktree
pre-existing files and other issue branches are untouched. No release was
published, no PR marked ready and no merge or automatic review requested.

The graph is unchanged because no new production module, completed eval,
satisfied dependency or gate is claimed. The eval catalog and ADR link this
bounded evidence without promoting their states. Rollback is removal of these
documentation/test changes and the disposable build directory.

Out-of-scope follow-ups: none implemented. Distribution provenance work already
has #155; unexpected GPL/commercial plugin collection and the missing native
environment/AT matrix belong to the remaining #82 distribution/validation
work, not production UI implementation.
