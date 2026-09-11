# Specification

Issue: #<number>
Status: Draft
Revision: 1
Baseline: <commit SHA>
Owner: maintainer

## Problem

Describe the user/system problem without prescribing implementation.

## Goal

State the desired observable outcome.

## Current evidence

For defect/evidence-based work, record externally produced deterministic Q0
evidence: exact full `main` commit SHA, command/procedure, observed result,
relevant artifact/fixture/test where applicable, evidence location, and producer.
The Spec Architect inspects this record and leaves the specification in `Draft`
if it is absent, stale, ambiguous, inaccessible, or not baseline-bound. Include
other relevant issues, PRs, commits, fixtures, or repository contracts.

## Required behavior

Define what must be true after implementation.

## Invariants

List repository/domain properties that must remain true.

## Scenarios

### S-01 — <name>

Given ...
When ...
Then ...

## Failure behavior

Define safe outcomes for invalid, missing, ambiguous, unavailable, partial, transient, and permanent failure cases that are in scope.

## Compatibility and migration

State compatibility, migration, backup, rollback, reopen, platform, and Python-version requirements that apply. Use `Not applicable` explicitly when none apply.

## Out of scope

List adjacent improvements and behaviors that this specification does not authorize.

## Acceptance mapping

| Issue criterion | Spec scenario/requirement |
| --- | --- |
| <criterion> | <mapping> |

## Open questions / evidence gaps

Record unresolved questions without guessing. An unresolved blocking question prevents approval.

## Approval record

Approved revision: —
Approved spec commit: —
Approved by: —
Approval evidence: —

For `Status: Approved`, replace every placeholder above. `Approved revision`
must equal `Revision`; `Approved spec commit` must be the full Git SHA containing
this revision's exact approval payload; and `Approval evidence` must link to a maintainer-authored GitHub
comment/review that explicitly approves this specification path, revision, and
commit. The canonical approval payload from current committed Git content must
remain exactly identical to the canonical payload at that commit, and the
specification path must have no uncommitted changes. See
`docs/engineering/spec-driven-development.md#approval-contract` for the exact
payload boundary, UTF-8/LF canonicalization, and lifecycle-only exclusions.

If the approval payload changes, set `Status: Draft`, increment `Revision`, and
clear this entire approval record before requesting new maintainer approval.

## Implementation record

Integrated revision/PR: —
Validation evidence: —
