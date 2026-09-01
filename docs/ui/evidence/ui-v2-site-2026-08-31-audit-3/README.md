# Published UI V2 conformance evidence

Evidence revision: `UIV2-SITE-2026-08-31-AUDIT-3`

Source: <https://woff-mate-ui-v2.pilotohans.chatgpt.site/>

Published deployment: `appgdep_6a95ebac3afc8191a3913a988ad16ac3`

Saved Site version: `17`

Saved Site version ID:
`appgprj_6a8baac178c88191acc54dde62e1870d~appgver_6b91e8fab2f481919c054576804969cf`

Published source commit: `d96fb6da3e5240919d9dc95fca68f9060c3e9434`

Evidence-set SHA-256: `5ff88aa30e908c3af4049ecd5adf0bae37bf8cbfa34c27516c0ccbace273bfac`

## Revision identity

This revision closes the four evidence gaps found during review of Issue #79:
non-text contrast, complete keyboard behavior, a rendered sparse-slot fixture,
and same-name career isolation for mission, aircrew, and report detail state.
It supersedes Audit 2 as the active acceptance record without modifying that
immutable predecessor.

The mutable Site URL is discovery metadata only. The final record is pinned by
the deployment ID, saved version ID, source commit, evidence revision, and file
hashes in `SHA256SUMS`.

This directory is immutable. A later Site deployment requires a new evidence
directory and revision; these files must not be overwritten.

## Sanitized evidence set

All recorded values are synthetic fixture data. The evidence contains no
personal filesystem path, production database content, log, raw WoFF payload,
credential, cookie, session value, or activation/license information.

| File | Screen or evidence | Contract ID |
|---|---|---|
| `conformance-measurements.json` | Full screen/state/scale, non-text, keyboard, sparse-slot, and isolation measurements | Supporting evidence |

Audit 2 retains the prior twelve-view visual baseline. Audit 3 re-ran all 15
screens, 14 semantic states, and four desktop scales against source version 17
and adds deterministic structured records for every review regression. The
public Site itself is the rendered source; Audit 3 introduces no additional
binary disclosure surface.

## Conformance summary

- all 15 required screen IDs, 14 semantic states, and four desktop scales pass;
- lowest normal-text contrast is `4.55:1` against the `4.5:1` requirement;
- lowest non-text control-boundary contrast is `3.34:1` against the `3:1`
  requirement;
- the two-ring focus treatment measures `5.62:1`, remains at least 3 CSS pixels
  thick, and is visible for every recorded sequential focus stop;
- sequential focus begins with Skip link, Career Selector, then the primary
  navigation; `h1#screen-title` remains a programmatic target outside Tab order;
- Enter, Space, arrow navigation, Escape, modal focus wrapping, and trigger
  focus restoration all pass;
- the deterministic `sparse-slots-2-3` fixture has no `Pilot1` option and keeps
  `WoFF Pilot 2` and `WoFF Pilot 3` at list indexes 0 and 1; and
- switching from RFC `RFC-14A-08F2` to same-name RAF `RAF-41B-22C1` removes the
  old selected mission, aircrew, and report references before showing the RAF
  career.

## Integrity check

After publication, run from this directory:

```console
sha256sum -c SHA256SUMS
```

The evidence-set digest is the SHA-256 of the complete, ordered `SHA256SUMS`
contents. Repository architecture tests verify every member hash and the set
digest.
