# Published UI V2 conformance evidence

Evidence revision: `UIV2-SITE-2026-08-31-AUDIT-2`

Source: <https://woff-mate-ui-v2.pilotohans.chatgpt.site/>

Published deployment: `appgdep_6a9555f927b081919b6cc2f33e9f3ffb`

Saved Site version: `16`

Published source commit: `07cc3397ac9a9204c6540becaf57ffcaad3c8897`

Evidence-set SHA-256: `a64fd0e67383d3cf828ec33edc225fde18df1a710833b648a838222938ee5ce9`

## Revision identity

The deployment status was read directly after publication and reported
`succeeded` for the deployment and saved version above. The mutable Site URL is
discovery metadata only. Review evidence is pinned by the deployment ID, saved
version, published source commit, evidence revision, and the file hashes in
[SHA256SUMS](SHA256SUMS).

This directory is immutable. A later Site deployment requires a new evidence
directory and revision; these files must not be overwritten.

## Sanitized capture set

All visible values are synthetic fixture data. The captures contain no personal
filesystem path, production database content, log, raw WoFF payload, credential,
cookie, session value, or activation/license information.

| File | Screen or evidence | Contract ID |
|---|---|---|
| `01-operations.jpg` | Operations Board | `OPR-01` |
| `02-pilot.jpg` | Pilot Dossier | `DOS-01` |
| `03-missions.jpg` | Mission Log | `MIS-01` |
| `04-squadron.jpg` | Squadron Roster | `SQD-01` |
| `05-diary.jpg` | War Diary | `JRN-01` |
| `06-reports.jpg` | Reports Library | `RPT-01` |
| `07-system-status.jpg` | Data & System Status | `SYS-01` |
| `08-mission-report.jpg` | Mission Report | `MIS-02` |
| `09-career-selector.jpg` | Same-name Career Selector | `SEL-01` |
| `10-fixture-matrix.jpg` | Fifteen-screen fixture matrix | Supporting evidence |
| `11-aircrew-profile.jpg` | Aircrew Profile | `SQD-02` |
| `12-report-viewer.jpg` | Report Viewer | `RPT-02` |
| `contrast-measurements.json` | Screen, state, scale, and interaction measurements | Supporting evidence |

The browser viewport was 1363 CSS pixels wide at device-pixel ratio 1. The
captured views use the Site's `Desktop 100%` fixture profile. Scale checks also
applied the 125%, 150%, and 200% profiles. The capture transport produced JPEG
data; the archived `.jpg` names reflect the actual media type.

## Conformance summary

- all 15 required screen IDs are available through the published fixture
  matrix;
- the lowest measured normal-text ratio across the required screens was
  4.55:1, against a 4.5:1 requirement;
- all 14 semantic states passed on the representative Pilot Dossier surface;
- all four desktop scale profiles passed without core horizontal overflow;
- meaningful text remained at or above 12 CSS pixels;
- primary navigation and fixture application focused `h1#screen-title` with
  `tabindex="-1"`;
- changing from the RFC `Arthur Bennett` career to the same-name RAF career
  removed the previous mission and squadron before presenting `WoFF Pilot 2`,
  `RAF-41B-22C1`, 41 Squadron RAF, and Bertangles; and
- `PilotN` remains a persistent simulator slot label, while `career_id` remains
  the immutable career identity.

## Integrity check

Run from this directory:

```console
sha256sum -c SHA256SUMS
```

The evidence-set digest is the SHA-256 of the complete, ordered `SHA256SUMS`
contents. Repository architecture tests verify every member hash and the set
digest.
