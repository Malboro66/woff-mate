from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = REPOSITORY_ROOT / "woff" / "assets" / "ui" / "branding"
EVIDENCE_ROOT = (
    REPOSITORY_ROOT / "docs" / "ui" / "evidence" / "ui-v2-branding-2026-09-24"
)
BRAND_GUIDE = REPOSITORY_ROOT / "docs" / "ui" / "woff-mate-branding.md"
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"
ICO_SIZES = (16, 24, 32, 48, 256)
REVIEW_SIZES = (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256)
SVG_ASSETS = {
    "woff_mate_wordmark_dark.svg",
    "woff_mate_wordmark_light.svg",
    "woff_mate_wordmark_v2.svg",
    "woff_mate_symbol_dark.svg",
    "woff_mate_symbol_light.svg",
    "woff_mate_symbol_v2.svg",
    "woff_mate_app_icon_master.svg",
    "woff_mate_app_icon_small.svg",
}
GENERATED_ASSETS = SVG_ASSETS | {"woff_mate_app.ico"}


def _manifest() -> dict[str, object]:
    loaded = json.loads((ASSET_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _checksums(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        assert relative not in parsed
        parsed[relative] = digest
    return parsed


def _png_info(payload: bytes) -> tuple[int, int, int, int, list[str], bytes]:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    width = height = bit_depth = color_type = 0
    chunks: list[str] = []
    compressed = bytearray()
    while offset < len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        kind = payload[offset + 4 : offset + 8].decode("ascii")
        data = payload[offset + 8 : offset + 8 + length]
        chunks.append(kind)
        if kind == "IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(
                ">IIBBBBB", data
            )
        if kind == "IDAT":
            compressed.extend(data)
        offset += 12 + length
    assert offset == len(payload)
    return width, height, bit_depth, color_type, chunks, zlib.decompress(compressed)


def _ico_entries(path: Path) -> dict[int, bytes]:
    payload = path.read_bytes()
    reserved, image_type, count = struct.unpack("<HHH", payload[:6])
    assert (reserved, image_type, count) == (0, 1, len(ICO_SIZES))
    entries: dict[int, bytes] = {}
    for index in range(count):
        cursor = 6 + index * 16
        width_byte, height_byte, colors, reserved_byte, planes, bits, size, offset = (
            struct.unpack("<BBBBHHII", payload[cursor : cursor + 16])
        )
        width = width_byte or 256
        height = height_byte or 256
        assert width == height
        assert colors == reserved_byte == 0
        assert (planes, bits) == (1, 32)
        assert width not in entries
        entries[width] = payload[offset : offset + size]
    return entries


def test_q0_identity_decision_is_bounded_and_recorded() -> None:
    manifest = _manifest()
    q0 = manifest["q0"]
    assert isinstance(q0, dict)
    assert q0["selected_direction"] == "plot-and-ledger monogram"
    considered = q0["considered_directions"]
    assert isinstance(considered, list)
    assert len(considered) == 3
    assert sum(direction["selected"] is True for direction in considered) == 1
    for field in (
        "core_identity_concept",
        "primary_visual_metaphor",
        "wordmark_symbol_relationship",
        "operations_room_1917_relationship",
        "monochrome_rationale",
        "similarity_avoidance",
        "small_size_simplification",
    ):
        assert q0[field]

    guide = BRAND_GUIDE.read_text(encoding="utf-8")
    guide_flat = re.sub(r"\s+", " ", guide)
    assert "## Q0 identity decision" in guide
    assert "## Similarity review" in guide
    assert "not legal trademark clearance" in guide_flat.lower()
    for reviewed in (
        "wings over flanders fields / off",
        "rise of flight",
        "flying circus",
        "pilot-wing and military-badge silhouettes",
        "legacy root `icon.png`",
    ):
        assert reviewed in guide_flat.lower()


def test_manifest_paths_ids_and_provenance_are_complete() -> None:
    manifest = _manifest()
    assert manifest["schema_version"] == 1
    assert manifest["package_id"] == "woff-mate-product-identity"
    assets = manifest["assets"]
    assert isinstance(assets, list)
    ids = [str(asset["id"]) for asset in assets]
    paths = [str(asset["path"]) for asset in assets]
    assert len(ids) == len(set(ids))
    assert len(paths) == len(set(paths))
    assert set(paths) == GENERATED_ASSETS
    for asset in assets:
        assert (ASSET_ROOT / str(asset["path"])).is_file()
        assert asset["purpose"]
        assert asset["canonical_source_type"]
        assert asset["status"] == "original/custom"
        assert asset["license"] == "MIT (repository license)"
        assert asset["attribution_required"] is False
        assert asset["notices_required"] is False
        assert asset["approved_variants"]
        assert asset["approved_uses"]
        assert asset["minimum_size"]
        assert asset["clear_space_or_safe_area"]
        assert asset["prohibited_uses"]

    typography = manifest["typography_provenance"]
    assert typography == {
        "strategy": "original custom vector lettering",
        "font_family": None,
        "font_file_required": False,
        "text_elements_in_canonical_svg": False,
        "license": "MIT (repository license)",
        "attribution_required": False,
    }


def test_canonical_svgs_are_self_contained_vector_geometry() -> None:
    forbidden_elements = {"image", "text", "script", "style", "foreignObject", "use"}
    forbidden_terms = (
        "font-family",
        "pyside",
        "pyqt",
        "react",
        "tailwind",
        "c:\\users\\",
        "/home/",
    )
    actual = {path.name for path in ASSET_ROOT.glob("*.svg")}
    assert actual == SVG_ASSETS
    for path in sorted(ASSET_ROOT.glob("*.svg")):
        root = ET.parse(path).getroot()
        assert root.tag == f"{SVG_NAMESPACE}svg"
        assert "viewBox" in root.attrib
        payload = path.read_text(encoding="utf-8")
        assert all(term not in payload.lower() for term in forbidden_terms)
        for element in root.iter():
            assert element.tag.rsplit("}", 1)[-1] not in forbidden_elements
            assert not any(attribute.endswith("href") for attribute in element.attrib)

    assert ET.parse(ASSET_ROOT / "woff_mate_wordmark_dark.svg").getroot().attrib[
        "viewBox"
    ] == "0 0 768 192"
    assert ET.parse(ASSET_ROOT / "woff_mate_symbol_dark.svg").getroot().attrib[
        "viewBox"
    ] == "0 0 256 256"
    assert ET.parse(ASSET_ROOT / "woff_mate_app_icon_master.svg").getroot().attrib[
        "viewBox"
    ] == "0 0 1024 1024"


def test_monochrome_and_v2_variants_are_complete_and_restrained() -> None:
    dark = (ASSET_ROOT / "woff_mate_wordmark_dark.svg").read_text(encoding="utf-8")
    light = (ASSET_ROOT / "woff_mate_wordmark_light.svg").read_text(encoding="utf-8")
    assert "#201D18" in dark
    assert "#F4EFE2" not in dark
    assert "#F4EFE2" in light
    assert "#201D18" not in light

    allowed_color_values = {"#111614", "#18231F", "#C2A86B", "#F4EFE2"}
    for name in (
        "woff_mate_wordmark_v2.svg",
        "woff_mate_symbol_v2.svg",
        "woff_mate_app_icon_master.svg",
        "woff_mate_app_icon_small.svg",
    ):
        payload = (ASSET_ROOT / name).read_text(encoding="utf-8")
        colors = set(re.findall(r"#[0-9A-Fa-f]{6}", payload))
        assert colors <= allowed_color_values
        assert "gradient" not in payload.lower()
        assert "filter" not in payload.lower()


def test_windows_icon_has_exact_required_entries_and_clean_alpha() -> None:
    entries = _ico_entries(ASSET_ROOT / "woff_mate_app.ico")
    assert tuple(sorted(entries)) == ICO_SIZES
    for size, png in entries.items():
        width, height, bit_depth, color_type, chunks, decoded = _png_info(png)
        assert (width, height) == (size, size)
        assert (bit_depth, color_type) == (8, 6)
        assert chunks[0] == "IHDR" and chunks[-1] == "IEND"
        assert not ({"tEXt", "zTXt", "iTXt", "tIME", "eXIf", "iCCP"} & set(chunks))
        stride = size * 4
        assert len(decoded) == size * (stride + 1)
        assert decoded[0] == 0
        top_left_alpha = decoded[1 + 3]
        center_row = size // 2
        center_column = size // 2
        center_offset = center_row * (stride + 1) + 1 + center_column * 4 + 3
        assert top_left_alpha == 0
        assert decoded[center_offset] == 255


def test_small_optical_master_is_distinct_and_usage_is_pinned() -> None:
    large = ET.parse(ASSET_ROOT / "woff_mate_app_icon_master.svg").getroot()
    small = ET.parse(ASSET_ROOT / "woff_mate_app_icon_small.svg").getroot()
    large_paths = [element.attrib.get("d") for element in large.iter() if "d" in element.attrib]
    small_paths = [element.attrib.get("d") for element in small.iter() if "d" in element.attrib]
    assert large_paths != small_paths

    windows_icon = _manifest()["windows_icon"]
    assert isinstance(windows_icon, dict)
    assert windows_icon["canonical_master"] == "woff_mate_app_icon_master.svg"
    assert windows_icon["optical_variants"] == [
        {
            "path": "woff_mate_app_icon_small.svg",
            "targets": [16, 20, 24, 30, 32, 36, 40],
            "reason": "wider strokes, larger counters, and no inset border",
        }
    ]
    assert windows_icon["embedded_ico_sizes"] == list(ICO_SIZES)
    assert windows_icon["reviewed_windows_target_sizes"] == list(REVIEW_SIZES)
    assert windows_icon["ico_source_map"] == {
        "16": "small",
        "24": "small",
        "32": "small",
        "48": "master",
        "256": "master",
    }


def test_usage_geometry_and_future_packaging_boundary_are_documented() -> None:
    manifest = _manifest()
    usage = manifest["usage"]
    assert isinstance(usage, dict)
    assert usage["wordmark_viewbox"] == "0 0 768 192"
    assert usage["symbol_viewbox"] == "0 0 256 256"
    assert usage["wordmark_clear_space"] == "one symbol divider width (16/256 symbol units)"
    assert usage["symbol_clear_space"] == "32/256 symbol units on every side"
    assert usage["wordmark_minimum_width_px"] == 160
    assert usage["symbol_minimum_size_px"] == 24
    assert usage["app_icon_safe_area"] == "critical WM geometry stays within the central 75%"

    guide = BRAND_GUIDE.read_text(encoding="utf-8")
    guide_flat = re.sub(r"\s+", " ", guide)
    for phrase in (
        "Do not stretch, condense, skew, rotate, outline, shadow, or rearrange",
        "Future Issue #82 consumption",
        "actual PyInstaller bundle consumption remains deferred",
        "native Windows shortcut, taskbar, and window-icon behavior remains deferred",
    ):
        assert phrase in guide_flat
    assert "build.spec" not in " ".join(str(path) for path in ASSET_ROOT.iterdir())
    build_spec = (REPOSITORY_ROOT / "build.spec").read_text(encoding="utf-8")
    assert "woff_mate_app.ico" not in build_spec


def test_package_and_evidence_checksums_cover_deliverables() -> None:
    package_checksums = _checksums(ASSET_ROOT / "SHA256SUMS")
    assert set(package_checksums) == GENERATED_ASSETS | {"README.md", "manifest.json"}
    for relative, expected in package_checksums.items():
        assert hashlib.sha256((ASSET_ROOT / relative).read_bytes()).hexdigest() == expected

    evidence_checksums = _checksums(EVIDENCE_ROOT / "SHA256SUMS")
    assert set(evidence_checksums) == {"brand-review.png", "windows-icon-review.png"}
    for relative, expected in evidence_checksums.items():
        path = EVIDENCE_ROOT / relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        width, height, bit_depth, color_type, chunks, _ = _png_info(path.read_bytes())
        assert width >= 1400 and height >= 900
        assert (bit_depth, color_type) == (8, 6)
        assert not ({"tEXt", "zTXt", "iTXt", "tIME", "eXIf", "iCCP"} & set(chunks))

    evidence_readme = (EVIDENCE_ROOT / "README.md").read_text(encoding="utf-8")
    for size in REVIEW_SIZES:
        assert str(size) in evidence_readme
    for context in ("shortcut", "taskbar", "window/app-icon"):
        assert context in evidence_readme.lower()
    assert "static evidence" in evidence_readme.lower()
    assert "Issue #82" in evidence_readme


def test_generation_is_deterministic_and_stdlib_only(tmp_path: Path) -> None:
    script = REPOSITORY_ROOT / "scripts" / "generate_branding_assets.py"
    subprocess.run(
        [sys.executable, "-I", "-S", str(script), "--output-root", str(tmp_path)],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    generated_asset_root = tmp_path / "woff" / "assets" / "ui" / "branding"
    generated_evidence_root = (
        tmp_path / "docs" / "ui" / "evidence" / "ui-v2-branding-2026-09-24"
    )
    for relative in GENERATED_ASSETS:
        assert (generated_asset_root / relative).read_bytes() == (ASSET_ROOT / relative).read_bytes()
    for relative in ("brand-review.png", "windows-icon-review.png"):
        assert (generated_evidence_root / relative).read_bytes() == (EVIDENCE_ROOT / relative).read_bytes()

    source = script.read_text(encoding="utf-8").lower()
    for forbidden in ("pillow", "cairosvg", "inkscape", "imagemagick", "openai", "requests"):
        assert forbidden not in source


def test_runtime_and_scope_boundaries_remain_intact() -> None:
    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pragma: no cover - Python 3.10 CI path
        import pip._vendor.tomli as tomllib  # type: ignore[no-redef]

    project = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependency_names = {
        re.split(r"[<>=!~ ;\[]", dependency, maxsplit=1)[0].lower()
        for dependency in project["project"]["dependencies"]
    }
    assert dependency_names.isdisjoint(
        {
            "pyside6",
            "pyqt6",
            "pyqt5",
            "pyside2",
            "pillow",
            "cairosvg",
            "openai",
            "react",
            "tailwind",
        }
    )
    package_data = " ".join(project["tool"]["setuptools"]["package-data"]["woff"])
    assert "assets/ui/branding" not in package_data
    assert "woff_mate_app.ico" not in (REPOSITORY_ROOT / "build.spec").read_text(
        encoding="utf-8"
    )
    graph = (REPOSITORY_ROOT / "docs" / "architecture" / "project-graph.yaml").read_text(
        encoding="utf-8"
    )
    assert "- scripts/generate_branding_assets.py" in graph
    assert "issue-132:" not in graph

    tracked_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (ASSET_ROOT / "README.md", ASSET_ROOT / "manifest.json", BRAND_GUIDE)
    ).lower()
    for prohibited in (
        "pilot face",
        "pilot nationality",
        "squadron badge",
        "rank insignia",
        "national roundel",
    ):
        assert prohibited in tracked_text
