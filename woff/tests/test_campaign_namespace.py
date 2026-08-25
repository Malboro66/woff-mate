from __future__ import annotations

from unittest.mock import patch

import pytest

from .. import campaign_namespace, woff_watchdog
from ..campaign_namespace import (
    CampaignNamespaceError,
    CampaignNamespaceResolver,
    campaign_namespace_for_root,
    campaign_namespaces_for_roots,
)
from ..config import InvalidConfigurationError, WatchdogConfig


def test_equivalent_windows_root_spellings_share_one_namespace() -> None:
    spellings = (
        r"C:\WoFF\Campaigns\RootA",
        r"c:/woff/campaigns/roota/.",
        r"\\?\C:\WOFF\Campaigns\RootA",
    )

    assert len({campaign_namespace_for_root(path) for path in spellings}) == 1


def test_distinct_roots_receive_distinct_sanitized_namespaces() -> None:
    namespaces = campaign_namespaces_for_roots(
        (r"C:\WoFF\CampaignA", r"D:\WoFF\CampaignB")
    )

    assert len(namespaces) == len(set(namespaces)) == 2
    assert all(namespace.startswith("root-v1:") for namespace in namespaces)
    assert all(
        "WoFF" not in namespace and "Campaign" not in namespace
        for namespace in namespaces
    )


@pytest.mark.parametrize(
    "watch_paths",
    [
        [r"C:\WoFF\Campaign", r"c:/woff/campaign/."],
        [r"C:\WoFF", r"C:\WoFF\Campaign"],
    ],
)
def test_duplicate_or_overlapping_roots_fail_with_sanitized_diagnostic(
    watch_paths: list[str],
) -> None:
    with pytest.raises(InvalidConfigurationError) as failure:
        WatchdogConfig(watch_paths=watch_paths)

    diagnostic = str(failure.value)
    assert "duplicate or overlapping" in diagnostic
    assert all(path not in diagnostic for path in watch_paths)


def test_resolver_rejects_sources_outside_configured_roots(tmp_path) -> None:
    root = tmp_path / "root"
    other = tmp_path / "other"
    resolver = CampaignNamespaceResolver([str(root)])

    assert resolver.namespace_for(str(root / "Pilot1Dossier.txt")) == (
        campaign_namespace_for_root(str(root))
    )
    with pytest.raises(CampaignNamespaceError, match="outside configured"):
        resolver.namespace_for(str(other / "Pilot1Dossier.txt"))


def test_resolver_never_recanonicalizes_an_already_canonical_root(
    tmp_path,
) -> None:
    root = tmp_path / "root"
    source = root / "Pilot1Dossier.txt"

    with patch.object(campaign_namespace.ntpath, "isabs", return_value=False):
        resolver = CampaignNamespaceResolver([str(root)])
        expected = campaign_namespace_for_root(str(root))

        assert resolver.namespace_for(str(source)) == expected


def test_conflicting_roots_fail_before_database_or_workers_are_created() -> None:
    config = WatchdogConfig(watch_paths=[r"C:\WoFF\Campaign"])
    config.watch_paths.append(r"c:/woff/campaign/.")

    with patch.object(woff_watchdog, "DatabaseManager") as database:
        with pytest.raises(InvalidConfigurationError):
            woff_watchdog.WoFFWatchdog(config)

    database.assert_not_called()
