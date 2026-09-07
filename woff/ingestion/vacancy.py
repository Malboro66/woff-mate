"""Conservative, complete Dossier inventories and bounded absence confirmation."""

from __future__ import annotations

import os
import stat
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from ..identity import is_dossier_source, pilot_slot
from .snapshot import StableSnapshotReader


@dataclass(frozen=True)
class DossierInventory:
    root_identity: tuple[int, int]
    slots: frozenset[int]


def _directory_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_mtime_ns, value.st_ctime_ns


def scan_dossiers(root: str) -> DossierInventory:
    """Scan the entire root, failing closed on inaccessible or changing trees.

    An entry named like a Dossier counts as present even when unreadable or
    empty. Symlinks are not followed: an unverified subtree cannot prove
    absence. Directory metadata is checked around enumeration, including
    the root, so a partial/changing scan is never an authoritative empty set.
    """
    slots: set[int] = set()

    def visit(directory: str) -> tuple[int, int]:
        before = os.stat(directory, follow_symlinks=False)
        if (
            not stat.S_ISDIR(before.st_mode)
            or getattr(before, "st_file_attributes", 0) & 0x400
        ):
            # Windows junctions/reparse directories are not ordinary subtrees.
            raise OSError("unavailable-dossier-root")
        with os.scandir(directory) as entries:
            for entry in entries:
                if is_dossier_source(entry.name):
                    slot = pilot_slot(entry.name)
                    if slot is not None:
                        slots.add(slot)
                if entry.is_symlink():
                    raise OSError("unverified-dossier-subtree")
                if entry.is_dir(follow_symlinks=False):
                    visit(entry.path)
        after = os.stat(directory, follow_symlinks=False)
        if _directory_identity(before) != _directory_identity(after):
            raise OSError("changed-dossier-inventory")
        return before.st_dev, before.st_ino

    identity = visit(root)
    return DossierInventory(identity, frozenset(slots))


class VacancyState(str, Enum):
    ABSENT = "absent"
    PRESENT = "present"
    DEFERRED = "deferred"


@dataclass(frozen=True)
class VacancyObservation:
    state: VacancyState
    root_identity: Optional[tuple[int, int]] = None


class DossierVacancyGuard:
    """Require absence at every observation throughout the stability window."""

    def __init__(
        self,
        timeout: float,
        interval: float,
        *,
        scan: Optional[Callable[[str], DossierInventory]] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._scan = scan or scan_dossiers
        self._sleep = sleep
        self.retry_delays = StableSnapshotReader(timeout, interval).retry_delays

    def confirm(self, root: str, slot: int) -> VacancyObservation:
        identity: Optional[tuple[int, int]] = None
        for delay in (0.0, *self.retry_delays):
            if delay:
                self._sleep(delay)
            try:
                inventory = self._scan(root)
            except OSError:
                return VacancyObservation(VacancyState.DEFERRED)
            if slot in inventory.slots:
                return VacancyObservation(VacancyState.PRESENT)
            if identity is not None and identity != inventory.root_identity:
                return VacancyObservation(VacancyState.DEFERRED)
            identity = inventory.root_identity
        return VacancyObservation(VacancyState.ABSENT, identity)
