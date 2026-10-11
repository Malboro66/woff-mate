"""Entirely synthetic regressions for Issue #183's CP1252 final-token delimiter.

No real WoFF data, paths, names, or private Dossier bytes belong here.
"""
import pytest

from ..parsers.dossier_parser import DossierValidationStatus, WoFFDossierParser


_FILENAME = "Pilot1Dossier.txt"
_THIRTY_THREE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567"
assert len(_THIRTY_THREE) == 33


def _fixture_key() -> str:
    """Independent encoding-key derivation matching the historical fixture rule."""
    alphabet = "78CrztPRVzYQpYu90MnyW"
    sum_val = sum(ord(ch) for ch in _FILENAME.removesuffix(".txt")) % 128
    start = sum_val % 10 or 9
    length = sum_val % 12 or 4
    pre = "".join(alphabet[i - 1] for i in range(start, start + length))
    post = "".join(alphabet[i - 1] for i in range(length, length + start))
    return pre + chr(sum_val) + alphabet + post


def _encode_lines(
    plain_lines: list[str],
    ending: bytes,
    *,
    nbsp_terminal_lines: frozenset[int] = frozenset(),
    mixed: bool = False,
) -> bytes:
    key = _fixture_key()
    result = bytearray()
    assert ending in (b"\n", b"\r\n")

    for physical_index, plain in enumerate(plain_lines):
        for index, char in enumerate(plain):
            value = ord(char) ^ ord(key[index % len(key)])
            assert value <= 0xFF
            result.extend(f"{value:02X}".encode("ascii"))
            # All of these are valid CP1252 counter/separator bytes.
            separator = (
                (0x80, 0xA0, 0xC0, 0xFF)[index % 4]
                if mixed
                else 0xC0 + (index % 48)
            )
            if (
                physical_index in nbsp_terminal_lines
                and index == len(plain) - 1
            ):
                separator = 0xA0
            result.append(separator)
        result.extend(ending)
        key = key[::-1]
    return bytes(result)


@pytest.mark.parametrize("ending", [b"\n", b"\r\n"], ids=["LF", "CRLF"])
@pytest.mark.parametrize("position", [0, 1, 2], ids=["first", "middle", "last"])
def test_terminal_nbsp_preserves_exact_33_characters(
    ending: bytes, position: int
) -> None:
    plain_lines = ["Fictional start", "Fictional middle", "Fictional end"]
    plain_lines[position] = _THIRTY_THREE
    raw = _encode_lines(
        plain_lines, ending, nbsp_terminal_lines=frozenset({position})
    )

    parser = WoFFDossierParser()
    decoded = parser._decode_lines(raw.splitlines(keepends=True), _fixture_key())

    assert decoded == plain_lines
    assert [record.encode("utf-8") for record in decoded] == [
        record.encode("utf-8") for record in plain_lines
    ]
    assert len(decoded[position]) == 33


@pytest.mark.parametrize("ending", [b"\n", b"\r\n"], ids=["LF", "CRLF"])
def test_mixed_counters_blank_line_and_xor_parity(ending: bytes) -> None:
    plain_lines = ["Opening", "", _THIRTY_THREE, "Final record"]
    raw = _encode_lines(
        plain_lines, ending, nbsp_terminal_lines=frozenset({2}), mixed=True
    )

    parser = WoFFDossierParser()
    assert parser._decode_lines(
        raw.splitlines(keepends=True), _fixture_key()
    ) == plain_lines


def test_other_terminal_counters_remain_valid() -> None:
    plain_lines = ["Opening", "Middle", "Ending"]
    raw = _encode_lines(plain_lines, b"\r\n", mixed=True)
    assert WoFFDossierParser()._decode_lines(
        raw.splitlines(keepends=True), _fixture_key()
    ) == plain_lines


def test_terminal_nbsp_finishes_one_digit_hex_token() -> None:
    # Independent known fixture key begins with R: ord("R") ^ 0x1 == ord("S").
    assert _fixture_key()[0] == "R"
    assert WoFFDossierParser()._decode_lines(
        [b"1\xa0\r\n"], _fixture_key()
    ) == ["S"]


def _member_record(rank: str, given: str, surname: str, size: int) -> str:
    parts = [""] * size
    parts[0:6] = [rank, given, surname, "3", "5", "In Service"]
    parts[11:13] = ["2", "30"]
    parts[16:19] = ["2", "3", "1897"]
    parts[19] = "Entirely fictional biography."
    return ";".join(parts)


@pytest.mark.parametrize("ending", [b"\n", b"\r\n"], ids=["LF", "CRLF"])
def test_verified_synthetic_roster_occupancy_and_width(ending: bytes) -> None:
    # Occupancy is five: a terminal 0xA0 may not shorten the N/A at 78
    # to N/, nor remove the final semicolon of the 32-field observer at 125.
    records = ["Null"] * 161
    for slot in (*range(63, 79), *range(113, 129)):
        records[slot] = "N/A"
    records[0] = "160"
    records[1] = "Britain"
    records[3] = "Flight Lieutenant"
    records[4:6] = ["Fictional", "Flyer"]
    records[81] = "5"
    for offset, given_name in enumerate(("Alfred", "Bert", "Clive", "Derek", "Ernest")):
        records[63 + offset] = _member_record(
            "Flight Lieutenant", given_name, "Example", 36
        )
    records[78] = "N/A"
    records[125] = _member_record("Captain", "Observer", "Example", 32)
    assert records[125].endswith(";")
    assert len(records[125].split(";")) == 32

    raw = _encode_lines(
        records, ending, nbsp_terminal_lines=frozenset({78, 125})
    )
    parser = WoFFDossierParser()
    assert parser.parse_bytes(raw, _FILENAME, require_verified_layout=True)
    assert parser.validation_status == DossierValidationStatus.SUPPORTED_FULL
    assert parser.raw_strings == records
    assert len(parser.wingmen) == 6
    assert parser.raw_strings[78] == "N/A"
    assert len(parser.raw_strings[125].split(";")) == 32
    assert not parser.roster_complete


@pytest.mark.parametrize(
    "raw",
    [
        b"1G\xa0\n",  # Malformed hexadecimal token
        b"41\r\n",  # Incomplete token: no counter/separator
        b"\x00\n",  # Unsupported control input
    ],
)
def test_malformed_or_unterminated_sources_fail_closed(raw: bytes) -> None:
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(raw, _FILENAME, require_verified_layout=True)
    assert parser.validation_status == DossierValidationStatus.DECRYPTION_FAILED
    assert parser.pilot is None
    assert not parser.wingmen


@pytest.mark.parametrize(
    "bad_line",
    [
        b"1G\xa0\n",  # Invalid hex token terminated by legitimate 0xA0.
        b"41\r\n",  # Valid hex digits but missing counter/separator.
        b"\x00\n",  # Unsupported control byte, not encoded hex.
    ],
    ids=["invalid-hex", "unterminated-hex", "control-byte"],
)
@pytest.mark.parametrize("verified", [False, True], ids=["diagnostic", "runtime"])
def test_malformed_encoded_line_rejects_otherwise_valid_dossier(
    bad_line: bytes, verified: bool
) -> None:
    # The malformed record is in a nonessential context slot; every other
    # position constitutes a valid fictional 161/160 Dossier. Merely testing
    # a one-line file would pass via the global nonempty-text guard.
    records = ["Null"] * 161
    for slot in (*range(63, 79), *range(113, 129)):
        records[slot] = "N/A"
    records[0] = "160"
    records[1] = "Britain"
    records[3] = "Flight Lieutenant"
    records[4:6] = ["Fictional", "Flyer"]
    records[81] = "0"

    original = _encode_lines(records, b"\r\n")
    control = WoFFDossierParser()
    assert control.parse_bytes(
        original, _FILENAME, require_verified_layout=True
    )
    assert control.validation_status == DossierValidationStatus.SUPPORTED_FULL

    physical = original.splitlines(keepends=True)
    assert len(physical) == 161
    physical[2] = bad_line
    parser = WoFFDossierParser()
    assert not parser.parse_bytes(
        b"".join(physical), _FILENAME, require_verified_layout=verified
    )
    assert parser.validation_status == DossierValidationStatus.DECRYPTION_FAILED
    assert parser.raw_strings == []
    assert parser.pilot is None
    assert parser.wingmen == []
    assert parser.decorations == []
