from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = REPOSITORY_ROOT / "woff" / "assets" / "ui" / "icons"
EVIDENCE_ROOT = (
    REPOSITORY_ROOT / "docs" / "ui" / "evidence" / "ui-v2-icons-2026-09-24"
)
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"
SIZES = (16, 20, 24, 32)
REQUIRED = {
    "nav.operations": ("nav_operations", ("regular", "filled")),
    "nav.pilot-dossier": ("nav_pilot_dossier", ("regular", "filled")),
    "nav.missions": ("nav_missions", ("regular", "filled")),
    "nav.squadron": ("nav_squadron", ("regular", "filled")),
    "nav.war-diary": ("nav_war_diary", ("regular", "filled")),
    "nav.reports": ("nav_reports", ("regular", "filled")),
    "nav.system-status": ("nav_system_status", ("regular", "filled")),
    "state.information": ("state_information", ("regular",)),
    "state.complete": ("state_complete", ("regular",)),
    "state.partial": ("state_partial", ("regular",)),
    "state.stale": ("state_stale", ("regular",)),
    "state.error": ("state_error", ("regular",)),
    "state.unavailable": ("state_unavailable", ("regular",)),
    "action.retry": ("action_retry", ("regular",)),
    "action.back": ("action_back", ("regular",)),
    "action.disclosure": ("action_disclosure", ("regular",)),
}


def _manifest() -> dict[str, object]:
    loaded = json.loads((ASSET_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _manifest_icons() -> list[dict[str, object]]:
    icons = _manifest()["icons"]
    assert isinstance(icons, list)
    assert all(isinstance(icon, dict) for icon in icons)
    return icons  # type: ignore[return-value]


def _expected_assets() -> set[str]:
    return {
        f"ui_{semantic}_{size}_{style}.svg"
        for semantic, styles in REQUIRED.values()
        for size in SIZES
        for style in styles
    }


def _load_checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        assert relative not in checksums
        checksums[relative] = digest
    return checksums


def test_q0_decision_and_provenance_are_pinned() -> None:
    manifest = _manifest()
    source = manifest["source"]
    assert isinstance(source, dict)
    assert source == {
        "strategy": "adapt",
        "family": "Microsoft Fluent System Icons",
        "repository": "https://github.com/microsoft/fluentui-system-icons",
        "revision": "8ab43f850c7e8858edf9cb848ba2376f30b7faa3",
        "revision_date": "2026-09-23",
        "license": "MIT",
        "license_file": "LICENSES/FLUENT-SYSTEM-ICONS-LICENSE.txt",
        "notice_file": "LICENSES/FLUENT-SYSTEM-ICONS-NOTICE.txt",
        "modification": (
            'Each upstream fill="#212121" is changed to fill="currentColor". '
            "Geometry, viewBox, dimensions, element order and size-specific "
            "optical masters are otherwise unchanged."
        ),
    }
    license_text = (ASSET_ROOT / str(source["license_file"])).read_text(
        encoding="utf-8"
    )
    assert "Copyright (c) 2020 Microsoft Corporation" in license_text
    assert "Permission is hereby granted" in license_text
    assert (ASSET_ROOT / str(source["notice_file"])).is_file()


def test_required_semantics_are_unique_and_complete() -> None:
    icons = _manifest_icons()
    ids = [str(icon["id"]) for icon in icons]
    semantics = [str(icon["semantic"]) for icon in icons]
    upstream = [str(icon["upstream_icon"]) for icon in icons]
    assert set(ids) == set(REQUIRED)
    assert len(ids) == len(set(ids)) == 16
    assert len(semantics) == len(set(semantics)) == 16
    assert len(upstream) == len(set(upstream)) == 16

    by_id = {str(icon["id"]): icon for icon in icons}
    for icon_id, (semantic, styles) in REQUIRED.items():
        icon = by_id[icon_id]
        assert icon["semantic"] == semantic
        assert icon["approved_sizes"] == list(SIZES)
        assert icon["styles"] == list(styles)
        assert icon["accessibility"]
        assert icon["prohibited_uses"]
        assert icon["rtl"] in {"do_not_mirror", "mirror_when_rtl_is_introduced"}
    assert by_id["action.back"]["rtl"] == "mirror_when_rtl_is_introduced"
    assert by_id["action.disclosure"]["rtl"] == "mirror_when_rtl_is_introduced"


def test_manifest_and_asset_files_are_synchronized() -> None:
    actual = {path.name for path in ASSET_ROOT.glob("ui_*.svg")}
    assert actual == _expected_assets()
    assert len(actual) == 92

    package_checksums = _load_checksums(ASSET_ROOT / "SHA256SUMS")
    expected_checked = _expected_assets() | {
        "LICENSES/FLUENT-SYSTEM-ICONS-LICENSE.txt",
        "LICENSES/FLUENT-SYSTEM-ICONS-NOTICE.txt",
        "README.md",
        "manifest.json",
    }
    assert set(package_checksums) == expected_checked
    for relative, expected in package_checksums.items():
        assert hashlib.sha256((ASSET_ROOT / relative).read_bytes()).hexdigest() == expected


def test_svgs_are_self_contained_themeable_shapes() -> None:
    forbidden_elements = {"image", "text", "script", "style", "foreignObject"}
    forbidden_metadata = ("pyside", "pyqt", "qt", "react", "tailwind", "font-family")
    for path in sorted(ASSET_ROOT.glob("ui_*.svg")):
        match = re.fullmatch(r"ui_.+_(16|20|24|32)_(regular|filled)\.svg", path.name)
        assert match is not None
        size = int(match.group(1))
        root = ET.parse(path).getroot()
        assert root.tag == f"{SVG_NAMESPACE}svg"
        assert root.attrib["width"] == str(size)
        assert root.attrib["height"] == str(size)
        assert root.attrib["viewBox"] == f"0 0 {size} {size}"

        payload = path.read_text(encoding="utf-8").lower()
        assert all(term not in payload for term in forbidden_metadata)
        assert "#212121" not in payload
        assert "currentcolor" in payload

        for element in root.iter():
            local_name = element.tag.rsplit("}", 1)[-1]
            assert local_name not in forbidden_elements
            assert not any(name.endswith("href") for name in element.attrib)
            for attribute, value in element.attrib.items():
                if attribute == "fill":
                    assert value in {"none", "currentColor"}


def test_small_sizes_use_distinct_optical_geometry() -> None:
    for _icon_id, (semantic, styles) in REQUIRED.items():
        for style in styles:
            geometry_by_size = []
            for size in SIZES:
                root = ET.parse(
                    ASSET_ROOT / f"ui_{semantic}_{size}_{style}.svg"
                ).getroot()
                geometry_by_size.append(
                    tuple(
                        element.attrib["d"]
                        for element in root.iter(f"{SVG_NAMESPACE}path")
                    )
                )
            assert len(set(geometry_by_size)) == len(SIZES), semantic


def test_evidence_is_reproducible_parseable_and_truthfully_bounded() -> None:
    checksums = _load_checksums(EVIDENCE_ROOT / "SHA256SUMS")
    assert set(checksums) == {"contact-sheet.svg", "scaling-matrix.svg"}
    for relative, expected in checksums.items():
        path = EVIDENCE_ROOT / relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        root = ET.parse(path).getroot()
        assert root.tag == f"{SVG_NAMESPACE}svg"

    readme = (EVIDENCE_ROOT / "README.md").read_text(encoding="utf-8")
    for size in SIZES:
        assert str(size) in readme
    for scale in ("100%", "125%", "150%", "200%"):
        assert scale in readme
    assert "do **not** prove native" in readme
    assert "Issue #82" in readme


def test_package_data_and_runtime_dependencies_preserve_boundary() -> None:
    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pragma: no cover - Python 3.10 CI path
        import pip._vendor.tomli as tomllib  # type: ignore[no-redef]

    project = tomllib.loads(
        (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    dependency_names = {
        re.split(r"[<>=!~ ;\[]", dependency, maxsplit=1)[0].lower()
        for dependency in project["project"]["dependencies"]
    }
    assert dependency_names.isdisjoint(
        {"pyside6", "pyqt6", "pyqt5", "pyside2", "react", "tailwind"}
    )
    package_data = project["tool"]["setuptools"]["package-data"]["woff"]
    assert "assets/ui/icons/*.svg" in package_data
    assert "assets/ui/icons/*.json" in package_data
    assert "assets/ui/icons/SHA256SUMS" in package_data
    assert "assets/ui/icons/LICENSES/*.txt" in package_data
