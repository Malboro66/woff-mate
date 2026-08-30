# Published UI V2 audit evidence

Evidence revision: `UIV2-SITE-2026-08-29-AUDIT-1`

Source: <https://woff-mate-ui-v2.pilotohans.chatgpt.site/>

Published deployment: `69c0abd6-d843-4646-b141-f76723098421`

Evidence-set SHA-256: `ef028e0f8a49663c1a5b7d835b61f4c5128b238a7dde0df0e0f8633d0892b161`

## Revision identity

The Site exposes the published deployment identifier in
`__artifactCompatibility.deploymentVersion`. It was read from the rendered
document on 2026-08-30 at 17:40 UTC, while the audited revision remained
published. The same document identified these build assets:

- stylesheet: `/assets/index-0Bx3PLow.css`;
- application bundle: `/assets/index-DGp2Itys.js`; and
- page bundle: `/assets/page-CpvFe6eO.js`.

The mutable Site URL is discovery metadata only. Review evidence is pinned by
the deployment identifier, this evidence revision, the repository commit, and
the file hashes in [SHA256SUMS](SHA256SUMS). A later Site deployment requires a
new evidence directory and revision; these files must not be overwritten.

## Sanitized capture set

All visible values are synthetic fixture data. The captures contain no personal
filesystem path, production database content, log, raw WoFF payload, credential,
cookie, session value, or activation/license information.

| File | Screen or evidence | Contract ID |
|---|---|---|
| `01-operations.jpg` | Operations Board | `OPR-01` |
| `02-pilot.jpg` | Pilot Dossier | `DOS-01` |
| `03-missions.jpg` | Mission Log | `MIS-01` |
| `04-diary.jpg` | War Diary | `JRN-01` |
| `05-reports.jpg` | Reports Library | `RPT-01` |
| `06-squadron.jpg` | Squadron Roster | `SQD-01` |
| `07-system-status.jpg` | Data & System Status | `SYS-01` |
| `08-mission-report.jpg` | Mission Report | `MIS-02` |
| `09-career-selector.jpg` | Career Selector overlay | `SEL-01` |
| `10-aircrew-profile.jpg` | Aircrew Profile | `SQD-02` |
| `11-report-viewer.jpg` | Report Viewer | `RPT-02` |
| `12-fixture-matrix.jpg` | Published fixture matrix | Supporting evidence |
| `contrast-measurements.json` | Computed styles and rendered-background measurements | Supporting evidence |

The browser viewport was 1363 by 936 CSS pixels at device-pixel ratio 1. The
Site displayed its `Desktop 100%` fixture profile. Full-page captures have
different image heights as content extends below the viewport. The capture
transport produced JPEG data; the archived `.jpg` names reflect the actual
media type.

## Integrity check

Run from this directory:

```console
sha256sum -c SHA256SUMS
```

The evidence-set digest is the SHA-256 of the complete, ordered `SHA256SUMS`
contents. Repository architecture tests verify every member hash and the set
digest.
