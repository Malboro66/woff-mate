"""Stable career and wingman identity evidence for WoFF ingestion sources."""

from __future__ import annotations

import ntpath
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

from .campaign_namespace import is_campaign_namespace
from .models import WoFFWingman


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
    campaign_namespace: Optional[str] = None
    vacancy_epoch: Optional[int] = None

    def __post_init__(self) -> None:
        if self.kind is PilotIdentityKind.UNRESOLVED:
            if (
                self.slot is not None
                or self.dossier_digest is not None
                or self.campaign_namespace is not None
                or self.vacancy_epoch is not None
            ):
                raise ValueError("unresolved identity cannot carry slot evidence")
            return
        if self.slot is None or self.slot <= 0:
            raise ValueError("identity evidence requires a positive slot")
        digest = self.dossier_digest or ""
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("identity evidence requires a lowercase SHA-256 digest")
        if not is_campaign_namespace(self.campaign_namespace):
            raise ValueError("identity evidence requires a campaign namespace")
        if self.vacancy_epoch is not None and (
            type(self.vacancy_epoch) is not int or self.vacancy_epoch < 0
        ):
            raise ValueError("vacancy epoch must be a nonnegative integer")

    @property
    def binding_key(self) -> tuple[str, int]:
        """Return the namespace-aware key shared by persistence and future deferral."""

        if self.campaign_namespace is None or self.slot is None:
            raise ValueError("unresolved identity has no binding key")
        return self.campaign_namespace, self.slot


@dataclass(frozen=True)
class PilotSlotBinding:
    """Last known source occupancy, independent of a career's military status."""

    campaign_namespace: str
    slot: int
    pilot_id: str
    dossier_digest: Optional[str]
    last_updated: str

    def __post_init__(self) -> None:
        if not is_campaign_namespace(self.campaign_namespace, allow_legacy=True):
            raise ValueError("slot binding requires a campaign namespace")
        if type(self.slot) is not int or self.slot <= 0:
            raise ValueError("slot binding requires a positive integer slot")


def is_dossier_source(source_name: str) -> bool:
    """Recognize only authoritative, positive-slot Dossier filenames."""
    slot = pilot_slot(source_name)
    basename = ntpath.basename(source_name.replace("/", "\\"))
    return slot is not None and basename.casefold() == (
        dossier_source_name(slot).casefold()
    )


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


class WingmanIdentityResolutionKind(str, Enum):
    """Explicit outcomes for conservative wingman reconciliation."""

    NEW = "new"
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    CONFLICTING = "conflicting"


@dataclass(frozen=True)
class WingmanIdentityResolution:
    """Privacy-safe result of one wingman reconciliation attempt."""

    kind: WingmanIdentityResolutionKind
    wingman_id: Optional[str] = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.kind is WingmanIdentityResolutionKind.MATCHED:
            if not self.wingman_id:
                raise ValueError("matched resolution requires a persistent wingman ID")
        elif self.wingman_id is not None:
            raise ValueError("only matched resolution may expose a persistent wingman ID")


class WingmanIdentityResolutionError(RuntimeError):
    """Fail-closed persistence error containing only sanitized diagnostics."""

    def __init__(
        self,
        kind: WingmanIdentityResolutionKind,
        reason: str,
    ) -> None:
        self.kind = kind
        self.reason = reason
        super().__init__(f"wingman identity {kind.value}: {reason}")


@dataclass(frozen=True)
class _WingmanEvidence:
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

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        return (
            self.first_name,
            self.last_name,
            self.birth_date,
            self.evidence_date,
            self.evidence_location,
        )


def _wingman_token(value: str) -> str:
    """Canonicalize evidence text without inventing source semantics."""

    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(normalized.split()).casefold()


def _wingman_evidence(wingman: WoFFWingman) -> _WingmanEvidence:
    return _WingmanEvidence(
        first_name=_wingman_token(wingman.fName),
        last_name=_wingman_token(wingman.sName),
        birth_date=_wingman_token(wingman.birthDate),
        evidence_date=_wingman_token(wingman.evidenceDate),
        evidence_location=_wingman_token(wingman.evidenceLocation),
    )


def wingman_identity_key(
    wingman: WoFFWingman,
) -> Optional[tuple[str, str, str, str, str]]:
    """Return complete normalized evidence for duplicate/ambiguity checks."""

    evidence = _wingman_evidence(wingman)
    return evidence.key if evidence.is_complete else None


def resolve_wingman_identity(
    incoming: WoFFWingman,
    existing: Iterable[WoFFWingman],
) -> WingmanIdentityResolution:
    """Resolve one Dossier roster member against already-scoped candidates.

    ``existing`` must contain only members from the same persistent pilot/career
    scope. Rank, status, roster position, statistics, biography, and the
    incoming object's generated ``id`` are never identity evidence.

    Complete stable evidence is intentionally required before either matching
    or creating identity. Sparse or contradictory same-name evidence fails
    closed rather than falling back to display name or row order.
    """

    source = _wingman_evidence(incoming)
    if not source.is_complete:
        return WingmanIdentityResolution(
            WingmanIdentityResolutionKind.AMBIGUOUS,
            reason="insufficient-evidence",
        )

    exact: list[WoFFWingman] = []
    plausible_incomplete = False
    conflict = False

    for candidate in existing:
        stored = _wingman_evidence(candidate)

        if not stored.is_complete:
            if stored.display_name == source.display_name:
                plausible_incomplete = True
            continue

        if stored == source:
            exact.append(candidate)
            continue

        if stored.display_name != source.display_name:
            # Different display names are never merged. Coincident personal
            # evidence is insufficient to prove they are the same person.
            continue

        personal_agreements = sum(
            left == right for left, right in zip(source.personal, stored.personal)
        )
        # Same-name candidates with partial stable-evidence agreement are
        # contradictory and must fail closed. Fully distinct personal evidence
        # remains the supported homonym case.
        if 0 < personal_agreements < len(source.personal):
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
