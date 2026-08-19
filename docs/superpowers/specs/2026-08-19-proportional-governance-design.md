# Proportional Governance Design

Date: 2026-08-19
Repository: Malboro66/woff-mate
Status: Approved design, implementation pending

## Purpose

Reduce governance overhead without weakening protections for data integrity, persistence, concurrency, Windows packaging, recovery, or release decisions.

The process will apply evidence in proportion to risk. Low-risk work receives a light process. Normal runtime changes receive focused validation. Critical changes retain the full governance model.

## Goals

- Preserve DATA-001 and DATA-002 without weakening their enforcement.
- Keep Q2, Q3, Q4, product gates, and cycle exit criteria where they are technically relevant.
- Stop treating every issue and pull request as if it had the same risk profile.
- Remove the requirement for every issue to own a formal eval.
- Make the project graph primarily an architectural context map rather than a duplicate operational tracker.
- Keep GitHub Issues, Pull Requests, Projects, and CI as the primary operational state system.
- Keep progressive autonomy as a stable area-based policy rather than per-issue paperwork.
- Use Codex Review as an independent audit after a pull request is stable, not as an implementation loop.

## Non-goals

- Do not remove evaluation-driven development.
- Do not remove the project graph.
- Do not remove Q0-Q6.
- Do not weaken migration, transaction, rollback, recovery, concurrency, or release requirements.
- Do not change the functional scope or exit criteria of cycle 3.3.0.
- Do not automate merge or release approval.

## Risk classes

### Light risk

Typical scope:

- documentation
- comments and formatting
- tests that do not change production behavior
- small governance maintenance
- mechanical maintenance with no runtime effect

Minimum process:

- scope is clear
- relevant validation passes
- complete diff is reviewed
- no personal data or generated artifacts enter the change

Historical non-duplication evidence is not mandatory unless the work claims to fix an existing defect.

A new eval is not required.

The project graph changes only when architecture, invariants, dependencies, cycles, or tracked critical contracts change.

Codex Review is optional unless the maintainer requests it.

### Normal risk

Typical scope:

- CLI behavior
- domain logic
- parsers
- configuration behavior
- ordinary runtime changes without direct persistence, migration, concurrency, or release risk

Minimum process:

- Q0 applies
- Q1 applies
- area-specific gates apply when relevant
- a regression test or deterministic reproduction is required for an observable defect
- a formal eval is added only when the behavior represents a durable contract, recurring risk, invariant, or cycle-level requirement
- the project graph changes only when its architectural or tracked-contract information changes
- one Codex Review is expected after the pull request is stable

### Critical risk

Typical scope:

- database writes and repositories
- schema and migrations
- transaction boundaries
- pilot isolation and campaign-data integrity
- concurrency, watchdog, scheduling, retry, snapshot, and recovery behavior
- destructive operations
- release and packaging changes with user-impact risk
- architectural changes that alter module boundaries or contracts

Minimum process:

- full Q0
- Q1
- Q2, Q3, Q4, Q5, or cycle gate as applicable
- explicit eval for the critical behavior
- project graph update when tracked contracts, dependencies, modules, invariants, or cycle evidence change
- failure-path testing where applicable
- rollback or recovery proof where applicable
- human review before merge
- independent Codex Review after stabilization

## Q0 redesign

Q0 remains the readiness gate but becomes risk-aware.

For normal and critical defect work, Q0 requires:

1. Historical check for prior work on the same behavior, root cause, or code path.
2. Inspection of current main to confirm the defect still exists.
3. Focused reproduction or deterministic evidence against current main.
4. Scope, owner, dependencies, and acceptance criteria.
5. Risk classification.

For light-risk maintenance and documentation work, Q0 is reduced to scope, applicability, and safety checks. Historical non-duplication evidence is required only when the work claims to resolve an existing defect or duplicates prior technical work.

If current main already satisfies the intended behavior, implementation stops and the issue is reclassified.

## Eval policy

The old rule, every issue must own an eval, is removed.

The new rule is:

If an issue declares an eval, every applicable declared eval must be implemented and passing before the issue closes.

A new eval is required when one or more of the following apply:

- the change protects a project invariant
- the change controls critical data or recovery behavior
- the defect has meaningful recurrence risk
- the behavior is part of a cycle exit criterion
- the contract needs long-term machine-readable traceability for agents

A normal regression test is sufficient when the behavior is local, low-impact, and already well represented by the test suite.

Aggregate cycle evals remain valid for release or cycle closure decisions.

## Project graph scope

The project graph remains the machine-readable context map for:

- modules and architectural dependency rules
- critical invariants
- structural work-item dependencies
- active or planned development cycles where dependency context matters
- critical or cycle-level evals
- gate definitions needed by machine-readable governance

The graph should not duplicate routine operational state already owned by GitHub unless the state is required to evaluate a structural dependency or cycle condition.

Routine changes do not require a graph edit solely to state that no graph edit was needed.

Work-item gate lists become optional. Gate applicability is primarily derived from risk classification and change type.

Work-item eval lists become optional. When present, reciprocal consistency with the eval registry remains required.

## GitHub responsibility

GitHub remains the primary operational source for:

- issue open or closed state
- pull request state
- review status
- day-to-day progress
- labels and milestones
- project-board workflow state
- CI results

The graph stores only operational information required for dependency reasoning, cycle reasoning, or architectural context.

## Progressive autonomy

Autonomy remains area-based and risk-based.

The autonomy document records:

- current maximum level by area
- promotions
- reductions
- incidents
- maintainer decisions that change authority

It does not require an entry for every issue or pull request.

Merge to main, public release, destructive campaign-data operations, and autonomy promotion remain human decisions.

## Codex Review policy

Codex Review is an audit step, not an implementation loop.

Expected use:

- light risk: optional
- normal risk: one review after stabilization
- critical risk: one independent review after stabilization, with another review only when a material correction changes the reviewed risk surface

Implementation, local tests, static analysis, and known corrections happen before requesting review.

## Cycle 3.3.0

Cycle 3.3.0 keeps its functional exit criteria.

The simplification does not remove:

- Issue #50 as the official tracker
- member issue acceptance criteria
- DATA-001 or DATA-002 protections
- critical member evals
- rollback and atomicity evidence
- bounded concurrency requirements
- snapshot stability requirements
- deterministic mission and date behavior
- deferred processing guarantees
- full-suite and Pyright expectations
- applicable Windows evidence
- maintainer approval for cycle completion

The cycle gate should no longer require documentation churn that has no relation to delivered behavior.

## Validator changes

The project graph validator should be simplified to match the new contract.

Keep validation for:

- YAML safety and duplicate keys
- module path coverage
- module dependency validity and cycles
- required invariants
- declared eval structure
- declared gate structure
- work-item dependency validity and cycles
- cycle membership and dependency consistency
- implemented eval enforcement paths

Relax validation so:

- work items may omit evals
- work items may omit gate lists
- an eval is required only when declared by a work item, invariant, or cycle contract
- reciprocal eval ownership is checked only for declared relations
- routine GitHub operational state is not required merely to satisfy the graph schema

## Files expected to change during implementation

- `AGENTS.md`
- `docs/engineering/quality-gates.md`
- `docs/engineering/evals.md`
- `docs/engineering/autonomy.md`
- `docs/architecture/project-graph.yaml`
- `scripts/validate_project_graph.py`
- `woff/tests/test_architecture_contracts.py`

Other files may change only if required to keep repository-owned documentation consistent with the approved policy.

## Testing strategy

Implementation must use test-driven changes for the validator contract.

Before changing validator behavior:

- add or adjust architecture-contract tests showing that a valid light-risk work item may omit evals and gates
- add tests showing declared eval and gate references still reject unknown IDs
- preserve tests for module dependency cycles, duplicate YAML keys, invalid paths, missing required invariants, invalid dependency states, and cycle consistency

After implementation:

- run focused architecture-contract tests
- run `python scripts/validate_project_graph.py`
- run the full pytest suite
- run Pyright
- run `git diff --check`
- review the complete diff

## Success criteria

The change is successful when:

- low-risk work no longer needs formal eval and gate bookkeeping by default
- normal work receives evidence proportional to runtime risk
- critical work retains full safety controls
- the graph remains useful to humans and agents without mirroring GitHub operations
- cycle 3.3.0 retains its technical exit criteria
- the validator enforces the reduced schema correctly
- existing critical invariants and implemented evals remain valid
- repository validation, tests, and static analysis pass
