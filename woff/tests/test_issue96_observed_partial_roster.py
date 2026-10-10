"""Issue #96: sanitized physical Dossier layout and partial-roster safety.

Synthetic data only. Positions reflect longitudinal structural evidence;
nothing here asserts that detailed slots enumerate all active airmen.
"""

from __future__ import annotations

from ..parsers.dossier_parser import DossierValidationStatus, WoFFDossierParser
from ..campaign_namespace import campaign_namespace_for_root
from .test_dossier_parser import _encode_dossier
from .test_dossier_transactions import dossier_runtime


def _member(
    rank: str,
    first: str,
    last: str,
    *,
    observer: bool = False,
    kills: int = 0,
    status: str = "In Service",
) -> str:
    fields = ["Null"] * (32 if observer else 36)
    fields[:6] = [rank, first, last, "0", str(kills), status]
    fields[6:11] = ["0"] * 5
    fields[11:19] = ["1", "80", "1500", "8", "3", "4", "5", "1894"]
    fields[19] = "Synthetic biography, not real campaign data."
    fields[20:24] = ["3", "27", "900", "0"]
    fields[24] = "1/3/1915"
    fields[25] = "Synthetic town of " + first
    fields[26:28] = ["0", "0"]
    if not observer:
        fields[35] = ""
    return ";".join(fields)


def _physical_lines(*, second_pilot: bool = True, second_status: str = "In Service", day: int = 10) -> list[str]:
    lines = ["Null"] * 161
    # The observed marker is a structural discriminator, not a universal version.
    for index, value in {
        0: "160", 1: "Britain", 3: "Flight Sub-Lieutenant",
        4: "Synthetic", 5: "Tester", 6: str(day), 7: "11", 8: "1915",
        11: "80", 12: "1", 13: "3", 14: "1915", 16: "0", 17: "0",
        41: "60", 46: "1", 52: "1520", 60: "In Service",
        83: "HQ Synthetic Squadron", 84: "Synthetic_Nieuport",
        88: "Synthetic Station", 89: "Synthetic Sector", 100: "96",
    }.items():
        lines[index] = value
    lines[63:79] = ["N/A"] * 16
    lines[113:129] = ["N/A"] * 16
    lines[63] = _member("Squadron Commander", "Alex", "Able", kills=7)
    if second_pilot:
        lines[65] = _member(
            "Flight Lieutenant", "Blair", "Baker",
            kills=3, status=second_status,
        )
    lines[81] = "2" if second_pilot else "1"
    lines[113] = _member(
        "2nd Lieutenant", "Casey", "Clark", observer=True
    )
    # The three-field name is contextual, not a roster occurrence.
    lines[112] = "Captain;Context;Only"
    # An unrelated exact-six-field record must not poison roster extraction.
    lines[140] = "Unrelated;prose;with;exactly;six;fields"
    # Genuine physical blank lines reverse the key and preserve their indices.
    for index in (69, 70, 71, 153):
        lines[index] = ""
    return lines


def _bytes(**kwargs) -> bytes:
    return _encode_dossier(_physical_lines(**kwargs), "Pilot1Dossier.txt")


def test_161_physical_indices_and_context_remain_distinct():
    parser = WoFFDossierParser()
    assert parser.parse_bytes(_bytes(), "Pilot1Dossier.txt")
    assert parser.roster_complete is False
    assert len(parser.raw_strings) == 161
    assert parser.raw_strings[69:72] == ["", "", ""]
    assert parser.pilot is not None
    assert parser.pilot.squadron == "HQ Synthetic Squadron"
    assert parser.pilot.aircraft == "Synthetic_Nieuport"
    assert parser.pilot.photo == "96"
    assert {(w.fName, w.sName) for w in parser.wingmen} == {
        ("Alex", "Able"), ("Blair", "Baker"), ("Casey", "Clark"),
    }
    # Observed [4] is displayed as Kills, never as morale.
    alex = next(w for w in parser.wingmen if w.fName == "Alex")
    assert "morale" not in alex.present_fields
    assert "skill" not in alex.present_fields
    assert alex.status == "In Service"


def test_malformed_recognized_slot_fails_closed():
    for malformed in ("", "Not a roster record"):
        lines = _physical_lines()
        lines[65] = malformed
        # Keep the source-provided count at two to prove no silent drop.
        parser = WoFFDossierParser()
        assert not parser.parse_bytes(
            _encode_dossier(lines, "Pilot1Dossier.txt"), "Pilot1Dossier.txt"
        )
        assert parser.validation_status is DossierValidationStatus.INVALID_ROSTER
        assert parser.wingmen == []


def test_partial_dossier_keeps_pending_roster_and_never_infers_absence(
    dossier_runtime,
):
    db, processor, path = dossier_runtime
    path.write_bytes(_bytes())
    first = processor.process(str(path), "modified")
    assert first.acknowledged_generation is not None
    with db.transaction():
        state = db.load_dossier_state(
            "Synthetic Tester", campaign_namespace_for_root(str(path.parent)), 1
        )
    assert state is not None
    assert state.roster_baseline_pending
    assert state.roster_candidate is None
    old_ids = dict(db._get_conn().execute(
        "SELECT fName, id FROM squad_members WHERE pilotId = ?", (state.pilot_id,)
    ).fetchall())
    assert set(old_ids) == {"Alex", "Blair", "Casey"}

    # Blair's disappearance from a *partial detail block* must not erase
    # identity/memory or generate an absence candidate/event.
    path.write_bytes(_bytes(second_pilot=False, day=11))
    second = processor.process(str(path), "modified")
    assert second.acknowledged_generation is not None
    new_ids = dict(db._get_conn().execute(
        "SELECT fName, id FROM squad_members WHERE pilotId = ?", (state.pilot_id,)
    ).fetchall())
    assert new_ids == old_ids
    with db.transaction():
        latest = db.load_dossier_state(
            "Synthetic Tester", campaign_namespace_for_root(str(path.parent)), 1
        )
    assert latest is not None
    assert latest.squadron == "HQ Synthetic Squadron"
    assert latest.roster_baseline_pending
    assert latest.roster_candidate is None
    assert db._get_conn().execute(
        "SELECT COUNT(*) FROM diary_entries WHERE pilotId = ?",
        (state.pilot_id,),
    ).fetchone()[0] == 0
