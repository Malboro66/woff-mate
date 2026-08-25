import hashlib

from ..campaign_namespace import campaign_namespace_for_root
from ..identity import PilotIdentityEvidence, PilotIdentityKind

TEST_CAMPAIGN_NAMESPACE = campaign_namespace_for_root(
    r"C:\Synthetic\CampaignRoot"
)


def dossier_evidence(
    slot: int,
    marker: str = "test",
    campaign_namespace: str = TEST_CAMPAIGN_NAMESPACE,
) -> PilotIdentityEvidence:
    return PilotIdentityEvidence(
        PilotIdentityKind.DOSSIER,
        slot,
        hashlib.sha256(f"{slot}:{marker}".encode("ascii")).hexdigest(),
        campaign_namespace,
    )


def dependent_evidence(
    slot: int,
    marker: str = "test",
    campaign_namespace: str = TEST_CAMPAIGN_NAMESPACE,
) -> PilotIdentityEvidence:
    return PilotIdentityEvidence(
        PilotIdentityKind.SLOT_DEPENDENT,
        slot,
        hashlib.sha256(f"{slot}:{marker}".encode("ascii")).hexdigest(),
        campaign_namespace,
    )
