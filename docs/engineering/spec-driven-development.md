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

The maintainer has approved the exact specification revision for implementation,
and the complete [approval contract](#approval-contract) is satisfied. The
Implementation Agent must treat its behavioral requirements as immutable.

If a requirement must change, return the specification to Draft, increment the
revision, document the reason, clear the prior approval record, and obtain a new
revision-bound maintainer approval before continuing the affected implementation
path. Status text copied from an earlier revision is not authorization.

### Implemented

The approved behavior has been integrated and validated against the revision-bound evidence. This state is recorded only after merge/integration evidence exists; it is not set merely because a branch implementation exists.

## Approval contract

Production implementation may begin only when all of the following are true:

1. `Status` is exactly `Approved`.
2. `Revision` is an explicit positive integer, and `Approved revision` exactly
   matches it.
3. `Approved spec commit` is the full Git commit SHA containing the exact
   approval payload for that revision.
4. `Approved by` identifies a non-placeholder human maintainer with approval
   authority for the repository.
5. `Approval evidence` is a direct link to a maintainer-authored GitHub issue or
   pull-request comment/review. Its text explicitly approves the specification
   path, revision, and full approved-spec commit SHA recorded above.
6. The current approval payload is byte-for-byte identical to the payload at
   that path in `Approved spec commit`.

The approval payload consists of the stable metadata (`Issue`, `Revision`,
`Baseline`, and `Owner`) and the normative content from `Problem` through
`Open questions / evidence gaps`. It excludes only mutable lifecycle metadata:
`Status`, the `Approval record`, and the `Implementation record`. This avoids a
self-referential commit while ensuring that requirements cannot change after
approval without invalidating it. After the maintainer posts the approval
evidence, a bookkeeping commit may set `Status: Approved` and populate the
approval record; it must not change the approval payload.

This Git revision and maintainer record is the pilot's minimal deterministic
binding; it is not a signing or cryptographic approval system. The Implementation
Agent must inspect the linked evidence and its author rather than trusting fields
inside the mutable specification alone.

Missing, placeholder, inaccessible, contradictory, stale, or ambiguous approval
data blocks implementation. A mismatch between the current approval payload and
the approved Git revision also blocks implementation even when `Status` still says
`Approved`. The agent must stop and report the exact missing or conflicting
evidence; it must not infer approval.

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

Produces a Draft implementation-independent specification from issue scope and
repository evidence. Its allowlist provides named, read-only GitHub issue,
pull-request, and commit tools plus repository read/search and file editing so it
can write the issue's specification. It has no GitHub mutation, terminal
execution, or agent-handoff capability. The current custom-agent format cannot
restrict `edit` to a path, so the profile also explicitly limits its writes to
`specs/<issue>-<slug>/spec.md`. It does not edit production code and cannot
approve its own spec.

### Implementation Agent

Requires the complete approval contract for the exact specification revision,
prepares/uses the technical plan and tasks, implements only authorized behavior,
validates the result, and reports contradictions instead of guessing. It has the
read, search, edit, and terminal capabilities required for implementation, but
only named, read-only GitHub issue, pull-request, and commit tools. Draft-PR
creation or updates use a separately authorized host workflow or a human
maintainer; the profile receives no GitHub mutation tool and cannot approve risk
or merge on behalf of the maintainer.

### Independent Reviewer

Performs a fresh capability-level read-only comparison of issue, Approved spec,
implementation diff, tests/evals, architecture and invariants. Its tool allowlist
contains only `read` and `search`. It has no `edit`, `execute`, GitHub mutation,
or agent-handoff tool. The clean review bundle must make remote issue, approval,
and PR evidence available for read-only inspection; missing evidence stops the
review rather than expanding capabilities. It reports findings; corrections
belong to the Implementation Agent or a separately authorized correction task.

The profiles follow the official
[custom-agent configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration):
the `tools` allowlist enables only named capabilities, while omission would
enable every available tool. GitHub MCP tools use the documented
`github/<tool-name>` syntax. Spec Architect and Implementation Agent GitHub
access is limited to `issue_read`, `search_issues`, `pull_request_read`,
`search_pull_requests`, `get_commit`, and `search_commits`, as documented by the
[GitHub MCP server](https://github.com/github/github-mcp-server#tools). These
operations are sufficient to inspect the current issue/PR and perform Q0 across
related issues, PRs, and commits. They cannot create or update a PR, write a
review, approve, merge, or mutate repository state.

Role prohibitions must also be reflected in tool capabilities wherever the host
supports enforcement. Server-wide wildcards such as `github/*` are prohibited
when the server can expose maintainer-only or other mutation operations. Prose
restrictions remain defense in depth; they are not a substitute for a
least-privilege allowlist.

The current custom-agent format does not define finer-grained path restrictions
for `edit` or command restrictions for `execute`. The Implementation Agent needs
`execute` for tests, static analysis, and local Git operations, so a host must not
expose maintainer-capable GitHub credentials through that terminal. The agent
must not use a shell or alternate client to bypass its GitHub tool allowlist.
Profiles otherwise use only documented aliases, and host enforcement of the
allowlist remains a prerequisite for the stated capability boundary.

## Human authority

The maintainer retains authority for:

- approving specification revisions;
- accepting or changing issue scope;
- accepting risk or evidence gaps;
- deciding whether a PR is ready for formal review;
- deciding merge;
- promoting SDD from pilot to project-wide policy.

No custom agent can approve its own output or merge its own work.

## Independent pre-review isolation

An official repository Independent Reviewer pass must start in a new session or
an equivalently isolated context. Selecting, invoking, or handing off to the
reviewer inside the implementation conversation is not an official independent
pass because it can inherit implementation assumptions.

The fresh review session receives only a clean, reproducible review bundle:

- issue and acceptance criteria;
- approved specification path, revision, full approved-spec commit, approver,
  and approval-evidence link;
- applicable `AGENTS.md`, architecture, project graph, evals, quality gates, and
  other governing contracts;
- implementation PR/diff and exact reviewed commit;
- focused/full tests, evals, gates, and CI evidence;
- repository state needed to reproduce or verify findings.

Do not include implementation chain-of-thought, informal implementation
discussion, discarded approaches, or the Implementation Agent's conclusions as
reviewer assumptions. The reviewer may inspect committed `plan.md` and `tasks.md`
as claims when relevant, but must derive findings independently from authoritative
requirements and evidence.

This Independent Reviewer is the repository's pre-review control. It runs before
the maintainer decides that a PR is ready for the separate official Codex Review
required by project policy. A clean Independent Reviewer result neither triggers,
replaces, nor waives Codex Review; Codex Review findings still receive
defect-class consolidation before the maintainer's merge decision.

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
