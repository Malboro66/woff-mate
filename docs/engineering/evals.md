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

Issue #50 is the official tracker. The eight functional members remain separate
issues and pull requests.

| Work item | Eval IDs | Required evidence |
|---|---|---|
| #34 | `EVAL-DB-001`, `EVAL-DB-002` | Atomic rollback and caller-owned transactions |
| #57 | `EVAL-PILOT-STATS-001`, `EVAL-PILOT-STATS-002` | Partial-source preservation and authoritative zero writes |
| #45 | `EVAL-CFG-001`, `EVAL-CFG-002` | Early validation and preservation of invalid personal config |
| #36 | `EVAL-SCHED-001`, `EVAL-SCHED-002` | Bounded scheduling and correct move handling |
| #42 | `EVAL-SNAP-001`, `EVAL-SNAP-002` | Exact stable snapshots and bounded Windows retry |
| #40 | `EVAL-DATE-001`, `EVAL-DATE-002` | Canonical validation and deterministic ordering |
| #39 | `EVAL-MISSION-001`, `EVAL-MISSION-002` | Stable identity and non-destructive enrichment |
| #27 | `EVAL-DEFER-001`, `EVAL-DEFER-002` | Deferred reprocessing without loss or unbounded retention |

### EVAL-CYCLE-330-001

The aggregate eval passes only when:

- all eight member issues satisfy their acceptance criteria
- every applicable member eval is implemented and passing
- dependency relations in the graph are satisfied
- focused tests, related tests, the full suite, and Pyright pass
- applicable database, concurrency, and Windows evidence passes
- project graph and public documentation reflect the delivered behavior
- `Q6-CYCLE-3.3.0` passes

Green CI alone does not pass this aggregate eval.

## Independent presentation foundation

Issue #56 is completed documentation and architecture-contract work. It is
intentionally independent of, and is not a member of, the active 3.3.0
reliability cycle. Its applicable gates are Q0 and Q1 only; this record does not
claim Q5 or approval of Product Gate A or Gate B.

| Eval | Work item | Evidence | Enforcement |
|---|---|---|---|
| `EVAL-UI-FOUNDATION-001` | #56 | Proposed toolkit and read-only presentation boundaries are documented, linked, dependency-free, and structurally enforced | `woff/tests/test_architecture_contracts.py` |

### Implemented scheduler evals

- `EVAL-SCHED-001` is enforced by deterministic burst, Windows alias,
  coalescing, saturation, metrics, submission-failure, and shutdown tests in
  `woff/tests/test_ingestion_scheduler.py`.
- `EVAL-SCHED-002` is enforced by destination identity tests in
  `woff/tests/test_ingestion_scheduler.py` and tmp-to-watched/move-away coverage
  in `woff/tests/test_handler_integration.py`.

## Planned cycle 3.4.0

| Work item | Eval IDs |
|---|---|
| #41 | `EVAL-NUM-001`, `EVAL-NUM-002` |
| #38 | `EVAL-NATION-001`, `EVAL-NATION-002` |
| #35 | `EVAL-DOSSIER-001`, `EVAL-DOSSIER-002` |
| #37 | `EVAL-ROSTER-001`, `EVAL-ROSTER-002` |
| #44 | `EVAL-XML-001` |
| #43 | `EVAL-NARR-001` |
| #28 | `EVAL-CLI-001` |

## Planned cycle 3.5.0

| Work item | Eval IDs |
|---|---|
| #48 | `EVAL-DISC-001` |
| #47 | `EVAL-DECODE-001`, `EVAL-DECODE-002` |
| #29 | `EVAL-CATALOG-001` |
| #46 | `EVAL-BLOB-001` |
| #49 | `EVAL-REG-001` |
| #30 | `EVAL-LINT-001` |

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
