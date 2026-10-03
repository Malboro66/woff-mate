# Issue #140 - Physical Windows P0 Walkthrough

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

## Post-review physical revalidation — 2026-10-02

**Branch:** `codex/issue-140-p0-functional-desktop`
**Validated head:** `64710a0b1bc46c19f267db10e4168403ce974066`
**Platform:** Windows 10 Pro 64-bit, build 19045
**Toolkit:** PySide6 6.11.2
**CI:** CI #302 completed successfully before this physical revalidation.

This follow-up walkthrough was performed after the second Codex Review correction pass and refreshed Linux offscreen evidence. It supplements, rather than replaces, the original 2026-09-29 physical walkthrough.

The revalidation specifically covered the review-driven presentation and state-handling corrections, including the standard-width navigation rail, stale/unavailable Operations behavior, retry behavior, payload guarding, career identity preservation for empty views, career isolation, and corrected presentation styling.

### Source application

**PASS — 100%, 125%, 150% and 200% Windows display scaling.**

The source application remained launchable and usable across all four required scaling profiles.

Observed results:

- all seven canonical destinations remained accessible;
- the normal navigation rail rendered correctly at standard window width;
- resizing to a narrow window preserved usable compact navigation;
- the `CAREER` context label remained legible;
- no blocking clipping, overlap, unexpected horizontal scrolling or inaccessible essential content was observed;
- switching synthetic Pilot 2 → same-name synthetic Pilot 3 immediately removed the previous career payload;
- switching back to Pilot 2 restored the correct fixture-backed content;
- Operations `stale/unavailable` exposed `Retry fixture view`;
- retry returned Operations to `ready`;
- the `Latest mission` card was not presented when the stale/unavailable Operations snapshot had no retained payload;
- Operations and Pilot Dossier empty views preserved the supplied career identity without inventing unavailable service/statistical content;
- close and reopen behavior remained functional.

### PyInstaller folder bundle

**PASS — 100%, 125%, 150% and 200% Windows display scaling.**

The rebuilt PyInstaller folder bundle passed the same required physical checks at all four scaling profiles.

Observed results:

- all seven destinations remained accessible;
- navigation, labels and controls remained legible and usable;
- no blocking clipping, overlap or unexpected horizontal scrolling was observed;
- same-name career switching did not retain stale content;
- Operations stale/unavailable exposed Retry;
- the stale Operations view did not show a false `Latest mission` card when no retained payload was present;
- closing and reopening the bundle succeeded normally.

### Screenshot handling

Local Windows screenshots were captured during this revalidation for maintainer inspection at several scaling profiles, but they are not committed repository evidence.

The versioned screenshots under `docs/ui/evidence/issue-140-p0/` remain the regenerated Linux Qt offscreen product-flow evidence. No Windows screenshot is relabelled as Linux evidence, and no Linux screenshot is relabelled as Windows physical evidence.

### Revalidation result

**PASS**

The post-review physical Windows revalidation confirms the corrected P0 desktop behavior in both source and PyInstaller folder-bundle form across the required 100%, 125%, 150% and 200% display scaling profiles.

This remains P0 functional-demonstration evidence only. It does not adopt the PySide6 ADR, complete R2, approve a Product Gate, authorize P1, or constitute release or accessibility certification.
