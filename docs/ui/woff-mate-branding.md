# WoFF Mate product identity and Windows application icon

Status: Issue #132 implementation contract

Baseline: `40e19ee1c2c7f7a9f3eda8bcceb8c75aba633d29` (`origin/main` on
2026-09-24)

## Q0 identity decision

Three bounded directions were considered:

1. **Plot-and-ledger monogram — selected.** An angular `W` reads as a plotted
   operational route; a columnar `M` reads as an orderly register. A narrow
   rule connects the monogram to custom drafting-like lettering.
2. **Dispatch-tab letterform — rejected.** It was restrained but generic and
   depended on an enclosing filing-tab silhouette rather than the product
   initials.
3. **Aerial-route monoline — rejected.** It was simple, but could read as a
   literal aircraft trajectory and lost its relationship to the product name
   at small sizes.

The selected concept communicates WoFF Mate as the operational companion where
plotted activity becomes a clear record. It reflects **Operations Room 1917**
through plotting geometry, registry rules, restrained ink and brass, and
drafting-like proportions—not artificial aging, a literal aircraft, or a
military badge. The wordmark and compact symbol share the WM geometry and
rounded line treatment while remaining separate compositions. Registry rules
are used where the composition benefits from them: the V2 compact symbol has a
central rule, while the wordmark extends its registry line to a wordmark-only
terminal square. That square is not a compact-symbol primitive.

Recognition comes from silhouette and geometry, so both marks work in one
color. The optional V2 treatment uses only light ink plus restrained brass and
is justified for representative dark-shell placement and the self-contained
Windows tile. Brass is not required for recognition and never denotes state.

The Windows icon uses the same monogram but is not a mechanical crop of the
wordmark. One small optical master widens strokes and counters and removes the
inset border for 16–40 px. No per-size vector family is necessary.

## Typography and provenance

All lettering is original custom vector geometry created for Issue #132. It
does not begin from a font, includes no SVG `<text>` element, and requires no
font file at design time or runtime. Canonical SVGs, generated derivatives,
and documentation are distributed under the repository MIT license with no
additional attribution or notice obligation.

The work does not copy, trace, redraw, or adapt a third-party logo or insignia.
The existing root `icon.png` was inspected only for duplication and conflict;
its winged-insignia construction is explicitly excluded and none of its pixels
or geometry are reused.

## Similarity review

This was a reasonable visual-design and provenance review, not legal trademark
clearance. Public references were inspected without copying or committing
their artwork:

- **Wings Over Flanders Fields / OFF:** the official OBD site and current box
  presentations use photographic combat aviation, ribbon title treatments,
  decorative serif/display lettering, and in some products medal/wreath-like
  devices. The selected mark uses none of those structures.
- **Rise of Flight:** the official product identity centers dramatic aircraft
  imagery and large flight-title treatment. The selected mark is an abstract
  administrative WM construction with no aircraft or sky imagery.
- **Flying Circus / IL-2:** the official product family emphasizes aircraft,
  national markings, combat scenes, and a separate established IL-2 title
  system. The selected mark shares neither its silhouette nor title treatment.
- **Common pilot-wing and military-badge silhouettes:** RAF Museum and
  Smithsonian descriptions show the characteristic outstretched wings,
  central monogram, wreath, and crown vocabulary. The selected mark avoids
  bilateral wings, feathers, wreaths, crowns, shields, service letters, and
  heraldic enclosure.
- **Legacy root `icon.png`:** its winged red monogram reads as a pilot-wing or
  qualification-badge form and is not an approved source or variant.

Conclusion: the selected mark is visually separated from WoFF/OFF game
branding, obvious WWI flight-simulator identities, and common military
qualification badges by its asymmetric plotted/ledger construction, plain
software tile, and absence of literal aviation or heraldic elements.

References consulted on 2026-09-24:

- <https://overflandersfields.com/>
- <https://riseofflight.com/>
- <https://il2sturmovik.com/media/>
- <https://www.rafmuseum.org.uk/research/online-exhibitions/taking-flight/historical-periods/pilots-wings/>
- <https://airandspace.si.edu/collection-objects/badge-pilot-royal-flying-corps/nasm_A19711761000>

## Geometry and usage

- Wordmark viewBox: `0 0 768 192`.
- Compact-symbol viewBox: `0 0 256 256`.
- App-icon master and small-master viewBox: `0 0 1024 1024`.
- Wordmark clear space: at least one 16/256 symbol-unit divider width on all
  sides at the mark's rendered scale.
- Compact-symbol clear space: at least 32/256 symbol units on all sides.
- Recommended minimum wordmark width: 160 px.
- Recommended minimum compact-symbol size: 24 × 24 px.
- Dark shell: use the light monochrome or restrained V2 variant.
- Light/paper: use the dark monochrome variant.

Do not stretch, condense, skew, rotate, outline, shadow, or rearrange the mark.
Do not add gradients, bevels, distress, extra colors, wings, aircraft, wreaths,
shields, crowns, ribbons, medals, service letters, or roundels. Do not recolor
the mark with semantic information, success, warning, error, stale, or
unavailable tokens.

## Windows icon generation and review

The canonical master uses an aviation-shell tile with transparent rounded
corners, a light WM, a restrained brass border, and a brass registry rule. The
SVG and raster source both construct that border as nested filled rounded
rectangles: brass outer bounds `72..952` with radius `150`, then aviation-shell
inner bounds `96..928` with radius `126`. No centered stroke can paint beyond
the declared outer bounds. An opaque tile is deliberately superior here
because it preserves contrast across uncontrolled light and dark shell
backgrounds. The critical monogram remains inside the central 75%; the master
tile's exact 72/1024 margin is 7.03125% on every side.

The small optical master serves 16, 20, 24, 30, 32, 36, and 40 px. It preserves
the same silhouette while widening the strokes, opening counters, and removing
the fragile inset border. The canonical master serves 48, 60, 64, 72, 80, 96,
and 256 px in static review.

The ICO contains only the required entries: 16, 24, 32, 48, and 256 px. Entries
are PNG-compressed 32-bit straight-alpha RGBA images with transparent corners.
Partially transparent edge pixels retain unpremultiplied source RGB. The 20,
30, 36, 40, 60, 64, 72, 80, and 96 px sizes are review targets, not embedded
entries.

Static review covers the full 16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80,
96, and 256 px target matrix, natural and 8× close views of 16/20/24/32, and
representative shortcut, taskbar, and window/app-icon contexts. It does not
claim native Windows, Qt, PyInstaller, DPI-transition, or accessibility
behavior.

## Future Issue #82 consumption

Issue #132 completes the product identity, canonical vector sources, one small
optical master, deterministic ICO, static review, provenance, and usage rules.
Future Issue #82 should use `woff/assets/ui/branding/woff_mate_app.ico` as the
candidate PyInstaller icon and retain both app-icon SVG masters for diagnosis.

The actual PyInstaller bundle consumption remains deferred; native Windows
shortcut, taskbar, and window-icon behavior remains deferred, as do real Qt
window integration, monitor/DPI transitions, clean-machine verification, and
packaged executable inspection. This issue does not modify `build.spec`, the
launcher, the installer, runtime package data, or the proposed toolkit ADR.
