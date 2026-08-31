# Evaluation catalog

## Purpose

WoFF Mate uses evaluation-driven development. Observable evidence is defined
before implementation. The smallest implementation is then accepted only when
the focused evidence and all applicable quality gates pass.

The machine-readable eval registry lives in
[`../architecture/project-graph.yaml`](../architecture/project-graph.yaml). This
document defines the human-readable contract and cycle aggregation rules.

## Eval types

| Type | Use | Preferred evidence |
|---|---|---|
| Deterministic | Database, parser, date, CLI, scheduler, migration, privacy, security, and RPG rules | pytest, sanitized fixtures, deterministic simulation, structural source checks |
| Judgment | Narrative quality, diagnostics, and future social experience | explicit rubric and human review |

WoFF Mate does not need an AI evaluation platform for deterministic behavior.

## Status values

| Status | Meaning |
|---|---|
| `planned` | The evidence contract exists but the implementation has not passed it |
| `implemented` | A concrete test or recorded procedure enforces the evidence |

Closing an issue requires its applicable evals to be implemented and passing.

## Completed corrective cycle 3.2.1

| Eval | Work item | Evidence | Enforcement |
|---|---|---|---|
| `EVAL-DIARY-001` | #26 | Editing Bob's diary changes no row owned by Alice | `woff/tests/test_woff_editor.py` |
| `EVAL-DIARY-002` | #26 | Empty input removes entries only for the selected pilot | `woff/tests/test_woff_editor.py` |

Cycle 3.2.1 records completed corrective scope. The graph does not claim a
public 3.2.1 release unless release evidence is recorded separately.

## Active cycle 3.3.0

Issue #50 is the official tracker. The sixteen work items remain separate
issues and pull requests.

| Work item | Eval IDs | Required evidence |
|---|---|---|
| #34 | `EVAL-DB-001`, `EVAL-DB-002` | Atomic rollback and caller-owned transactions |
| #57 | `EVAL-PILOT-STATS-001`, `EVAL-PILOT-STATS-002` | Partial-source preservation and authoritative zero writes |
| #45 | `EVAL-CFG-001`, `EVAL-CFG-002` | Early validation and preservation of invalid personal config |
| #36 | `EVAL-SCHED-001`, `EVAL-SCHED-002` | Bounded scheduling and correct move handling |
| #42 | `EVAL-SNAP-001`, `EVAL-SNAP-002`, `EVAL-SNAP-003` | Exact stable snapshots, bounded simulated Windows retry, persistence-aware acknowledgement, and observer-first startup coverage |
| #40 | `EVAL-DATE-001`, `EVAL-DATE-002` | Canonical validation and deterministic ordering |
| #39 | `EVAL-MISSION-001`, `EVAL-MISSION-002` | Stable identity and non-destructive enrichment |
| #70 | `EVAL-IDENTITY-001`, `EVAL-IDENTITY-002` | Career isolation across slot reuse, same-name independence, and rejection of identityless persistence |
| #87 | `EVAL-CAREER-REUSE-EVIDENCE-001` | Sanitized evidence distinguishes replay from same-slot, same-name career replacement or records that the source structure cannot do so safely |
| #71 | `EVAL-PILOT-STATUS-001`, `EVAL-PILOT-STATUS-002` | Preservation of authoritative status and idempotent explicit transitions |
| #72 | `EVAL-DOSSIER-TXN-001`, `EVAL-DOSSIER-TXN-002` | Atomic rollback and exactly-once consistent Dossier state |
| #93 | `EVAL-CAREER-SELECT-001`, `EVAL-CAREER-SELECT-002` | Stable career selection and pre-mutation rejection of ambiguous names |
| #94 | `EVAL-ROOT-BINDING-001`, `EVAL-ROOT-BINDING-002` | Root-namespaced slot and persistent-career identity, including retired-career isolation, plus migration recovery evidence |
| #95 | `EVAL-PERSIST-RETRY-001` through `EVAL-PERSIST-RETRY-004` | Exactly-once persistence, same-mission derived-state correction, a stable retry bound across late notifications, and complete startup recovery coverage |
| #73 | `EVAL-VICTORY-MERGE-001`, `EVAL-DECORATION-MERGE-001` | Lossless same-minute victories and non-destructive enrichment of stable rows |
| #27 | `EVAL-DEFER-001`, `EVAL-DEFER-002` | Deferred reprocessing without loss or unbounded retention |

### EVAL-CYCLE-330-001

The aggregate eval passes only when:

- all sixteen member issues satisfy their acceptance criteria
- every applicable member eval is implemented and passing
- dependency relations in the graph are satisfied
- focused tests, related tests, the full suite, and Pyright pass
- applicable database, concurrency, and Windows evidence passes
- project graph and public documentation reflect the delivered behavior
- `Q6-CYCLE-3.3.0` passes

Green CI alone does not pass this aggregate eval.

Issue #27 and its two deferred-ingestion evals reached `main` through PR #115.
Issue #87 remains the only unresolved cycle member. Its sanitized-evidence gap
does not weaken or reopen the guarantees already verified by #70. The aggregate
gate remains pending until #87 records either sufficient longitudinal evidence
or the structural limitation defined by its acceptance criteria.

## Newly registered data-integrity evals

| Eval | Work item | Required evidence |
|---|---|---|
| `EVAL-CAREER-REUSE-EVIDENCE-001` | #87 | Sanitized longitudinal fixtures distinguish replay from a same-slot, same-name replacement career, or prove that available Dossier structure cannot support the distinction safely |
| `EVAL-CAREER-SELECT-001` | #93 | Same-name careers stay separate in every query and editor flow selected by stable pilot ID |
| `EVAL-CAREER-SELECT-002` | #93 | Ambiguous names fail before export or mutation with a deterministic candidate contract |
| `EVAL-ROOT-BINDING-001` | #94 | Equal slots in distinct watched roots keep independent bindings and persistent career IDs, even after another root retires a same-name career, with correct dependent-file routing |
| `EVAL-ROOT-BINDING-002` | #94 | Any binding migration proves backup, integrity, rollback, and reopen behavior |
| `EVAL-PERSIST-RETRY-001` | #95 | Real transient SQLite contention retains the admitted generation and persists it exactly once after retry |
| `EVAL-PERSIST-RETRY-002` | #95 | Duplicate notifications cannot reset the four-attempt budget, including notifications received after active work drains |
| `EVAL-PERSIST-RETRY-003` | #95 | A pending correction with the same mission identity atomically aligns mission, diary, and RPG state after the retained generation completes |
| `EVAL-PERSIST-RETRY-004` | #95 | Startup waits cover source and dependent Dossier snapshots, four SQLite busy windows, and every bounded backoff delay |
| `EVAL-WINGMAN-IDENTITY-001` | #96 | Distinct same-name wingmen retain separate histories and personality ownership |
| `EVAL-WINGMAN-MERGE-001` | #96 | Poorer roster data cannot erase richer fields or reassign personality |
| `EVAL-DIARY-EMPTY-001` | #97 | Empty narrative in a retained block does not delete the row, while removed blocks follow explicit deletion semantics |
| `EVAL-CATALOG-STABILITY-001` | #98 | Empty, truncated, or changing input cannot replace the last known-good squadron payload |
| `EVAL-CATALOG-STABILITY-002` | #98 | Stable validated input replaces atomically and remains idempotent on replay |
| `EVAL-PILOT-PROVENANCE-001` | #99 | Partial sources preserve authoritative Dossier provenance and non-empty update time |
| `EVAL-PILOT-PROVENANCE-002` | #99 | Richer and poorer source replay converges without provenance regression |

## Planned wingman transfer feature evals

| Eval | Work item | Required evidence |
|---|---|---|
| `EVAL-WINGMAN-TRANSFER-001` | #101 | A confirmed transfer with reliable destination evidence creates exactly one event for the correct persistent wingman with source and destination squadrons |
| `EVAL-WINGMAN-TRANSFER-002` | #101 | A confirmed transfer without destination evidence creates exactly one event with an explicit unknown destination and never fabricates an assignment |
| `EVAL-WINGMAN-TRANSFER-003` | #101 | Same-squadron disappearance, partial or failed roster input, replay, and same-name members cannot produce a false or misattributed transfer |

## Independent presentation foundation

Issue #56 is completed documentation and architecture-contract work. It is
intentionally independent of, and is not a member of, the active 3.3.0
reliability cycle. Its applicable gates are Q0 and Q1 only; this record does not
claim Q5 or approval of Product Gate A or Gate B.

| Eval | Work item | Evidence | Enforcement |
|---|---|---|---|
| `EVAL-UI-FOUNDATION-001` | #56 | Proposed toolkit and read-only presentation boundaries are documented, linked, dependency-free, and structurally enforced | `woff/tests/test_architecture_contracts.py` |

## Read-only UI work

| Eval | Work item | Status | Evidence or required evidence | Enforcement |
|---|---|---|---|---|
| `EVAL-UI-DESIGN-001` | #79 | Implemented | The approved V2 screen map, visual tokens and materials, component/state inventory, focus order, Windows scaling behavior, persistent simulator-slot labels, and synthetic labels pass the recorded repository design walkthrough and the published UI V2 Site passes its rendered contrast and interaction audit | `woff/tests/test_architecture_contracts.py` |
| `EVAL-UI-STATES-001` | #80 | Planned | Deterministic synthetic fixtures cover every shared state and privacy constraint without production dependencies | — |
| `EVAL-UI-CONTRACTS-001` | #81 | Planned | Immutable toolkit-independent view models and query protocols preserve stable identity, state, freshness, warnings, and sanitized failures | — |
| `EVAL-UI-SPIKE-001` | #82 | Planned | One PySide6 line passes the supported Python and Windows packaging and measured resource matrix | — |
| `EVAL-UI-SPIKE-002` | #82 | Planned | Scaling, keyboard use, accessibility, plugin behavior, and licensing evidence support a Go, Conditional Go, or No-go recommendation | — |

Issue #79 is complete. Its repository design artifacts are
`docs/ui/ui-v2-reference.md`, `docs/ui/ui-v2-visual-system.md`, and
`docs/ui/ui-v2-walkthrough.md`. The architecture contract verifies the required
screen IDs, stable-career boundary, persistent sparse `PilotN` source-slot
labels, data-honesty vocabulary, material rules, focus/scaling coverage,
synthetic labeling, repository links, immutable evidence, and completed
governance state. It also preserves the absence of GUI runtime dependencies.
The published
[WoFF Mate UI V2 Site](https://woff-mate-ui-v2.pilotohans.chatgpt.site/)
replaces Figma as the active rendered source. Its
[recorded audit](../ui/ui-v2-rendered-audit.md) passes all 15 screen IDs, all 14
shared semantic states, Desktop 100%, 125%, 150%, and 200%, rendered WCAG AA
contrast, same-name career isolation, persistent slot presentation,
destination focus, navigation conformance, and required visual coverage.
`EVAL-UI-DESIGN-001` is implemented by the immutable
`UIV2-SITE-2026-08-31-AUDIT-2` evidence revision and the architecture contract.

Issue #80 remains unblocked planning work. Issue #81 waits for the shared state
and fixture vocabulary from #80. Issue #82 is an isolated feasibility spike
that also waits for #80. None of these items adopts Qt, creates a production UI,
or approves Product Gate A or Product Gate B.

### Implemented scheduler evals

- `EVAL-SCHED-001` is enforced by deterministic burst, Windows alias,
  coalescing, saturation, metrics, submission-failure, and shutdown tests in
  `woff/tests/test_ingestion_scheduler.py`.
- `EVAL-SCHED-002` is enforced by destination identity tests in
  `woff/tests/test_ingestion_scheduler.py` and tmp-to-watched/move-away coverage
  in `woff/tests/test_handler_integration.py`.

### Implemented snapshot evals

- `EVAL-SNAP-001` is enforced by deterministic snapshot/parser and processing
  contract tests in `woff/tests/test_stable_snapshot.py`. They prove that parsers
  consume verified bytes, changed generations retry, failed identity or
  persistence remains unacknowledged, and an acknowledged unchanged generation
  is suppressed.
- `EVAL-SNAP-002` is enforced by bounded denial, disappearance, replacement,
  mutation, backoff, saturation, and drained-shutdown simulations in
  `woff/tests/test_stable_snapshot.py` and
  `woff/tests/test_ingestion_scheduler.py`. These are deterministic simulations;
  this evidence does not claim a Windows-native run.
- `EVAL-SNAP-003` is enforced by
  `TestWatchdogStartup::test_live_file_created_after_observer_start_is_not_baseline_submitted`
  in `woff/tests/test_handler_integration.py`. Synchronization events create an
  approved file only after observer startup, exclude it from baseline globbing,
  coalesce a canonical duplicate, process its live generation once, and verify
  drained scheduler shutdown.

### Implemented persistence retry evals

- `EVAL-PERSIST-RETRY-001` is enforced by real SQLite `BEGIN IMMEDIATE`
  contention through the production `FileProcessor` and `EventScheduler` path
  in `woff/tests/test_persistence_retry.py`. The tests retain the exact verified
  source bytes and Dossier-backed identity, release the writer lock, and prove
  one automatic idempotent persistence replay. A pending newer event remains
  coalesced until the retained generation succeeds or reaches a terminal bound.
- `EVAL-PERSIST-RETRY-002` is enforced by the same module. Four total attempts
  use fixed scheduler backoff of 0.1, 0.2, and 0.4 seconds. Duplicate events for
  unchanged bytes do not reset that budget, even when they arrive after the
  active path drains. Exhaustion retains the terminal generation in a bounded
  cache, and shutdown emits filename-only diagnostics.
- `EVAL-PERSIST-RETRY-003` is enforced by the same module. A deterministic
  post-merge read failure leaves the core mission committed, propagates as a
  transient outcome, and replays its RPG and diary effects before processing a
  pending correction with the same natural identity. The correction replaces
  the mission-derived diary and RPG state in the correction transaction.
- `EVAL-PERSIST-RETRY-004` is enforced by
  `woff/tests/test_persistence_retry.py` and
  `woff/tests/test_handler_integration.py`. The startup phase budget includes
  source snapshot stability, the additional Dossier snapshot required by each
  dependent path, four five-second SQLite busy windows, all 0.7 seconds of
  scheduler backoff, and a bounded phase margin. The watchdog consumes that
  calculated budget instead of using only file-stability time.

### Implemented deferred ingestion evals

- `EVAL-DEFER-001` is enforced by
  `woff/tests/test_handler_integration.py` and
  `woff/tests/test_deferred_ingestion.py`. Deterministic concurrent tests admit
  Log, Claims, and Squads before their Dossier, retain the exact verified source
  bytes, and release them only after the matching campaign-root and slot
  identity persists. Duplicate notifications converge to one mission, victory,
  and diary entry while authoritative Dossier statistics remain unchanged.
- `EVAL-DEFER-002` is enforced by
  `woff/tests/test_deferred_ingestion.py`. Dependency work stays inside the
  existing canonical-path scheduler bound and retains at most 64 MiB globally.
  Queued and in-flight dependency replays remain charged to that byte bound.
  Four total attempts and a five-minute lifetime are fixed defaults. Exhaustion,
  expiry, memory saturation, and replay submission failure preserve an accepted
  newer coalesced generation with a fresh budget; shutdown follows the explicit
  cancellation policy. Startup can continue once a dependency is safely
  retained, while the monitor enforces its lifetime. Each admitted path keeps
  one matching resolution epoch across dependency processing and persistence
  backoff, so the race metadata is bounded by scheduler admission. Exhausted
  persistence generations retain only a marker, not snapshot bytes. All terminal
  diagnostics are filename-only, and a transient SQLite failure after dependency
  release continues through the existing persistence policy.

### Implemented canonical temporal evals

- `EVAL-DATE-001` is enforced by calendar, parser, write-boundary, legacy-row,
  campaign-engine, and RPG regressions in
  `woff/tests/test_normalization.py`, `woff/tests/test_xml_parser.py`,
  `woff/tests/test_mission_log_parser.py`,
  `woff/tests/test_temporal_contract.py`,
  `woff/tests/test_rpg_system.py`, and
  `woff/tests/test_campaign_engine.py`, plus initial/runtime filesystem-time
  regressions in `woff/tests/test_stable_snapshot.py`. New missions require a
  real date and, when supplied, a real clock time. Accepted values are stored
  as `YYYY-MM-DD` and `HH:MM`; missing time is `""`. Day-first numeric dates
  are the default, while the confirmed `Mission.log` format is parsed
  month-first explicitly. In flexible campaign XML, a decimal-only generic
  `Time` value is retained as flight duration rather than misclassified as a
  clock; explicit clock fields and clock-shaped generic values still use the
  strict time contract.
  Invalid parser records are rejected and invalid direct writes are quarantined
  with category-only diagnostics.
- `EVAL-DATE-002` is enforced by
  `woff/tests/test_bugfixes_review.py` and
  `woff/tests/test_temporal_contract.py`. Date-dependent reads canonicalize in
  memory without modifying an existing database, exclude rows with invalid
  dates, demote missing or malformed legacy times below known times on the same
  date, and break equal timestamps by mission type, aircraft, sector, source,
  and stable row ID. RPG history is therefore valid-only and newest-first.

`get_pilot_game_date()` returns `None` when neither mission history nor a real
career start date exists. Mission, life, and wingman derived effects reject a
missing game date instead of inventing `1917-01-01`. This issue performs no
schema migration and no cleanup or rewrite of an existing campaign database.
Valid legacy date/time spellings participate in the same in-memory mission
identity during writes and lookups, so a canonical reimport retains the
original row ID without rewriting its stored text. Malformed legacy values are
not assumed to identify a valid incoming mission. Child victories supplied
with that reimport are linked to the retained stored mission ID rather than the
discarded incoming ID. If an incoming mission is quarantined for an invalid
date, invalid time, or ID collision, victories explicitly linked to that
rejected ID are quarantined with it while independent victories remain valid.
Filesystem creation/modification times remain observation metadata and are
never passed to campaign effects as historical game dates. A Dossier wingman
comparison uses the latest stored game date when available; if the career has
none yet, it may use the canonical incoming Dossier start date before the core
merge so that the first dated roster event is not lost.

### Implemented mission merge evals

- `EVAL-MISSION-001` is enforced by
  `woff/tests/test_mission_upsert.py`. Reimport resolves the canonical natural
  identity supplied by Issue #40, updates the existing row in place, retains
  its `missionId`, keeps diary foreign keys valid, remains idempotent, and
  reports inserted, updated, and unchanged records separately.
- `EVAL-MISSION-002` is enforced by
  `woff/tests/test_mission_upsert.py`, with parser provenance checks in
  `woff/tests/test_mission_log_parser.py` and
  `woff/tests/test_xml_parser.py`. Row-level source authority is, from highest
  to lowest: live `mission.log` debrief, XML, historical `PilotNLog.txt`, and
  unknown sources. A lower source may fill an empty or parser-default field but
  cannot replace richer stored data.

The immutable identity fields are `pilotId`, `date`, `time`, `missionType`,
and `aircraft`; a merge also never replaces the stored row ID. Mutable text
fields are `duration`, `altitude`, `sector`, `squadron`, `weather`, `result`,
and `notes`. Blank text never erases stored text, while `Unknown` weather and
`Uneventful` results are treated as parser defaults rather than enrichment.
Positive contact and claim counts may enrich an empty/default count; a same- or
higher-authority source may correct another positive value. Default zero never
erases a positive value. Damage and wound flags are monotonic because current
parser models cannot distinguish an explicit false correction from an absent
field: `True` enriches `False`, while a parser-default `False` never clears
stored evidence. The row retains the highest-authority source observed.

This mission contract changes no schema and rewrites no mission identity field
in an existing campaign database.

### Implemented victory and decoration merge evals

- `EVAL-VICTORY-MERGE-001` is enforced by
  `woff/tests/test_victory_decoration_merge.py` and
  `woff/tests/test_victory_identity_migration.py`. Claims and XML parsers create
  privacy-safe identities from the sanitized source basename plus deterministic
  record position. Schema 3.4 maps each identity to a stable victory row. Two
  same-minute, same-type positions remain distinct, exact replay is idempotent,
  and the migration removes the lossy natural-key constraint without changing
  existing IDs, ownership, data, or mission relationships.
- `EVAL-DECORATION-MERGE-001` is enforced by the same tests. Unambiguous richer
  victory data and decoration date/citation data update the stable row in place.
  Source authority is XML, then `PilotNClaims.txt` or `PilotNDossier.txt`, then
  unknown input. Blank or lower-authority values never erase richer state;
  equal-authority conflicts and ambiguous cross-source occurrence matches are
  preserved as unresolved, category-only diagnostics.

Victory insertion links an otherwise unassociated row only when one positive-
claim mission for the same pilot and canonical date has a compatible start
time. It never rewrites `missions.claimsCount`: that value remains independent
source evidence. A difference between it and the associated victory-row count
is retained and reported as `count-mismatch`. Every batch emits inserted,
updated, unchanged, and unresolved counters. Backup, rollback, integrity,
foreign-key, and reopen evidence covers the 3.3-to-3.4 migration.

### Implemented career identity evals

- `EVAL-IDENTITY-001` is enforced by
  `woff/tests/test_pilot_identity.py`,
  `woff/tests/test_pilot_identity_migration.py`, and
  `woff/tests/test_handler_integration.py`. The tests preserve IDs and every
  covered relationship through schema 3.2, rotate a reused slot to a distinct
  career, reject a partial file observed against a changed Dossier, and prove
  that the old career receives no new fields, mission history, or diary effects.
- `EVAL-IDENTITY-002` is enforced by
  `woff/tests/test_pilot_identity.py`,
  `woff/tests/test_campaign_engine.py`,
  `woff/tests/test_handler_integration.py`, and
  `woff/tests/test_privacy_contracts.py`. The tests keep same-name careers in
  separate slots independent, target derived state by explicit career ID,
  reject identityless XML and `Mission.log` writes, and constrain rejection
  diagnostics to sanitized filename, reason category, and slot.

Same-name replacement in the same pilot slot remains an explicit evidence gap:
without sanitized longitudinal Dossier samples, an equal slot-and-name Dossier
is treated as a replay. The `needs-real-fixture` follow-up does not weaken or
block the verified Issue #70 cases.

### Implemented campaign-root namespace evals

- `EVAL-ROOT-BINDING-001` is enforced by
  `woff/tests/test_campaign_namespace.py`,
  `woff/tests/test_pilot_identity.py`, and
  `woff/tests/test_handler_integration.py`. Equivalent Windows
  spellings map to one privacy-preserving root namespace, distinct roots retain
  independent `(campaign_namespace, slot)` bindings, and Log, Claims, and Squads
  input is routed only to the career in its own root. The corrective regression
  also proves that Root B retains its incoming stable career ID when Root A has
  retired an unbound same-name career in the same slot; subsequent dependent
  input updates only Root B.
  `PilotIdentityEvidence.binding_key` exposes the composite identity for #27's
  future deferred-work key; this issue does not implement the deferred queue itself.
- `EVAL-ROOT-BINDING-002` is enforced by
  `woff/tests/test_pilot_identity_migration.py`. Schema 3.2 bindings migrate
  under verified backup and transaction protection, preserve every covered
  relationship, pass integrity and foreign-key checks, reopen successfully,
  restore after injected failure, and reject ambiguous multi-root ownership.
  Schema 3.1 recovery reuses a legacy career only through the unambiguous binding
  seeded during migration; runtime Dossier processing never claims an unbound
  retired career by global name and slot.

### Implemented pilot status provenance evals

- `EVAL-PILOT-STATUS-001` is enforced by
  `woff/tests/test_pilot_status_merge.py` and
  `woff/tests/test_normalization.py`. The model and parsers use `None` as the
  sole representation of absent status. Log, Claims, Squads, status-free
  Dossier, partial XML, and `Mission.log` therefore never fabricate `Active`;
  repeated partial-source merges preserve both stored status and the six
  numeric statistics governed by Issue #57.
- `EVAL-PILOT-STATUS-002` is enforced by
  `woff/tests/test_pilot_status_merge.py`. Only a Dossier carrying verified
  `PilotIdentityKind.DOSSIER` evidence may write pilot status. An explicit
  `Active`/`In Service` value remains writable, a real transition is persisted,
  and replay produces at most one matching life event. Slot-dependent sources
  cannot replace status even if a future parser accidentally supplies one.

XML and `Mission.log` remain identityless persistence sources under Issue #70.
The XML parser preserves explicit status presence, but neither source can update
a career until a separate verified identity contract exists. A new verified
Dossier with no status stores SQL `NULL`, and a later missing status preserves
the stored value without emitting a status life event. This contract changes no
schema and uses neither `Active` nor an empty string as an absence sentinel.

### Implemented Dossier transaction evals

- `EVAL-DOSSIER-TXN-001` is enforced by
  `woff/tests/test_dossier_transactions.py`. A Dossier application service loads
  the bound pilot and current roster inside the outer transaction, plans all
  narratives before the first write, and then composes pilot, decoration,
  roster, roster-snapshot, and diary writes under that caller-owned boundary.
  Deterministic failures after each core write and on a later diary write prove
  that no new state or earlier diary entry survives. Repository exceptions keep
  their original type, while an explicit Boolean diary rejection aborts the
  generation without acknowledgement.
- `EVAL-DOSSIER-TXN-002` is enforced by
  `woff/tests/test_dossier_transactions.py` and
  `woff/tests/test_stable_snapshot.py`. Retry after rollback reaches the same
  final state as first-attempt success, a completed Dossier digest performs no
  second merge, and both startup and live routing call the same application
  service. The latest non-empty roster is recorded in existing `meta` storage
  inside the same transaction, so a squadron transfer emits neither false
  missing nor mass-arrival events while historical `squad_members`, personality,
  and memory rows remain untouched.

PR #83 introduced an outer transaction around the then-current handler path and
therefore partially reduced the original Issue #72 failure window. It still
loaded some prior state before that transaction, ignored Boolean derived-write
rejections, and split orchestration across handler and campaign methods. Issue
#72 is limited to those remaining gaps. It changes no SQLite schema and leaves
mission-end behavior from Issue #34 unchanged. Issue #37 remains responsible
for the broader roster-generation and truncated-input policy.

### Implemented stable career-selection evals

- `EVAL-CAREER-SELECT-001` is enforced by
  `woff/tests/test_career_selection.py`. Query details, RPG state, missions,
  diary entries, wingmen, and journal exports resolve one persistent
  `pilot_id`; table, JSON, CSV, and Markdown evidence keeps two same-name
  careers in different slots isolated. Pilot listings and selected rows expose
  the stable ID, while a unique display name remains a compatibility selector.
- `EVAL-CAREER-SELECT-002` is enforced by
  `woff/tests/test_career_selection.py`. Ambiguous display names produce a
  deterministic slot-and-ID candidate list and return nonzero before query
  output, journal export, editor launch, backup, or database mutation. The
  editor resolves once and passes that explicit ID through export and import,
  preserving the ownership and verified-backup contract delivered by #26.
  Issue #28 completes the unknown-pilot and valid-empty-output matrix across
  formats, while #75 owns the broader exit-code and stream contract for every
  command failure.

### Implemented query pilot-validation eval

- `EVAL-CLI-001` is enforced by `woff/tests/test_woff_query.py`. An unknown
  persistent pilot ID returns status `2` before output in table, JSON, CSV, and
  Markdown, keeps stdout empty, and writes the diagnostic to stderr. A valid
  pilot with no missions, diary entries, or wingmen returns status `0`; JSON,
  CSV, and Markdown remain valid empty documents without a rendered profile,
  while table output retains its human-readable profile and empty-result
  message.
- The shared career resolver delivered by #93 performs the existence lookup
  before format selection. The command contract delivered by #75 supplies the
  stable exit code and stream separation. Issue #28 adds the dedicated
  cross-format regression matrix without changing production code or schema.

### Implemented command-entry-point evals

- `EVAL-CLI-CONTRACT-001` is enforced by
  `woff/tests/test_command_contracts.py`. Installed `woff-query`,
  `woff-watchdog`, and `woff-report` entry points use status `0` only for
  success, status `1` for runtime failures, and status `2` for invalid input,
  configuration, or missing resources. Query diagnostics stay on stderr;
  watchdog validates watch roots before database creation; parse-file and
  report failures retain their status across subprocess boundaries.
- `EVAL-CLI-CONTRACT-002` is enforced by the same module. Populated and empty
  JSON, CSV, and Markdown query results remain valid selected-format documents,
  report generation preserves zero instead of labelling it missing, and report
  publication plus the optional pre-processing SQLite snapshot are atomic.
  Backup failure preserves the previous verified snapshot. Issue #75 changes no
  schema. Issue #28's unknown-pilot matrix is enforced separately by
  `woff/tests/test_woff_query.py`.

### Implemented retained diary-block eval

- `EVAL-DIARY-EMPTY-001` is enforced by
  `woff/tests/test_woff_editor.py`. Empty and whitespace-only narratives in a
  retained block fail validation with the entry ID before `BEGIN IMMEDIATE`, so
  no row changes and no success message is emitted. The exported instructions
  define this policy and keep complete block removal as the only deletion
  signal. Existing coverage proves selected-pilot deletion, foreign-ID
  rejection, multiline and unchanged narratives, verified pre-import backup,
  and rollback behavior. The correction changes no SQLite schema.

## Active cycle 3.4.0

| Work item | Eval IDs |
|---|---|
| #41 | `EVAL-NUM-001`, `EVAL-NUM-002` |
| #38 | `EVAL-NATION-001`, `EVAL-NATION-002`, `EVAL-NORM-MISSION-001`, `EVAL-NORM-VICTORY-001` |
| #74 | `EVAL-PARSE-SEM-001`, `EVAL-PARSE-SEM-002` |
| #35 | `EVAL-DOSSIER-001`, `EVAL-DOSSIER-002` |
| #37 | `EVAL-ROSTER-001`, `EVAL-ROSTER-002` |
| #44 | `EVAL-XML-001` |
| #43 | `EVAL-NARR-001` |
| #28 | `EVAL-CLI-001` |
| #75 | `EVAL-CLI-CONTRACT-001`, `EVAL-CLI-CONTRACT-002` |
| #76 | `EVAL-RPG-DOMAIN-001`, `EVAL-RPG-DOMAIN-002` |
| #96 | `EVAL-WINGMAN-IDENTITY-001`, `EVAL-WINGMAN-MERGE-001` |
| #97 | `EVAL-DIARY-EMPTY-001` |
| #101 | `EVAL-WINGMAN-TRANSFER-001`, `EVAL-WINGMAN-TRANSFER-002`, `EVAL-WINGMAN-TRANSFER-003` |
| #79 | `EVAL-UI-DESIGN-001` |
| #80 | `EVAL-UI-STATES-001` |
| #81 | `EVAL-UI-CONTRACTS-001` |

Cycle 3.4.0 is `active`. Issues #28, #38, #41, #75, #79, and #97 are complete.
Issue #35 is the next dependency-ordered implementation item, #37 remains
blocked by #35, and #101 remains blocked by #37 and #96.
`EVAL-CYCLE-340-001` aggregates all sixteen members and remains planned until
every member acceptance criterion, applicable eval, and `Q6-CYCLE-3.4.0`
condition passes.

### Implemented exact normalization evals

- `EVAL-NATION-001` and `EVAL-NATION-002` are enforced by
  `woff/tests/test_normalization.py`, `woff/tests/test_dossier_parser.py`,
  `woff/tests/test_xml_parser.py`, and
  `woff/tests/test_mission_log_parser.py`. Known nation aliases use exact
  case-insensitive lookup, unknown explicit values remain unchanged, empty
  values remain empty, and short aliases such as `US` never match inside
  unrelated names such as `Austria` or `Russia`.
- `EVAL-NORM-MISSION-001` is enforced by
  `woff/tests/test_normalization.py`, `woff/tests/test_pilot_data_parser.py`,
  `woff/tests/test_xml_parser.py`, and `woff/tests/test_mission_upsert.py`.
  Mission aliases require token boundaries, the complete `Strafing` alias
  remains supported, and unknown mission text survives PilotLog and XML
  parsing. Replays reproduce every historical substring transition only for
  one canonical same-source row, preserving the stable mission ID and diary
  relationship without a schema change.
- `EVAL-NORM-VICTORY-001` is enforced by
  `woff/tests/test_normalization.py`, `woff/tests/test_pilot_data_parser.py`,
  `woff/tests/test_xml_parser.py`, and
  `woff/tests/test_victory_decoration_merge.py`. Exact victory aliases remain
  canonical while unknown text survives parsing. Legacy OOC replay is limited
  to one compatible same-source row with a validated stable source key, so the
  stable victory identity is preserved without rewriting unrelated records.

### Implemented numeric parsing evals

- `EVAL-NUM-001` is enforced by `woff/tests/test_numeric_parser.py` and
  `woff/tests/test_dossier_parser.py`. Permitted signed values, surrounding
  whitespace, explicit zero, missing input, malformed text, and SQLite integer
  boundaries remain distinct. Signed Dossier reputation values retain their
  value instead of becoming zero.
- `EVAL-NUM-002` is enforced by `woff/tests/test_numeric_parser.py`,
  `woff/tests/test_dossier_parser.py`, `woff/tests/test_xml_parser.py`, and
  `woff/tests/test_pilot_data_parser.py`. Unsigned fields reject negative,
  malformed, non-ASCII, and out-of-range input under explicit field policies.
  PilotLog date and time components remain unsigned, invalid XML counts reject
  only the affected mission, and invalid Dossier values never become an
  authoritative zero. Issue #41 changes no SQLite column type or schema.

## Planned cycle 3.5.0

| Work item | Eval IDs |
|---|---|
| #77 | `EVAL-SCHEMA-CONTRACT-001`, `EVAL-SCHEMA-CONTRACT-002` |
| #48 | `EVAL-DISC-001` |
| #47 | `EVAL-DECODE-001`, `EVAL-DECODE-002` |
| #29 | `EVAL-CATALOG-001` |
| #46 | `EVAL-BLOB-001` |
| #49 | `EVAL-REG-001` |
| #30 | `EVAL-LINT-001` |
| #98 | `EVAL-CATALOG-STABILITY-001`, `EVAL-CATALOG-STABILITY-002` |
| #99 | `EVAL-PILOT-PROVENANCE-001`, `EVAL-PILOT-PROVENANCE-002` |

### Implemented decoder evals

- `EVAL-DECODE-001` is enforced by `woff/tests/test_decode_common.py`. The
  exhaustive valid stream covers every output byte from `0x00` through `0xFF`.
  Dedicated contracts preserve CR/LF handling, empty and repeated delimiters,
  non-hex delimiter behavior, out-of-range rejection, and the shared Dossier,
  squadron decoder, and cataloger call paths.
- `EVAL-DECODE-002` is enforced by the same file. Its synthetic input contains
  `41|` repeated 250,000 times and is allocated before `tracemalloc` starts.
  The assertion compares peak traced bytes with the 750,000-byte encoded input
  and uses no wall-clock threshold. The Q0 baseline on `da133e8` decoded
  250,000 bytes with an 11,327,623-byte peak, or 45.31 bytes per output byte.
  The one-pass decoder measured 522,111 bytes, or 2.09 bytes per output byte,
  a 95.39 percent reduction under the same CPython 3.12 procedure.

Cycle 3.5.0 remains planned. Completing Issue #47 independently does not
activate or approve the aggregate cycle.

## Cross-cutting privacy and security

Issue #65 is a cross-cutting preventive control and is intentionally not added
to the active 3.3.0 functional cycle. Its invariants apply to every future
release once merged.

Local watchdog observation of approved WoFF-generated files is permitted core behavior and is not external telemetry. `External telemetry` means automatic collection followed by transmission outside the user's computer.

| Eval | Work item | Evidence | Enforcement |
|---|---|---|---|
| `EVAL-PRIV-001` | #65 | Persisted configuration and database source define no activation/license credential fields | `woff/tests/test_privacy_contracts.py` |
| `EVAL-LIC-001` | #65 | Registry discovery explicitly permits only `CFS3Path` and queries no activation/license value | `woff/tests/test_privacy_contracts.py` |
| `EVAL-NET-001` | #65 | Core production Python source contains no network-client imports used for external telemetry, tracking, upload, or remote diagnostics; local watchdog monitoring remains permitted | `woff/tests/test_privacy_contracts.py` |
| `EVAL-DISC-PRIV-001` | #65 | Unknown or credential-like text files are metadata-only while known WoFF files retain bounded local preview | `woff/tests/test_privacy_contracts.py` |

These evals implement the human-readable contract in
[`../security/privacy-and-local-data.md`](../security/privacy-and-local-data.md).
A future network feature requires a new tracked decision and explicit governance
changes. It must not silently weaken the activation-credential prohibition.

## Governance eval

`EVAL-GOV-001` requires graph validation to reject missing paths, unmapped
sources, unknown modules, invalid evals, invalid gates, inconsistent satisfied
dependencies, and unknown cycle members. Enforcement lives in
`woff/tests/test_architecture_contracts.py`.

## Eval record requirements

The machine-readable graph is a minimal registry, not the complete execution
record for an eval. Each graph entry defines its ID, owning work items, status,
observable evidence, and, once implemented, its enforcement paths. Planned
evals must not be populated with speculative execution details merely to fill
out a template.

When implementation begins or completion is claimed, the associated issue or
pull request carries the detailed execution record. That record defines the
controlled risk, initial state and input, assertion or metric, test or review
procedure, required gate, and last execution. These extended fields may be
linked to the registry but are not required graph fields.

Fixtures must be synthetic or sanitized. Logs and failure output must not expose
campaign data or personal paths.

## Execution workflow

1. Reproduce the current failure or document preventive evidence.
2. Add the eval or test and confirm the expected failure.
3. Implement the smallest scoped change.
4. Run the focused eval again.
5. Run related tests and applicable gates.
6. Record commands and results in the draft pull request.
7. Update the graph when the eval, dependency, invariant, module, or cycle changes.
