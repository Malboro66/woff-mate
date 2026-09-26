# WoFF Mate branding and Windows icon review evidence

Issue: #132

Evidence revision: `UIV2-BRANDING-2026-09-24-2`

This directory contains two deterministic, synthetic, toolkit-independent PNG
review composites generated from the canonical vector geometry. It contains no
player identity, campaign data, game screenshot, private path, database
content, log, WoFF payload, configuration secret, or activation/license data.

## Brand review

`brand-review.png` shows the primary wordmark and compact symbol as:

- restrained V2 light/brass wordmark placement on the dark aviation shell;
- a separate genuine light-on-dark monochrome compact symbol with no brass;
- dark-on-light monochrome on the paper surface;
- a clear-space example;
- the 160 px minimum wordmark; and
- the 24 px minimum compact symbol.

The composite demonstrates that the wordmark and symbol are related but not a
cropped copy. Its dark-shell monochrome region contains light geometry only,
so the artifact directly demonstrates that recognition survives without brass.

## Windows icon review

`windows-icon-review.png` distinguishes the complete static target-size matrix
from the embedded ICO entries. It renders 16, 20, 24, 30, 32, 36, 40, 48, 60,
64, 72, 80, 96, and 256 px. Only 16, 24, 32, 48, and 256 px are embedded in the
ICO.

The sheet includes natural and nearest-neighbor 8× views of 16, 20, 24, and 32
px for explicit pixel-level inspection. The single small optical master keeps
open W/M counters, wider strokes, transparent rounded corners, and no inset
border. The 48, 96, and 256 px representative master renders retain the same
silhouette and add the restrained brass inset border.

Representative shortcut, taskbar, and window/app-icon placements are clearly
labeled as **static evidence**. They do not prove native Windows shell,
PyInstaller, Qt, DPI transition, window-manager, keyboard, accessible-name, or
screen-reader behavior. Those measurements remain with Issue #82.

## Optical inspection

The two composites and the ICO entries were inspected at natural size and with
the recorded close views:

- 16 px retains two readable initials without isolated one-pixel ornament;
- 20 and 24 px keep the W valley and M center open;
- 32 px preserves stroke separation with no clipped edge;
- 48, 96, and 256 px retain a consistent monogram, border, and rounded tile;
- all target sizes keep critical geometry inside the tile safe area;
- transparent corner alpha is clean and partially covered pixels retain
  straight-alpha source RGB without a dark fringe; and
- the icon remains identifiable in monochrome geometry without relying on the
  brass accent.

## Reproduction and integrity

Regenerate from the repository root:

```text
python -I -S scripts/generate_branding_assets.py
```

The generator uses only the Python standard library. `SHA256SUMS` covers the
two generated review composites. The asset package has its own checksum
manifest and focused structural validation.
