"""Issue #44: XML-aware Mission boundary with trailing text debrief."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from ..handler import FileProcessor, ProcessingReason
from ..parsers.mission_log_parser import WoFFMissionLogParser


def _mission_xml(
    inside: str = "",
    *,
    open_tag: str = "<Mission>",
    close_tag: str = "</Mission>",
    trailing: str = "MissionEnded",
) -> bytes:
    xml = (
        f'{open_tag}{inside}'
        '<Params Date="9/20/1915" Time="9:30" Weather="Clear"/>'
        '<Overview>Approved briefing</Overview>'
        f"{close_tag}"
    )
    return (xml + "\n" + trailing).encode("utf-8")


@pytest.mark.parametrize(
    "inside",
    [
        "<!-- misleading </Mission> in a comment -->",
        "<Overview><![CDATA[literal </Mission> inside CDATA]]></Overview>",
        "<!-- a > terminator is not a root close -->",
        "<Nested><Nested/></Nested>",
    ],
)
def test_internal_text_cannot_end_root(inside: str) -> None:
    parser = WoFFMissionLogParser()
    assert parser.parse_bytes(_mission_xml(inside), "Mission.log")
    assert parser.mission is not None
    assert (parser.mission.date, parser.mission.time) == ("1915-09-20", "09:30")
    assert parser.mission.result == "Completed"
    assert parser.debriefing == "Mission Ended Successfully"


@pytest.mark.parametrize(
    ("open_tag", "close_tag"),
    [
        ('<Mission Version="1" Mode="sim">', "</Mission>"),
        (" \t\n<Mission   Version='1' >", "  </Mission   >"),
        ("<?xml version='1.0'?>\n<Mission>", "</Mission>"),
    ],
)
def test_root_attributes_and_whitespace_are_valid(
    open_tag: str, close_tag: str
) -> None:
    parser = WoFFMissionLogParser()
    assert parser.parse_bytes(_mission_xml(open_tag=open_tag, close_tag=close_tag), "Mission.log")
    assert parser.mission is not None
    assert parser.mission.result == "Completed"


def test_debrief_starts_after_real_root_and_preserves_normal_format() -> None:
    parser = WoFFMissionLogParser()
    assert parser.parse_bytes(
        _mission_xml(
            '<Overview><![CDATA[</Mission> pretend forced landing on friendly field]]></Overview>',
            trailing="\nMissionEnded",
        ),
        "Mission.log",
    )
    assert parser.mission is not None
    assert parser.mission.result == "Completed"
    assert parser.debriefing == "Mission Ended Successfully"


def test_post_xml_forced_landing_still_takes_precedence() -> None:
    parser = WoFFMissionLogParser()
    assert parser.parse_bytes(
        _mission_xml(trailing="MissionEnded\nForced landing on friendly field"),
        "Mission.log",
    )
    assert parser.mission is not None
    assert parser.mission.result == "Force-Landed (Friendly Lines)"


@pytest.mark.parametrize(
    "invalid",
    [
        b"<Mission><Params Date='9/20/1915'/>",
        b"<Mission><Params Date='9/20/1915'></Mission>",
        b"<WrongRoot><Params Date='9/20/1915'/></WrongRoot>",
        b"<Mission/>",
        b"<!DOCTYPE Mission [<!ENTITY secret 'expansion'>]>"
        b"<Mission><Params Date='9/20/1915'/></Mission>",
        b"<Mission><Params Date='9/20/1915'/>"
        b"<!DOCTYPE Mission [<!ENTITY x 'a'>]></Mission>",
    ],
)
def test_invalid_or_unsafe_xml_is_rejected_without_partial_state(
    invalid: bytes,
) -> None:
    parser = WoFFMissionLogParser()
    assert parser.parse_bytes(_mission_xml(), "Mission.log")
    assert not parser.parse_bytes(invalid + b"\nMissionEnded", "Mission.log")
    assert parser.mission is None
    assert parser.pilot is None
    assert parser.briefing == ""
    assert parser.debriefing == ""
    assert parser.squad_members == []
    assert parser.flight_plan == []


@pytest.mark.parametrize(
    "invalid",
    [
        b"<Mission><Params Date='9/20/1915'/>",
        b"<!DOCTYPE Mission [<!ENTITY exploit 'unsafe'>]>"
        b"<Mission><Params Date='9/20/1915'/></Mission>",
    ],
)
def test_rejected_mission_cannot_reach_database_merge(invalid: bytes) -> None:
    """Use the production text processing path, not a parser-only assertion."""
    database = Mock()
    processor = FileProcessor(database, Mock())
    with patch.object(
        processor, "_parser_input",
        return_value=(invalid + b"\nMissionEnded", "Mission.log"),
    ):
        reason = processor._process_text("Mission.log", "mission.log")
    assert reason is ProcessingReason.PARSER_REJECTED
    database.merge_and_write.assert_not_called()


def test_xml_declaration_does_not_reinterpret_normalized_unicode() -> None:
    parser = WoFFMissionLogParser()
    document = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>'
        '<Mission><Params Date="9/20/1915" Time="9:30"/>'
        '<Overview>Équipage décollé</Overview></Mission>'
        '\nMissionEnded'
    ).encode("utf-8")
    assert parser.parse_bytes(document, "Mission.log")
    assert parser.briefing == "Équipage décollé"
    assert parser.debriefing == "Mission Ended Successfully"
