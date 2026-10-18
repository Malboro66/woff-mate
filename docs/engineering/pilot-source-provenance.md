# Pilot source provenance contract — Issue #99

The persisted `pilots.source_file` and `pilots.last_updated` columns have
a single bounded meaning. They do **not** track the last input processed and
do not establish field-by-field lineage.

- **`pilots.source_file`** is the basename of the last *accepted, verified
  Dossier* for the current persistent career identity. The caller's
  `PilotIdentityKind.DOSSIER` and slot/namespace evidence must be validated
  before this field may change. A partial Log, Claims, or Squads input does
  not replace it, even when it updates other admitted pilot fields.
- **`pilots.last_updated`** is the most recent *accepted Dossier observation
  timestamp* for that career, generated during parsing. It is not the
  historical campaign event date, filesystem mtime, or time of the latest
  generic SQL update. A valid newer Dossier timestamp advances it; an absent,
  blank, malformed, older, or non-comparable observation cannot regress a
  valid stored value. Timestamps are parsed as ISO datetimes; if an aware and
  naive timestamp cannot be compared, the stored value wins.
- Partial-source provenance carried in parser models identifies the input
  file only. It must not be interpreted as permission to rewrite the
  authoritative `pilots` columns. `None` in an unsupplied model field
  means no evidence. A verified Dossier without a valid timestamp may retain
  the existing stored time; new rows may contain SQL NULL.
- Generic XML and `Mission.log` pilot models do not have accepted Dossier
  identity authority. They cannot write a `pilots` row and do not create
  an authoritative pilot observation timestamp. This policy does not change
  their existing mission, XML or non-pilot source handling.
- The separate `pilot_slot_bindings.last_updated` column remains binding
  bookkeeping, **not** the authoritative pilot timestamp; it may use the
  binding update time when the Dossier parser provides none.

## Query and report interpretation

A query or report displaying either persisted pilot column must label it
as the **Dossier source** and **last accepted Dossier observation**, not
"last source seen" or "last data refresh". Other admitted fields may have
changed more recently through Log, Claims or Squads. Consumers must not
infer field-level authority, freshness or file ownership from this pair.

## Compatibility and limitations

No schema change or destructive rewrite is required. Existing valid
Dossier provenance remains readable and is protected from future partial
merges. Previously damaged legacy metadata are **not** guessed or
automatically backfilled; a future verified Dossier can restore them.
Historical inaccuracy without new evidence remains explicitly unknown.

Regression coverage: `woff/tests/test_pilot_provenance_merge.py`, including
accepted Dossier refresh, old/missing timestamps, all three slot-dependent
sources, repeated partial input, identityless XML/Mission.log and existing
SQLite rows.
