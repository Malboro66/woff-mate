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
| Freshness | `current`, `stale`, `unknown`; current and stale require an aware observation time |
| Completeness | `complete` or `partial`; this is content status, not a seventh screen state |
| Observation | A known timezone-aware value or a `FieldValue` unavailable reason |
| Policy | A stable `FreshnessPolicyId` or an explicit unavailable reason; #80 supplies no policy ID, so fixture tests do not invent one |
| Authority | A closed application/synthetic authority, independent from a path or implementation object |
| Version | A validated `ContractVersion`, preserving the fixture contract version during conversion |
| Warnings | Immutable `WarningCode` values whose safe display text is repository-owned |
| Field gaps | `FieldValue` and `FieldUnavailable` preserve `unknown`, `not_supplied`, `source_conflict`, `redacted`, `unsupported`, `unreadable` and `truncated` |
| Failure | `SanitizedFailure` exposes only a closed code, fixed message and retryability; source exceptions are discarded |

Known zeroes and known empty tuples remain values. They are never represented
as missing, unknown or unavailable. `error` requires a sanitized failure;
non-error states cannot carry one. All nested collections are tuples and all
field values are checked for deep immutability.

## Six screen contracts

The original Issue #81 names use the current repository terminology below.

| Original domain | Current contract | Stable identities |
|---|---|---|
| Dashboard | `OperationsSnapshot` | `PilotId`, `MissionId` |
| Pilot | `PilotDossierSnapshot` | `PilotId`; the persistent pilot ID is the established career selection identity |
| Missions | `MissionsSnapshot` | `PilotId`, `MissionId`; detail selection resolves by ID, never position |
| Diary | `WarDiarySnapshot` | `PilotId`, `DiaryEntryId`, linked `MissionId` |
| Squadron | `SquadronSnapshot` | `PilotId`, `SquadronId`, `SquadronMemberId` |
| Settings | `SystemStatusSnapshot` | `SystemDiagnosticId`; no path or mutation field |

The #80 fixture catalog has no stable squadron identifier or freshness-policy
identifier. Fixture-backed tests therefore expose those fields as
`not_supplied`; they do not derive an ID from the squadron label or invent a
policy. Display names, labels, slots, timestamps and list positions are never
identity inputs.

Pilot affiliation is a `FieldValue[NationServicePresentation]` produced by the
canonical #136 domain. Nation and service codes, states and labels remain
independent. Unsupported source evidence and `serviceOrNationLabel` are not
part of this contract.

## Query-service boundary

Six protocols correspond to the six snapshot types. A `QueryRequest` carries:

- a new opaque `RequestId`;
- a stable typed selection;
- `initial`, `refresh` or `retry` intent;
- a positive timeout;
- the superseded request for refresh, or failed request for retry.

A refresh is a new application request with a new ID. It does not expose a
storage refresh method to presentation. Cancellation is a separate immutable
`CancellationRequest` addressed to a request ID. Implementations must translate
timeouts, cancellation and other failures into the closed sanitized envelope;
they must not leak the originating exception. Live repository adapters remain
deferred to the issues that stabilize their source semantics.

## Fixture-backed proof and limits

`tests/test_ui_contracts.py` consumes only the deterministic #80 catalog. It
proves frozen records, defensive copies, deep immutable fields, six screen
types, state/freshness/completeness distinctions, explicit stable IDs,
canonical nation/service presentation, sanitized failures, request lifecycle
semantics and absence of storage/toolkit imports.

This work adds no widgets, live reads, writes, schema changes, toolkit
dependency, toolkit decision, product-gate approval or production query
adapter.
