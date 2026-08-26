"""Shared process-level contracts for WoFF command entry points."""

from __future__ import annotations

import sys
from enum import IntEnum


class ExitCode(IntEnum):
    """Stable exit statuses exposed by the public commands."""

    SUCCESS = 0
    RUNTIME_ERROR = 1
    USAGE_ERROR = 2


def emit_diagnostic(message: str) -> None:
    """Write a human diagnostic without contaminating command data on stdout."""

    print(message, file=sys.stderr)
