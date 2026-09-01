# UI V2 executable conformance evidence

Evidence revision: `UIV2-SITE-2026-09-01-AUDIT-4`

Date: 2026-09-01

Status: Passed within the recorded coverage below.

This is synthetic fixture data from the Issue #79 design/reference prototype,
not campaign data, a production UI, or a toolkit decision. It supersedes Audit
3 as current acceptance evidence. Audit 1–3 remain byte-identical historical
artifacts; their earlier success claims do not replace these observations.

## Source and publication

- Site: [WoFF Mate UI V2](https://woff-mate-ui-v2.pilotohans.chatgpt.site/)
- Saved version: `18`
- Source commit: `cf20ea65049682d2fb84f33f329213b93ba0575e`
- Saved version ID: `appgprj_6a8baac178c88191acc54dde62e1870d~appgver_659eb3bc64f081919436991e057f63a7`
- Deployment: `appgdep_6a96d56b15608191b13155cbcb7f7204`
- Deployment status: `succeeded`, checked through the Sites deployment API.
- Evidence-set SHA-256: `164aabda86d7a7766345c9715d46815ce9c5ec8a4ae7c2e6b30444aabd6d992d`

The source was built, tested, committed, and pushed before saving the version.
The deployment packages that exact source. `source/` contains byte-for-byte
copies of the three presentation files, layout, package manifest, browser
driver, paint collector/calculator, tests, and reproduction instructions.
It is an archival snapshot, not code imported by the Python application.

`SHA256SUMS` covers the measurements and all 14 source files. The set digest
is SHA-256 of the manifest's ordered lines, each ending in LF. This README
is excluded to avoid a circular digest. Texture hashes are recorded separately
in the measurements; existing texture assets were not changed or re-uploaded.

## What was observed

| Review concern | Observations and executable rejection |
|---|---|
| Actual scaling | All 15 complete screens at four logical profiles; measured canvas, rail, overflow, Dossier columns and side-column position. A stuck profile or wrong geometry fails. |
| Full keyboard order | 28 complete screen/state sequences at 200%, continuing through the last main-content/action control; 36 modal controls, wrap and Escape restoration. Omitted, reordered or unfocused stops fail. |
| State semantics | All 14 shared states on DOS-01: visible values, absence of unvalidated values, field states, empty/unknown collections, sanitized text, permitted actions, and four action outcomes. |
| Pilot status | Eight normalized values plus missing, blank, unavailable and future value; visible text, accessible label, source value and unsupported-mapping explanation. |
| Pointer targets | Every discovered control on all 60 screen/profile cases; width ≥32, height ≥32, primary height ≥40 CSS px; modal targets also measured. |
| Read-only scope | Native interactive elements and ARIA roles, names, purposes, hrefs and exact main-control inventories. Unknown or prohibited write/session controls fail. |

The `sparse-slots-2-3` fixture has no `Pilot1` option: its first and second
items remain `WoFF Pilot 2` and `WoFF Pilot 3`. Three contextual isolation
flows record the RFC mission, aircrew and report before switching to RAF,
their absence afterward, and their absence after reopening the detail route.

The text contrast collector calculated conservative lower bounds for 86 cases
(60 complete surfaces, 14 states, 12 statuses). Minimum: 4.6137125392619245:1.
Required control-boundary minimum across 15 complete surfaces at 200%:
3.122832785229489:1. The replay recomputes the retained lowest RGB-bound ratios
and every recorded boundary ratio, rather than accepting a `passed` flag.

## Reproduction

From the Python repository:

```sh
python scripts/validate_ui_v2_evidence.py
python -m pytest woff/tests/test_ui_v2_evidence.py woff/tests/test_architecture_contracts.py -q
```

For a fresh browser run, use the exact Site source commit and
[`source/tests/README.md`](source/tests/README.md). Its `acceptanceCases` driver
uses visible controls and actual keyboard events, with read-only DOM/style
observation. It does not manufacture UI state or read React internals.
The committed Site checks passed 51 tests, the app-only TypeScript check and
the production build before publication.

## Explicit limits

- Python CI replays an immutable capture and checks hashes. It does not open
  or certify the current mutable public Site. Any source change requires a
  fresh rendered run and a new evidence revision.
- Profiles change the logical canvas, not host OS DPI. The host viewport was
  1363×936 CSS px. Native Windows/DPI/toolkit work remains outside #79.
- Shared semantic states use representative DOS-01, not a 15×14×4 cross-product.
- Contrast uses actual texture-crop bounds and computed compositing, not
  screenshot pixel sampling. Scroll-clipped text is explicitly excluded,
  never assigned an invented passing ratio. Modal contrast is not certified.
- Isolation captures before/after/reopened views, not a transient animation
  frame. Old selector Space/ArrowDown/Escape claims are historical, not newly
  certified by Audit 4. The modal's keyboard behavior is freshly recorded.
- No screen-reader or comprehensive WCAG certification is claimed. This is
  evidence for the recorded Issue #79 contracts only.

Issues #80, #81, #82 and #122, Product Gates and cycle-level completion remain
separate work. This revision does not implement or close them.
