# UI V2 published-site audit

Status: Passed

Date: 2026-08-31

Eval: `EVAL-UI-DESIGN-001`

Tracks: Issue #79

## Source and authority

The current rendered source for UI V2 is the published
[WoFF Mate UI V2 Site](https://woff-mate-ui-v2.pilotohans.chatgpt.site/).
It replaces Figma as the active visual reference. The original Figma file is
retained only as an archive and design-origin record.

This audit checks the published Site as a prototype. It does not treat the Site
as production code, approve a web runtime for the Windows application, or
replace the toolkit-independent contracts in
[UI V2 reference](ui-v2-reference.md) and
[UI V2 visual system](ui-v2-visual-system.md).

## Capture record

- Evidence revision:
  [`UIV2-SITE-2026-08-31-AUDIT-3`](evidence/ui-v2-site-2026-08-31-audit-3/README.md).
- Published deployment: `appgdep_6a95ebac3afc8191a3913a988ad16ac3`.
- Saved Site version: `17`.
- Published source commit: `d96fb6da3e5240919d9dc95fca68f9060c3e9434`.
- Evidence-set SHA-256:
  `5ff88aa30e908c3af4049ecd5adf0bae37bf8cbfa34c27516c0ccbace273bfac`.
- Browser viewport width: 1363 CSS pixels at device-pixel ratio 1.
- Evidence: structured browser measurements for the sparse Career Selector and
  the stable RAF result after same-name mission, aircrew, and report switches.
  Audit 2 retains the prior twelve-view visual baseline.
- Data: the Site's synthetic/sanitized fixture only.

The published fixture matrix exposed all 15 required screen IDs:
`APP-00`, `SEL-01`, `OPR-01`, `DOS-01`, `DOS-02`, `DOS-03`, `DOS-04`,
`MIS-01`, `MIS-02`, `SQD-01`, `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02`, and
`SYS-01`. It also exposed and passed all 14 semantic states and the Desktop
100%, 125%, 150%, and 200% profiles.

The failed 2026-08-29 evidence and passing Audit 2 evidence remain immutable
historical evidence. This audit is a new revision and does not overwrite either
earlier capture set.

## Contrast and typography method

For every visible text-bearing element, the audit recorded computed foreground,
font size and weight, visibility, and the nearest opaque rendered surface. It
used the WCAG relative-luminance formula for the resulting foreground/background
pair. Normal text required at least 4.5:1; large text required at least 3:1.
Visible focus indicators and required control boundaries were measured against
their adjacent rendered colors and required at least 3:1 non-text contrast.
Viewport captures were inspected alongside the measurements to confirm surface
selection, texture treatment, focus visibility, and absence of inherited dark-
surface colors on paper cards.

The minimum meaningful type size was checked separately at 12 CSS pixels. A
passing ratio does not excuse text below that approved caption floor.

| Screen | Lowest measured ratio | Required | Type below 12 px | Result |
|---|---:|---:|---:|---|
| `APP-00` Application Shell | 5.39:1 | 4.5:1 | 0 | Pass |
| `SEL-01` Career Selector | 5.54:1 | 4.5:1 | 0 | Pass |
| `OPR-01` Operations | 4.61:1 | 4.5:1 | 0 | Pass |
| `DOS-01` Pilot Dossier | 4.55:1 | 4.5:1 | 0 | Pass |
| `DOS-02` Career Record | 5.39:1 | 4.5:1 | 0 | Pass |
| `DOS-03` Victories & Claims | 5.39:1 | 4.5:1 | 0 | Pass |
| `DOS-04` Decorations | 5.39:1 | 4.5:1 | 0 | Pass |
| `MIS-01` Mission Log | 4.68:1 | 4.5:1 | 0 | Pass |
| `MIS-02` Mission Report | 4.59:1 | 4.5:1 | 0 | Pass |
| `SQD-01` Squadron Roster | 4.68:1 | 4.5:1 | 0 | Pass |
| `SQD-02` Aircrew Profile | 4.55:1 | 4.5:1 | 0 | Pass |
| `JRN-01` War Diary | 4.68:1 | 4.5:1 | 0 | Pass |
| `RPT-01` Reports Library | 4.68:1 | 4.5:1 | 0 | Pass |
| `RPT-02` Report Viewer | 5.39:1 | 4.5:1 | 0 | Pass |
| `SYS-01` System Status | 4.68:1 | 4.5:1 | 0 | Pass |

The Pilot Dossier representative surface was then re-rendered in Complete,
Loading, Empty, Partial, No career, Missing, Truncated, Unsupported,
Unreadable, Error, Stale, Authoritative zeroes, Unknown values, and Not
available states. Their lowest measured ratios were between 4.55:1 and 5.54:1,
with no type-size failure.

## Scale checks

| Profile | Document width | Main width | Horizontal overflow | Result |
|---|---:|---:|---|---|
| Desktop 100% | 1363 / 1363 | 1091 / 1091 | No | Pass |
| Desktop 125% | 1363 / 1363 | 1091 / 1091 | No | Pass |
| Desktop 150% | 1363 / 1363 | 1091 / 1091 | No | Pass |
| Desktop 200% | 1363 / 1363 | 1091 / 1091 | No | Pass |

Each width cell is `clientWidth / scrollWidth`. Text retained the 12-pixel
floor, navigation labels remained visible, and the resulting destination
heading remained the programmatic focus target.

## Interaction and contract checks

| Check | Observed evidence | Result |
|---|---|---|
| Stable same-name career selection | Changing from RFC career `RFC-14A-08F2` to same-name RAF career `RAF-41B-22C1` removed the selected mission `MIS-1917-08-15-027`, aircrew `RFC-14-A-002`, and report `RPT-RFC14A-19170815-CAREER` before presenting `WoFF Pilot 2`, 41 Squadron RAF, and Bertangles. | Pass |
| Persistent slot presentation | The `sparse-slots-2-3` fixture contains no `Pilot1`; list index 0 retains `WoFF Pilot 2` / `RAF-41B-22C1`, and index 1 retains `WoFF Pilot 3` / `CAREER-14B8`. Labels are never derived from list order. | Pass |
| Non-text contrast | Required control boundaries measure at least 3.34:1. The two-ring visible-focus treatment measures 5.62:1 and is at least 3 CSS pixels thick. | Pass |
| Sequential keyboard operation | Tab proceeds through Skip link, Career Selector, primary navigation, system status, and Fixture Matrix with visible focus. Enter, Space, ArrowDown, Escape, modal wrap, and trigger focus restoration all behave as specified. | Pass |
| Programmatic destination focus | Every primary destination and applied fixture focused `h1#screen-title`; the heading uses `tabindex="-1"` and remains outside sequential Tab order. | Pass |
| Published navigation contract | Visible order is `Operations`, `Pilot Dossier`, `Missions`, `Squadron`, `War Diary`, `Reports`, with `Data & System Status` separated in the footer. | Pass |
| Core and contextual routes | All 15 screen IDs are independently selectable or reachable; contextual routes and return controls have no dead end. | Pass |
| Required semantic states | Fourteen states are available and use shared, sanitized, read-only presentation without borrowing another career's values. | Pass |

The career-change loading geometry clears `selectedMission`, `selectedAircrew`,
and `selectedReport` before the new career becomes active. Records also carry
their owning `careerId`, so a stale detail cannot render if it does not belong
to the selected career.

## Privacy and scope result

All evidence is synthetic/sanitized. No capture or measurement contains a
personal path, database content, log, raw WoFF payload, activation/license
information, credential, cookie, or session value. The Site remains read-only
and exposes no create, edit, delete, import, repair, regeneration, launcher, or
live-session control.

## Outcome and rerun rule

`EVAL-UI-DESIGN-001` passes and is implemented. Issue #79 may advance to
`done`. This completes the repository design/reference work only; it does not
complete Issue #80, #81, #82, cycle 3.4.0, a toolkit ADR, or any Product Gate.

A later published Site revision must create a new immutable, sanitized,
checksummed evidence set and rerun:

- all 15 required screens;
- all 14 semantic states on the representative shared-state surface;
- Desktop 100%, 125%, 150%, and 200%;
- same-name career isolation and persistent slot labels;
- mission, aircrew, and report detail clearing during a career switch;
- sequential keyboard order, modal wrapping, Escape, and focus restoration;
- destination heading focus and navigation order; and
- WCAG AA text and non-text contrast plus the 12-pixel meaningful-text floor.
