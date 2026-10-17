# WoFF Mate — Issue #193
## Proposed SDD Revision 2 — REVISED / UNAPPROVED

**Document status:** Draft normative amendment for explicit maintainer consideration. **NOT APPROVED.**  
**Decision:** REVISE — limited normative clarification.  
**Authority:** Approved SDD revision 1, specification commit `0d7886faf80933dd07f5a4a533a6859c99438e59`.  
**Target:** `specs/193-sqlite-worker-connection-lifecycle/spec.md` — proposal only; the approved revision 1 remains unchanged and authoritative.  
**Implementation:** Not authorized by this document.  
**First official Codex Review:** HOLD.

### Amendment boundaries

This draft proposes only (1) an addition to R-01, (2) replacement wording for R-02, (3) an additional negative/positive contract scenario under S-03, and (4) targeted verification criteria for that scenario. **All other approved revision 1 text remains unchanged**, in particular R-03 through R-08, S-01, S-02, S-04 through S-06, transaction/persistence and owner-thread invariants, the approval history, and out-of-scope boundaries. The draft must not be treated as an in-place edit to revision 1.

The term **scheduler-managed work** below includes initial/live event processing, coalesced processing, persistence retry and dependency replay callbacks executed on the scheduler's worker threads. A generic scheduler cannot reliably discover from an arbitrary Python callback whether it accesses SQLite. Accordingly, the proposed contract relies on **explicit, validated capability declaration**, not runtime introspection or an implied absence of SQLite access.

## 1. R-01 — proposed addition after the current requirement

> The owner-thread release obligation applies to any `EventScheduler` configuration whose scheduler-managed work may acquire a SQLite connection, including direct scheduler callers outside `WoFFEventHandler`. Before the first admission, each scheduler configuration MUST explicitly declare whether scheduler-managed work **may access SQLite** (`SQLite-capable`) or **cannot access SQLite** (`no-SQLite`). The declaration covers all processing, retry and replay callbacks that can execute on scheduler-managed worker threads, including indirect calls. Omission or an unknown declaration MUST NOT be interpreted as `no-SQLite`.
>
> A `SQLite-capable` configuration MUST register a deterministic owner-thread release mechanism before admitting any work. The registered mechanism MUST run on the worker that owns the connection, after the entire task and all active transactions have completed through the existing commit or rollback paths. An explicitly declared `no-SQLite` configuration MAY omit a SQLite cleanup callback, but its worker callbacks MUST NOT open or use SQLite connections. The scheduler MUST NOT attempt to compensate for absent cleanup by closing a worker's connection from another thread. The existing `check_same_thread=False` setting and cross-thread policy are unchanged.

## 2. R-02 — proposed replacement of the current requirement

> A scheduler MUST validate its explicit SQLite capability declaration and, for a `SQLite-capable` configuration, the presence of an owner-thread release mechanism **before accepting any work**. If the declaration is missing, invalid or `SQLite-capable` without an appropriate release mechanism, the scheduler MUST fail closed during configuration or reject admission **before dispatch**. This failure MUST be deterministic and observable to the caller; it MUST NOT be reported as successful acceptance, successful processing or successful shutdown of rejected work. Already accepted work MUST NOT be silently discarded to enforce the contract.
>
> For an explicitly declared `no-SQLite` configuration, SQLite cleanup registration is not required and existing non-SQLite scheduling behavior remains available. Such a declaration is a binding contract about the work supplied by the caller; it is not a claim that the scheduler can infer or inspect arbitrary callback internals. A caller that declares `no-SQLite` but permits its callbacks to acquire SQLite violates the configuration contract and cannot claim the R-01/R-02 resource guarantee.
>
> When `EventScheduler.shutdown()` and the delegating handler shutdown return successfully for correctly configured work, all accepted work and dependency-monitor activity have finished, and no SQLite connection owned by completed scheduler-managed work remains open. Registered cleanup MUST run on the owning worker after work and transaction unwinding, including exceptional paths. A cleanup failure MUST remain observable under repository-standard reporting, and shutdown MUST NOT return successfully while an owned connection is known to remain unreleased. Shutdown MUST preserve existing bounded admission, coalescing, retry/replay and work-drain behavior.

## 3. S-03 — proposed additional contract cases

> **Negative — absent declaration:** Given a direct scheduler caller that does not explicitly declare its SQLite capability, configuration or first admission is rejected before task dispatch with an observable failure. The scheduler MUST NOT silently assume `no-SQLite`.
>
> **Negative — SQLite-capable without cleanup:** Given a caller that declares `SQLite-capable` but supplies no valid owner-thread release mechanism, configuration or admission is rejected before task dispatch. No SQLite-using callback executes, no task is silently accepted, and no cleanup success is claimed.
>
> **Positive — explicitly no-SQLite:** Given work that genuinely cannot access SQLite and an explicit `no-SQLite` declaration, the scheduler may process and drain accepted work without a SQLite cleanup callback, preserving existing admission, retry and shutdown semantics.
>
> **Positive — SQLite-capable with cleanup:** Given registered owner-thread release and admitted SQLite-using work, successful, exceptional, retried, dependency-replayed and coalesced tasks finish according to existing policy; the worker closes its own connection only after commit/rollback and the full task. Cleanup errors remain observable and cause shutdown to report failure rather than success.

### 4. Proposed verification and evidence (applies if revision 2 is approved)

Verify with synthetic scheduler/handler tests that:

1. An absent/invalid capability declaration is rejected before dispatch; absence is **not** silently mapped to `no-SQLite`.
2. `SQLite-capable` without registered owner-thread cleanup fails closed before any task admission; the rejection is observable and does not destroy already accepted work.
3. Explicit `no-SQLite` work continues to function without a SQLite cleanup callback, including bounded admission and shutdown. This test must use callbacks that truly do not access SQLite.
4. An explicitly `SQLite-capable` direct caller with cleanup passes the synthetic owner-thread lifecycle regression, commits/rollbacks before close, reopens the database, and deletes the temporary database immediately on applicable native Windows versions without GC, sleeps or retry loops.
5. The configured `WoFFEventHandler` preserves its existing owner-thread cleanup behavior, even on exceptions, retries, dependency replay and coalescing, and reports cleanup failures from `shutdown()`.
6. Existing test and production scheduler construction sites are inventoried and supplied with explicit valid declarations, without changing the underlying processing, transaction or retry rules. The API naming/shape is an implementation design choice requiring a separate explicit authorization after SDD approval.

**Limits of verification:** The scheduler cannot guarantee detection of a caller that falsely declares `no-SQLite` while its opaque callback acquires SQLite. The enforceable runtime rule is to reject missing/invalid declarations and declared `SQLite-capable` configurations lacking cleanup; violating the explicit `no-SQLite` contract remains a caller defect. Do not claim universal automatic inspection of SQLite usage or silently weaken this limitation.

## 5. S-05 and Issue #184 — no normative amendment

The approved S-05 remains unchanged: all four specified `TestHandlerIntegration` test bodies **and** their immediate temporary-database teardowns must pass under native Windows Python 3.10, 3.12, 3.13 and 3.14 without garbage collection, deletion retries or arbitrary sleeps. An owner-thread cleanup PASS alone is insufficient to claim S-05 PASS.

The one-pass, disposable combined candidate containing PR #196's SQLite lifecycle change and PR #192's isolated snapshot change passed all five selected tests once per Windows version. This is diagnostic **integration-dependency evidence**, not an integrated commit, proof of repeatability, authorization to merge or authorization to alter Issue #184's code within Issue #193.

For an eventual reviewable combined candidate, preserve the maintainer dossier's **proposed** evidence threshold of three independent fresh invocations per Windows runtime, plus relevant lifecycle-negative cases and broader focused/full suites, Pyright, project-graph validation, CI and exact source attribution. That threshold is a proposed review gate; it does not retroactively amend S-05 or replace other approved quality gates. Keep each PR's implementation and review decision separate until explicitly authorized otherwise.

## 6. Decision required from the maintainer

**Approve / Revise / Reject** this revised, still-unapproved normative proposal, specifically:

- The required **explicit SQLite capability declaration** before admission (including direct callers and indirect/retry/replay callbacks).
- The deterministic fail-closed outcome for missing/invalid declarations and `SQLite-capable` configurations without registered cleanup.
- Continued callback-free use by **explicitly declared, genuine no-SQLite** work.
- The non-detection limitation for dishonest/misconfigured `no-SQLite` callbacks, and the separate #184/#193 combined-candidate validation dependency.

**Until a new approval is explicitly recorded:** SDD revision 1 and commit `0d7886faf80933dd07f5a4a533a6859c99438e59` remain the only approved normative baseline. PR #196 remains Draft, Issue #193 remains open, and the first official Codex Review stays on HOLD. No application, branch, PR, issue, R1 or Product Gate A–D change is authorized by this draft.
