# UI V2 rendered conformance audit

Status: Passed within the recorded Issue #79 coverage.

Date: 2026-09-01

Eval: `EVAL-UI-DESIGN-001`

## Source and traceability

The active rendered source is the published
[WoFF Mate UI V2 Site](https://woff-mate-ui-v2.pilotohans.chatgpt.site/).
This is a sanitized design/reference prototype, not the production Python UI.
Figma is archival. Audits 1–3 are immutable historical evidence, superseded for
current acceptance because their flags did not enforce the claimed behavior.

- Evidence: [`UIV2-SITE-2026-09-01-AUDIT-4`](evidence/ui-v2-site-2026-09-01-audit-4/README.md).
- Saved version: `18`.
- Source commit: `cf20ea65049682d2fb84f33f329213b93ba0575e`.
- Deployment: `appgdep_6a96d56b15608191b13155cbcb7f7204`.
- Saved version ID: `appgprj_6a8baac178c88191acc54dde62e1870d~appgver_659eb3bc64f081919436991e057f63a7`.
- Deployment API status: `succeeded`.
- Evidence-set SHA-256: `164aabda86d7a7766345c9715d46815ce9c5ec8a4ae7c2e6b30444aabd6d992d`.

The saved archive was built from the tested, committed and pushed source.
The evidence includes actual DOM/style/control observations, the executable
browser driver, paint calculator, regression tests and presentation source
snapshots. `SHA256SUMS` verifies their immutable bytes.

## Method and boundaries

The driver selected every fixture through visible controls in the supervised
preview. It read rendered DOM and computed styles, pressed actual Tab keys,
and activated the four permitted state actions. It did not write DOM state,
force clicks or inspect React internals.

Browser viewport width: 1363 CSS pixels; height: 936 CSS pixels.
Four preview profiles resize a real logical canvas inside this fixed host.
They are not browser zoom labels or native Windows DPI certification.

Text contrast is a conservative lower bound computed from the actual texture
crop under each text rectangle and computed gradients, alpha and inset
shadows. Unsupported paint operations fail closed. The minimum retained text
bound is 4.61:1; required control boundaries measure at least 3.12:1.
The two-ring focus colors give 5.62:1 contrast with 3 px per ring.
These are not screenshot pixel samples. Scroll-clipped nodes are recorded as
excluded, never assigned an invented passing ratio.

Coverage is 60 complete screen/profile cases, 14 representative DOS-01 states
at 100%, 12 DOS-01 pilot-status inputs at 100%, 28 complete Tab sequences at
200%, four state-action flows, 36 fixture-dialog controls, and three same-name
career isolation flows. Text paint covers 86 cases; control boundaries cover
all 15 complete screens at 200%. Modal contrast and a full 15×14×4 semantic
cross-product are not claimed. Screen-reader/native-toolkit audits remain
separate work.

## Actual profile changes

| Profile | Logical cap | Actual canvas | Rail | Dossier stat columns | Side below ledger |
|---|---|---|---:|---:|---|
| Desktop 100% | 1440×1024 | 1363×936 | 256 | 6 | No |
| Desktop 125% | 1152×819 | 1152×819 | 232 | 3 | Yes |
| Desktop 150% | 960×683 | 960×683 | 232 | 3 | Yes |
| Desktop 200% | 720×512 | 720×512 | 184 | 2 | Yes |

Shell/main client and scroll widths match in every captured profile. There
are no measured text sizes below 12 px. A stuck canvas, unchanged rail,
incorrect column count or unchanged side placement fails the executable test.

## Screen and read-only control inventory

Counts below exclude the ten shell controls, which are also individually
recorded and checked. Contrast is the minimum of each screen's four profile
captures, rounded down. The JSON retains full precision.

| Screen | Main interactive controls | Text lower bound |
|---|---|---:|
| `APP-00` | 0 | 5.18:1 |
| `SEL-01` | 2 stable-slot career options | 5.18:1 |
| `OPR-01` | 6 owned mission/aircrew links | 4.61:1 |
| `DOS-01` | 3 dossier-context links | 5.18:1 |
| `DOS-02` | 1 return to Dossier | 4.83:1 |
| `DOS-03` | 1 return to Dossier | 5.05:1 |
| `DOS-04` | 1 return to Dossier | 4.83:1 |
| `MIS-01` | 4 filters + 5 record rows | 4.68:1 |
| `MIS-02` | 1 return to Mission Log | 4.86:1 |
| `SQD-01` | 4 filters + 11 aircrew rows | 4.68:1 |
| `SQD-02` | 1 return to Squadron | 4.67:1 |
| `JRN-01` | 4 filters + 5 mission links | 4.68:1 |
| `RPT-01` | 4 filters + 4 report links | 4.68:1 |
| `RPT-02` | 1 return to Reports | 5.08:1 |
| `SYS-01` | 5 status filters | 4.68:1 |

Every discovered interactive control has its role, accessible name, action
purpose, href, tabindex and bounding rectangle recorded. Unknown purposes or
write/session controls fail; tests inject Edit, Delete, Import, Reset, Launch,
Save, Repair and other prohibited actions on every required screen.
Minimum observed target width is 54.671875 px and height is 40 px.
The contract enforces ≥32×32 and primary height ≥40, per control and profile.

## Complete keyboard coverage

The shell order is Skip, career selector, Operations, Pilot Dossier, Missions,
Squadron, War Diary, Reports, Data & System Status, then Fixture matrix.
The latter is a prototype-only control. Each recorded sequence continues
through contextual returns, links, filters, record rows and state actions to
the final control. The 15 complete screens plus 13 exceptional Dossier states
give 28 sequences; observations retain every stop's visible focus and viewport
presence. `h1#screen-title` has tabindex −1 and receives destination focus;
it is never a sequential Tab stop.

The fixture dialog records all 36 controls, visible focus, forward/reverse
wrapping and Escape restoration. Its native status select receives visible
focus. Earlier career-selector Space/ArrowDown/Escape results remain historical
and are not newly certified by this run.

## State and status semantics

For every shared state, the capture retains displayed fields, their typed
states, collection counts, text, sanitized reason and permitted controls.

- Complete retains six authoritative values; empty collections retain unrelated
  career totals and do not become missing records.
- Loading and absent/invalid-source states contain no previous record values,
  no borrowed events/victories and no false valid-empty collections.
- Partial retains known fields and distinguishes unavailable, unknown and invalid.
- Zeroes remain explicit values; unknown values never become zero.
- No-career clears identity and offers Select career.
- Missing, truncated, unsupported, unreadable and unavailable have distinct reasons.
- Error offers Retry view and View data status without paths, payloads or raw exceptions.
- Stale retains the safe older snapshot and the 14 AUG 1917 · 23:41 timestamp,
  explicitly labels it non-current, and offers Refresh snapshot.
- Retry/refresh were observed before, during cleared loading, and after recovery;
  status navigation reached SYS-01 and Select career recovered the same career.

The eight normalized pilot statuses were separately rendered and checked:
`Active`, `KIA` → Killed in Action (KIA), `PoW` → Prisoner of War (PoW),
`MIA` → Missing in Action (MIA), `Invalided Out`, `Survived War`,
`Lightly Wounded`, and `Seriously Wounded`.
Missing, blank and unavailable input map to Unknown. The future value
Transferred (future) remains verbatim with an unsupported-mapping notice.
Source input, visible label and accessibility label are all recorded;
collapsing wound severity or changing only the accessibility label fails.

## Career and source-slot isolation

Changing from RFC career `RFC-14A-08F2` to same-name RAF career
`RAF-41B-22C1` was exercised independently from mission, aircrew and report
detail. Each old reference is visible first, absent after selection, and absent
when its detail route is reopened. The resulting RAF view shows WoFF Pilot 2,
41 Squadron and Bertangles. No claim is made about capturing the transient
animation frame between those observations.

The standalone sparse selector contains only WoFF Pilot 2 / RAF-41B-22C1 and
WoFF Pilot 3 / CAREER-14B8. It never derives a slot label from list position.
Slot-vacancy reconciliation and same-slot generation detection are backend
issues, not implemented by this design evidence.

## Enforcement and decision

`scripts/validate_ui_v2_evidence.py` verifies exact coverage, measured
geometry, state semantics, status labels, per-control targets/purposes, full
Tab order, action outcomes, contextual isolation and recomputed retained
contrast bounds. `test_ui_v2_evidence.py` deliberately corrupts each reviewed
contract and requires rejection. The architecture contract checks governance,
links, immutable source/measurement hashes and all historical manifests.

The pinned Site source passed 51 tests, its app-only TypeScript check and its
production build. Python CI replays the archive; it does not contact or
certify the mutable live Site. A changed Site source requires a fresh rendered
run and a new immutable evidence revision.

`EVAL-UI-DESIGN-001` passes and is implemented for this bounded design
acceptance. Issue #79 may close through PR #124 after review and merge.
This does not implement #80, #81, #82 or #122, adopt a GUI toolkit, approve a
Product Gate, or complete a release/cycle. No real campaign data or credentials
are present, and no Python production/runtime dependency is changed.
