import math
from dataclasses import asdict
from unittest.mock import patch

import pytest

from ..config import InvalidConfigurationError, WatchdogConfig, load_config


def valid_config(**overrides):
    values = asdict(WatchdogConfig())
    values.update(overrides)
    return values


@pytest.mark.parametrize(("field", "values"), [
    ("watch_paths", [None, "path", [""], [1]]),
    ("export_path", [None, 1, " "]),
    ("watched_extensions", [None, ".xml", [], ["xml"], ["."], [1], [".XML", ".xml"]]),
    ("stability_timeout_sec", [None, True, "3", 0, -1, math.inf, math.nan]),
    ("stability_check_interval_sec", [None, False, "1", 0, -1, math.inf, math.nan, 3.0]),
    ("backup_export", [None, 0, "true"]),
    ("discovery_log_path", [None, 1, " "]),
    ("log_level", [None, 1, "", "TRACE"]),
    ("max_workers", [None, True, 0, -1, 1.5, "4"]),
    ("max_pending_events", [None, True, 0, -1, 1.5, "1024"]),
    ("config_version", [None, 1, "future"]),
])
def test_invalid_fields_fail_both_construction_paths(field, values):
    for value in values:
        with pytest.raises(InvalidConfigurationError):
            WatchdogConfig(**valid_config(**{field: value}))
        with pytest.raises(InvalidConfigurationError):
            WatchdogConfig.from_dict(valid_config(**{field: value}))


def test_normalization_uses_both_construction_paths():
    direct = WatchdogConfig(log_level="warning", watched_extensions=[".XML", ".Txt"])
    loaded = WatchdogConfig.from_dict(valid_config(log_level="warning", watched_extensions=[".XML", ".Txt"]))
    assert direct.log_level == loaded.log_level == "WARNING"
    assert direct.watched_extensions == loaded.watched_extensions == [".xml", ".txt"]


def test_unsupported_watched_extensions_are_rejected_by_both_construction_paths():
    with pytest.raises(InvalidConfigurationError, match="not supported"):
        WatchdogConfig(watched_extensions=[".dat"])
    with pytest.raises(InvalidConfigurationError, match="not supported"):
        WatchdogConfig.from_dict(valid_config(watched_extensions=[".dat"]))


def test_missing_config_uses_fallback(tmp_path):
    path = tmp_path / "missing.json"
    with patch("woff.win_registry.get_woff_install_path", return_value=None):
        assert load_config(str(path)) == WatchdogConfig()
    assert not path.exists()


@pytest.mark.parametrize("content", [b"{broken", b"[]", b'{"max_workers": true}'])
def test_invalid_existing_config_is_preserved(tmp_path, content):
    path = tmp_path / "config.json"
    path.write_bytes(content)
    with patch("woff.win_registry.get_woff_install_path") as detection:
        with pytest.raises(InvalidConfigurationError):
            load_config(str(path))
    detection.assert_not_called()
    assert path.read_bytes() == content
