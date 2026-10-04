"""Build/evidence policy for #177; never imported by the headless core."""
from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import importlib.util
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

VERSION = "6.11.2"
BINDINGS = ("PySide", "PySide2", "PySide6", "PyQt4", "PyQt5", "PyQt6")
PACKAGES = ("PySide6", "PySide6_Essentials", "PySide6_Addons", "shiboken6")
ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    "pyproject.toml", "ui_adoption.spec", "ui_adoption_launcher.py",
    "scripts/ui_adoption_support.py", "scripts/ui_adoption_probe.py",
    "scripts/ui_adoption_inventory.py", "docs/ui/ui-adoption-licensing.md",
    "scripts/validate_ui_adoption_windows.ps1", "LICENSE",
    "woff/p0_desktop", "woff/ui_contracts.py", "woff/nation.py",
    "woff/tests/fixtures/ui_states/catalog.json", "woff/assets/ui",
)
# Widgets/SVG only. QtTest is deliberately retained for the candidate's executable
# keyboard evidence. DBus is an indirect Linux QtGui dependency, not a live service.
QT_MODULES = {"Core", "Gui", "Widgets", "Svg", "Test", "DBus"}
PLUGINS = {"platforms/qwindows.dll", "platforms/libqoffscreen.so",
           "platforms/qoffscreen.dll", "imageformats/qico.dll",
           "imageformats/libqico.so", "styles/qmodernwindowsstyle.dll"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_bindings(*, base: bool = False) -> dict:
    """Reject installed metadata AND importable unmanaged alternate bindings."""
    found = set()
    distributions = {re.sub(r"[-_.]+", "-", d.metadata["Name"]).lower()
                     for d in metadata.distributions() if d.metadata["Name"]}
    for name in BINDINGS:
        if any(d == name.lower() or d.startswith(name.lower() + '-') for d in distributions) or importlib.util.find_spec(name) is not None:
            found.add(name)
    expected = set() if base else {"PySide6"}
    if found != expected:
        raise RuntimeError(f"Expected Qt bindings {sorted(expected)}; found {sorted(found)}")
    versions = {} if base else {name: metadata.version(name) for name in PACKAGES}
    if any(version != VERSION for version in versions.values()):
        raise RuntimeError(f"UI packages must all be {VERSION}: {versions}")
    return {"bindings": sorted(found), "versions": versions}


def provenance() -> dict:
    files = []
    for name in INPUTS:
        path = ROOT / name
        if path.is_dir():
            files.extend(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        else:
            files.append(path)
    hashes = {p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted(files)}
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *INPUTS], cwd=ROOT, text=True).strip()
    return {"revision": revision, "input_tree_dirty": bool(dirty), "input_sha256": hashes,
            "input_digest": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()}


def environment() -> dict:
    return {"python": platform.python_version(), "system": platform.system(),
            "machine": platform.machine(), **check_bindings()}


def allowed_qt_file(name: str) -> bool:
    """Only constrain Qt/binding files; inventory records all other libraries."""
    normalized = name.replace("\\", "/")
    lower = normalized.lower()
    if any(token in lower for token in ("virtualkeyboard", "pyqt", "pyside2", "pyside/", "qt5", "/qml/")):
        return False
    if "/plugins/" in normalized:
        return normalized.split("/plugins/", 1)[1] in PLUGINS
    filename = normalized.rsplit("/", 1)[-1]
    match = re.match(r"(?:lib)?Qt6([A-Za-z0-9]+)(?:\.dll|\.so(?:\..*)?)$", filename)
    if match:
        return match.group(1) in QT_MODULES
    match = re.match(r"Qt([A-Za-z0-9]+)\.(?:abi3\.so|pyd)$", filename)
    if match and "PySide6/" in normalized:
        return match.group(1) in QT_MODULES
    return True


def binary_origin(path: Path) -> dict:
    """Sanitized collection identity; never persist a developer's absolute path."""
    result: dict = {'source_name': path.name, 'source_sha256': sha256(path)}
    for package in PACKAGES:
        dist = metadata.distribution(package)
        for entry in dist.files or []:
            if entry.name == path.name and Path(str(dist.locate_file(entry))).resolve() == path.resolve():
                result.update(origin=f'https://pypi.org/project/{package}/{dist.version}/',
                              package=package, version=dist.version, package_path=str(entry))
                return result
    if platform.system() == 'Linux':
        for candidate in {str(path), str(path.resolve()), str(path).replace('/usr/lib/', '/lib/')}:
            query = subprocess.run(['dpkg-query', '-S', candidate], capture_output=True, text=True)
            if query.returncode == 0:
                package = query.stdout.split(': ', 1)[0]
                version = subprocess.check_output(['dpkg-query', '-W', '-f=${Version}', package], text=True)
                copyright_path = Path('/usr/share/doc') / package.split(':')[0] / 'copyright'
                result.update(origin='build-host Debian package', package=package, version=version)
                if copyright_path.is_file():
                    result['copyright_sha256'] = sha256(copyright_path)
                    result['copyright_identifiers'] = sorted(set(re.findall(
                        r'^License: (.+)$', copyright_path.read_text(errors='replace'), re.MULTILINE)))
                return result
    result['origin'] = 'Python/toolchain runtime collection; source file identity retained'
    return result
