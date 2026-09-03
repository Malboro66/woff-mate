# WoFF Mate UI/UX development standard

Status: Canonical operational guidance for UI/UX research, design, review, and agent-assisted work

Tracks: Issue #135

Normative inputs: Issues #79 and #80 and the repository artifacts they delivered

## Purpose

This document defines how humans and agents may use external UI/UX references,
agent skills, component libraries, prompt collections, asset tools, and motion
examples while working on WoFF Mate.

It is an additive governance layer. It does not replace the approved UI V2
contract, reopen completed issues, adopt a GUI toolkit, or authorize production
UI code. External references are advisory unless a separate repository decision
explicitly promotes a rule, package, asset, or dependency.

The design intent remains **Operations Room 1917**: historical atmosphere with
modern interaction, strong data hierarchy, restrained materials, honest state
communication, and accessibility before decoration.

## Authority hierarchy

When instructions or examples conflict, use this precedence:

1. Observed and deterministically tested repository behavior, where applicable.
2. Repository architecture contracts, `AGENTS.md`, project graph, evals, and
   quality gates.
3. Current issue acceptance criteria and normative WoFF Mate UI V2 repository
   documentation.
4. This UI/UX development standard and approved agent-use rules.
5. External skills, galleries, libraries, prompt collections, design-system
   references, and asset-generation tools.

A visually attractive external example never overrides repository identity,
privacy, accessibility, state, provenance, or toolkit boundaries.

### Closed-issue safety

Completed issues are historical decision and evidence records. Later UI work:

- does not reopen them merely to modernize their wording;
- does not reinterpret stale or unchecked issue-body text as unfinished scope
  when the repository and issue state record completion;
- consumes the repository artifacts delivered by completed work as current
  normative input;
- does not silently rewrite a completed contract to resolve a newly discovered
  contradiction; and
- records a genuine contradiction as a separately scoped governance follow-up.

For this standard, #79 and #80 are consumed as completed prerequisites. Their
artifacts are referenced rather than reimplemented.

## Reference-stack classification

The categories below authorize research and controlled assistance, not runtime
adoption.

| Resource | Role | Permitted use | Not authorized by this standard |
|---|---|---|---|
| `designsystems.one` | Design-system/foundation reference | Naming, token taxonomy, foundations, accessibility, system thinking | Copying a foreign design system as WoFF Mate authority |
| `designsystemchecklist.com` | Review checklist | Foundation/component/state/accessibility completeness checks | Replacing repository acceptance criteria |
| `open-props.style` | Token-system reference | Studying reusable semantic scales and token organization | Adding Open Props or CSS runtime dependencies |
| `utopia.fyi` | Scale/layout reference | Studying proportional type and spacing systems | Importing CSS fluid-scale code into the desktop runtime |
| `component.gallery` | Component research | Comparing semantics and behavior across mature systems | Treating any one implementation as mandatory |
| `coss.com` | Component/pattern research | Studying hierarchy, states, composition, and interaction patterns | Adding coss, React, Tailwind, or its implementation architecture |
| `reui.io` | Component/pattern research | Studying shells, lists, empty states, profiles, tables, and interaction patterns | Adding shadcn, React, Tailwind, or web runtime dependencies |
| `interface.rauno.me` or equivalent Rauno guidance | Interaction/craft review | Interaction detail, typography, motion, responsiveness, accessibility | Overriding V2 visual or state contracts |
| `ui-skills.com` | Agent skill/reference | Loading the smallest relevant UI skill for a specific task | Scope expansion or automatic dependency adoption |
| `vibeprompts.dev` | Prompt-quality reference | Improving bounded UI research/prototype prompts | Treating generated layouts as approved designs |
| `iconcreator.dev` / Forma | Icon exploration/production support | Exploring metaphors and candidate SVG sources when an asset issue permits it | Bypassing #129 source, license, provenance, sizing, or accessibility rules |
| `kinetics.colorion.co` | Motion research | Studying restrained feedback and transition behavior | Decorative motion without functional purpose |
| `motion-primitives.com` | Motion research | Studying state, hierarchy, feedback, and causality patterns | Adding its React/Motion/Tailwind runtime stack |
| animated-buttons references | Motion/control research | Studying restrained press, lift, fill, and feedback patterns | Using animation as the sole state cue or adding web dependencies |
| `bg.ibelick.com` | Decorative/background reference | Limited inspiration for quiet non-semantic surface treatment | Overriding #79/#131 contrast, material, or historical-restraint rules |

When an external source materially changes a design choice, record the source
and the translated WoFF Mate decision in the issue, PR, or component research
record. Routine consultation that does not affect the decision does not require
an audit trail.

## Agent execution policy

For UI-related work, agents follow this sequence:

1. Read the active issue, `AGENTS.md`, and the relevant WoFF Mate UI contracts.
2. Identify the smallest external reference category or skill that can answer a
   concrete design/review question.
3. Load or use only that reference or skill.
4. Keep its instructions subordinate to the authority hierarchy above.
5. Translate useful patterns into WoFF Mate semantics instead of copying
   framework code.
6. Record material external influence when it changes a decision.
7. Do not introduce a toolkit, runtime package, asset pipeline, build system, or
   license obligation unless the active issue explicitly authorizes it.
8. Validate the result against issue acceptance criteria, accessibility,
   privacy, provenance, and repository quality gates.

A skill may improve execution quality. It may not expand the issue scope,
redefine a state, relax a gate, or approve a dependency.

## Design-system workflow

Use this order unless an issue explicitly narrows the task:

`Foundations -> Tokens -> Components -> Patterns -> Screens`

### Foundations

Start from product intent, hierarchy, identity boundaries, accessibility,
supported desktop scaling, and historical-restraint rules.

### Tokens

Consume the approved V2 token vocabulary instead of inventing screen-local
colors, typography, spacing, borders, elevation, or state colors. Token names
are semantic design contracts, not a CSS or Qt API.

### Components

Define reusable behavior, states, accessible semantics, and stable identity
before styling one-off screen instances.

### Patterns

Combine components into repeatable navigation, selection, detail, table,
notice, empty-state, loading, and read-only inspection patterns.

### Screens

Screens consume established foundations, tokens, components, and patterns.
A screen should not create local state semantics or undocumented identity rules
for convenience.

## Q0: machine-readable design tokens

The approved V2 visual system currently publishes concrete token names and
values in `docs/ui/ui-v2-visual-system.md`, including color, typography,
spacing, shape, borders, elevation, materials, and state treatment. That is a
normative human-readable source, but it is not a dedicated machine-readable
token artifact with a versioned schema intended for automated consumption.

Therefore #135 does **not** introduce a token pipeline. A separate narrowly
scoped follow-up is recommended to evaluate a machine-readable V2 token source
only when an actual consumer is identified. That future work should:

- preserve the existing V2 semantic names and values unless a separate design
  decision changes them;
- separate primitive, semantic, and component aliases only when the consumer
  justifies the distinction;
- remain toolkit-independent at the source boundary;
- avoid generated-file families without a measured consumer; and
- define schema/versioning and validation before any runtime adapter is added.

## Component research record

Create a lightweight component research record only for a new or materially
redesigned reusable component. It may live in the issue, PR, or a focused design
note.

Record:

- **User problem:** what the component helps the user understand or do.
- **Consumers:** intended screen IDs or reusable contexts.
- **States:** shared envelope states plus component-level variants that matter.
- **Interactions:** pointer, keyboard, focus, selection, disclosure, retry, or
  read-only navigation behavior.
- **References reviewed:** external patterns, if any.
- **Chosen behavior:** the toolkit-independent behavior adopted for WoFF Mate.
- **Rejected alternatives:** only when the rejection affects future decisions.
- **Accessibility:** accessible name/role, announcements, focus order, visible
  focus, contrast, and color-independent meaning.
- **Scaling:** behavior at the supported Windows logical scaling profiles.
- **Identity/data boundary:** stable IDs and facts supplied by presentation
  contracts; no name-based identity reconstruction or hidden inference.
- **Deferred toolkit questions:** native/PySide6 behavior that belongs to #82 or
  a later authorized production issue.

Do not create this record for trivial labels, separators, or other controls
whose behavior is already fully covered by an established component contract.

## Shared state and data-honesty policy

`docs/ui/screen-state-matrix.md` is the shared state authority. The six envelope
states remain:

- `loading`
- `ready`
- `empty`
- `missing`
- `stale/unavailable`
- `error`

`partial`, `unknown`, authoritative `0`, and field-level unavailable reasons are
content semantics within that envelope, not interchangeable placeholders or
new top-level states.

Required distinctions include:

- `empty` is a successful authoritative no-record result, not a missing source;
- `missing` is an unmet prerequisite, not a query failure;
- `error` is a failed query operation;
- stale data is visibly stale and retains only a safe same-career snapshot;
- `0` remains a known value and is never substituted for unknown/missing data;
- changing `career_id` clears previous-career content before presenting the new
  identity; and
- display names, list positions, icons, portraits, or visual similarity never
  become identity keys.

The UI does not manufacture nationality, service, rank, status, decoration,
victory, mission, squadron, freshness, health, or other authoritative facts.

## Accessibility baseline

The UI V2 accessibility contract remains authoritative. New work preserves at
least:

- WCAG AA rendered contrast: 4.5:1 for normal text and 3:1 for large text and
  essential non-text boundaries where applicable;
- visible keyboard focus that is not conveyed by brass/accent color alone;
- logical and deterministic focus order;
- one-time programmatic heading focus for top-level navigation/career changes,
  without making headings ordinary `Tab` stops;
- accessible names/roles for interactive controls;
- status expressed with text and/or shape/icon semantics, never hue alone;
- no essential information available only in a tooltip or image;
- desktop behavior reviewed at Windows logical scaling profiles equivalent to
  100%, 125%, 150%, and 200%; and
- reduced-motion behavior for nonessential transition/animation effects.

An external component is not acceptable merely because its source library calls
it accessible. WoFF Mate validates the rendered behavior in its own context.

## Motion policy

Motion is permitted only when it communicates at least one of:

- state transition;
- hierarchy or spatial relationship;
- user feedback;
- causality; or
- continuity during an interaction.

Motion is not a historical-atmosphere decoration layer. Avoid gratuitous
parallax, bouncing, looping ornament, theatrical page transitions, or animation
that delays access to data.

Motion must not be the only carrier of state. A reduced-motion mode removes or
materially minimizes nonessential movement while preserving state, focus,
feedback, and navigation meaning. Timing/easing decisions should ultimately be
expressed as a small controlled token vocabulary rather than component-local
magic numbers.

## Translating web references into toolkit-independent behavior

External web examples may demonstrate useful ideas, but their framework is not
the contract. Translate them through this sequence:

`external implementation -> user behavior -> states -> semantics -> accessibility -> toolkit-independent contract`

Only a later explicitly authorized implementation issue maps that contract to a
runtime toolkit.

Examples:

- A React navigation rail may inform selection, focus, hierarchy, and compact
  behavior; it does not authorize React or its component API.
- A Tailwind card may inform spacing and content grouping; it does not authorize
  Tailwind utilities or CSS tokens.
- A motion primitive may inform causality/feedback; it does not authorize Motion
  or a web animation dependency.
- A component gallery example may reveal missing states; it does not override
  the six-state envelope or V2 component semantics.

## Runtime and dependency guard

Issue #135 and this document do not authorize adding or adopting:

- React;
- Tailwind;
- shadcn;
- coss/reui runtime packages;
- Qt;
- PySide6;
- PyQt;
- another GUI or web runtime;
- a new asset-generation runtime;
- a new design-token build pipeline; or
- a new third-party license obligation.

`docs/architecture/adr-ui-toolkit.md` and #82 remain the authority for toolkit
feasibility/adoption evidence. PySide6 + Qt Widgets is proposed, not accepted by
this standard.

## Asset and provenance policy

Asset work remains owned by #129-#133 and the V2 visual contract. Apply these
principles:

- **Need before asset:** prove the target UI consumer first.
- **Adopt before custom:** prefer one coherent redistribution-compatible family
  for generic semantic icons before drawing custom alternatives.
- **Vector where semantic/geometric:** SVG is preferred for icons and marks when
  practical.
- **Raster where pictorial:** use lossless masters for portraits or justified
  pictorial material.
- **Monochrome first:** semantic UI icons and product identity must work without
  arbitrary multicolor styling.
- **Optical review over blind scaling:** small targets require explicit review.
- **Provenance before merge:** record exact upstream source/revision, license,
  notice obligations, and custom/synthetic status before committing third-party
  assets.
- **Facts stay in data:** artwork never invents pilot identity, service, rank,
  status, decorations, victories, squadron, or nationality.

Forma/IconCreator may assist #129 exploration, but #129 remains authoritative
for adopt/adapt/custom strategy, icon semantics, canonical SVG delivery,
optical sizing, accessibility, and provenance.

## Privacy and sanitization

UI research, fixtures, screenshots, reviews, prompts, and assets must not expose
or embed:

- real player or campaign data;
- personal names from campaign data;
- personal installation paths or usernames;
- SQLite database contents or copies;
- logs or raw WoFF payloads;
- activation/license information;
- unredacted screenshots containing such information; or
- prior-career content reused as a placeholder while another career loads.

Use synthetic or explicitly approved sanitized evidence. Diagnostic UI text
must not reveal SQL, cursors, local paths, raw exceptions, payloads, or secrets.

## Relationship to current UI work

- **#79:** completed normative UI V2 reference and visual system. This standard
  consumes its repository artifacts and does not reopen it.
- **#80:** completed shared state matrix and sanitized fixture vocabulary. This
  standard consumes those semantics and does not redefine them.
- **#81:** future immutable presentation/query contracts must expose data in a
  form that allows the presentation layer to obey this standard without direct
  repository, SQLite, parser, or filesystem access.
- **#82:** remains the isolated PySide6/Qt feasibility, packaging, scaling, and
  accessibility spike. This standard does not accept the toolkit ADR.
- **#129:** owns the core UI V2 icon package and source/provenance decision.
- **#130-#132:** own portraits, optional material treatments, and branding/app
  icon work respectively.
- **#133:** tracks visual-asset definition/production and remains separate from
  cycle membership unless governance explicitly changes that status.

## Project-graph and release-gate boundary

This standard does not add #135 to `docs/architecture/project-graph.yaml`, does
not alter aggregate cycle membership, and does not approve Product Gates or the
UI toolkit ADR. A future decision that makes this policy release-blocking must
register that change explicitly through the normal governance process.

## Review checklist

Before completing UI-related work, confirm that:

- repository contracts were read before external references;
- any skill/reference use was minimal and task-specific;
- no external framework implementation leaked into the runtime contract;
- state meanings and stable identity were preserved;
- accessibility and supported scaling were considered;
- motion has a functional purpose and a reduced-motion behavior;
- external assets have provenance/license evidence before merge;
- fixtures/evidence are synthetic or sanitized;
- no completed issue was silently reopened or rewritten; and
- any genuine contract contradiction was reported rather than resolved by scope
  expansion.
