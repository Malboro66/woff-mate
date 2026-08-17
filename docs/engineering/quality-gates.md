# Quality gates

## Authority

The `main` branch and `.github/workflows/ci.yml` define the final command names
and supported CI environments. This document defines the evidence required to
advance work. A green workflow is necessary but does not replace functional exit
criteria.

## Q0: ready for implementation

Work enters implementation only when:

- the defect is reproduced or preventive risk is evidenced
- the issue has passed the mandatory historical non-duplication check below
- dependencies are verified in the project graph
- affected files and owning module are identified
- acceptance criteria are observable
- at least one eval exists or preventive work has a reproducible justification
- fixtures are synthetic or sanitized
- database, Windows, and privacy risk are classified
- large or structural work has a focused technical plan

### Mandatory historical non-duplication check

Before implementation starts, every issue must provide all three forms of evidence:

1. Historical evidence: search closed issues, pull requests, and relevant commits for earlier work that addressed the same behavior, root cause, or code path.
2. Current-main evidence: inspect the exact affected code on the current `main` branch and identify why the defect or preventive risk still exists after previous changes.
3. Reproduction evidence: run a focused regression test or deterministic reproduction against current `main` that fails for the expected reason. Preventive work without a failing runtime defect must instead provide executable or structural evidence of the risk.

The outcome controls implementation:

- if current `main` already satisfies the intended behavior, stop implementation and classify the issue as a duplicate, obsolete, or already resolved candidate
- if earlier work solved only part of the problem, update the issue scope to the remaining defect and reference the prior issue, pull request, or commit
- if the reproduction does not fail for the expected reason, do not implement until the issue is revalidated
- only a confirmed remaining defect or evidenced preventive risk may pass Q0

The issue or draft pull request must record the historical references, current-main code path, and reproduction result so the Q0 decision is auditable.

## Q1: local behavior

Every change requires:

- a new test or eval failed for the expected reason before implementation
- focused tests pass after implementation
- related tests pass
- the full test suite passes
- Pyright passes
- `git diff --check` passes
- the complete diff is reviewed
- no personal data or generated artifact enters the commit

Baseline commands:

```bash
python scripts/validate_project_graph.py
python -m pytest path/to/focused_test.py -q
python -m pytest -q
pyright
git diff --check
```

## Q2: database and data

Apply Q2 to writes, transactions, schemas, and migrations:

- backup behavior is tested
- failures are injected at relevant write boundaries
- rollback is proven
- `PRAGMA integrity_check` returns `ok`
- `PRAGMA foreign_key_check` reports no violation
- an old database is converted
- the converted database closes and reopens
- IDs and references remain stable
- recovery is documented

## Q3: files and concurrency

Apply Q3 to watchdog, scheduling, snapshots, and parsers:

- event bursts remain bounded
- duplicate events are coalesced under the documented policy
- canonical Windows paths and aliases share identity
- move events process the correct destination
- partial and replaced files follow explicit behavior
- transient access denial uses bounded retry
- shutdown handles pending work deterministically
- queue, retry, and retention limits are tested

## Q4: Windows and packaging

Apply Q4 to registry, launcher, build, installation, and release work:

- supported Python checks pass
- Windows smoke passes
- PyInstaller build passes
- the executable starts and exposes help when applicable
- paths with spaces and non-ASCII characters are covered
- a machine without the development environment is tested
- installation, upgrade, and rollback are exercised
- release checksums and notes are prepared

## Q5: product decision gates

| Gate | Approval question | Required condition |
|---|---|---|
| A. Reliable data | Does the companion avoid losing, mixing, or inventing data? | Critical integrity backlog, stable real cycles, and tested recovery |
| B. Viable launcher | Does WoFF start and remain observable without fragile automation? | Ten repeatable Windows cycles |
| C. Social RPG | Is the small social core coherent and testable? | Deterministic model, persistent relationships, and safe simulation |
| D. Public release | Does a non-technical user install, use, update, and recover? | Installer, diagnostics, documentation, upgrade, and rollback validated |

## Q6-CYCLE-3.3.0: integrity and ingestion

Issue #50 closes only when all conditions below pass:

- #34, #45, #36, #42, #40, #39, and #27 are complete
- every dependency in `cycle-3.3.0` is satisfied
- all member acceptance criteria are demonstrated
- every applicable eval in `EVAL-CYCLE-330-001` passes
- atomic writes and rollback are proven
- invalid configuration fails before partial startup
- event admission, retries, and pending work remain bounded
- parsers consume stable snapshots
- mission dates, ordering, identity, and enrichment converge deterministically
- dependent pilot files are reprocessed without duplication or silent loss
- focused tests, related tests, full suite, and Pyright pass
- applicable Windows checks pass
- project graph, eval catalog, quality gates, and public documentation are current
- the maintainer approves completion

CI success alone does not close #50 or release 3.3.0.

## Minimum gate matrix

| Change | Minimum gates |
|---|---|
| Documentation without technical effect | Q0 and diff review |
| CLI correction | Q0, Q1 |
| Parser | Q0, Q1, Q3 |
| Database or repository | Q0, Q1, Q2 |
| Watchdog or concurrency | Q0, Q1, Q3, Windows smoke |
| Registry or launcher | Q0, Q1, Q4 |
| Schema | Q0, Q1, Q2, Q4 |
| Release | Q1, applicable Q2, Q3, Q4, and the product gate |

## Pull request evidence

Every draft pull request lists:

- issue and module
- Q0 non-duplication evidence: related historical issues, pull requests, or commits, current-main code path, and reproduction result
- eval IDs
- applicable gates
- exact commands and results
- data and privacy impact
- rollback or recovery path when relevant
- graph changes or a statement explaining why none were required
- known evidence unavailable in the local environment
