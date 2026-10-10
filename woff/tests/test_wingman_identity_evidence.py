# Legacy synthetic decoding here is nonauthoritative; runtime admission is tested separately.
from ..parsers.dossier_parser import WoFFDossierParser


_FILENAME = "Pilot1Dossier.txt"


def _create_test_key(filename: str) -> str:
    plainkey = "78CrztPRVzYQpYu90MnyW"
    p_name = filename.replace(".txt", "")
    sum_val = sum(ord(char) for char in p_name) % 128

    pos = sum_val % 10
    if pos == 0:
        pos = 9

    length = sum_val % 12
    if length == 0:
        length = 4

    prekey = "".join(
        plainkey[index - 1]
        for index in range(pos, pos + length)
    )
    postkey = "".join(
        plainkey[index - 1]
        for index in range(length, length + pos)
    )
    return prekey + chr(sum_val) + plainkey + postkey


def _encode_lines(lines: list[str], filename: str = _FILENAME) -> bytes:
    current_key = _create_test_key(filename)
    raw_data = bytearray()

    for line in lines:
        key_index = 0
        counter = 0x80
        for character in line:
            xor_value = ord(character) ^ ord(current_key[key_index])
            raw_data.extend(f"{xor_value:02X}".encode("ascii"))
            raw_data.append(counter)
            counter = 0x80 + ((counter - 0x80 + 1) % 128)
            key_index = (key_index + 1) % len(current_key)
        raw_data.extend(b"\r\n")
        current_key = current_key[::-1]

    return bytes(raw_data)


def _roster_record(
    *,
    rank: str = "Lieutenant",
    status: str = "In Service",
    skill: int = 3,
    morale: int = 5,
    flight_minutes: int = 1550,
) -> str:
    return (
        f"{rank};Alex;Doe;{skill};{morale};{status};0;0;0;0;0;6;"
        f"{flight_minutes};1500;9;2;8;8;1896;Reliable pilot.;75;21;651;1;"
        "19/7/1913;Arras;2;0;Null;Null;Null;Null;Null;Null;Null"
    )


def _parse_single_wingman(record: str):
    lines = ["Null"] * 105
    lines[1] = "France"
    lines[3] = "Capitaine"
    lines[4] = "Sample"
    lines[5] = "Pilot"
    lines[104] = record

    parser = WoFFDossierParser()
    assert parser.parse_bytes(_encode_lines(lines), _FILENAME)
    assert len(parser.wingmen) == 1
    return parser.wingmen[0]


def test_supported_roster_record_preserves_reconciliation_evidence() -> None:
    wingman = _parse_single_wingman(_roster_record())

    assert wingman.birthDate == "1896-08-08"
    assert wingman.evidenceDate == "1913-07-19"
    assert wingman.evidenceLocation == "Arras"


def test_mutable_roster_state_does_not_change_reconciliation_evidence() -> None:
    before = _parse_single_wingman(
        _roster_record(
            status="On Leave",
            skill=1,
            morale=2,
            flight_minutes=1500,
        )
    )
    after = _parse_single_wingman(
        _roster_record(
            status="In Service",
            skill=5,
            morale=4,
            flight_minutes=8420,
        )
    )

    before_evidence = (
        before.fName,
        before.sName,
        before.birthDate,
        before.evidenceDate,
        before.evidenceLocation,
    )
    after_evidence = (
        after.fName,
        after.sName,
        after.birthDate,
        after.evidenceDate,
        after.evidenceLocation,
    )
    assert before_evidence == after_evidence


def test_observed_french_rank_spellings_remain_parseable() -> None:
    for rank in ("Adjutant", "Sous Lieutenant"):
        wingman = _parse_single_wingman(_roster_record(rank=rank))
        assert wingman.rank == rank
