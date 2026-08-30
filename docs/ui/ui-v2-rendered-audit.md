# UI V2 published-site audit

Status: Failed — corrections required

Date: 2026-08-29

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

- Browser viewport: 1363 by 936 CSS pixels at device-pixel ratio 1.
- Fixture profile displayed by the Site: `Desktop 100%`.
- Captures: full-page PNG for the seven persistent-navigation destinations,
  plus the Career Selector, Mission Report, Aircrew Profile, Report Viewer, and
  Desktop Fixture Matrix.
- Data: the Site's synthetic/sanitized fixture only.
- Source states exercised: `Complete` for the recorded contrast table, a
  same-name career change, primary navigation, and contextual entry/return
  routes.

The Site exposed these fixture-matrix screen IDs: `OPR-01`, `DOS-01`, `MIS-01`,
`MIS-02`, `SQD-01`, `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02`, and `SYS-01`. It
also exposed fourteen semantic states and four desktop scale profiles.

## Contrast method

For every visible text run, the audit recorded the computed foreground,
cumulative opacity, font size and weight, bounding rectangle, and nearest
rendered surface. A lossless full-page capture supplied the actual textured
backdrop. The reported rendered ratio uses the WCAG relative-luminance formula
against the median of the adjacent four-pixel background ring. This avoids
counting anti-aliased glyph pixels as background while retaining the paper,
wood, felt, gradient, and opacity composition visible beside the glyphs.

The table records one representative failure per destination. All examples are
normal text and therefore require at least 4.5:1. Because even the local median
is below 4.5:1, the failure does not depend on claiming a global pixel minimum.

| Screen | Representative text | Computed base pair | Rendered local ratio | Required | Result |
|---|---|---:|---:|---:|---|
| `OPR-01` Operations Board | `RFC · FORM 14A · FIELD COPY` | 2.02:1 | 2.17:1 | 4.5:1 | Fail |
| `DOS-01` Pilot Dossier | `· READ ONLY` | 2.02:1 | 2.07:1 | 4.5:1 | Fail |
| `MIS-01` Mission Log | `14 SQN · RFC` | 2.68:1 | 2.96:1 | 4.5:1 | Fail |
| `JRN-01` War Diary | `Location` | 1.06:1 | 1.14:1 | 4.5:1 | Fail |
| `RPT-01` Reports Library | `Period` | 1.06:1 | 1.15:1 | 4.5:1 | Fail |
| `SQD-01` Squadron Roster | `Bailleul Aerodrome · 15 AUG 1917` | 3.05:1 | 3.20:1 | 4.5:1 | Fail |
| `SYS-01` System Status | unknown-value em dash | 2.67:1 | 2.73:1 | 4.5:1 | Fail |

Two repeated causes are visible in the computed styles:

- dark-surface muted text (`rgb(173, 179, 161)`) is reused on textured paper,
  producing approximately 1.06:1 before the texture is sampled; and
- stamps and small paper metadata use muted color and opacity combinations
  that remain below the normal-text threshold.

The published Site also renders essential metadata at 7–10 CSS pixels even
though `type.caption` is 12 logical pixels in the approved visual system. That
is a separate conformance problem from the contrast ratio.

## Interaction and contract checks

| Check | Observed evidence | Result |
|---|---|---|
| Stable same-name career selection | Selecting career `RAF-41B-22C1` from `MIS-02` updated the context to `41 Squadron RAF` but retained the previous `MIS-1917-08-15-027` report, including `14 Squadron RFC` content. | Fail |
| Programmatic destination focus | Primary navigation to Pilot Dossier left focus on `<main class="workspace" tabindex="-1">`; the `h1` had no `tabindex` and was not active. | Fail |
| Published navigation contract | The visible order is `Dashboard`, `Pilot`, `Missions`, `Diary`, `Reports`, `Squadron`; the normative order is `Operations`, `Pilot Dossier`, `Missions`, `Squadron`, `War Diary`, `Reports`. | Fail |
| Core contextual routes | `MIS-02`, `SQD-02`, `RPT-02`, the Career Selector, fixture states, filters, and return routes were reachable without a dead end. | Pass |
| Required visual coverage | The fixture matrix does not expose standalone `APP-00`, `SEL-01`, `DOS-02`, `DOS-03`, or `DOS-04` records. | Partial |

The same-name result is a presentation-boundary failure: changing the active
career must clear or replace previous-career content before presenting the new
context. A fixture label is not sufficient protection when contradictory
career data remains visible.

## Required corrections

1. Scope text colors to their rendered surface. Paper metadata must use the
   approved ink tokens at full effective contrast; muted dark-surface tokens
   cannot inherit into paper cards. Recheck every state and scale after texture
   and opacity composition.
2. Raise essential typography to the approved token floor; do not use 7–10
   pixel text for status, provenance, table headings, or other meaningful data.
3. On `career_id` change, clear the current detail snapshot immediately, enter
   the loading/no-career-safe geometry, and route only to content belonging to
   the newly selected identity.
4. Move one-time programmatic focus to the destination `h1` with
   `tabindex="-1"` or the toolkit-equivalent API. Keep the heading out of the
   sequential `Tab` order and restore overlay focus to its opener.
5. Align the published navigation label/order with the normative screen map and
   either add the missing contextual coverage or identify the Site explicitly
   as a partial visual source.

## Outcome and rerun rule

`EVAL-UI-DESIGN-001` remains `planned` and Issue #79 remains `in_progress`.
The repository contract is reviewable, but the published rendered source does
not yet satisfy its contrast, identity-isolation, focus, navigation, or coverage
requirements.

The audit may pass only after a new published revision records:

- at least 4.5:1 for every normal-text role and 3:1 for large text and
  essential non-text boundaries on the rendered pixels;
- all required screen/state/scale coverage or an approved reduction of scope;
- no previous-career content after a `career_id` change; and
- the specified focus and navigation behavior.

Flat token calculations and an archived Figma export remain supporting design
data only; neither substitutes for a passing audit of the published Site.
