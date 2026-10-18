# Issue #98 — Squadron catalog-generation contract

Scope: Scratchpad `*.txt` catalog input only. No WoFF source writes, schema
migration, medal catalog changes, or shared SQLite connection-policy changes.

## Admission

1. Enumerate selected `*.txt` files in deterministic filename order.
2. Reject inaccessible, directory, symlink, empty, or unsupported sources.
3. Acquire two identical nonempty observations with the existing bounded
   `StableSnapshotReader` (metadata, digest and content checks).
4. Decode using the existing `unscramble` compatibility semantics; reject
   undecodable input, streams with no uppercase-hex evidence, and decoded
   payloads shorter than two bytes.
5. Stage every validated generation before starting the SQLite write batch.
6. Within one SQLite transaction, preflight every staged replacement against its
   existing row before writing catalog rows. A nonempty stored TEXT payload
   is retained when the new decoded hexadecimal string is shorter; reject
   the **entire batch** with `shorter-than-stored`. If an existing non-NULL
   payload has an unsupported storage type, reject with `unsupported-stored`
   rather than overwriting unknown data.

Two decoded bytes are a deliberately minimal **provisional** validity floor,
not a reverse-engineered squadron record schema. Historical separators remain
permitted by `unscramble`. We cannot identify every longer, stable but
semantically truncated file without independently verified Scratchpad format
markers, length, or checksum. The retained-length guard rejects the concrete
shorter-than-previously-stored case, but does **not** prove completeness for a
first-seen record or one that stays the same length or grows. Legitimately
shorter fresh generations are conservatively rejected until an independently
verified real-format criterion allows them. Never represent this as complete
source-level truncation detection.

## Persistence / errors

- An empty directory is a no-op, never a delete instruction.
- An invalid member rejects the **whole selected batch**. Existing rows and
  other valid candidates remain unchanged.
- Once staged, the existing-row length/type preflight runs before any
  INSERT/UPDATE statements within the same SQLite transaction. A rejected
  member rolls back the full batch without changing any catalog rows.
  An SQL error also rolls back all candidates.
- An unchanged row is not rewritten on replay (`ON CONFLICT DO UPDATE WHERE`).
- One bounded warning/error records the **category only** (empty, truncated,
  shorter-than-stored, unsupported-stored, unsupported, inaccessible,
  changed-generation, timeout or sqlite-write).
  It does not include paths, source names, original bytes or payload content.
- A later successful run may apply data after a rejection; rejected input
  itself is never persisted.

## Boundaries and evidence

- `EVAL-CATALOG-STABILITY-001`: synthetic empty, malformed/short, mutation,
  truncate, inaccessible and batch-rejection tests.
- `EVAL-CATALOG-STABILITY-002`: synthetic stable update, replay, batch
  success and SQL rollback tests.
- Issue #29 still owns central database connections/locks.
- Issue #46 still owns the future TEXT-to-BLOB migration.
- Neither of these issues is implicitly completed by #98.
