"""Typed processing outcomes and bounded SQLite persistence retry policy."""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..identity import PilotIdentityEvidence
from .snapshot import FileGeneration, StableFileSnapshot


class ProcessingStatus(str, Enum):
    """Observable terminal or retryable states for one verified generation."""

    SUCCESS = "success"
    UNCHANGED = "unchanged"
    PERMANENT_REJECTION = "permanent-rejection"
    TRANSIENT_FAILURE = "transient-failure"


class ProcessingReason(str, Enum):
    """Sanitized reasons that never carry paths, SQL, or campaign content."""

    SUCCESS = "success"
    UNCHANGED = "unchanged"
    UNSUPPORTED_SOURCE = "unsupported-source"
    SNAPSHOT_REJECTED = "snapshot-rejected"
    IDENTITY_REJECTED = "identity-rejected"
    PARSER_REJECTED = "parser-rejected"
    PERSISTENCE_REJECTED = "persistence-rejected"
    SQLITE_BUSY = "sqlite-busy"
    SQLITE_LOCKED = "sqlite-locked"
    SQLITE_PROTOCOL = "sqlite-protocol"
    SQLITE_IO_BLOCKED = "sqlite-io-blocked"
    SQLITE_PERMANENT = "sqlite-permanent"
    UNEXPECTED_ERROR = "unexpected-error"


_TRANSIENT_REASONS = frozenset(
    {
        ProcessingReason.SQLITE_BUSY,
        ProcessingReason.SQLITE_LOCKED,
        ProcessingReason.SQLITE_PROTOCOL,
        ProcessingReason.SQLITE_IO_BLOCKED,
    }
)


@dataclass(frozen=True)
class VerifiedProcessingInput:
    """Immutable bytes plus any verified identity needed to replay them safely."""

    snapshot: StableFileSnapshot
    dependent_identity: Optional[PilotIdentityEvidence] = None


@dataclass(frozen=True)
class ProcessingOutcome:
    """One typed result returned for every admitted processing attempt."""

    status: ProcessingStatus
    reason: ProcessingReason
    generation: Optional[FileGeneration] = None
    retry_input: Optional[VerifiedProcessingInput] = None

    def __post_init__(self) -> None:
        acknowledged = self.status in {
            ProcessingStatus.SUCCESS,
            ProcessingStatus.UNCHANGED,
        }
        if acknowledged:
            expected_reason = (
                ProcessingReason.SUCCESS
                if self.status is ProcessingStatus.SUCCESS
                else ProcessingReason.UNCHANGED
            )
            if (
                self.reason is not expected_reason
                or self.generation is None
                or self.retry_input is not None
            ):
                raise ValueError("acknowledged outcomes require only a generation")
            return
        if self.status is ProcessingStatus.TRANSIENT_FAILURE:
            if (
                self.retry_input is None
                or self.generation != self.retry_input.snapshot.generation
                or self.reason not in _TRANSIENT_REASONS
            ):
                raise ValueError(
                    "transient outcomes require matching verified retry input"
                )
            return
        if (
            self.reason in _TRANSIENT_REASONS
            or self.reason
            in {ProcessingReason.SUCCESS, ProcessingReason.UNCHANGED}
            or self.generation is not None
            or self.retry_input is not None
        ):
            raise ValueError("permanent rejection cannot acknowledge or retain input")

    @classmethod
    def success(cls, generation: FileGeneration) -> "ProcessingOutcome":
        return cls(ProcessingStatus.SUCCESS, ProcessingReason.SUCCESS, generation)

    @classmethod
    def unchanged(cls, generation: FileGeneration) -> "ProcessingOutcome":
        return cls(ProcessingStatus.UNCHANGED, ProcessingReason.UNCHANGED, generation)

    @classmethod
    def permanent(
        cls, reason: ProcessingReason
    ) -> "ProcessingOutcome":
        return cls(ProcessingStatus.PERMANENT_REJECTION, reason)

    @classmethod
    def transient(
        cls,
        retry_input: VerifiedProcessingInput,
        reason: ProcessingReason,
    ) -> "ProcessingOutcome":
        return cls(
            ProcessingStatus.TRANSIENT_FAILURE,
            reason,
            retry_input.snapshot.generation,
            retry_input,
        )

    @property
    def acknowledged_generation(self) -> Optional[FileGeneration]:
        if self.status in {
            ProcessingStatus.SUCCESS,
            ProcessingStatus.UNCHANGED,
        }:
            return self.generation
        return None


@dataclass(frozen=True)
class PersistenceRetryPolicy:
    """Fixed bounded retry: four attempts and at most 0.7 s of backoff."""

    max_attempts: int = 4
    initial_delay: float = 0.1
    max_delay: float = 0.4

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or self.max_attempts <= 0
        ):
            raise ValueError("max_attempts must be a positive integer")
        for name in ("initial_delay", "max_delay"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{name} must be a finite nonnegative number")
        if self.max_delay < self.initial_delay:
            raise ValueError("max_delay must be at least initial_delay")

    def delay_after_failure(self, failures: int) -> float:
        """Return the delay before the next attempt after ``failures`` failures."""
        if failures <= 0:
            raise ValueError("failures must be positive")
        return min(self.initial_delay * (2 ** (failures - 1)), self.max_delay)


def classify_transient_sqlite_error(
    error: BaseException,
) -> Optional[ProcessingReason]:
    """Classify only SQLite errors with a verified retryable code or message.

    Python 3.11+ exposes ``sqlite_errorcode``. Python 3.10 falls back to the
    exact SQLite messages below rather than broad substring matching.
    """

    current: Optional[BaseException] = error
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, sqlite3.Error):
            code = getattr(current, "sqlite_errorcode", None)
            if type(code) is int:
                if code == 2826:  # SQLITE_IOERR_BLOCKED
                    return ProcessingReason.SQLITE_IO_BLOCKED
                primary_code = code & 0xFF
                if primary_code == 5:  # SQLITE_BUSY and extended BUSY codes
                    return ProcessingReason.SQLITE_BUSY
                if primary_code == 6:  # SQLITE_LOCKED and extended LOCKED codes
                    return ProcessingReason.SQLITE_LOCKED
                if primary_code == 15:  # SQLITE_PROTOCOL
                    return ProcessingReason.SQLITE_PROTOCOL

            if code is None and isinstance(current, sqlite3.OperationalError):
                message = " ".join(str(current).strip().casefold().split())
                fallback = {
                    "database is busy": ProcessingReason.SQLITE_BUSY,
                    "database is locked": ProcessingReason.SQLITE_BUSY,
                    "database table is locked": ProcessingReason.SQLITE_LOCKED,
                    "database schema is locked": ProcessingReason.SQLITE_LOCKED,
                    "locking protocol": ProcessingReason.SQLITE_PROTOCOL,
                }
                for prefix, reason in fallback.items():
                    if message == prefix or message.startswith(f"{prefix}:"):
                        return reason

        cause = current.__cause__
        current = cause if cause is not None else current.__context__
    return None
