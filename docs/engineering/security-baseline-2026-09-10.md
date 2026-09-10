# Security Baseline — 2026-09-10

## Revision-bound result

| Field | Recorded value |
|---|---|
| Audit date | 2026-09-10 |
| Audited integrated revision | `736c43df86d686c07aadd549c14105feaf59f89d` (`main`) |
| P0 findings | None confirmed |
| P1 adversarial-security defects | None confirmed |
| Product Gate A | **NOT APPROVED** |
| Public distribution | **NOT APPROVED** |

This concise record preserves the repository-governance outcome of the read-only
Security Baseline Audit. The underlying deterministic reproductions, repository
observations, and focused issues are the evidence; model-generated assessment is
not stronger evidence than those sources.

## Finding ownership

- The three confirmed P1 data-safety defects remain owned by #96, #74, and #142.
- The newly reproduced P2 output/input path-isolation defect is owned by #151.
- The unprotected `main` repository-control gap is owned by #152. The audit found
  no active branch protection or ruleset for `main`; this record does not claim
  that GitHub settings have since changed.
- #153 owns staged P3 reproducible dependency, vulnerability-audit, immutable
  GitHub Action, and controlled-update policy work.
- #154 owns staged P3 WoFF-specific threat-model and compact Security Gate work.
- #155 owns staged P3 release provenance, checksums, SBOM/provenance evidence,
  and the code-signing decision before the first public binary distribution.

The audit found that local-only privacy controls remained effective and found no
live credentials. Product Gate A and public distribution remain unapproved.

## Scheduling and cycle disposition

| Issue | Classification and required disposition | Cycle decision |
|---|---|---|
| #151 | P2 data-safety defect in `platform`; complete before Gate A can claim safe operation against real WoFF roots. It does not supersede the existing P1 Gate A correction order. | Not added to a Q6 cycle |
| #152 | P2 repository-governance control; enforce and verify `main` pull-request/check requirements plus force-push/deletion protection before the next Product Gate approval. It is not an application or data-integrity defect. | Not added to a Q6 cycle |
| #153 | P3 supply-chain hardening; complete before release-oriented product work becomes active, unless a concrete vulnerability requires earlier action. It is not a current Gate A blocker. | Not added to a Q6 cycle |
| #154 | P3 security governance; the future threat model and compact Security Gate must compose with Q0-Q6 instead of creating a second workflow. This reconciliation does not implement that gate. | Not added to a Q6 cycle |
| #155 | P3 pre-release work; complete before the first public binary distribution. It is not a current Gate A blocker or active development priority. | Not added to a Q6 cycle |

Security adds guardrails and justified blockers; it does not create a second
roadmap. Registration in the graph is separate from engineering-cycle
membership, and this audit creates no security milestone.

