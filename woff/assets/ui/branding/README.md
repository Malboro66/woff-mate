# WoFF Mate product identity package

This directory contains the toolkit-independent product identity and Windows
application-icon sources for Issue #132. SVG is canonical. The ICO is a
deterministic distribution derivative for future Issue #82 consumption; it is
not wired into the current launcher, installer, PyInstaller spec, or runtime.

The eight committed SVG files are the authoritative editable artwork. Edit
them intentionally and review the diff directly. The derivative generator
validates and consumes their constrained geometry; it never rewrites them.

## Identity

The selected **plot-and-ledger** direction combines an angular plotted `W`
with a columnar `M`. Shared WM geometry and rounded line treatment connect the
compact monogram to the custom wordmark. Registry rules are
composition-specific: the V2 compact symbol uses a central rule, while the
terminal square belongs only to the wordmark's extended registry line. The
construction is original vector geometry: it uses no font file, live SVG text,
traced artwork, stock mark, third-party logo, aircraft, wing, wreath, shield,
crown, ribbon, medal, roundel, or service emblem.

The dark and light files are complete one-color marks. The V2 variant adds
only the approved brass token to the registry details; recognition does not
depend on it. The restrained color variant exists because it materially ties
representative dark-shell placement and the Windows tile to the approved V2
system without introducing status color or a second visual language.

## Windows icon

`woff_mate_app_icon_master.svg` is the canonical square source for 48 px and
larger targets. `woff_mate_app_icon_small.svg` is the only optical variant and
serves 16, 20, 24, 30, 32, 36, and 40 px. It widens the WM strokes and counters
and removes the inset border. Both retain the same monogram, palette, rounded
tile, and silhouette.

The opaque aviation-shell tile was chosen after static review because it keeps
the light monogram legible on both light and dark Windows backgrounds. The
rounded corners outside the tile remain transparent. Critical WM geometry
stays within the central 75%. The master uses nested filled rounded rectangles
with outer bounds `72..952` and inner bounds `96..928`, so its 7.03125% margin
is preserved in raster derivatives rendered directly from the canonical SVG.

`woff_mate_app.ico` contains exactly 16, 24, 32, 48, and 256 px PNG-compressed
32-bit straight-alpha RGBA entries. The first three use the small optical
master; 48 and 256 use the canonical master. Other target sizes are review
exports, not additional ICO entries.

## Reproduction

From the repository root:

```text
python -I -S scripts/generate_branding_assets.py
```

The generator uses only the Python standard library. It reads the clean,
self-contained canonical SVGs and writes only the ICO, the two metadata-free
PNG review composites, and their SHA-256 inventories. Ordinary regeneration
never authors or modifies canonical artwork. Unsupported SVG elements,
attributes, path commands, transforms, effects, references, or colors fail
closed instead of being silently ignored. `SHA256SUMS` freezes every delivered
package file.

## Boundaries

The mark is product identity, not part of the Issue #129 semantic icon family.
It must not encode a pilot face, pilot nationality, military service, squadron
badge, rank insignia, qualification wing, national roundel, decoration, or UI
state. The legacy root `icon.png` is neither a source nor an approved variant.

No production GUI, web, image-generation, launcher, session, installer,
PyInstaller, database, WoFF-file, parser, repository, or network dependency is
introduced here. Native packaging, shortcut, taskbar, window-icon, DPI, and
clean-machine validation remain with Issue #82.
