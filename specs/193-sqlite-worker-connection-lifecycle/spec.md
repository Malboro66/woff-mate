# Specification

Issue: #193
Status: Draft
Revision: 2
Baseline: 28d6e94d732f99a71ac3482490cac3c60d24cacd
Owner: maintainer

## Problem

`DatabaseManager` keeps SQLite connections in thread-local state, while its
`close()` method closes only the connection belonging to the calling thread.
The ingestion scheduler waits for accepted work during shutdown but does not
ensure that connections opened by its worker threads have been closed by those
threads. On native Windows, completed integration-test teardown can therefore
fail to delete its temporary database even though no worker remains active.

This is a pre-existing SQLite connection-lifecycle defect. It is separate from
the stable-snapshot correction in Issue #184 / Draft PR #192.

## Goal

After background ingestion has stopped, every SQLite connection owned by its
worker threads is explicitly closed on its owning thread at a safe lifecycle
boundary. When `shutdown()` returns, no connection owned by completed worker
processing prevents immediate removal of a temporary database directory.

## Current evidence

The Q0 evidence is the native-Windows reproduction comment on Issue #193. It
was produced by a separately authorized Windows investigation and records:

- Exact integrated `main` baseline: `28d6e94d732f99a71ac3482490cac3c60d24cacd`.
  The GitHub `main` reference and PR #192 base resolve to this same commit.
- Comparator: Draft PR #192 head
  `9a9a7a2a89248415c0191076b4fd377183b05b52`.
- Environment: Windows 10 Pro build 19045.6466, NTFS, CPython 3.10.11,
  3.12.8, 3.13.1, and 3.14.7.
- Procedure: the original `probe.py` imports production `DatabaseManager` and
  `EventScheduler` from disposable detached checkouts, creates a synthetic
  temporary SQLite database, admits a scheduler event, opens and uses a
  worker-owned connection, shuts down the scheduler, closes the main-thread
  connection, and attempts immediate directory removal before garbage
  collection. It observes connection ownership and explicit closes, worker
  liveness, transaction state, and Windows sharing violations. The procedure
  runs default, GC-disabled, and owner-thread-close control modes, as well as
  four `TestHandlerIntegration` teardown cases. The published Q0 comment
  describes these cases but does not provide their complete identifier list.
- The four test identifiers associated with the original
  `probe.py`/`run_native.py`/`rerun_base_v2.py` investigation and its JSON
  evidence are listed in S-05. Their exact spelling has been verified against
  `woff/tests/test_handler_integration.py`. This identifier list's provenance
  is the original investigation evidence as supplied for this specification
  review, not a verbatim list contained in the published Q0 comment.
- The recorded result is that Windows Python 3.10 cleanup succeeds, while
  Python 3.12–3.14 reports `WinError 32` on both base and candidate. At the
  failure point, no worker remains alive, but a SQLite connection remains
  open without an active transaction. Garbage collection later releases it;
  explicitly closing it on its owner thread permits immediate removal. The
  candidate snapshot assertions pass; the observed failures occur in teardown.
- Revision preparation records exact detached SHA checkouts verified with
  `git rev-parse HEAD`; `run_native.py` creates isolated per-version virtual
  environments and invokes the original probe. `rerun_base_v2.py` repeats the
  corrected observer against the base to correct an earlier misleading base
  attribution.
- Relevant production and test locations are
  `woff/database.py` (`DatabaseManager._get_conn()` and `close()`),
  `woff/ingestion/scheduler.py` (`EventScheduler.shutdown()`),
  `woff/handler.py` (`WoFFEventHandler.shutdown()`), and
  `woff/tests/test_handler_integration.py` (`TestHandlerIntegration.tearDown()`).
- The comment identifies the original producer scripts
  (`probe.py`, `run_native.py`, `rerun_base_v2.py`) and sanitized result files
  (`investigation-results.json`, `base-observer-v2-results.json`), including
  their recorded creation intervals. It states that the original scripts and
  JSON files were re-opened read-only by the authorized producer on 2026-10-15.
  These raw artifacts are not attached or otherwise accessible in the issue;
  this specification relies on the published reproduction record and
  preserves that audit limitation below.
- The issue's initial historical review distinguishes #193 from open Issue
  #29, which concerns catalogers' direct SQLite connections, and closed Issue
  #145 / merged PR #150, which addressed native validation tooling. Issue
  #184 / PR #192 concerns snapshot acquisition; the recorded candidate
  comparison does not attribute this teardown failure to that change.

The evidence location and producer are the Q0 reproduction comment on Issue
#193, authored by a repository collaborator and describing a maintainer-
authorized native-Windows investigation. This specification consumes that
published record; it does not claim to have executed the reproduction or
independently inspected its unavailable raw output files.

Current code paths inspected at the recorded baseline show thread-local
connections and caller-thread-only `DatabaseManager.close()`, scheduler
shutdown waiting for workers and the dependency monitor, handler delegation to
scheduler shutdown, and integration teardown removing the temporary directory
after closing only the main-thread connection.

## Required behavior

### R-01 — Close worker-owned connections on their owner thread

Every SQLite connection opened by background ingestion must be explicitly
released by its owning thread at a safe lifecycle boundary. Closing a
connection from another thread is not a substitute. Here, ownership describes
the logical lifecycle responsibility for using and closing a connection; it
does not assert SQLite's runtime thread-affinity check is enabled.

The current connection configuration uses `check_same_thread=False`. Issue
#193 does not authorize changing that setting or broadening cross-thread
connection usage. The correction must guarantee deterministic connection
release through the established ownership model and preserve the existing
cross-thread connection policy.

The owner-thread release obligation applies to any `EventScheduler` configuration whose scheduler-managed work may acquire a SQLite connection, including direct scheduler callers outside `WoFFEventHandler`. Before the first admission, each scheduler configuration MUST explicitly declare whether scheduler-managed work **may access SQLite** (`SQLite-capable`) or **cannot access SQLite** (`no-SQLite`). The declaration covers all processing, retry and replay callbacks that can execute on scheduler-managed worker threads, including indirect calls. Omission or an unknown declaration MUST NOT be interpreted as `no-SQLite`.

A `SQLite-capable` configuration MUST register a deterministic owner-thread release mechanism before admitting any work. The registered mechanism MUST run on the worker that owns the connection, after the entire task and all active transactions have completed through the existing commit or rollback paths. An explicitly declared `no-SQLite` configuration MAY omit a SQLite cleanup callback, but its worker callbacks MUST NOT open or use SQLite connections. The scheduler MUST NOT attempt to compensate for absent cleanup by closing a worker's connection from another thread. The existing `check_same_thread=False` setting and cross-thread policy are unchanged.

### R-02 — Shutdown is a resource-lifecycle boundary

A scheduler MUST validate its explicit SQLite capability declaration and, for a `SQLite-capable` configuration, the presence of an owner-thread release mechanism **before accepting any work**. If the declaration is missing, invalid or `SQLite-capable` without an appropriate release mechanism, the scheduler MUST fail closed during configuration or reject admission **before dispatch**. This failure MUST be deterministic and observable to the caller; it MUST NOT be reported as successful acceptance, successful processing or successful shutdown of rejected work. Already accepted work MUST NOT be silently discarded to enforce the contract.

For an explicitly declared `no-SQLite` configuration, SQLite cleanup registration is not required and existing non-SQLite scheduling behavior remains available. Such a declaration is a binding contract about the work supplied by the caller; it is not a claim that the scheduler can infer or inspect arbitrary callback internals. A caller that declares `no-SQLite` but permits its callbacks to acquire SQLite violates the configuration contract and cannot claim the R-01/R-02 resource guarantee.

When `EventScheduler.shutdown()` and the delegating handler shutdown return successfully for correctly configured work, all accepted work and dependency-monitor activity have finished, and no SQLite connection owned by completed scheduler-managed work remains open. Registered cleanup MUST run on the owning worker after work and transaction unwinding, including exceptional paths. A cleanup failure MUST remain observable under repository-standard reporting, and shutdown MUST NOT return successfully while an owned connection is known to remain unreleased. Shutdown MUST preserve existing bounded admission, coalescing, retry/replay and work-drain behavior.

### R-03 — Close only outside active transactions

A connection must not be closed while its owner is executing an active
transaction. Processing must first complete the existing commit or rollback
behavior. A processing failure must not turn cleanup into a commit, suppress
the original processing/persistence error, or leave the connection open.

### R-04 — Cover every background processing outcome

The lifecycle guarantee applies to initial and live ingestion, successful
processing, exceptions and aborted processing, transient persistence retry,
dependency replay, coalesced events, and graceful shutdown. Reuse of a worker
for multiple events must not leave a connection behind when the worker's
lifecycle ends.

### R-05 — Preserve persistence semantics

Connection cleanup must not lose or duplicate committed data and must preserve
successful commits, failure rollback, nested and rollback-only transaction
behavior, foreign-key enforcement, integrity, and idempotent replay. The
database must remain closeable and reopenable after processing and cleanup.

### R-06 — Immediate temporary-database cleanup

After shutdown and closure of the test's main-thread connection, each affected
`TestHandlerIntegration` case must be able to remove its temporary database
directory immediately on supported Windows runtimes, without garbage
collection, retry loops, arbitrary sleeps, or blanket test exclusions.

### R-07 — Preserve thread ownership and scheduler behavior

Do not solve this defect by changing `check_same_thread=False`, broadening
cross-thread connection usage, or relying on SQLite's disabled thread check
as a substitute for deterministic release through logical owner-thread
lifecycle. Preserve the existing connection configuration and cross-thread
connection policy, as well as event admission/coalescing, bounded shutdown,
retries, dependency handling, and retained-generation/acknowledgment behavior.

### R-08 — Preserve compatibility and scope

The behavior must remain compatible with Python 3.10 and the tested Python
3.12–3.14 Windows runtimes. Linux test behavior must remain meaningful. No
schema or migration change is authorized by this issue.

## Invariants

- SQLite connections remain owned by the threads that use them; cleanup occurs
  on the owner thread.
- Active transactions are allowed to finish through existing commit or
  rollback paths before connection closure.
- Accepted ingestion work is neither silently discarded nor duplicated by
  cleanup or shutdown.
- Existing database transaction, foreign-key, WAL, busy-timeout, retry, and
  error-propagation policies remain in force.
- No real WoFF campaign data or personal filesystem paths are required in
  tests or public evidence. Synthetic test databases and sanitized results
  remain local or sanitized.
- This lifecycle correction does not change snapshot identity or acquisition
  behavior, schema, UI, or product-gate decisions.

## Scenarios

### S-01 — Worker connection is closed after successful work

Given a worker processes a synthetic event and opens a SQLite connection,
when the event has completed and the worker lifecycle reaches its safe cleanup
boundary,
then the connection is explicitly closed by that worker thread and the
committed result remains available.

### S-02 — Failed processing rolls back before cleanup

Given a worker has entered a transaction and processing raises an exception,
when the existing rollback path completes,
then the owner thread closes the connection without committing partial data,
and the original processing or persistence failure remains observable.

### S-03 — Shutdown drains work and releases worker resources

Given accepted work includes normal, retried, dependency-replayed, or
coalesced events,
when scheduler and handler shutdown return,
then accepted processing is settled according to existing policy, the
dependency monitor is stopped, and no worker-owned SQLite connection remains
open. Shutdown reports success only when this guarantee is satisfied; if
owner-thread cleanup fails, shutdown remains observably failed and cannot be
represented as successful completion.

#### Revision 2 — Explicit scheduler-capability cases

**Negative — absent declaration:** Given a direct scheduler caller that does not explicitly declare its SQLite capability, configuration or first admission is rejected before task dispatch with an observable failure. The scheduler MUST NOT silently assume `no-SQLite`.

**Negative — SQLite-capable without cleanup:** Given a caller that declares `SQLite-capable` but supplies no valid owner-thread release mechanism, configuration or admission is rejected before task dispatch. No SQLite-using callback executes, no task is silently accepted, and no cleanup success is claimed.

**Positive — explicitly no-SQLite:** Given work that genuinely cannot access SQLite and an explicit `no-SQLite` declaration, the scheduler may process and drain accepted work without a SQLite cleanup callback, preserving existing admission, retry and shutdown semantics.

**Positive — SQLite-capable with cleanup:** Given registered owner-thread release and admitted SQLite-using work, successful, exceptional, retried, dependency-replayed and coalesced tasks finish according to existing policy; the worker closes its own connection only after commit/rollback and the full task. Cleanup errors remain observable and cause shutdown to report failure rather than success.

#### Revision 2 — Verification and evidence

Verify with synthetic scheduler/handler tests that:

1. An absent/invalid capability declaration is rejected before dispatch; absence is **not** silently mapped to `no-SQLite`.
2. `SQLite-capable` without registered owner-thread cleanup fails closed before any task admission; the rejection is observable and does not destroy already accepted work.
3. Explicit `no-SQLite` work continues to function without a SQLite cleanup callback, including bounded admission and shutdown. This test must use callbacks that truly do not access SQLite.
4. An explicitly `SQLite-capable` direct caller with cleanup passes the synthetic owner-thread lifecycle regression, commits/rollbacks before close, reopens the database, and deletes the temporary database immediately on applicable native Windows versions without GC, sleeps or retry loops.
5. The configured `WoFFEventHandler` preserves its existing owner-thread cleanup behavior, even on exceptions, retries, dependency replay and coalescing, and reports cleanup failures from `shutdown()`.
6. Existing test and production scheduler construction sites are inventoried and supplied with explicit valid declarations, without changing the underlying processing, transaction or retry rules. The API naming/shape is an implementation design choice requiring a separate explicit authorization after SDD approval.

**Limits of verification:** The scheduler cannot guarantee detection of a caller that falsely declares `no-SQLite` while its opaque callback acquires SQLite. The enforceable runtime rule is to reject missing/invalid declarations and declared `SQLite-capable` configurations lacking cleanup; violating the explicit `no-SQLite` contract remains a caller defect. Do not claim universal automatic inspection of SQLite usage or silently weaken this limitation.

### S-04 — Transaction composition and reopen remain correct

Given successful, nested, rollback-only, and injected-failure transaction
paths,
when processing and owner-thread cleanup finish and the database is reopened,
then commit/rollback outcomes, foreign-key and integrity checks, and
idempotent replay match the existing database contract.

### S-05 — Windows integration teardown removes the database immediately

Given each affected `TestHandlerIntegration` case below has completed and its
handler has shut down,
when teardown closes the main-thread connection and removes the temporary
directory on Windows Python 3.10, 3.12, 3.13, or 3.14,
then removal succeeds immediately without GC or timing workarounds:

- `test_all_dependent_sources_converge_after_dossier_without_duplicates`
- `test_file_modified_event`
- `test_log_received_before_dossier_is_replayed_after_identity_persists`
- `test_startup_wait_settles_while_missing_dossier_is_retained`

The identifiers are verified against
`woff/tests/test_handler_integration.py`. Their provenance is the original
native-Windows investigation artifacts as identified for this specification
review; the published Q0 comment does not contain this complete list. This
scenario specifies the required acceptance coverage and does not claim
per-test results beyond the outcomes recorded in the Q0 evidence.

### S-06 — Regression evidence isolates the lifecycle defect

Given the exact `main` baseline and the exact PR #192 candidate are tested
using the same synthetic lifecycle procedure,
when results are compared by Python version,
then the evidence distinguishes base and candidate, identifies whether the
failure occurs in handler teardown rather than snapshot verification, and
records the owner-thread-close control. The existing Q0 record reports the
failure on both revisions for Python 3.12–3.14 and successful cleanup on
Python 3.10.

## Failure behavior

- A processing or persistence failure remains visible through the existing
  error-reporting path; cleanup must not replace it with a success-shaped
  outcome.
- A failed transaction follows existing rollback semantics before cleanup.
- Successful shutdown guarantees that accepted processing has settled and all
  worker-owned SQLite resources have been released.
- If owner-thread cleanup fails, the failure must remain observable through
  repository-standard error reporting. Shutdown cannot silently report
  success or successful temporary-database cleanup while an owned resource
  remains unreleased.

## Compatibility and migration

- Python: preserve Python 3.10 compatibility; validate Windows Python 3.10
  and 3.14 suites as specified by the issue, and retain the reported native
  Windows 3.12 and 3.13 regression coverage.
- Operating systems: physical Windows evidence is distinct from hosted CI;
  Linux tests remain meaningful.
- Schema and migration: not applicable; no schema change is authorized.
- Database reopen: required after connection cleanup and transaction paths.
- Data backup or campaign-data mutation: not applicable; use synthetic
  temporary databases only.

## Out of scope

- Changes to `StableSnapshotReader`, `_identity()`, `_cross_identity()`, or
  any other snapshot-acquisition behavior from Issue #184 / PR #192.
- Changes to Issue #184, PR #192, its review status, or its acceptance.
- Centralizing raw cataloger connections from Issue #29.
- Reworking Windows validation tooling from Issue #145 / PR #150.
- Unrelated parsers, UI, branding, schema/migrations, or dependency changes.
- GC/finalizer investigation, `gc.collect()`, arbitrary sleeps, process-exit
  cleanup, blanket test exclusions, or unrelated refactoring as a substitute
  for deterministic owner-thread closure.
- Any change to R1, Product Gates A–D, or their decisions.

## Acceptance mapping

| Issue criterion | Spec scenario/requirement |
| --- | --- |
| Revalidate `main`, non-duplication, and repository contracts | Current evidence; R-08; S-06 |
| Deterministic pre-fix Windows reproduction with base/candidate attribution | Current evidence; S-06 |
| Explicit owner-thread closure and no preventing handles after shutdown | R-01, R-02; S-01, S-03 |
| No leaks across exceptions, aborted work, ingestion, retries, replay, coalescing, and shutdown | R-03, R-04; S-02, S-03 |
| Preserve transaction semantics, integrity, idempotence, and reopen | R-03, R-05; S-02, S-04 |
| Four integration cases pass and teardown deletes immediately on Windows | R-06, R-08; S-05 |
| Focused/full tests, Python 3.10/3.14, Pyright, graph, diff check, CI, and platform-specific evidence | S-05, S-06; Compatibility and migration |
| Record revision, commands, before/after evidence, ownership rationale, limitations, and isolated diff without private data | Current evidence; S-06; Invariants |

## Open questions / evidence gaps

- The published Q0 comment names the original producer scripts and sanitized
  JSON results but does not attach or link those raw artifacts. This review
  verified the published record, its stated procedure, and the exact `main`
  and candidate revisions against GitHub; it did not independently inspect
  the original script or raw output files. The comment reports that the
  authorized producer re-opened them read-only. The maintainer may require
  publication of sanitized raw artifacts for a stronger audit.
- The complete four-test identifier list is associated with the original
  investigation scripts and JSON evidence, as identified for this review, and
  each identifier's spelling was checked in `woff/tests/test_handler_integration.py`.
  The list is not present in the published Q0 comment itself; the specification
  does not attribute it verbatim to that comment. The exact per-test,
  per-version, per-revision result matrix remains unavailable in the raw JSON.
- Native Python 3.11 behavior was not measured. The issue requests support
  across Windows 3.10–3.14 behavior; implementation validation should not
  claim a native 3.11 result unless separately evidenced.
- `check_same_thread=False` remains the existing connection configuration.
  Issue #193 does not authorize changing it or broadening cross-thread
  connection usage; deterministic release must use the established logical
  owner-thread lifecycle.

## Approval record

Approved revision: —
Approved spec commit: —
Approved by: —
Approval evidence: —

Normative amendment approved by: mksdpro
Normative amendment evidence: https://github.com/Malboro66/woff-mate/issues/193#issuecomment-6224564336
Approved normative source SHA-256: ec50a626580f15a05d915fbf3d4e5b193f2542df16397d1fe3f60ea0f8d3481a
Approved normative source: history/Issue-193-Proposed-SDD-Revision-2-REVISED-UNAPPROVED.md
Revision 1 archive: history/revision-1-approved.md
Revision 1 approved-spec commit: 0d7886faf80933dd07f5a4a533a6859c99438e59

## Implementation record

Integrated revision/PR: —
Validation evidence: —
