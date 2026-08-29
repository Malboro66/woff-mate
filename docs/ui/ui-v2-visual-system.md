# UI V2 visual system

Status: Approved design specification

Date: 2026-08-29

Tracks: Issue #79

## Intent

The visual language is **Operations Room 1917**: a calm, information-dense
desktop workspace with restrained First World War aviation references. Modern
interaction, readable typography, and honest state communication take priority
over decoration.

This inventory is toolkit-independent. Token names describe Figma and future
presentation intent; they are not a CSS, Qt, or runtime API.

## Color tokens

| Token | Value | Use |
|---|---|---|
| `color.shell.graphite` | `#111614` | Navigation and the deepest shell surface. |
| `color.shell.aviation` | `#18231F` | Main desktop background. |
| `color.surface.felt` | `#26332D` | Matte grouping surface and secondary panels. |
| `color.surface.paper` | `#E7D8B8` | Beige reading cards and document-like content. |
| `color.surface.paper-raised` | `#F0E4CA` | Selected or raised paper surface. |
| `color.border.dark` | `#46534C` | Low-emphasis separation on dark surfaces. |
| `color.border.paper` | `#A99A7C` | Borders on paper surfaces. |
| `color.accent.brass` | `#C2A86B` | Limited selection, divider, and icon accent. |
| `color.text.on-dark` | `#F4EFE2` | Primary text on shell and felt. |
| `color.text.muted-dark` | `#C2BCAF` | Secondary text on shell and felt. |
| `color.text.ink` | `#201D18` | Primary text on beige paper. |
| `color.text.muted-ink` | `#5B5345` | Secondary text on beige paper. |
| `color.state.info` | `#77AFC2` | Informational icon or edge, always with text. |
| `color.state.success` | `#82B58A` | Confirmed success or complete coverage, always with text. |
| `color.state.warning` | `#E0B65C` | Partial, stale, or warning condition, always with text. |
| `color.state.error` | `#D97872` | Error or risk, always with text. |
| `color.focus.outer` | `#F7F2E6` | High-contrast outer focus ring on dark surfaces. |
| `color.focus.inner` | `#7D5A18` | Inner focus edge on paper surfaces. |

Text does not use `color.accent.brass` as its only contrast-bearing color.
Status never relies on hue alone. Figma contrast checks must use the rendered
surface, including any texture, and meet WCAG AA: at least 4.5:1 for normal
text and 3:1 for large text and essential non-text boundaries.

Flat-token contrast was calculated with the WCAG relative-luminance formula:

| Pair | Ratio |
|---|---:|
| Primary text / aviation shell | 14.08:1 |
| Muted text / aviation shell | 8.55:1 |
| Ink / paper | 11.93:1 |
| Muted ink / paper | 5.39:1 |
| Information / aviation shell | 6.69:1 |
| Success / aviation shell | 6.87:1 |
| Warning / aviation shell | 8.48:1 |
| Error / aviation shell | 5.30:1 |

These ratios pass the normal-text target for their listed pair. Each rendered
Figma frame must still be checked after texture, opacity, focus, and state
composition are applied.

## Material tokens

Material is atmospheric, non-semantic, and subordinate to content.

| Token | Treatment | Constraint |
|---|---|---|
| `material.paper.subtle` | Fine monochrome fiber/noise on beige reading cards. | Keep local luminance variation at or below 4%; never place stains, folds, torn edges, handwriting, or false data behind text. |
| `material.felt.matte` | Nearly flat dark green with very low-frequency variation. | Use only for broad grouping surfaces; no directional pattern that suggests a control state. |
| `material.canvas.quiet` | Fine, low-contrast weave for optional empty shell regions. | Do not use beneath dense tables, small labels, or diagnostics. |
| `material.wood.restrained` | Dark, desaturated grain on a narrow structural edge or top-level rail. | Never wrap every card, simulate drawers, or become the primary content surface. |
| `material.brass.aged` | Flat warm-metal fill or 1-pixel accent with restrained highlight. | No glossy bevels; never substitute for focus, selected text, or warning semantics. |

All beige cards use `material.paper.subtle`. The texture must remain visible
enough to identify a paper surface but quiet enough that disabling it would not
change hierarchy or meaning. Paper cards remain single surfaces; stacked sheets,
grunge, coffee marks, heavy distress, and skeuomorphic controls are prohibited.

## Typography tokens

| Token | Size / line height | Weight | Intended use |
|---|---:|---:|---|
| `type.display` | 32 / 40 | 600 | Screen title or Dossier name. |
| `type.heading-1` | 24 / 32 | 600 | Major section title. |
| `type.heading-2` | 18 / 26 | 600 | Card or subsection title. |
| `type.body` | 16 / 24 | 400 | Primary reading and controls. |
| `type.body-strong` | 16 / 24 | 600 | Labels needing emphasis. |
| `type.small` | 14 / 20 | 400 | Secondary metadata. |
| `type.caption` | 12 / 18 | 500 | Nonessential caption and safe provenance summary. |
| `type.stat` | 28 / 34 | 600 | Numeric statistic with a visible text label. |

Historical headings use a restrained serif such as Source Serif 4 with Georgia
as a prototype fallback. Controls, data, and long-form text use a highly legible
sans-serif such as Inter or Segoe UI. No essential wording is embedded in an
image. All type follows Windows scaling; Figma uses logical sizes rather than
rasterized text.

## Spacing, shape, border, and elevation

| Family | Tokens |
|---|---|
| Spacing | `space.1=4`, `space.2=8`, `space.3=12`, `space.4=16`, `space.6=24`, `space.8=32`, `space.12=48` logical pixels. |
| Radius | `radius.control=4`, `radius.card=6`, `radius.dialog=8`; paper never uses exaggerated rounded corners. |
| Border | `border.hairline=1`, `border.emphasis=2`, `border.focus=2` logical pixels. |
| Elevation | `elevation.base=0`, `elevation.card=1`, `elevation.overlay=3`; use tonal separation before shadow. |

Touch-like oversized spacing is not required, but every pointer target is at
least 32 by 32 logical pixels and every primary control is at least 40 pixels
high. Related information stays closer than unrelated sections.

## Icon treatment

- Use one consistent linear icon family at 1.5- to 2-pixel logical stroke.
- Pair navigation and status icons with visible text.
- Use a filled shape only for the current primary destination or urgent status.
- Do not use flags as the sole service/nationality label.
- Do not use medals, wings, or insignia decoratively when they could be read as
  pilot facts.
- Provide an accessible name for every icon-only control; icon-only controls
  are limited to universally understood window or disclosure actions.

## Component inventory

| Component | Minimum variants |
|---|---|
| `AppNavigation` | default, current destination, keyboard focus, system footer entry |
| `CareerSelector` | default, homonym, unknown metadata, no selection, unavailable |
| `ContextBar` | career selected, no career, partial data, unavailable data |
| `PageHeader` | default, back route, contextual read-only link, warning summary |
| `CareerIdentityHeader` | complete, partial, unknown status, no portrait |
| `CareerStatusBadge` | `Active`, `KIA`, `PoW`, `MIA`, `Invalided Out`, `Survived War`, `Lightly Wounded`, `Seriously Wounded`, unknown, unsupported authoritative value |
| `DataCoverageBadge` | complete, partial, missing, truncated, unsupported, unreadable |
| `StatTile` | known positive, authoritative zero, unknown, unavailable, invalid |
| `MissionSummary` | ready, no narrative, no mission, unavailable detail |
| `TimelineEvent` | mission, transfer, promotion, injury, recovery, award, status |
| `RecordPreview` | populated, none recorded, unavailable |
| `DataTable` | populated, sorted, keyboard row focus, empty, partial |
| `InlineNotice` | information, warning, error, sanitized retry |
| `EmptyState` | no career, no missions, no victories, no decorations, no reports |
| `PortraitFrame` | image, neutral fallback, loading, unavailable |
| `ReadOnlyField` | known, authoritative zero, unknown, unavailable |
| `Dialog` | information, confirmation-free warning, error detail; no write confirmation |

A variant is preferred over a screen-specific component when the underlying
presentation contract is the same.

## Shared state treatment

| State | Stable layout | Announcement and content | Permitted action |
|---|---|---|---|
| Loading | Keep shell, context, and final geometry. | Label progress; skeletons contain no previous career data. | None. |
| Complete | Show all supplied sections. | `Complete record` is discreet and textual. | Open read-only details. |
| Partial | Keep confirmed identity and known fields. | Persistent `Partial record` notice and field-level absence. | `View data status`. |
| Empty | Keep the ordinary screen structure. | Use a collection-specific `None recorded` message. | Normal navigation. |
| No career | Keep shell and orientation. | Explain that a career must be selected. | `Select career`. |
| Missing | Keep only context known to be safe. | Name the missing record or source without inference. | `View data status` or select another career. |
| Truncated | Do not render unvalidated values. | Explain that the record is incomplete. | `View data status`. |
| Unsupported | Do not imply successful support. | Identify the format as unsupported. | `View data status`. |
| Unreadable | Do not show payloads or local paths. | Give a sanitized read failure. | `View data status`. |
| Error | Preserve active-career context. | Give a sanitized temporary-failure message. | `Retry view` and `View data status`. |
| Stale | Keep the last safe snapshot and timestamp. | Label it stale; never present it as current. | Request a new approved snapshot. |

`Unknown`, `Not available`, `None recorded`, and `0` are content states, not
interchangeable placeholders.

## Keyboard model

The default focus sequence is structural and remains stable across screens:

1. Skip to content.
2. Career selector.
3. Primary navigation in visual order.
4. Data & System Status footer entry.
5. Contextual back control, when present.
6. Page-level read-only links.
7. Main content in reading order.
8. Contextual records or rows.
9. Safe retry or data-status action in an exceptional state.

Rules:

- `Tab` and `Shift+Tab` move through interactive elements only.
- Arrow keys move within a navigation group, tab set, or table row group when
  that pattern is represented.
- `Enter` and `Space` activate the focused control according to Windows norms.
- `Escape` closes a selector, dialog, or temporary overlay and restores focus
  to its opener.
- Focus is never moved merely because data refreshes or a warning appears.
- A two-edge, 2-pixel minimum focus treatment remains visible on paper, felt,
  canvas, and shell surfaces and is not communicated by brass color alone.
- Loading a different career clears old content before the new career snapshot
  is presented and moves focus programmatically to the resulting page heading.

Page headings are programmatic focus targets, not stops in the sequential `Tab`
order. After primary navigation or career selection changes the top-level view,
the resulting heading receives one-time programmatic focus through
`tabindex="-1"` or the toolkit-equivalent accessibility API. A contextual back
control remains an ordinary interactive `Tab` stop when present; headings are
never made generally tabbable.

## Windows scaling behavior

V2 is a desktop layout, not a mobile breakpoint system. All dimensions below
are logical pixels; Windows scaling changes physical size.

| Scale | Navigation | Content behavior | Dossier statistics |
|---:|---|---|---|
| 100% | 256-pixel rail with icons and labels. | Two-column detail where space permits; 32-pixel margins. | Six columns. |
| 125% | Rail remains labelled; compact gaps may reduce from 24 to 16. | Two-column detail unless the effective width crosses the high-scale threshold. | Three or six columns, whichever preserves the minimum tile width. |
| 150% | Rail may compact while retaining visible labels or an accessible expansion control. | Side column moves below main; margins may reduce to 24. | Three columns, then two if required. |
| 200% | Compact desktop rail; no icon-only ambiguity. | One content column; dialogs stay within the effective work area. | Two columns. |

At every supported scale:

- core content has no horizontal scrollbar;
- the active career, screen title, warning summary, and primary value remain
  visible before secondary previews;
- tables may replace low-priority columns with an explicit details view, but
  never truncate identity or status silently;
- text reflows rather than shrinking below its token size;
- the side column follows the main column in both visual and focus order; and
- skeletons and notices reserve enough space to avoid disruptive layout shifts.

## Content and accessibility rules

- Status is always text plus icon, never color alone.
- The rendered design meets WCAG AA contrast after texture is applied.
- Tooltips repeat or expand information; they never contain the only copy of an
  essential value or action.
- Data tables expose a heading, column labels, row focus, and a deterministic
  reading order.
- Portrait alt text identifies the display label only; the image never supplies
  status, rank, service, or nationality that is absent from text.
- Dates use an unambiguous display and remain unknown when the canonical value
  is absent.
- Sanitized messages exclude SQL, cursors, raw payloads, database contents,
  personal paths, usernames, logs, and activation/license information.
- Operational indicators such as watchdog, database, and last sync are labelled
  `Synthetic`, `Fixture-backed`, or `Unavailable`, never `Live` in this phase.

## Asset boundary

Prototype assets are invented, generated, or sanitized and carry a visible
`Synthetic` annotation in the source page. They contain no real player names,
campaign screenshots, local paths, database copies, logs, game payloads, or
activation/license information. Issue #80, not this visual inventory, owns the
formal deterministic fixture set.
