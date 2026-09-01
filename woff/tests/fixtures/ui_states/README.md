# Synthetic UI fixture inventory

Issue #80 · `EVAL-UI-STATES-001` · contract `synthetic-ui-v1`

`catalog.json` is a closed, hand-authored demonstration catalog. Every envelope
carries `synthetic: true` and the visible label `Synthetic`. All names, units,
IDs, narratives, event dates, observation times and diagnostics are invented.
The `synthetic://installation` URI is an inert example, never an OS path.

The [screen-state matrix](../../../../docs/ui/screen-state-matrix.md) defines
semantics, state priority, field reasons, source authority, freshness and the
UI V2 visual aliases. Each case is an independent scenario; consumers must not
combine the empty, stale and complete variants into a single live career.
The mission and diary examples deliberately share safe stable references.

## Inventory

| Fixture ID | Intended screens | Shared state | Coverage |
|---|---|---|---|
| `careers-ready` | `APP-00`, `SEL-01` | `ready` | Homonyms have different career IDs and persistent slots 2 and 3. |
| `diary-ready` | `JRN-01` | `ready` | Two invented narratives link to supplied stable mission IDs. |
| `empty-global` | `APP-00`, `SEL-01`, `SYS-01` | `empty` | A successful global collection contains no entries; no career is required. |
| `empty-records` | `OPR-01`, `DOS-01`, `DOS-02`, `DOS-03`, `DOS-04`, `MIS-01`, `MIS-02`, `SQD-01`, `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02` | `empty` | A successful selected-career collection contains no entries. |
| `error-query` | `APP-00`, `SEL-01`, `OPR-01`, `DOS-01`, `DOS-02`, `DOS-03`, `DOS-04`, `MIS-01`, `MIS-02`, `SQD-01`, `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02`, `SYS-01` | `error` | A failed query exposes only the fixed safe diagnostic. |
| `loading` | `APP-00`, `SEL-01`, `OPR-01`, `DOS-01`, `DOS-02`, `DOS-03`, `DOS-04`, `MIS-01`, `MIS-02`, `SQD-01`, `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02`, `SYS-01` | `loading` | A pending request contains no old payload. |
| `missing-career` | `APP-00`, `SEL-01`, `OPR-01`, `DOS-01`, `DOS-02`, `DOS-03`, `DOS-04`, `MIS-01`, `MIS-02`, `SQD-01`, `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02` | `missing` | Required selection is absent; global system status remains reachable. |
| `missing-source` | `APP-00`, `SEL-01`, `OPR-01`, `DOS-01`, `DOS-02`, `DOS-03`, `DOS-04`, `MIS-01`, `MIS-02`, `SQD-01`, `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02`, `SYS-01` | `missing` | Required source identity has not been established. |
| `missions-ready` | `MIS-01`, `MIS-02` | `ready` | Equal event timestamps are ordered by stable mission ID. |
| `pilot-partial-conflict` | `OPR-01`, `DOS-01` | `ready` | Known values, unknown status, missing flight time, conflicting service, two warnings. |
| `pilot-ready` | `OPR-01`, `DOS-01` | `ready` | Confirmed victories are explicitly zero; other known values remain distinct. |
| `pilot-stale` | `OPR-01`, `DOS-01` | `stale/unavailable` | Retain the safe older observation and a persistent warning. |
| `pilot-unknown-freshness` | `OPR-01`, `DOS-01` | `ready` | Usable data has no observation time and is never called current. |
| `reports-ready` | `RPT-01`, `RPT-02` | `ready` | An invented report has a stable ID and safe text. |
| `settings-ready` | `SYS-01` | `ready` | Redacted paths, inert example URI, unknown operational indicators and safe diagnostics. |
| `source-truncated` | `APP-00`, `SEL-01`, `OPR-01`, `DOS-01`, `DOS-02`, `DOS-03`, `DOS-04`, `MIS-01`, `MIS-02`, `SQD-01`, `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02`, `SYS-01` | `stale/unavailable` | An identified but incomplete source supplies no unvalidated values. |
| `source-unreadable` | `APP-00`, `SEL-01`, `OPR-01`, `DOS-01`, `DOS-02`, `DOS-03`, `DOS-04`, `MIS-01`, `MIS-02`, `SQD-01`, `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02`, `SYS-01` | `stale/unavailable` | Read failure is a source result, with no raw exception. |
| `source-unsupported` | `APP-00`, `SEL-01`, `OPR-01`, `DOS-01`, `DOS-02`, `DOS-03`, `DOS-04`, `MIS-01`, `MIS-02`, `SQD-01`, `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02`, `SYS-01` | `stale/unavailable` | An unsupported source supplies no invented replacement values. |
| `squadron-ready` | `SQD-01`, `SQD-02` | `ready` | An unknown transfer status stays unknown; no departure is inferred. |
| `unavailable-source` | `APP-00`, `SEL-01`, `OPR-01`, `DOS-01`, `DOS-02`, `DOS-03`, `DOS-04`, `MIS-01`, `MIS-02`, `SQD-01`, `SQD-02`, `JRN-01`, `RPT-01`, `RPT-02`, `SYS-01` | `stale/unavailable` | The service cannot answer and there is no retained snapshot. |

## Determinism and privacy

- The reference clock is fixed at `2026-01-01T12:00:00Z`; it never uses the
  wall clock. An age greater than 60 seconds is stale in this demo policy.
- Fixture IDs and warning codes are sorted; screens follow the approved
  inventory order; records sort by `(occurred_at, id)` ascending, including ties.
  This illustrates deterministic display without defining production mission
  ordering or an ingestion rule. Event dates never stand in for observation time.
- The validator accepts only the two declared UTF-8 files. Database copies,
  binaries, raw game files, logs, screenshots, subdirectories and symlinks are
  rejected. No personal source was used to create this catalog.
- Exact object keys and approved display-text/diagnostic vocabularies reject
  arbitrary names, narratives, installation paths, credentials and raw payloads,
  including values prefixed with `Synthetic`. IDs occupy numeric synthetic
  namespaces. Activation/license fields are prohibited even if redacted.
- Extending the catalog or text vocabulary requires human review of invented
  content and appropriate mutation tests. This check certifies this bounded
  catalog; it is not a general-purpose personal-data detector or a sanitizer
  that makes uploaded campaign data safe to publish.

Run from the repository root:

```bash
python -I -S scripts/validate_ui_fixtures.py
python -m pytest tests/test_ui_state_fixtures.py -q
```

The new tests live outside `woff/tests` because that directory's shared
`conftest.py` imports persistence. These fixtures and the standard-library
validator do not import the package or open SQLite, WoFF files, network
connections, Qt, watchdog, parsers, repositories or the launcher. They are
excluded from the installed package by the existing test-package exclusion.
They do not create production view models (#81), widgets, live refresh,
configuration editing, a toolkit decision, or Product Gate approval.
