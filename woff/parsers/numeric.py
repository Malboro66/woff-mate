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

    sign = value[0] if value[0] in "+-" else ""
    digits = value[1:] if sign else value
    magnitude = digits.lstrip("0") or "0"
    is_negative = sign == "-" and magnitude != "0"

    def compare_to_bound(bound: int) -> int:
        """Compare the normalized source value to a bounded Python integer."""

        bound_is_negative = bound < 0
        if is_negative != bound_is_negative:
            return -1 if is_negative else 1

        bound_magnitude = str(abs(bound))
        if len(magnitude) != len(bound_magnitude):
            magnitude_comparison = -1 if len(magnitude) < len(bound_magnitude) else 1
        elif magnitude == bound_magnitude:
            magnitude_comparison = 0
        else:
            magnitude_comparison = -1 if magnitude < bound_magnitude else 1
        return -magnitude_comparison if is_negative else magnitude_comparison

    below_minimum = (
        policy.minimum is not None and compare_to_bound(policy.minimum) < 0
    )
    above_maximum = (
        policy.maximum is not None and compare_to_bound(policy.maximum) > 0
    )
    if below_minimum or above_maximum:
        raise InvalidIntegerError("integer outside permitted range")

    normalized = f"-{magnitude}" if is_negative else magnitude
    try:
        return int(normalized)
    except ValueError as exc:
        # Python 3.11+ can reject an unbounded, extremely long decimal string.
        raise InvalidIntegerError("integer outside permitted range") from exc
