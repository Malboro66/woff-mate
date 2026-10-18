#!/usr/bin/env python3
"""Validate complete Scratchpad generations before replacing squadron catalog rows.

Issue #98: this is input-preservation only. Connection centralization belongs
to #29; TEXT-to-BLOB representation/migration belongs to #46.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import stat
from contextlib import closing
from dataclasses import dataclass
from typing import Optional

from woff.decode.common import HEX_DIGITS, unscramble
from .ingestion.snapshot import SnapshotFailure, StableSnapshotReader

log = logging.getLogger("WoFFWatch")

# Conservative provisional floor for opaque decoded data. A one-byte prefix is
# never authoritative. No stronger structural claims are made without a
# validated Scratchpad format; see the Issue #98 contract note.
_MIN_DECODED_BYTES = 2


class _RejectedGeneration(ValueError):
    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


@dataclass(frozen=True)
class _CatalogEntry:
    squad_id: str
    filename: str
    raw_hex: str


def _decode_validated(encoded: bytes) -> str:
    if not encoded:
        raise _RejectedGeneration("empty")
    # The shared decoder intentionally maps delimiter-only streams to NUL.
    # A catalog generation with no hexadecimal evidence is not admissible.
    if not any(byte in HEX_DIGITS for byte in encoded):
        raise _RejectedGeneration("unsupported")
    try:
        decoded = unscramble(encoded)
    except (ValueError, OverflowError) as exc:
        raise _RejectedGeneration("unsupported") from exc
    if len(decoded) < _MIN_DECODED_BYTES:
        raise _RejectedGeneration("truncated")
    return decoded.hex()


def catalog_squadrons(
    scratchpad_dir: str,
    db_path: str,
    *,
    reader: Optional[StableSnapshotReader] = None,
) -> None:
    """All-or-nothing per selected .txt batch; rejected input retains every row.

    Snapshot acquisition has a bounded retry budget. No catalog entries are
    persisted until every selected file supplies one validated generation.
    Reprocessing identical values performs no SQL UPDATE. Existing separate
    connection ownership is intentionally deferred to Issue #29.
    """
    if not os.path.isdir(scratchpad_dir):
        log.warning("squadron-catalog skipped: inaccessible-directory")
        return

    try:
        filenames = sorted(
            filename for filename in os.listdir(scratchpad_dir)
            if filename.lower().endswith(".txt")
        )
    except OSError:
        log.warning("squadron-catalog rejected: inaccessible-directory")
        return

    snapshots = reader if reader is not None else StableSnapshotReader()
    entries: list[_CatalogEntry] = []
    for filename in filenames:
        path = os.path.join(scratchpad_dir, filename)
        try:
            metadata = os.lstat(path)
        except OSError:
            log.warning("squadron-catalog batch rejected: inaccessible-file")
            return
        if not stat.S_ISREG(metadata.st_mode):
            log.warning("squadron-catalog batch rejected: unsupported-file")
            return
        if metadata.st_size == 0:
            log.warning("squadron-catalog batch rejected: empty")
            return
        try:
            observed = snapshots.acquire(path)
            raw_hex = _decode_validated(observed.data)
        except SnapshotFailure as exc:
            log.warning("squadron-catalog batch rejected: snapshot-%s", exc.kind.value)
            return
        except _RejectedGeneration as exc:
            log.warning("squadron-catalog batch rejected: %s", exc.kind)
            return
        entries.append(_CatalogEntry(os.path.splitext(filename)[0], filename, raw_hex))

    if not entries:
        return

    try:
        with closing(sqlite3.connect(db_path)) as conn:
            try:
                conn.execute("BEGIN")
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS squadrons ("
                    "id TEXT PRIMARY KEY, name TEXT, raw_data TEXT, source_file TEXT)"
                )
                changes = 0
                for entry in entries:
                    cursor = conn.execute(
                        "INSERT INTO squadrons (id, name, raw_data, source_file) "
                        "VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(id) DO UPDATE SET "
                        "name=excluded.name, raw_data=excluded.raw_data, "
                        "source_file=excluded.source_file "
                        "WHERE squadrons.name IS NOT excluded.name "
                        "OR squadrons.raw_data IS NOT excluded.raw_data "
                        "OR squadrons.source_file IS NOT excluded.source_file",
                        (entry.squad_id, entry.squad_id, entry.raw_hex, entry.filename),
                    )
                    changes += cursor.rowcount
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise
    except sqlite3.Error:
        log.error("squadron-catalog batch rejected: sqlite-write")
        return

    log.info("squadron-catalog committed %d changed rows", changes)
