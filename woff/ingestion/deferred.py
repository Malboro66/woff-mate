"""Bounded policy and key types for temporary ingestion dependencies."""

from __future__ import annotations

import math
from dataclasses import dataclass


DependencyKey = tuple[str, int]


@dataclass(frozen=True)
class DependencyRetryPolicy:
    """Bound retained identity dependencies by attempts, age, and bytes."""

    max_attempts: int = 4
    max_age_seconds: float = 300.0
    max_retained_bytes: int = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        for name in ("max_attempts", "max_retained_bytes"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer")
        if (
            isinstance(self.max_age_seconds, bool)
            or not isinstance(self.max_age_seconds, (int, float))
            or not math.isfinite(self.max_age_seconds)
            or self.max_age_seconds <= 0
        ):
            raise ValueError(
                "max_age_seconds must be a finite positive number"
            )
