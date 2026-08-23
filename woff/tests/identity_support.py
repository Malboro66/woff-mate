import hashlib

from ..identity import PilotIdentityEvidence, PilotIdentityKind


def dossier_evidence(slot: int, marker: str = "test") -> PilotIdentityEvidence:
    return PilotIdentityEvidence(
        PilotIdentityKind.DOSSIER,
        slot,
        hashlib.sha256(f"{slot}:{marker}".encode("ascii")).hexdigest(),
    )


def dependent_evidence(
    slot: int, marker: str = "test"
) -> PilotIdentityEvidence:
    return PilotIdentityEvidence(
        PilotIdentityKind.SLOT_DEPENDENT,
        slot,
        hashlib.sha256(f"{slot}:{marker}".encode("ascii")).hexdigest(),
    )
