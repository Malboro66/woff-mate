# UI V2 portrait package

This directory is the toolkit-independent portrait package for Issue #130. It
contains one generated canonical raster master and one custom neutral vector
fallback. It is presentation material only: no asset is an authoritative source
for identity, nationality, service, branch, squadron, rank, decorations,
victories, injury, career status, death, or historical events.

## Q0 consumer and non-duplication decision

The approved repository contracts justify only these portrait regions:

| Screen | Existing region | Current decision |
|---|---|---|
| `DOS-01` Pilot Dossier | `CareerIdentityHeader`; 140 × 176 logical px in the standard audited layout and 104 × 135 in its compact layout | One resolved synthetic exemplar may be shown for the explicitly mapped `pilot-ready` fixture; all other cases remain eligible for the fallback. |
| `SQD-01` Squadron | Roster/list rows contain textual member identity and disclosure only | No portrait slot and no portrait asset. |
| `SQD-02` Aircrew Profile | Identity region; 142 × 166 logical px in the standard audited layout and 102 × 132 in its compact layout | The current fixture carries no portrait reference, so it demonstrates the fallback. |

`OPR-01` and the other approved screens do not define a portrait slot. No new
screen or consumer is introduced here. The immutable Issue #81 snapshots do not
carry image paths; this package does not alter those contracts. A future
presentation adapter may select an asset only from an explicit, sanitized
mapping and must never derive facts from pixels.

The minimum inventory is therefore **one synthetic exemplar plus one neutral
fallback**. A second face for `SQD-02`, a nationality/rank catalog, roster
thumbnails, and scale-specific raster families would be speculative.

## Canonical master and crop policy

`ui_portrait_synthetic_aster_master.png` is a lossless 1120 × 1400 RGB PNG
(4:5). It was generated at higher-than-minimum source quality and cropped by two
pixels total in each dimension without resampling; it was not upscaled.

- Composition: head and upper torso, quiet studio backdrop, restrained sepia,
  no embedded text or fabricated campaign detail.
- Identity safe area: normalized `x=12–88%`, `y=6–82%`; the head, face, and
  identifying facial features remain inside this region.
- Composition safe area: normalized `x=5–95%`, `y=4–96%`; shoulder edges may
  be clipped decoratively, but not the face or head.
- Eye-line band for this family: `y=29–34%` from the top.
- Approved 4:5 slots use the entire source. The existing 104 × 135 compact
  Dossier slot uses a centered cover crop, removing about 1.9% from each side.
  A future crop may not move the focal point or cut the identity safe area.
- No production derivative sizes are committed. Toolkit-specific caches and
  measured runtime exports remain deferred.

`ui_portrait_unavailable.svg` is an 800 × 1000 (4:5) custom vector tile with an
abstract head-and-shoulders silhouette. It contains no initials, uniform,
headwear, insignia, text, or status cue. Its fixed V2 neutral colors keep the
silhouette readable on both paper content and the dark shell; visible fallback
wording still belongs to the consuming presentation layer.

## Fixture mapping and state safety

The manifest maps only `pilot-ready` on `DOS-01` to the synthetic exemplar.
`aircrew-detail-ready` on `SQD-02` maps to the fallback because the fixture does
not supply a portrait reference. `squadron-ready` has no image consumer.

A portrait association is presentation metadata, never part of the fixture's
authoritative pilot record. The visible name, service, rank, status, and all
other facts must come from the fixture/view model.

Career changes and payload-free states must follow this order:

```text
previous portrait -> clear/replace with loading or fallback -> new resolved portrait
```

The previous portrait must not remain visible while another career is loading,
selected, unavailable, partial without an explicit mapping, or switching. This
is a consumer invariant; Issue #130 adds no production state-management code.

Accessibility names also come from structured visible data:

- resolved: `Portrait of <display name>`;
- unavailable: `Portrait unavailable`.

Do not append inferred rank, service, nationality, squadron, decorations, or
status. A future consuming layer may mark a particular occurrence decorative,
but that choice does not change the data contract.

## Provenance and integrity

`manifest.json` records stable IDs, consumers, fixture mapping, generation,
rights, dimensions, crop rules, accessibility, and prohibited interpretations.
`GENERATION.md` preserves the exact generation prompt and processing record.
`SHA256SUMS` freezes every delivered package file.

The synthetic master uses no input image or real person. The fallback was
custom-authored as repository SVG geometry. Both are distributed under the
repository MIT license; neither requires a third-party attribution or notice.

## Scope boundary

These are source assets only. The package adds no PySide6, PyQt, Qt, web,
image-generation, image-recognition, facial-recognition, SQLite, WoFF-file,
network, parser, repository, launcher, widget, or live-binding runtime path.
Static evidence is not native Windows DPI or Qt rendering evidence; those
questions remain with Issue #82 or later authorized consumer work.
