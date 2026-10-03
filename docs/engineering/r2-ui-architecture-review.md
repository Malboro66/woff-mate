# R2 — UI Architecture Decision review record

## Revision and disposition

| Field | Recorded value |
|---|---|
| Review checkpoint | R2 — UI Architecture Decision / first Full Application Review pass |
| Audited integrated revision | `bfa7647ac94cafba658a077e52a55a3c2240a4dd` (`main`) |
| Review date | 2026-10-02 |
| Evidence correction/rerun date | 2026-10-03 |
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
contract includes the adoption evidence, residual-risk dispositions, a new
revision-bound repeat R2 and the final explicit maintainer ADR decision that
have not occurred. Treating this HOLD as completion would authorize neither the
decision nor its evidence.

## R2 auditor commands and exact results

The following commands were rerun from a detached worktree whose `HEAD` was the
exact audited revision. They are R2-auditor executions, not reconstructed
historical results. The disposable audit environment used Python 3.12.14; paths
beginning `../.audit-r2-venv/` refer to its isolated virtual environment.

| Exact command | Exact recorded result |
|---|---|
| `git rev-parse HEAD` | `bfa7647ac94cafba658a077e52a55a3c2240a4dd`; exit 0 |
| `git rev-parse origin/main` | `bfa7647ac94cafba658a077e52a55a3c2240a4dd`; exit 0 |
| `../.audit-r2-venv/bin/python --version` | `Python 3.12.14`; exit 0 |
| `../.audit-r2-venv/bin/python scripts/validate_project_graph.py` | `project graph is valid: docs/architecture/project-graph.yaml`; exit 0 |
| `PYTHONPATH=. ../.audit-r2-venv/bin/python -m pytest -q -p no:cacheprovider woff/tests/test_architecture_contracts.py woff/tests/test_product_milestones.py woff/tests/test_ui_development_standard.py woff/tests/test_ui_v2_evidence.py tests/test_ui_contracts.py tests/test_ui_state_fixtures.py tests/test_ui_spike_evidence.py tests/test_ui_icon_assets.py tests/test_ui_portrait_assets.py` | `1025 passed in 21.65s`; exit 0 |
| `../.audit-r2-venv/bin/python -I -S scripts/validate_ui_fixtures.py` | `UI fixtures valid: 30 synthetic cases, 6 shared states.`; exit 0 |
| `PYTHONPATH=. QT_QPA_PLATFORM=offscreen ../.audit-r2-venv/bin/python -m pytest -q -p no:cacheprovider tests/test_p0_desktop.py` | `6 passed, 3 skipped in 0.04s`; exit 0. The three optional Qt tests were skipped because PySide6 was unavailable locally. |
| `sha256sum --check docs/ui/evidence/issue-140-p0/SHA256SUMS` | `dossier-ready.png: OK`; `homonym-missing.png: OK`; `missions-error.png: OK`; `operations-ready.png: OK`; exit 0 |
| `PYTHONPYCACHEPREFIX="$(mktemp -d)" ../.audit-r2-venv/bin/python -m compileall -q woff scripts tests p0_launcher.py` | no output; exit 0 |
| `../.audit-r2-venv/bin/python -m ensurepip --upgrade && ../.audit-r2-venv/bin/python -m pip install -e . --no-deps` | Installed `pip-25.0.1`, built the editable `woff-3.2.0` wheel and installed `woff-3.2.0`; exit 0. This supplied the repository's console scripts before the applicable full-suite run. |
| `PYTHONPATH=. ../.audit-r2-venv/bin/python -m pytest -q -p no:cacheprovider` | After installing this checkout's console scripts in the isolated environment: `1 failed, 1927 passed, 7 skipped, 175 subtests passed in 72.57s`; exit 1. The sole failure was `woff/tests/test_performace.py::TestPerformance::test_memory_usage`, where the executor reported `psutil.NoSuchProcess` for its ephemeral PID 2. |
| `PYTHONPATH=. ../.audit-r2-venv/bin/python -m pytest -q -p no:cacheprovider -k 'not test_memory_usage'` | `1927 passed, 7 skipped, 1 deselected, 175 subtests passed in 72.05s`; exit 0 |
| `../.audit-r2-venv/bin/pyright --pythonpath ../.audit-r2-venv/bin/python` | `8 errors, 0 warnings, 0 informations`; exit 1. All eight were unresolved `PySide6` imports (`scripts/capture_p0.py`: 1, `woff/p0_desktop/__main__.py`: 1, `woff/p0_desktop/window.py`: 6) because PySide6 was unavailable in the audit executor; Pyright also warned that the configured `.venv` directory did not exist in the detached worktree. |
| `git diff --check` | no output; exit 0 |

Before the editable audit install, the same full-suite command also exposed 27
missing-console-script failures plus the same `psutil` failure. Installing the
audited checkout into the disposable venv removed all 27 setup failures. That
preparation attempt is not used as product evidence; the post-install results
above are the applicable audit result. No test failure was suppressed or
relabelled as a pass.

## Evidence classes and audit-environment limits

### Inherited P0 and #82 historical evidence

The auditor inspected, but did not recreate or relabel:

- the immutable #81 presentation contracts and #80 synthetic fixture catalog;
- #82's archived Python 3.10/3.14 Windows 10 source/bundle measurements,
  scaling, keyboard, accessibility exposure, Qt plugin and licensing evidence;
- #140's committed Linux Qt-offscreen captures and SHA-256 manifest; and
- the maintainer-observed physical Windows 10 source and prototype-folder
  walkthrough, including the 2026-10-02 post-review revalidation at 100%, 125%,
  150% and 200%.

The R2 reruns above do not claim to be those historical executions. #82 remains
feasibility evidence; #140 remains bounded fixture-backed P0 evidence.

### GitHub Actions evidence

Merged PR #173's green **CI #303**, after correction of its eight P2 review
findings, was used as external supported-environment evidence. It reported
success for the workflow's Linux tests on Python 3.10 and 3.14, Pyright with
PySide6 installed, the experimental Linux-offscreen P0 fixture/test/source/
PyInstaller/bundle-smoke job, and Windows smoke/build checks. CI #303 was not an
R2 audit command and is not presented as one; it is inherited GitHub Actions
evidence attached to the audited integration.

### Unavailable in the audit environment

The audit executor did not provide PySide6, a physical Windows host, the
supported Python/Windows matrix, clean-machine installation, final UIA or
assistive-technology inspection, installer/update/rollback execution, or
release signing/provenance. Consequently:

- the three optional Qt tests were skipped locally and are supported externally
  by CI #303 plus the revision-bound physical evidence below;
- local Pyright was incomplete only because PySide6 imports could not resolve;
  CI #303 is the authoritative supported-environment Pyright result; and
- none of the unavailable adoption/release checks is inferred from green CI or
  historical P0 evidence. Their absence is part of the HOLD.

## Standard Full Application Review scope

The review covered every repository-policy category against exact revision
`bfa7647ac94cafba658a077e52a55a3c2240a4dd`. A disposition below does not waive
existing blockers, risks or gate requirements.

| Policy category | Disposition | R2 evidence and retained condition |
|---|---|---|
| Architecture/module dependencies | **reviewed — relevant and satisfactory for this R2 decision** | Architecture/governance tests and structural P0 checks confirm the fixture-only/UI-contract boundary. A retained Qt production architecture would add optional-dependency, entry-point, plugin and packaging ownership, so adoption remains on HOLD. |
| Career/slot/campaign/wingman identity | **reviewed — existing unrelated blocker/risk retained** | P0's two same-name synthetic careers remain isolated by stable `career_id`, but this does not close production identity work. Existing Gate A/cycle risk including #96 remains unchanged. |
| Transactions/rollback/atomicity | **not changed by the UI architecture/P0 path, with the relevant existing evidence** | P0 performs no writes. Existing transaction/rollback evidence, completed #143 work and residual #146 recovery risk remain authoritative and are not reopened or waived. |
| Ingestion/retry/coalescing/startup/shutdown | **reviewed — existing unrelated blocker/risk retained** | P0 structurally excludes watchdog, parsers and ingestion. The Gate A startup blocker #142 and bounded-acquisition risk #147 remain independent of R2. |
| Data preservation/authority/provenance | **reviewed — existing unrelated blocker/risk retained** | Immutable fixtures/contracts and SHA-256 evidence are satisfactory for P0, not live data. Gate A remains blocked, including #151 output/input isolation; P0 supplies no production authority or preservation proof. |
| Schema migration/backward compatibility | **not changed by the UI architecture/P0 path, with the relevant existing evidence** | P0 opens no database and changes no schema. Existing Q2 migration, integrity, reopen and rollback contracts remain required for applicable work. |
| Parser known/missing/unsupported/invalid semantics | **not changed by the UI architecture/P0 path, with the relevant existing evidence** | The P0 runtime excludes parsers and uses the closed synthetic catalog. Existing parser evals/tests and known/missing/unsupported/invalid distinctions remain authoritative. |
| SQLite/concurrency behavior | **reviewed — existing unrelated blocker/risk retained** | Structural checks exclude SQLite from P0. Existing Q2/Q3 evidence remains, including the independent #29 writer-ownership/concurrency risk; this review neither fixes nor waives it. |
| Privacy/local-only/credential exclusions | **reviewed — relevant and satisfactory for this R2 decision** | The P0 fixture boundary contains no personal campaign data, network access or credential handling. Existing `PRIV-001`, `LIC-001`, `NET-001` and credential exclusions remain mandatory for production/release. |
| CLI/editor/presentation contracts | **reviewed — relevant and satisfactory for this R2 decision** | #81 immutable presentation contracts and the focused architecture/UI suites pass. P0 changes no CLI/editor contract, and its widgets do not perform SQL, parsing or domain inference. |
| Windows packaging and supported Python compatibility | **reviewed — existing unrelated blocker/risk retained** | #82 and #140 prove bounded feasibility/demonstrability only. Windows 11, remaining supported Python/package combinations, clean-machine behavior, production optional dependencies/entry points and representative production packaging remain adoption blockers. |
| Test/eval blind spots | **reviewed — existing unrelated blocker/risk retained** | Automation covers routing/navigation calls, focus results, career switching/isolation, states, rail/layout and close/reopen, but does not synthesize Tab/Shift+Tab, rail arrows, Enter/Space or selector interaction. Those are maintainer-observed Windows evidence; local Qt/UIA coverage was unavailable. |
| Project graph/gates/issues/docs/code consistency | **reviewed — relevant and satisfactory for this R2 decision** | Audited `main` contained governance drift after #140 completion. This correction records #140 as done under bounded `Q4-P0-PROTOTYPE`; `review-r2`/its eval remain pending and all Product Gates remain unapproved. |
| Residual risks and explicit maintainer decisions | **reviewed — existing unrelated blocker/risk retained** | No new UI `priority:P0` or `priority:P1` defect was found, but adoption gaps and existing #142, #96 and #151 Gate A blockers remain. The ADR is Proposed; no production-retention, P1 or Product Gate decision is authorized. |

## Physical Windows evidence bound to the audited merge

The post-review physical walkthrough ran on
`64710a0b1bc46c19f267db10e4168403ce974066`. It did not run after the squash
merge. The final branch documentation commit was
`691749ce3e2c9e9c807142c1c6b326846c4bc269`; R2 audited squash-merged `main` at
`bfa7647ac94cafba658a077e52a55a3c2240a4dd`.

The following repository commands bind the physical evidence to the audited
merge by direct content comparison rather than ancestry:

| Exact command | Exact recorded result |
|---|---|
| `git diff --exit-code 64710a0b1bc46c19f267db10e4168403ce974066 bfa7647ac94cafba658a077e52a55a3c2240a4dd -- pyproject.toml woff/__init__.py woff/p0_desktop p0_desktop.spec p0_launcher.py tests/test_p0_desktop.py woff/ui_contracts.py woff/nation.py woff/maps.py woff/tests/fixtures/ui_states woff/assets/ui/icons woff/assets/ui/portraits woff/assets/ui/branding scripts/validate_ui_fixtures.py` | no output; exit 0. All relevant P0 executable/runtime/build, dependency-metadata, contract, fixture, test and asset inputs are identical. |
| `git diff --name-only 64710a0b1bc46c19f267db10e4168403ce974066 691749ce3e2c9e9c807142c1c6b326846c4bc269` | `docs/ui/evidence/issue-140-p0/windows-physical-walkthrough.md`; exit 0. The final pre-merge head differs from the physically validated head only by the evidence record. |
| `git diff --exit-code 691749ce3e2c9e9c807142c1c6b326846c4bc269 bfa7647ac94cafba658a077e52a55a3c2240a4dd` | no output; exit 0. The final PR head and audited squash merge have identical complete repository content. |
| `git rev-parse 691749ce3e2c9e9c807142c1c6b326846c4bc269^{tree}` | `6927873b08f3867fa3d43bb620f1de9910b4e560`; exit 0 |
| `git rev-parse bfa7647ac94cafba658a077e52a55a3c2240a4dd^{tree}` | `6927873b08f3867fa3d43bb620f1de9910b4e560`; exit 0 |

Therefore the physical run is applicable to the audited squash merge because
its runtime/build-input tree is proven identical. This does not relabel the run
as post-merge execution.

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

These results complete P0 demonstrability under `Q4-P0-PROTOTYPE`. They do not
satisfy full Q4 or establish production adoption readiness.

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

### Correctly deferred release-only work

Release signing, trusted public artifact provenance, supported installer,
installation/update/rollback certification and final public-distribution
approval remain outside #140's approved P0 scope and inside full Q4/release
work. Their deferral does not cure the adoption gaps above, complete #155, or
approve Product Gate D.

## Disposition and mandatory next review

The result remains **HOLD / Conditional No-Go for production retention**.
Therefore:

1. production retention is not authorized;
2. the toolkit ADR remains Proposed;
3. P1 remains unauthorized;
4. no Product Gate A, B, C or D is approved; and
5. adoption-readiness remains the next technical evidence phase.

After relevant adoption-readiness changes are integrated, a new revision-bound
R2 Full Application Review **MUST** be performed against the then-current
integrated `main`. Only after that repeat review may the explicit maintainer
production-retention ADR decision occur. A scope-impact determination may cover
only unrelated, non-material intervening changes between the repeated R2 review
revision and the final decision revision under the existing policy; it cannot
replace the mandatory repeat R2. Only that review and subsequent explicit
decision, together with every existing adoption gate, can retain the production
UI architecture or authorize P1.
