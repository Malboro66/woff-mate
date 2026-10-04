# Repeated R2 — UI Architecture Full Application Review

## Revision and disposition

| Field | Recorded value |
|---|---|
| Review date | 2026-10-04 |
| Audited integrated `main` | `f394ece9d139b9af1a0ae14faea5d7982816a33a` |
| Integrated repository tree | `30ff40214a23d46776c5b74b29e3b2227f2065ef` |
| Final pre-merge evidence head | `e70c040b82496f1108d34a914885f9e5fb04799c` |
| Integration | [PR #178](https://github.com/Malboro66/woff-mate/pull/178), squash-merged; [#177](https://github.com/Malboro66/woff-mate/issues/177) completed |
| Technical disposition | **GO / Recommend Retain — PySide6 + Qt Widgets 6.11.2** |
| Toolkit ADR | **Proposed — pending separate explicit maintainer decision** |
| Review work item | `review-r2`: `done` |
| Review eval | `EVAL-R2-REVIEW-001`: **Implemented** |

This governance record formalizes the maintainer-supplied repeated read-only R2
Full Application Review of the exact integrated revision above. It is a
toolkit-retention recommendation, **not formal ADR acceptance**, P1 authorization,
Product Gate approval, or release/public-distribution approval. Marking the review
done and its eval Implemented records the completed technical review; the separate
maintainer decision remains mandatory. No new runtime evidence is manufactured by
this recording pass.

The [first R2](r2-ui-architecture-review.md) remains immutable historical evidence:
it audited `bfa7647ac94cafba658a077e52a55a3c2240a4dd` and returned **HOLD /
Conditional No-Go for production retention**. Its Git blob remains
`a0ed5a8c06e6a38945bda9fddda5b7fe6b431485`. That earlier evidence gap was real at
the reviewed revision; this later GO does not rewrite the first review as a pass.

## Integration and evidence binding

The final evidence head and integrated squash commit resolve to the same tree:

```text
git rev-parse f394ece9d139b9af1a0ae14faea5d7982816a33a^{tree}
30ff40214a23d46776c5b74b29e3b2227f2065ef
git rev-parse e70c040b82496f1108d34a914885f9e5fb04799c^{tree}
30ff40214a23d46776c5b74b29e3b2227f2065ef
git diff --exit-code e70c040b82496f1108d34a914885f9e5fb04799c f394ece9d139b9af1a0ae14faea5d7982816a33a
exit 0; no content differences
```

These comparisons were verified during reconciliation. Squash integration changed
commit history, not reviewed repository content. The recording branch is a later
governance change; it is not relabeled as the audited `main` revision.

Bounded UI Adoption Readiness is **complete and integrated**. Supporting records:

- [Current readiness summary](../ui/ui-adoption-readiness.md).
- [Correction investigation](../ui/ui-adoption-correction.md) and
  [automated correction archive](../ui/evidence/issue-177-correction/README.md).
- [Physical Windows 10 reports, index and separate maintainer attestation](../ui/evidence/issue-177-physical-windows10/README.md).
- [Qt licensing/plugin engineering disposition](../ui/ui-adoption-licensing.md).
- [Historical P0 evidence](../ui/p0-functional-desktop.md), #81 immutable
  presentation contracts and [#82 feasibility evidence](../ui/pyside6-spike-82.md).

The physical candidate remains bound to tested head
`f1346f99287df4202ad6495eae17acef520d4c34`, Adoption run #8 and actual embedded
merge checkout `c35fe885c7f8ffeabfd3d00c773042f2fa01845b`. Its executable SHA-256 is
`5a471827ba26431fa77544ca1e9ebaabb55a69cea5c1118d02cbe577040a94fb` and inventory
SHA-256 is `c143453e97615a32897e9b7d0ba6ffa323b133096a532f7bda7433cbcb4ca4d7`.
These identities are not replaced by the final evidence head or squash SHA.
Identical raw physical reports do not independently encode display scale; the
filenames and separate maintainer attestation distinguish the four real scales
and resolve the untouched manual-observation placeholders.

## Adoption-gate assessment

| Requirement | Result | Evidence and limits |
|---|---|---|
| #81/#82/#140 design, contracts, fixtures and P0 | Satisfied | Integrated historical evidence remains applicable; no live-data claim. |
| Optional dependency/headless isolation | Satisfied | `PySide6==6.11.2` is confined to optional `ui`; base remains Qt-free. |
| Exactly one Qt binding | Satisfied | Candidate rejects mixed bindings and version drift. |
| Python 3.10–3.14 | Satisfied | Executed source/UI matrix covers 3.10, 3.11, 3.12, 3.13 and 3.14. |
| Physical reference platform | Satisfied | Microsoft Windows 10 Pro, version 10.0.19045, build 19045. |
| Real display scaling/startup/layout | Satisfied | 100%, 125%, 150%, 200%: successful startup, no compact-layout or branding clipping, no physical regression. |
| Keyboard/focus/basic native UIA | Satisfied with residual | Visible focus, Tab, Shift+Tab, navigation and keyboard operation of both career and fixture-state selectors passed; names, roles and focusability exposed. See SetFocus limitation below. |
| Representative package/startup | Satisfied | Windows/Linux endpoint candidates build and start; Windows Python 3.10/3.14 packages supply native UIA evidence. |
| Bundle/component inventory | Satisfied | Actual collected files, modules, plugins, versions, origins and hashes distinguish installed distributions from bundled components. |
| Qt licensing/plugin disposition | Satisfied for architecture retention | Bounded LGPL engineering path; Qt Virtual Keyboard excluded; unnecessary QML/Quick, PDF, WebEngine and network/TLS surfaces removed/guarded. |
| Fixture-only/live-data boundary | Satisfied | No live WoFF, SQLite, parser, watchdog, repository, query-service, network or launcher integration. |
| Revision-bound repeated R2 | Satisfied by this record | GO recommendation against exact integrated `main` `f394ece9`; first HOLD preserved. |
| Explicit maintainer ADR acceptance | Pending separate decision | ADR remains Proposed; review completion cannot accept it. |
| Physical Windows 11, clean-machine and release certification | Deferred/outside retention prerequisites | Not claimed complete; applicable full-Q4/release/Gate-D obligations remain. |

## Full Application Review category dispositions

All categories required by [product policy](product-milestones.md) are retained;
unaffected core risks are not waived by the narrower toolkit review.

| Policy category | Disposition | Evidence and retained condition |
|---|---|---|
| Architecture/module dependencies | Reviewed — satisfactory for toolkit retention | Optional toolkit, binding guard and candidate exclusions preserve the headless/fixture boundary. |
| Career/slot/campaign/wingman identity | Reviewed — existing unrelated blocker/risk retained | Synthetic career identities stay isolated; #96 remains a confirmed production identity/data-preservation P1 blocker for Gate A/P1. |
| Transactions/rollback/atomicity | Not changed by UI adoption | Candidate performs no campaign/database writes; existing transaction/recovery requirements remain authoritative. |
| Ingestion/retry/coalescing/startup/shutdown | Reviewed — existing unrelated blocker/risk retained | Watchdog/ingestion are excluded; #142 remains the confirmed nested-file startup P1 blocker for Gate A/P1. |
| Data preservation/authority/provenance | Reviewed — satisfactory for R2 scope | Closed synthetic catalog, immutable contracts, executable/inventory/source hashes and equivalent integrated tree bind evidence; no live-data authority is inferred. |
| Schema migration/backward compatibility | Not changed by UI adoption | No database opening or schema migration; Q2 migration/reopen/rollback requirements remain. |
| Parser known/missing/unsupported/invalid semantics | Not changed and isolated | Candidate calls no parser; existing parser semantics and evidence remain authoritative. |
| SQLite/concurrency behavior | Reviewed — existing unrelated risks retained | `sqlite3`, `_sqlite3` and `woff.database` excluded; no claim that core concurrency risks are solved. |
| Privacy/local-only/credential exclusions | Reviewed — satisfactory for toolkit-retention scope | Deterministic synthetic fixtures; no personal campaign data, telemetry, external network client or credentials introduced. |
| CLI/editor/presentation contracts | Reviewed — satisfactory | Base CLI remains separate; #81 contracts and fixtures unchanged; no widget-side SQL, parsing or domain inference. |
| Windows packaging and supported Python compatibility | Reviewed — satisfactory for retention | Source 3.10–3.14, endpoint packaging/startup and physical Windows 10 evidence satisfy bounded contract; no physical Windows 11 or clean-machine claim. |
| Test/eval blind spots | Reviewed — bounded and disclosed | Automated key/UIA observations and independent physical focus/selector checks are available; no speech certification, release certification or live-data validation. |
| Project graph/gates/issues/docs/code consistency | Reviewed — one P2 wording finding reconciled | R2-repeat-P2-001 addresses current post-merge status; graph/eval record completed technical review separately from ADR acceptance. |
| Residual risks and explicit maintainer decisions | Reviewed — residuals retained | Native QComboBox SetFocus limitation, deferred release evidence, #96/#142 and explicit ADR decision remain; P1 and Gates A–D stay unauthorized/unapproved. |

### Native QComboBox / UIA SetFocus residual

Native Qt 6.11.2 `QComboBox` does not honor the tested programmatic UIA `SetFocus`
action in this path. Unsuccessful calls and observed targets remain recorded as
warnings; they are **not relabeled successful**. No artificial workaround,
replacement control or application focus override is introduced.

Real keyboard focus and selector operation passed **independently**: Tab and
Shift+Tab reach both selectors; native FocusedElement/HasKeyboardFocus is
observable; Up/Down changes selection and restoration works; visible focus was
confirmed physically at all four scales. Accessible ComboBox role and focusability
are exposed. Under the bounded retention contract this is a disclosed residual
toolkit/platform characteristic, not a blocking application defect. Narrator/NVDA
speech certification and complete accessibility compliance are not claimed.

## Findings and scope boundaries

**R2-repeat-P2-001 — Post-merge UI Adoption Readiness status wording is stale.**
At audited `f394ece9`, current forward-looking documentation still described
integration as pending. This recording pass reconciles readiness, eval, milestone,
quality-gate and graph status. The finding is documentation/governance only: no
runtime impact, evidence corruption or architectural boundary violation, and no
reason to reopen #177, repeat physical tests or return to HOLD.

Historical first R2, raw evidence, evidence archive READMEs/indexes and historical
issue/PR statements remain unchanged, including truthful earlier Draft/pending
wording. Current summaries link the later result without rewriting those snapshots.

The supplied repeated review identified no new priority:P0 or priority:P1 UI
architecture defect. #96 and #142 were independently verified still open with
`priority:P1` during reconciliation. They remain valid blockers for their applicable
Gate A/P1 path, **not toolkit-retention blockers**. Neither issue is modified,
closed or waived.

No physical Windows testing is repeated or new Windows 11 requirement imposed.
Clean-machine execution, installers, updates, rollback, signing, release provenance,
corresponding-source/public-distribution notices, relinking instructions and final
release SBOM reconciliation remain later obligations; they are not manufactured
or required for this recording pass. No licensing legal certification is asserted.

## Validation provenance

The supplied repeated R2 reports post-merge CI #329 on audited `f394ece9` passing,
including Python 3.10 **1959 passed, 12 skipped, 175 subtests passed**, graph,
architecture contracts, Python 3.14, Pyright, Windows smoke and Linux-offscreen P0
jobs. These are the reported integrated-review results, not new local executions.
[Adoption #9](https://github.com/Malboro66/woff-mate/actions/runs/37238608969)
and [general CI #328](https://github.com/Malboro66/woff-mate/actions/runs/37238608942)
are separate final pre-merge evidence validations; physical evidence remains run #8.

Reconciliation validation uses focused governance/R2 tests, architecture/product
milestone tests, project-graph validation, full pytest, Pyright and `git diff --check`.
The recording PR reports its own commands/results and reviewed branch head
separately from the audited revision and historical runtime evidence.

## Current governance and required next step

- Repeated R2: **GO / Recommend Retain — PySide6 + Qt Widgets 6.11.2**.
- `review-r2`: **done**; `EVAL-R2-REVIEW-001`: **Implemented**.
- UI toolkit ADR: **Proposed**; formal acceptance is pending.
- P1: **not authorized**; Product Gates A, B, C and D: **not approved**.
- No live WoFF/SQLite/parser/watchdog/repository/query-service/launcher integration.

First review and integrate this governance record under the applicable repository
controls and explicit maintainer merge authorization. This recording pass does not
merge, mark the PR Ready or request Codex Review. **After the record is reviewed and
integrated, the next step is a separate explicit maintainer decision on whether to
accept the PySide6 + Qt Widgets 6.11.2 ADR.** Before that decision, compare its
integrated revision with audited `f394ece9`: a scope-impact determination may cover
only unrelated, non-material intervening changes; material adoption/runtime changes
require renewed affected review. Toolkit acceptance would still not authorize P1
or approve any Product Gate.
