"""Stable, privacy-preserving identity for configured campaign roots."""

from __future__ import annotations

import hashlib
import ntpath
import os
import re
from typing import Optional, Sequence


CAMPAIGN_NAMESPACE_PREFIX = "root-v1:"
LEGACY_CAMPAIGN_NAMESPACE = "legacy-v3.2"
_CAMPAIGN_NAMESPACE = re.compile(r"^root-v1:[0-9a-f]{64}$")


class CampaignNamespaceError(ValueError):
    """Raised when a source cannot be assigned to one configured root."""


class CampaignNamespaceConflict(CampaignNamespaceError):
    """Raised when configured roots do not define distinct namespaces."""


def canonical_windows_path(path: str) -> str:
    """Return one absolute identity key for equivalent native/Windows paths."""

    if not isinstance(path, str) or not path.strip():
        raise CampaignNamespaceError("path must be a nonblank string")
    normalized = path.replace("/", "\\")
    lowered = normalized.lower()
    if lowered.startswith("\\\\?\\unc\\"):
        normalized = "\\\\" + normalized[8:]
    elif lowered.startswith("\\\\?\\"):
        normalized = normalized[4:]
    if not ntpath.isabs(normalized):
        normalized = os.path.abspath(path).replace("/", "\\")
    return ntpath.normcase(ntpath.normpath(normalized))


def campaign_namespace_for_root(root: str) -> str:
    """Derive a stable namespace without persisting the configured path."""

    canonical = canonical_windows_path(root)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{CAMPAIGN_NAMESPACE_PREFIX}{digest}"


def is_campaign_namespace(value: object, *, allow_legacy: bool = False) -> bool:
    """Return whether a value is a supported persisted namespace identifier."""

    return isinstance(value, str) and (
        _CAMPAIGN_NAMESPACE.fullmatch(value) is not None
        or (allow_legacy and value == LEGACY_CAMPAIGN_NAMESPACE)
    )


def campaign_namespace_label(namespace: str) -> str:
    """Return a short sanitized identifier suitable for diagnostics."""

    if namespace == LEGACY_CAMPAIGN_NAMESPACE:
        return namespace
    if not is_campaign_namespace(namespace):
        return "invalid"
    return f"root-v1:{namespace[-12:]}"


def _contains(root: str, path: str) -> bool:
    try:
        return ntpath.commonpath((root, path)) == root
    except ValueError:
        return False


def canonical_watch_roots(roots: Sequence[str]) -> tuple[str, ...]:
    """Validate that configured roots are unique and never overlap."""

    canonical = tuple(canonical_windows_path(root) for root in roots)
    for index, root in enumerate(canonical):
        for other in canonical[index + 1 :]:
            if _contains(root, other) or _contains(other, root):
                raise CampaignNamespaceConflict(
                    "watch_paths contain duplicate or overlapping campaign roots"
                )
    return canonical


def campaign_namespaces_for_roots(roots: Sequence[str]) -> tuple[str, ...]:
    """Return one deterministic namespace for every configured root."""

    canonical = canonical_watch_roots(roots)
    return tuple(campaign_namespace_for_root(root) for root in canonical)


class CampaignNamespaceResolver:
    """Resolve each source path to exactly one configured campaign namespace."""

    def __init__(self, roots: Optional[Sequence[str]] = None) -> None:
        self._strict = roots is not None
        self._roots = canonical_watch_roots(roots or ())

    def namespace_for(self, path: str) -> str:
        canonical = canonical_windows_path(path)
        matches = [root for root in self._roots if _contains(root, canonical)]
        if len(matches) == 1:
            return campaign_namespace_for_root(matches[0])
        if len(matches) > 1:
            raise CampaignNamespaceConflict("source matches multiple campaign roots")
        if self._strict:
            raise CampaignNamespaceError("source is outside configured campaign roots")
        parent = ntpath.dirname(canonical)
        return campaign_namespace_for_root(parent)
