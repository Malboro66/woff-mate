"""Issue #185: entirely synthetic, bounded rank/service admission regressions.

No real campaign records, source paths, private R0.1 aliases or WOFF bytes.
Rank spellings are transcribed from maintainer-supplied v1.38 *Ranks.txt
catalogues; source-service assertions remain deliberately narrow.
"""
from __future__ import annotations

import pytest

from ..parsers.dossier_parser import DossierValidationStatus, WoFFDossierParser
from .test_dossier_parser import _encode_dossier
from .test_issue96_observed_partial_roster import _member, _physical_lines


def _case(
    nation: str,
    squadron: str,
    pilot_rank: str,
    observer_rank: str = "N/A",
    *,
    change_index: int | None = None,
    change_to: str | None = None,
) -> bytes:
    lines = _physical_lines(second_pilot=False)
    lines[1], lines[3], lines[83] = nation, pilot_rank, squadron
    lines[4], lines[5] = "Fictional", "Aviator"
    lines[63] = _member(pilot_rank, "Emil", "Example")
    lines[113] = (
        _member(observer_rank, "Olive", "Observer", observer=True)
        if observer_rank != "N/A" else "N/A"
    )
    lines[81] = "1"
    if change_index is not None:
        assert change_to is not None
        lines[change_index] = change_to
    return _encode_dossier(lines, "Pilot1Dossier.txt")


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize(
    ("nation", "squadron", "pilot_rank", "observer_rank"),
    [
        ("Britain", "16 RFC", "Sergeant", "Captain"),
        ("Britain", "16 RFC", "Major", "2nd Lieutenant"),
        ("RFC", "16 RFC", "Lieutenant", "Lieutenant"),
        ("RAF", "RAF", "Major", "Captain"),
        ("RNAS", "1 Sqn RNAS", "Flight Sub-Lieutenant", "Captain"),
        ("Britain", "1 Sqn RNAS", "Squadron Commander", "Lieutenant"),
        ("France", "Escadrille N 15", "Capitaine", "Adjutant"),
        ("France", "Escadrille N 15", "Sous Lieutenant", "Caporal"),
        ("Germany", "Jasta 4", "Rittmeister", "Hauptmann"),
        ("Germany", "Jasta 4", "Gefreiter", "Leutnant"),
        ("USA", "20th Aero", "1st Lieutenant", "Lt Colonel"),
        ("USA", "20th Aero", "Major", "Major"),
        ("Germany", "Marine Feld Jagdstaffel 1", "Flugmaat", "N/A"),
        ("Germany", "Marine Feld Jagdstaffel 1", "Leutnant zur See", "N/A"),
    ],
)
def test_attested_profiles_accept_only_matching_roles(
    nation: str, squadron: str, pilot_rank: str, observer_rank: str, verified: bool,
) -> None:
    parser = WoFFDossierParser()
    assert parser.parse_bytes(
        _case(nation, squadron, pilot_rank, observer_rank),
        "Pilot1Dossier.txt", require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.SUPPORTED_FULL
    assert parser.has_verified_structure
    assert parser.roster_complete is False
    assert len(parser.wingmen) == (1 if observer_rank == "N/A" else 2)
    assert parser.wingmen[0].rank == pilot_rank


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize(
    ("nation", "squadron", "pilot_rank", "observer_rank"),
    [
        ("Britain", "16 RFC", "Flight Lieutenant", "Captain"),
        ("Britain", "16 RFC", "Major", "Major"),
        ("Britain", "Unknown Unit", "Major", "Captain"),
        ("Britain", "1 Sqn RNAS", "Sergeant", "Captain"),
        ("RFC", "1 Sqn RNAS", "Major", "Captain"),  # contradictory service
        ("France", "Escadrille N 15", "Capitaine", "Capitaine"),
        ("Germany", "Jasta 4", "Flugmaat", "Leutnant"),
        ("Germany", "Marine Feld Jagdstaffel 1", "Gefreiter", "N/A"),
        ("Germany", "Jasta 4", "Rittmeister", "Rittmeister"),
        ("USA", "20th Aero", "Sergeant", "Major"),
        ("USA", "20th Aero", "1st Lieutenant", "Sergeant"),
        ("Belgium", "Unverified Squadron", "Major", "Captain"),
    ],
)
def test_cross_role_cross_service_and_unknown_reject_without_partial_records(
    nation: str, squadron: str, pilot_rank: str, observer_rank: str, verified: bool,
) -> None:
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        _case(nation, squadron, pilot_rank, observer_rank),
        "Pilot1Dossier.txt", require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.INVALID_ROSTER
    assert parser.wingmen == []
    assert parser.raw_strings == []


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize(
    ("index", "value"),
    [
        (63, "Sergeant;No;Name"),
        (63, "Sergeant;Bad!;Name;" + ";".join(["0"] * 33)),
        (63, "Sergeant;Emil;Example;invalid;5;In Service;" + ";".join(["Null"] * 30)),
        (63, "Sergeant;Emil;Example;0;5;;" + ";".join(["Null"] * 30)),
        (81, "2"),
    ],
)
def test_structural_guards_survive_rank_admission(
    index: int, value: str, verified: bool,
) -> None:
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        _case("Britain", "16 RFC", "Sergeant", "Captain", change_index=index, change_to=value),
        "Pilot1Dossier.txt", require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.INVALID_ROSTER
    assert parser.wingmen == []


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
def test_context_is_not_roster_and_absent_slots_are_not_people(verified: bool) -> None:
    parser = WoFFDossierParser()
    assert parser.parse_bytes(
        _case("USA", "20th Aero", "Major", "Lt Colonel"),
        "Pilot1Dossier.txt", require_verified_layout=verified,
    )
    assert len(parser.wingmen) == 2
    assert {w.fName for w in parser.wingmen} == {"Emil", "Olive"}
    assert parser.raw_strings[112] == "Captain;Context;Only"
    assert parser.raw_strings[65] == "N/A"
    assert parser.roster_complete is False
