# Progressive autonomy

## Principle

Autonomy depends on risk. Documentation and sanitized tests permit more agent
action than database migrations, destructive operations, merges, and releases.

## Levels

| Level | Authorized activity | Human control |
|---|---|---|
| L0: analysis | Read, reproduce, explain, and propose a plan | Approves every mutation |
| L1: local implementation | Create a local branch, tests, and scoped changes | Reviews the diff and decides publication |
| L2: draft pull request | Run gates, publish the branch, and open a draft PR | Reviews and decides ready status |
| L3: limited delivery | Take approved low or medium risk work through draft PR | Approves merge and sensitive decisions |
| L4: controlled maintenance | Execute repeatable tasks from an approved list | Maintains audit and approves releases |

## Initial maximum by area

| Area | Maximum | Reason |
|---|---|---|
| Reading, diagnosis, and planning | L1 | Reversible |
| Sanitized tests and fixtures | L2 | Low risk without personal data |
| Documentation and governance | L2 | Low runtime risk and simple review |
| Isolated CLI correction | L2 | Limited data impact |
| Parser and normalization | L1 | Changes campaign interpretation |
| Concurrency and watchdog | L1 | Failures may lose events |
| Transactions and repositories | L1 | Partial-state risk |
| Schema and migration | L0 or L1 | Direct database risk |
| Retained/production read-only interface | L2 only after R2, applicable ADR adoption gates, and applicable Product Gates | Maximum execution level after every prerequisite is satisfied |
| Merge to `main` | Human only | Official integration point |
| Release and distribution | Human only | Affects real users |
| Destructive operation | Human only | May be irreversible |

An autonomy level is a maximum operational permission, not authorization to
bypass unresolved dependencies, architecture decisions, Product Gates, R2,
ADR adoption requirements, or issue-specific gates.

Before Product Gate A, UI work may proceed only where current governance
explicitly authorizes its bounded scope, such as design work, sanitized
fixtures, immutable toolkit-independent UI contracts, isolated feasibility
spikes, and the fixture-only P0 prototype. Each item remains subject to its
issue, graph dependencies, evidence requirements, and human controls.
Experimental or fixture-only work cannot silently become retained production
architecture or a live-data interface.

Issue #51 is authorized through L2. It may publish a branch and open a draft
pull request. It may not mark the pull request ready, merge, or publish a
release without a new maintainer decision.

## Permanently human decisions

- merge to `main`
- public release or installer publication
- destructive campaign-data operation
- acceptance of a migration without tested recovery
- product scope or product-gate change
- reduced data-protection requirement
- autonomy promotion

## Promotion

An area may move up one level only when:

- five comparable consecutive changes pass all gates
- none requires rollback after merge
- no data or privacy incident occurs
- review feedback is incorporated into a graph, eval, gate, or checklist
- the maintainer explicitly approves promotion

## Immediate reduction

Autonomy drops when:

- a regression escapes the defined tests
- a change exceeds authorized scope
- real or personal data enters a fixture, log, or commit
- a migration fails to reopen safely
- an applicable gate is skipped
- `main` or a release changes without approval

## Current record

| Date | Area | Level | Evidence or decision |
|---|---|---|---|
| 2026-08-14 | Documentation and executable governance | L2 | Issue #51 authorized as a small independent draft PR |
| 2026-08-14 | Issue #34 transactions and repositories | L1 | Structural data work remains under human publication and merge control |
| 2026-08-14 | Merge and release | Human only | Approved Master Plan and repository policy |

## Updating this record

Any autonomy change records the date, area, previous level, new level, evidence,
approver, and any incident or rollback condition. Operational GitHub Project
fields may display the current workstream but do not replace this record.
