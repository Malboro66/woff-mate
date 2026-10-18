from __future__ import annotations

import hashlib
import os
import runpy
import json
import math
from unittest import mock
import re
import shutil
import struct
import subprocess
import sys
import zlib

import pytest
from scripts import generate_branding_assets as branding_generator
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

# Approved original inventories; independent of mutable checksum files.
APPROVED_ASSET_SUMS_SHA256 = "4dad33e6083dbd3cc685cc60627908018b8ca8b2f60a05f71a70ae536d86c99d"
APPROVED_EVIDENCE_SUMS_SHA256 = "a92a0c3761ec76458f8a3062a11ef3be0db1e7cc95ea9882802c9c4d072c83f6"
GENERATOR_INPUTS = SVG_ASSETS | {"README.md", "manifest.json"}


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


def _rgba_rows(payload: bytes) -> list[list[tuple[int, int, int, int]]]:
    width, height, bit_depth, color_type, _, decoded = _png_info(payload)
    assert (bit_depth, color_type) == (8, 6)
    stride = width * 4
    rows: list[list[tuple[int, int, int, int]]] = []
    cursor = 0
    for _ in range(height):
        assert decoded[cursor] == 0
        scanline = decoded[cursor + 1 : cursor + 1 + stride]
        rows.append(
            [
                (
                    scanline[offset],
                    scanline[offset + 1],
                    scanline[offset + 2],
                    scanline[offset + 3],
                )
                for offset in range(0, stride, 4)
            ]
        )
        cursor += stride + 1
    assert cursor == len(decoded)
    return rows


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


def _prepare_generator_root(root: Path) -> Path:
    target = root / "woff" / "assets" / "ui" / "branding"
    target.mkdir(parents=True)
    for relative in GENERATOR_INPUTS:
        shutil.copyfile(ASSET_ROOT / relative, target / relative)
    return target


def _run_generator(root: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(REPOSITORY_ROOT / "scripts" / "generate_branding_assets.py"),
            "--output-root",
            str(root),
        ],
        cwd=REPOSITORY_ROOT,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


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

    relationship = str(q0["wordmark_symbol_relationship"]).lower()
    assert "terminal register square belongs only to the wordmark" in relationship
    assert "terminal register square used by the compact symbol" not in relationship

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
    source = manifest["source"]
    assert isinstance(source, dict)
    assert source["authority"] == (
        "the eight committed SVG files are the authoritative editable artwork"
    )
    assert source["edit_workflow"] == (
        "edit canonical SVGs directly; run the generator only to validate them and "
        "refresh derivatives"
    )
    assert source["generator_behavior"] == (
        "consumes canonical SVG geometry without rewriting SVG files; writes ICO, "
        "review PNGs, and checksum inventories"
    )
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

    symbol_dark = ET.parse(ASSET_ROOT / "woff_mate_symbol_dark.svg").getroot()
    symbol_light = ET.parse(ASSET_ROOT / "woff_mate_symbol_light.svg").getroot()
    symbol_v2 = ET.parse(ASSET_ROOT / "woff_mate_symbol_v2.svg").getroot()
    assert not list(symbol_dark.iter(f"{SVG_NAMESPACE}rect"))
    assert not list(symbol_light.iter(f"{SVG_NAMESPACE}rect"))
    v2_rects = list(symbol_v2.iter(f"{SVG_NAMESPACE}rect"))
    assert [rect.attrib for rect in v2_rects] == [
        {
            "x": "128",
            "y": "82",
            "width": "8",
            "height": "92",
            "rx": "4",
            "fill": "#C2A86B",
        }
    ]

    guide = BRAND_GUIDE.read_text(encoding="utf-8").lower()
    package_readme = (ASSET_ROOT / "README.md").read_text(encoding="utf-8").lower()
    for contract in (guide, package_readme):
        assert "terminal square" in contract
        assert "wordmark" in contract
        assert "terminal square connect the compact monogram" not in contract


def test_brand_evidence_separates_limited_color_from_true_monochrome() -> None:
    rows = _rgba_rows((EVIDENCE_ROOT / "brand-review.png").read_bytes())
    brass = (194, 168, 107, 255)
    on_dark = (244, 239, 226, 255)

    limited_color = {
        rows[y][x] for y in range(205, 385) for x in range(74, 794)
    }
    monochrome = {
        rows[y][x] for y in range(194, 374) for x in range(1100, 1280)
    }
    assert brass in limited_color
    assert on_dark in monochrome
    assert brass not in monochrome


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

        rows = _rgba_rows(png)
        partially_transparent = [
            pixel for row in rows for pixel in row if 0 < pixel[3] < 255
        ]
        assert partially_transparent
        expected_edge_rgb = (24, 35, 31) if size <= 32 else (194, 168, 107)
        assert {pixel[:3] for pixel in partially_transparent} == {expected_edge_rgb}


def test_app_icon_svg_geometry_matches_raster_safe_area_contract() -> None:
    manifest = _manifest()
    windows_icon = manifest["windows_icon"]
    assert isinstance(windows_icon, dict)

    master = ET.parse(ASSET_ROOT / "woff_mate_app_icon_master.svg").getroot()
    master_rects = list(master.iter(f"{SVG_NAMESPACE}rect"))
    assert [
        {
            key: rect.attrib[key]
            for key in ("x", "y", "width", "height", "rx", "fill")
        }
        for rect in master_rects[:2]
    ] == [
        {
            "x": "72",
            "y": "72",
            "width": "880",
            "height": "880",
            "rx": "150",
            "fill": "#C2A86B",
        },
        {
            "x": "96",
            "y": "96",
            "width": "832",
            "height": "832",
            "rx": "126",
            "fill": "#18231F",
        },
    ]
    assert all("stroke" not in rect.attrib for rect in master_rects[:2])
    assert {
        key: master_rects[2].attrib[key]
        for key in ("x", "y", "width", "height", "rx", "fill")
    } == {
        "x": "503",
        "y": "350",
        "width": "18",
        "height": "324",
        "rx": "9",
        "fill": "#C2A86B",
    }
    assert 2 * float(master_rects[2].attrib["rx"]) == float(
        master_rects[2].attrib["width"]
    )
    assert windows_icon["master_tile_geometry"] == {
        "outer_bounds": [72, 72, 952, 952],
        "outer_corner_radius": 150,
        "inner_bounds": [96, 96, 928, 928],
        "inner_corner_radius": 126,
        "construction": (
            "nested filled rounded rectangles consumed directly from the canonical SVG"
        ),
    }

    small = ET.parse(ASSET_ROOT / "woff_mate_app_icon_small.svg").getroot()
    small_tile = next(small.iter(f"{SVG_NAMESPACE}rect"))
    assert {
        key: small_tile.attrib[key]
        for key in ("x", "y", "width", "height", "rx", "fill")
    } == {
        "x": "64",
        "y": "64",
        "width": "896",
        "height": "896",
        "rx": "172",
        "fill": "#18231F",
    }
    small_rects = list(small.iter(f"{SVG_NAMESPACE}rect"))
    assert {
        key: small_rects[1].attrib[key]
        for key in ("x", "y", "width", "height", "rx", "fill")
    } == {
        "x": "499",
        "y": "350",
        "width": "26",
        "height": "324",
        "rx": "13",
        "fill": "#C2A86B",
    }
    assert 2 * float(small_rects[1].attrib["rx"]) == float(
        small_rects[1].attrib["width"]
    )
    assert windows_icon["small_tile_geometry"] == {
        "outer_bounds": [64, 64, 960, 960],
        "outer_corner_radius": 172,
        "construction": (
            "single filled rounded rectangle consumed directly from the optical SVG"
        ),
    }

    for element in list(master.iter(f"{SVG_NAMESPACE}path")) + master_rects[2:]:
        if element.tag.endswith("path"):
            coordinates = [
                float(value)
                for value in re.findall(r"\d+(?:\.\d+)?", element.attrib["d"])
            ]
            xs, ys = coordinates[::2], coordinates[1::2]
            radius = float(element.attrib["stroke-width"]) / 2
            bounds = (
                min(xs) - radius,
                min(ys) - radius,
                max(xs) + radius,
                max(ys) + radius,
            )
        else:
            left = float(element.attrib["x"])
            top = float(element.attrib["y"])
            bounds = (
                left,
                top,
                left + float(element.attrib["width"]),
                top + float(element.attrib["height"]),
            )
        assert bounds[0] >= 128 and bounds[1] >= 128
        assert bounds[2] <= 896 and bounds[3] <= 896


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
    _assert_approved_inventory_digests()
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


def _canonical_branding_toolchain() -> bool:
    return branding_generator._is_canonical_toolchain()


def _assert_approved_inventory_digests(
    asset_root: Path = ASSET_ROOT, evidence_root: Path = EVIDENCE_ROOT
) -> None:
    assert hashlib.sha256((asset_root / "SHA256SUMS").read_bytes()).hexdigest() == (
        APPROVED_ASSET_SUMS_SHA256
    )
    assert hashlib.sha256((evidence_root / "SHA256SUMS").read_bytes()).hexdigest() == (
        APPROVED_EVIDENCE_SUMS_SHA256
    )


def _verified_png_content(payload: bytes) -> tuple[tuple[bytes, ...], bytes]:
    """Require valid PNG chunks/CRCs and return non-IDAT data and scanlines."""
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    non_idat = []
    compressed = bytearray()
    kinds = []
    offset = 8
    while offset < len(payload):
        assert offset + 12 <= len(payload)
        size = struct.unpack(">I", payload[offset : offset + 4])[0]
        assert offset + 12 + size <= len(payload)
        kind = payload[offset + 4 : offset + 8]
        data = payload[offset + 8 : offset + 8 + size]
        crc = struct.unpack(">I", payload[offset + 8 + size : offset + 12 + size])[0]
        assert zlib.crc32(kind + data) & 0xFFFFFFFF == crc
        kinds.append(kind)
        if kind == b"IDAT":
            compressed.extend(data)
        else:
            non_idat.append(kind + data)
        offset += 12 + size
    assert offset == len(payload)
    assert kinds == [b"IHDR", b"IDAT", b"IEND"]
    width, height, depth, color, _, _ = _png_info(payload)
    assert (depth, color) == (8, 6)
    inflater = zlib.decompressobj()
    raw = inflater.decompress(bytes(compressed)) + inflater.flush()
    assert inflater.eof, "incomplete zlib stream"
    assert not inflater.unused_data, "extra bytes after zlib stream"
    assert not inflater.unconsumed_tail, "unconsumed compressed data"
    assert len(raw) == height * (1 + 4 * width)
    for row in range(height):
        assert raw[row * (1 + 4 * width)] == 0
    return tuple(non_idat), raw


def _assert_png_equivalence(canonical: bytes, generated: bytes) -> None:
    assert _verified_png_content(generated) == _verified_png_content(canonical)


def _assert_inventory(root: Path, names: set[str]) -> None:
    entries = _checksums(root / "SHA256SUMS")
    assert set(entries) == names
    for name, digest in entries.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest


def test_generation_is_deterministic_and_stdlib_only(tmp_path: Path) -> None:
    script = REPOSITORY_ROOT / "scripts" / "generate_branding_assets.py"
    generated_asset_root = _prepare_generator_root(tmp_path)
    canonical_before = {
        relative: (generated_asset_root / relative).read_bytes()
        for relative in SVG_ASSETS
    }
    result = _run_generator(tmp_path)
    generated_evidence_root = (
        tmp_path / "docs" / "ui" / "evidence" / "ui-v2-branding-2026-09-24"
    )
    assert {
        relative: (generated_asset_root / relative).read_bytes()
        for relative in SVG_ASSETS
    } == canonical_before

    # Never downgrade the original canonical bytes or checked-in SHA-256
    # inventories when running on a different Python/zlib toolchain.
    assets = GENERATED_ASSETS | {"README.md", "manifest.json"}
    evidence = {"brand-review.png", "windows-icon-review.png"}
    _assert_approved_inventory_digests()
    _assert_inventory(ASSET_ROOT, assets)
    _assert_inventory(EVIDENCE_ROOT, evidence)
    _assert_inventory(generated_asset_root, assets)
    _assert_inventory(generated_evidence_root, evidence)

    canonical_ico = (ASSET_ROOT / "woff_mate_app.ico").read_bytes()
    generated_ico = (generated_asset_root / "woff_mate_app.ico").read_bytes()
    original_entries = _ico_entries(ASSET_ROOT / "woff_mate_app.ico")
    new_entries = _ico_entries(generated_asset_root / "woff_mate_app.ico")
    assert set(original_entries) == set(new_entries) == set(ICO_SIZES)
    for size in ICO_SIZES:
        _assert_png_equivalence(original_entries[size], new_entries[size])
    for relative in ("brand-review.png", "windows-icon-review.png"):
        _assert_png_equivalence(
            (EVIDENCE_ROOT / relative).read_bytes(),
            (generated_evidence_root / relative).read_bytes(),
        )

    if _canonical_branding_toolchain():
        assert "NONCANONICAL BRANDING OUTPUT" not in result.stderr
        assert canonical_ico == generated_ico
        assert (generated_asset_root / "SHA256SUMS").read_bytes() == (
            ASSET_ROOT / "SHA256SUMS"
        ).read_bytes()
        for relative in ("brand-review.png", "windows-icon-review.png", "SHA256SUMS"):
            assert (generated_evidence_root / relative).read_bytes() == (
                EVIDENCE_ROOT / relative
            ).read_bytes()
    else:
        # Output may be pixel-identical yet not a canonical binary build.
        assert "NONCANONICAL BRANDING OUTPUT" in result.stderr

    source = script.read_text(encoding="utf-8").lower()
    for forbidden in ("pillow", "cairosvg", "inkscape", "imagemagick", "openai", "requests"):
        assert forbidden not in source


def _isolated_generator(tmp_path: Path):
    """Load a separate disposable generator with a forced noncanonical host."""
    import importlib.util

    fake_repo = tmp_path / "isolated-repository"
    fake_script = fake_repo / "scripts" / "generate_branding_assets.py"
    fake_script.parent.mkdir(parents=True)
    shutil.copyfile(REPOSITORY_ROOT / "scripts" / "generate_branding_assets.py", fake_script)
    fake_assets = fake_repo / "woff" / "assets" / "ui" / "branding"
    fake_assets.mkdir(parents=True)
    sample = fake_assets / "woff_mate_wordmark_dark.svg"
    shutil.copyfile(ASSET_ROOT / sample.name, sample)
    spec = importlib.util.spec_from_file_location("_woff194_isolated_generator", fake_script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {spec.name: module}):
        spec.loader.exec_module(module)
    return fake_repo, fake_script, fake_assets, module


def _assert_noncanonical_refusal(module, script: Path, root: Path) -> None:
    import contextlib
    import io

    error_stream = io.StringIO()
    with (
        mock.patch.object(module, "_is_canonical_toolchain", return_value=False),
        mock.patch.object(sys, "argv", [str(script), "--output-root", str(root)]),
        contextlib.redirect_stderr(error_stream),
        pytest.raises(SystemExit) as failure,
    ):
        module.main()
    assert failure.value.code == 2
    assert "noncanonical branding toolchain" in error_stream.getvalue()


def test_noncanonical_default_root_fails_closed_without_asset_write(
    tmp_path: Path,
) -> None:
    fake_repo, script, assets, module = _isolated_generator(tmp_path)
    _assert_noncanonical_refusal(module, script, fake_repo)
    assert not (assets / "woff_mate_app.ico").exists()


def _make_directory_alias(link: Path, target: Path) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True, capture_output=True, text=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


def test_noncanonical_nested_directory_aliases_are_rejected(tmp_path: Path) -> None:
    fake_repo, script, assets, module = _isolated_generator(tmp_path)
    (fake_repo / "docs").mkdir()
    diagnostics = tmp_path / "separate-diagnostics"
    diagnostics.mkdir()
    _make_directory_alias(diagnostics / "woff", fake_repo / "woff")
    _make_directory_alias(diagnostics / "docs", fake_repo / "docs")
    _assert_noncanonical_refusal(module, script, diagnostics)
    assert not (assets / "woff_mate_app.ico").exists()


def test_noncanonical_hardlinked_output_is_rejected(tmp_path: Path) -> None:
    fake_repo, script, assets, module = _isolated_generator(tmp_path)
    output_dir = tmp_path / "separate-diagnostics" / "woff" / "assets" / "ui" / "branding"
    output_dir.mkdir(parents=True)
    official_ico = assets / "woff_mate_app.ico"
    official_ico.write_bytes(b"disposable canary")
    os.link(official_ico, output_dir / "woff_mate_app.ico")
    _assert_noncanonical_refusal(module, script, output_dir.parents[3])
    assert official_ico.read_bytes() == b"disposable canary"


def test_approved_digest_pins_reject_replaced_self_consistent_inventory(
    tmp_path: Path,
) -> None:
    assets = tmp_path / "assets"
    evidence = tmp_path / "evidence"
    shutil.copytree(ASSET_ROOT, assets)
    shutil.copytree(EVIDENCE_ROOT, evidence)
    _assert_approved_inventory_digests(assets, evidence)
    ico = assets / "woff_mate_app.ico"
    ico.write_bytes(b"noncanonical counterfeit")
    sums = assets / "SHA256SUMS"
    old_digest = _checksums(sums)["woff_mate_app.ico"]
    sums.write_text(
        sums.read_text(encoding="ascii").replace(
            old_digest, hashlib.sha256(ico.read_bytes()).hexdigest()
        ), encoding="ascii",
    )
    _assert_inventory(assets, GENERATED_ASSETS | {"README.md", "manifest.json"})
    with pytest.raises(AssertionError):
        _assert_approved_inventory_digests(assets, evidence)


def test_png_rejects_trailing_data_after_valid_zlib_stream() -> None:
    canonical = (EVIDENCE_ROOT / "brand-review.png").read_bytes()
    chunks = []
    cursor = 8
    while cursor < len(canonical):
        length = struct.unpack(">I", canonical[cursor : cursor + 4])[0]
        kind = canonical[cursor + 4 : cursor + 8]
        data = canonical[cursor + 8 : cursor + 8 + length]
        if kind == b"IDAT":
            data += b"trailing bytes"
        chunks.append(
            struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )
        cursor += length + 12
    tampered = canonical[:8] + b"".join(chunks)
    with pytest.raises(AssertionError, match="extra bytes after zlib stream"):
        _assert_png_equivalence(canonical, tampered)


def test_exact_final_cpython_release_requirement() -> None:
    from collections import namedtuple

    info = namedtuple("Version", "major minor micro releaselevel serial")
    canonical = info(3, 10, 11, "final", 0)
    with (
        mock.patch.object(branding_generator.sys, "platform", "win32"),
        mock.patch.object(branding_generator.sys, "version_info", canonical),
        mock.patch.object(branding_generator.zlib, "ZLIB_VERSION", "1.2.13"),
        mock.patch.object(branding_generator.zlib, "ZLIB_RUNTIME_VERSION", "1.2.13"),
    ):
        assert branding_generator._is_canonical_toolchain() is True
        with mock.patch.object(
            branding_generator.sys, "version_info", info(3, 10, 11, "candidate", 1)
        ):
            assert branding_generator._is_canonical_toolchain() is False


def test_canonical_svg_edits_drive_derivatives_and_keep_rounded_dividers(
    tmp_path: Path,
) -> None:
    generated_asset_root = _prepare_generator_root(tmp_path)
    replacements = {
        "woff_mate_app_icon_master.svg": (
            '<rect x="503" y="350" width="18" height="324" rx="9" fill="#C2A86B"/>',
            '<rect x="448" y="350" width="128" height="324" rx="64" fill="#C2A86B"/>',
        ),
        "woff_mate_app_icon_small.svg": (
            '<rect x="499" y="350" width="26" height="324" rx="13" fill="#C2A86B"/>',
            '<rect x="448" y="350" width="128" height="324" rx="64" fill="#C2A86B"/>',
        ),
    }
    for relative, (before, after) in replacements.items():
        path = generated_asset_root / relative
        payload = path.read_text(encoding="utf-8")
        assert payload.count(before) == 1
        path.write_text(payload.replace(before, after), encoding="utf-8", newline="\n")

    canonical_before = {
        relative: (generated_asset_root / relative).read_bytes()
        for relative in SVG_ASSETS
    }
    _run_generator(tmp_path)
    assert {
        relative: (generated_asset_root / relative).read_bytes()
        for relative in SVG_ASSETS
    } == canonical_before

    changed_entries = _ico_entries(generated_asset_root / "woff_mate_app.ico")
    baseline_entries = _ico_entries(ASSET_ROOT / "woff_mate_app.ico")
    assert tuple(sorted(changed_entries)) == ICO_SIZES
    assert all(changed_entries[size] != baseline_entries[size] for size in ICO_SIZES)

    square_dividers = {
        "woff_mate_app_icon_master.svg": (
            '<rect x="448" y="350" width="128" height="324" rx="64" fill="#C2A86B"/>',
            '<rect x="503" y="350" width="18" height="324" rx="0" fill="#C2A86B"/>',
        ),
        "woff_mate_app_icon_small.svg": (
            '<rect x="448" y="350" width="128" height="324" rx="64" fill="#C2A86B"/>',
            '<rect x="499" y="350" width="26" height="324" rx="0" fill="#C2A86B"/>',
        ),
    }
    for relative, (before, after) in square_dividers.items():
        path = generated_asset_root / relative
        payload = path.read_text(encoding="utf-8")
        assert payload.count(before) == 1
        path.write_text(
            payload.replace(before, after),
            encoding="utf-8",
            newline="\n",
        )
    _run_generator(tmp_path)
    square_entries = _ico_entries(generated_asset_root / "woff_mate_app.ico")

    for size in (32, 48, 256):
        rounded_rows = _rgba_rows(baseline_entries[size])
        square_rows = _rgba_rows(square_entries[size])
        scale = size / 1024
        left_source, right_source, radius_source = (
            (499, 525, 13) if size == 32 else (503, 521, 9)
        )
        left = max(0, int(left_source * scale))
        right = min(size, math.ceil(right_source * scale))
        top = max(0, int(350 * scale))
        bottom = min(size, math.ceil(674 * scale))
        radius = max(1, math.ceil(radius_source * scale))
        assert any(
            rounded_rows[y][x] != square_rows[y][x]
            for y in range(top, min(bottom, top + radius + 1))
            for x in range(left, right)
        )
        assert any(
            rounded_rows[y][x] != square_rows[y][x]
            for y in range(max(top, bottom - radius - 1), bottom)
            for x in range(left, right)
        )
        middle = int(512 * scale)
        assert rounded_rows[middle] == square_rows[middle]


def test_generator_fails_closed_on_unsupported_canonical_svg(tmp_path: Path) -> None:
    generated_asset_root = _prepare_generator_root(tmp_path)
    symbol = generated_asset_root / "woff_mate_symbol_dark.svg"
    payload = symbol.read_text(encoding="utf-8")
    symbol.write_text(
        payload.replace(
            "</svg>", '  <circle cx="128" cy="128" r="12" fill="#201D18"/>\n</svg>'
        ),
        encoding="utf-8",
        newline="\n",
    )
    result = _run_generator(tmp_path, check=False)
    assert result.returncode != 0
    assert "unsupported SVG element" in result.stderr


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
