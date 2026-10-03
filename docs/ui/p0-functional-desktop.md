# P0 — Functional Desktop Prototype (Issue #140)

Status: Issue #140 completed and integrated through merged PR #173 at `main`
`bfa7647ac94cafba658a077e52a55a3c2240a4dd`. The implementation remains an
experimental, fixture-backed P0 product-demonstrability record, not Product
Gate approval, production-retention authorization or ADR acceptance.

## User capability gained

A maintainer can launch an actual Qt Widgets WoFF Mate window, navigate the seven V2 destinations from one persistent shell, switch between two same-name synthetic careers distinguished by stable ID and WoFF slot, inspect the fixture-backed content and six shared states, and use the shell by keyboard. The executable presents the committed V2 icon, portrait, branding and palette. It starts deterministically with synthetic career 02 in Operations, and restart does not use any saved configuration.

**Data class:** `Synthetic fixture-backed only`.

PR #173 merged the P0 implementation after green CI #303 and correction of all
eight P2 review findings. This integration completes #140/P0 only; it does not
convert the isolated prototype path into production UI architecture.

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

This evidence satisfies only `Q4-P0-PROTOTYPE`: source launch/smoke and a
prototype PyInstaller folder build with bundle smoke/launch on the approved
Windows development/test environment, physical 100/125/150/200% scaling,
close/reopen, the synthetic fixture-only boundary and truthful prototype/not-
installer labeling. It does not satisfy or replace full Q4 obligations for a
clean production machine, installer, installation/update/rollback, release
checksums/signing/provenance or production distribution, and it approves no
Product Gate.

## Demonstration and validation evidence

Representative synthetic captures live in [`evidence/issue-140-p0`](evidence/issue-140-p0/) with SHA-256 inventory. These are **Linux Qt offscreen** screenshots of Operations ready, Dossier ready, Missions error and career 03 missing. Reproduce from the repository root with `QT_QPA_PLATFORM=offscreen python -m scripts.capture_p0 docs/ui/evidence/issue-140-p0` on a suitable Linux test host. They are product-flow illustrations, not Windows DPI or UIA certification and do not supersede #79/#82 historical evidence.

Portable checks: `tests/test_p0_desktop.py` proves seven routes and six states, immutable ID isolation, immediate widget clearing, focus and clean reopen via Qt offscreen, asset resolution and a structural forbidden-import boundary. The separate P0 PyInstaller spec excludes live integration modules. The #82 archived Windows 10 evidence established toolkit feasibility at the four Qt override scaling profiles; it did not execute this Issue #140 window. No #82 measurement is relabelled as a P0 measurement.

**Startup/package comparison with #82:** Issue #82 remains the historical measured baseline and its measurements are not relabelled as P0 results. Its final Windows 10 series recorded launch-to-paint samples of `0.467 / 0.459 / 0.448 s` for Python 3.10 source and `0.479 / 0.461 / 0.467 s` for Python 3.14 source; packaged samples were `0.552 / 0.431 / 0.428 s` on Python 3.10 and `0.550 / 0.456 / 0.464 s` on Python 3.14. The corresponding complete onedir artifacts were `110.08 MB` and `116.83 MB`. The Issue #140 physical walkthrough did not repeat that benchmark or produce a new timing series; it confirmed functional source and folder-bundle launch, close and reopen on the same Windows 10 development host. Therefore #82 supplies the inherited quantitative startup/package baseline while #140 supplies revision-specific functional demonstrability evidence.

**Physical Windows P0 check — completed 2026-09-29:** The fixture-backed P0 was exercised on the physical Windows 10 developer host from both source and the PyInstaller folder bundle at 100%, 125%, 150% and 200% display scaling. All seven destinations remained reachable; Tab/Shift+Tab, rail arrows, Enter/Space, selector interaction, heading focus and Retry were usable; Pilot 2 → same-name Pilot 3 switching cleared the previous widgets, portrait and data before presenting the expected missing state; resizing remained usable at all four profiles; and source/bundle close and reopen succeeded. The detailed maintainer-observed record is in [`evidence/issue-140-p0/windows-physical-walkthrough.md`](evidence/issue-140-p0/windows-physical-walkthrough.md). No Windows screenshots were captured. The existing representative screenshots remain explicitly Linux Qt offscreen evidence and are not relabelled as Windows observations. This walkthrough is P0 functional evidence only, not Narrator/NVDA, clean-machine, release-certification, ADR-adoption, R2 or Product Gate evidence.

**Post-review physical Windows revalidation — completed 2026-10-02:** After
the review-driven corrections and before integration, the corrected source and
rebuilt PyInstaller folder bundle passed again on the same physical Windows 10
development host at 100%, 125%, 150% and 200% display scaling. The maintainer
rechecked all seven destinations, standard/compact navigation, career-label
legibility, stale/unavailable Retry, the Operations payload guard, empty-view
identity preservation, same-name career isolation, resizing, close and reopen.
This later pass supplements rather than rewrites the historical 2026-09-29
walkthrough. Local Windows screenshots from revalidation were not committed;
the versioned captures remain Linux Qt offscreen evidence. The same detailed
walkthrough record distinguishes both observation dates and evidence classes.

### Physical-evidence revision binding

The post-review physical run executed on
`64710a0b1bc46c19f267db10e4168403ce974066`; it did **not** execute after the
squash merge. The final branch documentation commit was
`691749ce3e2c9e9c807142c1c6b326846c4bc269`, and R2 audited squash-merged `main`
at `bfa7647ac94cafba658a077e52a55a3c2240a4dd`. The physical result applies to
the audited merge because repository comparisons prove that all relevant P0
runtime, bundle, test, contract, fixture and asset inputs are byte-identical:

```text
git diff --exit-code 64710a0b1bc46c19f267db10e4168403ce974066 bfa7647ac94cafba658a077e52a55a3c2240a4dd -- pyproject.toml woff/__init__.py woff/p0_desktop p0_desktop.spec p0_launcher.py tests/test_p0_desktop.py woff/ui_contracts.py woff/nation.py woff/maps.py woff/tests/fixtures/ui_states woff/assets/ui/icons woff/assets/ui/portraits woff/assets/ui/branding scripts/validate_ui_fixtures.py
```

Result: no output, exit 0. The same input set was therefore unchanged between
the physically validated revision and audited merge. The intervening branch
change was evidence-only:

```text
git diff --name-only 64710a0b1bc46c19f267db10e4168403ce974066 691749ce3e2c9e9c807142c1c6b326846c4bc269
docs/ui/evidence/issue-140-p0/windows-physical-walkthrough.md
```

Finally, the final pre-merge PR tree and audited squash tree are identical:

```text
git diff --exit-code 691749ce3e2c9e9c807142c1c6b326846c4bc269 bfa7647ac94cafba658a077e52a55a3c2240a4dd
# no output, exit 0
git rev-parse 691749ce3e2c9e9c807142c1c6b326846c4bc269^{tree}
6927873b08f3867fa3d43bb620f1de9910b4e560
git rev-parse bfa7647ac94cafba658a077e52a55a3c2240a4dd^{tree}
6927873b08f3867fa3d43bb620f1de9910b4e560
```

This is direct content equivalence across the squash boundary, not an ancestry
claim and not a relabeling of the physical run as post-merge testing.

The explicit keyboard observations came from the original 2026-09-29 run at
`46b18097be490f1741f5792c84d945f6077c465b`; the 2026-10-02 revalidation did
not enumerate Tab/Shift+Tab, rail Up/Down, Enter/Space or selector sequences.
`window.py` is not claimed to be wholly identical between that original head
and audited `bfa7647...`. The ordinary command
`git diff --unified=1 46b18097be490f1741f5792c84d945f6077c465b bfa7647ac94cafba658a077e52a55a3c2240a4dd -- woff/p0_desktop/window.py`
showed only destination-specific empty messages, rail width, selector-label
styling, warning de-duplication, stale Operations Retry and an Operations-card
guard — no keyboard-contract change.

The [R2 keyboard-walkthrough revision binding](../engineering/r2-ui-architecture-review.md#keyboard-walkthrough-revision-binding)
records the full exact AST extraction/comparison command and its hashes. It
returned exit 0 and `RESULT: 8/8 keyboard-relevant AST blocks identical` for
the skip-control focus, navigation-button construction, career `QComboBox`,
`QWidget.setTabOrder(...)`, `_nav_button`, `eventFilter`, `navigate(...)` and
heading-focus-transfer blocks. Both revisions lack a `keyPressEvent` override,
so the physical Enter/Space and selector observations continue to bind to the
unchanged native `QPushButton`/`QComboBox` behavior. Thus the original keyboard
walkthrough remains applicable to audited `bfa7647...` by reproducible source
equivalence; it is not relabelled as post-merge, and no physical rerun was
required.

## Architecture status and P1 blockers

PySide6 + Qt Widgets **6.11.2** is authorized only for experimental P0. The UI
toolkit ADR remains **Proposed**. The [first R2 review](../engineering/r2-ui-architecture-review.md)
of the exact integrated SHA returned **HOLD / Conditional No-Go for production
retention**: it found no new priority:P0 or priority:P1 UI defect and confirmed
the fixture-only boundary, but adoption-readiness evidence remains incomplete.
P1 is not authorized and no Product Gate is approved. `review-r2` and its final
eval remain pending until the relevant adoption-readiness work, a revision-valid
repeat review and the explicit maintainer ADR decision.

Actual blockers to **P1 — Read-only Vertical Slice**: completion of the
adoption-readiness evidence, a revision-valid R2 production-retention decision
and applicable ADR adoption gates; approved application query services; and
authorization of the narrow real local read-only data path. The physical P0
Windows launch/build/interaction validation is complete. The fixture inventory's
second-career screen absence is a P0 demonstration limitation, not a reason to
invent live data or reopen #80.
