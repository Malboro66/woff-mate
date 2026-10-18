#!/usr/bin/env python3
r"""
Windows registry discovery for the local WoFF BHaH II installation.

Only explicitly approved, versioned OFFManager Settings keys are probed.
Only the CFS3Path value is read. No enumeration or credential access occurs.
"""

from __future__ import annotations

import logging
import ntpath
import os
from pathlib import Path
from typing import Any, Optional, Protocol, Tuple, cast

log = logging.getLogger("WoFFWatch")

# Keep the historical key public for existing consumers and tests.
WOFF_REG_KEY = r"Software\VB and VBA Program Settings\OFFManager4\Settings"
WOFF_REG_VALUE = "CFS3Path"
ALLOWED_WOFF_REGISTRY_VALUES = frozenset({WOFF_REG_VALUE})

# Fixed allowlist, not a scan of OFFManager* or unrelated software.
# OFFManager5 is a synthetic forward-compatibility candidate: its existence in
# any released WoFF build has NOT been verified. Prefer newer valid paths so a
# stale old installation does not conceal an installed newer version.
WOFF_REG_KEYS = (
    r"Software\VB and VBA Program Settings\OFFManager5\Settings",
    WOFF_REG_KEY,
)


class _WinReg(Protocol):
    """Minimal, injectable read-only registry surface."""

    HKEY_CURRENT_USER: int

    def OpenKey(self, key: int, sub_key: str) -> Any: ...
    def QueryValueEx(self, key: Any, value_name: str) -> Tuple[Any, int]: ...
    def CloseKey(self, key: Any) -> None: ...


def _valid_install_dir(candidate: Any) -> Optional[Tuple[str, bool]]:
    """Return an existing root and whether optional generated watch folders exist."""
    if not isinstance(candidate, str):
        return None
    path = candidate.strip()
    if not path or not os.path.isabs(path):
        return None
    # On Windows reject rooted-but-drive-less and drive-relative paths. POSIX
    # absolute paths remain useful for injected fake-registry Linux tests.
    if os.name == "nt" and not ntpath.splitdrive(path)[0]:
        return None
    try:
        root = Path(path)
        if not root.is_dir():
            return None
        pilots = root / "campaigns" / "CampaignData" / "Pilots"
        logs = root / "Logs"
        parent_logs = root.parent / "Logs"
        ready = pilots.is_dir() and (logs.is_dir() or parent_logs.is_dir())
        return path, ready
    except (OSError, ValueError):
        return None


def get_woff_install_path(registry: Optional[_WinReg] = None) -> Optional[str]:
    """Prefer an existing complete WoFF root; allow one awaiting generated folders.

    Missing/stale/malformed keys are not evidence the game is uninstalled.
    "registry" can be replaced with a fake for deterministic tests.
    """
    if registry is None:
        try:
            import winreg
        except ImportError:
            log.warning(
                "WoFF registry auto-discovery unavailable on this platform; "
                "configure the WoFF watch paths manually."
            )
            return None
        registry = cast(_WinReg, winreg)

    first_existing_root: Optional[str] = None
    for sub_key in WOFF_REG_KEYS:
        try:
            key = registry.OpenKey(registry.HKEY_CURRENT_USER, sub_key)
        except (OSError, ValueError, TypeError):
            continue

        try:
            value, value_type = registry.QueryValueEx(key, WOFF_REG_VALUE)
        except (OSError, ValueError, TypeError):
            continue
        finally:
            # Always release opened keys, including missing CFS3Path values.
            try:
                registry.CloseKey(key)
            except OSError:
                log.debug("Unable to close WoFF registry handle for %s", sub_key)

        # Windows REG_SZ (1) and REG_EXPAND_SZ (2) only, never binary/numeric.
        if value_type not in (1, 2):
            continue
        if value_type == 2 and isinstance(value, str):
            value = os.path.expandvars(value)

        valid = _valid_install_dir(value)
        if valid is not None:
            path, folders_ready = valid
            if folders_ready:
                log.info("WoFF registry auto-discovery selected %s", sub_key)
                return path
            if first_existing_root is None:
                first_existing_root = path

    # The configuration loader intentionally accepts roots before a career
    # creates the Pilots/Logs folders, and then reports missing folders.
    if first_existing_root is not None:
        log.info("WoFF registry auto-discovery found an existing installation directory; "
                 "some generated data folders may not exist yet")
        return first_existing_root

    log.warning(
        "WoFF auto-discovery found no valid CFS3Path in the approved "
        "OFFManager5/OFFManager4 registry keys; configure watch paths manually."
    )
    return None
