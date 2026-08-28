"""Field-aware integer parsing for WoFF source files."""

from dataclasses import dataclass
import re


class InvalidIntegerError(ValueError):
    """Raised when a present source value violates its integer policy."""


@dataclass(frozen=True)
class IntegerPolicy:
    """Describe the accepted integer syntax for one source field."""

    allow_sign: bool = False
    minimum: int | None = None
    maximum: int | None = None
    sentinels: frozenset[int] = frozenset()
    missing_tokens: frozenset[str] = frozenset()


SQLITE_INTEGER_MIN = -(1 << 63)
SQLITE_INTEGER_MAX = (1 << 63) - 1
SIGNED_SQLITE_INTEGER = IntegerPolicy(
    allow_sign=True,
    minimum=SQLITE_INTEGER_MIN,
    maximum=SQLITE_INTEGER_MAX,
)
UNSIGNED_SQLITE_INTEGER = IntegerPolicy(
    minimum=0,
    maximum=SQLITE_INTEGER_MAX,
)


def parse_integer(raw: str | None, *, policy: IntegerPolicy) -> int | None:
    """Parse one source integer according to its field policy."""

    value = (raw or "").strip()
    if not value or value.casefold() in policy.missing_tokens:
        return None
    pattern = r"[+-]?[0-9]+" if policy.allow_sign else r"[0-9]+"
    if re.fullmatch(pattern, value) is None:
        raise InvalidIntegerError("invalid integer syntax")
    parsed = int(value)
    below_minimum = policy.minimum is not None and parsed < policy.minimum
    above_maximum = policy.maximum is not None and parsed > policy.maximum
    if parsed not in policy.sentinels and (below_minimum or above_maximum):
        raise InvalidIntegerError("integer outside permitted range")
    return parsed
