# Shared UI states and synthetic fixtures

Issue #80 · `EVAL-UI-STATES-001` · test contract `synthetic-ui-v1`

This document formalizes the [read-only foundation](read-only-foundation.md).
The [fixture inventory](../../woff/tests/fixtures/ui_states/README.md) maps
20 small UTF-8 examples to their intended screens and states. Its catalog is
isolated test data, not a production query service or the view-model API owned
by #81. It imports no SQLite, WoFF file reader, parser, repository, watchdog,
GUI toolkit or launcher, and performs no network access.

## Current screen names and reference authority

Issue #79, completed by PR #124, approved UI V2 and replaced Figma with the
published Site as the active rendered reference. The repository remains the
normative contract; the old Figma file is an archive. The original #80 wording
uses these earlier names:

| Original #80 name | Approved V2 destination |
|---|---|
| Dashboard | Operations (`OPR-01`) |
| Pilot | Pilot Dossier (`DOS-01`) |
| Missions | Mission Log and Mission Report (`MIS-01/02`) |
| Diary | War Diary (`JRN-01`) |
| Squadron | Squadron and Aircrew Profile (`SQD-01/02`) |
| Settings | Data & System Status (`SYS-01`), strictly read-only |

V2 also includes Reports, the shell, career selection and contextual Dossier
views. All 15 approved screen IDs have guidance below. The immutable #79 audit
is preserved; #80 does not claim a new Site deployment or rewrite archived
Figma frames. The explicit alias mapping below connects its visual examples
to this six-state contract.

## One envelope, six states

Evaluate the request phase first. A pending request is `loading`; a failed
query is `error`. A completed query may report a missing prerequisite, an
unavailable source, or a usable result. For a usable result, freshness is
checked before collection cardinality: an expired empty collection is stale,
not current `empty`. A current or explicitly unknown-freshness collection
with zero items is `empty`; a populated collection or valid singleton is
`ready`. These rules choose exactly one state.

| State | Required evidence | Visible behavior |
|---|---|---|
| `loading` | Request pending; `reason=request_pending`; no payload, timestamp or warnings. | Announce loading; retain shell geometry and safe selection context. Never borrow a previous career's content. |
| `ready` | Valid singleton or nonempty primary collection; `reason=null`; current or explicitly unknown freshness. | Show supplied data, field reasons, observation time and every warning. Optional empty collections do not make the whole screen empty. |
| `empty` | Successful authoritative primary-collection result with `records=[]`; current or explicitly unknown freshness. | Say which collection has no records. Preserve a valid subject header. Do not infer zero for unrelated statistics. |
| `missing` | Required career/record/source identity has not been established; `career_not_selected` or `source_missing`; no payload. | Explain the prerequisite and offer selection, return to the parent list, or data status. An absent detail ID is missing, never an invented empty record. |
| `stale/unavailable` | Expired snapshot, unavailable service, or explicit source rejection (`source_truncated`, `source_unsupported`, `source_unreadable`). | Identify the exact reason. Retain only a validated snapshot for the same career, with its safe timestamp and warning, and never label it current. Without one, show no payload or invented timestamp. |
| `error` | The query operation failed (`query_failed`); no payload or observation time. | Show the fixed safe diagnostic, `Retry view` and data-status navigation. Preserve selection context, never raw exception details. |

`empty` therefore requires a successful query; `missing` describes an unmet
prerequisite, not an exception; `error` describes a failed operation. A query
that successfully reports an unreadable source yields `stale/unavailable`,
not `error`. `Partial`, `Unknown` and `Authoritative zeroes` describe content
inside an envelope and are not additional shared states.

An expired empty collection also uses `stale/unavailable`: its retained
payload keeps the named collection and empty records, with the old timestamp
and warning. `empty` must never conceal that the observation is old.

## Test envelope fields

| Field | Contract |
|---|---|
| `id`, `screens` | Stable fixture identifier and ordered intended-screen inventory; not live routes or domain identifiers. |
| `synthetic`, `label` | Exactly `true` and `Synthetic` on every envelope, including no-data states. A copied fixture keeps both. |
| `contract_version` | `synthetic-ui-v1`, the demonstration selection/shape contract. Version changes require review; this is not a WoFF format version. |
| `state`, `reason` | One shared state and its stable reason above. Successful snapshots have a null envelope reason. |
| `career_id` | Stable synthetic career identity, or null for a global/unselected scope. Selected-career payloads require an ID. Names and visible list positions never select a career. |
| `source_authority` | `synthetic-records`, `synthetic-derived`, `synthetic-settings`, `synthetic-query`, or `unresolved`. Indicates the origin of the demo snapshot, never authority over real campaign data. Successful/retained payloads require a records, derived or settings authority. |
| `observed_at` | Strict UTC `YYYY-MM-DDTHH:MM:SSZ` observation time, or null when unknown. Never substitute a mission date, file mtime, render time or current wall clock. |
| `freshness` | `current`, `stale`, or `unknown`; always displayed with its evidence. Unknown is not current. |
| `warnings` | Zero or more unique `{code, message}` entries, sorted by code, from the fixed safe vocabulary. Display all warnings; do not collapse a source conflict into a generic badge. |
| `data` | Null when no usable snapshot exists; otherwise `{collection, fields, records}`. A null collection denotes a singleton. A named collection denotes an authoritative collection result. |

The demonstration clock is fixed at `2026-01-01T12:00:00Z`. The demo freshness
policy uses 60 seconds inclusive for current observations; an age above 60
seconds is stale. Future times are rejected. Unknown observation time remains
null with `freshness_unknown`; it cannot establish freshness. The catalog
bounds retained observations to two days purely to keep the examples small.
These values do not choose a production refresh interval or cache policy.

During service unavailability, a safe retained snapshot may have unknown
freshness even when its timestamp is known; both `source_unavailable` and
`freshness_unknown` must remain visible. An expired retained observation also
requires `snapshot_expired`. Replacing the active `career_id` clears the old
snapshot before the new identity is presented; cached data from another
career cannot satisfy any of these states.

Each scalar field is `{value, unavailable_reason}` and inherits the snapshot's
source authority and contract. A known value has a null reason; an unavailable
value is null with one of the reasons below. `0` is a known integer, never a
missing-value substitute; booleans are rejected as numeric counts. An empty
primary collection is represented by an actual empty list, not null.

| Field reason | Meaning and display |
|---|---|
| `unknown` | The concept exists but no value is known; show `Unknown`. Missing status never becomes Active. |
| `not_supplied` | The current source/contract does not supply this optional value; show `Not available`. |
| `source_conflict` | Candidate sources disagree; keep the value null, show the conflict warning and choose no winner. |
| `redacted` | Deliberately withheld information; show `Hidden`, never the original value. |
| `unsupported` | This field cannot be represented under the current source contract; show `Not available — unsupported`. |
| `unreadable` | No safe field value could be read; show `Not available — unreadable`. |
| `truncated` | The field failed completeness validation; show `Not available — incomplete`. |

Unavailable optional fields keep a valid snapshot `ready`. They require a
`partial_record` warning, except deliberate redaction, which requires
`redacted_fields`. A conflict adds `source_conflict`; these warnings coexist.
The conflict example withholds service and retains the known identity and
zero confirmed victories. It does not establish a source-precedence policy.

Records carry stable synthetic IDs, their owning `career_id`, an invented
event time and safe fields. Diary references resolve to a supplied mission of
the same career. RFC, RNAS and RAF are distinct literals. The selector includes
same-name careers in slots 2 and 3; it does not create Pilot1 or renumber Pilot2.

## Visible guidance for every approved screen

Each cell supplies user guidance, in addition to the common timestamp,
warning, labeling and navigation rules. “Retry” requests a new read-only view;
it never ingests, repairs, edits configuration, or triggers a launcher.
For singleton detail views, `empty` applies only to a successfully queried
child collection with an established subject; a missing subject is `missing`.
`SYS-01` remains reachable with no career selected and never demands one.

<!-- state-matrix:start -->
| Screen | `loading` | `ready` | `empty` | `missing` | `stale/unavailable` | `error` |
|---|---|---|---|---|---|---|
| `APP-00` | Loading career context; keep navigation. | Show selected career and destinations. | No careers recorded; open data status. | Select a career; data status remains available. | Career context unavailable; show safe prior time if retained. | Context could not load; retry or open data status. |
| `SEL-01` | Loading career list. | Show separate stable-ID options, including homonyms. | No careers recorded. | Career source missing; open data status. | Career list not current; show its observation time. | Career list failed; retry or open data status. |
| `OPR-01` | Loading operations overview. | Show known summaries and all warnings. | No activity recorded for this established career. | Select a career or inspect missing overview source. | Overview not current; retain safe time and offer retry. | Overview failed; retry or open data status. |
| `DOS-01` | Loading pilot dossier. | Show known identity, statistics and unavailable field reasons. | No service records for this established pilot; keep known identity. | Pilot identity/source missing; select career or open data status. | Dossier unavailable or old; identify source reason and retained time. | Dossier failed; retry or open data status. |
| `DOS-02` | Loading career record. | Show confirmed service events. | No service events recorded. | Career/source missing; return to Dossier. | Service record not current; show reason and retained time. | Career record failed; retry or return to Dossier. |
| `DOS-03` | Loading victories and claims. | Distinguish claims from confirmed victories. | No claims or victories recorded; do not infer other counts. | Required career/source missing; return to Dossier. | Claims source unavailable or old; show reason and time. | Claims view failed; retry or open data status. |
| `DOS-04` | Loading decorations. | Show supplied confirmed decorations. | No decorations recorded. | Required career/source missing; return to Dossier. | Decorations unavailable or old; show reason and time. | Decorations failed; retry or return to Dossier. |
| `MIS-01` | Loading mission history. | Show supplied stable IDs in documented order. | No missions recorded in this query. | Required career/source missing; select career or open data status. | Mission history not current; show warning and retained time. | Mission history failed; retry or open data status. |
| `MIS-02` | Loading selected mission. | Show supplied mission details and field reasons. | No related events for this established mission. | Mission ID not established; return to Mission Log. | Mission detail unavailable or old; show reason and time. | Mission detail failed; retry or return to Mission Log. |
| `SQD-01` | Loading squadron roster. | Show known roster and unknown transfer reasons. | No members recorded in this roster query. | Squadron identity/source missing; open data status. | Roster not current; never infer a member departure. | Roster failed; retry or open data status. |
| `SQD-02` | Loading aircrew profile. | Show supplied profile without changing career selection. | No service events for this established member. | Member ID missing; return to Squadron. | Profile unavailable or old; retain safe timestamp. | Profile failed; retry or return to Squadron. |
| `JRN-01` | Loading war diary. | Show supplied narratives and stable mission associations. | No diary entries recorded. | Career/narrative source missing; open data status. | Diary not current; show warning and retained time. | Diary failed; retry or open data status. |
| `RPT-01` | Loading report library. | Show supplied report IDs and safe summaries. | No reports recorded. | Career/report source missing; open data status. | Report library not current; show warning and time. | Report library failed; retry or open data status. |
| `RPT-02` | Loading selected report. | Show supplied safe report content. | No sections for this established report. | Report ID missing; return to Reports. | Report unavailable or old; show reason and time. | Report failed; retry or return to Reports. |
| `SYS-01` | Loading effective settings and data status. | Show redacted settings, known diagnostics and unknown indicators. | No diagnostic observations recorded; never infer healthy status. | Required configuration/status source missing; explain without editing. | Status unavailable or old; no live-service claim. | Status query failed; show safe diagnostic and retry. |
<!-- state-matrix:end -->

## Prototype aliases and synthetic labeling

The #79 Site's fourteen visual choices map to the same state names as follows.
They are UI scenario labels, not competing enum values. An optional failed
field inside a usable record stays `ready`; the table's unavailable choices
describe the whole-source variants captured by #79.

<!-- visual-aliases:start -->
| Prototype scenario ID | Shared state | Meaning inside the envelope |
|---|---|---|
| `complete` | `ready` | Supplied complete record. |
| `loading` | `loading` | Pending request. |
| `empty` | `empty` | Successful empty primary collection. |
| `partial` | `ready` | Known identity and explicit unavailable optional fields. |
| `no-career` | `missing` | `career_not_selected`. |
| `missing` | `missing` | `source_missing`. |
| `truncated` | `stale/unavailable` | `source_truncated`; hide unvalidated payload. |
| `unsupported` | `stale/unavailable` | `source_unsupported`. |
| `unreadable` | `stale/unavailable` | `source_unreadable`. |
| `error` | `error` | `query_failed`, fixed sanitized diagnostic. |
| `stale` | `stale/unavailable` | `snapshot_expired`, safe retained timestamp and warning. |
| `zeroes` | `ready` | Explicit zero scalar values; an empty primary collection still uses `empty`. |
| `unknown` | `ready` | Unknown fields; no zero or Active fallback. |
| `unavailable` | `stale/unavailable` | Whole source unavailable; optional unavailable fields remain field reasons. |
<!-- visual-aliases:end -->

Mockups and captured examples must visibly show `Synthetic`, plus the fixture
ID and canonical state in their fixture controls or annotations. The label
remains visible in loading, empty, missing, unavailable and error examples,
and accompanies crops/exports. It is not confined to a README or tooltip.
Prototype indicators, including last sync, watchdog and database connection,
are explicitly synthetic or unavailable. Tests retain the label when copying
a snapshot. The prior Site audit supplies visual-label evidence; these new
tests check the payload/alias contract without claiming a fresh rendered audit.

## Privacy, isolation and acceptance evidence

`scripts/validate_ui_fixtures.py` accepts exact keys, a closed invented-text
vocabulary, numeric synthetic IDs, bounded integers, safe UTC timestamps and
fixed diagnostic templates. It rejects personal names, real installation
paths, activation/license fields or values, raw game payloads, database
copies, logs, screenshots, binary files, unknown fields, duplicate JSON keys,
non-finite numbers and symlinks. Prefixing unapproved text with `Synthetic`
does not make it pass. Rejection output never echoes the rejected value.

Catalog extensions require review of the new invented text. Automated checks
enforce this closed catalog; they do not establish that arbitrary uploaded
data is anonymized. No campaign attachment was used as fixture input.

The fixture tests run outside `woff/tests`, whose shared setup imports SQLite.
The standalone validator also runs under `python -I -S`, with imports and
audit events for SQLite, networking and application/toolkit code blocked in
the isolation regression. Both forms read only this catalog and code needed
to validate it. The existing package exclusion keeps fixtures out of runtime
distribution; the installed dependency contract remains unchanged.

Q0: on `main` at `2d3e269`, #56/PR #68 supplied the state vocabulary and
#79/PR #124 supplied visual examples; neither implemented this formal catalog.
Historical issue/PR/commit inspection found no equivalent implementation.
The new primary-screen/state test failed with `FileNotFoundError` for
`catalog.json` before implementation. The immutable audit has a separate
purpose and remains intact.

Validation: the standalone checker, fixture mutation/isolation tests, complete
architecture-contract and privacy suites, project-graph validation, full
pytest suite, Pyright and `git diff --check`. Completion satisfies #80's
fixture prerequisite for #81 and #82; it does not adopt Qt, approve Product
Gates A/B, certify native Windows DPI, or complete cycle 3.4.0.
