# Data-Loss Issue Registration Implementation Plan

> **For agentic workers:** Execute this plan task by task with repository validation and review checkpoints.

**Goal:** Register seven validated data-loss defects as complete GitHub issues and synchronize their milestones, dependencies, executable governance, and persistent planning documents without modifying the implementation of Issue #72 or PR #92.

**Architecture:** GitHub issues remain the operational backlog. `docs/architecture/project-graph.yaml` remains the executable source for work items, dependencies, evals, gates, and cycles. Persistent planning documents summarize the same state after GitHub returns final issue numbers.

**Technical baseline:** `main` at `4fd7a313d0cb670e698a5c4449357fbc57aea4f3`, containing merged PR #92.

## Global constraints

- Preserve Python 3.10 compatibility.
- Do not change production code or the SQLite schema in this governance task.
- Do not modify Issue #72 or PR #92.
- Create every GitHub issue in English.
- Assign each new issue a priority label, area labels, `risk:data-loss`, a type label, and a milestone.
- Keep one implementation issue per future branch and draft PR.
- Do not merge the governance PR.

## Task 1: Register the seven validated defects

- [x] Search open and closed issues for each root cause and stop on a true duplicate.
- [x] Create three P1 issues in milestone 3.3.0.
- [x] Create two P2 issues in milestone 3.4.0.
- [x] Create two P3 issues in milestone 3.5.0.
- [x] Include deterministic reproduction, root cause, impact, contract, scope, acceptance criteria, dependencies, evals, constraints, and non-duplication rationale.
- [x] Read every created issue back and verify title, body, labels, milestone, and open state.

Result: Issues #93 through #99.

## Task 2: Synchronize operational dependencies

- [x] Add #94 and #95 as blockers of #27.
- [x] Record #96 as coordinated with #35, #37, and #72 without changing the closed #72 work.
- [x] Record #98 before #29 and #46.
- [x] Add #93, #94, and #95 to tracker #50 and record the post-#72 execution order.
- [x] Read #27, #29, #37, #46, and #50 back and verify each relation once.

## Task 3: Update persistent audit and planning documents

- [x] Add one current checkpoint section to each canonical planning document without rewriting historical sections.
- [x] Map every `F-2026-08-23-*` alias to its final issue number.
- [x] Record that PR #92 merged and Issue #72 is complete.
- [x] Validate headings, counts, links, sequence, and current-state statements.
- [x] Replace each persistent file using its stable file ID.

## Task 4: Synchronize executable governance

- [x] Confirm PR #92 merged and refresh `main` before editing.
- [x] Create `codex/register-data-loss-findings` from merged `main` in an isolated worktree.
- [x] Add seven work items, their evals, gates, cycles, and technical dependencies to the graph.
- [x] Add matching eval definitions and cycle summaries to `docs/engineering/evals.md`.
- [x] Update Q6 membership and exit criteria in `docs/engineering/quality-gates.md`.
- [x] Run graph validation, architecture contracts, Pyright, full suite, and diff checks.
- [x] Commit the governance-only diff with an English commit message.
- [x] Open a draft PR with an English title and no implementation-issue closing keywords.

## Task 5: Final verification

- [x] Confirm the seven issues exist exactly once and all have milestones.
- [x] Confirm Issue #72 and PR #92 were not modified by the registration work.
- [x] Confirm all dependency references resolve to existing issue numbers.
- [x] Confirm every persistent document has a successful replacement result.
- [x] Confirm the governance PR is draft and unmerged.
- [ ] Report issue URLs, updated documents, checks, and remaining implementation work.
