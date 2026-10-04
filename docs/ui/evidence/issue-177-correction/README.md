# Post-fix Adoption Readiness evidence — #177 / Draft PR #178

These 38 raw JSON reports are a separate post-fix execution archive. Original
failures/reports in `../issue-177-adoption/` remain byte-identical and historical.

- Pre-fix reviewed revision: `251a960259ee9b9ab13e1ee1cf86c76935cf465c`.
- Implementation revision: `1b8fe1361b291bf6e6e3e3cfebe708a2adf0a527`.
- Actual GitHub PR merge checkout: `94085c99942279e807929dee33e6722cb3c95d3d`.
- [Adoption run #7](https://github.com/Malboro66/woff-mate/actions/runs/37215243168): all seven jobs passed.
- `index.json`: report SHA-256 values, revisions and remaining limitations.
- `artifact-origins.json`: original GitHub artifact IDs/names and ZIP digests;
  downloaded ZIP hashes were checked before extracting unchanged report bytes.
- All reports retain complete candidate input hashes; the regression checks
  current source/asset inputs, permitting only text LF/CRLF checkout differences.
  No deleted branch or historical Git object must be recovered to validate them.

## Coverage and results

| Reports | Coverage |
| --- | --- |
| 28 source reports | Linux Python 3.10–3.14 and Windows 3.10/3.14, each at 100/125/150/200% |
| 4 bundled reports | Linux/Windows endpoint startup, keyboard, Qt accessibility and layout |
| 4 inventories | Actual corrected endpoint bundles, libraries/plugins/origins/hashes/licensing |
| 2 native UIA reports | Packaged Windows selectors/buttons, names/types/focusability and keyboard focus/value |

The Windows compact brand now has 135px available for its 135px advance. The
localized rail grows from its 184px baseline to 201px where native metrics require
it. Four scales and compact/breakpoint/normal/return transitions pass; actual
compact viewport is 680×520. Linux keeps the baseline where sufficient.

Both native Windows selectors pass Tab focus, observable HasKeyboardFocus,
Shift+Tab and Down/Up value changes. `programmatic_combo_focus_warnings` still
records both ignored UIA SetFocus requests. The native Qt 6.11.2 limitation is
not relabeled as fixed: the runtime selectors are unchanged. See
[the investigation](../../ui-adoption-correction.md) for the plain-control
experiment, upstream source explanation and disposition.

The Windows OS in these reports is **Windows Server 2025 Datacenter**, hosted
CI. `physical_windows10` is false and visible-focus observation remains pending.
These reports do not certify physical Windows 10, speech or release readiness.
Use the matching corrected bundle/inventory and the physical delta procedure in
[readiness](../../ui-adoption-readiness.md). Targeted compact/200% and normal-scale
checks remain required; no full page/state DPI walkthrough is requested.

ADR remains Proposed. Historical first R2 remains HOLD / Conditional No-Go.
P1 and Product Gates A–D remain unauthorized/unapproved. No final repeated R2.
