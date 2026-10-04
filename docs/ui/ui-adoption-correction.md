# Issue #177 bounded correction — 2026-10-04

The maintainer expanded the scope of Draft PR #178 only for the demonstrated
compact brand-width defect and investigation/minimal correction of two selectors.
No new issue, branch, feature, presentation contract, toolkit or live integration.
ADR remains Proposed; P1 and Product Gates A–D remain unauthorized/unapproved.
The later physical Windows 10 delta is complete; see the separate attestation below. No repeated R2 is performed here.

## Pre-fix facts (preserved)

Reviewed head `251a960259ee9b9ab13e1ee1cf86c76935cf465c` had passing general CI
#325 and failing adoption #6. Both Windows endpoints reported Georgia brand text
advance 135px in a 120px label at 680×520 and scale factor 2. The original 17
reports, index and README under `evidence/issue-177-adoption/` remain byte-identical.
They describe the pre-fix candidate, not the corrected window. Historical P0 and
first R2 evidence are also unchanged.

## Localized layout correction

`P0Window.resizeEvent` reserves the actual native font's brand advance plus the
existing symbol, 8px spacing, 32px rail margins and 2px rounding allowance. The
184px compact / 256px normal baseline is retained whenever sufficient. No font,
text, destination, navigation, content hierarchy or fixture behavior is changed.

The probe verifies text fit, icon/text separation and career minimum width across
680×520, 999×700, 1000×700, 1200×850 and return-to-compact transitions, at scale
factors 1, 1.25, 1.5 and 2. A deterministic wider-text regression exercises the
previous 120px slot even on hosts without Windows Georgia; it changes test data
only. The historical compact regression remains enforced.

## Selector investigation and engineering disposition

A plain native `QComboBox` without application style/callbacks reproduces the
ignored accessible SetFocus action on Qt 6.11.2. Both application combos and the
plain control acquire focus through QWidget and expose Qt `state().focused`.
Tab/Shift+Tab traverses the two application selectors, and Up/Down changes their
values. Career changes intentionally transfer focus to the heading under the
unchanged presentation/navigation behavior; the probe re-enters the selector
before reversing the choice.

Primary upstream source inspected at tag **v6.11.2**:

- [QAccessibleComboBox](https://github.com/qt/qtbase/blob/v6.11.2/src/widgets/accessible/complexwidgets.cpp):
  actionNames exposes ShowMenu/Press; doAction handles those popup actions and
  does not handle SetFocus. File SHA-256:
  `21995c552267ee816cd5e9be9b6f5202d79217dadd44c5698bb993ff0004838c`.
- [QWindowsUiaMainProvider](https://github.com/qt/qtbase/blob/v6.11.2/src/plugins/platforms/windows/uiautomation/qwindowsuiamainprovider.cpp):
  SetFocus forwards to the Qt accessible action and returns success, without
  verifying resulting focus. File SHA-256:
  `edb00979fe04bcc252b317895bed7a3e61564c0fd09a82085d0710026c7257c8`.

Classification: a native Qt accessibility action limitation, reproduced outside
application behavior; the previous probe conflated programmatic focus acquisition
with keyboard accessibility. No selector runtime workaround, replacement control,
focus override or new dependency is justified. The unsuccessful SetFocus requests
remain recorded separately. This does not claim complete accessibility compliance.

The extended native Windows probe uses foreground-window-guarded keyboard input,
then independently observes UIA FocusedElement, HasKeyboardFocus, name/type,
keyboard focusability and ValuePattern changes for Tab/Shift+Tab/Up/Down. It
fails if those required interactions are not observed. Speech is out of scope.

## Post-fix evidence status

Implementation revision: **`1b8fe1361b291bf6e6e3e3cfebe708a2adf0a527`**.
[Adoption workflow #7](https://github.com/Malboro66/woff-mate/actions/runs/37215243168)
passed all seven jobs. [General CI #326](https://github.com/Malboro66/woff-mate/actions/runs/37215243189) also passed. Coverage includes both Windows endpoint packages and the preserved
historical compact regression. Raw reports retain the actual PR merge checkout
`94085c99942279e807929dee33e6722cb3c95d3d` and complete input hashes.

The separate [post-fix archive](evidence/issue-177-correction/README.md) contains
38 reports: source 3.10–3.14 on Linux plus Windows endpoints at all four scales,
endpoint bundle startup/inventories on both systems, and two Windows UIA runs.
At compact size, Windows brand advance **135px now fits a 135px label**, with
rail width **201px**, across all four scales. The actual viewport remains 680×520.
No assertion was weakened to permit clipping.

Both Windows selectors passed native UIA-observed Tab/Shift+Tab focus,
HasKeyboardFocus and Up/Down value changes. Their SetFocus warnings remain in the
same reports. This closes the basic automated keyboard/UIA evidence gap while
retaining the narrower native Qt programmatic-action limitation for future R2.
The Windows host is **Server 2025**, not physical Windows 10.

Local full suite on the implementation revision: **1965 passed, 4 skipped,
175 subtests passed**. Focused correction suite: 34 passed; Pyright: zero errors;
project graph and diff checks passed. Archive integrity plus focused/governance validation passed 60 tests in
the evidence commit; later documentation/test-only commits do not relabel these
executions. The subsequent physical check below has now passed.

## Physical Windows 10 delta — subsequently passed

The maintainer supplied four successful physical Windows 10 Pro build 19045
executions and manual observations at real 100%, 125%, 150% and 200% display scale,
using the run #8 candidate associated with head `f1346f9`. The raw reports retain
actual merge checkout `c35fe885c7f8ffeabfd3d00c773042f2fa01845b`.
[Separate physical archive and attestation](evidence/issue-177-physical-windows10/README.md)
preserve all generated bytes, explain identical reports and resolve manual focus/
layout placeholders without editing the JSON. No physical regression was observed.
This closes bounded readiness evidence, not integration, repeated R2 or ADR acceptance.
