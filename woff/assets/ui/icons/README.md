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

## SYS-01 mapping decision

The `Data & System Status` destination uses Fluent `Database`, replacing the
initial `Settings` candidate after a bounded same-family review:

- `Settings` supplies every native size and style but conventionally suggests
  editable configuration, which the read-only V2 contract explicitly excludes.
- `Data Usage` supplies every variant but reads as analytics and overlaps the
  Reports destination.
- `Hard Drive` supplies every variant but suggests device/storage health.
- `Database` supplies native 16/20/24/32 regular and filled variants, remains
  visually coherent with the other Fluent navigation icons, and most directly
  identifies the read-only data/source-status destination without implying an
  editing action.

The cylinder is navigation presentation only. It is not evidence of SQLite
access, a live database connection, system health, campaign availability, or
editable configuration.

## Naming and use

Files use `ui_<semantic>_<size>_<style>.svg`. Regular is the default style.
Filled files exist only for the seven primary navigation destinations and are
reserved for a meaningful selected/current distinction.

All icon foreground shapes use `currentColor`. A future toolkit adapter may
resolve that value in memory to the active V2 token, but must not rewrite the
canonical files. State tokens are optional context styling, not semantics:
shape and visible text remain required. On paper surfaces, use the ink token
unless the actual state-token/surface pair independently reaches 3:1.

Navigation icons require visible labels, state icons require visible state
wording, and retry/refresh requires visible action text. `back` also retains a
visible destination label. An accessible name alone does not authorize
icon-only use. Within this package, only a universally understood disclosure
control may later be icon-only, and only when the normative production UI
contract explicitly authorizes it and supplies an accessible name and state.
`back` and `disclosure` mirror if RTL localization is introduced; other icons
do not. Static assets make no claim about native keyboard, focus,
accessible-name, screen-reader, Windows DPI, or PySide6 behavior.

`unavailable` is a content state with its own subtract-circle silhouette and
visible wording. It is never represented only by reduced opacity.

## Reproduction

With the upstream repository checked out at the pinned revision:

```text
python scripts/vendor_ui_v2_icons.py --source <fluent-system-icons-checkout>
```

This helper is deliberately source-specific and does not download content or
serve as a general asset pipeline.
