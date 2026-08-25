import pytest

from ..campaign_engine import CampaignEngine
from ..database import DatabaseManager
from ..handler import FileProcessor
from ..ingestion.outcome import ProcessingStatus
from ..identity import PilotIdentityEvidence, PilotIdentityKind, PilotIdentityRejected
from ..models import WoFFPilot
from ..normalization import normalize_status
from ..parsers.dossier_parser import WoFFDossierParser
from ..parsers.mission_log_parser import WoFFMissionLogParser
from ..parsers.pilot_data_parser import WoFFPilotDataParser
from ..parsers.xml_parser import WoFFXMLParser
from .identity_support import dependent_evidence, dossier_evidence
from .test_dossier_parser import _encode_dossier


STATUS_STATS = (12, 845, 7, 5, 68, 420)
LOG_DATA = (
    "1\n6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;"
    "SE.5a;No. 56 Sqn;troops;Target;N50;E2;;Mission completed.\n"
)
CLAIMS_DATA = (
    "1\n6;4;1917;10;35;Arras;Filescamp;OP;SE.5a;1;"
    "Albatros D.III;Destroyed Confirmed;Albatros\n"
)
SQUADS_DATA = (
    "7;4;1917;10;30;Flanders;New Base;No. 60 Sqn;Sopwith Camel;"
    "Camel;Transferred, rank: Major.;No. 60 Squadron\n"
)
PARTIAL_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Campaign>
  <Pilot>
    <PilotName>James Hartley</PilotName>
    <Rank>Major</Rank>
    <Squadron>No. 60 Sqn</Squadron>
  </Pilot>
</Campaign>
"""
MISSION_LOG = (
    b'<Mission><Params Date="6/15/1917" Time="10:30" Weather="Clear" />'
    b'<AirFormation Country="RFC" SquadName="No. 56 Sqn">'
    b'<Unit IsPlayer="y" Type="SE.5a" />'
    b'</AirFormation></Mission>MissionEnded'
)


@pytest.fixture
def database(tmp_path):
    manager = DatabaseManager(str(tmp_path / "pilot-status.sqlite"))
    yield manager
    manager.close()


def _dossier_bytes(status: str | None, *, rank: str = "Captain") -> bytes:
    lines = ["Null"] * 105
    values = {
        1: "Britain",
        3: rank,
        4: "James",
        5: "Hartley",
        6: "6",
        7: "4",
        8: "1917",
        11: str(STATUS_STATS[1]),
        16: str(STATUS_STATS[2]),
        17: str(STATUS_STATS[3]),
        41: str(STATUS_STATS[4]),
        46: str(STATUS_STATS[0]),
        52: str(STATUS_STATS[5]),
        83: "No. 56 Sqn",
        84: "SE.5a",
        88: "Filescamp",
        89: "Arras",
    }
    if status is not None:
        values[60] = status
    for index, value in values.items():
        lines[index] = value
    return _encode_dossier(lines, "Pilot1Dossier.txt")


def _parse_dossier(status: str | None, *, rank: str = "Captain") -> WoFFPilot:
    parser = WoFFDossierParser()
    assert parser.parse_bytes(
        _dossier_bytes(status, rank=rank), "Pilot1Dossier.txt"
    )
    assert parser.pilot is not None
    return parser.pilot


def _stored_state(database: DatabaseManager):
    return database._get_conn().execute(
        """
        SELECT status, missions, flminutes, claimsCount, killsCount, skill,
               reputation, rank, squadron
        FROM pilots WHERE name='James Hartley'
        """
    ).fetchone()


def _persist_dossier(
    database: DatabaseManager, status: str | None, *, marker: str = "current"
) -> str:
    pilot = _parse_dossier(status)
    pilot_id = database.merge_and_write(
        pilot, [], [], [], identity=dossier_evidence(1, marker)
    )
    assert pilot_id is not None
    return pilot_id


def test_missing_status_is_explicit_across_all_partial_parser_models():
    assert WoFFPilot().status is None
    assert normalize_status("") is None
    assert normalize_status("Missed a deadline") is None
    assert normalize_status("Active") == "Active"

    for filename, content in (
        ("Pilot1Log.txt", LOG_DATA),
        ("Pilot1Claims.txt", CLAIMS_DATA),
        ("Pilot1Squads.txt", SQUADS_DATA),
    ):
        parser = WoFFPilotDataParser()
        assert parser.parse_bytes(content, filename)
        assert parser.pilot is not None
        assert parser.pilot.status is None

    xml_parser = WoFFXMLParser()
    assert xml_parser.parse_bytes(PARTIAL_XML, "campaign.xml")
    assert xml_parser.pilot is not None
    assert xml_parser.pilot.status is None

    mission_parser = WoFFMissionLogParser()
    assert mission_parser.parse_bytes(MISSION_LOG, "Mission.log")
    assert mission_parser.pilot is not None
    assert mission_parser.pilot.status is None


def test_missing_dossier_status_stays_null_until_authoritative_input(database):
    missing = _parse_dossier(None)
    assert missing.status is None
    pilot_id = database.merge_and_write(
        missing, [], [], [], identity=dossier_evidence(1, "missing")
    )
    assert pilot_id is not None
    assert _stored_state(database)[:7] == (None, *STATUS_STATS)

    explicit = _parse_dossier("KIA")
    assert database.merge_and_write(
        explicit, [], [], [], identity=dossier_evidence(1, "explicit")
    ) == pilot_id
    assert _stored_state(database)[:7] == ("KIA", *STATUS_STATS)


def test_explicit_active_and_kia_transitions_remain_writable(database):
    pilot_id = _persist_dossier(database, "Active", marker="active-1")
    assert _stored_state(database)[:7] == ("Active", *STATUS_STATS)

    for status, marker in (("KIA", "kia"), ("Active", "active-2")):
        assert database.merge_and_write(
            _parse_dossier(status),
            [],
            [],
            [],
            identity=dossier_evidence(1, marker),
        ) == pilot_id
        assert _stored_state(database)[:7] == (status, *STATUS_STATS)


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("Pilot1Log.txt", LOG_DATA),
        ("Pilot1Claims.txt", CLAIMS_DATA),
        ("Pilot1Squads.txt", SQUADS_DATA),
    ],
)
def test_partial_text_sources_preserve_kia_and_numeric_statistics(
    database, filename, content
):
    pilot_id = _persist_dossier(database, "KIA")
    parser = WoFFPilotDataParser()
    assert parser.parse_bytes(content, filename)
    assert parser.pilot is not None

    snapshots = []
    for _ in range(2):
        assert database.merge_and_write(
            parser.pilot,
            parser.missions,
            parser.victories,
            [],
            identity=dependent_evidence(1, "current"),
        ) == pilot_id
        assert _stored_state(database)[:7] == ("KIA", *STATUS_STATS)
        snapshots.append(
            (
                _stored_state(database),
                database._get_conn().execute(
                    "SELECT COUNT(*) FROM missions"
                ).fetchone(),
                database._get_conn().execute(
                    "SELECT COUNT(*) FROM victories"
                ).fetchone(),
            )
        )
    assert snapshots[0] == snapshots[1]


def test_slot_dependent_status_cannot_override_authoritative_dossier(database):
    pilot_id = _persist_dossier(database, "KIA")
    accidental_status = WoFFPilot(
        name="Pilot 1",
        status="Active",
        squadron="New Sqn",
        source_file="Pilot1Log.txt",
    )

    assert database.merge_and_write(
        accidental_status,
        [],
        [],
        [],
        identity=dependent_evidence(1, "current"),
    ) == pilot_id
    assert _stored_state(database) == (
        "KIA",
        *STATUS_STATS,
        "Captain",
        "New Sqn",
    )


def test_partial_xml_is_absent_and_cannot_change_authoritative_state(database):
    _persist_dossier(database, "KIA")
    parser = WoFFXMLParser()
    assert parser.parse_bytes(PARTIAL_XML, "campaign.xml")
    assert parser.pilot is not None
    assert parser.pilot.status is None

    with pytest.raises(PilotIdentityRejected, match="unsupported-identity-source"):
        database.merge_and_write(
            parser.pilot,
            parser.missions,
            parser.victories,
            parser.decorations,
            identity=PilotIdentityEvidence(PilotIdentityKind.UNRESOLVED),
        )
    assert _stored_state(database)[:7] == ("KIA", *STATUS_STATS)


def test_explicit_active_transition_writes_one_life_event(tmp_path):
    database = DatabaseManager(str(tmp_path / "life-event.sqlite"))
    processor = FileProcessor(
        database,
        CampaignEngine(database),
        stability_timeout=0.5,
        stability_interval=0.001,
    )
    dossier_path = tmp_path / "Pilot1Dossier.txt"

    try:
        dossier_path.write_bytes(_dossier_bytes(None))
        first_generation = processor.process(str(dossier_path), "initial")
        assert first_generation.status is ProcessingStatus.SUCCESS
        assert _stored_state(database)[:7] == (None, *STATUS_STATS)
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM diary_entries"
        ).fetchone() == (0,)

        dossier_path.write_bytes(_dossier_bytes("Wounded"))
        established_generation = processor.process(
            str(dossier_path), "modified", first_generation
        )
        assert established_generation.status is ProcessingStatus.SUCCESS
        assert established_generation.generation != first_generation.generation
        assert _stored_state(database)[:7] == ("Wounded", *STATUS_STATS)
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM diary_entries"
        ).fetchone() == (0,)

        dossier_path.write_bytes(_dossier_bytes(None))
        missing_generation = processor.process(
            str(dossier_path), "modified", established_generation
        )
        assert missing_generation.status is ProcessingStatus.SUCCESS
        assert missing_generation.generation != established_generation.generation
        assert _stored_state(database)[:7] == ("Wounded", *STATUS_STATS)
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM diary_entries"
        ).fetchone() == (0,)

        dossier_path.write_bytes(_dossier_bytes("Active"))
        second_generation = processor.process(
            str(dossier_path), "modified", missing_generation
        )
        assert second_generation.status is ProcessingStatus.SUCCESS
        assert second_generation.generation != missing_generation.generation
        assert _stored_state(database)[:7] == ("Active", *STATUS_STATS)

        rows = database._get_conn().execute(
            "SELECT narrative FROM diary_entries"
        ).fetchall()
        assert len(rows) == 1
        assert "alta médica" in rows[0][0]

        replayed = processor.process(str(dossier_path), "modified")
        assert replayed.status is ProcessingStatus.SUCCESS
        assert replayed.generation == second_generation.generation
        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM diary_entries"
        ).fetchone() == (1,)
    finally:
        database.close()


def test_file_processor_log_preserves_kia_without_status_life_event(tmp_path):
    database = DatabaseManager(str(tmp_path / "processor.sqlite"))
    processor = FileProcessor(
        database,
        CampaignEngine(database),
        stability_timeout=0.5,
        stability_interval=0.001,
    )
    dossier_path = tmp_path / "Pilot1Dossier.txt"
    log_path = tmp_path / "Pilot1Log.txt"

    try:
        dossier_path.write_bytes(_dossier_bytes("KIA"))
        log_path.write_text(LOG_DATA, encoding="cp1252")
        assert (
            processor.process(str(dossier_path), "initial").status
            is ProcessingStatus.SUCCESS
        )
        assert (
            processor.process(str(log_path), "modified").status
            is ProcessingStatus.SUCCESS
        )
        assert _stored_state(database)[:7] == ("KIA", *STATUS_STATS)

        assert database._get_conn().execute(
            "SELECT COUNT(*) FROM diary_entries WHERE missionId IS NULL"
        ).fetchone() == (0,)
    finally:
        database.close()
