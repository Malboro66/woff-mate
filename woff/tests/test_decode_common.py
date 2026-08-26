"""Contracts and allocation regression tests for the shared WoFF decoder."""

import tracemalloc
from collections.abc import Callable

import pytest

from woff import decode_dossier, decode_squad, squadron_cataloger
from woff.decode.common import unscramble


def test_unscramble_decodes_every_byte_value_from_valid_hex_tokens() -> None:
    encoded = b"|".join(f"{value:02X}".encode("ascii") for value in range(256)) + b"|"

    assert unscramble(encoded) == bytes(range(256))


@pytest.mark.parametrize(
    ("encoded", "expected"),
    [
        (b"", b""),
        (b"4\r\n1|42|", b"AB"),
        (b"41||42|", b"A\x00B"),
        (b"|", b"\x00"),
        (b"4G1|", b"\x04\x01"),
    ],
)
def test_unscramble_preserves_line_break_and_delimiter_policy(
    encoded: bytes, expected: bytes
) -> None:
    assert unscramble(encoded) == expected


@pytest.mark.parametrize("encoded", [b"100|", b"FFFF"])
def test_unscramble_rejects_tokens_outside_one_byte(encoded: bytes) -> None:
    with pytest.raises(ValueError):
        unscramble(encoded)


@pytest.mark.parametrize(
    "caller",
    [
        decode_dossier.unscramble,
        decode_squad.unscramble,
        squadron_cataloger.unscramble,
    ],
)
def test_existing_decoder_callers_retain_shared_output(
    caller: Callable[[bytes], bytes],
) -> None:
    assert caller(b"41|42|") == b"AB"


def test_large_token_stream_has_bounded_peak_memory() -> None:
    """Measure allocations after creating input, without a wall-clock assertion."""
    encoded = b"41|" * 250_000

    tracemalloc.start()
    try:
        decoded = unscramble(encoded)
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert decoded == b"A" * 250_000
    assert peak_bytes < len(encoded)
