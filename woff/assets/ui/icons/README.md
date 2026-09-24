# UI V2 core icon package

This directory is the toolkit-independent icon package for Issue #129. SVG is
canonical. The 24-unit asset for each semantic is the design master; the
16-, 20-, and 32-unit files are the upstream family's independently drawn
optical variants rather than mechanical exports.

## Q0 source decision

The decision is **Adapt**:

- **Adopt** was preferred but rejected because the upstream SVG files bake in
  `#212121`, which is incompatible with V2 token-driven foregrounds.
- **Adapt** uses Microsoft Fluent System Icons from the exact commit recorded in
  `manifest.json`. The only change is `fill="#212121"` to
  `fill="currentColor"`; geometry and size-specific masters are unchanged.
- **Custom** was unnecessary because one family covers all required navigation,
  state, and action meanings without a semantic gap.

The upstream MIT license permits use, modification, and redistribution when its
copyright and permission notice are retained. The upstream license and NOTICE
are redistributed under `LICENSES/`. `SHA256SUMS` freezes every delivered asset
and notice byte sequence.

## Naming and use

Files use `ui_<semantic>_<size>_<style>.svg`. Regular is the default style.
Filled files exist only for the seven primary navigation destinations and are
reserved for a meaningful selected/current distinction.

All icon foreground shapes use `currentColor`. A future toolkit adapter may
resolve that value in memory to the active V2 token, but must not rewrite the
canonical files. State tokens are optional context styling, not semantics:
shape and visible text remain required. On paper surfaces, use the ink token
unless the actual state-token/surface pair independently reaches 3:1.

Navigation and status icons are always paired with visible labels. `back` and
`disclosure` mirror if RTL localization is introduced; other icons do not.
Static assets make no claim about native keyboard, focus, accessible-name,
screen-reader, Windows DPI, or PySide6 behavior.

`unavailable` is a content state with its own subtract-circle silhouette and
visible wording. It is never represented only by reduced opacity.

## Reproduction

With the upstream repository checked out at the pinned revision:

```text
python scripts/vendor_ui_v2_icons.py --source <fluent-system-icons-checkout>
```

This helper is deliberately source-specific and does not download content or
serve as a general asset pipeline.
