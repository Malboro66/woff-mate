# UI V2 design walkthrough

Status: Passed repository design review

Date: 2026-08-29

Eval: `EVAL-UI-DESIGN-001`

Tracks: Issue #79

## Review boundary

This walkthrough validates the approved UI V2 design handoff in
[UI V2 reference](ui-v2-reference.md) and
[UI V2 visual system](ui-v2-visual-system.md). It verifies navigation,
terminology, states, focus order, scaling, and privacy at the design level.

It does not claim that a Figma frame, Site prototype, Qt widget, query service,
or live integration is production code. It uses synthetic scenario labels only;
Issue #80 owns the formal deterministic fixture matrix.

## Controlled scenario

The review uses two synthetic career labels with the same display name and
different stable identities:

| Safe label | Value |
|---|---|
| Display label | `Lt. Avery North` |
| Career A | `career-demo-001` — service `RFC`, status `Unknown` |
| Career B | `career-demo-002` — service `RAF`, status `Active` |
| Selected career | `career-demo-001` |
| Authoritative missions | `0` |
| Confirmed victories | `Unknown` |
| Decorations | `None recorded` |
| Operational indicators | `Unavailable — design reference only` |

The labels are invented and are not a repository fixture, WoFF record, local
path, database row, log excerpt, or real person's asserted identity.

## Main-flow walkthrough

| Step | Action and expected result | Focus return / exit | Result |
|---:|---|---|---|
| 1 | Open `APP-00` with no career. The shell keeps its six historical destinations visible, presents no previous-career values, and keeps the separated `SYS-01` system entry available. | `Select career` opens `SEL-01`; `View data status` opens `SYS-01` without a career. | Pass |
| 2 | Open `SEL-01`. The two `Lt. Avery North` entries remain distinct through their safe reference and metadata; selection value is `career_id`. | Choose `career-demo-001`; focus returns to the `OPR-01` heading. | Pass |
| 3 | Review `OPR-01`. The active career is visible, `0` missions is a value, warnings are textual, and operational indicators say `Unavailable`. | Open Pilot Dossier or another primary destination. | Pass |
| 4 | Open `DOS-01`. RFC is not changed to RAF, absent status is `Unknown`, `0` is not a placeholder, and unavailable victories are not treated as an empty collection. | Open `DOS-02`, `DOS-03`, or `DOS-04`; each returns to Dossier. | Pass |
| 5 | Open `MIS-01`. The valid empty state says no missions are recorded rather than saying the source is missing or failed. | Normal navigation remains available; a populated state would open `MIS-02`. | Pass |
| 6 | Review the `MIS-02` reference state. Mission identity is stable, claims remain separate from confirmed victories, and a related narrative can open `JRN-01`. | Return to Mission Log or open the related War Diary entry. | Pass |
| 7 | Open `JRN-01`. Entries are read-only and expose no create, edit, delete, save, or regenerate command. | A mission-linked entry can return to `MIS-02`; primary navigation remains available. | Pass |
| 8 | Open `SQD-01`, then `SQD-02`. The roster does not convert a member into the active career and does not infer transfer status. | Aircrew Profile returns to Squadron. | Pass |
| 9 | Open `RPT-01`, then `RPT-02`. Unavailable report content is explicit and sanitized. | Report Viewer returns to Reports. | Pass |
| 10 | Open `SYS-01` from the separated footer entry. Configuration and source coverage contain no personal path, SQL, raw payload, or live-status claim. | Return to the originating screen or any primary destination. | Pass |

The flow reaches every required destination and provides an explicit return or
next route. There is no dead end.

## State walkthrough

| Condition | Required distinction | Result |
|---|---|---|
| Authoritative zero | `0` uses the normal value style and remains distinct from unknown. | Pass |
| Unknown scalar | Em dash and `Unknown` accessible text; no inferred fallback. | Pass |
| Unavailable scalar | `Not available` plus an optional safe reason. | Pass |
| Valid empty collection | `None recorded` with collection-specific wording. | Pass |
| Partial record | Confirmed identity and known fields remain; a persistent notice explains gaps. | Pass |
| Missing record | No fabricated content; the missing record or source is named safely. | Pass |
| Truncated input | Unvalidated values are withheld and System Status is available. | Pass |
| Unsupported format | The design does not imply the format was parsed successfully. | Pass |
| Unreadable source | The message contains no local path, raw exception, or payload. | Pass |
| Query error | Active-career context remains; `Retry view` and `View data status` are available. | Pass |
| Loading after career change | Geometry remains stable and no prior-career values appear. | Pass |

### Authoritative status walkthrough

The status badge was checked against every value produced by the normalized
pilot-status contract. Each value remains distinguishable in visible and
accessible text:

| Normalized value | Expected badge label | Result |
|---|---|---|
| `Active` | Active | Pass |
| `KIA` | Killed in Action (KIA) | Pass |
| `PoW` | Prisoner of War (PoW) | Pass |
| `MIA` | Missing in Action (MIA) | Pass |
| `Invalided Out` | Invalided Out | Pass |
| `Survived War` | Survived War | Pass |
| `Lightly Wounded` | Lightly Wounded | Pass |
| `Seriously Wounded` | Seriously Wounded | Pass |
| Missing or unavailable | Unknown | Pass |

No prisoner, missing, invalided-out, survived-war, or wound-severity value is
collapsed into a generic `Wounded` or `Unknown` badge.

## Keyboard walkthrough

The reference order was reviewed as:

1. Skip to content
2. Career selector
3. Operations
4. Pilot Dossier
5. Missions
6. Squadron
7. War Diary
8. Reports
9. Data & System Status
10. Page heading or contextual back route
11. Page-level read-only links
12. Main content and contextual records in visual reading order

The visible focus token works on graphite, aviation green, felt/canvas, beige
paper, and overlays. Opening and closing `SEL-01` or another overlay restores
focus to its opener. Selecting a career sends focus to the resulting page
heading. Dynamic status does not steal focus.

Result: Pass.

## Scaling walkthrough

| Windows scale | Review assertion | Result |
|---:|---|---|
| 100% | Labelled 256-pixel navigation, full desktop hierarchy, six-stat row. | Pass |
| 125% | Labels remain visible; compact gaps preserve hierarchy and target size. | Pass |
| 150% | Side content follows main content; statistics use three or two columns; focus order is unchanged. | Pass |
| 200% | One content column and compact labelled navigation fit without a core horizontal scrollbar. | Pass |

The result is a reflowed desktop interface, not a mobile redesign. Text is not
shrunk below its token size, and no essential control becomes icon-only without
an accessible, visible way to obtain its label.

## Material and contrast walkthrough

| Surface | Review assertion | Result |
|---|---|---|
| Beige paper cards | Restrained paper texture is present; luminance variation stays low and no stains, folds, stacked sheets, or grunge intersect content. | Pass |
| Felt/canvas | Texture is limited to broad, low-density surfaces and carries no state meaning. | Pass |
| Wood | Grain is restricted to a narrow structural accent rather than every card. | Pass |
| Brass | Used sparingly and never as the sole focus, selection, status, or text contrast. | Pass |
| Text and controls | Flat token pairs pass at 5.30:1 or higher; each textured Figma composition remains subject to a rendered WCAG AA check. | Pass |

## Privacy and scope review

- All examples are visibly synthetic or explicitly unavailable.
- No example contains a real campaign name, player name, path, database copy,
  log, screenshot, raw WoFF payload, activation credential, or license value.
- No screen reads SQL, files, watchdog state, or repository internals.
- No screen offers campaign/configuration writes or launcher/session control.
- No PySide, PyQt, React, web runtime, or other GUI dependency is introduced.
- No Product Gate, toolkit ADR, or aggregate cycle is approved by this review.

Result: Pass.

## Traceability

| Acceptance area | Repository evidence |
|---|---|
| Screen IDs, entries, exits, and future gates | `ui-v2-reference.md` — Navigation architecture and Screen inventory |
| Stable career identity and Dossier semantics | `ui-v2-reference.md` — Career selection contract and Pilot Dossier reference |
| Tokens, materials, components, and shared states | `ui-v2-visual-system.md` |
| Keyboard and Windows scaling | `ui-v2-visual-system.md` — Keyboard model and Windows scaling behavior |
| Synthetic/unavailable operational labels | Both specifications and the controlled scenario above |
| No-dead-end flow | Main-flow walkthrough above |
| Governance and automated structure checks | `project-graph.yaml` and `test_architecture_contracts.py` |

## Review result and follow-up ownership

`EVAL-UI-DESIGN-001` passes for the repository design reference. Issue #79 can
close when the pull request containing this record is merged.

The following remain intentionally unresolved here:

- Issue #80: formal state matrix and deterministic sanitized fixtures;
- Issue #81: immutable view models and application query-service protocols;
- Issue #82: isolated toolkit feasibility, packaging, scaling, accessibility,
  plugin, resource, and licensing evidence; and
- formal acceptance of the proposed toolkit ADR and applicable Product Gates.
