import pytest

from ..identity import (
    PilotIdentityEvidence,
    PilotIdentityKind,
    dossier_source_name,
    pilot_slot,
)


@pytest.mark.parametrize(
    ("source_name", "expected"),
    [
        ("Pilot1Dossier.txt", 1),
        ("pilot12log.TXT", 12),
        (r"C:\\WoFF\\Pilot3Claims.txt", 3),
        ("/tmp/Pilot4Squads.txt", 4),
        ("Mission.log", None),
        ("Pilot0Dossier.txt", None),
        ("Pilot1Unknown.txt", None),
    ],
)
def test_pilot_slot_accepts_only_supported_positive_slot_sources(
    source_name, expected
):
    assert pilot_slot(source_name) == expected


def test_identity_evidence_requires_complete_dossier_proof():
    with pytest.raises(ValueError, match="positive slot"):
        PilotIdentityEvidence(PilotIdentityKind.DOSSIER, 0, "a" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        PilotIdentityEvidence(PilotIdentityKind.SLOT_DEPENDENT, 1, "short")


def test_dossier_source_name_is_canonical():
    assert dossier_source_name(7) == "Pilot7Dossier.txt"
