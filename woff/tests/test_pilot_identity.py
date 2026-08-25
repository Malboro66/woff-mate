import hashlib

import pytest

from ..campaign_namespace import campaign_namespace_for_root
from ..database import DatabaseManager
from ..identity import (
    PilotIdentityAmbiguous,
    PilotIdentityEvidence,
    PilotIdentityKind,
    PilotIdentityRejected,
    PilotIdentityUnavailable,
    dossier_source_name,
    pilot_slot,
)
from ..models import WoFFMission, WoFFPilot, WoFFVictory


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(str(tmp_path / "identity.sqlite"))
    yield manager
    manager.close()


DEFAULT_NAMESPACE = campaign_namespace_for_root(r"C:\Synthetic\Default")


def dossier_evidence(
    slot: int,
    marker: str,
    campaign_namespace: str = DEFAULT_NAMESPACE,
) -> PilotIdentityEvidence:
    return PilotIdentityEvidence(
        PilotIdentityKind.DOSSIER,
        slot,
        hashlib.sha256(marker.encode("ascii")).hexdigest(),
        campaign_namespace,
    )


def dependent_evidence(
    slot: int,
    marker: str,
    campaign_namespace: str = DEFAULT_NAMESPACE,
) -> PilotIdentityEvidence:
    return PilotIdentityEvidence(
        PilotIdentityKind.SLOT_DEPENDENT,
        slot,
        hashlib.sha256(marker.encode("ascii")).hexdigest(),
        campaign_namespace,
    )


def _rows(db, sql: str, parameters=()):
    return db._get_conn().execute(sql, parameters).fetchall()


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
    with pytest.raises(ValueError, match="campaign namespace"):
        PilotIdentityEvidence(PilotIdentityKind.DOSSIER, 1, "a" * 64)


def test_dossier_source_name_is_canonical():
    assert dossier_source_name(7) == "Pilot7Dossier.txt"


def test_binding_key_includes_campaign_namespace_and_slot():
    evidence = dossier_evidence(7, "binding-key")

    assert evidence.binding_key == (DEFAULT_NAMESPACE, 7)
    with pytest.raises(ValueError, match="no binding key"):
        PilotIdentityEvidence(PilotIdentityKind.UNRESOLVED).binding_key


def test_same_name_careers_in_different_slots_keep_distinct_ids(db):
    first = WoFFPilot(
        id="career-a", name="Same Name", source_file="Pilot1Dossier.txt"
    )
    second = WoFFPilot(
        id="career-b", name="Same Name", source_file="Pilot2Dossier.txt"
    )

    assert db.merge_and_write(
        first, [], [], [], identity=dossier_evidence(1, "a")
    ) == "career-a"
    assert db.merge_and_write(
        second, [], [], [], identity=dossier_evidence(2, "b")
    ) == "career-b"
    assert _rows(db, "SELECT id, name FROM pilots ORDER BY id") == [
        ("career-a", "Same Name"),
        ("career-b", "Same Name"),
    ]
    assert db.resolve_pilot_id("Same Name") is None


def test_same_slot_in_distinct_roots_keeps_independent_bindings(db):
    root_a = campaign_namespace_for_root(r"C:\Campaigns\RootA")
    root_b = campaign_namespace_for_root(r"D:\Campaigns\RootB")
    first = WoFFPilot(
        id="career-root-a", name="Same Name", source_file="Pilot1Dossier.txt"
    )
    second = WoFFPilot(
        id="career-root-b", name="Same Name", source_file="Pilot1Dossier.txt"
    )

    assert db.merge_and_write(
        first,
        [],
        [],
        [],
        identity=dossier_evidence(1, "same-digest", root_a),
    ) == "career-root-a"
    assert db.merge_and_write(
        second,
        [],
        [],
        [],
        identity=dossier_evidence(1, "same-digest", root_b),
    ) == "career-root-b"

    assert _rows(
        db,
        "SELECT campaign_namespace, slot, pilotId "
        "FROM pilot_slot_bindings ORDER BY pilotId",
    ) == [
        (root_a, 1, "career-root-a"),
        (root_b, 1, "career-root-b"),
    ]

    assert db.merge_and_write(
        WoFFPilot(name="Pilot 1", squadron="A Sqn", source_file="Pilot1Log.txt"),
        [],
        [],
        [],
        identity=dependent_evidence(1, "same-digest", root_a),
    ) == "career-root-a"
    assert db.merge_and_write(
        WoFFPilot(name="Pilot 1", squadron="B Sqn", source_file="Pilot1Log.txt"),
        [],
        [],
        [],
        identity=dependent_evidence(1, "same-digest", root_b),
    ) == "career-root-b"
    assert _rows(db, "SELECT id, squadron FROM pilots ORDER BY id") == [
        ("career-root-a", "A Sqn"),
        ("career-root-b", "B Sqn"),
    ]

    assert db.merge_and_write(
        WoFFPilot(
            id="career-root-a-next",
            name="Alice Next",
            source_file="Pilot1Dossier.txt",
        ),
        [],
        [],
        [],
        identity=dossier_evidence(1, "root-a-next", root_a),
    ) == "career-root-a-next"
    assert _rows(
        db,
        "SELECT campaign_namespace, pilotId "
        "FROM pilot_slot_bindings ORDER BY pilotId",
    ) == sorted(
        [
            (root_a, "career-root-a-next"),
            (root_b, "career-root-b"),
        ],
        key=lambda row: row[1],
    )


def test_retired_career_is_never_reused_across_campaign_namespaces(db):
    root_a = campaign_namespace_for_root(r"C:\Campaigns\RootA")
    root_b = campaign_namespace_for_root(r"D:\Campaigns\RootB")

    assert db.merge_and_write(
        WoFFPilot(
            id="root-a-alice",
            name="Alice",
            squadron="Root A History",
            source_file="Pilot1Dossier.txt",
        ),
        [
            WoFFMission(
                id="root-a-history",
                pilotId="root-a-alice",
                date="1917-04-01",
                time="08:00",
            )
        ],
        [],
        [],
        identity=dossier_evidence(1, "root-a-alice", root_a),
    ) == "root-a-alice"
    assert db.merge_and_write(
        WoFFPilot(
            id="root-a-bob",
            name="Bob",
            squadron="Root A Current",
            source_file="Pilot1Dossier.txt",
        ),
        [],
        [],
        [],
        identity=dossier_evidence(1, "root-a-bob", root_a),
    ) == "root-a-bob"
    assert db.merge_and_write(
        WoFFPilot(
            id="root-b-alice",
            name="Alice",
            squadron="Root B Current",
            source_file="Pilot1Dossier.txt",
        ),
        [],
        [],
        [],
        identity=dossier_evidence(1, "root-b-alice", root_b),
    ) == "root-b-alice"

    assert db.merge_and_write(
        WoFFPilot(
            name="Pilot 1",
            squadron="Root B Updated",
            source_file="Pilot1Log.txt",
        ),
        [],
        [],
        [],
        identity=dependent_evidence(1, "root-b-alice", root_b),
    ) == "root-b-alice"
    assert _rows(
        db,
        "SELECT id, name, squadron FROM pilots ORDER BY id",
    ) == [
        ("root-a-alice", "Alice", "Root A History"),
        ("root-a-bob", "Bob", "Root A Current"),
        ("root-b-alice", "Alice", "Root B Updated"),
    ]
    assert _rows(db, "SELECT id, pilotId FROM missions") == [
        ("root-a-history", "root-a-alice")
    ]
    assert _rows(
        db,
        "SELECT campaign_namespace, slot, pilotId "
        "FROM pilot_slot_bindings ORDER BY pilotId",
    ) == sorted(
        [
            (root_a, 1, "root-a-bob"),
            (root_b, 1, "root-b-alice"),
        ],
        key=lambda row: row[2],
    )


def test_dossier_name_change_rotates_binding_without_mutating_old_career(db):
    old = WoFFPilot(
        id="career-a",
        name="Alice",
        rank="Captain",
        squadron="Old Sqn",
        source_file="Pilot1Dossier.txt",
    )
    new = WoFFPilot(
        id="career-b",
        name="Bob",
        rank="Lieutenant",
        squadron="New Sqn",
        source_file="Pilot1Dossier.txt",
    )
    db.merge_and_write(old, [], [], [], identity=dossier_evidence(1, "old"))
    db.merge_and_write(new, [], [], [], identity=dossier_evidence(1, "new"))

    assert _rows(
        db,
        "SELECT id, name, rank, squadron, source_file FROM pilots ORDER BY id",
    ) == [
        ("career-a", "Alice", "Captain", "Old Sqn", "Pilot1Dossier.txt"),
        ("career-b", "Bob", "Lieutenant", "New Sqn", "Pilot1Dossier.txt"),
    ]
    assert _rows(db, "SELECT slot, pilotId FROM pilot_slot_bindings") == [
        (1, "career-b")
    ]


def test_slot_dependent_write_requires_matching_current_dossier_digest(db):
    db.merge_and_write(
        WoFFPilot(
            id="career-a", name="Alice", source_file="Pilot1Dossier.txt"
        ),
        [],
        [],
        [],
        identity=dossier_evidence(1, "old"),
    )
    partial = WoFFPilot(name="Pilot 1", source_file="Pilot1Log.txt")

    with pytest.raises(PilotIdentityUnavailable, match="stale-dossier-binding"):
        db.merge_and_write(
            partial,
            [],
            [],
            [],
            identity=dependent_evidence(1, "new"),
        )
    assert _rows(db, "SELECT id, name, source_file FROM pilots") == [
        ("career-a", "Alice", "Pilot1Dossier.txt")
    ]


def test_matching_slot_dependent_write_targets_only_bound_career(db):
    db.merge_and_write(
        WoFFPilot(
            id="career-a", name="Alice", source_file="Pilot1Dossier.txt"
        ),
        [],
        [],
        [],
        identity=dossier_evidence(1, "current"),
    )
    partial = WoFFPilot(
        id="discarded-parser-id",
        name="Pilot 1",
        squadron="Updated Sqn",
        source_file="Pilot1Log.txt",
    )

    assert db.merge_and_write(
        partial,
        [],
        [],
        [],
        identity=dependent_evidence(1, "current"),
    ) == "career-a"
    assert _rows(db, "SELECT id, name, squadron FROM pilots") == [
        ("career-a", "Alice", "Updated Sqn")
    ]


def test_identityless_pilot_is_rejected_before_any_write(db):
    blank = WoFFPilot(id="phantom", name="")
    mission = WoFFMission(id="mission", source_file="Mission.log")
    with pytest.raises(PilotIdentityRejected, match="unsupported-identity-source"):
        db.merge_and_write(
            blank,
            [mission],
            [],
            [],
            identity=PilotIdentityEvidence(PilotIdentityKind.UNRESOLVED),
        )
    assert _rows(db, "SELECT COUNT(*) FROM pilots") == [(0,)]
    assert _rows(db, "SELECT COUNT(*) FROM missions") == [(0,)]


def test_same_name_same_slot_dossier_replay_preserves_bound_id(db):
    first = WoFFPilot(
        id="career-a", name="Alice", source_file="Pilot1Dossier.txt"
    )
    replay = WoFFPilot(
        id="new-parser-id",
        name="Alice",
        rank="Captain",
        source_file="Pilot1Dossier.txt",
    )
    assert db.merge_and_write(
        first, [], [], [], identity=dossier_evidence(1, "first")
    ) == "career-a"
    assert db.merge_and_write(
        replay, [], [], [], identity=dossier_evidence(1, "replay")
    ) == "career-a"

    assert _rows(db, "SELECT id, rank FROM pilots") == [("career-a", "Captain")]
    assert _rows(db, "SELECT pilotId FROM pilot_slot_bindings") == [
        ("career-a",)
    ]


def test_new_pilot_requires_typed_identity_evidence(db):
    pilot = WoFFPilot(
        id="career-a", name="Alice", source_file="Pilot1Dossier.txt"
    )

    with pytest.raises(PilotIdentityRejected, match="unsupported-identity-source"):
        db.merge_and_write(pilot, [], [], [])
    assert _rows(db, "SELECT COUNT(*) FROM pilots") == [(0,)]


def test_pilot_free_write_rejects_mixed_or_unknown_explicit_ids(db):
    for pilot_id, slot in (("career-a", 1), ("career-b", 2)):
        db.merge_and_write(
            WoFFPilot(
                id=pilot_id,
                name=pilot_id,
                source_file=f"Pilot{slot}Dossier.txt",
            ),
            [],
            [],
            [],
            identity=dossier_evidence(slot, pilot_id),
        )

    with pytest.raises(PilotIdentityAmbiguous, match="mixed-explicit-pilot-ids"):
        db.merge_and_write(
            None,
            [WoFFMission(id="mission-a", pilotId="career-a")],
            [WoFFVictory(id="victory-b", pilotId="career-b")],
            [],
        )
    with pytest.raises(PilotIdentityRejected, match="unknown-explicit-pilot-id"):
        db.merge_and_write(
            None,
            [WoFFMission(id="unknown", pilotId="missing")],
            [],
            [],
        )

    assert _rows(db, "SELECT COUNT(*) FROM missions") == [(0,)]
    assert _rows(db, "SELECT COUNT(*) FROM victories") == [(0,)]
