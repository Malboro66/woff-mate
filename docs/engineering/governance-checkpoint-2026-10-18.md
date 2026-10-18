# WoFF Mate — Integrated governance checkpoint (2026-10-18)

**Status:** current-state governance reconciliation proposal, **not a Product Gate decision**
**Scope:** Issue #209; documentation and controls only
**Verified integrated `main`:** `d230d1e139a49e1746e9e24fb70b0adc9905d8ab`
**Verification:** GitHub comparison `d230d1e139a49e1746e9e24fb70b0adc9905d8ab...main` was `identical` (0 ahead / 0 behind) on 2026-10-18.
**Software identifiers from `woff/version.py`:** app `3.2.0`, SQLite schema `3.5`, config `1`; `pyproject.toml` specifies Python `>=3.10,<3.15` and optional `ui = ["PySide6==6.11.2"]`.

This document supersedes older *current-state summaries* only where they conflict with independently observed integrated revisions, issue/PR states, or explicit later maintainer decisions. It **does not** amend the original Master Plan, erase revision-bound reviews, change executable project-graph issue states, declare a CI run successful, or grant implementation, merge, release or gate authorization.

## 1. Authority and reconciliation

1. Reproducible observed behavior, source snapshots and deterministic tests govern what the implementation actually does.
2. Integrated `main`, its committed `AGENTS.md`, `project-graph.yaml`, CI, architecture contracts, version source and applicable tests govern the current repository implementation.
3. GitHub issue/PR state, recorded human decisions, and approved revision-bound specifications govern work authorization and intended changes. A Draft PR is not integrated behavior.
4. Full Application Review records, evals, quality gates, ADRs and product evidence govern eligibility for specific decisions. An earlier verdict remains historically true for its audited SHA.
5. Older plans and analyses provide rationale and history; their dated backlog counts and unaccepted proposals cannot override newer evidence.

If these sources conflict, **record the exact conflict and stop only the affected decision**. Do not silently mark a gate done or overwrite historical measurements. Before review or merge, revalidate the head/base and issue/PR states; this checkpoint is dated, not automatically live.

## 2. Verified status at this checkpoint

| Area | Verified fact | Boundary |
|---|---|---|
| UI ADR | **Accepted** by explicit maintainer decision on **2026-10-05**: PySide6 + Qt Widgets **6.11.2** | Toolkit selection is not P1, live data, launcher, Gate A/B or release authorization |
| First R1 | **FAIL** on integrated `f8da6c3d4da3264c025303d851f8bd2fcf1d8f4b` | Remains historical; affected-scope repeated R1 and Gate A approval are still required |
| First R2 | **HOLD / Conditional No-Go** on `bfa7647ac94cafba658a077e52a55a3c2240a4dd` | Preserve unmodified |
| Repeated R2 | **GO / Recommend Retain** on `f394ece9d139b9af1a0ae14faea5d7982816a33a` | Technical recommendation; later explicit ADR acceptance is independent |
| Main protection | #152 completed; existing ruleset evidence is recorded in `main-protection-2026-09-27.md` | Human merge authority remains |
| Wingman identity | #96 closed; PR #182 merged | Does not itself validate all real-source ingestion or wingman transfers |
| SQLite worker lifecycle | #193 closed; PR #198 merged, with separate #184 Windows snapshot work closed | Do not infer that an unrun Windows test or new application-wide R1 passed |
| PilotClaims zero header | #186 closed | Historical pre-correction R1 verdict remains |
| SQLite constraint certification | #77 closed | Not equivalent to final database release certification |
| Source provenance | #99 closed | Its tested contract does not close unrelated ingestion risks |
| Startup reconciliation | #142 **open**; PR #203 **open Draft**, observed head `0489cde4f377078e2f84e902f4d71198aa91226d` | Unmerged candidate, not a Gate A pass |
| Squadron catalog integrity | #98 **open**; PR #208 **open Draft**, observed head `f676fd0cf62a1cd755e2e1b1f86a485c3575a37a` | No implementation claim before review/integration |
| Other relevant open work | #146 permanent derived-state failure; #195 attested RFC-13 Dossier ranks; #87 safe longitudinal same-name career evidence; tracker #50 remains open | Resolve or formally disposition where required; no blanket reinterpretation of priority |
| Public product | No Product Gate A, B, C or D approval was found in the governing accepted decisions | Do not infer approval from CI, a toolkit, a prototype, or a merged PR |

The base/main comparison confirms the **Git revision**; this pass has **not** executed the full local test suite, physical Windows scenarios, a complete CI-job inventory, a fresh Full Application Review, or a live WOFF mission replay. Unmeasured outcomes are **unknown**, not PASS.

## 3. Work queues and dependency rules

**Reliability / Gate A:** finish independent review and disposition of #142/PR #203; evaluate real-source #195 and permanent derived-state #146 against their distinct contracts; preserve #87 as evidence-bound; keep #50 open until its aggregate eval, remaining evidence and maintainer approval are satisfied. Other open issues must be triaged according to their own dependency graph rather than automatically escalated. Reassess #98/PR #208 on its own P3 catalog boundary; do not treat it as merged, combine it with #29/#46, or silently convert it into a Gate A blocker without new evidence.

**UI:** the retained toolkit is decided. Continue only separately authorized fixture, contract, design and bounded preview work. P1 real/local data through application query services needs the explicit applicable Gate A/B decisions; a preview or demo cannot transfer that permission. No widget-side SQL, file parsing, inferred career identity or raw-game-data mutation.

**RPG / future Headquarters:** long-term vision includes relationships, persistent wingman memory, morale/reputation, transfers, promotions, recovery, encounters and squadron life. This is *planning context*, not current feature authorization. Require stable `career_id`/`wingman_id`, source authority, typed events, replay/idempotency, atomic persistence, and recovery before an RPG vertical slice. A missing squadron member is **not** automatically dead, transferred, discharged or on leave; confirmed information and unknown destinations must stay distinguishable. Use a separate scope/issue and applicable Gate C decision.

**Windows and release:** supported Python range, native Windows compatibility, privacy/local-only, packaging obligations, #153/#154 staged security work and #155 pre-distribution provenance stay distinct from active Gate A work. No official installer, tag, release or distribution authorization is created here.

Only one active structural implementation workstream should be preferred; independent small governance/fixture work may proceed when it does not compete with or bypass the reliability boundary. No unrelated refactor in a corrective PR.

## 4. Proportional evidence and review guardrail

Every proposed test campaign, spike, environmental setup, specialist tool, formal review or certification **must identify**:

- the approved requirement or exact current decision it informs;
- the smallest reproducible experiment capable of changing that decision;
- its risk, cost and stopping criterion;
- whether available evidence is observed, simulated, vendor-stated, historical, missing or unverified.

An issue checklist alone does **not** justify unbounded validation. Do **not** expand into virtual machines, physical Windows 11, clean-machine distribution certification, Narrator/NVDA screen-reader campaigns, extra accessibility certification, additional Codex Review loops, speculative security infrastructure or external environments unless the maintainer explicitly approves that requirement **and** the result materially affects a current engineering/product decision. This does not waive routine keyboard/focus/usability checks or release/security obligations when genuinely applicable. Record the evidence gap and defer disproportionate work instead of manufacturing a PASS or silently deleting a gate.

Spikes end at the **minimum decision-sufficient evidence**. Stop and reassess when the experiment costs more than the decision it resolves. Preserve already collected historical results even when their evidence is superseded.

## 5. Validation, reviews and autonomy

- Follow `AGENTS.md` and Q0 historical non-duplication before implementation; synthetic/sanitized reproducible failing-before evidence (or justified preventive evidence), issue-specific scope, module boundary, evals and tests precede code.
- Q1 full suite, Pyright, graph validator and affected Q2/Q3/Q4 gates remain required by actual scope; do not substitute a CI green badge for behavioral evidence.
- Codex Review is an **independent final audit of stabilized work**. Treat findings by full defect class. Generally budget one review (two for normal exceptional correction; three at most for critical scope). Further reviews require explicit reevaluation rather than an automatic loop. Requested reviews and applicable material threads must be disposed **before merge**.
- The independent Full Application Review (R1/R2 and future transitions) is **not** the same as an additional Codex Review of a draft PR. Every result is revision-bound; scope-impact determination for intervening commits requires documentation and maintainer acceptance.
- Spec-Driven Development applies only to explicitly selected issues, with the approved exact revision and evidence binding; do not infer authorization from draft text.
- Autonomy for documentation and governance is at most **L2 Draft PR**. Human approval is required for ready-for-review status where mandated, merge, changes to gates/architecture, destructive operations, migration acceptance, release and escalation of autonomy. This checkpoint itself does not promote autonomy.

## 6. Real WOFF source proof — separate, read-only evidence track

The maintainer's collected WOFF BH&H II Dossier/Log/Squads observations and test flight can support future deterministic integration evidence. They are **not** a passed product gate by themselves.

Use native physical Windows and **immutable local copies** of approved WoFF-generated source files. Keep original files, private paths and raw identifying campaign content out of GitHub. Inventory basename/type, file size and SHA-256 in a private evidence manifest; compare T0 and post-mission T1 source generations. First run an isolated replay into a fresh temporary SQLite database; then, only after the isolated replay is successful and separately authorized, conduct local **shadow/read-only observation** of the real campaign. Do not write to the game's career files.

The bounded evidence record must compare observed career identity, squadron/aircraft, mission count/outcome, known-vs-missing values, source/provenance, roster changes and idempotent replay, explicitly marking each observation PASS/FAIL/UNKNOWN and capturing the exact code revision and procedure. A successful parsing or XOR roundtrip proves only its own scoped property. No inferred transfer, mission, injury, victory or RPG event may be marked confirmed absent source evidence.

If a new defect is confirmed, search existing issues first (especially #87, #96, #101, #142, #146, #195 and #98) and open only a narrowly scoped non-duplicate issue. A real-source observation does not silently expand a Draft PR, change schema or authorize a Gate A approval.

## 7. Completion and next decision

The current change is complete as a **governance Draft PR** when the checkpoint and discoverability amendments pass documentation review, the graph validator and diff checks (or record exact unavailable validations), no production code or project gate changes are introduced, and the maintainer is offered a revision-bound integration decision.

After a separately approved merge, the most valuable next product action is **a bounded read-only T0/T1 real WOFF replay**, coordinated with existing Gate A blockers—not a new UI certification campaign or a premature RPG/launcher feature.

**References:** [Master Plan](../architecture/project-graph.yaml), [quality gates](quality-gates.md), [eval catalog](evals.md), [autonomy](autonomy.md), [product checkpoints](product-milestones.md), [SDD pilot](spec-driven-development.md), [UI ADR](../architecture/adr-ui-toolkit.md), [first R1](r1-integrity-baseline.md), [first R2](r2-ui-architecture-review.md), [repeated R2](r2-ui-architecture-review-repeat.md), [Issue #209](https://github.com/Malboro66/woff-mate/issues/209).
