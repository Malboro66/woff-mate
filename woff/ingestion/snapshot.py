"""Acquire immutable, generation-verified input for the ingestion pipeline."""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Protocol


class StatMetadata(Protocol):
    @property
    def st_dev(self) -> int: ...
    @property
    def st_ino(self) -> int: ...
    @property
    def st_size(self) -> int: ...
    @property
    def st_mtime_ns(self) -> int: ...
    @property
    def st_ctime_ns(self) -> int: ...


class SnapshotFailureKind(str, Enum):
    TIMEOUT = "timeout"
    INACCESSIBLE = "inaccessible"
    CHANGED = "changed-generation"


class SnapshotFailure(RuntimeError):
    """A sanitized final acquisition result; source paths/data are omitted."""

    def __init__(self, kind: SnapshotFailureKind, attempts: int) -> None:
        self.kind = kind
        self.attempts = attempts
        super().__init__(f"snapshot acquisition {kind.value} after {attempts} attempts")


@dataclass(frozen=True)
class FileGeneration:
    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int
    digest: str


@dataclass(frozen=True)
class StableFileSnapshot:
    data: bytes
    path: str
    name: str
    generation: FileGeneration
    attempts: int


class _GenerationChanged(OSError):
    pass


class StableSnapshotReader:
    """Require two identical full observations within a fixed attempt budget."""

    def __init__(
        self,
        timeout: float = 3.0,
        interval: float = 0.15,
        *,
        stat: Callable[[str], StatMetadata] = os.stat,
        read: Optional[Callable[[str], bytes]] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.timeout = timeout
        self.interval = interval
        self._stat = stat
        self._read = read or self._read_verified
        self._sleep = sleep

    @property
    def max_attempts(self) -> int:
        return len(self.retry_delays) + 1

    @property
    def retry_delays(self) -> tuple[float, ...]:
        """Exponential delays capped so their sum never exceeds timeout."""
        remaining = self.timeout
        delay = self.interval
        delays = []
        while remaining > 0:
            bounded = min(delay, remaining)
            delays.append(bounded)
            remaining -= bounded
            delay *= 2
        return tuple(delays)

    @staticmethod
    def _identity(value: StatMetadata) -> tuple[int, int, int, int, int]:
        return (
            int(value.st_dev), int(value.st_ino), int(value.st_size),
            int(value.st_mtime_ns), int(value.st_ctime_ns),
        )

    def _read_verified(self, path: str) -> bytes:
        with open(path, "rb") as source:
            before = os.fstat(source.fileno())
            data = source.read()
            after = os.fstat(source.fileno())
        current = self._stat(path)
        if not (
            self._identity(before) == self._identity(after) == self._identity(current)
            and len(data) == before.st_size
        ):
            raise _GenerationChanged()
        return data

    def acquire(self, path: str) -> StableFileSnapshot:
        previous: Optional[tuple[FileGeneration, bytes]] = None
        final_kind = SnapshotFailureKind.TIMEOUT
        delays = self.retry_delays
        attempts = len(delays) + 1
        for attempt in range(1, attempts + 1):
            try:
                metadata = self._stat(path)
                data = self._read(path)
                current = self._stat(path)
                if (
                    self._identity(metadata) != self._identity(current)
                    or len(data) != metadata.st_size
                ):
                    raise _GenerationChanged()
                generation = FileGeneration(
                    *self._identity(current), hashlib.sha256(data).hexdigest()
                )
                if not data:
                    previous = None
                    final_kind = SnapshotFailureKind.TIMEOUT
                elif previous == (generation, data):
                    return StableFileSnapshot(
                        data=data,
                        path=path,
                        name=Path(path).name,
                        generation=generation,
                        attempts=attempt,
                    )
                else:
                    previous = (generation, data)
                    final_kind = SnapshotFailureKind.CHANGED
            except _GenerationChanged:
                previous = None
                final_kind = SnapshotFailureKind.CHANGED
            except (FileNotFoundError, PermissionError, OSError):
                previous = None
                final_kind = SnapshotFailureKind.INACCESSIBLE
            if attempt < attempts:
                self._sleep(delays[attempt - 1])
        raise SnapshotFailure(final_kind, attempts)
