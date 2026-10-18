# Implementation Tasks

Issue: #193
Spec revision: 2
Approved spec commit: `5436c1315592cfe54663c6550642907774a632a8`
Maintainer approval: https://github.com/Malboro66/woff-mate/issues/193#issuecomment-6241153390
Integrated SDD publication: `2a3cd59d9f6b30f3c9137c6d1138ef4ff9400b7a`
Candidate: Draft PR #198 (branch `integration/184-193-validation`)
Pre-reconciliation head: `e561a581d36f73d67e86ed801307479c2ad1f9f0`

The revision-1 T01-T08 implementation sequence and requirement mapping
remain **historical** and unmodified in `history/revision-1-tasks.md`
(with the associated `history/revision-1-plan.md`). This checklist
tracks revision-2 reconciliation and subsequent gates. A checked item is
not a maintainer merge or Issue-closure authorization.

## Previously implemented/evidenced on old exact head

- [x] R2-01: Explicit `sqlite-capable` / `no-sqlite` declarations; missing,
  invalid and SQLite-capable-without-callable-cleanup fail before dispatch
  (R-01/R-02 and negative S-03).
- [x] R2-02: Genuine no-SQLite caller and SQLite-capable direct caller with
  owner-thread cleanup regression; production handler registration
  (positive S-03 and R-01).
- [x] R2-03: Owner-thread lifecycle, exception observability, rollback,
  transaction composition, retries/replay/coalescing and Windows S-05
  evidence on old SHA (R-03 through R-08, S-01 through S-06).
- [x] R2-04: Revision-2 SDD published on `main` with approved revision-1
  archive preserved. Post-merge main CI 5/5 passed.

## Pending on the newly reconciled candidate

- [x] R2-05: Resolve `spec.md` by retaining byte-exact integrated revision 2;
  preserve revision-1 plan/tasks byte-for-byte; bind active plan/tasks to
  the full approved-spec SHA and maintainer decision.
- [ ] R2-06: Inspect all tracked scheduler construction sites and
  direct/indirect/retry/replay callback behavior; verify truthfulness of
  `no-sqlite` declarations (R-01/R-02/S-03).
- [ ] R2-07: Verify snapshot `woff/ingestion/snapshot.py` remains exactly the
  #184/PR #192 blob; rerun targeted R-01 through R-07/S-01 through S-06
  regressions and the four S-05 native Windows cases.
- [ ] R2-08: Run complete Python 3.10 and 3.14 suites, Pyright, graph,
  diff check, hosted CI and applicable quality gates on the new SHA;
  explicitly distinguish previous-head evidence.
- [ ] R2-09: Obtain a fresh, isolated independent Full Application
  Integration Review on new head. Resolve any new material findings.
- [ ] R2-10: After independent GO obtain applicable official Codex Review
  bound to the new SHA; prior review at `39bef55...` does not count.
- [ ] R2-11: Separate maintainer merge decision. Until authorized, keep
  Draft and unmerged; Issue #193 remains open, R1 and Product Gates
  A-D unchanged.

## Requirement / evidence map

| Contract | Tasks |
| --- | --- |
| R-01/R-02; S-03 explicit capability / fail closed | R2-01, R2-02, R2-06, R2-07 |
| R-03/R-05; S-02/S-04 transaction cleanup | R2-03, R2-07, R2-08 |
| R-04/R-07; S-01/S-03 retry, replay and drain | R2-02, R2-03, R2-06, R2-07 |
| R-06/R-08; S-05/S-06 Windows and scope | R2-03, R2-07, R2-08 |
| Provenance / independent / Codex / merge | R2-04, R2-05, R2-09, R2-10, R2-11 |

No schema, migration, cross-thread policy, snapshot behavior, UI, release,
or Product Gate change is included in these revision-2 tasks.
