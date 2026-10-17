# Implementation Plan

Issue: #193
Spec revision: 1
Approved spec commit: `0d7886faf80933dd07f5a4a533a6859c99438e59`
Approval bookkeeping commit: `2694d8fdab9a6a3e06481975ef15a84895bbaeb6`
Baseline: `28d6e94d732f99a71ac3482490cac3c60d24cacd`
Branch: `spec/193-sqlite-worker-connection-lifecycle`

## Preconditions and verified state

- `spec.md` is `Status: Approved`, `Revision: 1`; its `Approved revision` is
  `1`, its approved spec commit is the full SHA above, `Approved by` is
  `mksdpro`, and the direct approval evidence is
  [the maintainer's Issue #193 comment](https://github.com/Malboro66/woff-mate/issues/193#issuecomment-6182061636).
  The comment author is `mksdpro` and explicitly approves the specification
  path, revision, and full commit SHA.
- The specification path has no staged or unstaged changes. Its committed
  content at the current `HEAD` and at the approved spec commit was strictly
  decoded as UTF-8, normalized only for CRLF/CR line endings, and compared by
  the SDD approval-payload rule. The stable metadata plus `Problem` through
  `Open questions / evidence gaps` are byte-for-byte equal after that
  normalization. The payloads were both 17,176 UTF-8 bytes.
- The configured remote is `origin`
  (`https://github.com/Malboro66/woff-mate.git`). `git ls-remote` and local
  remote-tracking refs agree: `origin/main` is
  `28d6e94d732f99a71ac3482490cac3c60d24cacd`; the existing local branch and
  `origin/spec/193-sqlite-worker-connection-lifecycle` are both
  `2694d8fdab9a6a3e06481975ef15a84895bbaeb6`. The worktree was clean before
  these planning artifacts were created.
- `origin/main` is the approved baseline. A source comparison confirmed that
  the affected production and test paths on this branch match `origin/main`;
  the branch delta from `main` is the specification and its approval
  bookkeeping only.
- Issue #193 is open. Related-work disposition remains distinct: #29 is open
  and addresses raw cataloger connections (and remains blocked on #98 in the
  project graph); #145 is closed with PR #150 merged and addressed Windows
  validation tooling; #184 is open and PR #192 is still a Draft with base
  `28d6e94d732f99a71ac3482490cac3c60d24cacd` and head
  `9a9a7a2a89248415c0191076b4fd377183b05b52`. The published Q0 evidence
  attributes the connection leak to both the baseline and that comparator.
- The Q0 evidence is the existing native-Windows reproduction record on
  Issue #193. It reports Windows 10 Pro/NTFS and Python 3.10, 3.12, 3.13, and
  3.14 outcomes, including an owner-thread-close control. Its original scripts
  and raw JSON are not attached to the issue, and the exact per-test,
  per-version result table is unavailable. This plan does not claim to have
  rerun that physical reproduction.
- `docs/architecture/project-graph.yaml` assigns `woff/database.py` to
  persistence, `woff/ingestion/scheduler.py` to ingestion, and `woff/handler.py`
  to application. It has no Issue #193 entry. Existing database and scheduler
  evaluation coverage includes EVAL-DB-001/002 and EVAL-SCHED-001/002; Q1 and
  Q3 apply. No new dependency on #29, graph relationship, eval, or gate is
  inferred here. Project-graph validation remains a required check.
- The applicable repository requirements are Python 3.10 compatibility,
  relative imports inside `woff`, synthetic database fixtures, no schema
  changes, transaction/integrity/reopen safety, bounded event admission and
  shutdown, and no changes to R1 or Product Gates A–D.

## Current architecture and evidence

- `DatabaseManager._get_conn()` stores one connection in
  `threading.local()` and recreates it when closed. `_open_conn()` explicitly
  retains `check_same_thread=False`, WAL, and foreign-key enforcement.
  `DatabaseManager.close()` closes only the calling thread's connection.
- `DatabaseManager.transaction()` composes nested work with thread-local depth
  and rollback-only state. The outer scope commits on success and rolls back
  failures; failed rollback/commit paths preserve the primary error and may
  discard an uncertain connection. Existing transaction semantics must remain
  authoritative.
- `EventScheduler._run()` invokes the initial, coalesced, persistence-retry,
  and dependency-replay processing callbacks within a worker task. It catches
  processing exceptions and logs them before settling scheduler state. A pool
  worker may be reused for later `_run()` tasks.
- `EventScheduler.shutdown()` stops admission, applies the existing deferred
  dependency and retry shutdown policy, waits for executor work, and joins the
  dependency monitor. It currently has no worker-connection finalizer.
- The dependency monitor expires or cancels in-memory deferred states; its
  current loop does not use `DatabaseManager`. The scheduler's vacancy check is
  also an in-memory processor map, not a database query.
- `WoFFEventHandler` supplies the processing/replay callbacks to the scheduler;
  its `shutdown()` delegates to `scheduler.shutdown()`. This is the narrow
  integration point for supplying the database manager's existing
  caller-thread `close()` operation as worker cleanup.
- `TestHandlerIntegration.tearDown()` shuts the handler down, closes the
  test-thread connection, then removes the temporary directory. The four
  acceptance cases are the exact test identifiers in S-05. The Q0 record says
  that on Windows 3.12–3.14 the workers have stopped and no transaction is
  active, but a worker connection remains open until garbage collection.

## Technical approach

Add a scheduler-owned worker-task cleanup callback, supplied by
`WoFFEventHandler` as `db_manager.close`. Invoke it in a `finally` boundary
around the complete `_run()` task, after all processing/retry/replay callbacks
and their transaction contexts have returned or unwound. A worker therefore
closes its own thread-local connection after each complete scheduled task,
including exceptional exits; it does not wait for a pool thread to terminate
or depend on a thread-pool private hook. A worker reused for a later task starts
with no prior task connection.

Make cleanup failures observable rather than relying on an unobserved
`ThreadPoolExecutor` future exception: record and log the failure in
thread-safe scheduler state, finish the existing executor/monitor shutdown
sequence, then raise an explicit shutdown failure. Handler shutdown continues
to propagate scheduler failure. Preserve the original processing/persistence
error and rollback behavior; cleanup must not commit, replace the primary
failure with a success-shaped result, or make shutdown appear successful when
the resource guarantee failed.

Keep the existing admission, coalescing, retry, dependency, acknowledgement,
and shutdown policies intact. The callback surrounds the full worker task, not
an individual retry attempt, so it cannot close a connection between steps of
one accepted task. Existing transaction context managers must finish their
commit/rollback before the callback closes the connection. Keep
`check_same_thread=False` and all cross-thread policy unchanged. No
cross-thread connection registry or connection close from the handler/main
thread is proposed. Because the current dependency monitor does not access
SQLite, it needs no database finalizer; shutdown must nevertheless continue to
join it before returning.

The expected production change is limited to the scheduler callback/finally
and its handler wiring. `DatabaseManager.close()` already implements
caller-thread closure and is not expected to change unless focused tests show a
specific error-reporting defect in that method.

## Connection ownership and cleanup boundaries

| Work | Connection owner | Cleanup boundary |
| --- | --- | --- |
| Initial/live ingestion, coalesced processing, persistence retry, dependency replay | Executor worker executing `_run()` | `finally` after the entire task and its transaction contexts settle |
| Main-thread assertions and test setup/teardown | Test/main thread | Existing explicit `db.close()` in teardown |
| Dependency monitor | Monitor thread; currently no SQLite use | Existing monitor join; do not add unrelated connection management |

Successful scheduler shutdown must wait for every accepted executor task's
owner-thread cleanup and for the dependency monitor join. If any owner cleanup
fails, the drain still completes as far as possible but shutdown reports
failure explicitly.

## Error-handling and shutdown strategy

1. Preserve `_run()`'s current exception reporting and scheduler state
   transitions.
2. Run owner-thread cleanup on all task exit paths, including processing
   exceptions and unexpected scheduler-task errors.
3. Preserve transaction context behavior: commit only on the established
   success path, roll back on failure, and do not close during active work.
   Cleanup never commits. Existing primary processing/persistence exceptions
   remain visible; cleanup failures are separately logged and latched.
4. Keep shutdown ordering: stop admission and retain current deferred/retry
   policy, wait for executor tasks (including their finalizers), join the
   dependency monitor, then raise if any cleanup failed. Return normally only
   when the resource-release guarantee holds.
5. Keep `WoFFEventHandler.shutdown()` as a delegating boundary and allow any
   scheduler cleanup failure to propagate to its caller.

## Compatibility, persistence, and data safety

- Preserve Python 3.10 and supported Windows Python 3.12–3.14 behavior;
  continue to run meaningful Linux coverage.
- Preserve the exact `check_same_thread=False` setting, connection
  thread-locality, WAL, foreign keys, busy-timeout, locks, transaction
  composition, rollback-only handling, persistence retry, idempotence, and
  error propagation.
- Do not close a worker connection between callbacks/retries in one `_run()`
  task or during an active transaction.
- Use only synthetic temporary databases. Do not read, modify, or publish
  campaign data, private paths, credentials, or unsanitized probe output.
- No schema, migration, dependency, snapshot, UI, parser, or product-gate
  change. No backup or migration procedure is applicable because persistent
  data and schema are not changed.

## Risks and rollback strategy

- **Premature close:** a finalizer at callback-attempt granularity could
  interrupt an accepted retry/replay. Keep it around the complete `_run()`
  task and test multi-attempt paths.
- **Masked failures:** executor futures are not surfaced by `shutdown()`.
  Explicitly latch cleanup failures and test that shutdown raises after
  draining; preserve the processing error in its existing reporting path.
- **Transaction interference:** close only after the processing callback has
  returned or unwound its existing transaction context; prove commit, rollback,
  nested rollback-only, integrity, and reopen behavior.
- **Shutdown semantics:** cleanup must not change bounded admission, accepted
  event settlement, dependency retention, or existing retry cancellation at
  shutdown. Use scheduler tests to detect changes.
- **Windows file handles:** test immediate deletion directly; do not add GC,
  retries, sleeps, or teardown workarounds.
- **Rollback:** if implementation validation fails, revert only the reviewed
  Issue #193 scheduler/handler/test/CI changes through the normal reviewed
  branch workflow. There is no schema or campaign-data state to restore.

## Validation approach and regression matrix

The first implementation change must be preceded by a deterministic failing
regression on the approved baseline. Use a synthetic worker event that opens a
real temporary SQLite connection and records the worker identity and explicit
`Connection.close()` call. The regression must assert that the close call
occurs on the same owner thread before the scheduled task completes and
shutdown returns; immediate directory removal is an additional assertion, not
a substitute for observing explicit closure. This makes the regression fail
against the uncorrected implementation even on Python 3.10, where the SQLite
handle may be released automatically, and pass only after Issue #193's
owner-thread cleanup is implemented. Run without GC, retries, or arbitrary
sleeps. Repeat the documented Q0 lifecycle procedure on immutable
baseline/comparator checkouts and the implementation candidate for S-06; do
not edit PR #192.

Run the four S-05 `TestHandlerIntegration` cases exactly:

- `test_all_dependent_sources_converge_after_dossier_without_duplicates`
- `test_file_modified_event`
- `test_log_received_before_dossier_is_replayed_after_identity_persists`
- `test_startup_wait_settles_while_missing_dossier_is_retained`

Each must retain its functional assertions and immediately remove its
temporary database directory during teardown. Also exercise worker success,
processing/transaction failure, cleanup failure, nested/rollback-only
transactions, foreign-key/integrity checks, database reopen, and repeated
idempotent processing.

| Validation environment | Required coverage | Evidence distinction |
| --- | --- | --- |
| Physical Windows, native Python 3.10, 3.12, 3.13, and 3.14 | All four S-05 tests and the deterministic lifecycle/owner-close control; immediate temporary-directory removal. Record exact Python patch version, OS/build, filesystem, commit, command, and result for each runtime. | Maintainer-controlled physical-machine results; not inferred from hosted CI. |
| Hosted GitHub Windows job, Python 3.10 | Run all four S-05 tests and the T01 deterministic owner-thread regression in the existing Windows job. The regression must assert an explicit close call on the opening worker thread independently of automatic handle release. | Hosted Windows runner is not the physical-machine evidence required for 3.12–3.14. |
| Hosted Linux CI, Python 3.10 and 3.14 | Existing full pytest matrix and focused tests; Linux results remain meaningful but do not establish Windows file-lock behavior. | Hosted Linux evidence only. |
| Exact baseline/comparator/candidate lifecycle probe | Reproduce against baseline `28d6e94d732f99a71ac3482490cac3c60d24cacd`, PR #192 head `9a9a7a2a89248415c0191076b4fd377183b05b52` read-only, and the implementation candidate. Include the owner-thread-close control and identify teardown versus snapshot assertions. | Revision-bound physical evidence; no PR #192 modification. |

Focused validation should include the T01 owner-thread regression and
`woff/tests/test_ingestion_scheduler.py`,
`woff/tests/test_handler_integration.py`, and the existing
`woff/tests/test_composable_transactions.py` / database tests. Run the
four S-05 cases plus the T01 regression in the hosted Windows Python 3.10 job.
Before implementation completion run
`python -m pytest -q`, `pyright`,
`python scripts/validate_project_graph.py`,
`python -m pytest woff/tests/test_architecture_contracts.py -q`, applicable
privacy/security checks if scope changes, and `git diff --check`. Report
physical and hosted results separately; do not claim an unmeasured Windows
Python 3.11 result.

## Expected implementation files

Primary expected changes:

- `woff/ingestion/scheduler.py` — per-task worker cleanup and observable
  cleanup failure handling.
- `woff/handler.py` — wire `DatabaseManager.close` as the scheduler's cleanup
  callback.
- `woff/tests/test_ingestion_scheduler.py` — worker ownership, cleanup on all
  exits, shutdown failure, and unchanged drain/coalescing behavior.
- `woff/tests/test_handler_integration.py` — lifecycle regression and
  four-case functional/immediate-teardown coverage.
- `woff/tests/test_composable_transactions.py` — add only if a focused worker
  transaction/reopen regression cannot be expressed in the scheduler or
  handler tests; existing transaction tests must still pass.
- `.github/workflows/ci.yml` — run the four named S-05 integration cases and
  the T01 deterministic owner-thread-close regression in the existing hosted
  Windows Python 3.10 job.

`woff/database.py` is not expected to change: its current `close()` is
thread-local and `_open_conn()` already preserves the mandated SQLite
configuration. Do not change `spec.md`, the project graph, schema/migrations,
R1, Product Gates A–D, PR #192, or Issue #194.

## Alternatives rejected

- Closing a registry of worker connections from the handler/main thread:
  violates the approved owner-thread lifecycle even though
  `check_same_thread=False` is configured.
- Changing `check_same_thread`, permitting broader cross-thread access, or
  relying on SQLite's disabled affinity check: explicitly outside R-01/R-07.
- Depending on executor private thread hooks, garbage collection, finalizers,
  process exit, or a global connection registry: not a reliable, minimal
  owner-thread boundary and unnecessary for the existing `_run()` task
  lifecycle.
- Closing after each individual retry/replay callback: risks closing while
  the same accepted `_run()` task is still processing.
- Weakening test teardown with sleeps, retries, `gc.collect()`, or exclusions:
  hides rather than fixes the handle leak and violates R-06.
- Changing scheduler admission, acknowledgement, dependency, or retry policy:
  unrelated to connection release and prohibited by R-02/R-07.

## Contradictions or unresolved evidence gaps

No contradiction was found between the Approved behavior and the current
baseline architecture. The Q0 raw producer scripts and JSON output remain
unavailable in the issue, so per-test/per-version pre-fix results cannot be
independently audited from those artifacts in this session. Preserve that
limitation in the implementation evidence; obtain sanitized artifacts from
their authorized producer or recreate the deterministic procedure without
claiming access to the missing files. Native Python 3.11 was not measured.

## Scope exclusions

No Issue #193 production implementation, test edit, CI edit, PR, merge, schema
change, migration, campaign-data operation, PR #192 modification, Issue #194
work, R1 change, Product Gates A–D change, or Codex Review is authorized by
this planning artifact. These documents do not authorize implementation.
