# Implementation Plan

Issue: #193
Spec revision: 2
Approved spec commit: `5436c1315592cfe54663c6550642907774a632a8`
Approval bookkeeping commit: `540c33d7e8945d4b9b2dea5806507045596e2d42`
Integrated SDD publication: `2a3cd59d9f6b30f3c9137c6d1138ef4ff9400b7a`
Maintainer approval: https://github.com/Malboro66/woff-mate/issues/193#issuecomment-6241153390
Original Q0 baseline: `28d6e94d732f99a71ac3482490cac3c60d24cacd`
Candidate: Draft PR #198, `integration/184-193-validation`
Pre-reconciliation head: `e561a581d36f73d67e86ed801307479c2ad1f9f0`

## Authority and preserved history

The integrated canonical `spec.md` is `Status: Approved`, `Revision: 2`.
Its approved normative commit is the full SHA above; approver: `mksdpro`.
Revision 2 changes R-01, R-02 and S-03 only; other revision-1
requirements, scenarios, and invariants remain binding and unchanged.

The original approved revision-1 specification is preserved in
`history/revision-1-approved.md` (approval commit
`0d7886faf80933dd07f5a4a533a6859c99438e59`). Its original
implementation `plan.md` and `tasks.md` are preserved byte-for-byte in
`history/revision-1-plan.md` and `history/revision-1-tasks.md`.
Those describe an earlier approved state and are historical evidence, not
current revision-2 authority.

PR #199 published the approved canonical revision 2 on `main`. Its
integration did not merge the separate runtime implementation in PR #198.

## Problem, solution and explicit declaration boundary

`DatabaseManager.close()` releases only the current thread's SQLite
connection. Every SQLite-capable scheduler-managed task, including direct
callers and indirect processing/retry/replay/coalesced work, needs registered
owner-thread release that runs after processing and transaction unwind.

The pre-reconciliation PR #198 implementation:

1. Requires `EventScheduler(sqlite_capability=...)` with either
   `sqlite-capable` or `no-sqlite`. Missing, unknown or invalid declarations
   cause deterministic `ValueError` before executor creation/admission.
2. Requires callable `worker_task_cleanup` for `sqlite-capable`. Production
   `WoFFEventHandler` supplies `db_manager.close`. Worker cleanup executes
   after the task, including exceptions; cleanup failure is observable and
   prevents successful shutdown from masking unreleased resources.
3. Allows legitimate `no-sqlite` work without cleanup. The declaration
   covers all processing and indirect retry/replay callbacks; the scheduler
   does not attempt opaque callback introspection. A caller falsely claiming
   `no-sqlite` violates the binding contract.
4. Preserves bounded admission, retry/replay, coalescing, shutdown drain,
   rollback/commit, integrity and idempotence semantics. No
   `check_same_thread` configuration, schema, or migration changes.

Issue #184 is distinct. Keep `woff/ingestion/snapshot.py` identical to
Draft PR #192 blob `55b10b07cb6dfff22131d4907885468eda89310b`.

## Prior validated evidence (belongs to old exact head)

Previous candidate: `e561a581d36f73d67e86ed801307479c2ad1f9f0`.

- Native Windows Python 3.10.11 full suite:
  2,724 passed, 1 skipped, 179 subtests passed.
- Native Windows Python 3.10.11 / 3.12.8 / 3.13.1 / 3.14.7:
  three independent executions each (12/12 passes), selecting all four
  S-05 handler integration tests plus direct scheduler owner-thread close.
- Focused six-module suite: 216 passed, 10 subtests passed.
- Pyright 0 errors and warnings; graph and diff checks passed.
- Hosted CI https://github.com/Malboro66/woff-mate/actions/runs/39071196209
  and UI Adoption https://github.com/Malboro66/woff-mate/actions/runs/39071196174
  successful at the previous implementation head.
- `main` after PR #199: 5/5 hosted CI checks passed at
  `2a3cd59d9f6b30f3c9137c6d1138ef4ff9400b7a`:
  https://github.com/Malboro66/woff-mate/actions/runs/39075683327.

These records are not evidence that a newly reconciled PR #198 head has
passed. The earlier independent review HOLD was a governance/source
inspection deficit, not a proven new runtime defect.

## Reconciliation, validation and integration controls

- Merge the exact integrated main into the existing PR #198 branch. Resolve
  `spec.md` add/add by preserving the integrated revision-2 file exactly.
  Archive revision-1 plan/tasks before updating the active planning files.
- Verify new `spec.md` against integrated `main` and immutable approved
  commit, including unchanged normative approval payload.
- Inventory every tracked `EventScheduler` construction site and all
  processing, retry and replay callback paths. Confirm that each actual
  `no-sqlite` declaration is truthful, not merely syntactically present.
- Run focused R-01/R-02/S-03 negative and positive tests, owner-thread
  cleanup, transaction rollback, retries/replay and coalescing, and all four
  S-05 native Windows immediate-teardown tests. Run broader tests, Pyright,
  project graph, applicable quality gates, and hosted CI on the new head.
- Independently review the *new* candidate and confirm #184 compatibility,
  SDD convergence, callback truthfulness and exact-head evidence. Only
  after an independent GO request applicable official Codex Review.
- Maintain PR #198 Draft; do not merge it, mark it Ready, close Issue #193,
  modify PRs #192/#196, authorize R1, or approve Product Gates A-D without
  a separate explicit maintainer decision.

## Scope / rollback

The current reconciliation is documentary and provenance-only, preserving
runtime behavior from the previous validated PR #198. Failures at new gates
must be recorded before further implementation or integration decisions.
