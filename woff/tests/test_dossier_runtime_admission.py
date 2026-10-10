"""The attested v1.38 structure is runtime evidence; legacy decoding is diagnostic.

All bytes and people are synthetic. No fixture claims an exhaustive v1.38
format matrix or a complete census from the observed detailed slots.
"""

from __future__ import annotations

import pytest

from ..campaign_namespace import campaign_namespace_for_root
from ..ingestion.outcome import ProcessingReason, ProcessingStatus
from ..parsers.dossier_parser import WoFFDossierParser
from .test_dossier_parser import _dossier_fixture, _encode_dossier
from .test_dossier_transactions import _dossier_bytes, dossier_runtime
from .test_issue96_codex_exception_regressions import _observed


def _unsupported(kind: str) -> bytes:
    if kind == "short":
        return _encode_dossier(_dossier_fixture("short_valid_sanitized.txt"), "Pilot1Dossier.txt")
    if kind == "full":
        return _dossier_bytes()
    arity = int(kind)
    return _dossier_bytes(wingmen=(
        ";".join(["Unrelated", "prose", "with", "exactly", "synthetic", "fields", "extra"][:arity]),
    ))


@pytest.mark.parametrize("kind", ["short", "full", "5", "6", "7"])
def test_unverified_runtime_generation_is_neutral_and_recovers(dossier_runtime, kind):
    db, processor, path = dossier_runtime
    path.write_bytes(_observed())
    assert processor.process(str(path), "modified").acknowledged_generation
    pilot_id, member_id = db._get_conn().execute(
        "SELECT pilotId, id FROM squad_members ORDER BY id LIMIT 1"
    ).fetchone()
    assert db.save_wingman_personality(member_id, pilot_id, {"personality_trait": "Steady"})
    assert db.save_wingman_memory(member_id, "mission", "1917-04-01", "Synthetic memory")
    # Stipulate a trusted historical census/candidate via repository interfaces;
    # it is not inferred from the partial runtime observation above.
    with db.transaction():
        state = db.load_dossier_state("James Hartley", campaign_namespace_for_root(str(path.parent)), 1)
        assert state is not None
        db.save_dossier_roster_state(pilot_id, state.squadron, state.wingmen)
        db.save_dossier_roster_candidate(
            pilot_id, state.squadron, state.wingmen,
            state.squadron, state.wingmen[:1],
        )
    before = tuple(db._get_conn().iterdump())
    path.write_bytes(_unsupported(kind))
    for _ in range(2):
        outcome = processor.process(str(path), "modified")
        assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
        assert outcome.reason is ProcessingReason.UNSUPPORTED_LAYOUT
        assert outcome.acknowledged_generation is None and outcome.retry_input is None
        assert tuple(db._get_conn().iterdump()) == before
    db.close()
    assert db._get_conn().execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert db._get_conn().execute("PRAGMA foreign_key_check").fetchall() == []
    assert tuple(db._get_conn().iterdump()) == before
    path.write_bytes(_observed(day=11))
    assert processor.process(str(path), "modified").acknowledged_generation
    after = tuple(db._get_conn().iterdump())
    assert processor.process(str(path), "modified").acknowledged_generation
    assert tuple(db._get_conn().iterdump()) == after
    assert db.get_wingman_personality(member_id) is not None
    assert db._get_conn().execute("SELECT wingmanId FROM wingmen_memory").fetchall() == [(member_id,)]
    assert db._get_conn().execute("SELECT COUNT(*) FROM diary_entries").fetchone() == (0,)


@pytest.mark.parametrize("kind", ["short", "full", "6"])
def test_unverified_first_generation_cannot_create_a_career(dossier_runtime, kind):
    db, processor, path = dossier_runtime
    before = tuple(db._get_conn().iterdump())
    path.write_bytes(_unsupported(kind))
    for _ in range(2):
        outcome = processor.process(str(path), "initial")
        assert outcome.reason is ProcessingReason.UNSUPPORTED_LAYOUT
        assert outcome.status is ProcessingStatus.PERMANENT_REJECTION
        assert outcome.acknowledged_generation is None and outcome.retry_input is None
        assert tuple(db._get_conn().iterdump()) == before


@pytest.mark.parametrize("kind", ["short", "full"])
def test_legacy_diagnostic_decode_does_not_assert_census_authority(kind):
    parser = WoFFDossierParser()
    assert parser.parse_bytes(_unsupported(kind), "Pilot1Dossier.txt")
    assert parser.roster_complete is False
    assert parser.has_verified_structure is False


def test_runtime_only_guard_does_not_enter_the_legacy_roster_fallback(monkeypatch):
    parser = WoFFDossierParser()
    def forbidden(_parts):
        raise AssertionError("Unsupported input entered legacy member recognition")
    monkeypatch.setattr(parser, "_has_roster_shape", forbidden)
    assert not parser.parse_bytes(_unsupported("6"), "Pilot1Dossier.txt", require_verified_layout=True)
    assert parser.validation_status.value == "unsupported-layout"
