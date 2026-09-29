# Issue #140 â€” Physical Windows P0 Walkthrough

**Date:** 2026-09-29
**Platform:** Windows 10 Pro 64-bit, build 19045
**Branch:** `codex/issue-140-p0-functional-desktop`
**Commit:** `46b18097be490f1741f5792c84d945f6077c465b`
**Python:** 3.10.11
**PySide6:** 6.11.2
**PyInstaller:** 6.22.3

This record captures maintainer-observed execution of the fixture-backed P0 desktop prototype on the physical Windows 10 development host.

It is functional demonstration evidence only. It is not Product Gate approval, ADR adoption, R2 completion, release certification, clean-machine certification, Narrator/NVDA evidence, or authorization for P1.

No Windows screenshots were captured during this walkthrough. The representative synthetic screenshots already committed under `docs/ui/evidence/issue-140-p0/` remain Linux Qt offscreen product-flow illustrations and are not relabelled as Windows evidence.

## Environment and launch

The isolated P0 environment was created successfully.

Fixture validation passed:

`UI fixtures valid: 30 synthetic cases, 6 shared states.`

The source `--smoke` launch completed successfully.

The source application launched normally on the physical Windows host.

The PyInstaller folder bundle was built successfully, its `--smoke` launch completed successfully, and the bundled application launched normally.

## 100% scaling

**PASS**

The source application opened in Operations with synthetic Pilot 2 selected.

All seven primary destinations were reached successfully:

- Operations
- Pilot Dossier
- Missions
- Squadron
- War Diary
- Reports
- Data & System Status

No blocking clipping or overlap was observed.

The six canonical fixture states were exercised successfully:

- ready
- loading
- empty
- missing
- stale/unavailable
- error

Retry returned the application to `ready`.

Keyboard interaction was exercised successfully using:

- Tab
- Shift+Tab
- navigation-rail arrow keys
- Enter
- Space
- career selector
- page-heading focus after destination changes
- keyboard activation of Retry

Career isolation was exercised on Pilot Dossier.

Switching from synthetic Pilot 2 to the same-name synthetic Pilot 3 immediately removed the previous career's widgets, portrait and data. Career 03 displayed the expected missing/source_missing state. Switching back to Pilot 2 restored the correct fixture-backed dossier.

The source application closed and reopened normally without retaining the previous session state.

The PyInstaller bundle also passed the seven-destination walkthrough, career switch, keyboard interaction, fixture-state/Retry checks and resizing.

## 125% scaling

**PASS**

Source and PyInstaller bundle launched successfully.

All seven destinations remained accessible.

Window resizing remained usable without blocking clipping or overlap.

Basic keyboard navigation remained functional.

Switching Pilot 2 to Pilot 3 removed the previous career content immediately.

## 150% scaling

**PASS**

Source and PyInstaller bundle launched successfully.

All seven destinations remained accessible.

Window resizing remained usable without blocking clipping or overlap.

Basic keyboard navigation remained functional.

Switching Pilot 2 to Pilot 3 removed the previous career content immediately.

## 200% scaling

**PASS**

Source and PyInstaller bundle launched successfully.

All seven destinations remained accessible.

Window resizing remained usable without blocking clipping, overlap, unexpected horizontal scrolling or inaccessible essential content.

Basic keyboard navigation remained functional.

Switching Pilot 2 to Pilot 3 removed the previous career content immediately.

## Result

**PASS**

The Issue #140 fixture-backed P0 desktop prototype was successfully demonstrated on the physical Windows 10 development host in both source and PyInstaller folder-bundle form at 100%, 125%, 150% and 200% display scaling.

The walkthrough exercised launch/reopen behavior, all seven primary destinations, deterministic fixture states, keyboard interaction, resizing and stable career isolation.

No live SQLite database, WoFF campaign files, parsers, catalogers, repositories, watchdog, launcher/session control, network access, runtime AI or real player data were exercised.

This result closes the pending physical Windows functional walkthrough for P0. It does not adopt the PySide6 ADR, complete R2, approve any Product Gate, authorize P1, or constitute release certification.
