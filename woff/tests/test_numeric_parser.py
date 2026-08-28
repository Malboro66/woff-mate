import pytest

from ..parsers.numeric import IntegerPolicy, InvalidIntegerError, parse_integer


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


def test_declared_sentinel_is_accepted_outside_normal_bounds() -> None:
    policy = IntegerPolicy(
        allow_sign=True,
        minimum=0,
        maximum=100,
        sentinels=frozenset({-1}),
    )

    assert parse_integer("-1", policy=policy) == -1
