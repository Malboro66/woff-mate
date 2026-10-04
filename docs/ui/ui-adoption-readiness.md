# Bounded UI Adoption Readiness — Issue #177

Implementation in progress from verified main
`741bad8192517c4ade38e9e718845f086beff849` after #175 / PR #176.

This candidate validates PySide6 + Qt Widgets 6.11.2 with deterministic synthetic
fixtures. The UI toolkit ADR remains **Proposed**. Historical first R2 remains
**HOLD / Conditional No-Go for production retention**. P1 is not authorized and
Product Gates A, B, C and D remain unapproved. #96/#142 remain Gate A/P1 blockers,
not toolkit-retention blockers.

## Evaluation contract

- `EVAL-UI-ADOPTION-MATRIX-001`: real Python 3.10–3.14 source/UI smoke,
  optional dependency isolation and exactly one Qt binding.
- `EVAL-UI-ADOPTION-PACKAGE-001`: separate fixture-only candidate packaging,
  representative startup, keyboard/focus/accessibility and proportional physical
  Windows 10 launch/basic UIA delta.
- `EVAL-UI-ADOPTION-LICENSE-001`: actual bundle inventory, hashes, origins and
  engineering licensing disposition; remove Qt Virtual Keyboard and unnecessary
  modules/plugins and prevent their reintroduction.

Evidence is pending until executed and revision-bound. Linux offscreen and hosted
Windows CI cannot substitute for the maintainer's physical Windows 10 delta.
Unchanged P0 rendering/scaling evidence may be reused with explicit source hashes.

## Canonical entry and optional installation

For this phase the supported UI paths are a source checkout and the separate
one-directory `WoFFMateAdoption` bundle. The canonical source command, from the
checkout root, is `python ui_adoption_launcher.py`. Install its optional toolkit
with `python -m pip install '.[ui]'` into a fresh venv. The launcher checks the
exactly-one-binding invariant before importing Qt. `--help` does not need Qt.

The base wheel/`pip install .` remains headless and does not ship P0 widgets,
the synthetic test catalog, or a UI console entry point. The `ui` extra declares
the pinned candidate toolkit; it does not turn that wheel into a standalone UI
installation. A final installed production UI entry point belongs to a later
authorized architecture/integration step. Do not advertise `python -m
woff.p0_desktop` as the guarded candidate entry: that is the historical P0 command.

`ui_adoption.spec` wraps the unchanged P0 window/fixtures and excludes live
database/parser/repository/watchdog code. It does not modify `build.spec` or
`p0_desktop.spec`. Linux offscreen is evidence only; physical Windows 10 remains
the reference desktop. No rendering/layout changes justify a repeated DPI suite.

## Reproduction

Use a clean checkout of the recorded candidate revision and a fresh environment:

```sh
python -m pip install .
python -c "from scripts.ui_adoption_support import check_bindings; check_bindings(base=True)"
python -m pip install '.[ui]' pytest pyinstaller==6.22.3 pyinstaller-hooks-contrib==2026.8
python ui_adoption_launcher.py --smoke --evidence build/adoption/source.json
python -m PyInstaller --clean --noconfirm ui_adoption.spec
python -m scripts.ui_adoption_inventory dist/WoFFMateAdoption build/adoption/inventory.json
```

On Linux set `QT_QPA_PLATFORM=offscreen`. Run the packaged executable with
`--smoke --evidence build/adoption/bundled.json`. The source/bundle smoke sends
Tab, Shift+Tab, arrow, Space and selector events, checks focus movement and retry,
and checks Qt accessible names/roles/focusability. The selectable navigation
buttons are exposed by Qt as CheckBox roles (Windows UIA must confirm this);
Space is their keyboard activation. Enter is not asserted for non-default push
buttons. Qt accessibility interface results are not native Windows UIA evidence.

The packaging spec refuses uncommitted candidate inputs. Its embedded build record
has the actual Git revision and SHA-256 of every relevant source/fixture/asset,
policy and licensing input. Inventories list every collected file, its hash,
Qt module/plugin classification, package metadata identities and sanitized binary
source origin. CI artifacts retain reports and Windows candidate bundles privately.

## Physical Windows 10 delta — pending

After obtaining a passing Windows endpoint candidate and its matching inventory,
run from the checkout root in PowerShell (do not set the offscreen platform):

```powershell
.\scripts\validate_ui_adoption_windows.ps1 -Bundle .\dist\WoFFMateAdoption -Inventory .\build\adoption\inventory.json -Output .\build\adoption\physical-windows10-uia.json -PhysicalWindows10
```

This verifies the exact file set/hashes, launches only the candidate window and
checks representative native UIA names, roles, enabled/focusable status and button
focus acquisition. Hosted runs found that UIA `SetFocus` did not move focus into
the combo selectors. The collector records each unsuccessful combo focus request
and its observed target in `programmatic_combo_focus_warnings`; it does not
relabel those requests as successful. Keyboard Tab/selector navigation is tested
separately by the Qt probe. This residual limitation must be presented to future
R2; full UIA interaction/speech certification is not claimed.
The physical flag is an explicit maintainer attestation;
the script verifies Windows 10 but cannot infer physical hardware from an OS name.
Hosted Windows results always remain labelled non-physical.

At the maintainer's normal scale, observe one launch, visible focus using
Tab/Shift+Tab, navigation with arrows/Space, the career selector, and normal close.
Return the JSON plus the scale and visible-focus observation. Screenshots are
needed only if a changed behavior or defect appears. The historical four-scale
P0 walkthrough remains reusable because full window/fixture/contract hashes are
unchanged. Speech, Windows 11 and clean-machine certification are not requested.

## Decision sequence and exclusions

Implementation → future integration into main → mandatory new revision-bound R2
Full Application Review → explicit maintainer ADR decision. No repeated R2 is
performed in this initial implementation pass.

Physical Windows 11, clean-machine/installer/updater/install-update-rollback,
signing, public provenance/distribution/release SBOM, Narrator/NVDA speech,
live SQLite/WoFF/parser/watchdog/query-service/network integration and P1 are
outside this issue. This work is engineering evidence, not legal certification.
