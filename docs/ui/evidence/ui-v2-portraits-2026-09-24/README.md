# UI V2 portrait review evidence

Issue: #130
Evidence revision: `UIV2-PORTRAITS-2026-09-24-1`

This directory contains deterministic, sanitized, toolkit-independent review
surfaces generated from the committed portrait package. It contains no player
identity, real campaign data, WoFF screenshot, private path, database content,
log, parser payload, configuration secret, or activation/license information.

## Coverage

`contact-sheet.png` shows:

- the canonical 1120 × 1400 synthetic master with the documented identity safe
  area and eye-line band;
- the standard 140 × 176 and compact 104 × 135 `DOS-01` slots;
- the 142 × 166 `SQD-02` fallback region;
- resolved and unavailable treatments on paper and dark V2 surfaces;
- the required career-switch sequence; and
- the deliberate absence of portraits from `SQD-01`, `OPR-01`, and other
  unapproved consumers.

`scaling-matrix.png` renders the standard `DOS-01` logical slot as static
physical-size equivalents:

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
- the resolved portrait remains legible in every 100–200% static profile;
- the fallback keeps its head/shoulders silhouette and inner border clear in
  standard, compact, paper, and dark-shell contexts; and
- no raster text, insignia, decoration, unit marker, document, aircraft mark,
  or campaign-specific background detail is present.

The fallback silhouette (`#F4EFE2`) reaches 11.15:1 against its neutral tile
(`#2D342D`), and the brass inner boundary (`#C2A86B`) reaches 5.55:1. Visible
`Portrait unavailable` wording remains required, so color is not the only cue.

## Reproduction and integrity

Regenerate from the repository root:

```bash
python -I -S scripts/generate_ui_portrait_evidence.py
```

The generator uses the Python standard library, the two committed canonical
assets, and the Inkscape CLI. Revision 1 was rendered with Inkscape 1.2.2;
another renderer version may produce byte-different antialiasing and requires
fresh visual review before checksums are updated. `SHA256SUMS` covers the two
generated PNG review surfaces.
