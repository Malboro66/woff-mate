"""Issue #136: closed identities, source parity and lossless stored evidence."""

from dataclasses import FrozenInstanceError
import io
import sqlite3
from xml.sax.saxutils import escape

import pytest

from ..database import DatabaseManager
from ..models import WoFFPilot
from ..parsers.dossier_parser import WoFFDossierParser
from ..parsers.xml_parser import WoFFXMLParser
from ..parsers.mission_log_parser import WoFFMissionLogParser
from .identity_support import dossier_evidence, dependent_evidence
from .test_dossier_parser import _dossier_fixture, _encode_dossier


CASES = [
    ("GB", "GB", None), ("FR", "FR", None), ("DE", "DE", None),
    ("US", "US", None), ("BE", "BE", None),
    ("Britain", "GB", None), ("British", "GB", None), ("UK", "GB", None),
    ("RFC", "GB", "RFC"), ("Royal Flying Corps", "GB", "RFC"),
    ("RNAS", "GB", "RNAS"), ("Royal Naval Air Service", "GB", "RNAS"),
    ("naval", "GB", "RNAS"), ("RAF", "GB", "RAF"),
    ("Royal Air Force", "GB", "RAF"),
    ("French", "FR", None), ("France", "FR", None), ("aeronautique", "FR", None),
    ("German", "DE", None), ("Germany", "DE", None),
    ("luftstreitkrafte", "DE", None), ("deutsche", "DE", None),
    ("American", "US", None), ("USAS", "US", None), ("USA", "US", None),
    ("Belgian", "BE", None), ("Belgium", "BE", None), ("belge", "BE", None),
    ("Brazil", None, None), ("Russia", None, None), ("Austria", None, None),
    ("Martian", None, None), ("Prussia", None, None), ("RAF veteran", None, None),
    ("", None, None), ("   ", None, None),
]


def test_exactly_five_nations_and_three_evidence_backed_services():
    from ..nation import NationCode, ServiceCode

    assert {value.value for value in NationCode} == {"GB", "FR", "DE", "US", "BE"}
    assert {value.value for value in ServiceCode} == {"RFC", "RNAS", "RAF"}
    for raw in ("Brazil", "Russia", "Austria", "Martian", "RFC"):
        with pytest.raises(ValueError):
            NationCode(raw)


@pytest.mark.parametrize("raw,nation,service", CASES)
def test_domain_and_parser_parity(raw, nation, service):
    lines = _dossier_fixture("current_full_sanitized.txt")
    lines[1] = raw or "Null"
    # A birthplace and a surname are not nation/service evidence.
    lines[5] = "French"
    lines[92] = "Britain"
    dossier = WoFFDossierParser()
    assert dossier.parse_bytes(_encode_dossier(lines, "Pilot1Dossier.txt"), "Pilot1Dossier.txt")
    xml = WoFFXMLParser()
    assert xml.parse_bytes(
        f"<Root><Pilot><PilotName>Sample French</PilotName><Nation>{escape(raw)}</Nation></Pilot></Root>".encode(),
        "sample.xml",
    )
    expected_state = "known" if nation else "unsupported" if raw.strip() else "missing"
    for pilot in (WoFFPilot(nation=raw), dossier.pilot, xml.pilot):
        assert pilot is not None
        assert pilot.nation_code == nation
        assert pilot.service_code == service
        assert pilot.nation_state == expected_state
        assert pilot.nation_raw == raw.strip()
        assert pilot.affiliation.service_state == (
            "known" if service else "missing_or_unknown"
        )


@pytest.mark.parametrize("raw,nation,service", CASES)
def test_case_whitespace_and_mission_log_use_same_domain(raw, nation, service):
    from ..nation import NationService

    value = NationService(f"  {raw.swapcase()}  ")
    assert (value.nation_code, value.service_code) == (nation, service)
    parser = WoFFMissionLogParser()
    assert parser.parse_bytes(
        (
            '<Mission><Params Date="6/15/1917" Time="10:30" />'
            f'<AirFormation Country="{escape(raw)}" SquadName="Sample Squadron">'
            '<Unit IsPlayer="y" Type="SE.5a" /></AirFormation></Mission>MissionEnded'
        ).encode(), "mission.log",
    )
    assert parser.pilot is not None
    assert parser.pilot.affiliation == NationService(raw)


def test_snapshot_is_immutable_and_does_not_expose_private_evidence():
    from ..nation import NationService

    pilot = WoFFPilot(nation="RFC")
    snapshot = pilot.affiliation
    assert snapshot.nation_code == "GB"
    assert snapshot.service_code == "RFC"
    with pytest.raises(FrozenInstanceError):
        setattr(snapshot, "nation_raw", "France")
    with pytest.raises(AttributeError):
        setattr(pilot, "nation_code", "FR")
    pilot.nation = "RNAS"
    assert snapshot.service_code == "RFC"
    assert pilot.service_code == "RNAS"
    for raw in ("RFC", "Britain", "", "Martian", r"C:\Private\Campaign\Pilot.txt"):
        value = NationService(raw)
        view = value.presentation()
        assert view.nation_code == value.nation_code
        assert view.service_code == value.service_code
        assert view.nation_state == value.nation_state
        assert "Private" not in repr(view)
        assert not hasattr(view, "serviceOrNationLabel")
        with pytest.raises(FrozenInstanceError):
            setattr(view, "nation_label", "France")
    view = NationService("RFC").presentation()
    assert view.nation_label == "Britain"
    assert view.service_label == "RFC"
    assert NationService("Britain").presentation().service_label is None
    assert NationService("Martian").presentation().nation_label == "Unsupported nation"


@pytest.mark.parametrize("raw,nation,service", CASES)
def test_legacy_and_new_evidence_survive_reopen_without_schema_migration(tmp_path, raw, nation, service):
    path = tmp_path / "nation.sqlite"
    db = DatabaseManager(str(path))
    try:
        with db.transaction():
            db._get_conn().execute("INSERT INTO pilots (id, name, nation) VALUES (?, ?, ?)", ("legacy", "Legacy Pilot", raw))
        schema = db._get_conn().execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
        lines = _dossier_fixture("current_full_sanitized.txt")
        lines[1] = raw or "Null"
        parser = WoFFDossierParser()
        assert parser.parse_bytes(_encode_dossier(lines, "Pilot1Dossier.txt"), "Pilot1Dossier.txt")
        pilot = parser.pilot
        assert pilot is not None
        db.merge_and_write(pilot, [], [], [], identity=dossier_evidence(1))
        pilot_id = pilot.id
    finally:
        db.close()
    reopened = DatabaseManager(str(path))
    try:
        for identity in ("legacy", pilot_id):
            value = reopened.get_pilot_nation_service(identity)
            assert value is not None
            assert (value.nation_code, value.service_code) == (nation, service)
            assert value.nation_raw == raw.strip()
        assert reopened._get_conn().execute("SELECT nation FROM pilots WHERE id='legacy'").fetchone()[0] == raw
        assert reopened._get_conn().execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall() == schema
        assert reopened._get_conn().execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert reopened._get_conn().execute("PRAGMA foreign_key_check").fetchall() == []
        assert not (tmp_path / ".woff-migration-backups").exists()
    finally:
        reopened.close()


def test_missing_partial_input_preserves_service_and_failed_write_rolls_back(tmp_path):
    db = DatabaseManager(str(tmp_path / "merge.sqlite"))
    try:
        pilot = WoFFPilot(name="Sample Pilot", nation="RNAS", source_file="Pilot1Dossier.txt")
        db.merge_and_write(pilot, [], [], [], identity=dossier_evidence(1))
        partial = WoFFPilot(name="Sample Pilot", source_file="Pilot1Log.txt")
        db.merge_and_write(partial, [], [], [], identity=dependent_evidence(1))
        before = db.get_pilot_nation_service(pilot.id)
        assert before is not None and before.service_code == "RNAS"
        pilot.nation = "Martian"
        with pytest.raises(RuntimeError):
            with db.transaction():
                db.merge_and_write(pilot, [], [], [], identity=dossier_evidence(1))
                raise RuntimeError("injected failure")
        assert db.get_pilot_nation_service(pilot.id) == before
        db.merge_and_write(pilot, [], [], [], identity=dossier_evidence(1))
        value = db.get_pilot_nation_service(pilot.id)
        assert value is not None and value.nation_state == "unsupported"
        assert value.nation_raw == "Martian"
    finally:
        db.close()


@pytest.mark.parametrize("raw,nation_label,service_label", [
    ("RFC", "Britain", "RFC"), ("RNAS", "Britain", "RNAS"),
    ("RAF", "Britain", "RAF"), ("French", "France", "Vazio"),
    ("Britain", "Britain", "Vazio"), ("", "Vazio", "Vazio"),
    ("Martian", "Unsupported nation", "Vazio"),
    (r"C:\Private\Campaign\Pilot.txt", "Unsupported nation", "Vazio"),
])
def test_cli_and_report_consume_separate_safe_labels(tmp_path, capsys, raw, nation_label, service_label):
    from woff_query import Colors, show_pilot_details
    from ..career_selection import CareerSelection
    from ..gerar_relatorio import _write_report

    path = tmp_path / "presentation.sqlite"
    db = DatabaseManager(str(path))
    try:
        with db.transaction():
            db._get_conn().execute("INSERT INTO pilots (id, name, nation) VALUES (?, ?, ?)", ("sample", "Sample Pilot", raw))
    finally:
        db.close()
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        assert show_pilot_details(conn, CareerSelection("sample", "Sample Pilot", 1), Colors(False))
    output = capsys.readouterr().out
    assert f"Nação: {nation_label}" in output
    assert f"Serviço: {service_label}" in output
    assert "Private" not in output

    lines = _dossier_fixture("current_full_sanitized.txt")
    lines[1] = raw or "Null"
    (tmp_path / "Pilot1Dossier.txt").write_bytes(_encode_dossier(lines, "Pilot1Dossier.txt"))
    report = io.StringIO()
    _write_report(report, [str(tmp_path)])
    output = report.getvalue()
    assert nation_label in output
    assert service_label in output
    assert "Private" not in output
