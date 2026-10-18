"""Issue #195: entirely synthetic, exact RFC source/display pairs.

No WOFF source records, pilot identities, screenshots or local paths.
"""
from __future__ import annotations

import pytest

from ..parsers.dossier_parser import DossierValidationStatus, WoFFDossierParser
from .test_issue185_rank_profiles import _case


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize(
    ("display", "source"),
    [("2 RFC", "RFC-2"), ("13 RFC", "RFC-13")],
)
@pytest.mark.parametrize("rank", ["Sergeant", "2nd Lieutenant", "Lieutenant", "Captain", "Major"])
@pytest.mark.parametrize("observer", ["2nd Lieutenant", "Lieutenant", "Captain"])
def test_attested_british_rfc_pair_has_role_specific_ranks(
    display: str, source: str, rank: str, observer: str, verified: bool,
) -> None:
    parser = WoFFDossierParser()
    assert parser.parse_bytes(
        _case("Britain", display, rank, observer, source_unit=source),
        "Pilot1Dossier.txt", require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.SUPPORTED_FULL
    assert parser.has_verified_structure
    assert parser.roster_complete is False
    assert len(parser.wingmen) == 2
    assert parser.wingmen[0].rank == rank
    assert parser.wingmen[1].rank == observer


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize(
    ("nation", "display", "source", "pilot_rank", "observer"),
    [
        ("Britain", "2 RFC", "RFC-99", "Sergeant", "Lieutenant"),
        ("Britain", "13 RFC", "RFC-99", "Sergeant", "Lieutenant"),
        ("Britain", "2 RFC", "RFC-13", "Sergeant", "Lieutenant"),
        ("Britain", "13 RFC", "RFC-2", "Sergeant", "Lieutenant"),
        ("Britain", "Unknown", "RFC-2", "Sergeant", "Lieutenant"),
        ("Britain", "Unknown", "RFC-13", "Sergeant", "Lieutenant"),
        ("RAF", "2 RFC", "RFC-2", "Sergeant", "Lieutenant"),
        ("RAF", "13 RFC", "RFC-13", "Sergeant", "Lieutenant"),
        ("RNAS", "2 RFC", "RFC-2", "Sergeant", "Lieutenant"),
        ("RNAS", "13 RFC", "RFC-13", "Sergeant", "Lieutenant"),
        ("RFC", "2 RFC", "RFC-13", "Sergeant", "Lieutenant"),
        ("RFC", "13 RFC", "RFC-2", "Sergeant", "Lieutenant"),
        ("Britain", "2 RFC", "RFC-2", "Flight Lieutenant", "Captain"),
        ("Britain", "13 RFC", "RFC-13", "Sergeant", "Major"),
    ],
)
def test_mismatched_service_source_display_and_role_fail_closed(
    nation: str, display: str, source: str, pilot_rank: str, observer: str,
    verified: bool,
) -> None:
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        _case(nation, display, pilot_rank, observer, source_unit=source),
        "Pilot1Dossier.txt", require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.INVALID_ROSTER
    assert parser.raw_strings == []
    assert parser.wingmen == []


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize("display,source", [("2 RFC", "RFC-2"), ("13 RFC", "RFC-13")])
@pytest.mark.parametrize("invalid_field", [
    (63, "Sergeant;No;Name"),
    (81, "2"),
    (63, "Sergeant;Emil;Example;0;5;;" + ";".join(["Null"] * 30)),
])
def test_new_pairs_preserve_roster_structure_guards(
    verified: bool, display: str, source: str, invalid_field: tuple[int, str],
) -> None:
    parser = WoFFDossierParser()
    index, value = invalid_field
    assert not parser.parse_bytes(
        _case("Britain", display, "Sergeant", "Lieutenant",
              source_unit=source, change_index=index, change_to=value),
        "Pilot1Dossier.txt", require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.INVALID_ROSTER
    assert parser.wingmen == []
    assert parser.raw_strings == []


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
def test_existing_16_rfc_contract_retained(verified: bool) -> None:
    parser = WoFFDossierParser()
    assert parser.parse_bytes(
        _case("Britain", "16 RFC", "Sergeant", "Captain", source_unit="RFC-16"),
        "Pilot1Dossier.txt", require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.SUPPORTED_FULL
    assert parser.roster_complete is False
