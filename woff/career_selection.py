"""Stable career selection shared by user-facing command consumers."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class CareerSelection:
    """One persistent career selected independently of its display name."""

    pilot_id: str
    name: str
    slot: Optional[int]


class CareerResolutionError(ValueError):
    """Base error for a selector that cannot identify exactly one career."""


class CareerNotFoundError(CareerResolutionError):
    """Raised when a stable ID or compatibility name matches no career."""


class AmbiguousCareerError(CareerResolutionError):
    """Raised when a compatibility display name matches multiple careers."""

    def __init__(self, candidates: Sequence[CareerSelection]) -> None:
        self.candidates = tuple(candidates)
        hints = "; ".join(
            f"pilot_id={candidate.pilot_id} "
            f"slot={candidate.slot if candidate.slot is not None else 'unbound'}"
            for candidate in self.candidates
        )
        super().__init__(
            "Pilot name is ambiguous. Use --pilot-id. "
            f"Candidates: {hints}"
        )


def _has_slot_bindings(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'pilot_slot_bindings'
        """
    ).fetchone() is not None


def _career_rows(
    conn: sqlite3.Connection,
    *,
    pilot_id: Optional[str] = None,
    pilot_name: Optional[str] = None,
) -> list[CareerSelection]:
    if pilot_id is not None and pilot_name is not None:
        raise ValueError("career lookup accepts only one selector")

    if _has_slot_bindings(conn):
        slot_expression = """
            (SELECT MIN(binding.slot)
             FROM pilot_slot_bindings AS binding
             WHERE binding.pilotId = p.id)
        """
    else:
        slot_expression = "NULL"

    where = ""
    parameters: tuple[str, ...] = ()
    if pilot_id is not None:
        where = "WHERE p.id = ?"
        parameters = (pilot_id,)
    elif pilot_name is not None:
        where = "WHERE p.name = ?"
        parameters = (pilot_name,)

    rows = conn.execute(
        f"""
        SELECT p.id AS pilot_id,
               p.name AS pilot_name,
               {slot_expression} AS slot
        FROM pilots AS p
        {where}
        ORDER BY p.name,
                 CASE WHEN slot IS NULL THEN 1 ELSE 0 END,
                 slot,
                 p.id
        """,
        parameters,
    ).fetchall()
    return [
        CareerSelection(
            pilot_id=str(row[0]),
            name=str(row[1]),
            slot=int(row[2]) if row[2] is not None else None,
        )
        for row in rows
    ]


def list_careers(conn: sqlite3.Connection) -> list[CareerSelection]:
    """Return every career in deterministic display-name, slot, and ID order."""

    return _career_rows(conn)


def resolve_career(
    conn: sqlite3.Connection,
    *,
    pilot_id: Optional[str] = None,
    pilot_name: Optional[str] = None,
) -> CareerSelection:
    """Resolve one explicit ID or one unambiguous compatibility name."""

    if (pilot_id is None) == (pilot_name is None):
        raise ValueError("exactly one career selector is required")

    candidates = _career_rows(
        conn,
        pilot_id=pilot_id,
        pilot_name=pilot_name,
    )
    if not candidates:
        selector = "pilot ID" if pilot_id is not None else "pilot name"
        raise CareerNotFoundError(f"Selected {selector} was not found.")
    if len(candidates) > 1:
        raise AmbiguousCareerError(candidates)
    return candidates[0]
