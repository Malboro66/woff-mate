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
    source_unit: str | None = None,
) -> bytes:
    lines = _physical_lines(second_pilot=False)
    lines[1], lines[3], lines[83] = nation, pilot_rank, squadron
    if source_unit is not None:
        lines[2] = source_unit
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
        ("RFC", "RAF", "Major", "Captain"),  # explicit RFC/RAF conflict
        ("RFC", "RAF", "Lieutenant", "2nd Lieutenant"),
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


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
def test_german_naval_verified_two_field_source_has_pilots_and_observers(
    verified: bool,
) -> None:
    # Sanitized structural pattern only: 5 pilot details and 6 observers.
    # These are invented names, NOT a copy of the real naval career.
    lines = _physical_lines(second_pilot=False)
    lines[1], lines[2], lines[3], lines[83] = (
        "Germany", "MFJ I", "Flugmaat", "III MLFA"
    )
    pilot_names = ("Alfred", "Bert", "Clive", "Derek", "Ernest")
    observer_names = ("Felix", "Gustav", "Heinz", "Ingo", "Julius", "Kurt")
    pilot_ranks = (
        "Oberflugmeister", "Oberflugmaat", "Leutnant zur See",
        "Oberflugmeister", "Oberflugmaat",
    )
    observer_ranks = (
        "Hauptmann", "Oberleutnant", "Hauptmann",
        "Oberleutnant", "Hauptmann", "Hauptmann",
    )
    for offset, (rank, name) in enumerate(zip(pilot_ranks, pilot_names)):
        lines[63 + offset] = _member(rank, name, "Example")
    for offset, (rank, name) in enumerate(zip(observer_ranks, observer_names)):
        lines[113 + offset] = _member(rank, name, "Example", observer=True)
    lines[81] = "5"
    parser = WoFFDossierParser()
    assert parser.parse_bytes(
        _encode_dossier(lines, "Pilot1Dossier.txt"), "Pilot1Dossier.txt",
        require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.SUPPORTED_FULL
    assert parser.has_verified_structure
    assert parser.roster_complete is False
    assert len(parser.wingmen) == 11
    assert len(parser.raw_strings) == 161
    assert parser.raw_strings[0] == "160"
    assert parser.raw_strings[81] == "5"
    assert all(len(parser.raw_strings[i].split(";")) == 36 for i in range(63, 68))
    assert all(len(parser.raw_strings[i].split(";")) == 32 for i in range(113, 119))
    assert parser.raw_strings[68] == "N/A"
    assert parser.raw_strings[119] == "N/A"


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize(
    ("nation", "squadron", "source_unit", "pilot_rank", "observer_rank"),
    [
        ("Germany", "III MLFA", None, "Oberflugmeister", "Hauptmann"),
        ("Germany", "III MLFA", "Jasta 4", "Oberflugmeister", "Hauptmann"),
        ("Germany", "Jasta 4", "MFJ I", "Oberflugmeister", "Hauptmann"),
        ("Germany", "IV MLFA", "MFJ I", "Oberflugmeister", "Hauptmann"),
        ("Germany", "III MLFA", "MFJ II", "Oberflugmeister", "Hauptmann"),
        ("France", "III MLFA", "MFJ I", "Oberflugmeister", "Hauptmann"),
        ("Germany", "Marine Feld Jagdstaffel 1", None, "Flugmaat", "N/A"),
        ("Germany", "III MLFA", "MFJ I", "Gefreiter", "Hauptmann"),
        ("Germany", "III MLFA", "MFJ I", "Oberflugmeister", "Rittmeister"),
        ("Germany", "III MLFA", "MFJ I", "Leutnant", "Hauptmann"),
    ],
)
def test_german_naval_unverified_or_conflicting_source_fails_closed(
    nation: str,
    squadron: str,
    source_unit: str | None,
    pilot_rank: str,
    observer_rank: str,
    verified: bool,
) -> None:
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        _case(
            nation, squadron, pilot_rank, observer_rank,
            source_unit=source_unit,
        ),
        "Pilot1Dossier.txt", require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.INVALID_ROSTER
    assert parser.wingmen == []
    assert parser.raw_strings == []


# The literal values in these profiles are transcribed from all eleven
# maintainer-supplied base-v1.38 *Ranks.txt catalogues, deduplicated by
# service+role (not merged into a global allowlist). Each rank is exercised
# as field zero of the correct detailed 36/32-field record.
@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize(
    ("nation", "squadron", "source_unit", "pilot_ranks", "observer_ranks"),
    [
        pytest.param(
            "RFC", "16 RFC", None,
            ("Sergeant", "2nd Lieutenant", "Lieutenant", "Captain", "Major"),
            ("2nd Lieutenant", "Lieutenant", "Captain"),
            id="britain-rfc",
        ),
        pytest.param(
            "RAF", "RAF", None,
            ("Sergeant", "2nd Lieutenant", "Lieutenant", "Captain", "Major"),
            ("2nd Lieutenant", "Lieutenant", "Captain"),
            id="britain-raf",
        ),
        pytest.param(
            "RNAS", "1 Sqn RNAS", None,
            (
                "Flight Sub-Lieutenant", "Flight Lieutenant",
                "Flight Commander", "Squadron Commander",
            ),
            ("2nd Lieutenant", "Lieutenant", "Captain"),
            id="britain-rnas",
        ),
        pytest.param(
            "France", "Escadrille C 13", None,
            (
                "Caporal", "Sergent", "Adjutant", "Sous Lieutenant",
                "Lieutenant", "Capitaine",
            ),
            ("Caporal", "Sergent", "Adjutant", "Sous Lieutenant", "Lieutenant"),
            id="france",
        ),
        pytest.param(
            "Germany", "FFA 27", None,
            (
                "Gefreiter", "Unteroffizier", "Vizefeldwebel", "Feldwebel",
                "Leutnant", "Oberleutnant", "Hauptmann", "Rittmeister",
            ),
            ("Leutnant", "Oberleutnant", "Hauptmann"),
            id="germany-land",
        ),
        pytest.param(
            "Germany", "III MLFA", "MFJ I",
            (
                "Flugmaat", "Oberflugmaat", "Vizeflugmeister",
                "Flugmeister", "Oberflugmeister",
                "Leutnant zur See", "Oberleutnant zur See",
            ),
            ("Leutnant", "Oberleutnant", "Hauptmann"),
            id="germany-naval-verified",
        ),
        pytest.param(
            "USA", "20th Aero", None,
            ("2nd Lieutenant", "1st Lieutenant", "Captain", "Major", "Lt Colonel"),
            ("2nd Lieutenant", "1st Lieutenant", "Captain", "Major", "Lt Colonel"),
            id="usa",
        ),
    ],
)
def test_each_catalogue_rank_in_its_explicit_service_and_role(
    nation: str,
    squadron: str,
    source_unit: str | None,
    pilot_ranks: tuple[str, ...],
    observer_ranks: tuple[str, ...],
    verified: bool,
) -> None:
    # Validate each pilot token in the *pilot block* and each observer
    # token in the *observer block*. Synthetic names and encoding only.
    for rank in pilot_ranks:
        parser = WoFFDossierParser()
        accepted = parser.parse_bytes(
            _case(
                nation, squadron, rank, observer_ranks[0],
                source_unit=source_unit,
            ),
            "Pilot1Dossier.txt", require_verified_layout=verified,
        )
        assert accepted, ("pilot", nation, squadron, rank, parser.validation_status)
        assert parser.validation_status is DossierValidationStatus.SUPPORTED_FULL
        assert parser.has_verified_structure
        assert not parser.roster_complete
        assert len(parser.wingmen) == 2
        assert parser.wingmen[0].rank == rank
        assert parser.wingmen[1].rank == observer_ranks[0]

    for rank in observer_ranks:
        parser = WoFFDossierParser()
        accepted = parser.parse_bytes(
            _case(
                nation, squadron, pilot_ranks[0], rank,
                source_unit=source_unit,
            ),
            "Pilot1Dossier.txt", require_verified_layout=verified,
        )
        assert accepted, ("observer", nation, squadron, rank, parser.validation_status)
        assert parser.validation_status is DossierValidationStatus.SUPPORTED_FULL
        assert parser.has_verified_structure
        assert not parser.roster_complete
        assert len(parser.wingmen) == 2
        assert parser.wingmen[0].rank == pilot_ranks[0]
        assert parser.wingmen[1].rank == rank


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize("pilot_rank", ["Major", "Lieutenant", "Sergeant"])
def test_explicit_rfc_conflicts_with_raf_squadron(
    pilot_rank: str, verified: bool,
) -> None:
    # Explicit service identity RFC cannot be broadened to an RAF source.
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        _case("RFC", "RAF", pilot_rank, "Captain"),
        "Pilot1Dossier.txt", require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.INVALID_ROSTER
    assert parser.raw_strings == []
    assert parser.wingmen == []


@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
@pytest.mark.parametrize(
    ("nation", "squadron", "pilot_rank"),
    [
        ("RFC", "16 RFC", "Major"),
        ("RAF", "RAF", "Major"),
    ],
)
def test_nonconflicting_rfc_and_raf_still_admitted(
    nation: str, squadron: str, pilot_rank: str, verified: bool,
) -> None:
    parser = WoFFDossierParser()
    assert parser.parse_bytes(
        _case(nation, squadron, pilot_rank, "Lieutenant"),
        "Pilot1Dossier.txt", require_verified_layout=verified,
    )
    assert parser.validation_status is DossierValidationStatus.SUPPORTED_FULL
    assert not parser.roster_complete
