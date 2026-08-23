"""Stable career identity evidence for WoFF ingestion sources."""

from __future__ import annotations

import ntpath
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PilotIdentityKind(str, Enum):
    """Supported evidence classes at the persistence boundary."""

    DOSSIER = "dossier"
    SLOT_DEPENDENT = "slot-dependent"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class PilotIdentityEvidence:
    """Verified source evidence used to resolve one persistent career ID."""

    kind: PilotIdentityKind
    slot: Optional[int] = None
    dossier_digest: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind is PilotIdentityKind.UNRESOLVED:
            if self.slot is not None or self.dossier_digest is not None:
                raise ValueError("unresolved identity cannot carry slot evidence")
            return
        if self.slot is None or self.slot <= 0:
            raise ValueError("identity evidence requires a positive slot")
        digest = self.dossier_digest or ""
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("identity evidence requires a lowercase SHA-256 digest")


class PilotIdentityError(RuntimeError):
    """Base exception containing only sanitized identity diagnostics."""

    def __init__(self, reason: str, slot: Optional[int] = None) -> None:
        self.reason = reason
        self.slot = slot
        super().__init__(reason)


class PilotIdentityUnavailable(PilotIdentityError):
    """Raised when verified identity may become available after a retry."""


class PilotIdentityRejected(PilotIdentityError):
    """Raised when a source cannot safely identify a persistent career."""


class PilotIdentityAmbiguous(PilotIdentityError):
    """Raised when existing data cannot select exactly one career."""


_SLOT_SOURCE = re.compile(
    r"^Pilot([1-9][0-9]*)(?:Dossier|Log|Claims|Squads)\.txt$", re.IGNORECASE
)


def pilot_slot(source_name: str) -> Optional[int]:
    """Return a positive slot only for supported pilot source filenames."""

    basename = ntpath.basename(source_name.replace("/", "\\"))
    match = _SLOT_SOURCE.fullmatch(basename)
    return int(match.group(1)) if match else None


def dossier_source_name(slot: int) -> str:
    """Return the canonical Dossier filename for a positive pilot slot."""

    if slot <= 0:
        raise ValueError("slot must be positive")
    return f"Pilot{slot}Dossier.txt"
