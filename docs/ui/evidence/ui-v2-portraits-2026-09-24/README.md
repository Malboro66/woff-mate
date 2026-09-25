# UI V2 portrait review evidence

Issue: #130
Evidence revision: `UIV2-PORTRAITS-2026-09-24-2`

This directory contains deterministic, sanitized, toolkit-independent review
surfaces generated from the committed portrait package. It contains no player
identity, real campaign data, WoFF screenshot, private path, database content,
log, parser payload, configuration secret, or activation/license information.
The `source/` subdirectory separately preserves the exact generated original as
provenance evidence; it is not a runtime asset or production derivative.

## Coverage

`contact-sheet.png` shows:

- the canonical 1120 × 1400 synthetic master with the documented identity safe
  area and eye-line band;
- the standard 140 × 176 and compact 104 × 135 `DOS-01` slots;
- the standard 142 × 166 and compact 102 × 132 `SQD-02` fallback regions;
- resolved and unavailable treatments on paper and dark V2 surfaces;
- the required career-switch sequence; and
- the deliberate absence of portraits from `SQD-01`, `OPR-01`, and other
  unapproved consumers.

`scaling-matrix.png` renders only the standard `DOS-01` logical slot as a
representative static physical-size matrix:

| Profile | Resolved/fallback slot |
|---:|---:|
| 100% | 140 × 176 px |
| 125% | 175 × 220 px |
| 150% | 210 × 264 px |
| 200% | 280 × 352 px |

The two PNGs are disposable review composites, not production portrait
derivatives. The generator embeds the exact canonical package bytes in a
temporary self-contained SVG, rasterizes the complete review canvas, and
discards the temporary source. It does not create a family of portrait sizes.
The matrix is not exhaustive evidence for every declared consumer slot or every
native Windows/Qt render size; the contact sheet provides the approved-slot
coverage owned by this issue.

## Review boundary

These files demonstrate composition, crop safety, fallback geometry, static
surface compatibility, and integer equivalents of the four logical profiles.
They do **not** prove native Windows DPI transitions, device-pixel-ratio
behavior, Qt/PySide6 decoding, native raster quality, caching performance,
keyboard behavior, accessible names/roles, or screen-reader announcements.
Those remain Issue #82 or later authorized consumer work.

## Optical inspection

Both generated surfaces were rendered with Inkscape at their natural canvas
dimensions and inspected after regeneration:

- the face and entire head remain inside the documented identity safe area;
- the 104 × 135 centered compact crop retains the face, hair, neck, and both
  shoulders without moving the focal point;
- the 102 × 132 compact `SQD-02` fallback keeps the complete neutral head and
  shoulders geometry and the visible `Portrait unavailable` treatment;
- the resolved portrait remains legible in every 100–200% static profile;
- the fallback keeps its head/shoulders silhouette and inner border clear in
  standard, compact, paper, and dark-shell contexts; and
- no raster text, insignia, decoration, unit marker, document, aircraft mark,
  or campaign-specific background detail is present.

The fallback silhouette (`#F4EFE2`) reaches 11.15:1 against its neutral tile
(`#2D342D`), and the brass inner boundary (`#C2A86B`) reaches 5.55:1. Visible
`Portrait unavailable` wording remains required, so color is not the only cue.

## Reproduction and integrity

`source/ui_portrait_synthetic_aster_original.png` is the exact 1122 × 1402 RGB
generation output (SHA-256
`ecc9c17596aa2d9d8c4b807844190d1936092a901e9fd56d22aeaed48803404b`).
Removing exactly one pixel from each edge yields pixel content identical to the
1120 × 1400 canonical master. The source is retained only for provenance and is
deliberately outside `woff/` so package-data rules do not install it.

Regenerate from the repository root:

```bash
python -I -S scripts/generate_ui_portrait_evidence.py
```

The generator uses the Python standard library, the two committed canonical
assets, and the Inkscape CLI. Revision 1 was rendered with Inkscape 1.2.2;
another renderer version may produce byte-different antialiasing and requires
fresh visual review before checksums are updated. `SHA256SUMS` covers the exact
original source and both generated PNG review surfaces.
