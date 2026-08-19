from __future__ import annotations

import ast
import sys
from pathlib import Path

from woff import win_registry
from woff.config import WatchdogConfig
from woff.discovery import DiscoveryLogger


REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOT = REPO_ROOT / "woff"
FORBIDDEN_NETWORK_IMPORT_ROOTS = frozenset(
    {
        "aiohttp",
        "ftplib",
        "http",
        "httpx",
        "opentelemetry",
        "requests",
        "sentry_sdk",
        "smtplib",
        "socket",
        "telnetlib",
        "urllib",
        "websockets",
    }
)
FORBIDDEN_PERSISTED_CREDENTIAL_NAMES = frozenset(
    {
        "activation",
        "activation_key",
        "activationkey",
        "licence_key",
        "license_key",
        "product_key",
        "productkey",
        "serial",
        "serial_key",
    }
)
FORBIDDEN_REGISTRY_ENUMERATION_CALLS = frozenset({"EnumKey", "EnumValue"})


def _production_python_files() -> list[Path]:
    candidates = set(REPO_ROOT.glob("*.py"))
    candidates.update(PRODUCTION_ROOT.rglob("*.py"))
    candidates.update((REPO_ROOT / "scripts").rglob("*.py"))
    return sorted(path for path in candidates if "tests" not in path.parts)


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _import_roots(path: Path) -> set[str]:
    tree = _parse(path)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_registry_value_allowlist_is_explicit_and_minimal() -> None:
    allowed = getattr(win_registry, "ALLOWED_WOFF_REGISTRY_VALUES", None)
    assert allowed == frozenset({"CFS3Path"})


def test_registry_discovery_queries_only_the_install_path_value(monkeypatch) -> None:
    queried_values: list[str] = []

    class FakeWinReg:
        HKEY_CURRENT_USER = 1

        @staticmethod
        def OpenKey(key: int, sub_key: str):
            return (key, sub_key)

        @staticmethod
        def QueryValueEx(key, value_name: str):
            queried_values.append(value_name)
            return (r"C:\\OBDSoftware\\WOFF", 1)

        @staticmethod
        def CloseKey(key) -> None:
            return None

    monkeypatch.setitem(sys.modules, "winreg", FakeWinReg)

    assert win_registry.get_woff_install_path() == r"C:\OBDSoftware\WOFF"
    assert queried_values == ["CFS3Path"]


def test_production_registry_code_never_enumerates_values() -> None:
    violations: list[str] = []
    for path in _production_python_files():
        for node in ast.walk(_parse(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in FORBIDDEN_REGISTRY_ENUMERATION_CALLS
            ):
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno}:{node.func.attr}"
                )

    assert violations == []


def test_every_registry_value_query_uses_cfs3path_contract() -> None:
    violations: list[str] = []
    for path in _production_python_files():
        for node in ast.walk(_parse(path)):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "QueryValueEx"
            ):
                continue

            if len(node.args) < 2:
                violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}:missing-value")
                continue

            value_arg = node.args[1]
            approved = (
                isinstance(value_arg, ast.Name)
                and value_arg.id == "WOFF_REG_VALUE"
            ) or (
                isinstance(value_arg, ast.Constant)
                and value_arg.value == "CFS3Path"
            )
            if not approved:
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno}:unapproved-value"
                )

    assert violations == []


def test_core_runtime_has_no_network_client_imports() -> None:
    violations: list[str] = []
    for path in _production_python_files():
        forbidden = _import_roots(path) & FORBIDDEN_NETWORK_IMPORT_ROOTS
        if forbidden:
            relative = path.relative_to(REPO_ROOT)
            violations.append(f"{relative}: {sorted(forbidden)}")

    assert violations == []


def test_persisted_surfaces_do_not_define_activation_credentials() -> None:
    config_fields = {name.lower() for name in WatchdogConfig.__dataclass_fields__}
    assert config_fields.isdisjoint(FORBIDDEN_PERSISTED_CREDENTIAL_NAMES)

    database_source = (PRODUCTION_ROOT / "database.py").read_text(encoding="utf-8").lower()
    violations = sorted(
        token for token in FORBIDDEN_PERSISTED_CREDENTIAL_NAMES if token in database_source
    )
    assert violations == []


def test_discovery_never_previews_activation_like_file(tmp_path: Path) -> None:
    log_path = tmp_path / "woff_discovery.log"
    sensitive = tmp_path / "activation_key.txt"
    sensitive.write_text("SYNTHETIC-SECRET-MUST-NOT-BE-LOGGED", encoding="utf-8")

    logger = DiscoveryLogger(str(log_path))
    logger.log_file(str(sensitive), "created")

    log_text = log_path.read_text(encoding="utf-8")
    assert "SYNTHETIC-SECRET-MUST-NOT-BE-LOGGED" not in log_text
    assert "preview bloqueado pela política de privacidade" in log_text.lower()


def test_discovery_previews_known_woff_pilot_log(tmp_path: Path) -> None:
    log_path = tmp_path / "woff_discovery.log"
    pilot_log = tmp_path / "Pilot1Log.txt"
    pilot_log.write_text("SANITIZED-WOFF-CAMPAIGN-DATA", encoding="utf-8")

    logger = DiscoveryLogger(str(log_path))
    logger.log_file(str(pilot_log), "modified")

    log_text = log_path.read_text(encoding="utf-8")
    assert "SANITIZED-WOFF-CAMPAIGN-DATA" in log_text
