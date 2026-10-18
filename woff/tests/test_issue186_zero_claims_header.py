"""Synthetic regression contracts for Issue #186."""
import pytest
from ..parsers.pilot_data_parser import WoFFPilotDataParser

HEADER = (
    "Day;Month;Year;Hour;Minute;MissionRegion;MissionBase;Missiontype;"
    "AircraftName;ClaimQty;EnemyCraftName;Circumstances;AircraftTruncatedName"
)
RECORD = (
    "6;4;1917;10;30;Arras;FictionalBase;OP;SE.5a;1;"
    "FictionalCraft;Forced to land Confirmed;Fictional"
)


def parse(text):
    parser = WoFFPilotDataParser()
    returned = parser.parse_bytes(text, "Pilot1Claims.txt")
    return parser, returned


@pytest.mark.parametrize("text", [
    "0\n" + HEADER + "\n",
    "\n0\n\n" + HEADER + ";\n",
    "0\n " + HEADER.lower() + " ;\n",
])
def test_attested_header_is_valid_empty(text):
    p, returned = parse(text)
    assert returned is False
    assert (p.declared_records, p.observed_records, p.rejected_records) == (0, 0, 0)
    assert p.is_complete and p.valid_empty and p.victories == []


def test_zero_counter_alone_retained():
    p, returned = parse("0\n")
    assert not returned and p.is_complete and p.valid_empty


@pytest.mark.parametrize("text", [
    HEADER + "\n", "1\n" + HEADER + "\n",
    "0\n" + HEADER + "\n" + HEADER + "\n",
    "0\n" + HEADER + "\nmalformed\n",
    "0\n" + HEADER + "\n" + RECORD + "\n",
    "0\n" + RECORD + "\n" + HEADER + "\n",
    "0\n" + HEADER.replace("MissionRegion", "InventedColumn") + "\n",
    "0\n" + HEADER.replace("MissionRegion;", "") + "\n",
    "0\n" + HEADER.replace("MissionRegion;MissionBase;", "MissionBase;MissionRegion;") + "\n",
    "0\n" + HEADER + "\n0\n",
    "0\n" + HEADER + "\n1\n",
])
def test_unknown_or_misplaced_metadata_not_valid_empty(text):
    p, _ = parse(text)
    assert not p.valid_empty
    assert not p.is_complete
    assert p.rejected_records > 0 or p.declared_records != p.observed_records


@pytest.mark.parametrize("value,expected", [
    ("Forced to land Confirmed", True),
    ("Driven Down (Unconfirmed)", False),
    ("Confirmation pending", None),
    ("Destroyed in flames", None),
])
def test_normal_claim_semantics_and_physical_line_key(value, expected):
    record = RECORD.replace("Forced to land Confirmed", value)
    p, returned = parse("1\n" + record + "\n")
    assert returned and p.is_complete and len(p.victories) == 1
    assert p.victories[0].confirmed is expected
    assert p.victories[0].source_record_key is not None
