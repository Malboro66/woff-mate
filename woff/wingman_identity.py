"""Conservative wingman identity reconciliation for Issue #96.

The Dossier does not expose a verified immutable per-wingman source key.
Persistent identity therefore remains owned by WoFF Mate and may only be
reused when stable personal evidence resolves exactly one existing member.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

from .models import WoFFWingman


class WingmanIdentityResolutionKind(str, Enum):
    """Explicit outcomes for conservative wingman reconciliation."""

    NEW = "new"
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    CONFLICTING = "conflicting"


@dataclass(frozen=True)
class WingmanIdentityResolution:
    """Privacy-safe result of one reconciliation attempt."""

    kind: WingmanIdentityResolutionKind
    wingman_id: Optional[str] = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.kind is WingmanIdentityResolutionKind.MATCHED:
            if not self.wingman_id:
                raise ValueError("matched resolution requires a persistent wingman ID")
        elif self.wingman_id is not None:
            raise ValueError("only matched resolution may expose a persistent wingman ID")


@dataclass(frozen=True)
class _Evidence:
    first_name: str
    last_name: str
    birth_date: str
    evidence_date: str
    evidence_location: str

    @property
    def display_name(self) -> tuple[str, str]:
        return self.first_name, self.last_name

    @property
    def personal(self) -> tuple[str, str, str]:
        return self.birth_date, self.evidence_date, self.evidence_location

    @property
    def is_complete(self) -> bool:
        return all((*self.display_name, *self.personal))


def _token(value: str) -> str:
    """Canonicalize evidence text without inventing source semantics."""

    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(normalized.split()).casefold()


def _evidence(wingman: WoFFWingman) -> _Evidence:
    return _Evidence(
        first_name=_token(wingman.fName),
        last_name=_token(wingman.sName),
        birth_date=_token(wingman.birthDate),
        evidence_date=_token(wingman.evidenceDate),
        evidence_location=_token(wingman.evidenceLocation),
    )


def resolve_wingman_identity(
    incoming: WoFFWingman,
    existing: Iterable[WoFFWingman],
) -> WingmanIdentityResolution:
    """Resolve one Dossier roster member against already-scoped candidates.

    ``existing`` must contain only members from the same persistent pilot/career
    scope. The function never uses rank, status, roster position, statistics,
    biography, or the incoming object's generated ``id`` as identity evidence.

    A complete evidence tuple is intentionally required before either matching
    or creating a new identity. This is fail-closed: sparse evidence remains
    unresolved rather than falling back to display name or row order.
    """

    source = _evidence(incoming)
    if not source.is_complete:
        return WingmanIdentityResolution(
            WingmanIdentityResolutionKind.AMBIGUOUS,
            reason="insufficient-evidence",
        )

    exact: list[WoFFWingman] = []
    plausible_incomplete = False
    conflict = False

    for candidate in existing:
        stored = _evidence(candidate)

        # Incomplete same-name legacy evidence could represent the same person;
        # never create or select an identity through that uncertainty.
        if not stored.is_complete:
            if stored.display_name == source.display_name:
                plausible_incomplete = True
            continue

        if stored == source:
            exact.append(candidate)
            continue

        personal_agreements = sum(
            left == right for left, right in zip(source.personal, stored.personal)
        )

        if stored.display_name == source.display_name:
            # Fully different personal evidence is the supported same-name,
            # distinct-person case. Partial agreement plus disagreement is
            # conflicting evidence and must fail closed.
            if 0 < personal_agreements < len(source.personal):
                conflict = True
        elif personal_agreements == len(source.personal):
            # All stable personal evidence agrees but the name differs. Treat
            # this as contradictory source evidence rather than silently
            # creating a duplicate identity.
            conflict = True

    if conflict:
        return WingmanIdentityResolution(
            WingmanIdentityResolutionKind.CONFLICTING,
            reason="contradictory-stable-evidence",
        )

    if plausible_incomplete or len(exact) > 1:
        return WingmanIdentityResolution(
            WingmanIdentityResolutionKind.AMBIGUOUS,
            reason=(
                "incomplete-existing-candidate"
                if plausible_incomplete
                else "multiple-exact-matches"
            ),
        )

    if len(exact) == 1:
        return WingmanIdentityResolution(
            WingmanIdentityResolutionKind.MATCHED,
            wingman_id=exact[0].id,
            reason="unique-exact-evidence-match",
        )

    return WingmanIdentityResolution(
        WingmanIdentityResolutionKind.NEW,
        reason="no-plausible-existing-match",
    )
