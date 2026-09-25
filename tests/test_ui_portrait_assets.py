from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = REPOSITORY_ROOT / "woff" / "assets" / "ui" / "portraits"
EVIDENCE_ROOT = (
    REPOSITORY_ROOT / "docs" / "ui" / "evidence" / "ui-v2-portraits-2026-09-24"
)
SOURCE_ORIGINAL = (
    EVIDENCE_ROOT / "source" / "ui_portrait_synthetic_aster_original.png"
)
FIXTURE_CATALOG = REPOSITORY_ROOT / "woff" / "tests" / "fixtures" / "ui_states" / "catalog.json"
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"


def _manifest() -> dict[str, object]:
    loaded = json.loads((ASSET_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _assets() -> list[dict[str, object]]:
    assets = _manifest()["assets"]
    assert isinstance(assets, list)
    assert all(isinstance(asset, dict) for asset in assets)
    return assets  # type: ignore[return-value]


def _checksums(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        assert relative not in parsed
        parsed[relative] = digest
    return parsed


def _png_chunks(path: Path) -> tuple[tuple[int, int, int, int, int], list[str]]:
    payload = path.read_bytes()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    ihdr: tuple[int, int, int, int, int] | None = None
    chunks: list[str] = []
    while offset < len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        kind = payload[offset + 4 : offset + 8].decode("ascii")
        data = payload[offset + 8 : offset + 8 + length]
        chunks.append(kind)
        if kind == "IHDR":
            ihdr = struct.unpack(">IIBBBBB", data)[:5]
        offset += 12 + length
    assert offset == len(payload)
    assert ihdr is not None
    return ihdr, chunks


def _png_chunk_payloads(path: Path) -> dict[str, list[bytes]]:
    payload = path.read_bytes()
    offset = 8
    chunks: dict[str, list[bytes]] = {}
    while offset < len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        kind = payload[offset + 4 : offset + 8].decode("ascii")
        chunks.setdefault(kind, []).append(payload[offset + 8 : offset + 8 + length])
        offset += 12 + length
    return chunks


def _png_rgb_rows(path: Path) -> tuple[bytes, ...]:
    payload = path.read_bytes()
    offset = 8
    width = height = 0
    compressed = bytearray()
    while offset < len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        kind = payload[offset + 4 : offset + 8]
        data = payload[offset + 8 : offset + 8 + length]
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            assert (bit_depth, color_type, interlace) == (8, 2, 0)
        elif kind == b"IDAT":
            compressed.extend(data)
        offset += 12 + length

    stride = width * 3
    decoded = zlib.decompress(compressed)
    assert len(decoded) == height * (stride + 1)
    rows: list[bytes] = []
    prior = bytearray(stride)
    cursor = 0
    for _ in range(height):
        filter_type = decoded[cursor]
        cursor += 1
        raw = decoded[cursor : cursor + stride]
        cursor += stride
        row = bytearray(stride)
        for index, value in enumerate(raw):
            left = row[index - 3] if index >= 3 else 0
            above = prior[index]
            upper_left = prior[index - 3] if index >= 3 else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            else:
                assert filter_type == 4
                candidate = left + above - upper_left
                distances = (
                    abs(candidate - left),
                    abs(candidate - above),
                    abs(candidate - upper_left),
                )
                predictor = (left, above, upper_left)[distances.index(min(distances))]
            row[index] = (value + predictor) & 0xFF
        rows.append(bytes(row))
        prior = row
    return tuple(rows)


def test_common_manifest_fields_follow_the_ui_asset_package_convention() -> None:
    manifest = _manifest()
    icon_manifest = json.loads(
        (REPOSITORY_ROOT / "woff" / "assets" / "ui" / "icons" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["schema_version"] == icon_manifest["schema_version"] == 1
    assert manifest["package_id"] == "woff-mate-ui-v2-portraits"
    assert manifest["package_id"] != icon_manifest["package_id"]
    assert "manifest_version" not in manifest
    for field in (
        "canonical_source_type",
        "source",
        "theme_contract",
        "shared_accessibility",
        "prohibited_domain_uses",
    ):
        assert manifest[field]
        assert icon_manifest[field]


def test_q0_consumers_and_minimum_inventory_are_pinned() -> None:
    manifest = _manifest()
    q0 = manifest["q0"]
    assert isinstance(q0, dict)
    assert q0["inventory_decision"] == "one synthetic exemplar plus one neutral fallback"
    consumers = q0["consumers"]
    assert isinstance(consumers, list)
    by_screen = {consumer["screen"]: consumer for consumer in consumers}
    assert set(by_screen) == {"DOS-01", "SQD-01", "SQD-02"}
    assert by_screen["DOS-01"]["approved_logical_slots"] == [[140, 176], [104, 135]]
    assert by_screen["SQD-01"]["approved_logical_slots"] == []
    assert by_screen["SQD-01"]["role"] == "no portrait consumer"
    assert by_screen["SQD-02"]["role"] == "fallback under current fixture contract"

    assets = _assets()
    assert len(assets) == 2
    assert {asset["id"] for asset in assets} == {"portrait.synthetic.aster", "portrait.unavailable"}
    assert sum(asset["synthetic"] is True for asset in assets) == 1


def test_manifest_paths_ids_and_provenance_are_complete() -> None:
    assets = _assets()
    ids = [str(asset["id"]) for asset in assets]
    paths = [str(asset["path"]) for asset in assets]
    assert len(ids) == len(set(ids))
    assert len(paths) == len(set(paths))
    for asset in assets:
        assert (ASSET_ROOT / str(asset["path"])).is_file()
        assert asset["source_type"]
        assert asset["generation_method"]
        assert asset["provenance"]
        assert asset["redistribution_status"]
        assert asset["license"] == "MIT (repository license)"
        assert asset["attribution_required"] is False
        assert asset["notices_required"] is False
        assert asset["accessibility"]
        prohibited = asset["prohibited_interpretations"]
        assert isinstance(prohibited, list)
        assert {"identity", "nationality", "service", "rank", "career status"} <= set(prohibited)

    generated = next(asset for asset in assets if asset["id"] == "portrait.synthetic.aster")
    assert generated["synthetic"] is True
    assert generated["third_party"] is False
    assert generated["canonical_dimensions"] == [1120, 1400]
    assert generated["source_dimensions"] == [1122, 1402]
    assert "no resampling or upscaling" in str(generated["processing"])


def test_canonical_png_is_valid_exact_4_by_5_and_metadata_clean() -> None:
    path = ASSET_ROOT / "ui_portrait_synthetic_aster_master.png"
    ihdr, chunks = _png_chunks(path)
    width, height, bit_depth, color_type, compression = ihdr
    assert (width, height) == (1120, 1400)
    assert width >= 800 and height >= 1000
    assert width * 5 == height * 4
    assert bit_depth == 8
    assert color_type == 2  # RGB; no hidden alpha payload
    assert compression == 0
    assert chunks[0] == "IHDR" and chunks[-1] == "IEND"
    assert not ({"tEXt", "zTXt", "iTXt", "tIME", "eXIf", "iCCP"} & set(chunks))


def test_exact_generated_source_is_retained_and_matches_the_canonical_crop() -> None:
    source = _manifest()["source"]
    assert isinstance(source, dict)
    assert source["id"] == "source.synthetic.aster.original"
    assert source["synthetic"] is True
    assert source["path"] == SOURCE_ORIGINAL.relative_to(REPOSITORY_ROOT).as_posix()
    assert source["dimensions"] == [1122, 1402]
    assert source["canonical_master_dimensions"] == [1120, 1400]
    assert hashlib.sha256(SOURCE_ORIGINAL.read_bytes()).hexdigest() == source["sha256"]

    canonical = ASSET_ROOT / "ui_portrait_synthetic_aster_master.png"
    assert hashlib.sha256(canonical.read_bytes()).hexdigest() == source["canonical_master_sha256"]
    source_ihdr, source_chunks = _png_chunks(SOURCE_ORIGINAL)
    assert source_ihdr[:3] == (1122, 1402, 8)
    assert source_ihdr[3] == 2
    assert not ({"tEXt", "zTXt", "iTXt", "tIME", "eXIf", "iCCP"} & set(source_chunks))

    source_rows = _png_rgb_rows(SOURCE_ORIGINAL)
    canonical_rows = _png_rgb_rows(canonical)
    assert len(source_rows) == 1402
    assert len(canonical_rows) == 1400
    assert tuple(row[3:-3] for row in source_rows[1:-1]) == canonical_rows


def test_fallback_is_neutral_self_contained_vector_geometry() -> None:
    path = ASSET_ROOT / "ui_portrait_unavailable.svg"
    root = ET.parse(path).getroot()
    assert root.tag == f"{SVG_NAMESPACE}svg"
    assert root.attrib["width"] == "800"
    assert root.attrib["height"] == "1000"
    assert root.attrib["viewBox"] == "0 0 800 1000"
    forbidden = {"image", "text", "script", "style", "foreignObject", "use"}
    for element in root.iter():
        assert element.tag.rsplit("}", 1)[-1] not in forbidden
        assert not any(attribute.endswith("href") for attribute in element.attrib)
    payload = path.read_text(encoding="utf-8").lower()
    attribute_payload = " ".join(value.lower() for element in root.iter() for value in element.attrib.values())
    for prohibited in ("pilot", "rfc", "raf", "rnas", "rank", "kia", "medal", "victory", "squadron"):
        assert prohibited not in attribute_payload
    assert "#2d342d" in payload and "#f4efe2" in payload


def test_fixture_mappings_are_explicit_non_authoritative_and_resolve() -> None:
    catalog = json.loads(FIXTURE_CATALOG.read_text(encoding="utf-8"))
    fixtures = {fixture["id"]: fixture for fixture in catalog["fixtures"]}
    mappings = _manifest()["fixture_mappings"]
    assert isinstance(mappings, list)
    assert {mapping["fixture_id"] for mapping in mappings} == {"pilot-ready", "aircrew-detail-ready", "squadron-ready"}
    asset_ids = {asset["id"] for asset in _assets()}
    for mapping in mappings:
        fixture = fixtures[mapping["fixture_id"]]
        assert mapping["screen"] in fixture["screens"]
        assert mapping["authoritative_data"] is False
        if mapping["asset_id"] is not None:
            assert mapping["asset_id"] in asset_ids
    squadron = next(mapping for mapping in mappings if mapping["fixture_id"] == "squadron-ready")
    assert squadron["presentation"] == "no_portrait_slot"
    assert squadron["asset_id"] is None


def test_crop_state_and_accessibility_contracts_are_fail_closed() -> None:
    manifest = _manifest()
    crop = manifest["crop_policy"]
    assert isinstance(crop, dict)
    assert crop["primary_aspect_ratio"] == "4:5"
    assert crop["identity_safe_area_percent"] == {"left": 12, "top": 6, "right": 88, "bottom": 82}
    assert crop["eye_line_percent_from_top"] == [29, 34]
    assert "No production raster derivatives" in str(crop["derivative_policy"])

    state = manifest["state_policy"]
    assert isinstance(state, dict)
    assert state["career_switch_sequence"] == ["clear_previous", "show_loading_or_fallback", "show_new_resolved"]
    assert set(state["payload_free_states"]) == {"loading", "missing", "unavailable", "error"}
    assert "must never remain visible" in str(state["rule"])

    package_readme = (ASSET_ROOT / "README.md").read_text(encoding="utf-8")
    assert "Portrait of <display name>" in package_readme
    assert "Portrait unavailable" in package_readme
    assert "previous portrait -> clear/replace with loading or fallback -> new resolved portrait" in package_readme


def test_package_checksums_cover_every_delivered_file() -> None:
    checksums = _checksums(ASSET_ROOT / "SHA256SUMS")
    expected = {"GENERATION.md", "README.md", "manifest.json", "ui_portrait_synthetic_aster_master.png", "ui_portrait_unavailable.svg"}
    assert set(checksums) == expected
    for relative, expected_digest in checksums.items():
        assert hashlib.sha256((ASSET_ROOT / relative).read_bytes()).hexdigest() == expected_digest


def test_static_evidence_is_reproducible_and_truthfully_bounded() -> None:
    checksums = _checksums(EVIDENCE_ROOT / "SHA256SUMS")
    expected_dimensions = {
        "source/ui_portrait_synthetic_aster_original.png": (1122, 1402),
        "contact-sheet.png": (1600, 1020),
        "scaling-matrix.png": (1500, 1310),
    }
    assert set(checksums) == set(expected_dimensions)
    for relative, expected_digest in checksums.items():
        path = EVIDENCE_ROOT / relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_digest
        ihdr, chunks = _png_chunks(path)
        assert ihdr[:2] == expected_dimensions[relative]
        assert chunks[0] == "IHDR" and chunks[-1] == "IEND"
        chunk_payloads = _png_chunk_payloads(path)
        assert not ({"zTXt", "iTXt", "eXIf"} & set(chunk_payloads))
        text_metadata = b"\n".join(chunk_payloads.get("tEXt", [])).lower()
        assert b"/workspace/" not in text_metadata
        assert b"\\users\\" not in text_metadata
        assert b"c:\\" not in text_metadata

    readme = (EVIDENCE_ROOT / "README.md").read_text(encoding="utf-8")
    for profile in ("100%", "125%", "150%", "200%"):
        assert profile in readme
    assert "do **not** prove native" in readme
    assert "Issue #82" in readme

    generator = (REPOSITORY_ROOT / "scripts" / "generate_ui_portrait_evidence.py").read_text(encoding="utf-8")
    assert "TemporaryDirectory" in generator
    assert 'shutil.which("inkscape")' in generator
    assert "image_gen" not in generator
    assert '"SQD-02 compact · 102 × 132"' in generator
    assert "not exhaustive" in generator


def test_package_data_and_runtime_dependencies_preserve_boundary() -> None:
    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pragma: no cover - Python 3.10 CI path
        import pip._vendor.tomli as tomllib  # type: ignore[no-redef]

    project = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependency_names = {
        re.split(r"[<>=!~ ;\[]", dependency, maxsplit=1)[0].lower()
        for dependency in project["project"]["dependencies"]
    }
    assert dependency_names.isdisjoint({"pyside6", "pyqt6", "pyqt5", "pyside2", "pillow", "openai", "opencv-python", "face-recognition", "react", "tailwind"})
    package_data = project["tool"]["setuptools"]["package-data"]["woff"]
    for pattern in (
        "assets/ui/portraits/*.json",
        "assets/ui/portraits/*.md",
        "assets/ui/portraits/*.png",
        "assets/ui/portraits/*.svg",
        "assets/ui/portraits/SHA256SUMS",
    ):
        assert pattern in package_data
    assert "docs/ui/evidence" not in " ".join(package_data)
