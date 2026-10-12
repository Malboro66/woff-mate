"""Issue #185 follow-up: synthetic, narrowly scoped v1.38 TAB evidence.

No source identities, campaign data or original Dossier bytes are embedded here.
The 161/160 observed layout, both roster roles and negative controls are tested
in diagnostic and verified-runtime admission modes.
"""

from __future__ import annotations

import pytest

from ..parsers.dossier_parser import DossierValidationStatus, WoFFDossierParser
from .test_dossier_parser import _encode_dossier

_SOURCE = "Pilot1Dossier.txt"


def _member(rank: str, first: str, *, observer: bool = False) -> str:
    parts = ["Null"] * (32 if observer else 36)
    parts[:6] = [rank, first, "Example", "3", "5", "In Service"]
    parts[11:13] = ["2", "30"]
    parts[16:19] = ["2", "3", "1897"]
    parts[19] = "Entirely fictional biography."
    parts[25] = "Fictional station near town"
    return ";".join(parts)


def _candidate_lines() -> list[str]:
    # Entirely synthetic, structurally verified 161/160 Dossier family.
    lines = ["Null"] * 161
    lines[0], lines[1], lines[3] = "160", "Britain", "Flight Sub-Lieutenant"
    lines[4], lines[5] = "Fictional", "Aviator"
    lines[81], lines[83] = "1", "HQ Synthetic Squadron"
    lines[63:79] = ["N/A"] * 16
    lines[113:129] = ["N/A"] * 16
    lines[63] = _member("Squadron Commander", "Alfred")
    lines[113] = _member("2nd Lieutenant", "Olive", observer=True)
    return lines


def _case(index: int, field: int | None, value: str, *, marker: str = "160") -> bytes:
    lines = _candidate_lines()
    lines[0] = marker
    if field is None:
        lines[index] = value
    else:
        parts = lines[index].split(";")
        parts[field] = value
        lines[index] = ";".join(parts)
    return _encode_dossier(lines, _SOURCE)


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize("slot", [63, 113], ids=["pilot-36", "observer-32"])
def test_embedded_tab_only_in_detailed_member_location_is_admitted(
    verified: bool, slot: int,
) -> None:
    parser = WoFFDossierParser()
    assert parser.parse_bytes(
        _case(slot, 25, "Fictional town\tnear station"),
        _SOURCE, require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.SUPPORTED_FULL
    assert parser.has_verified_structure
    assert parser.roster_complete is False
    assert len(parser.raw_strings) == 161
    assert parser.raw_strings[0] == "160"
    assert parser.raw_strings[81] == "1"
    assert len(parser.raw_strings[slot].split(";")) == (36 if slot < 79 else 32)
    assert parser.raw_strings[slot].split(";")[25] == "Fictional town\tnear station"
    assert len(parser.wingmen) == 2
    assert any(w.evidenceLocation == "Fictional town\tnear station" for w in parser.wingmen)


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize(
    ("slot", "field"),
    [(63, 0), (63, 1), (63, 3), (63, 5), (63, 11), (63, 19),
     (113, 0), (113, 2), (113, 3), (113, 5), (113, 19)],
)
def test_tab_in_other_roster_fields_fails_closed(
    verified: bool, slot: int, field: int,
) -> None:
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        _case(slot, field, "Bad\tField"),
        _SOURCE, require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.DECRYPTION_FAILED
    assert parser.raw_strings == []
    assert parser.wingmen == []
    assert parser.pilot is None


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize("slot", [63, 113], ids=["pilot", "observer"])
@pytest.mark.parametrize("value", ["\tCity", "City\t", "\t", "City\x00town", "City\ufffdname", "City\nName"])
def test_boundary_or_other_nonprintable_location_rejected(
    verified: bool, slot: int, value: str,
) -> None:
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        _case(slot, 25, value), _SOURCE, require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.DECRYPTION_FAILED
    assert parser.raw_strings == []
    assert parser.wingmen == []


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize("index", [1, 4, 83, 112, 140])
def test_tab_outside_detailed_roster_rejected(verified: bool, index: int) -> None:
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        _case(index, None, "Fictional\tcontext"),
        _SOURCE, require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.DECRYPTION_FAILED
    assert parser.wingmen == []


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
def test_bad_width_does_not_create_location_exception(verified: bool) -> None:
    lines = _candidate_lines()
    parts = lines[63].split(";")
    parts[25] = "Fictional\ttown"
    lines[63] = ";".join(parts[:-1])
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        _encode_dossier(lines, _SOURCE), _SOURCE, require_verified_layout=verified,
    )
    assert parser.validation_status in (
        DossierValidationStatus.DECRYPTION_FAILED,
        DossierValidationStatus.INVALID_ROSTER,
    )
    assert parser.raw_strings == []


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
def test_other_envelope_cannot_admit_control_character(verified: bool) -> None:
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        _case(63, 25, "Fictional\ttown", marker="159"),
        _SOURCE, require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.DECRYPTION_FAILED
    assert parser.wingmen == []


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize(
    ("first_slot", "second_slot"),
    [(63, 113), (63, 64), (113, 114)],
    ids=["pilot-and-observer", "two-pilots", "two-observers"],
)
def test_two_distinct_member_location_tabs_reject_entire_dossier(
    verified: bool, first_slot: int, second_slot: int,
) -> None:
    # Each location individually looks valid, but the source has two TABs.
    lines = _candidate_lines()
    if second_slot == 64:
        lines[64] = _member("Flight Commander", "Bert")
        lines[81] = "2"
    if second_slot == 114:
        lines[114] = _member("Captain", "Bert", observer=True)
    for slot in (first_slot, second_slot):
        fields = lines[slot].split(";")
        fields[25] = "Fictional town\tnear station"
        lines[slot] = ";".join(fields)
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        _encode_dossier(lines, _SOURCE),
        _SOURCE, require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.DECRYPTION_FAILED
    assert parser.raw_strings == []
    assert parser.wingmen == []
    assert parser.pilot is None


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize("slot", [63, 113], ids=["pilot", "observer"])
@pytest.mark.parametrize(
    "location",
    [
        " \tCity",
        "City\t ",
        " \t ",
        "  \t City  ",
        "City \t  ",
        " \tCity ",
        " City\t ",
        "   \t City",
    ],
    ids=[
        "leading-space-then-tab", "trailing-tab-then-space",
        "only-surrounding-whitespace", "padded-leading-tab",
        "padded-trailing-tab", "leading-tab-with-trailing-space",
        "left-space-and-boundary-tab", "wide-leading-padding",
    ],
)
def test_padded_boundary_tab_fails_closed(
    verified: bool, slot: int, location: str,
) -> None:
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        _case(slot, 25, location),
        _SOURCE, require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.DECRYPTION_FAILED
    assert parser.raw_strings == []
    assert parser.wingmen == []
    assert parser.pilot is None


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize("slot", [63, 113], ids=["pilot", "observer"])
def test_genuinely_embedded_tab_survives_surrounding_location_spaces(
    verified: bool, slot: int,
) -> None:
    location = "  Fictional town \t near station  "
    parser = WoFFDossierParser()
    assert parser.parse_bytes(
        _case(slot, 25, location),
        _SOURCE, require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.SUPPORTED_FULL
    assert parser.has_verified_structure
    assert parser.roster_complete is False
    assert len(parser.wingmen) == 2
    assert any(w.evidenceLocation == location.strip() for w in parser.wingmen)


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
def test_no_tab_payload_still_admitted(verified: bool) -> None:
    parser = WoFFDossierParser()
    assert parser.parse_bytes(
        _encode_dossier(_candidate_lines(), _SOURCE),
        _SOURCE, require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.SUPPORTED_FULL
    assert len(parser.wingmen) == 2
    assert parser.roster_complete is False
