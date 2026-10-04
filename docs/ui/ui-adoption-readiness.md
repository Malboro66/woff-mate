# Bounded UI Adoption Readiness — Issue #177

Bounded evidence scope complete for candidate head
`f1346f99287df4202ad6495eae17acef520d4c34`; integration remains pending.
Implementation started from verified main
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

Pre-fix evidence remains under [issue-177-adoption](evidence/issue-177-adoption/README.md).
Current corrected evidence is under [issue-177-correction](evidence/issue-177-correction/README.md).
**Bounded Adoption Readiness is complete.** The maintainer performed the physical
Windows 10 Pro build 19045 delta at real 100%, 125%, 150% and 200% scaling.
[Raw physical reports and separate manual attestation](evidence/issue-177-physical-windows10/README.md)
record successful startup, unclipped compact layout, visible focus, navigation and
both keyboard-operated selectors. The raw merge-checkout provenance remains
separate from the tested PR head. Identical raw reports are expected because the
validator does not encode scale; manual observation resolves their unchanged
pending placeholders. No authorized readiness evidence requirement remains open.
Earlier archive status fields remain historical snapshots of their executions;
the separate physical attestation supplies the current completion result.
Integration, repeated R2 and the explicit ADR decision remain future steps.

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

`ui_adoption.spec` wraps the P0 window with a localized metric-sized brand rail,
retains unchanged fixtures and excludes live
database/parser/repository/watchdog code. It does not modify `build.spec` or
`p0_desktop.spec`. Linux offscreen is evidence only; physical Windows 10 remains
the reference desktop. The rail sizing delta requires targeted compact/normal
viewport checks; no full page/state DPI suite is required.

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

## Physical Windows 10 delta — passed

### Historical compact-layout finding and corrective pass

Hosted Windows on both Python endpoints reproduced an inherited compact-layout
failure in `test_offscreen_shell_navigation_switch_focus_and_retry`: at 680×520
and `QT_SCALE_FACTOR=2`, the Georgia brand text measured 135 logical pixels in a
120-pixel label. Waiting for layout settlement did not remove the failure.
Run [37171816406](https://github.com/Malboro66/woff-mate/actions/runs/37171816406)
binds this observation to `fba2516abc96665223221cd65bfac0391570717f`.

The historical failure remains preserved in the original archive. The correction
reserves the measured brand text width plus the existing icon, spacing and margins;
it retains the 184/256 logical-pixel rail baselines whenever they suffice. The
original regression remains enforced, alongside four-scale viewport transition
checks. The subsequent physical delta passed at all four real Windows scales;
see the separate physical archive and maintainer attestation above.

The completed run used the matching run #8 candidate/inventory. For reproduction,
run from the checkout root in PowerShell (do not set the offscreen platform):

```powershell
.\scripts\validate_ui_adoption_windows.ps1 -Bundle .\dist\WoFFMateAdoption -Inventory .\build\adoption\inventory.json -Output .\build\adoption\physical-windows10-uia.json -PhysicalWindows10
```

This verifies the exact file set/hashes, launches only the candidate window and
checks representative native UIA names, roles, enabled/focusable status and button
focus acquisition. Hosted runs found that UIA `SetFocus` did not move focus into
the combo selectors. The collector records each unsuccessful combo focus request
and its observed target in `programmatic_combo_focus_warnings`; it does not
relabel those requests as successful. The updated collector also sends Tab/Shift+Tab
and Up/Down to the foreground candidate, verifying native UIA focus state and
selection values independently of SetFocus. The Qt probe separately checks the
native control, widget focus and accessible state. This residual limitation must
be presented to future
R2; full UIA interaction/speech certification is not claimed.
The physical flag is an explicit maintainer attestation;
the script verifies Windows 10 but cannot infer physical hardware from an OS name.
Hosted Windows results always remain labelled non-physical.

The maintainer has supplied successful manual observations at all four real
Windows scaling values. No screenshots are required in the absence of regression.
Historical P0/automated reports remain historical and unmodified. The known native
Qt ComboBox SetFocus limitation remains disclosed, while physical keyboard focus
and operation passed. Speech, Windows 11 and clean-machine certification remain
outside the evidence scope.

## Decision sequence and exclusions

Implementation → future integration into main → mandatory new revision-bound R2
Full Application Review → explicit maintainer ADR decision. No repeated R2 is
performed in this initial implementation pass.

Physical Windows 11, clean-machine/installer/updater/install-update-rollback,
signing, public provenance/distribution/release SBOM, Narrator/NVDA speech,
live SQLite/WoFF/parser/watchdog/query-service/network integration and P1 are
outside this issue. This work is engineering evidence, not legal certification.
