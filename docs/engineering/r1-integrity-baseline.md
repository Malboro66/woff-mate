# R1 — Integrity Baseline review record

## Revision and verdict

| Field | Recorded value |
|---|---|
| Review checkpoint | R1 — Integrity Baseline / Full Application Review |
| Audited integrated revision | `f8da6c3d4da3264c025303d851f8bd2fcf1d8f4b` (`main`) |
| Review date | 2026-09-08 |
| Verdict | **FAIL — confirmed blocking defects exist** |
| Product Gate A | **NOT APPROVED** |
| Governance owner | #148 |

This is a revision-bound record under
[`product-milestones.md`](product-milestones.md). It records the smallest
authoritative repository summary of the review; the focused GitHub issues own
the reproducible evidence and corrective acceptance criteria. A model
inference is not repository fact unless supported by executable or repository
evidence.

## Validation and evidence

These are the exact commands and recorded results from the R1 audit of the
integrated revision above. They are historical baseline evidence, not reruns by
the governance PR.

### Baseline validation

| Exact command | Recorded result |
|---|---|
| `.venv\Scripts\python.exe scripts/validate_project_graph.py` | `PASS, exit 0` |
| `.venv\Scripts\python.exe -m pytest woff/tests/test_architecture_contracts.py -q` | `123 passed` |
| `.venv\Scripts\python.exe -m pytest woff/tests/test_privacy_contracts.py -q` | `10 passed` |
| `.venv\Scripts\python.exe -m pytest woff/tests/test_pilot_vacancy.py -q` | `38 passed` |
| `.venv\Scripts\python.exe -m pytest -q` | `15 failed, 1233 passed, 1 skipped, 23 warnings; 145 subtests passed` |
| `.venv\Scripts\pyright.exe` | `FAIL: 28 errors, 3 warnings` |
| `git diff --check` | `PASS, exit 0` |

### Native-Windows diagnostics

| Exact command | Recorded result |
|---|---|
| `.venv\Scripts\pyright.exe --pythonpath .venv\Scripts\python.exe` | `1 error, 0 warnings: os.O_ACCMODE at woff/tests/test_command_contracts.py:778` |
| `.venv\Scripts\python.exe -m pytest woff/tests/test_command_contracts.py woff/tests/test_woff_query.py -q` (UTF-8 interpreter mode enabled in the audit environment) | `1 failed, 65 passed`; the remaining failure was the `os.O_ACCMODE` portability defect |

The audit's initial sandboxed focused-test attempts encountered
`PermissionError: [WinError 5]` while accessing pytest's existing temporary
directory. Authorized reruns outside that sandbox preparation boundary
succeeded. This was environment preparation context, not a product defect.

The audited SHA's GitHub CI run succeeded for Linux Python 3.10/3.14 tests,
Linux Pyright, and Windows smoke/build. It did not run or establish a passing
native-Windows full suite. The baseline full-suite/Pyright failures and the
diagnostic `os.O_ACCMODE`, interpreter-selection, subprocess-decoding, and
byte-sensitive-checkout portability defects remain owned by #145.

## Finding ownership and disposition

The Classification column reproduces the authoritative R1 labels verbatim.
Ownership and Gate A disposition describe follow-up without altering that
classification. Each numbered owner below is the repository-local GitHub issue
that holds the finding's reproducible evidence and acceptance criteria; R1-009
instead requires the revision-bound Gate A decision/demonstration evidence.

| Finding | Classification | Owner | Gate A disposition |
|---|---|---|---|
| R1-001 | VERIFIED DEFECT | #96 | Blocking `priority:P1`; correct and revalidate |
| R1-002 | VERIFIED DEFECT | #74 | Blocking `priority:P1`; correct and revalidate |
| R1-003 | VERIFIED DEFECT | #142 | Blocking `priority:P1`; correct and revalidate |
| R1-004 | VERIFIED DEFECT | #143 | Resolve the abnormal-exit rollback contract before the reliable-data claim |
| R1-005 | VERIFIED DEFECT | #144 | Resolve incomplete live-ingestion acknowledgement before the reliable-data claim |
| R1-006 | VERIFIED DEFECT | #145 | Restore deterministic native Windows validation before consideration |
| R1-007 | EVIDENCE GAP | #136 | #136 remains open and planned; #81 remains blocked |
| R1-008 | EVIDENCE GAP | #87 / #50 | Resolve under the cycle 3.3.0 evidence contract; do not close from assumption |
| R1-009 | EVIDENCE GAP | Gate A decision record | Produce the revision-bound reliable-companion/recovery demonstration after blocking corrections |
| R1-010 | VERIFIED DEFECT | #99 | Correct or explicitly disposition under existing governance |
| R1-011 | VERIFIED DEFECT | #77 | Correct or explicitly disposition under existing governance |
| R1-012 | STRUCTURAL RISK | #145 | Preserve deterministic raw evidence bytes across supported Windows checkouts |
| R1-013 | VERIFIED DEFECT | #98 | Correct or explicitly disposition under existing governance |
| R1-014 | STRUCTURAL RISK | #146 | Define and evidence atomic or durable derived-state recovery |
| R1-015 | STRUCTURAL RISK | #29 | Correct or explicitly disposition catalog-writer ownership/concurrency risk |
| R1-016 | STRUCTURAL RISK | #147 | Evidence a bounded acquisition policy or record the residual-risk decision |
| R1-017 | VERIFIED DEFECT | #44 | Correct or explicitly disposition under existing governance |
| R1-018 | VERIFIED DEFECT | #76 | Correct or explicitly disposition under existing governance |
| R1-019 | EVIDENCE GAP | #148 | Synchronize this record, graph, evals, cycles and dependencies |
| R1-020 | INTENTIONALLY DEFERRED WORK | #81 / #82 / #140 | Preserve sequence and fixture-only P0 boundary; P0 absence does not itself block Gate A |

Issues #142–#147 are registered as independently owned R1 follow-ups with
planned evals and applicable Q0–Q5 references. They are not members of cycles
3.3.0 or 3.4.0 merely because R1 found them. The existing GitHub milestones and
cycle scopes remain unchanged; Gate A disposition and engineering-cycle
membership are separate decisions.

| Issue | Graph module and dependency rationale | Cycle decision |
|---|---|---|
| #142 | `ingestion`; extends completed #42 snapshot/startup and #122 inventory contracts | Post-R1 Gate A correction, not a retroactive 3.3.0 member |
| #143 | `persistence`; extends completed #34 composable transactions | Post-R1 Gate A correction, not a retroactive 3.3.0 member |
| #144 | `ingestion`; reconciles completed #75 command completeness with #42 live snapshot admission | Post-R1 Gate A correction, not a retroactive 3.3.0/3.4.0 member |
| #145 | `governance`; restores cross-cycle native validation and immutable-evidence checkout | Cross-cutting gate evidence, not an engineering-cycle feature |
| #146 | `application`; follows completed #34/#39/#95 transaction, mission and retry contracts | Cross-system residual-risk work, not a silent reopening of 3.3.0 |
| #147 | `ingestion`; bounds the completed #42 snapshot path and composes with #27 retention | Preventive cross-cutting risk, not an automatic cycle member |

## Reconciled dependency state

- #136 is reopened for implementation. Its five evals remain planned, and #81
  remains blocked on its unsatisfied dependency.
- #139 is complete through merged PR #141. The #139 dependency into #140 is
  satisfied; #140 remains blocked by #81 and #82 and remains fixture-backed
  only. No production toolkit is accepted.
- #122 is complete and its six vacancy evals are implemented. #87 and the
  aggregate cycle 3.3.0 eval remain pending, so #50 and the cycle remain open
  until the applicable evidence and maintainer approval exist.

## Gate A path and revision validity

Product Gate A is not approved. Consideration requires, at minimum:

1. correction or explicit existing-governance disposition of the blocking R1
   findings;
2. restoration of the required native Windows/local validation through #145;
3. resolution of #87 evidence as required by cycle 3.3.0;
4. Full Application Review evidence valid for the corrected integrated
   revision;
5. a reproducible reliable-companion/recovery demonstration bound to that
   revision; and
6. explicit maintainer approval.

CI success alone satisfies none of these decisions.

This R1 result applies only to
`f8da6c3d4da3264c025303d851f8bd2fcf1d8f4b`. After corrective changes are
integrated, the affected R1 scope must be rerun against the corrected `main`.
Only intervening changes proven not to affect the audited scope or evidence may
reuse existing results through the documented scope-impact determination and
maintainer approval. There is no blanket documentation or governance exemption.
