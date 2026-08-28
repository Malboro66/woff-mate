import pytest

from ..parsers.numeric import (
    SIGNED_SQLITE_INTEGER,
    SQLITE_INTEGER_MAX,
    SQLITE_INTEGER_MIN,
    UNSIGNED_SQLITE_INTEGER,
    IntegerPolicy,
    InvalidIntegerError,
    parse_integer,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" -1 ", -1),
        (" +5 ", 5),
    ],
)
def test_signed_policy_preserves_permitted_signs(raw: str, expected: int) -> None:
    policy = IntegerPolicy(allow_sign=True)

    assert parse_integer(raw, policy=policy) == expected


def test_explicit_zero_remains_distinct_from_missing_input() -> None:
    policy = IntegerPolicy()

    assert parse_integer("0", policy=policy) == 0
    assert parse_integer("   ", policy=policy) is None
    assert parse_integer(None, policy=policy) is None


@pytest.mark.parametrize("raw", ["-1", "+5", "not-a-number", "１２"])
def test_unsigned_policy_rejects_signed_or_non_ascii_syntax(raw: str) -> None:
    with pytest.raises(InvalidIntegerError, match="invalid integer syntax"):
        parse_integer(raw, policy=IntegerPolicy())


@pytest.mark.parametrize("raw", ["--1", "+ 5", "-", "１２"])
def test_signed_policy_rejects_malformed_or_non_ascii_syntax(raw: str) -> None:
    with pytest.raises(InvalidIntegerError, match="invalid integer syntax"):
        parse_integer(raw, policy=IntegerPolicy(allow_sign=True))


@pytest.mark.parametrize("raw", ["-1", "101"])
def test_policy_rejects_values_outside_declared_bounds(raw: str) -> None:
    policy = IntegerPolicy(allow_sign=True, minimum=0, maximum=100)

    with pytest.raises(InvalidIntegerError, match="outside permitted range"):
        parse_integer(raw, policy=policy)


@pytest.mark.parametrize(
    ("raw", "policy", "expected"),
    [
        (str(SQLITE_INTEGER_MIN), SIGNED_SQLITE_INTEGER, SQLITE_INTEGER_MIN),
        (str(SQLITE_INTEGER_MAX), SIGNED_SQLITE_INTEGER, SQLITE_INTEGER_MAX),
        (str(SQLITE_INTEGER_MAX), UNSIGNED_SQLITE_INTEGER, SQLITE_INTEGER_MAX),
    ],
)
def test_sqlite_integer_boundaries_are_inclusive(
    raw: str, policy: IntegerPolicy, expected: int
) -> None:
    assert parse_integer(raw, policy=policy) == expected


@pytest.mark.parametrize(
    ("raw", "policy"),
    [
        (str(SQLITE_INTEGER_MIN - 1), SIGNED_SQLITE_INTEGER),
        (str(SQLITE_INTEGER_MAX + 1), SIGNED_SQLITE_INTEGER),
        (str(SQLITE_INTEGER_MAX + 1), UNSIGNED_SQLITE_INTEGER),
    ],
)
def test_sqlite_integer_values_adjacent_to_boundaries_are_rejected(
    raw: str, policy: IntegerPolicy
) -> None:
    with pytest.raises(InvalidIntegerError, match="outside permitted range"):
        parse_integer(raw, policy=policy)


def test_overlong_sqlite_integer_uses_the_controlled_range_error() -> None:
    with pytest.raises(InvalidIntegerError, match="outside permitted range"):
        parse_integer("9" * 5_000, policy=UNSIGNED_SQLITE_INTEGER)
