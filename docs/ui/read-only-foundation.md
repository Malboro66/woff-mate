# Read-only UI foundation

## Status and reference boundary

This contract maps the current Figma reference captured by Issue #56 into a
future read-only presentation surface. The Figma navigation is **Dashboard,
Pilot, Missions, Diary, Squadron, and Settings**. Visuals are design intent,
not evidence of implemented services or production behavior.

In particular, Figma indicators such as **watchdog running**, **database
connected**, and **last sync** are aspirational and fixture-backed until their
application-service contracts are approved. A mock must label them as fixture
data; production presentation must render them unavailable rather than infer
them from files, threads, or a database connection.

## Layer boundary

The only permitted read path is:

`presentation -> application query services -> repositories -> SQLite`

Presentation must never execute SQL and must never read WoFF files directly.
It must not call parsers, catalogers, watchdogs, repository internals, or accept
database connections and cursors. Query services own orchestration and convert
repository results into stable snapshots; repositories alone translate between
SQLite records and application data.

UI inputs are immutable/plain view-model snapshots: frozen value records or
equivalent copied scalars, tuples, and immutable mappings. They must not be
database connections, cursors, raw parser payloads, mutable domain objects, or
live collections. Every snapshot records:

- source authority and the contract/version that selected it;
- observation time and freshness (including an explicit unknown value);
- warnings and partial-data reasons; and
- fields that are unavailable, with a machine-stable reason rather than an
  invented value.

No view triggers ingestion, refresh writes, diary edits, configuration changes,
or other commands. Refresh means requesting a new snapshot from an approved
query service, not reading storage itself.

## Shared view states

Every screen supports the same explicit state envelope:

| State | Meaning and presentation rule |
|---|---|
| `loading` | A snapshot request is pending; preserve layout and announce progress without inventing data. |
| `ready` | A valid snapshot is available; warnings and freshness remain visible. |
| `empty` | The authoritative query succeeded and its collection has no items. |
| `missing` | A required identity or source has not been established; say what is missing. |
| `stale/unavailable` | The last snapshot is outside its freshness policy or a source/service cannot currently answer; retain timestamp and warning when safe. |
| `error` | The query failed; show a sanitized diagnostic and retry affordance, never a cursor, SQL text, personal path, or raw payload. |

`empty` is not `missing`; `missing` is not an error; and stale data must never be
presented as current. Fields inside a `ready` snapshot may still be explicitly
unavailable and carry warnings.

## Navigation and stable inputs

| Screen | Responsibility | Immutable view-model inputs |
|---|---|---|
| Dashboard | Read-only campaign overview and entry points. | Selected pilot summary, campaign summary cards, recent-mission summaries, freshness/warnings, and explicitly unavailable operational-indicator fixtures. |
| Pilot | Read-only identity, service record, and derived status. | Pilot identity snapshot, authoritative field provenance, service/stat summaries, availability map, freshness, and warnings. |
| Missions | Read-only mission history and selection. | Stable mission IDs, ordered mission-summary tuple, selected mission details, order-policy identifier, provenance, freshness, and warnings. |
| Diary | Read-only narrative entries associated with stable mission IDs. **Diary is strictly read-only** and exposes no create, edit, delete, save, or regeneration commands. | Ordered immutable diary-entry summaries, narrative provenance/contract version, unavailable reasons, freshness, and warnings. |
| Squadron | Read-only current roster and documented historical context. | Squadron identity, roster snapshot, transfer-status value when authoritative, provenance, freshness, and warnings. |
| Settings | Read-only effective-configuration and diagnostic visibility for this phase; it cannot mutate, save, auto-detect, browse for, or reset configuration. | Redacted effective-configuration snapshot, validation status, capability/diagnostic values, provenance, freshness, warnings, and unavailable fields. |

## Unstable data contracts

The shell must not conceal or locally compensate for these current dependencies:

- **Dossier/pilot:** authoritative identity and partial-source behavior depend on
  the Dossier field-validation work (#35) and related normalization contracts.
- **Missions/order:** canonical dates, deterministic ordering, stable identity,
  and non-destructive enrichment depend on #40 and #39.
- **Squadron transfer:** transfer versus missing-wingman semantics depend on #37
  and its Dossier prerequisites.
- **Narratives:** association and narrative inputs depend on #43 and the mission
  contracts it references. Diary rendering cannot create or repair narratives.

Until those contracts settle, fixtures must exercise unavailable and warning
states and must not freeze accidental repository shapes into a UI API.

## Sanitized fixture contract

Fixture-backed prototypes use invented people, squadrons, missions, paths, and
narratives. Personal campaign data, real player names, installation paths,
database copies, logs, screenshots containing personal data, activation/license
credentials, and unredacted WoFF payloads are prohibited. Fixtures must be
small, reviewable UTF-8 text or typed values, deterministic, and marked
synthetic. They cover every shared state, field-level unavailability, stale
timestamps, multiple warnings, and source-authority conflicts without accessing
WoFF files or SQLite.

## Planned work and dependency order

The approved follow-up work is now tracked explicitly:

- #79 completes the six-screen Figma flow, tokens, components, focus order, and
  Windows scaling notes without production UI code.
- #80 defines the shared state matrix and deterministic sanitized fixtures used
  by designs, contract tests, and the toolkit spike.
- #81 defines immutable read-only view models and application query-service
  protocols after #80 establishes the shared vocabulary.
- #82 measures one isolated PySide6 and Qt Widgets line after #80, including
  supported Python and Windows versions, PyInstaller packaging, startup,
  memory, scaling, keyboard use, accessibility, plugins, and licensing.

Issues #79 and #80 may proceed without a GUI runtime dependency. Issues #81
and #82 remain blocked by #80. A retained production shell still requires ADR
acceptance, applicable Product Gate A and Product Gate B decisions, an approved
optional-dependency policy, clean Windows packaging evidence, and explicit
maintainer approval. None of these planning items claims those decisions.
