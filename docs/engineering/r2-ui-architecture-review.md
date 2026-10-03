# R2 — UI Architecture Decision review record

## Revision and disposition

| Field | Recorded value |
|---|---|
| Review checkpoint | R2 — UI Architecture Decision / first Full Application Review pass |
| Audited integrated revision | `bfa7647ac94cafba658a077e52a55a3c2240a4dd` (`main`) |
| Review date | 2026-10-02 |
| Disposition | **HOLD / Conditional No-Go for production retention** |
| Preferred candidate | **PySide6 + Qt Widgets 6.11.2** |
| UI toolkit ADR | **Proposed — not accepted** |
| P1 | **Not authorized** |
| Product Gates A-D | **Not approved** |
| Review work item | `review-r2` remains pending |

This is the revision-bound first-pass R2 record required by
[`product-milestones.md`](product-milestones.md). The HOLD is a completed review
observation, not the final production-retention decision. PySide6 + Qt Widgets
6.11.2 remains the technically preferred candidate, but incomplete
adoption-readiness evidence prevents production retention.

`review-r2` remains `backlog` and `EVAL-R2-REVIEW-001` remains `planned`. Their
contract includes the adoption evidence, residual-risk dispositions and final
explicit maintainer ADR decision that have not occurred. Treating this HOLD as
completion would incorrectly authorize neither the decision nor its evidence.

## Audited scope and evidence

The review assessed the integrated evidence from #81, #82 and #140/P0 at the
exact revision above. Its evidence basis includes:

- the immutable presentation contracts and synthetic fixtures completed by
  #81 and #80;
- the isolated PySide6 feasibility record completed by #82;
- the merged #140 implementation and product-demonstrability record in
  [`../ui/p0-functional-desktop.md`](../ui/p0-functional-desktop.md);
- automated P0 flow and structural boundary coverage in
  `tests/test_p0_desktop.py`;
- committed Linux Qt-offscreen captures and their SHA-256 manifest under
  `docs/ui/evidence/issue-140-p0/`;
- the maintainer-observed physical Windows 10 source and prototype-bundle
  walkthrough, including the 2026-10-02 post-review revalidation at 100%, 125%,
  150% and 200%; and
- merged PR #173 and green CI #303, after all eight P2 review findings were
  corrected.

Automated checks, Linux captures and physical Windows observations remain
distinct evidence classes. Local Windows screenshots inspected during the
post-review revalidation are not committed evidence and are not relabelled as
Linux captures. #82 measurements remain historical feasibility evidence and
are not presented as #140 measurements.

## Findings

### Technical result within approved P0 scope

- #81, #82 and #140 are technically coherent within their approved scopes.
- The P0 fixture-only/runtime dependency boundary passed: the prototype does
  not bind live SQLite, WoFF files, parsers, repositories, watchdog, launcher,
  network, configuration mutation, campaign mutation or runtime AI.
- No new UI `priority:P0` or `priority:P1` defect was found.
- All eight P2 findings raised during PR #173 review were corrected before
  merge.
- PySide6 + Qt Widgets 6.11.2 remains the technically preferred candidate.

These results complete P0 demonstrability. They do not establish production
adoption readiness.

### Verified governance defect

The audited `main` retained pre-integration governance values after #140 was
completed: `issue-140` and its three evals were pending, the R2 dependency on
#140 was unsatisfied, milestone/gate/eval narratives still awaited P0, the P0
record still described a branch/Draft PR, and the governance tests enforced
those stale claims. This is verified governance drift, not a P0 runtime defect.
The focused reconciliation following this review corrects only those versioned
records and their assertions.

### Blocking adoption evidence gaps

Production retention remains blocked on evidence for:

- Windows 11 execution;
- the remaining supported Python/package matrix;
- clean-machine validation;
- final-P0 UI accessibility/UIA evidence where applicable;
- the production optional-dependency and entry-point policy;
- representative production packaging and startup behavior;
- the bundle inventory, SBOM and licensing route; and
- Qt plugin/licensing disposition, including Qt Virtual Keyboard if present in
  the production bundle.

These are adoption-readiness gaps. This review does not implement them, infer
their results or waive any existing ADR adoption gate.

### Structural risks that are not P0 defects

- Retaining Qt in production would create optional-dependency, entry-point,
  plugin-discovery and packaging ownership that the isolated P0 path
  intentionally does not resolve.
- Supported-platform claims remain broader than the physical P0 host and the
  currently exercised package matrix.
- Accessibility semantics observed during feasibility/P0 work do not by
  themselves constitute final production UIA or assistive-technology evidence.
- Qt component and plugin inventory can change the licensing and distribution
  obligations of a production bundle.

These risks are consequences of a possible production architecture choice;
they are not regressions in the approved fixture-backed prototype.

### Correctly deferred release-only work

Release signing, trusted public artifact provenance, installer/update/rollback
certification and final public-distribution approval remain release-stage work.
Their deferral does not cure the adoption gaps above, complete #155, or approve
Product Gate D. No release-only task is silently promoted into this governance
reconciliation.

## Disposition and next decision point

The result is **HOLD / Conditional No-Go for production retention**. Therefore:

1. production retention is not authorized;
2. the toolkit ADR remains Proposed;
3. P1 remains unauthorized;
4. no Product Gate A, B, C or D is approved; and
5. adoption-readiness remains the next technical evidence phase.

After the relevant adoption-readiness changes are integrated, R2 must be
repeated against the exact then-current `main` revision, or every intervening
change must have an approved scope-impact determination under the repository
policy. Only that revision-valid review plus an explicit maintainer decision
can retain the production UI architecture or authorize P1.
