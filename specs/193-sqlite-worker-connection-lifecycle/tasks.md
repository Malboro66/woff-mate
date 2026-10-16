# Implementation Tasks

Issue: #193
Spec revision: 1
Approved spec commit: `0d7886faf80933dd07f5a4a533a6859c99438e59`
Plan baseline: `28d6e94d732f99a71ac3482490cac3c60d24cacd`

These tasks are a test-driven implementation sequence for maintainer review.
They are not authorization to start implementation. All items remain
unchecked.

## Tasks

- [ ] T01 — Add the failing owner-thread lifecycle regression before production changes.
  - Add a synthetic scheduler/handler regression using a temporary SQLite
    database. Capture the worker thread identity and explicit
    `Connection.close()` call. Assert the close call occurs on the same owner
    thread before the scheduled task completes and shutdown returns; immediate
    directory removal is an additional assertion, not a substitute for
    explicit-close observation.
  - Make the regression fail against the uncorrected implementation and pass
    after the Issue #193 fix. Its close-call assertion must fail on Python 3.10
    even if that runtime automatically releases the SQLite handle; do not use
    file deletion alone as the regression oracle.
  - Reproduce against exact baseline `28d6e94d732f99a71ac3482490cac3c60d24cacd`
    on native Windows Python 3.12–3.14; retain Python 3.10 as the passing
    compatibility control. Record the owner-thread-close control. Do not claim
    a fresh reproduction unless physically run.
  - Map: R-01, R-02, R-06, R-07; S-01, S-03, S-05, S-06.
  - Validation: focused regression fails on the expected missing owner-thread
    close before production changes; physical Windows result recorded by
    runtime and exact baseline SHA.

- [ ] T02 — Add per-task owner-thread cleanup and wire handler ownership.
  - Add the smallest scheduler finalizer boundary around the complete `_run()`
    worker task and supply `DatabaseManager.close` from `WoFFEventHandler`.
    Ensure cleanup runs after callback/transaction unwinding on success and
    exception paths; keep `check_same_thread=False` and all admission,
    coalescing, retry, replay, and acknowledgement behavior unchanged.
  - Map: R-01, R-02, R-03, R-07, R-08; S-01, S-02, S-03.
  - Validation: T01 passes; scheduler shutdown still drains accepted work and
    the worker's explicit close is observed on the same thread that opened the
    connection.

- [ ] T03 — Make cleanup failures observable without masking processing errors.
  - Record/log worker cleanup failure so that executor futures cannot hide it;
    complete the normal drain and monitor join, then make scheduler/handler
    shutdown observably fail. Preserve the original processing or persistence
    error and do not commit during cleanup.
  - Add injected cleanup-failure and processing-failure coverage, including
    rollback-before-close and no success-shaped shutdown result.
  - Map: R-02, R-03, R-05; S-02, S-03, S-04.
  - Validation: focused failure tests prove primary errors remain observable,
    cleanup failure is separately visible, rollback completes first, and
    shutdown does not report success when release fails.

- [ ] T04 — Cover replay, retry, coalescing, transaction composition, and reopen.
  - Exercise initial/live work, multiple events on a reused worker, coalesced
    reruns, transient persistence retry, dependency replay, and graceful
    shutdown using existing scheduler/handler fixtures.
  - Reuse and extend transaction regressions only as needed to verify successful
    commit, failed rollback, nested/rollback-only behavior, foreign keys,
    integrity, idempotence, and closing/reopening the synthetic database.
  - Map: R-03, R-04, R-05, R-07; S-01 through S-04.
  - Validation: focused scheduler, handler, transaction, and database tests
    pass; accepted processing is neither dropped nor duplicated and each
    completed worker task closes its own connection.

- [ ] T05 — Verify all four integration cases and immediate teardown.
  - Run the four exact S-05 cases without changing their functional
    expectations: `test_all_dependent_sources_converge_after_dossier_without_duplicates`,
    `test_file_modified_event`,
    `test_log_received_before_dossier_is_replayed_after_identity_persists`, and
    `test_startup_wait_settles_while_missing_dossier_is_retained`.
  - Keep teardown direct: handler shutdown, main-thread close, then immediate
    temporary-directory removal; add no GC, sleeps, retries, or exclusions.
  - Map: R-04, R-06, R-08; S-05.
  - Validation: selected four-case pytest run passes and each test removes its
    temporary DB directory immediately on the tested Windows runtimes.

- [ ] T06 — Retain hosted Windows regression coverage.
  - Add selectors for all four S-05 integration tests and the deterministic
    owner-thread regression introduced in T01 to the existing hosted Windows
    Python 3.10 job in `.github/workflows/ci.yml`. The new regression must
    assert explicit close on the opening worker thread independently of
    automatic SQLite-handle release; do not represent hosted evidence as
    physical-machine validation.
  - Map: R-01, R-06, R-08; S-01, S-05.
  - Validation: the updated GitHub Windows 3.10 job passes all four S-05 tests
    and the T01 regression; the regression fails on uncorrected code and passes
    after the fix. Existing hosted Linux full-suite jobs remain green on
    Python 3.10 and 3.14.

- [ ] T07 — Complete physical Windows and revision-bound reproduction evidence.
  - On a physical Windows machine, run the four S-05 cases and the
    deterministic lifecycle/owner-close procedure under native Python 3.10,
    3.12, 3.13, and 3.14. Record exact patch versions, OS/build, filesystem,
    commit, commands, and immediate cleanup results separately from hosted CI.
  - Compare the same S-06 procedure on the exact `main` baseline, immutable
    PR #192 head, and implementation candidate; identify teardown failures
    separately from snapshot assertions. Do not change PR #192.
  - Map: R-01, R-02, R-06, R-08; S-05, S-06.
  - Validation: revision-bound sanitized evidence has one result per physical
    runtime and comparison target, includes the owner-thread-close control,
    and does not publish private paths or raw campaign data.

- [ ] T08 — Run the complete repository validation and review scope.
  - Run focused and full tests, Pyright, project-graph validation,
    architecture-contract tests, `git diff --check`, and applicable CI.
    Review the complete diff and check lifecycle failure paths, accepted-work
    semantics, transaction boundaries, Windows cleanup, and spec convergence.
  - Map: R-01 through R-08; S-01 through S-06.
  - Validation:
    `python -m pytest woff/tests/test_ingestion_scheduler.py woff/tests/test_handler_integration.py woff/tests/test_composable_transactions.py woff/tests/test_database_manager.py -q`;
    `python -m pytest -q`;
    `pyright`;
    `python scripts/validate_project_graph.py`;
    `python -m pytest woff/tests/test_architecture_contracts.py -q`;
    `git diff --check`.
  - Report hosted and physical Windows results separately; do not claim native
    Python 3.11 evidence.

## Requirement and scenario mapping

| Approved item | Implementing tasks | Regression/evidence |
| --- | --- | --- |
| R-01 — Owner-thread closure | T01, T02, T04, T06, T07 | Explicit close-call and worker identity assertions independent of automatic handle release; hosted regression, S-01, S-03, S-05 |
| R-02 — Shutdown resource boundary | T01–T03, T07 | Accepted-work drain, cleanup failure surfaced, handler shutdown; S-03 |
| R-03 — No close during active transaction | T02–T04 | Injected exception, rollback-before-close, nested transaction regressions; S-02, S-04 |
| R-04 — Every background outcome | T04, T05 | Initial/live, exception, retry, dependency replay, coalescing, graceful shutdown; S-02, S-03, S-05 |
| R-05 — Persistence semantics | T03, T04 | Commit, rollback, rollback-only, FK/integrity, idempotence, close/reopen; S-02, S-04 |
| R-06 — Immediate temporary-DB removal | T01, T05–T07 | Four named integration cases plus explicit-close regression; direct removal without GC/timing workaround; S-05 |
| R-07 — Preserve thread/scheduler policy | T02, T04 | Assert unchanged connection config, bounded admission, retries, replay and ack semantics; S-01, S-03 |
| R-08 — Compatibility and scope | T05–T08 | Python 3.10 and 3.12–3.14 Windows matrix, hosted Windows 3.10 includes four integration tests and explicit-close regression, Linux suite, no schema change; S-05, S-06 |
| S-01 — Successful work | T01, T02, T04, T06 | Owner close on success with committed result readable after reopen; explicit-close regression runs in hosted Windows Python 3.10 |
| S-02 — Failure rollback | T02–T04 | Original exception visible, rollback before owner close, no partial commit |
| S-03 — Shutdown drain and resource release | T01–T04, T07 | Normal/retry/replay/coalesced work settles; cleanup failure makes shutdown fail |
| S-04 — Composition and reopen | T03, T04, T08 | Existing and added transaction tests, foreign-key/integrity checks, idempotent replay |
| S-05 — Windows teardown | T05–T07 | All four exact integration test IDs on physical Windows 3.10/3.12/3.13/3.14; hosted Windows 3.10 runs all four plus the explicit owner-thread-close regression separately |
| S-06 — Defect isolation | T01, T07 | Exact main/PR #192/candidate comparison and owner-close control; teardown distinguished from snapshot assertions |

## Adjacent findings

Keep #29's raw cataloger connection centralization, #145's validation-tooling
work, #184/PR #192 snapshot behavior, and unavailable raw Q0 artifacts as
separate concerns. Do not implement those adjacent issues in this work.

## Completion evidence

To be filled only after a separately authorized implementation. These planning
tasks do not authorize production or test changes, a branch/PR operation, or
issue completion.
