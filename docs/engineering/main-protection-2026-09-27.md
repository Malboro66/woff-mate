# Main protection enforcement record — 2026-09-27

## Revision-bound administrative evidence

| Field | Verified value |
|---|---|
| Administrative configuration date | 2026-09-27 |
| Repository | `Malboro66/woff-mate` |
| Governance owner | Issue #152 |
| Pre-change `main` SHA | `74d3576e87efb112b1f42cc07100d496ff66bcd1` |
| Ruleset | `24065034` — `Protect main and require CI` |
| Enforcement state | `active` |
| Target | Repository default branch (`~DEFAULT_BRANCH`), resolving to `main` |
| Pull requests | Required |
| Required approving reviews | `0` |
| Review thread resolution | Not required |
| CODEOWNERS review | Not required |
| Last-push approval | Not required |
| Branch up to date before merge | Not required |
| Force pushes | Blocked by the `non_fast_forward` rule |
| Branch deletion | Blocked by the `deletion` rule |
| Bypass | No configured bypass actors |
| Allowed merge methods | Merge, squash, and rebase |

The required checks are exactly:

- `Tests (Python 3.10)`
- `Tests (Python 3.14)`
- `Pyright`
- `Windows smoke test`

Each required check is bound to GitHub App integration ID `15368`. Read-only
verification of the checks on the recorded `main` SHA identified that app as
GitHub Actions (`github-actions`), and every check completed successfully.

## Verification result and evidence boundary

Post-configuration read-only verification on 2026-09-27 confirmed that ruleset
`24065034` still existed with the name, active state, target, empty bypass list,
pull-request policy, exact required checks, integration IDs, merge methods,
force-push block, and deletion block recorded above. The current workflow at
`.github/workflows/ci.yml` produces the same authoritative check names.

The active GitHub ruleset is the live enforcement mechanism. Repository tests
do not call GitHub and do not independently enforce branch settings; they only
protect this immutable snapshot and the related governance state from internal
drift. The effective rule can be inspected at
`https://github.com/Malboro66/woff-mate/rules/24065034?ref=refs%2Fheads%2Fmain`.

This record is the later remediation of the historical finding in the
[2026-09-10 Security Baseline](security-baseline-2026-09-10.md), whose audited
revision correctly had no active protection. Product Gate A remains NOT
APPROVED. This remediation does not approve Gate A, R2, any Product Gate, a UI
toolkit, the PySide6 ADR, or a release.
