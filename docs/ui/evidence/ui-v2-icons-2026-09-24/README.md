# UI V2 icon review evidence

Issue: #129
Evidence revision: `UIV2-ICONS-2026-09-24-1`
Asset source: Microsoft Fluent System Icons at
`8ab43f850c7e8858edf9cb848ba2376f30b7faa3`

This directory contains deterministic, synthetic, toolkit-independent review
surfaces generated from the delivered SVG package. It contains no campaign or
player data, private paths, database content, logs, WoFF payloads, or license
activation data.

## Coverage

`contact-sheet.svg` renders all 16 semantic assignments on both the V2 dark
shell and paper surface. Every semantic is shown at its native 16-, 20-, 24-,
and 32-unit optical master. The context column shows filled current-navigation
variants and regular information/complete/partial/stale/error/unavailable and
action examples with visible text.

Current navigation is demonstrated with the filled icon, the approved raised
or selected surface, and a 2-unit non-focus boundary. Keyboard focus is
not represented in these current/selected examples; no focus token is reused
as a selection token. Navigation and state examples retain visible wording,
and retry/refresh remains a visible-text action.

`scaling-matrix.svg` renders representative current, partial, unavailable, and
error shapes from every logical master at static physical-size equivalents for
Windows 100%, 125%, 150%, and 200%. The resulting dimensions are integral:

| Logical size | 100% | 125% | 150% | 200% |
|---:|---:|---:|---:|---:|
| 16 | 16 | 20 | 24 | 32 |
| 20 | 20 | 25 | 30 | 40 |
| 24 | 24 | 30 | 36 | 48 |
| 32 | 32 | 40 | 48 | 64 |

These are static SVG rendering equivalents. They do **not** prove native
Windows DPI transitions, Qt/PySide6 rendering, keyboard behavior, accessible
names/roles, or screen-reader announcements. Those remain within Issue #82 or
a later authorized production UI.

## Optical inspection

The generated surfaces were inspected at their natural dimensions after an
Inkscape raster pass. Across 16/20/24/32 and the four equivalent scaling rows:

- silhouettes remain distinct and no outer geometry is clipped;
- the Contact Card, People Team, Book Open, Document Data, Database, Info,
  Checkmark Circle, Warning, Clock, Dismiss Circle, and Subtract Circle counters
  remain open;
- back, refresh, and disclosure strokes remain legible without fragile isolated
  one-pixel marks;
- regular and filled navigation variants retain a consistent family weight;
- partial, stale, error, and unavailable remain shape-distinct without color;
  and
- the 16- and 20-unit files visibly use their own simplified geometry rather
  than downscaled 24-unit paths.

The flat token pairs used by the evidence exceed the 3:1 non-text boundary
requirement:

| Foreground / adjacent surface | Contrast |
|---|---:|
| `color.text.on-dark` / `color.shell.aviation` | 14.08:1 |
| `color.accent.brass` / `color.shell.aviation` | 7.01:1 |
| `color.state.info` / `color.shell.aviation` | 6.69:1 |
| `color.state.success` / `color.shell.aviation` | 6.87:1 |
| `color.state.warning` / `color.shell.aviation` | 8.48:1 |
| `color.state.error` / `color.shell.aviation` | 5.30:1 |
| `color.text.ink` / `color.surface.paper` | 11.93:1 |
| `color.text.muted-ink` / `color.surface.paper-raised` | 6.02:1 |

Paper examples deliberately use ink for icon geometry. A future consumer may
use a state token on paper only after measuring the actual rendered adjacent
surface at 3:1 or better. Color is never the only state cue.

## Reproduction and integrity

Regenerate from the repository root:

```text
python scripts/generate_ui_icon_evidence.py
```

The generator uses only the Python standard library. `SHA256SUMS` covers the
two generated SVGs. The asset package has its own checksum manifest.
