# UI V2 design walkthrough

Status: Passed

Date: 2026-08-31

Eval: `EVAL-UI-DESIGN-001`

Tracks: Issue #79

## Review boundary

This walkthrough validates the approved UI V2 design handoff in
[UI V2 reference](ui-v2-reference.md) and
[UI V2 visual system](ui-v2-visual-system.md). It verifies navigation,
terminology, states, focus, scaling, privacy, stable career identity, and
persistent simulator-slot presentation.

The published
[WoFF Mate UI V2 Site](https://woff-mate-ui-v2.pilotohans.chatgpt.site/) is the
current rendered source; Figma is archival only. The Site is a sanitized,
read-only prototype, not production UI or approval of a web runtime for the
future Windows application.

## Controlled scenario

The rendered review uses two synthetic careers with the same display name and
different stable identities:

| Safe label | Value |
|---|---|
| Display label | `Lt. Arthur Bennett` |
| Career A | `rfc-14a-08f2` / `RFC-14A-08F2` / `WoFF Pilot 1` / RFC |
| Career B | `raf-41b-22c1` / `RAF-41B-22C1` / `WoFF Pilot 2` / RAF |
| Additional option | `career-14b8` / `CAREER-14B8` / `WoFF Pilot 3` |
| Selection value | immutable `career_id` |
| Slot rule | `PilotN` is a persistent source-slot label, not list position or historical identity |
| Operational indicators | synthetic or fixture-backed; never live |

Deleting `Pilot1` would leave `Pilot2` and `Pilot3` unchanged. A later new
`Pilot1` would require a new `career_id`; the old career's records could not
be inherited through the reused slot label.

## Main-flow walkthrough

| Step | Action and expected result | Focus return / exit | Result |
|---:|---|---|---|
| 1 | Open `APP-00`. The persistent shell shows six historical destinations and keeps `SYS-01` separate in the footer. | Any primary destination, `SEL-01`, or `SYS-01`. | Pass |
| 2 | Open `SEL-01`. Same-name RFC and RAF careers remain distinct by `career_id`, stable reference, service, and persistent slot label. | Selecting a different career clears prior details and focuses the resulting `OPR-01` heading. | Pass |
| 3 | Review `OPR-01`. Only the active career's missions, squadron, station, totals, and slot label are shown. | Open a primary or contextual read-only destination. | Pass |
| 4 | Open `DOS-01`, then `DOS-02/03/04`. Status, claims, victories, decorations, identity, and source slot remain distinct concepts. | Each contextual record returns to Pilot Dossier. | Pass |
| 5 | Open `MIS-01`, then `MIS-02`. The mission list and detail are filtered by their owning `careerId`. | Mission Report returns to Mission Log. | Pass |
| 6 | Open `SQD-01`, then `SQD-02`. A roster entry never becomes the active career and a missing roster never borrows another career's unit. | Aircrew Profile returns to Squadron. | Pass |
| 7 | Open `JRN-01`. Timeline entries remain read-only and career-scoped. | A linked entry can open its owned `MIS-02`. | Pass |
| 8 | Open `RPT-01`, then `RPT-02`. Reports remain career-scoped and unavailable content is explicit. | Report Viewer returns to Reports. | Pass |
| 9 | Open `SYS-01`. Configuration, coverage, freshness, and failure labels expose no private implementation data. | Any primary destination remains available. | Pass |
| 10 | Apply every standalone screen from the fixture matrix. All 15 IDs render independently without a dead end. | Applying a fixture focuses its destination heading. | Pass |

## State walkthrough

| Condition | Required distinction | Result |
|---|---|---|
| Complete | Show all supplied regions. | Pass |
| Loading | Preserve shell and geometry; reuse no previous-career value. | Pass |
| Empty | Use a collection-specific valid-empty message. | Pass |
| Partial | Keep confirmed identity and label unavailable fields. | Pass |
| No career | Keep shell orientation without borrowing a career. | Pass |
| Missing | Name the missing record safely and invent nothing. | Pass |
| Truncated | Withhold unvalidated values. | Pass |
| Unsupported | Do not imply the format was parsed successfully. | Pass |
| Unreadable | Show no path, payload, or raw exception. | Pass |
| Error | Preserve safe context and a sanitized reason. | Pass |
| Stale | Label the older snapshot and never present it as current. | Pass |
| Authoritative zeroes | Render `0` as a value, never a placeholder. | Pass |
| Unknown values | Keep unknown distinct from zero and empty. | Pass |
| Not available | State that the source contract does not provide the field or view. | Pass |

Status rendering was also reviewed across `Active`, `KIA`, `PoW`, `MIA`,
`Invalided Out`, `Survived War`, `Lightly Wounded`, and `Seriously Wounded`;
each value retains the lossless wording defined by the reference contract.

The Pilot Dossier representative surface passed all 14 rendered states with a
lowest measured normal-text ratio between 4.55:1 and 4.92:1 and no meaningful
text below 12 CSS pixels.

## Keyboard walkthrough

The verified sequential order is:

1. Skip to content
2. Career selector
3. Operations
4. Pilot Dossier
5. Missions
6. Squadron
7. War Diary
8. Reports
9. Data & System Status
10. Contextual back control, when present
11. Page-level read-only links
12. Main content and contextual records in visual reading order

Primary navigation and fixture application move one-time programmatic focus to
`h1#screen-title`. The heading has `tabindex="-1"`, is not a sequential Tab
stop, and receives visible focus. Escape closes Career Selector or the fixture
dialog and returns focus to its opener.

Contract result: Pass. Published Site result: Pass.

## Scaling walkthrough

| Windows scale | Review assertion | Result |
|---:|---|---|
| 100% | Labelled desktop navigation and full hierarchy. | Pass |
| 125% | Labels remain visible and target sizes remain usable. | Pass |
| 150% | Secondary content follows primary content without focus-order change. | Pass |
| 200% | Compact labelled navigation and content fit without core horizontal overflow. | Pass |

At each profile, document `clientWidth` equalled `scrollWidth` (1363
pixels), main `clientWidth` equalled `scrollWidth` (1091 pixels), contrast
remained at least 4.61:1 on the representative Operations view, and no
meaningful text fell below 12 CSS pixels.

## Material and contrast walkthrough

| Surface | Review assertion | Result |
|---|---|---|
| Beige paper cards | Restrained paper texture, ink-scoped text, no stains or grunge behind content. | Pass |
| Felt/canvas | Texture is limited to broad surfaces and carries no state meaning. | Pass |
| Wood | Grain remains a narrow structural treatment. | Pass |
| Brass | Never the sole focus, selection, status, or contrast cue. | Pass |
| Text and controls | Every required screen meets the 4.5:1 normal-text or 3:1 large-text threshold. | Pass |
| Meaningful metadata | No audited text is below the 12-pixel caption floor. | Pass |

The recorded minima span 4.55:1 to 5.54:1 across the 15 required screen IDs.
Exact per-screen, per-state, and per-scale values are in the
[published-site audit](ui-v2-rendered-audit.md) and its immutable evidence.

## Published Site interaction evidence

- The visible order is `Operations`, `Pilot Dossier`, `Missions`,
  `Squadron`, `War Diary`, and `Reports`, with `Data & System Status`
  separated in the footer.
- The fixture matrix exposes `APP-00`, `SEL-01`, `OPR-01`, `DOS-01`,
  `DOS-02`, `DOS-03`, `DOS-04`, `MIS-01`, `MIS-02`, `SQD-01`,
  `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02`, and `SYS-01`.
- Selecting `RAF-41B-22C1` after opening RFC mission
  `MIS-1917-08-15-027`, aircrew `RFC-14-A-002`, or report
  `RPT-RFC14A-19170815-CAREER` removes every selected RFC detail before
  presenting the RAF career's `WoFF Pilot 2`, 41 Squadron, and Bertangles.
- The `sparse-slots-2-3` fixture renders no `Pilot1`; its first two list items
  remain `WoFF Pilot 2` and `WoFF Pilot 3` instead of being renumbered.
- Sequential Tab order, visible focus, Enter, Space, ArrowDown, Escape, modal
  wrapping, and trigger focus restoration pass the recorded keyboard sequence.
- Primary navigation and the completed career transition focus
  `h1#screen-title`.

## Privacy and scope review

- All examples are visibly synthetic or explicitly unavailable.
- No example contains a real campaign name, personal path, database content,
  log, screenshot, raw WoFF payload, activation credential, or license value.
- No screen reads SQL, files, watchdog state, or repository internals.
- No screen offers campaign/configuration writes or launcher/session control.
- No production GUI dependency is introduced into this repository.
- No Product Gate, toolkit ADR, or aggregate cycle is approved by this review.

Result: Passed.

## Traceability

| Acceptance area | Repository evidence |
|---|---|
| Screen IDs, entries, exits, future gates, and persistent slots | `ui-v2-reference.md` |
| Tokens, materials, components, and shared states | `ui-v2-visual-system.md` |
| Keyboard, focus, and Windows scaling | This walkthrough and the published-site audit |
| Same-name career isolation | Published-site interaction evidence and `conformance-measurements.json` |
| Sanitized captures and measurements | `evidence/ui-v2-site-2026-08-31-audit-3/` |
| Governance and automated structure checks | `project-graph.yaml` and `test_architecture_contracts.py` |

## Review result and follow-up ownership

`EVAL-UI-DESIGN-001` passes and is `implemented`. Issue #79 is `done`.
This approves the repository UI V2 reference and its current rendered
conformance evidence only.

The following remain intentionally unresolved:

- Issue #80: formal deterministic state fixtures;
- Issue #81: immutable application view-model and query-service protocols;
- Issue #82: isolated toolkit feasibility and packaging evidence;
- the proposed toolkit ADR and applicable Product Gates; and
- cycle 3.4.0 aggregate completion.
