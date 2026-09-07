# Product demonstrability and full-application reviews

## Purpose

WoFF Mate tracks two independent forms of progress:

1. **engineering progress** — issues, evals, quality gates, cycle completion, CI, architecture and data-safety evidence;
2. **product demonstrability** — what a user or maintainer can actually open, navigate, observe and evaluate as an integrated product artifact.

A technically healthier codebase is valuable even when it adds no visible capability, but long engineering sequences must not silently replace product validation. At every product checkpoint, the project records what became demonstrable, which artifact proves it, what data source it uses, its known limitations, and the next blocker to a stronger vertical slice.

This document supplements rather than replaces `quality-gates.md`, the project graph, issue acceptance criteria, Codex Review policy, or maintainer approval.

## Milestone model

The identifiers below are product/review checkpoints. They do not replace semantic versions, GitHub milestones, or Product Gates A-D.

| Checkpoint | Meaning | Minimum evidence |
|---|---|---|
| **R0 — Foundation Baseline** | Historical foundation checkpoint | Existing integrated engineering baseline; no new audit is required merely to adopt this policy |
| **R1 — Integrity Baseline** | Integrated review before Product Gate A approval | Full Application Review of the reliable-companion boundary and explicit residual-risk decision |
| **P0 — Functional Desktop Prototype** | First launchable/navigable desktop WoFF Mate prototype | Fixture-backed shell, synthetic careers, primary navigation, shared states, keyboard/scaling evidence, no live SQLite/WoFF binding |
| **R2 — UI Architecture Decision** | Cross-system review after presentation contracts/toolkit evidence | #81/#82 evidence, ADR decision, packaging/accessibility results, boundary review before retained production UI architecture |
| **P1 — Read-only Vertical Slice** | First narrow end-to-end real local read flow | Stable career selection and approved core screens driven through application query services, with no widget-side SQL/parsing/inference |
| **P2 — Installable Alpha** | First installable Windows alpha usable by a non-developer for approved scope | Clean-machine install/start, diagnostics, bounded alpha flow, packaging evidence and known limitations |
| **P3 — Companion Beta** | Normal companion flow suitable for broader controlled testing | Stable ordinary usage path, recovery evidence, regression coverage and user-facing limitations |
| **P4 — Social/RPG Alpha** | First coherent persistent social/RPG loop | Deterministic domain model, persistence, identity, safe simulation and demonstrable loop |
| **RC1 — Public Release Candidate** | Candidate for Product Gate D/public distribution | Full release-readiness evidence, installation/update/recovery, privacy/local-only contract and final Full Application Review |

## Full Application Review

A Full Application Review is an integrated audit of current `main`. It is not a larger Codex Review of one pull request and it is not satisfied by green CI alone.

A Full Application Review is mandatory before approving each major Product Gate transition and may also be triggered exceptionally.

### Standard audit scope

Review the applicable integrated state across:

- architecture and module dependencies;
- career, slot, campaign and wingman identity;
- transactions, rollback and atomicity;
- ingestion, retry, coalescing, startup and shutdown;
- data preservation, authority and provenance;
- schema migration and backward compatibility;
- parser known/missing/unsupported/invalid semantics;
- SQLite and concurrency behavior;
- privacy, local-only operation and credential exclusions;
- CLI, editor and presentation contracts;
- Windows packaging and supported Python compatibility;
- tests/evals for blind spots, implementation-coupling and missing cross-system cases;
- project graph, gates, issues, documentation and code consistency;
- known residual risks and explicit maintainer decisions.

The review must distinguish verified defects, structural risks, evidence gaps and intentionally deferred work. Missing evidence is not replaced by model inference.

### Extraordinary triggers

Run a Full Application Review or a scoped equivalent before continuing related structural work when any of these occur:

- confirmed post-merge P0/P1 defect;
- the same defect class appears across multiple pull requests or subsystems;
- major identity/schema/concurrency redesign;
- material drift between graph, gates, issues, documentation and code;
- repeated review cycles indicate that issue-local review is discovering a systemic problem;
- a release or product transition exposes integration assumptions not covered by existing evals.

## Product-demonstrability record

At P0, P1, P2, P3, P4 and RC1 record at minimum:

- **user-capability statement:** what can now be done that could not be demonstrated at the previous checkpoint;
- **artifact:** exact executable/build/site/evidence revision used for evaluation;
- **data class:** synthetic, fixture-backed, sanitized representative, or live local read-only data;
- **supported flow:** what was actually exercised;
- **unavailable flow:** behavior intentionally not implemented or not authorized;
- **accessibility/interaction evidence:** keyboard, focus, scaling and other applicable evidence;
- **safety boundary:** writes/network/privacy/schema implications;
- **next blocker:** the narrowest missing capability preventing the next product checkpoint.

A long engineering sequence can legitimately have no new user-visible capability. When that happens, the next checkpoint must say so explicitly and record why the engineering work was required before a demonstrable increment.

## Near-term WoFF Mate sequence

The current priority is to convert the strong foundation into demonstrable product increments without weakening reliability.

1. Stabilize the currently open integrity/governance work.
2. Synchronize governance after those merges.
3. Perform **R1** before Product Gate A is approved.
4. Resolve the remaining cycle 3.3.0 evidence/gate decision.
5. Complete **#81** immutable read-only presentation/query contracts.
6. Execute **#82** toolkit/packaging/scaling/accessibility spike and make the explicit ADR decision required for retained desktop work.
7. Implement **#140 — P0 Functional Desktop Prototype**.
8. Use P0 as the first recurring product-demonstrability checkpoint.
9. Move next toward **P1 — Read-only Vertical Slice**, replacing fixture-only data only through approved application query services.

The sequence does not require every 3.4.0/3.5.0 item to finish before P0. Work unrelated to the P0 safety and presentation boundary must not indefinitely postpone the first functional desktop prototype.

## P0 boundary

P0 exists to prove product flow, not live integration.

It may:

- render approved UI V2 screens;
- use deterministic synthetic fixtures;
- switch synthetic careers by stable identity;
- demonstrate ready/loading/empty/missing/stale-unavailable/error states;
- exercise keyboard, focus, resizing and scaling;
- be packaged for maintainer evaluation when #82 supports that path.

It must not:

- open/query SQLite;
- read WoFF campaign files;
- call parsers, catalogers or watchdog;
- mutate configuration/campaign data;
- launch or control WoFF;
- fabricate domain facts in widgets;
- introduce AI into runtime;
- use personal campaign data.

## Model routing for reviews

Model selection is a development-tooling decision only.

- Routine governance synchronization remains a narrow/moderate task suitable for the project's standard engineering model.
- A Full Application Review is cross-cutting XL work and should use the strongest approved cross-system auditor under the current model-routing policy.
- Repository contracts, tests, observed behavior and maintainer decisions always outrank model inference.
- No AI model is part of WoFF Mate runtime, campaign processing or player-facing simulation.

## Relationship to Product Gates

The existing Product Gates remain authoritative:

- **Gate A — Reliable data**
- **Gate B — Viable launcher**
- **Gate C — Social RPG**
- **Gate D — Public release**

Their current technical conditions remain necessary. This policy adds two requirements to a gate decision:

1. the applicable **Full Application Review** must be completed and its P0/P1 findings disposed or explicitly accepted by the maintainer;
2. the strongest applicable **product-demonstrability record** must exist so the decision is based on an integrated artifact, not only issue completion and green automation.

A product checkpoint never auto-approves a Product Gate, and completion of an engineering cycle never auto-approves a product checkpoint.

## Governance rules

- Engineering and product progress are reported separately.
- Full Application Review findings are tracked by defect class, not only individual examples.
- P0/P1 findings block the applicable transition until corrected or explicitly handled under existing governance.
- Evidence gaps remain evidence gaps; they cannot be closed by assumption.
- No checkpoint bypasses Q0-Q6, data protection, privacy, migration policy, Codex Review gates or human approval.
- Changes to these milestone definitions require an explicit governance change.
