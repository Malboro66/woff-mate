# Issue #177 bounded correction — 2026-10-04

The maintainer expanded the scope of Draft PR #178 only for the demonstrated
compact brand-width defect and investigation/minimal correction of two selectors.
No new issue, branch, feature, presentation contract, toolkit or live integration.
ADR remains Proposed; P1 and Product Gates A–D remain unauthorized/unapproved.
Physical Windows 10 remains pending. No repeated R2 is performed here.

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

Focused local correction tests passed (34 tests). Broader suite, current Windows
endpoint packages, four-scale source evidence and native UIA keyboard results are
being collected on the implementation revision; no Windows pass is inferred from
Linux or upstream source inspection. A separate post-fix archive will retain
actual execution revisions and input hashes without replacing the original reports.

## Physical Windows 10 delta (still required)

Use the corrected bundle and matching inventory with the command in
[readiness procedure](ui-adoption-readiness.md). Observe launch/close, visible
Tab/Shift+Tab focus, both selectors and a compact 680×520 / 200% brand-fit check,
plus normal-scale use. Record actual viewport/scale if the desktop cannot fit the
requested logical size. Full page/state scaling repetition, physical Windows 11,
clean-machine/release certification and speech certification remain out of scope.
