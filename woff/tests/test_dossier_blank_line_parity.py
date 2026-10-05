from pathlib import Path

from ..parsers.dossier_parser import WoFFDossierParser


_DOSSIER_FIXTURES = Path(__file__).parent / "fixtures" / "dossier"
_FILENAME = "Pilot1Dossier.txt"
_WINGMAN_RECORD = (
    "Lieutenant;Alex;Doe;3;5;In Service;0;0;0;0;0;6;1550;1500;9;2;8;8;"
    "1896;Reliable pilot.;75"
)


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


def _encode_physical_lines(physical_lines: list[str], filename: str) -> bytes:
    current_key = _create_test_key(filename)
    raw_data = bytearray()

    for line in physical_lines:
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


def test_decode_advances_xor_parity_across_blank_physical_line() -> None:
    physical_lines = (
        _DOSSIER_FIXTURES / "blank_line_parity_sanitized.txt"
    ).read_text(encoding="utf-8").splitlines()
    assert physical_lines[2] == ""

    parser = WoFFDossierParser()
    encoded = _encode_physical_lines(physical_lines, _FILENAME)
    decoded = parser._decode_lines(
        encoded.splitlines(keepends=True),
        _create_test_key(_FILENAME),
    )

    assert decoded == [line for line in physical_lines if line]
    assert decoded[-1] == _WINGMAN_RECORD


def test_blank_physical_line_does_not_create_record_or_corrupt_later_roster() -> None:
    semantic_lines = ["Null"] * 105
    semantic_lines[1] = "France"
    semantic_lines[3] = "Capitaine"
    semantic_lines[4] = "Sample"
    semantic_lines[5] = "Pilot"
    semantic_lines[104] = _WINGMAN_RECORD

    physical_lines = semantic_lines[:100] + [""] + semantic_lines[100:]
    encoded = _encode_physical_lines(physical_lines, _FILENAME)

    parser = WoFFDossierParser()
    assert parser.parse_bytes(encoded, _FILENAME)
    assert len(parser.raw_strings) == len(semantic_lines)
    assert parser.raw_strings[104] == _WINGMAN_RECORD
    assert len(parser.wingmen) == 1
    assert parser.wingmen[0].fName == "Alex"
    assert parser.wingmen[0].sName == "Doe"
