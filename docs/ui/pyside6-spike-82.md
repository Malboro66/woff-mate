# Issue #82: PySide6 / Qt Widgets feasibility evidence

Historical measurements: 2026-09-13/14; original validation: 2026-09-15.
Synchronization: 2026-09-20; current external Windows observations:
2026-09-20/21 UTC, at `1817414`. See current validation below.
Recommendation: **Conditional Go for further investigation**.
Production adoption and distribution remain blocked. This report evaluates the
criteria, including explicit evidence gaps; it does **not** claim completion of
#82, acceptance of either spike eval, Product Gates A/B, or the toolkit ADR.

## Baseline, authority and Q0

Repository: `Malboro66/woff-mate`. Branch: `codex/issue-82-pyside6-spike`.
Exact historical main baseline fetched before the original experiment:
`0c8a3d3c8afd4a9addae1cd5902faa79aa4f7445`. The original archive is preserved at `a632e61d2ca3ee1f7adcd2d1ec6853b568dddf04`;
its observations do not describe the synchronized branch. [Provenance](evidence/issue-82-pyside6/provenance.json) binds the
baseline, fixture digest, environment and experiment recipe.
During original finalization, main advanced through #136/PR #164 (`143226d`).
The current branch now includes that change and the #81 squash merge,
`18faf9cd31be90ea5d74738e5cf299dfdbb9e832`, through source merge `0684805e6926b3d923d4017023b178ce8b198114`.
The #80 catalog and every historical JSON observation remain unchanged.
The following Q0 paragraph records the original investigation, not current issue states.

Q0 inspected current #82, closed #79/#80, open #81, related issue search
(`repo:Malboro66/woff-mate PySide6`), PR #128, and matching Git history. #56/PR
#68 (`3552a42`) supplied the proposal; #79/PR #124 (`2d3e269`) supplied the
approved V2 reference; #80/PR #128 (`47bbfcb3010245ca11cdf779864c2a798194b183`)
supplied the 30-case catalog. None supplied measured native Qt feasibility.
That historical tree had no spike report/harness or retained Python UI contract.
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
placeholders. #81 is now closed and its graph dependency is satisfied.
Formal #82 completion remains blocked by external evidence. The disposable
exploration does not implement a query service or replace the final contracts.

## Candidate and environment matrix

**PySide6 / Qt / shiboken6 6.11.2**, regular CPython x64, was selected because
the publisher's `Requires-Python: >=3.10,<3.15` and `cp310-abi3-win_amd64` wheels
cover the project's whole Python range, while Qt 6.11 documents Windows 10
1809+ and Windows 11 support. This was the selected experimental release line, not a
new adoption decision or a refreshed compatibility certification. The wheels contain matching Qt libraries.
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
| 3.10 | Verified authoritative metadata | Historical and current source/packaged, 3.10.11 | Not executed |
| 3.11 | Verified authoritative metadata | Not executed; interpreter unavailable locally | Not executed |
| 3.12 | Verified authoritative metadata | Current source smoke, 3.12.8; packaged not executed | Not executed |
| 3.13 | Verified authoritative metadata | Current source smoke, 3.13.1; packaged not executed | Not executed |
| 3.14 | Verified authoritative metadata | Historical source/packaged 3.14.3; current source/packaged 3.14.7 | Not executed |

Historical local environment: Windows 10 x64 build 19045; 6 physical / 12 logical CPU
cores; 16,526,876,672 bytes RAM; 2560×1080 primary display, native DPR 1. This
is a development workstation, not a clean or agreed reference machine. No
machine identifier, user path or campaign input is archived. PyInstaller
6.22.0, hooks-contrib 2026.7 and psutil 7.2.2 were used. Complete isolated
environment versions are in `inventory10.json` and `inventory14.json`.

The current external run used Windows 10 Pro 10.0.19045 build 19045 x64 on a
developer host, PySide6 6.11.2 and the four actually executed versions above.
`current-windows10-inventory10/12/13/14.json` record their exact environments.
Current packaged execution and the scaling audit cover 3.10/3.14 only.

## Historical reproduction and measurement method

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

Historical final series: three source and three packaged restarts on each installed
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

## Historical budgets and observed behavior

<!-- measurement-summary -->
Historical dedicated startup series, three runs per row; import is the median, memory
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

The historical relocation probe copied both complete bundles to a directory
containing spaces and ran each three times from a different working directory,
again with only System32 on PATH. Both rendered and exited successfully; these
historical timings do not prove clean-machine behavior. The first relocated
launch exceeded five seconds, reinforcing the unresolved startup variability.
Raw `relocated310.json` and `relocated314.json` preserve every historical sample.
The old `relocation-provenance.json` authentication claim is **superseded**:
the earlier recipe deleted retained destinations before inventory. Its hashes
cannot prove that those retained bytes produced the old timing observations.
The prior Linux session had neither historical Windows bundle; the old timing
association remains unauthenticated. The revised recipe
inventories source and retained destination first, preserves mismatches, reuses
verified destinations, verifies fresh copies and measures into a new observation
directory. Only observations from that invocation receive new provenance.
Historical timing bytes remain unchanged and are not current acceptance evidence.

Current Windows 10 execution now supplies six separate relocated observations
and two provenance records in `current-windows10-relocated310/314.json` and
`current-windows10-relocation-provenance310/314.json`. Canonical authentication
binds the current build's source hash, ordered file inventory, count/bytes and
current result JSON; the native copy-and-verify procedure authenticated relocated
inventories before measurement. Replay resolves each sidecar's original result
basename with the archive prefix, without rewriting it. These are authenticated
same-host observations, not clean-machine evidence or proof of historical timings.

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
module. Neither historical nor current bundles may be treated as an approved LGPL-only
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

All 48 historical final interaction runs perform 55 checks each (2,640 observations):
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
historical **Windows UI Automation** probe of the error-state window exposed
12 elements, including all seven navigation buttons, state selector, safe
diagnostic and Retry view, with expected Button/ComboBox/Text roles and no
offscreen elements. The first probe could not find the window through the venv
redirector process; using the shell's explicitly emitted HWND fixed discovery.
The HWND and process IDs are not archived. The probe's process exit code is
unavailable (`null`); normal measurement runs separately verify exit status.
The historical UIA record also lacks stderr and Qt-message evidence, so it
is rejected by current replay and retained only as limited exposure history.
The revised probe requires exit zero, window/elements, actual redirected stderr,
well-formed shell output and zero captured Qt diagnostics. UIA has no benign
stderr allowlist. [Historical exposure result](evidence/issue-82-pyside6/uia.json).

The corrected observer has now executed successfully on Windows 10 at
`1817414`: [current UIA result](evidence/issue-82-pyside6/current-windows10-uia.json)
records `window_found: true`, 12 elements, exit 0, `stderr_nonempty: false`,
`stdout_unexpected: false` and `qt_message_count: 0`. Strict current validation
passes. `announcements_verified: false` preserves the exposure-only boundary;
actual Narrator/NVDA speech remains unverified.

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

| #82 acceptance criterion | Classification | Evidence / limit |
|---|---|---|
| Exactly one Qt binding | Satisfied | Historical and current isolated environments contain PySide6 only; source and artifact inventories exclude alternative bindings. |
| Candidate version and rationale | Satisfied | PySide6/Qt/shiboken 6.11.2 and original metadata rationale preserved. No refreshed vendor policy claim. |
| Wheel availability and smoke for every Python | Partially satisfied | Historical metadata covers five Python versions; current Windows source smoke covers 3.10/3.12/3.13/3.14. Python 3.11 remains unexecuted; current packaged/audit coverage is 3.10/3.14 only. |
| Representative Windows 10/11 | Partially satisfied | Historical and current Windows 10 developer-host runs; representative clean machine and Windows 11 pending. |
| Clean-machine packaged render | Blocked | No clean representative Windows machine is available in this session. |
| Reproducible performance/resource measurements | Partially satisfied | Historical samples preserved; 72 current measurement rows plus six authenticated same-host relocated observations pass strict replay. True cold/reference-machine baseline pending. |
| 100/125/150/200% scaling | Partially satisfied | Historical and current Qt overrides; native DPI settings/transitions pending. |
| Keyboard/focus/order/names/roles/announcements | Partially satisfied | Historical and current shell checks; corrected native UIA exposure now passes. Actual AT speech and broader manual flows pending. |
| Synthetic #80 fixtures only | Satisfied | Catalog and shell digests unchanged; deterministic fixture gate. |
| No forbidden application/live integrations | Satisfied | Shell import boundary and final #81 architecture checks. |
| No mandatory production Qt dependency | Satisfied | Current native Windows wheel/executable inventories and clean `--help` stderr pass with unchanged production spec; no Qt distributions or forbidden entries. Prior adapted Linux result preserved separately. |
| Licensing notices and distribution actions | Partially satisfied | GPL/commercial plugin and missing notices preserved; final version-bound licensing/distribution confirmation pending. |
| Explicit recommendation | Satisfied | Conditional Go for further evidence collection. |
| ADR remains Proposed | Satisfied | Status unchanged; no gate approval. |
| No shipped temporary spike artifact | Satisfied | Only documentation, text recipes/results and deterministic tests enter the PR; builds/environments/logs remain external. |

Before production adoption: complete the remaining formal #82/P0/R2 sequence;
#81 is integrated and requires no reimplementation;
run Python 3.11 smoke, resolve packaged 3.12/3.13 coverage required by the
criterion, and complete representative Windows 10/11 clean-machine
coverage; establish repeatable cold/warm budgets on an agreed baseline;
validate OS-native scaling and screen-reader/keyboard flows; resolve the exact
licensed bundle, notices, source and replacement mechanism; approve an optional
UI dependency policy, the ADR and applicable Product Gates. Qt 6.12 is the last
line documented to support Windows 10, so future release selection needs an
explicit lifecycle decision. No gate or budget is changed here.

## Historical validation and cleanup

<!-- validation-summary -->
The original `a93f040` archive reported validation in the Qt-free Python
3.10.11 Windows development environment. These preserved counts are historical;
they do not describe `a632e61` or the synchronized branch.
In the following commands, `python`/`pyright` resolve to that environment;
`<external-temp>` is a writable directory outside this issue checkout.

| Historical command / check | Original reported result |
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

The original [Windows production result](evidence/issue-82-pyside6/production-isolation.json)
records exit zero but omits stderr evidence and used incomplete Qt detection.
It is superseded for isolation acceptance; its bytes remain historical.
The prior regenerated production result uses the stricter observer on Linux,
with exact interpreter/tool versions and build inputs. It is preserved byte-for-byte
as `production-isolation-linux-0684805.json` and does not certify Windows.
The unchanged spec first failed on Linux because EXE and COLLECT target the
same suffix-less name. The observer explicitly applies only a temporary `.exe`
filename suffix on Linux; the archived result declares this variant and its
effective spec hash. Production `build.spec` is unchanged; native Windows CI
uses that exact spec separately. No failure is reclassified as a successful
unchanged-spec Linux build.
`production-isolation-current.json` now records native Windows/Python 3.10.11
execution at `1817414` with the unchanged spec, build exits 0/0, executable
help exit 0, explicit empty stderr, 52 wheel/57 executable entries and no Qt
distributions or forbidden entries. Current replay authenticates source/build
inputs independently. The Linux filename workaround remains earlier evidence.
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


## Reconciliation with the final Issue #81 contracts

The authoritative `main` is `18faf9cd31be90ea5d74738e5cf299dfdbb9e832`.
Issues #136 and #81 are closed. A merge, without conflict or history rewriting,
preserved both published spike commits and all integrated production changes.
`woff/ui_contracts.py`, `woff/nation.py`, the #80 catalog and production packaging
configuration are unchanged relative to that main. The existing #81 tests are
run directly; no duplicate contract, adapter or widget binding is introduced.

The disposable shell's bytes and historical hash remain unchanged. It renders
four synthetic #80 fixtures directly and has no contract imports. Its timer
transition is an experiment, not an application refresh/retry implementation.
The final reference is [application-contracts.md](application-contracts.md):

| Boundary | Reconciliation |
|---|---|
| Six screen values | OperationsSnapshot, PilotDossierSnapshot, MissionsSnapshot, WarDiarySnapshot, SquadronSnapshot and SystemStatusSnapshot are defined only in `woff/ui_contracts.py`. |
| Selection and identity | Five career queries accept optional selection; absent selection is missing/career_not_selected. Stable pilot/mission/diary/squadron IDs are supplied, never derived from labels or positions. |
| Value semantics | Frozen values, copied collections, exact integer types, deterministic warnings and mission ordering remain enforced by #81. |
| State/payload | Loading/missing/error are payload-free. Successful list cardinality, optional SYS-01 profile and safely observed retained payload follow the final contract. |
| Nation/service | Closed GB/FR/DE/US/BE nation codes and distinct RFC/RNAS/RAF service values come from #136. No display-label inference or raw unsupported values cross the presentation boundary. |
| Diagnostics | Closed sanitized failures/warnings and field-level unavailable reasons remain separate from observer-local logs. |

These are reference boundaries for future authorized consumers. This spike
implements none of #140 or the production query path.

## Prior branch validation at 1817414 on Linux

The counts in this section describe the prior published tree only, not the
edited Windows evidence reconciliation. Its original commands use `V` for the external temporary validation root
(path redaction only); `P=$V/.venv/bin/python` is CPython 3.12.14 on Linux.
Both development and production environments are Qt-free. Pyright is 1.1.414;
pytest is 9.1.1. The production environment separately uses PyInstaller 6.22.3,
hooks 2026.7, build 1.6.1, setuptools 84.0.0 and wheel 0.48.0. The PR body
records the final validated commit and remote CI run. The production result binds
its actual build revision, observer hashes and every production build input;
replay checks those inputs against this tree even after documentation-only commits.

<!-- current-validation -->
The following ledger is preserved from publication at `1817414`; the PR records
that SHA and its remote CI. It is not a claim that these commands were rerun
after the current evidence edits.
Exit status is **0** for each successful row. Test counts are not inferred from
historical totals. Non-test commands have no test count or skips.

| Exact command (`P`/`V` as defined above) | Result | Classification |
|---|---|---|
| `P -m pytest tests/test_ui_spike_evidence.py -q -ra --basetemp=$V/spike-final -o cache_dir=$V/pytest-cache` | **131 passed**, no skips | Prior branch validation, including manifest/replay and negative cases |
| `P -m pytest tests/test_ui_contracts.py tests/test_ui_state_fixtures.py woff/tests/test_architecture_contracts.py woff/tests/test_product_milestones.py woff/tests/test_ui_development_standard.py woff/tests/test_privacy_contracts.py -q -ra --basetemp=$V/focused-final -o cache_dir=$V/pytest-cache` | **665 passed**, no skips | Prior architecture, immutable contracts, fixtures and related gates |
| `P -m pytest -q -ra --tb=short --basetemp=$V/full-final -o cache_dir=$V/pytest-cache` | **1,862 passed, 4 skipped, 175 subtests passed** | Prior full suite; all four skips are existing Windows-only ordinary directory-junction cases |
| `$V/.venv/bin/pyright --venvpath $V` | **0 errors, 0 warnings** | Prior static analysis |
| `P scripts/validate_project_graph.py` | Graph valid | Prior branch validation |
| `P -I -S scripts/validate_ui_fixtures.py` | **30 synthetic cases, 6 shared states** | Prior fixture validation |
| `P scripts/validate_ui_v2_evidence.py` | **60 captures, 14 states, 12 statuses, 28 complete keyboard sequences** | Replay of existing UI V2 evidence; no new native measurement |
| `$V/production-env/bin/python $V/recipes/production_check.py --repository $V/source-revision --scratch $V/production-results --linux-executable-suffix` | Wheel/build/help exit **0/0/0**, `executable_help_stderr_nonempty: false`; no forbidden entries; **52 wheel entries, 16 executable entries** | Regenerated on Linux/Python 3.12.14 at source merge `0684805e6926b3d923d4017023b178ce8b198114`; final input/hash equality checked by replay |
| `P $V/replay_summary.py` (recipe below) | Every historical summary value reproduced | Historical derived replay, no new timing measurement |
| `P $V/check_syntax.py` (recipe below) | **105 tracked Python files + 9 archived recipes** satisfy Python 3.10 grammar | Prior syntax validation, not execution on Python 3.10 |
| `git diff --check`; `git diff origin/main --check` | Passed | Prior whitespace/full-diff validation |

The temporary `check_syntax.py` recipe is:

```python
import ast, subprocess
from pathlib import Path
paths = [Path(p) for p in subprocess.check_output(
    ['git', 'ls-files', '*.py'], text=True).splitlines()]
recipes = sorted(Path('docs/ui/evidence/issue-82-pyside6').glob('*.py.txt'))
for path in paths + recipes:
    ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path),
              feature_version=(3, 10))
print(len(paths), len(recipes))
```

The temporary `replay_summary.py` copies archived JSON and the current
`summarize.py.txt` / `evidence_contract.py.txt` recipes into a new external
scratch directory, removes `.txt` from recipe names, executes
`[P, 'summarize.py', '--historical']` there, and asserts parsed JSON equality
between the generated and archived `summary.json`. It never overwrites history.

The complete diff was manually reviewed against authoritative `main`: all
production modules, dependencies, schema, fixtures and #81 contracts remain
identical. At that revision, exactly **49 spike payloads** plus **18 prior Site payloads** remained
under the strict byte-sensitive manifest/LF check. All **36 historical JSONs**
and the archived shell retain their original hashes. No private path or raw log
is included in the regenerated evidence. Remote CI is recorded separately in
the PR and must pass at the published head.
<!-- /current-validation -->

## Current branch validation

This continuation stays on `codex/issue-82-pyside6-spike`, PR #165, with source
HEAD `181741488803aeb0399477ba89fab0004ea5662f` and source tree
`ae33516f5e739478f8a41a3062bb9bd012f42207`. Q0 rechecked open #82, Draft PR #165,
closed related issues and PR history through the GitHub connector. Remote main
still resolves to `18faf9c`; its final #81 contracts, application-contract
document and project graph match this branch. Main contains no #82 archive.
This is the remaining archive/replay reconciliation after the observer fixes
in `a632e61`/`0684805` and publication at `1817414`.

The received dirty archive was preserved. Before editing, the manifest replay
failed deterministically on the changed `production-isolation-current.json`
hash: **1 failed, 130 deselected, 0 skipped**, exit **1**. The prior Linux bytes
were independently compared with the former current file at HEAD and matched.
The terminal lacked `gh` and direct GitHub networking; connector reads confirmed
the remote state without changing the issue or PR.

Current external native observations are separate from both the immutable
historical baseline and prior regenerated Linux production result:

| Current external evidence at 1817414 | Result and boundary |
|---|---|
| 12 source smoke rows | Three each on Python 3.10.11, 3.12.8, 3.13.1 and 3.14.7; Windows 10 Pro build 19045 x64, developer host. Python 3.11 unexecuted. |
| 60 final source/packaged rows | Python 3.10/3.14 only; 12 ordinary measurements and 48 audit measurements. Together with source smoke, all **72** rows pass strict current replay, zero exit, explicit false stderr/stdout flags, no Qt messages and passing shell checks. |
| Scaling audit | Ordered Qt overrides 1, 1.25, 1.5, 2; native DPI settings/transitions unverified. Every measurement retains `cold_boot_verified: false`. |
| Six relocated observations / two provenance records | Canonical source/inventory/result hashes, file counts and byte counts match current evidence. Native copy verification authenticated the relocated inventory on the same developer host; clean-machine acceptance remains pending. |
| Three source / six packaged plugin observations | Current replay passes; `qwindows.dll` discovered, no unexpected warnings/output. |
| Corrected UIA observer | 12 elements, window found, exit 0, clean stderr/stdout, zero Qt messages; exposure only, no Narrator/NVDA speech claim. |
| Native production isolation | Python 3.10.11, unchanged spec, build/help exits 0/0/0, explicit empty stderr, 52 wheel / 57 executable entries, no Qt distributions or forbidden raw entries. Prior Linux/Python 3.12.14 result at `0684805` preserved separately. |

Exact current filenames and byte hashes are in
[evidence-status.json](evidence/issue-82-pyside6/evidence-status.json).
The archive has 74 direct payloads plus its manifest (49 prior payloads and 25
new files). The architecture LF gate covers those 74 plus 18 prior Site payloads.
All 36 historical JSON hashes and received current/versioned Linux bytes remain
unchanged. Current naming, LF normalization, canonical versus byte hashing and
privacy checks are documented in the [archive README](evidence/issue-82-pyside6/README.md).

The earlier focused stage used the ordinary development environment: **CPython
3.10.11 on Windows, pytest 9.1.1**, via `python`. `V` below denotes the unique
external temporary directory allocated for this continuation; its local path
is omitted for privacy. Commands use PowerShell spelling. Test counters below
apply to the edited worktree only; the prior Linux suite totals above do not.

<!-- windows-focused-validation -->
| Exact command (`$V` is path redaction only) | Exit | Passed / skipped / deselected |
|---|---:|---|
| `python -m pytest tests/test_ui_spike_evidence.py -q -ra --tb=short --basetemp=$V/spike-reviewed -o cache_dir=$V/cache-spike` | 0 | **152 / 1 / 0** |
| `python -m pytest woff/tests/test_architecture_contracts.py -q -ra --tb=short --basetemp=$V/architecture-reviewed -o cache_dir=$V/cache-architecture` | 0 | **127 / 0 / 0** |
| `python -m pytest tests/test_ui_contracts.py -q -ra --tb=short --basetemp=$V/contracts-reviewed -o cache_dir=$V/cache-contracts` | 0 | **304 / 0 / 0** |
| `python -I -S scripts/validate_ui_fixtures.py` | 0 | **30 synthetic cases / 6 shared states**; pytest counters not applicable |
| `git diff --check` | 0 | No whitespace errors; test counters not applicable |

The single skip is the existing relocation symlink-safety test: this Windows
environment lacks permission to create symbolic links. No tests were deselected
in the three final module runs. Total: **583 passed, 1 skipped, 0 deselected**.
At that earlier focused stage the full suite was deferred by request. The
complete final validation below supersedes that pending status.

Failure/correction ledger for this continuation (same interpreter):

- Pre-edit reproduction used `python -m pytest tests/test_ui_spike_evidence.py
  -q -ra --tb=short -k evidence_digest_and_synthetic_provenance
  --basetemp=$V/preflight -o cache_dir=$V/pytest-cache`: exit 1,
  **1 failed, 0 passed, 0 skipped, 130 deselected**; stale production hash.
- The first complete edited spike run used the final command's options with
  `--basetemp=$V/spike-final`: exit 1, **13 failed, 139 passed, 1 skipped,
  0 deselected**. Twelve new assertions addressed nonexistent nested
  `result.messages`; the archive records `qt_messages` at row level. The other
  failure caught Windows `Path` case-insensitive sorting in the new manifest
  generator. Corrected the assertion to the recorded field and sorted by each
  filename string, preserving exact lexicographic order.
- The corrected complete spike run used `--basetemp=$V/spike-corrected`: exit 0,
  **152 passed, 1 skipped, 0 deselected**. Final reviewed-tree commands above
  confirm the corrected result. Initial complete architecture/contracts runs
  used `architecture-final` / `contracts-final` with their listed cache paths:
  exit 0, **127 / 304 passed**, respectively, no skips or deselections.

Review confirmed exact preservation of all 26 received JSON payloads (24 current
Windows files, current production and prior Linux production), all 36 historical
payload hashes, and the unchanged historical hash map. New decoded JSON and the
complete diff contain no private/local paths or usernames. No Issue #82 closing
keyword, platform/clean-machine promotion, native DPI/speech/cold-start claim,
licensing completion, accepted ADR or approved gate was introduced.
<!-- /windows-focused-validation -->

No production runtime, schema, packaging input, fixture, final #81 contract or
project-graph state changes. The recommendation remains **Conditional Go**,
Issue #82 incomplete/open, PR #165 Draft and the ADR Proposed; no Product Gate
approval, publication, commit, push or further Codex Review is performed.

## Final edited-worktree validation (2026-09-21)

This ledger records the complete validation requested after the earlier focused
stage. These are newly executed Windows results, not reused Linux/CI totals.
All repository commands run in `$R`, the existing Issue #82 worktree root.
`$V` is a newly allocated external temporary validation directory; the symbols
below redact local paths only. Logs, copied sources, builds, installations,
pytest basetemp/cache, and helper scripts remain outside the worktree.
No archived JSON or manifest was changed during this final-validation step.

| Interpreter/environment alias | Actual environment |
|---|---|
| `$P` | Existing development venv, CPython 3.10.11 x64, Windows 10 build 19045; pytest 9.1.1, Pyright 1.1.411, watchdog 6.0.0, psutil 7.2.2, PyYAML 6.0.3; no Qt distributions. |
| `$B` | Existing separate Qt-free production-build venv, CPython 3.10.11; build 1.6.1, wheel 0.48.0, setuptools 65.5.0, PyInstaller 6.22.3, hooks-contrib 2026.7, watchdog 6.0.0. |
| `$I` | Fresh disposable installed-wheel venv under `$V/install-env`, CPython 3.10.11; corrected runtime dependency watchdog 6.0.0; no Qt. |
| `$DevVenvParent` | Parent directory containing the existing development `.venv`, passed explicitly to Pyright because the worktree has no private development environment. |

The gate runner sets `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUTF8=1`,
`PYTHONIOENCODING=utf-8`, `TEMP=$V/tmp`, `TMP=$V/tmp` and
`PYINSTALLER_CONFIG_DIR=$V/pyinstaller-cache`. Fixture validation deliberately
uses `-I -S`; syntax validation uses `ast.parse(..., feature_version=(3, 10))`
and emits no bytecode. No tracked cache, build, log or runtime file is added.
The one dependency-install correction uses an explicit external pip cache.

Before testing, complete unstaged-diff review and independent byte/semantic
checks confirmed all 33 paths are Issue #82 reconciliation/evidence candidates;
all 36 historical hashes and their map are unchanged; the versioned Linux JSON
exactly equals the former current blob at `1817414`; and current production
source commit/tree, build inputs and native Windows flags authenticate correctly.
All 24 current Windows JSONs are UTF-8/LF, sanitized and covered by the 74-entry
basename-only sorted manifest. Decoded JSON and candidate text were checked for
private/local paths, local usernames/host identity, activation/license credentials
and real campaign data; recorded identities are the synthetic #80 fixture values.
The shell remains byte-identical, fixture-backed and isolated, imports no `woff`
module and duplicates no `woff/ui_contracts.py`. Production inputs/dependencies,
#81 contracts, schema, fixtures and graph remain unchanged. The ADR is Proposed,
recommendation Conditional Go, Issue #82 incomplete and gates unapproved.

The pytest result columns below are **passed / failed / skipped / deselected /
subtests passed**. All rows use `$P` in `$R`, with the development environment
above, and classify as **current branch validation**. No new Qt timing,
clean-machine, native DPI, speech or cold-boot observation is claimed.

| Gate | Exact command | Exit | P / F / S / D / subtests |
|---|---|---:|---|
| spike | `& $P -m pytest tests/test_ui_spike_evidence.py -q -ra --tb=short --basetemp=$V/spike -o cache_dir=$V/pytest-cache` | 0 | **152 / 0 / 1 / 0 / 0** |
| architecture | `& $P -m pytest woff/tests/test_architecture_contracts.py -q -ra --tb=short --basetemp=$V/architecture -o cache_dir=$V/pytest-cache` | 0 | **127 / 0 / 0 / 0 / 0** |
| ui-contracts | `& $P -m pytest tests/test_ui_contracts.py -q -ra --tb=short --basetemp=$V/ui-contracts -o cache_dir=$V/pytest-cache` | 0 | **304 / 0 / 0 / 0 / 0** |
| fixture-tests | `& $P -m pytest tests/test_ui_state_fixtures.py -q -ra --tb=short --basetemp=$V/fixture-tests -o cache_dir=$V/pytest-cache` | 0 | **203 / 0 / 1 / 0 / 0** |
| milestones | `& $P -m pytest woff/tests/test_product_milestones.py -q -ra --tb=short --basetemp=$V/milestones -o cache_dir=$V/pytest-cache` | 0 | **14 / 0 / 0 / 0 / 0** |
| ui-standard | `& $P -m pytest woff/tests/test_ui_development_standard.py -q -ra --tb=short --basetemp=$V/ui-standard -o cache_dir=$V/pytest-cache` | 0 | **6 / 0 / 0 / 0 / 0** |
| privacy | `& $P -m pytest woff/tests/test_privacy_contracts.py -q -ra --tb=short --basetemp=$V/privacy -o cache_dir=$V/pytest-cache` | 0 | **10 / 0 / 0 / 0 / 0** |
| packaging-tests | `& $P -m pytest tests/test_ui_spike_evidence.py -k 'packaging or production or wheel or raw_qt or executable_inventory or linux_observer' -q -ra --tb=short --basetemp=$V/packaging-tests -o cache_dir=$V/pytest-cache` | 0 | **40 / 0 / 0 / 113 / 0** |
| command-contracts | `& $P -m pytest woff/tests/test_command_contracts.py -q -ra --tb=short --basetemp=$V/command-contracts -o cache_dir=$V/pytest-cache` | 0 | **47 / 0 / 0 / 0 / 0** |
| package-version | `& $P -m pytest woff/tests/test_version_consistency.py::test_package_cli_config_example_and_version_consumers_are_consistent -q -ra --tb=short --basetemp=$V/package-version -o cache_dir=$V/pytest-cache` | 0 | **1 / 0 / 0 / 0 / 0** |
| full | `& $P -m pytest -q -ra --tb=short --basetemp=$V/full -o cache_dir=$V/pytest-cache` | 0 | **1886 / 0 / 2 / 0 / 175** |

The two full-suite skips are existing platform/privilege cases:
`test_relocation_rejects_links_and_preserves_outside_target` cannot create a
Windows symbolic link, and the fixture-catalog symlink case reports symlinks
unavailable. All other full-suite cases passed, including the Windows junction
cases skipped by the older Linux run. The full suite has **1,886 passed,
0 failed, 2 skipped, 0 deselected and 175 subtests passed**.

The following commands have no pytest cases: passed/failed/skipped/deselected/
subtest counters are **not applicable**, rather than inferred. `$P` rows are
current branch validation; `$B`/`$I` packaging rows regenerate disposable build
or install outputs for current-branch validation, never replace archived native
spike evidence. The CWD and interpreter aliases specify each actual environment.

| Gate | Exact command | CWD | Exit | Observed result |
|---|---|---|---:|---|
| fixtures | `& $P -I -S scripts/validate_ui_fixtures.py` | `$R` | 0 | 30 synthetic cases / six shared states valid |
| manifests | `& $P -B $V/audit_checks.py` | `$R` | 0 | 74 spike payloads and immutable/current hash checks passed |
| historical-replay | `& $P -B $V/replay_summary.py` | `$R` | 0 | Exact historical summary equality; 60 rows, including 48 audit rows / 2,640 checks |
| ui-v2-replay | `& $P scripts/validate_ui_v2_evidence.py` | `$R` | 0 | 60 captures / 14 states / 12 statuses / 28 complete keyboard sequences |
| graph | `& $P scripts/validate_project_graph.py` | `$R` | 0 | Project graph valid |
| wheel-build | `& $B -m build --wheel --no-isolation --outdir $V/wheel` | `$V/package-source` | 0 | Fresh wheel built successfully |
| pyinstaller-build | `& $B -m PyInstaller --clean --noconfirm --distpath $V/dist --workpath $V/build-work build.spec` | `$V/package-source` | 0 | Unchanged production spec built successfully |
| packaged-help | `& $V/dist/WoFFWatchdog/WoFFWatchdog.exe --help` | `$V` | 0 | Exit zero; stderr explicitly empty |
| install-venv | `& $B -m venv --system-site-packages $V/install-env` | `$V` | 0 | Disposable install venv created |
| wheel-install | `& $I -m pip install --no-deps --no-index $V/wheel/woff-3.2.0-py3-none-any.whl` | `$V` | 0 | Newly built wheel installed without dependencies |
| installed-imports | `& $I -B -c 'import importlib,pkgutil,woff; modules=list(pkgutil.walk_packages(woff.__path__,woff.__name__+".")); [importlib.import_module(m.name) for m in modules]; print("Installed modules imported:",len(modules))'` | `$V` | 1 | Failed: watchdog missing in new install environment; corrected below |
| installed-imports-corrected | `& $I -B -c 'import importlib,pkgutil,woff; modules=list(pkgutil.walk_packages(woff.__path__,woff.__name__+".")); [importlib.import_module(m.name) for m in modules]; print("Installed modules imported:",len(modules))'` | `$V` | 0 | 44 installed modules imported; stderr empty |
| installed-woff-watchdog | `& $V/install-env/Scripts/woff-watchdog.exe --help` | `$V` | 0 | Installed CLI help passed; stderr empty |
| installed-woff-query | `& $V/install-env/Scripts/woff-query.exe --help` | `$V` | 0 | Installed CLI help passed; stderr empty |
| installed-woff-report | `& $V/install-env/Scripts/woff-report.exe --help` | `$V` | 0 | Installed CLI help passed; stderr empty |
| install-watchdog-correction | `& $I -m pip install watchdog==6.0.0 --disable-pip-version-check --cache-dir $V/pip-cache` | `$R` | 0 | Declared watchdog 6.0.0 installed into disposable environment |
| pyright | `& $P -m pyright --venvpath $DevVenvParent` | `$R` | 0 | 0 errors / 0 warnings / 0 informations |
| syntax | `& $P -B $V/check_syntax.py` | `$R` | 0 | 105 tracked Python files + nine archived recipes pass Python 3.10 grammar |
| diff-check | `git diff --check` | `$R` | 0 | No whitespace errors |
| final-privacy | `& $P -B $V/audit_checks.py` | `$R` | 0 | All preservation, scope, privacy and isolation checks passed |

The external packaging helper first copied all **295 tracked/untracked worktree
files** byte-for-byte into `$V/package-source`, including tests and
documentation, so package exclusion checks were not bypassed by a reduced copy.
Build-system output then stayed in that disposable snapshot. Exactly one new
wheel was selected. The existing `validate_production_result` contract inspected
**52 wheel entries and 57 collected/embedded executable entries**, mandatory
metadata dependencies, no Qt distributions/artifacts, help exit zero and explicit
empty stderr. The copied `build.spec` stayed byte-identical to the worktree.
Fresh installation was exercised from `$V`, outside the source checkout.
The enclosing `& $B -B $V/validate_packaging.py` invocation ran in `$R` and
exited 1 at the missing-dependency import described below; its already successful
build/isolation subcommands are recorded individually above. After the dependency
correction, `& $P -B $V/installed_smoke.py` ran in `$R` and exited 0, repeating
the import and executing the three CLI help subcommands from `$V`. These helper
invocations have no pytest case counters and introduce no repository code.

The external `replay_summary.py` follows the earlier documented recipe: copy
archived JSON and the two recipes to a unique external directory, run
`$P summarize.py --historical` there, and compare parsed summary equality.
`audit_checks.py` checks exact SHA-256 bytes, historical-map equality, source/input
hashes, scope, LF/manifest completeness, decoded-string privacy, the preserved
synthetic boundary and unapproved governance state. Its initial direct command,
`& $P -B $V/audit_checks.py` from `$R`, exited 1 because a broad text scan matched
an existing synthetic plugin test path. Manual comparison with HEAD proved both
occurrences unchanged. The auxiliary scan now distinguishes that exact existing
fixture from actual local data; archived JSON retains the strict no-local-path
check. The corrected direct command exited 0 before tests; manifest/final scan
rows above also passed. No repository validator or test was weakened.

The other failure was environment setup: `--system-site-packages` inherits the
base interpreter packages, not the parent build venv's dependencies. Consequently
`pip install --no-deps` left watchdog absent and the first installed-module import
exited 1. Installing the declared watchdog 6.0.0 in the disposable venv corrected
that environment. The same all-module import and all three installed CLI help
checks then exited zero with empty stderr. Wheel/build/isolation checks had
already passed and their inputs were unchanged; no production correction or
archived-evidence regeneration was necessary. All repository tests and Pyright
passed on their first execution in this complete-validation stage.

`gh` is unavailable. Read-only authenticated GitHub connector checks confirmed
PR #165 is open/Draft on `codex/issue-82-pyside6-spike`, head `1817414`, with
`Related to #82` and no closing keyword; Issue #82 is open. The timeline contains
only the two prior explicit review requests (2026-09-16 00:37:18 and 01:33:00 UTC)
and the corresponding Codex reviews of `a93f040422` / `a632e61d2c`. No new review
request or GitHub mutation was performed. The remote PR body still describes the
previous evidence revision and will need reconciliation in a later authorized
publication step; it was deliberately left unchanged here.

The three evidence generations and all acceptance classifications above remain
unchanged: immutable historical Windows baseline; prior regenerated Linux
production result at `0684805`; current archived native Windows 10 developer-host
validation at `1817414`. This final ledger is current edited-branch validation,
with disposable regenerated production packaging only. External blockers remain
Windows 11, a clean representative Windows machine, Python 3.11 execution,
packaged 3.12/3.13 if required by the criterion, native DPI settings/transitions,
Narrator/NVDA speech, truly cold startup and final licensing/distribution approval.
Maintainer judgment is still needed on the packaged 3.12/3.13 acceptance matrix.

After writing this ledger, the exact `full`, `pyright`, `syntax`, `diff-check`
and `final-privacy` commands above were executed again on the final documented
worktree with the same results and exit zero. Those five rows each represent
two executions; other rows represent one execution unless separately identified.
No production, test, fixture or evidence input changed between the two full
runs; the second run additionally covers the final report text. The final manual
review found no scope expansion, private data, unsupported acceptance claim or
historical-byte change. All 32 candidate files other than this report still match
the hashes captured at the start of this final-validation step.

The technical changes are suitable for one commit on the existing branch; that does not complete #82,
accept the ADR or approve adoption/gates. The index stays empty, HEAD unchanged,
and no commit, push, merge, Ready transition, issue closure, release or further
Codex Review is performed. Complete candidate paths remain listed below.

## External evidence still required

Use the revised recipes from a clean checkout of the final PR revision, copy them
and the validated #80 catalog to an external temporary directory, and retain only
sanitized JSON and checksummed inventories. Preserve each actual measurement
revision/date/platform/interpreter; do not reuse historical result files as new output.

| Required environment | Exact command/procedure | Required artifact / acceptance evidence |
|---|---|---|
| Windows 10 and Windows 11 x64, without developer/Qt installations | Build using `run.py` in an isolated PySide6 6.11.2 environment; transfer the complete bundle; `python measure.py <bundle>/Issue82.exe <configuration>` (three runs) | Authenticated source/build/copy inventory, platform and interpreter versions, render and process evidence, explicit clean-machine preparation. Metadata alone does not pass. |
| Python 3.11; packaged 3.12/3.13 if required by the criterion | Create one optional venv per interpreter with the same pinned Qt binding; adapt the explicit interpreter matrix in `run.py`; run source and packaged `measure.py` series | Python 3.11 execution and applicable packaged provenance. Current 3.12/3.13 source smoke already passes on the developer host; it does not satisfy representative clean-machine coverage. |
| Windows desktop at native 100/125/150/200% and monitor transitions | Change Windows Display Settings for each profile; clear `QT_SCALE_FACTOR`; run the fixture shell and keyboard audit; record native transition procedure | Native DPR, geometry/focus observations and sanitized screenshots for each actual OS setting/transition. Override evidence is insufficient. |
| Windows UI Automation and Narrator or NVDA | `./uia.ps1`; manually exercise navigation/retry and record actual spoken state changes | Current Windows 10 UIA exposure already passes; representative-host exposure and a separate AT/version/procedure/announcement record remain. UIA exposure does not prove speech. |
| Reference Windows host after documented cold start | Cold-boot preparation, then `python measure.py <executable> <configuration>`; retain first samples and cache-control procedure | At least three independently prepared cold observations and warm comparisons against unchanged budgets. Current recipe labels remain uncontrolled unless a separate authentic cold procedure proves otherwise. |
| Clean representative host receiving verified native spike bundles | `py310/Scripts/python.exe relocate.py` with authenticated transfer/preparation | Same-host native relocation already passes in the current archive. Clean-host timing/provenance and preparation remain required; historical timing attribution remains unavailable. |
| Approved distribution and licensing review environment | Inventory exact candidate bundle; evaluate every library/plugin, notices, corresponding source and replacement procedure | Version-bound SBOM/notices, resolved Virtual Keyboard licensing route, demonstrated replacement rights and maintainer disposition. No clearance is claimed here. |

Recommendation remains **Conditional Go** for further evidence collection.
Issue #82 and both spike evals remain open/planned, PR #165 remains Draft,
the ADR remains Proposed, and no Product Gate or production adoption is approved.


## Consolidated correction and verification record

| Review finding | Correction and principal regression |
|---|---|
| UIA accepted unexpected stderr | Actual stderr and shell diagnostic collection; explicit false flags/zero Qt-message count; malformed/missing input fails. `test_uia_collector_reads_redirected_stderr`, `test_uia_missing_or_malformed_diagnostics_fail`, `test_uia_collector_rejects_incomplete_or_unexpected_diagnostics`. Current native Windows UIA replay passes in `test_current_windows_uia_exposure_is_not_speech`; speech and representative-host acceptance remain pending. |
| Old production JSON accepted without stderr | Old JSON is rejected and preserved; new observer records explicit false plus actual environment/build identities. `test_production_stderr_evidence_fails_closed`, `test_explicit_false_production_stderr_passes_other_valid_invariants`, `test_regenerated_production_evidence_matches_current_build_inputs`, `test_current_windows_production_is_native_and_revision_bound`. Native unchanged-spec Windows execution now passes; broader environment acceptance remains separate. |
| Raw Qt artifacts missed | Component-aware normalized DLL/library/tool/framework/plugin matching; scan wheel, executable, embedded entries and directories. `test_raw_qt_artifact_is_detected`, `test_unrelated_artifact_names_are_allowed`, `test_production_replay_recomputes_qt_inventory`, `test_executable_inventory_includes_empty_qt_plugin_directories`. Current native Windows wheel/executable/embedded inventories pass classification; this does not clear spike distribution licensing. |
| Retained bundle deleted before authentication | Inventory first; reject/preserve mismatches; reuse authentic retained copies; verify new copies; write observations into unique directories. `test_retained_relocation_mismatch_is_preserved`, `test_verified_retained_relocation_is_not_replaced`, `test_relocation_rejects_links_and_preserves_outside_target`. `test_current_windows_relocation_authenticates_current_build_and_results` independently authenticates both current native executions. Historical attribution remains superseded; clean-machine acceptance is pending. |
| Stale validation and inventory totals | Current focused gates cover 74 exact spike payloads plus 18 prior Site payloads, with all 36 historical JSON hashes pinned. Full-suite validation of the edited tree now passes as recorded in the final validation ledger below. `test_evidence_digest_and_synthetic_provenance`, `test_historical_observations_and_provenance_are_not_rewritten`, existing raw-LF architecture gate. |

Root causes: A — permissive diagnostic collection/replay; B — incomplete
artifact identity/isolation/provenance; C — revision-unbound evidence reporting.
Equivalent-case review also tightened measurement first-paint/stdout handling,
plugin boolean/stdout replay, and summary input validation. Explicit historical
mode preserves only recorded invariants and cannot produce current acceptance.

The prior consolidation Q0 rechecked both completed Codex Reviews (a93f040 and a632e61), all eight
threads and both original PR commits, closed #81/#136, and authoritative main.
Current main contains the final contracts but no #82 evidence implementation;
the remaining observer defects were reproduced on the synchronized PR tree.
At that earlier consolidation, the worktrees contained no unrelated changes.
This continuation instead preserves the intentionally dirty authenticated archive. No third review is requested.

Prior consolidation development validation (not current edited-tree totals):

| Command / environment | Exit and exact result | Classification / correction |
|---|---|---|
| `git fetch origin` | 128; configured #81 remote branch had been deleted | Preflight; explicit `git fetch origin refs/heads/main:refs/remotes/origin/main refs/heads/codex/issue-82-pyside6-spike:refs/remotes/origin/codex/issue-82-pyside6-spike` passed. |
| `git merge --no-ff --no-commit origin/main`; sync spike/contracts/fixtures/architecture pytest selection | 0; no conflicts; 652 passed, no skips | Current branch synchronization; both main integrations preserved. |
| `P -m pytest tests/test_ui_spike_evidence.py -q -ra --tb=short -k 'uia_recipe_collects or archived_production_result_requires or raw_qt or retained_relocation'` | 1; 18 failed, 4 passed, 36 deselected, no skips | Expected pre-fix reproductions. |
| Focused corrections excluding not-yet-regenerated records | 0; 110 passed, 3 deselected, no skips | Initial focused correction. |
| Expanded focused corrections | 1; 2 failed, 124 passed, 3 deselected; then 0, 126 passed, 3 deselected | Discovered historical empty-stderr/unload flag inconsistency; retained only under explicit historical replay. |
| Linux filename adaptation focused rerun | 0; 127 passed, 3 deselected, no skips | Temporary observer adaptation covered by regression. |
| First unchanged production observer, separate Linux environment | 1; wheel build 0, PyInstaller build 1 | Exact production spec EXE/COLLECT filename collision; no passing claim. |
| Observer with `--linux-executable-suffix`, first successful candidate | 0; both builds 0, help 0, stderr false | Regenerated Linux candidate, replaced by final regeneration after directory-inventory correction. |
| Candidate Pyright before package installation finished | 1; 5 missing-watchdog-import errors | Environment setup; installed built wheel/watchdog, rerun 0 errors/0 warnings. |
| Candidate spike / related gates / full suite | 0; 130 passed / 665 passed / 1,861 passed, 4 Windows-only junction skips, 175 subtests | Pre-final candidate; superseded by final validation after the additional directory case. |
| `P -m pytest tests/test_ui_spike_evidence.py -q -k empty_qt_plugin_directories` | 1; 1 failed, 130 deselected; after correction 0, 1 passed, 130 deselected | Empty plugin directories were omitted from executable inventory; now included. |
| `git -c credential.interactive=false push --dry-run origin HEAD:refs/heads/codex/issue-82-pyside6-spike` | 128; terminal has no write credential | Publication uses the already connected GitHub app, exact Git blob/tree hashes, and a non-force fast-forward ref update. |

The GitHub source merge has the original PR tip and authoritative main as
parents. It preserves the published history. Local unpublished commits were
aligned to the identical GitHub tree with compare-and-swap `git update-ref`;
no worktree content or unrelated branch was replaced. That earlier result publication
used the same identity checks, followed by tests at its exact publication commit.


## Files changed by the prior consolidation

- `docs/architecture/adr-ui-toolkit.md`
- `docs/ui/evidence/issue-82-pyside6/README.md`
- `docs/ui/evidence/issue-82-pyside6/SHA256SUMS`
- `docs/ui/evidence/issue-82-pyside6/evidence-status.json`
- `docs/ui/evidence/issue-82-pyside6/evidence_contract.py.txt`
- `docs/ui/evidence/issue-82-pyside6/measure.py.txt`
- `docs/ui/evidence/issue-82-pyside6/plugin_probe.py.txt`
- `docs/ui/evidence/issue-82-pyside6/production-isolation-current.json`
- `docs/ui/evidence/issue-82-pyside6/production_check.py.txt`
- `docs/ui/evidence/issue-82-pyside6/relocate.py.txt`
- `docs/ui/evidence/issue-82-pyside6/summarize.py.txt`
- `docs/ui/evidence/issue-82-pyside6/uia.ps1.txt`
- `docs/ui/pyside6-spike-82.md`
- `tests/test_ui_spike_evidence.py`
- `woff/tests/test_architecture_contracts.py`

The cumulative PR also retains its original historical JSON archive, `.gitattributes`
rule and eval-catalog link. Those historical payloads are preserved, not regenerated.


## Files in this uncommitted continuation

Seven tracked files were edited in this continuation; the already modified
production result and 25 already untracked evidence files were preserved.
The complete worktree diff relative to HEAD contains these 33 paths:

- `docs/architecture/adr-ui-toolkit.md` (edited reconciliation)
- `docs/ui/evidence/issue-82-pyside6/README.md` (edited reconciliation)
- `docs/ui/evidence/issue-82-pyside6/SHA256SUMS` (edited reconciliation)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-build-inventory.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-final-packaged310-audit.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-final-packaged310.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-final-packaged314-audit.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-final-packaged314.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-final-source310-audit.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-final-source310.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-final-source314-audit.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-final-source314.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-inventory10.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-inventory12.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-inventory13.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-inventory14.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-plugin-discovery.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-relocated310.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-relocated314.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-relocation-provenance310.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-relocation-provenance314.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-source-plugin-discovery.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-source310-smoke.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-source312-smoke.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-source313-smoke.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-source314-smoke.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/current-windows10-uia.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/evidence-status.json` (edited reconciliation)
- `docs/ui/evidence/issue-82-pyside6/production-isolation-current.json` (preserved received evidence)
- `docs/ui/evidence/issue-82-pyside6/production-isolation-linux-0684805.json` (preserved received evidence)
- `docs/ui/pyside6-spike-82.md` (edited reconciliation)
- `tests/test_ui_spike_evidence.py` (edited reconciliation)
- `woff/tests/test_architecture_contracts.py` (edited reconciliation)
