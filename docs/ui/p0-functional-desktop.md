# P0 — Functional Desktop Prototype (Issue #140)

Status: experimental implementation on Issue #140 Draft PR; physical Windows P0 demonstration completed on 2026-09-29. This record is branch evidence, not Product Gate or ADR approval.

## User capability gained

A maintainer can launch an actual Qt Widgets WoFF Mate window, navigate the seven V2 destinations from one persistent shell, switch between two same-name synthetic careers distinguished by stable ID and WoFF slot, inspect the fixture-backed content and six shared states, and use the shell by keyboard. The executable presents the committed V2 icon, portrait, branding and palette. It starts deterministically with synthetic career 02 in Operations, and restart does not use any saved configuration.

**Data class:** `Synthetic fixture-backed only`.

The first career (`synthetic-career-02`, WoFF Pilot 2) has ready snapshots for Operations, Dossier, Missions, Squadron, War Diary and Reports. The second (`synthetic-career-03`, WoFF Pilot 3) has authoritative selector identity but no screen payload in the #80 catalog. Switching to it immediately removes prior widgets and portrait and shows `missing/source_missing` under career 03; no record or timestamp from career 02 is reused. Global System Status remains independent of the selected career. This is deliberate fixture coverage, not a live-source failure.

## Architecture and supported behavior

- `woff/p0_desktop/fixtures.py` reads the closed 30-case #80 catalog from the source tree or the separately bundled P0 data. It maps fields and envelopes into the six frozen #81 snapshots in `woff/ui_contracts.py`. The #81 contracts are imported, not copied into the toolkit package. Reports lacks a #81 snapshot; a small frozen P0-only report value checks career ownership and cardinality.
- `woff/p0_desktop/window.py` consumes those immutable values. The shell retains six primary buttons, a separated `SYS-01` footer, career context, page title and content. Top-level navigation moves focus once to the page heading. The heading has click/programmatic focus, while Tab moves through controls. Arrow keys traverse the rail; Enter/Space activate native Qt buttons; the selector is a native combo box with disambiguating persistent slots. The first Tab stop skips to content. Retry in the synthetic error scenario selects the ready fixture; it never invokes ingestion or repair.
- The explicitly labelled **P0 FIXTURE STATE** combo exercises `ready`, `loading`, `empty`, `missing`, `stale/unavailable` and `error` with canonical scenario IDs visible under the heading. These are independent scenarios, not an invented historical sequence. On career 03, the selector-only inventory means every career-screen request resolves to `missing`.
- `woff/assets/ui/icons/` supplies navigation and retry icons. SVG `currentColor` is resolved in memory; committed masters remain unchanged. `woff/assets/ui/branding/` supplies the shell mark and window ICO, bundled only in the separate P0 spec rather than ordinary package data. The exemplar portrait is restricted to `DOS-01` with `pilot-ready`; the approved neutral fallback is used for an unmapped dossier payload. Images never supply identity or status.
- Layouts use Qt logical dimensions and a scrollable vertical content region with no horizontal scrolling. The labelled rail compacts at narrower widths; the context controls occupy two rows. This design targets the #82 100/125/150/200% scaling profiles, subject to the physical Windows interaction check below.

Intentionally unavailable: live SQLite, WoFF installation/campaign file reads, parsers, catalogers, repositories, watchdog, ingestion, writes, editable settings, launch/session control, synchronization, network requests, personal data, runtime AI, public distribution and production social/RPG actions. No button promises these capabilities.

## Reproducible launch and prototype build

From the repository root in an isolated Python 3.10–3.14 environment:

```powershell
py -3.10 -m venv .venv-p0
.venv-p0\Scripts\python.exe -m pip install -e . PySide6==6.11.2 pyinstaller
.venv-p0\Scripts\python.exe -I -S scripts\validate_ui_fixtures.py
.venv-p0\Scripts\python.exe -m woff.p0_desktop --smoke
.venv-p0\Scripts\python.exe -m woff.p0_desktop
```

The source launch is deliberately from the repository root: the closed fixture catalog and `woff.p0_desktop` remain excluded from the ordinary production wheel. PySide6 6.11.2 is installed explicitly into the isolated P0 environment; the base dependency metadata and existing Qt-free `build.spec` are unchanged. `--smoke` constructs, shows and closes the shell with no event loop or external state. CI exercises this source and bundle in a separate Linux offscreen P0 job; it does not substitute for the Windows walkthrough.

For a maintainer-evaluation Windows folder bundle, from the same root and isolated environment:

```powershell
.venv-p0\Scripts\python.exe -m PyInstaller --clean --noconfirm --distpath .p0-dist --workpath .p0-build p0_desktop.spec
.p0-dist\WoFFMateP0\WoFFMateP0.exe --smoke
.p0-dist\WoFFMateP0\WoFFMateP0.exe
```

Keep the complete `WoFFMateP0` folder together. This is a prototype bundle, not an installer or approved release. Output directories above are ignored local build products, not repository evidence.

## Demonstration and validation evidence

Representative synthetic captures live in [`evidence/issue-140-p0`](evidence/issue-140-p0/) with SHA-256 inventory. These are **Linux Qt offscreen** screenshots of Operations ready, Dossier ready, Missions error and career 03 missing. Reproduce from the repository root with `QT_QPA_PLATFORM=offscreen python -m scripts.capture_p0 docs/ui/evidence/issue-140-p0` on a suitable Linux test host. They are product-flow illustrations, not Windows DPI or UIA certification and do not supersede #79/#82 historical evidence.

Portable checks: `tests/test_p0_desktop.py` proves seven routes and six states, immutable ID isolation, immediate widget clearing, focus and clean reopen via Qt offscreen, asset resolution and a structural forbidden-import boundary. The separate P0 PyInstaller spec excludes live integration modules. The #82 archived Windows 10 evidence established toolkit feasibility at the four Qt override scaling profiles; it did not execute this Issue #140 window. No #82 measurement is relabelled as a P0 measurement.

**Startup/package comparison with #82:** Issue #82 remains the historical measured baseline and its measurements are not relabelled as P0 results. Its final Windows 10 series recorded launch-to-paint samples of `0.467 / 0.459 / 0.448 s` for Python 3.10 source and `0.479 / 0.461 / 0.467 s` for Python 3.14 source; packaged samples were `0.552 / 0.431 / 0.428 s` on Python 3.10 and `0.550 / 0.456 / 0.464 s` on Python 3.14. The corresponding complete onedir artifacts were `110.08 MB` and `116.83 MB`. The Issue #140 physical walkthrough did not repeat that benchmark or produce a new timing series; it confirmed functional source and folder-bundle launch, close and reopen on the same Windows 10 development host. Therefore #82 supplies the inherited quantitative startup/package baseline while #140 supplies revision-specific functional demonstrability evidence.

**Physical Windows P0 check — completed 2026-09-29:** The fixture-backed P0 was exercised on the physical Windows 10 developer host from both source and the PyInstaller folder bundle at 100%, 125%, 150% and 200% display scaling. All seven destinations remained reachable; Tab/Shift+Tab, rail arrows, Enter/Space, selector interaction, heading focus and Retry were usable; Pilot 2 → same-name Pilot 3 switching cleared the previous widgets, portrait and data before presenting the expected missing state; resizing remained usable at all four profiles; and source/bundle close and reopen succeeded. The detailed maintainer-observed record is in [`evidence/issue-140-p0/windows-physical-walkthrough.md`](evidence/issue-140-p0/windows-physical-walkthrough.md). No Windows screenshots were captured. The existing representative screenshots remain explicitly Linux Qt offscreen evidence and are not relabelled as Windows observations. This walkthrough is P0 functional evidence only, not Narrator/NVDA, clean-machine, release-certification, ADR-adoption, R2 or Product Gate evidence.

## Architecture status and P1 blockers

PySide6 + Qt Widgets **6.11.2** is authorized only for experimental P0. The UI toolkit ADR remains **Proposed**; **R2 is pending** until post-P0 review; no Product Gate is approved. Issue #140 and its graph dependency into R2 remain pending until integration and acceptance.

Actual blockers to **P1 — Read-only Vertical Slice**: post-P0 R2 architectural decision and applicable ADR adoption gates; approved application query services; and authorization of the narrow real local read-only data path. The physical P0 Windows launch/build/interaction validation is complete. The fixture inventory's second-career screen absence is a P0 demonstration limitation, not a reason to invent live data or reopen #80.
