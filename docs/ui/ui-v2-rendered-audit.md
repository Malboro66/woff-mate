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
  [`UIV2-SITE-2026-08-31-AUDIT-2`](evidence/ui-v2-site-2026-08-31/README.md).
- Published deployment: `appgdep_6a9555f927b081919b6cc2f33e9f3ffb`.
- Saved Site version: `16`.
- Published source commit: `07cc3397ac9a9204c6540becaf57ffcaad3c8897`.
- Evidence-set SHA-256:
  `a64fd0e67383d3cf828ec33edc225fde18df1a710833b648a838222938ee5ce9`.
- Browser viewport width: 1363 CSS pixels at device-pixel ratio 1.
- Captures: versioned viewport JPEG evidence for the seven persistent
  destinations, Career Selector, Mission Report, Aircrew Profile, Report
  Viewer, and Desktop Fixture Matrix.
- Data: the Site's synthetic/sanitized fixture only.

The published fixture matrix exposed all 15 required screen IDs:
`APP-00`, `SEL-01`, `OPR-01`, `DOS-01`, `DOS-02`, `DOS-03`, `DOS-04`,
`MIS-01`, `MIS-02`, `SQD-01`, `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02`, and
`SYS-01`. It also exposed and passed all 14 semantic states and the Desktop
100%, 125%, 150%, and 200% profiles.

The failed 2026-08-29 evidence remains immutable historical evidence. This
audit is a new revision and does not overwrite the earlier capture set.

## Contrast and typography method

For every visible text-bearing element, the audit recorded computed foreground,
font size and weight, visibility, and the nearest opaque rendered surface. It
used the WCAG relative-luminance formula for the resulting foreground/background
pair. Normal text required at least 4.5:1; large text required at least 3:1.
Viewport captures were inspected alongside the measurements to confirm surface
selection, texture treatment, focus visibility, and absence of inherited dark-
surface colors on paper cards.

The minimum meaningful type size was checked separately at 12 CSS pixels. A
passing ratio does not excuse text below that approved caption floor.

| Screen | Lowest measured ratio | Required | Type below 12 px | Result |
|---|---:|---:|---:|---|
| `APP-00` Application Shell | 4.92:1 | 4.5:1 | 0 | Pass |
| `SEL-01` Career Selector | 4.92:1 | 4.5:1 | 0 | Pass |
| `OPR-01` Operations | 4.61:1 | 4.5:1 | 0 | Pass |
| `DOS-01` Pilot Dossier | 4.55:1 | 4.5:1 | 0 | Pass |
| `DOS-02` Career Record | 4.92:1 | 4.5:1 | 0 | Pass |
| `DOS-03` Victories & Claims | 4.92:1 | 4.5:1 | 0 | Pass |
| `DOS-04` Decorations | 4.92:1 | 4.5:1 | 0 | Pass |
| `MIS-01` Mission Log | 4.68:1 | 4.5:1 | 0 | Pass |
| `MIS-02` Mission Report | 4.86:1 | 4.5:1 | 0 | Pass |
| `SQD-01` Squadron Roster | 4.68:1 | 4.5:1 | 0 | Pass |
| `SQD-02` Aircrew Profile | 4.55:1 | 4.5:1 | 0 | Pass |
| `JRN-01` War Diary | 4.68:1 | 4.5:1 | 0 | Pass |
| `RPT-01` Reports Library | 4.68:1 | 4.5:1 | 0 | Pass |
| `RPT-02` Report Viewer | 4.92:1 | 4.5:1 | 0 | Pass |
| `SYS-01` System Status | 4.68:1 | 4.5:1 | 0 | Pass |

The Pilot Dossier representative surface was then re-rendered in Complete,
Loading, Empty, Partial, No career, Missing, Truncated, Unsupported,
Unreadable, Error, Stale, Authoritative zeroes, Unknown values, and Not
available states. Their lowest measured ratios were between 4.55:1 and 4.92:1,
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
| Stable same-name career selection | Changing from RFC career `RFC-14A-08F2` to same-name RAF career `RAF-41B-22C1` removed the prior mission and `14 Squadron RFC` content before presenting `WoFF Pilot 2`, 41 Squadron RAF, and Bertangles. | Pass |
| Persistent slot presentation | `WoFF Pilot 1`, `WoFF Pilot 2`, and `WoFF Pilot 3` remain source-slot labels; the selected value and historical identity remain `career_id`. Slot labels are never derived from list order or renumbered after an earlier slot becomes vacant. | Pass |
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
- destination heading focus and navigation order; and
- WCAG AA contrast and the 12-pixel meaningful-text floor.
