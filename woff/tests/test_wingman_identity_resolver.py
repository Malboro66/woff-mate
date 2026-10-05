from ..models import WoFFWingman
from ..wingman_identity import (
    WingmanIdentityResolutionKind,
    resolve_wingman_identity,
)


def _wingman(
    wingman_id: str,
    *,
    first_name: str = "Alex",
    last_name: str = "Doe",
    birth_date: str = "1896-08-08",
    evidence_date: str = "1913-07-19",
    evidence_location: str = "Arras",
    rank: str = "Lieutenant",
    status: str = "In Service",
    skill: int = 3,
    morale: int = 5,
    flminutes: int = 1550,
) -> WoFFWingman:
    return WoFFWingman(
        id=wingman_id,
        fName=first_name,
        sName=last_name,
        birthDate=birth_date,
        evidenceDate=evidence_date,
        evidenceLocation=evidence_location,
        rank=rank,
        status=status,
        skill=skill,
        morale=morale,
        flminutes=flminutes,
    )


def test_complete_unseen_evidence_resolves_new() -> None:
    result = resolve_wingman_identity(_wingman("incoming"), [])

    assert result.kind is WingmanIdentityResolutionKind.NEW
    assert result.wingman_id is None
    assert result.reason == "no-plausible-existing-match"


def test_unique_exact_evidence_preserves_existing_persistent_id() -> None:
    stored = _wingman("persistent-a")
    incoming = _wingman(
        "generated-import-id",
        rank="Capitaine",
        status="On Leave",
        skill=5,
        morale=2,
        flminutes=8420,
    )

    result = resolve_wingman_identity(incoming, [stored])

    assert result.kind is WingmanIdentityResolutionKind.MATCHED
    assert result.wingman_id == "persistent-a"
    assert result.reason == "unique-exact-evidence-match"


def test_multiple_exact_matches_fail_closed_as_ambiguous() -> None:
    result = resolve_wingman_identity(
        _wingman("incoming"),
        [_wingman("persistent-a"), _wingman("persistent-b")],
    )

    assert result.kind is WingmanIdentityResolutionKind.AMBIGUOUS
    assert result.wingman_id is None
    assert result.reason == "multiple-exact-matches"


def test_incoming_sparse_evidence_never_falls_back_to_display_name() -> None:
    incoming = _wingman("incoming", birth_date="")

    result = resolve_wingman_identity(incoming, [_wingman("persistent-a")])

    assert result.kind is WingmanIdentityResolutionKind.AMBIGUOUS
    assert result.wingman_id is None
    assert result.reason == "insufficient-evidence"


def test_incomplete_existing_same_name_blocks_new_identity() -> None:
    legacy = _wingman(
        "legacy-a",
        birth_date="",
        evidence_date="",
        evidence_location="",
    )

    result = resolve_wingman_identity(_wingman("incoming"), [legacy])

    assert result.kind is WingmanIdentityResolutionKind.AMBIGUOUS
    assert result.wingman_id is None
    assert result.reason == "incomplete-existing-candidate"


def test_same_name_with_fully_distinct_personal_evidence_is_new() -> None:
    distinct_homonym = _wingman(
        "persistent-b",
        birth_date="1895-07-25",
        evidence_date="1914-06-10",
        evidence_location="Privas, Ardèche, France",
    )

    result = resolve_wingman_identity(_wingman("incoming"), [distinct_homonym])

    assert result.kind is WingmanIdentityResolutionKind.NEW
    assert result.wingman_id is None


def test_same_name_partial_agreement_with_disagreement_is_conflicting() -> None:
    stored = _wingman(
        "persistent-a",
        birth_date="1896-08-08",
        evidence_date="1913-07-19",
        evidence_location="Cambrai",
    )

    result = resolve_wingman_identity(_wingman("incoming"), [stored])

    assert result.kind is WingmanIdentityResolutionKind.CONFLICTING
    assert result.wingman_id is None
    assert result.reason == "contradictory-stable-evidence"


def test_different_name_with_identical_personal_evidence_is_conflicting() -> None:
    stored = _wingman(
        "persistent-a",
        first_name="Louis",
        last_name="Triggiers",
    )

    result = resolve_wingman_identity(_wingman("incoming"), [stored])

    assert result.kind is WingmanIdentityResolutionKind.CONFLICTING
    assert result.wingman_id is None


def test_text_normalization_does_not_make_operational_fields_identity() -> None:
    stored = _wingman(
        "persistent-a",
        first_name="Émile",
        last_name="Du Pont",
        evidence_location="  Saint   Omer  ",
        status="On Leave",
        skill=1,
        morale=1,
        flminutes=100,
    )
    incoming = _wingman(
        "generated-import-id",
        first_name="ÉMILE",
        last_name="du pont",
        evidence_location="Saint Omer",
        status="In Service",
        skill=5,
        morale=5,
        flminutes=9000,
    )

    result = resolve_wingman_identity(incoming, [stored])

    assert result.kind is WingmanIdentityResolutionKind.MATCHED
    assert result.wingman_id == "persistent-a"
