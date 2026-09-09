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

## Validation summary

On the audited revision, project-graph validation, the focused architecture,
privacy and pilot-vacancy suites, and `git diff --check` passed. Cross-system
reproductions confirmed the verified defects assigned below.

The native Windows full suite and Pyright did not provide a clean gate result.
The observed interpreter selection, unsupported test-only file-mode constant,
locale-dependent subprocess decoding, and byte-sensitive checkout behavior are
owned by #145. Green Linux full-suite/Pyright CI and the narrower Windows
smoke/build job do not replace that missing native Windows evidence.

## Finding ownership and disposition

The classifications below preserve the review distinction between a reproduced
defect, a structural risk, an evidence gap, a governance action, and work that
is intentionally deferred.

| Finding | Classification | Owner | Gate A disposition |
|---|---|---|---|
| R1-001 | Verified defect | #96 | Blocking `priority:P1`; correct and revalidate |
| R1-002 | Verified defect | #74 | Blocking `priority:P1`; correct and revalidate |
| R1-003 | Verified defect | #142 | Blocking `priority:P1`; correct and revalidate |
| R1-004 | Verified defect | #143 | Resolve the abnormal-exit rollback contract before the reliable-data claim |
| R1-005 | Verified defect | #144 | Resolve incomplete live-ingestion acknowledgement before the reliable-data claim |
| R1-006 | Verified validation defect | #145 | Restore deterministic native Windows validation before consideration |
| R1-007 | Verified governance/implementation discrepancy | #136 | #136 remains open and planned; #81 remains blocked |
| R1-008 | Evidence gap | #87 / #50 | Resolve under the cycle 3.3.0 evidence contract; do not close from assumption |
| R1-009 | Required evidence | Gate A decision record | Produce the revision-bound reliable-companion/recovery demonstration after blocking corrections |
| R1-010 | Verified defect | #99 | Correct or explicitly disposition under existing governance |
| R1-011 | Verified defect | #77 | Correct or explicitly disposition under existing governance |
| R1-012 | Structural risk | #145 | Preserve deterministic raw evidence bytes across supported Windows checkouts |
| R1-013 | Verified defect | #98 | Correct or explicitly disposition under existing governance |
| R1-014 | Structural risk | #146 | Define and evidence atomic or durable derived-state recovery |
| R1-015 | Verified defect | #29 | Correct or explicitly disposition catalog-writer ownership/concurrency risk |
| R1-016 | Structural risk | #147 | Evidence a bounded acquisition policy or record the residual-risk decision |
| R1-017 | Verified defect | #44 | Correct or explicitly disposition under existing governance |
| R1-018 | Verified defect | #76 | Correct or explicitly disposition under existing governance |
| R1-019 | Governance action | #148 | Synchronize this record, graph, evals, cycles and dependencies |
| R1-020 | Intentional deferral | #81 / #82 / #140 | Preserve sequence and fixture-only P0 boundary; P0 absence does not itself block Gate A |

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

Product Gate A remains unapproved. Consideration requires, at minimum:

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
