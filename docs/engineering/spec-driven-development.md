# WoFF Mate Spec-Driven Development Pilot

Status: Pilot governance
Owner: maintainer
Applies to: issues explicitly selected for the SDD pilot

## Purpose

Spec-Driven Development (SDD) adds an approved behavioral specification between issue analysis and implementation. It complements, and does not replace, TDD, regression tests, evals, project-graph governance, quality gates, CI, independent review, or Codex Review.

The pilot is intentionally small and reversible. Historical issues do not need to be retrofitted.

## Authority and precedence

All work remains subject to the repository `AGENTS.md`, current architecture contracts, project graph, applicable evals and quality gates, security/privacy/data invariants, and the GitHub issue scope.

For existing behavior, reproduced evidence and current `main` define the current state. For an authorized change, an Approved specification defines the desired behavior within that issue's scope.

A specification may clarify an issue, but it may not silently broaden it, weaken repository invariants, or override stronger repository contracts.

## Lifecycle

```text
Issue / need
-> Q0 and current-evidence verification
-> spec.md: Draft
-> specification review
-> maintainer approval
-> spec.md: Approved
-> plan.md
-> tasks.md
-> model routing
-> implementation
-> focused tests and evals
-> spec-convergence check
-> full validation / project graph / quality gates
-> independent review
-> CI
-> Codex Review when applicable
-> consolidated corrections
-> maintainer merge decision
-> integrated evidence
-> spec.md: Implemented
```

## Specification states

### Draft

The specification is still being refined. The Spec Architect may update it. Production implementation must not start from a Draft spec.

### Approved

The maintainer has approved the specification revision for implementation. The Implementation Agent must treat its behavioral requirements as immutable.

If a requirement must change, return the specification to Draft, increment the revision, document the reason, and obtain maintainer approval again before continuing the affected implementation path.

### Implemented

The approved behavior has been integrated and validated against the revision-bound evidence. This state is recorded only after merge/integration evidence exists; it is not set merely because a branch implementation exists.

## Contradictions and evidence gaps

Agents must never silently reconcile contradictions between an Approved specification and repository evidence.

When a contradiction is discovered:

1. stop the affected implementation path;
2. record the contradictory evidence precisely;
3. identify whether the issue, spec, architecture contract, test/eval, or current implementation is inconsistent;
4. return the spec to Draft when desired behavior must change;
5. require maintainer approval before implementation resumes.

Missing WoFF evidence remains an evidence gap. Agents must not invent source semantics, identity fields, aliases, historical behavior, or campaign facts to complete a spec.

## Required artifacts

Each pilot issue uses:

```text
specs/<issue>-<slug>/
  spec.md
  plan.md
  tasks.md
```

`spec.md` defines desired behavior and observable outcomes.

`plan.md` defines the implementation strategy. It must not redefine requirements.

`tasks.md` decomposes the approved plan into small executable units with explicit validation expectations.

## Agent roles

### Spec Architect

Produces a Draft implementation-independent specification from issue scope and repository evidence. It may investigate and reproduce behavior, but it does not edit production code and cannot approve its own spec.

### Implementation Agent

Requires an Approved specification revision, prepares/uses the technical plan and tasks, implements only authorized behavior, validates the result, and reports contradictions instead of guessing.

### Independent Reviewer

Performs a fresh read-only comparison of issue, Approved spec, implementation diff, tests/evals, architecture and invariants. It reports findings rather than repairing them unless separately authorized.

## Human authority

The maintainer retains authority for:

- approving specification revisions;
- accepting or changing issue scope;
- accepting risk or evidence gaps;
- deciding whether a PR is ready for formal review;
- deciding merge;
- promoting SDD from pilot to project-wide policy.

No custom agent can approve its own output or merge its own work.

## Relationship to TDD and evals

SDD answers: what behavior is required?

TDD/regression tests answer: does the implementation satisfy local behavior?

Evals answer: do important repository-level behaviors and invariants remain satisfied?

Quality gates answer: is the change safe to integrate?

Independent review and Codex Review answer: what did the specification, tests and implementation still miss?

## Model routing

Model selection is proportional to task complexity and does not change permissions or acceptance criteria.

- Narrow/mechanical work and routine governance: GPT-5.6 Sol class by default.
- Cross-contract architecture, identity, migration, concurrency or similarly difficult work: GPT-6 Astra class when available and justified.
- Review must be independent from the implementation context even when the same model family is used.

Do not hard-code a model identifier into an agent profile when the active environment does not expose that exact identifier.

## Pilot sequence

1. Establish this SDD/custom-agent foundation under Issue #157.
2. Use Issue #151 as the first implementation pilot.
3. For #151, produce and approve the specification before changing production code.
4. Evaluate a second, intentionally different pilot such as #81 only if its current dependencies permit it.
5. Review pilot evidence before making SDD mandatory project-wide.

## Pilot measurements

Record at minimum:

- spec revision count after implementation begins;
- human clarifications/interventions;
- unauthorized scope expansion;
- focused/full validation cycles;
- Codex Review count;
- valid P1/P2 findings after stabilization;
- rework caused by implicit or missing requirements;
- available model/tool usage information.

## Out of scope for the pilot foundation

- implementing Issue #151;
- adopting Spec Kit or another SDD framework;
- changing the project-graph schema solely for SDD;
- adding complex spec validators or mandatory CI enforcement;
- mass-migrating historical issues;
- creating domain-specific database/UI/security/release agents;
- changing production behavior, schema, runtime dependencies, release controls, or product gates.
