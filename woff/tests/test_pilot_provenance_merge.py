"""Issue #99: Dossier provenance survives replay of partial pilot sources."""

import pytest

from ..database import DatabaseManager
from ..identity import PilotIdentityRejected
from ..models import WoFFPilot
from ..parsers.dossier_parser import WoFFDossierParser
from ..parsers.mission_log_parser import WoFFMissionLogParser
from ..parsers.pilot_data_parser import WoFFPilotDataParser
from ..parsers.xml_parser import WoFFXMLParser
from .identity_support import dependent_evidence, dossier_evidence
from .test_pilot_status_merge import _dossier_bytes


LOG = (
    "1\n6;4;1917;10;30;Arras;Filescamp;OP;SE.5a;;45;100;"
    "SE.5a;No. 56 Sqn;troops;Target;N50;E2;;Mission completed.\n"
)
CLAIMS = (
    "1\n6;4;1917;10;35;Arras;Filescamp;OP;SE.5a;1;"
    "Albatros D.III;Destroyed Confirmed;Albatros\n"
)
SQUADS = (
    "7;4;1917;10;30;Flanders;New Base;No. 60 Sqn;Sopwith Camel;"
    "Camel;Transferred, rank: Major.;No. 60 Squadron\n"
)
XML = b"<Campaign><Pilot><PilotName>James Hartley</PilotName></Pilot></Campaign>"
MISSION_LOG = (
    b'<Mission><Params Date="6/15/1917" Time="10:30" Weather="Clear" />'
    b'<AirFormation Country="RFC" SquadName="No. 56 Sqn">'
    b'<Unit IsPlayer="y" Type="SE.5a" />'
    b'</AirFormation></Mission>MissionEnded'
)
EARLY = "2026-08-23T12:34:56"
LATER = "2026-08-24T12:34:56"


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(str(tmp_path / "pilot-provenance.sqlite"))
    yield manager
    manager.close()


def _save(db, pilot, evidence):
    return db.merge_and_write(pilot, [], [], [], identity=evidence)


def _metadata(db, pilot_id):
    return db._get_conn().execute(
        "SELECT source_file, last_updated FROM pilots WHERE id=?",
        (pilot_id,),
    ).fetchone()


def _dossier(timestamp: str | None = EARLY):
    return WoFFPilot(
        name="James Hartley",
        source_file="Pilot1Dossier.txt",
        last_updated=timestamp,
        status="Active",
    )


@pytest.mark.parametrize("filename,content", [
    ("Pilot1Log.txt", LOG),
    ("Pilot1Claims.txt", CLAIMS),
    ("Pilot1Squads.txt", SQUADS),
])
def test_partial_parser_replay_keeps_authoritative_dossier_metadata(db, filename, content):
    parser = WoFFPilotDataParser()
    assert parser.parse_bytes(content, filename)
    assert parser.pilot is not None
    assert parser.pilot.last_updated is None
    assert parser.pilot.source_file == filename

    pilot_id = _save(db, _dossier(), dossier_evidence(1))
    expected = ("Pilot1Dossier.txt", EARLY)
    assert _metadata(db, pilot_id) == expected
    assert _save(db, parser.pilot, dependent_evidence(1)) == pilot_id
    assert _metadata(db, pilot_id) == expected
    assert _save(db, parser.pilot, dependent_evidence(1)) == pilot_id
    assert _metadata(db, pilot_id) == expected


def test_partial_supplied_timestamp_cannot_claim_authoritative_refresh(db):
    pilot_id = _save(db, _dossier(), dossier_evidence(1))
    partial = WoFFPilot(
        name="James Hartley",
        source_file="Pilot1Log.txt",
        last_updated="2026-09-01T00:00:00",
    )
    assert _save(db, partial, dependent_evidence(1)) == pilot_id
    assert _metadata(db, pilot_id) == ("Pilot1Dossier.txt", EARLY)


def test_authoritative_refresh_advances_but_old_or_absent_dossier_time_does_not_regress(db):
    pilot_id = _save(db, _dossier(), dossier_evidence(1))
    assert _save(db, _dossier(LATER), dossier_evidence(1)) == pilot_id
    assert _metadata(db, pilot_id) == ("Pilot1Dossier.txt", LATER)
    assert _save(db, _dossier(EARLY), dossier_evidence(1)) == pilot_id
    assert _metadata(db, pilot_id) == ("Pilot1Dossier.txt", LATER)
    assert _save(db, _dossier(None), dossier_evidence(1)) == pilot_id
    assert _metadata(db, pilot_id) == ("Pilot1Dossier.txt", LATER)


def test_missing_metadata_models_use_none_instead_of_writable_empty_values():
    assert WoFFPilot().source_file is None
    assert WoFFPilot().last_updated is None
    parser = WoFFXMLParser()
    assert parser.parse_bytes(XML, "campaign.xml")
    assert parser.pilot is not None
    assert parser.pilot.last_updated is None
    mission = WoFFMissionLogParser()
    assert mission.parse_bytes(MISSION_LOG, "Mission.log")
    assert mission.pilot is not None
    assert mission.pilot.last_updated is None


def test_unverified_xml_cannot_replace_stored_provenance(db):
    pilot_id = _save(db, _dossier(), dossier_evidence(1))
    parsed = WoFFXMLParser()
    assert parsed.parse_bytes(XML, "campaign.xml")
    with pytest.raises(PilotIdentityRejected):
        _save(db, parsed.pilot, None)
    assert _metadata(db, pilot_id) == ("Pilot1Dossier.txt", EARLY)


def test_verified_dossier_parser_refresh_is_retained_after_partial_replay(db):
    dossier = WoFFDossierParser()
    assert dossier.parse_bytes(_dossier_bytes("Active"), "Pilot1Dossier.txt")
    assert dossier.pilot is not None
    assert dossier.pilot.last_updated is not None
    timestamp = dossier.pilot.last_updated
    pilot_id = _save(db, dossier.pilot, dossier_evidence(1))
    assert _metadata(db, pilot_id) == ("Pilot1Dossier.txt", timestamp)
    assert _save(
        db,
        WoFFPilot(name="Pilot 1", source_file="Pilot1Log.txt"),
        dependent_evidence(1),
    ) == pilot_id
    assert _metadata(db, pilot_id) == ("Pilot1Dossier.txt", timestamp)


def test_legacy_valid_row_remains_readable_without_schema_rewrite(db):
    pilot_id = _save(db, _dossier(), dossier_evidence(1))
    with db.transaction():
        db._get_conn().execute(
            "UPDATE pilots SET source_file=?,last_updated=? WHERE id=?",
            ("Pilot1Dossier.txt", EARLY, pilot_id),
        )
    assert _save(
        db,
        WoFFPilot(name="James Hartley", source_file="Pilot1Claims.txt"),
        dependent_evidence(1),
    ) == pilot_id
    assert _metadata(db, pilot_id) == ("Pilot1Dossier.txt", EARLY)
