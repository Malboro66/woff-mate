# Immutable read-only application contracts

Issue #81 · `EVAL-UI-CONTRACTS-001` · presentation contract
`synthetic-ui-v1`

The executable contract is [`woff/ui_contracts.py`](../../woff/ui_contracts.py).
It is independent of the eventual desktop toolkit and contains no live query
implementation. The only permitted data path remains:

`presentation -> application query services -> repositories -> SQLite`

Presentation receives copied frozen values and can only request or cancel a
snapshot. It never receives a repository, connection, cursor, SQL statement,
parser payload, source path, watcher, queue or mutable domain record.

## Shared envelope

Every screen snapshot owns one `SnapshotEnvelope`. Its independent closed
dimensions prevent unlike conditions from being collapsed:

| Dimension | Values and rule |
|---|---|
| Screen state | `loading`, `ready`, `empty`, `missing`, `stale/unavailable`, `error` |
| Freshness | `current`, `stale`, `unknown`; current and stale require an aware observation time, `snapshot_expired` requires `stale`, and other unavailable outcomes require `unknown`. Retained payload always requires a known, valid, timezone-aware observation, even when freshness is unknown |
| Completeness | `complete` or `partial`; this is content status, not a seventh screen state, and snapshots derive it from their nested field gaps |
| Observation | A known timezone-aware value or a `FieldValue` unavailable reason |
| Policy | A stable `FreshnessPolicyId` or an explicit unavailable reason; #80 supplies no policy ID, so fixture tests do not invent one |
| Authority | A closed application/synthetic authority, independent from a path or implementation object; successful and retained payloads require records, derived or settings authority, while query/unresolved authority is limited to no-result or transitional outcomes |
| Version | A validated `ContractVersion`, preserving the fixture contract version during conversion |
| Warnings | Defensively copied, unique by `WarningCode`, sorted by the code's value; duplicate and unordered inputs are normalized. Safe display text is repository-owned |
| Field gaps | Nested `FieldValue` values are authoritative. `FieldUnavailable` is the immutable summary, augmented from the entire payload (including records in collections), preserving `unknown`, `not_supplied`, `source_conflict`, `redacted`, `unsupported`, `unreadable` and `truncated` |
| Failure | `SanitizedFailure` exposes only a closed code, fixed message and retryability; source exceptions are discarded |

Known zeroes and known empty tuples remain values. They are never represented
as missing, unknown or unavailable. `error` requires a sanitized failure;
non-error states cannot carry one. All nested collections are tuples and all
field values are checked for deep immutability.

Known integer fields require `type(value) is int`: booleans, floats, strings
and integer subclasses are rejected. This applies to the source slot, every
`PilotStatistics` field, and both `MissionSummary` count fields. Zero remains
known, and unavailable reasons remain valid without a numeric substitute.
Warning, failure and diagnostic codes are closed at runtime as well as in
annotations; validation errors never echo rejected diagnostic values.

The envelope fields are validated as one semantic unit. In particular, an
expired snapshot cannot be labelled current, a stale freshness value cannot be
attached to a successful state, and a usable result cannot leave source
authority unresolved. Screen construction augments the unavailable-field
summary from every nested `FieldValue` and derives completeness, so an omitted
manual summary cannot turn a partial payload into a complete one.

`loading`, `missing` and `error` never carry payload. A payload-free snapshot
cannot declare partial completeness or field gaps. Whole-source rejection
(`source_truncated`, `source_unsupported`, `source_unreadable`) cannot carry
unvalidated data. Retention is limited to `source_unavailable` and
`snapshot_expired`, with resolved authority and a known aware observation.
Unknown freshness remains usable for a newly supplied successful result or
for a safely timestamped retained result; it never excuses an undatable cache.
The query service owns observation age and policy evaluation; constructors
do not substitute the wall clock, event dates or a production expiry policy.

## Six screen contracts

The original Issue #81 names use the current repository terminology below.

| Original domain | Current contract | Stable identities |
|---|---|---|
| Dashboard | `OperationsSnapshot` | Standalone selected `PilotId`, `MissionId` |
| Pilot | `PilotDossierSnapshot` | Standalone selected `PilotId`; the persistent pilot ID is the established career selection identity |
| Missions | `MissionsSnapshot` | `PilotId`, `MissionId`; detail selection resolves by ID, never position |
| Diary | `WarDiarySnapshot` | `PilotId`, `DiaryEntryId`, linked `MissionId` |
| Squadron | `SquadronSnapshot` | `PilotId`, independently retained selected `SquadronId` and `SquadronMemberId` |
| Settings | `SystemStatusSnapshot` | `SystemDiagnosticId`; no path or mutation field |

The #80 fixture catalog has no stable squadron identifier or freshness-policy
identifier. Fixture-backed tests therefore expose those fields as
`not_supplied`; they do not derive an ID from the squadron label or invent a
policy. Display names, labels, slots, timestamps and list positions are never
identity inputs.

Career and detail selection context is independent from optional payload.
Loading, missing-source, unavailable and error snapshots can therefore retain
the selected stable IDs without retaining old records. A selected detail ID is
required to resolve only when an authoritative or retained collection is
present (and for successful `ready`/`empty` results); payload-free transitions
do not fabricate records merely to preserve selection.

State/cardinality checks depend on the screen context:

| Context | Successful-state rule |
|---|---|
| `MIS-01`, `JRN-01`, `SQD-01` | The primary mission, diary or roster tuple is nonempty for `ready` and empty for `empty`. A roster header cannot make an empty roster ready. |
| `MIS-02`, `SQD-02` | An explicit selected subject must resolve. A valid subject may remain visible in `empty` while its related child collection has no content; the parent subject is not erased. |
| `OPR-01`, `DOS-01` | `ready` needs actual overview/dossier payload. Optional recent missions may be empty. `empty` may retain known subject/statistics context, but cannot carry recent missions. |
| `SYS-01` | `ready` needs settings or diagnostic payload. `empty` requires no diagnostics and may retain a settings header; it never implies healthy status. |

`SystemStatusSnapshot.profile` is optional: `None` means no settings payload.
`FieldValue.unavailable(...)` instead denotes a real settings field gap, so it
can produce partial completeness only in a payload-bearing state. It is
rejected as fabricated payload in loading, missing and error states. Global
system status uses `source_missing`, never `career_not_selected`.

Clearing a career also clears mission, squadron and member selection IDs.
An unselected snapshot cannot retain a subject from the previous career.

Every child record that carries `pilot_id` must match its snapshot's standalone
career context. Every identifiable collection rejects duplicate stable IDs.
This applies to Operations/Missions mission summaries, diary entries, squadron
members and system diagnostics, as applicable. Pilot identity payloads are
checked against the same context.

Both mission-bearing snapshots carry
`MissionOrderPolicy.NEWEST_FIRST_STABLE_ID`. Construction normalizes mission
summaries by aware `occurred_at` descending and then `MissionId` ascending. This
preserves the #40/repository newest-first temporal contract while giving exact
timestamp ties a presentation-safe stable-identity tie-breaker. The #80 fixture
catalog's ascending inventory order remains fixture input determinism, not a
production ordering rule. A record without a known, aware event time is
rejected from this ordered collection rather than assigned an invented temporal
position; input or storage order is never a tie-breaker.

Pilot affiliation is a `FieldValue[NationServicePresentation]` produced by the
canonical #136 domain. Nation and service codes, states and labels remain
independent. Unsupported source evidence and `serviceOrNationLabel` are not
part of this contract.

## Query-service boundary

Six protocols correspond to the six snapshot types. A `QueryRequest` carries:

- a new opaque `RequestId`;
- a stable typed selection, or explicit `None` when no career is selected;
- `initial`, `refresh` or `retry` intent;
- a positive timeout;
- the superseded request for refresh, or failed request for retry.

A refresh is a new application request with a new ID. It does not expose a
storage refresh method to presentation. Cancellation is a separate immutable
`CancellationRequest` addressed to a request ID. Implementations must translate
timeouts, cancellation and other failures into the closed sanitized envelope;
they must not leak the originating exception. Live repository adapters remain
deferred to the issues that stabilize their source semantics.

The five career-scoped protocols accept `QueryRequest[Optional[Selection]]`,
using the appropriate `PilotSelection`, `MissionSelection` or
`SquadronSelection` type. `None` requests a payload-free
`missing/career_not_selected` snapshot with no pilot or subject IDs; widgets
must not invent IDs or construct that result outside the service boundary.
For example, use `QueryRequest[Optional[MissionSelection]].initial(...)` for
either a selected or unselected mission request. The immutable generic request
remains invariant, so callers declare the protocol's optional type explicitly.
Refresh and retry may carry `None` too, with the same new-ID, linkage, positive
timeout and cancellation rules. `SystemStatusQueryService` remains global and
accepts `QueryRequest[None]` independently of career selection.

## Fixture-backed proof and limits

`tests/test_ui_contracts.py` consumes only the deterministic #80 catalog. It
proves frozen records, defensive copies, deep immutable fields, six screen
types, state/freshness/authority/completeness coherence, owner-scoped and
duplicate-free stable IDs, retained selection context, deterministic mission
ordering and ties, canonical nation/service presentation, sanitized failures,
request lifecycle semantics and absence of storage/toolkit imports.

This work adds no widgets, live reads, writes, schema changes, toolkit
dependency, toolkit decision, product-gate approval or production query
adapter.
