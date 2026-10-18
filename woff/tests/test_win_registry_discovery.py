"""Issue #49: bounded, version-tolerant WoFF registry discovery."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from woff import win_registry
from woff.config import load_config


CURRENT = r"Software\VB and VBA Program Settings\OFFManager4\Settings"
NEXT = r"Software\VB and VBA Program Settings\OFFManager5\Settings"


class FakeWinReg:
    HKEY_CURRENT_USER: int = 1

    def __init__(self, entries: dict[str, object]):
        self.entries = entries
        self.opened: list[str] = []
        self.queried: list[tuple[str, str]] = []
        self.closed: list[str] = []

    def OpenKey(self, key: int, sub_key: str) -> str:
        assert key == self.HKEY_CURRENT_USER
        self.opened.append(sub_key)
        if sub_key not in self.entries:
            raise FileNotFoundError(sub_key)
        return sub_key

    def QueryValueEx(self, key: str, value_name: str) -> tuple[object, int]:
        self.queried.append((key, value_name))
        value = self.entries[key]
        if isinstance(value, Exception):
            raise value
        return value, 1

    def CloseKey(self, key: str) -> None:
        self.closed.append(key)


def _make_dir(tmp_path: Path, name: str) -> str:
    folder = tmp_path / name
    (folder / "campaigns" / "CampaignData" / "Pilots").mkdir(parents=True)
    (folder / "Logs").mkdir()
    return str(folder)


def test_explicit_order_and_allowlist() -> None:
    assert win_registry.WOFF_REG_KEY == CURRENT
    assert win_registry.WOFF_REG_KEYS == (NEXT, CURRENT)
    assert win_registry.ALLOWED_WOFF_REGISTRY_VALUES == frozenset({"CFS3Path"})


@pytest.mark.parametrize(
    ("entries", "selected", "checked", "queried", "closed"),
    [
        ({"current": "valid"}, "current", [NEXT, CURRENT], [CURRENT], [CURRENT]),
        ({"current": "valid", "next": "valid"}, "next", [NEXT], [NEXT], [NEXT]),
        ({"current": "valid", "next": "stale"}, "current", [NEXT, CURRENT], [NEXT, CURRENT], [NEXT, CURRENT]),
        ({"current": "valid", "next": "blank"}, "current", [NEXT, CURRENT], [NEXT, CURRENT], [NEXT, CURRENT]),
        ({"current": "valid", "next": "wrong-type"}, "current", [NEXT, CURRENT], [NEXT, CURRENT], [NEXT, CURRENT]),
        ({"current": "valid", "next": "relative"}, "current", [NEXT, CURRENT], [NEXT, CURRENT], [NEXT, CURRENT]),
        ({"current": "valid", "next": "missing-value"}, "current", [NEXT, CURRENT], [NEXT, CURRENT], [NEXT, CURRENT]),
    ],
)
def test_precedence_and_validation(
    tmp_path: Path,
    entries: dict[str, str],
    selected: str,
    checked: list[str],
    queried: list[str],
    closed: list[str],
) -> None:
    current_path = _make_dir(tmp_path, "current")
    next_path = _make_dir(tmp_path, "next")
    values: dict[str, object] = {
        "valid": None,
        "stale": str(tmp_path / "does-not-exist"),
        "blank": " \t ",
        "wrong-type": 99,
        "relative": "relative/path",
        "missing-value": FileNotFoundError("CFS3Path"),
    }
    values_for_keys: dict[str, object] = {}
    for name, value in entries.items():
        key = CURRENT if name == "current" else NEXT
        values_for_keys[key] = (current_path if name == "current" else next_path) if value == "valid" else values[value]

    fake = FakeWinReg(values_for_keys)
    result = win_registry.get_woff_install_path(registry=fake)

    assert result == (current_path if selected == "current" else next_path)
    assert fake.opened == checked
    assert fake.queried == [(key, "CFS3Path") for key in queried]
    assert fake.closed == closed


def test_only_explicit_keys_are_probed(tmp_path: Path) -> None:
    unrelated = r"Software\AnotherProduct\Settings"
    fake = FakeWinReg({unrelated: _make_dir(tmp_path, "unrelated")})
    assert win_registry.get_woff_install_path(registry=fake) is None
    assert fake.opened == [NEXT, CURRENT]
    assert fake.queried == []
    assert fake.closed == []


def test_open_error_skips_candidate(tmp_path: Path) -> None:
    current_path = _make_dir(tmp_path, "current")
    fake = FakeWinReg({CURRENT: current_path})
    # The newer key is missing; a valid current-version key must still work.
    assert win_registry.get_woff_install_path(registry=fake) == current_path
    assert fake.opened == [NEXT, CURRENT]


def test_missing_candidates_have_one_actionable_warning(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeWinReg({})
    with caplog.at_level(logging.WARNING, logger="WoFFWatch"):
        assert win_registry.get_woff_install_path(registry=fake) is None
    warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "manual" in warnings[0].lower()
    assert "OFFManager4" in warnings[0]
    assert "OFFManager5" in warnings[0]
    assert "not installed" not in warnings[0].lower()


def test_config_loader_integrates_with_registry_candidate(tmp_path: Path) -> None:
    game = tmp_path / "game"
    (game / "campaigns" / "CampaignData" / "Pilots").mkdir(parents=True)
    (game / "Logs").mkdir()
    fake = FakeWinReg({NEXT: str(game)})
    from unittest.mock import patch

    discover = win_registry.get_woff_install_path
    with patch("woff.win_registry.get_woff_install_path", side_effect=lambda: discover(registry=fake)):
        config = load_config(str(tmp_path / "settings.json"))

    assert config.watch_paths == [
        str(game / "campaigns" / "CampaignData" / "Pilots"),
        str(game / "Logs"),
    ]
    assert (tmp_path / "settings.json").exists()
    assert fake.queried == [(NEXT, "CFS3Path")]


def test_existing_unrelated_directory_is_not_a_woff_install(tmp_path: Path) -> None:
    unrelated = tmp_path / "just-a-directory"
    unrelated.mkdir()
    current = _make_dir(tmp_path, "current")
    fake = FakeWinReg({NEXT: str(unrelated), CURRENT: current})
    assert win_registry.get_woff_install_path(registry=fake) == current
    assert fake.opened == [NEXT, CURRENT]
    assert fake.closed == [NEXT, CURRENT]


def test_parent_logs_directory_is_accepted(tmp_path: Path) -> None:
    root = tmp_path / "game" / "sim"
    (root / "campaigns" / "CampaignData" / "Pilots").mkdir(parents=True)
    (root.parent / "Logs").mkdir()
    fake = FakeWinReg({CURRENT: str(root)})
    assert win_registry.get_woff_install_path(registry=fake) == str(root)


def test_registry_query_type_and_access_errors_fall_through(tmp_path: Path) -> None:
    current = _make_dir(tmp_path, "current")
    newer = _make_dir(tmp_path, "newer")

    class FakeProblemWinReg(FakeWinReg):
        def QueryValueEx(self, key: str, value_name: str) -> tuple[object, int]:
            if key == NEXT:
                self.queried.append((key, value_name))
                return newer, 4  # REG_DWORD is not a valid path type
            return super().QueryValueEx(key, value_name)

    wrong_type = FakeProblemWinReg({NEXT: newer, CURRENT: current})
    assert win_registry.get_woff_install_path(registry=wrong_type) == current
    assert wrong_type.closed == [NEXT, CURRENT]

    class FakeAccessDeniedWinReg(FakeWinReg):
        def OpenKey(self, key: int, sub_key: str) -> str:
            if sub_key == NEXT:
                self.opened.append(sub_key)
                raise PermissionError("registry access denied")
            return super().OpenKey(key, sub_key)

    denied = FakeAccessDeniedWinReg({CURRENT: current})
    assert win_registry.get_woff_install_path(registry=denied) == current
    assert denied.opened == [NEXT, CURRENT]
    assert denied.closed == [CURRENT]


def test_existing_root_without_generated_folders_is_retained(tmp_path: Path) -> None:
    """No career yet: do not turn a supported existing install into 'not found'."""
    game_root = tmp_path / "empty-woff-install"
    game_root.mkdir()
    fake = FakeWinReg({CURRENT: str(game_root)})
    assert win_registry.get_woff_install_path(registry=fake) == str(game_root)

    from unittest.mock import patch

    discover = win_registry.get_woff_install_path
    config_path = tmp_path / "new-config.json"
    with patch("woff.win_registry.get_woff_install_path",
               side_effect=lambda: discover(registry=fake)):
        cfg = load_config(str(config_path))

    assert cfg.watch_paths == [
        str(game_root / "campaigns" / "CampaignData" / "Pilots"),
        str(game_root / "Logs"),
    ]
    assert config_path.exists()


def test_ready_candidate_takes_precedence_over_incomplete_newer_root(
    tmp_path: Path,
) -> None:
    ready = _make_dir(tmp_path, "ready")
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    fake = FakeWinReg({NEXT: str(incomplete), CURRENT: ready})

    assert win_registry.get_woff_install_path(registry=fake) == ready
    assert fake.opened == [NEXT, CURRENT]
    assert fake.closed == [NEXT, CURRENT]


def test_two_incomplete_existing_roots_use_documented_key_order(
    tmp_path: Path,
) -> None:
    newer = tmp_path / "newer"
    older = tmp_path / "older"
    newer.mkdir()
    older.mkdir()
    fake = FakeWinReg({CURRENT: str(older), NEXT: str(newer)})

    assert win_registry.get_woff_install_path(registry=fake) == str(newer)
    assert fake.opened == [NEXT, CURRENT]
    assert fake.closed == [NEXT, CURRENT]


def test_config_loader_missing_keys_has_one_manual_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeWinReg({})
    from unittest.mock import patch

    discover = win_registry.get_woff_install_path
    with caplog.at_level(logging.WARNING, logger="WoFFWatch"):
        with patch("woff.win_registry.get_woff_install_path",
                   side_effect=lambda: discover(registry=fake)):
            cfg = load_config(str(tmp_path / "missing-config.json"))

    assert cfg.watch_paths == []
    assert not (tmp_path / "missing-config.json").exists()
    warnings = [r.getMessage() for r in caplog.records
                if r.name == "WoFFWatch" and r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "manual" in warnings[0].lower()
    assert "OFFManager4" in warnings[0]
    assert "OFFManager5" in warnings[0]
