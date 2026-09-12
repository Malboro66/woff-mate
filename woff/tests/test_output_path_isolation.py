from pathlib import Path
import os
import subprocess
from unittest.mock import patch

import pytest

from .. import config as config_module
from ..config import InvalidConfigurationError, WatchdogConfig
from ..woff_watchdog import WoFFWatchdog


def test_export_path_equal_to_watch_root_is_rejected_before_database_open(tmp_path: Path) -> None:
    root = tmp_path / "woff-source"
    root.mkdir()

    with patch("woff.woff_watchdog.DatabaseManager") as database:
        with pytest.raises(InvalidConfigurationError, match="export_path"):
            WoFFWatchdog(
                WatchdogConfig(
                    watch_paths=[str(root)],
                    export_path=str(root),
                    discovery_log_path=str(tmp_path / "discovery.log"),
                    backup_export=False,
                )
            )

    database.assert_not_called()


@pytest.mark.parametrize("field", ["export_path", "discovery_log_path"])
def test_output_descendant_of_watch_root_is_rejected(field: str, tmp_path: Path) -> None:
    root = tmp_path / "woff-source"
    root.mkdir()
    values = {
        "watch_paths": [str(root)],
        "export_path": str(tmp_path / "external.db"),
        "discovery_log_path": str(tmp_path / "external.log"),
        "backup_export": False,
    }
    values[field] = str(root / "nested" / Path(values[field]).name)

    with pytest.raises(InvalidConfigurationError, match=field):
        WatchdogConfig(**values)


def test_similarly_prefixed_external_output_remains_valid(tmp_path: Path) -> None:
    root = tmp_path / "woff"
    sibling = tmp_path / "woff-backup"
    root.mkdir()
    sibling.mkdir()

    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(sibling / "output.db"),
        discovery_log_path=str(sibling / "discovery.log"),
        backup_export=False,
    )

    assert config.export_path == str(sibling / "output.db")


@pytest.mark.parametrize(
    ("field", "filename"),
    [("export_path", "Pilot1Dossier.txt"), ("discovery_log_path", "Mission.log")],
)
def test_supported_case_alias_is_rejected_without_changing_source(
    field: str, filename: str, tmp_path: Path
) -> None:
    root = tmp_path / "woff-source"
    root.mkdir()
    source = root / filename
    original = b"SYNTHETIC-WOFF-SOURCE\r\n"
    source.write_bytes(original)
    alias = root / filename.swapcase()
    values = {
        "watch_paths": [str(root)],
        "export_path": str(tmp_path / "external.db"),
        "discovery_log_path": str(tmp_path / "external.log"),
        "backup_export": False,
    }
    values[field] = str(alias)

    with pytest.raises(InvalidConfigurationError, match=field):
        WatchdogConfig(**values)

    assert source.read_bytes() == original


def test_overlapping_diagnostic_is_field_specific_and_sanitized(tmp_path: Path) -> None:
    root = tmp_path / "private-campaign-root"
    root.mkdir()

    with pytest.raises(InvalidConfigurationError) as failure:
        WatchdogConfig(
            watch_paths=[str(root)],
            export_path=str(tmp_path / "external.db"),
            discovery_log_path=str(root / "Mission.log"),
            backup_export=False,
        )

    diagnostic = str(failure.value)
    assert diagnostic == "discovery_log_path overlaps a watched root"
    assert str(root) not in diagnostic


@pytest.mark.parametrize("field", ["export_path", "discovery_log_path"])
def test_identity_failure_diagnostic_is_field_specific_and_sanitized(
    field: str, tmp_path: Path
) -> None:
    root = tmp_path / "private-campaign-root"
    root.mkdir()
    values = {
        "watch_paths": [str(root)],
        "export_path": str(tmp_path / "external.db"),
        "discovery_log_path": str(tmp_path / "external.log"),
        "backup_export": False,
    }
    values[field] = str(tmp_path / "private-output-alias")

    real_identity = config_module._filesystem_identity

    def fail_selected_identity(path: str) -> str:
        if path == values[field]:
            raise InvalidConfigurationError("output path identity could not be established")
        return real_identity(path)

    with patch.object(config_module, "_filesystem_identity", side_effect=fail_selected_identity):
        with pytest.raises(InvalidConfigurationError) as failure:
            WatchdogConfig(**values)

    diagnostic = str(failure.value)
    assert field in diagnostic
    assert "filesystem identity could not be established" in diagnostic
    assert str(root) not in diagnostic
    assert str(values[field]) not in diagnostic


def test_watched_root_identity_failure_keeps_output_field_context(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private-watched-root"
    root.mkdir()
    external_output = tmp_path / "external.db"
    external_log = tmp_path / "external.log"
    real_identity = config_module._filesystem_identity

    def fail_watched_root(path: str) -> str:
        if path == str(root):
            raise InvalidConfigurationError("output path identity could not be established")
        return real_identity(path)

    with patch.object(config_module, "_filesystem_identity", side_effect=fail_watched_root):
        with pytest.raises(
            InvalidConfigurationError,
            match="export_path watched-root filesystem identity could not be established",
        ):
            WatchdogConfig(
                watch_paths=[str(root)],
                export_path=str(external_output),
                discovery_log_path=str(external_log),
                backup_export=False,
            )


def test_watchdog_rejects_discovery_output_before_logger_construction(
    tmp_path: Path,
) -> None:
    root = tmp_path / "woff-source"
    root.mkdir()
    source = root / "Mission.log"
    original = b"SYNTHETIC-MISSION-SOURCE\r\n"
    source.write_bytes(original)
    external = tmp_path / "outputs"
    external.mkdir()
    config = WatchdogConfig(
        watch_paths=[str(root)],
        export_path=str(external / "export.sqlite"),
        discovery_log_path=str(external / "discovery.log"),
        backup_export=False,
    )
    config.discovery_log_path = str(root / "nested" / "discovery.log")

    with patch("woff.woff_watchdog.DiscoveryLogger") as discovery_logger:
        with pytest.raises(InvalidConfigurationError, match="discovery_log_path"):
            WoFFWatchdog(config, discovery=True)

    discovery_logger.assert_not_called()
    assert source.read_bytes() == original
    assert not (root / "nested" / "discovery.log").exists()


def _make_junction(link: Path, target: Path) -> None:
    if os.name != "nt":
        pytest.skip("ordinary directory junctions are Windows-only")
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        pytest.skip("ordinary directory junctions are unavailable on this host")


def test_output_through_directory_junction_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "physical-source"
    alias = tmp_path / "output-alias"
    root.mkdir()
    _make_junction(alias, root)

    with pytest.raises(InvalidConfigurationError, match="export_path"):
        WatchdogConfig(
            watch_paths=[str(root)],
            export_path=str(alias / "nested" / "output.db"),
            discovery_log_path=str(tmp_path / "external.log"),
            backup_export=False,
        )


def test_watched_root_through_directory_junction_is_rejected(tmp_path: Path) -> None:
    physical = tmp_path / "physical-source"
    alias = tmp_path / "watched-alias"
    physical.mkdir()
    _make_junction(alias, physical)

    with pytest.raises(InvalidConfigurationError, match="discovery_log_path"):
        WatchdogConfig(
            watch_paths=[str(alias)],
            export_path=str(tmp_path / "external.db"),
            discovery_log_path=str(physical / "Mission.log"),
            backup_export=False,
        )


@pytest.mark.parametrize("field", ["export_path", "discovery_log_path"])
def test_broken_directory_junction_fails_closed(
    field: str, tmp_path: Path
) -> None:
    target = tmp_path / "junction-target"
    alias = tmp_path / "broken-alias"
    target.mkdir()
    _make_junction(alias, target)
    target.rmdir()

    values = {
        "watch_paths": [str(tmp_path / "external-source")],
        "export_path": str(tmp_path / "external.db"),
        "discovery_log_path": str(tmp_path / "external.log"),
        "backup_export": False,
    }
    values[field] = str(alias / "output.db")

    with pytest.raises(
        InvalidConfigurationError,
        match=rf"{field} .*filesystem identity could not be established",
    ):
        WatchdogConfig(**values)