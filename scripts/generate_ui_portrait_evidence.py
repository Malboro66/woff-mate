"""Generate deterministic static review surfaces for UI V2 portrait assets."""

from __future__ import annotations

import base64
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = REPOSITORY_ROOT / "woff" / "assets" / "ui" / "portraits"
EVIDENCE_ROOT = (
    REPOSITORY_ROOT / "docs" / "ui" / "evidence" / "ui-v2-portraits-2026-09-24"
)
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def _element(name: str, attributes: dict[str, object]) -> ET.Element:
    return ET.Element(
        f"{{{SVG_NS}}}{name}", {key: str(value) for key, value in attributes.items()}
    )


def _add(parent: ET.Element, name: str, **attributes: object) -> ET.Element:
    child = _element(name, attributes)
    parent.append(child)
    return child


def _linked(parent: ET.Element, name: str, href: str, **attributes: object) -> ET.Element:
    attributes["href"] = href
    attributes[f"{{{XLINK_NS}}}href"] = href
    child = _element(name, attributes)
    parent.append(child)
    return child


def _text(
    parent: ET.Element,
    value: str,
    x: float,
    y: float,
    *,
    fill: str,
    size: int = 14,
    weight: int = 400,
) -> None:
    item = _add(
        parent,
        "text",
        x=x,
        y=y,
        fill=fill,
        **{
            "font-family": "sans-serif",
            "font-size": size,
            "font-weight": weight,
        },
    )
    item.text = value


def _clip(defs: ET.Element, clip_id: str, x: int, y: int, width: int, height: int) -> None:
    clip = _add(defs, "clipPath", id=clip_id)
    _add(clip, "rect", x=x, y=y, width=width, height=height, rx=4)


def _sources(defs: ET.Element, master_href: str, fallback_href: str) -> None:
    master = _add(
        defs,
        "symbol",
        id="master-source",
        viewBox="0 0 1120 1400",
        preserveAspectRatio="xMidYMid slice",
    )
    _linked(master, "image", master_href, width=1120, height=1400)
    fallback = _add(
        defs,
        "symbol",
        id="fallback-source",
        viewBox="0 0 800 1000",
        preserveAspectRatio="xMidYMid slice",
    )
    _linked(fallback, "image", fallback_href, width=800, height=1000)


def _asset(
    parent: ET.Element,
    source_id: str,
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    clip_id: str,
) -> None:
    _linked(
        parent,
        "use",
        f"#{source_id}",
        x=x,
        y=y,
        width=width,
        height=height,
        preserveAspectRatio="xMidYMid slice",
        **{"clip-path": f"url(#{clip_id})"},
    )


def _frame(parent: ET.Element, x: int, y: int, width: int, height: int) -> None:
    _add(
        parent,
        "rect",
        x=x,
        y=y,
        width=width,
        height=height,
        rx=4,
        fill="none",
        stroke="#755F3D",
        **{"stroke-width": 3},
    )


def _data_uri(path: Path, media_type: str) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _contact_sheet(master_href: str, fallback_href: str) -> ET.Element:
    width, height = 1600, 1020
    root = _element("svg", {"width": width, "height": height, "viewBox": f"0 0 {width} {height}"})
    defs = _add(root, "defs")
    _sources(defs, master_href, fallback_href)
    _clip(defs, "master", 70, 154, 448, 560)
    _clip(defs, "dossier", 646, 208, 140, 176)
    _clip(defs, "compact", 1060, 208, 104, 135)
    _clip(defs, "sqd-standard", 1200, 208, 142, 166)
    _clip(defs, "sqd-compact", 1390, 208, 102, 132)
    _clip(defs, "dark-fallback", 678, 506, 88, 110)

    _add(root, "rect", width=width, height=height, fill="#0B0F0D")
    _text(root, "WoFF Mate · UI V2 portrait package · Issue #130", 32, 42, fill="#F4EFE2", size=24, weight=600)
    _text(root, "One synthetic 4:5 master + one neutral fallback · static toolkit-independent review", 32, 70, fill="#C2BCAF", size=14)

    _add(root, "rect", x=28, y=100, width=540, height=850, rx=8, fill="#18231F", stroke="#46534C")
    _text(root, "Canonical master and crop contract", 54, 134, fill="#F4EFE2", size=18, weight=600)
    _asset(root, "master-source", 70, 154, 448, 560, clip_id="master")
    _frame(root, 70, 154, 448, 560)
    _add(root, "rect", x=124, y=188, width=340, height=426, fill="none", stroke="#E0B65C", **{"stroke-width": 3, "stroke-dasharray": "10 8"})
    _add(root, "line", x1=124, y1=316, x2=464, y2=316, stroke="#77AFC2", **{"stroke-width": 3})
    _text(root, "identity safe area · x 12–88% · y 6–82%", 70, 748, fill="#E0B65C", size=13, weight=600)
    _text(root, "eye-line family band · y 29–34%", 70, 773, fill="#77AFC2", size=13, weight=600)
    _text(root, "1120 × 1400 PNG · exact 4:5 · no upscaling", 70, 808, fill="#F4EFE2", size=13)
    _text(root, "Synthetic Pilot Aster · presentation mapping only", 70, 833, fill="#C2BCAF", size=13)
    _text(root, "No name, rank, service, status, or identity is read from pixels.", 70, 875, fill="#C2BCAF", size=12)

    _add(root, "rect", x=594, y=100, width=978, height=850, rx=8, fill="#E7D8B8", stroke="#A99A7C")
    _text(root, "Approved contexts", 620, 134, fill="#201D18", size=18, weight=600)

    _add(root, "rect", x=620, y=154, width=928, height=260, rx=6, fill="#F0E4CA", stroke="#A99A7C")
    _text(root, "DOS-01 · Pilot Dossier · standard", 646, 184, fill="#201D18", size=14, weight=600)
    _asset(root, "master-source", 646, 208, 140, 176, clip_id="dossier")
    _frame(root, 646, 208, 140, 176)
    _text(root, "Synthetic Pilot Aster", 810, 244, fill="#201D18", size=18, weight=600)
    _text(root, "Portrait of Synthetic Pilot Aster", 810, 275, fill="#5B5345", size=12)
    _text(root, "Fixture data remains authoritative", 810, 301, fill="#5B5345", size=12)

    _text(root, "DOS-01 compact", 1040, 184, fill="#201D18", size=12, weight=600)
    _asset(root, "master-source", 1060, 208, 104, 135, clip_id="compact")
    _frame(root, 1060, 208, 104, 135)
    _text(root, "center cover", 1064, 366, fill="#5B5345", size=11)

    _text(root, "SQD-02 standard", 1185, 184, fill="#201D18", size=12, weight=600)
    _asset(root, "fallback-source", 1200, 208, 142, 166, clip_id="sqd-standard")
    _frame(root, 1200, 208, 142, 166)
    _text(root, "Portrait unavailable", 1186, 395, fill="#201D18", size=11, weight=600)

    _text(root, "SQD-02 compact · 102 × 132", 1362, 184, fill="#201D18", size=11, weight=600)
    _asset(root, "fallback-source", 1390, 208, 102, 132, clip_id="sqd-compact")
    _frame(root, 1390, 208, 102, 132)
    _text(root, "Portrait unavailable", 1368, 368, fill="#201D18", size=11, weight=600)

    _add(root, "rect", x=620, y=438, width=928, height=226, rx=6, fill="#18231F", stroke="#46534C")
    _text(root, "Dark V2 shell · fallback state", 646, 472, fill="#F4EFE2", size=15, weight=600)
    _add(root, "rect", x=652, y=494, width=820, height=138, rx=5, fill="#26332D", stroke="#C2A86B", **{"stroke-width": 2})
    _asset(root, "fallback-source", 678, 506, 88, 110, clip_id="dark-fallback")
    _text(root, "Portrait unavailable", 792, 549, fill="#F4EFE2", size=20, weight=600)
    _text(root, "No previous-career image is retained", 792, 579, fill="#C2BCAF", size=13)
    _text(root, "clear previous → loading/fallback → new resolved", 792, 603, fill="#E0B65C", size=13, weight=600)

    _add(root, "rect", x=620, y=688, width=928, height=222, rx=6, fill="#F0E4CA", stroke="#A99A7C")
    _text(root, "Q0 exclusions", 646, 724, fill="#201D18", size=15, weight=600)
    _text(root, "SQD-01 roster rows: no approved portrait slot", 646, 760, fill="#201D18", size=13)
    _text(root, "OPR-01 and other screens: no portrait consumer", 646, 788, fill="#201D18", size=13)
    _text(root, "No nationality/rank/service catalog and no mechanical derivative family", 646, 816, fill="#201D18", size=13)
    _text(root, "Static review only · not native Windows DPI, Qt, screen-reader, or runtime evidence", 646, 866, fill="#5B5345", size=12)
    return root


def _scaling_matrix(master_href: str, fallback_href: str) -> ET.Element:
    width, height = 1500, 1310
    root = _element("svg", {"width": width, "height": height, "viewBox": f"0 0 {width} {height}"})
    defs = _add(root, "defs")
    _sources(defs, master_href, fallback_href)
    rows = (("100%", 140, 176), ("125%", 175, 220), ("150%", 210, 264), ("200%", 280, 352))
    y_positions = (128, 344, 604, 908)
    for index, ((_, portrait_width, portrait_height), y) in enumerate(zip(rows, y_positions)):
        _clip(defs, f"resolved-{index}", 254, y, portrait_width, portrait_height)
        _clip(defs, f"fallback-{index}", 802, y, portrait_width, portrait_height)

    _add(root, "rect", width=width, height=height, fill="#111614")
    _text(root, "Static Windows logical-profile equivalents", 32, 42, fill="#F4EFE2", size=24, weight=600)
    _text(root, "Representative DOS-01 standard slot only · 100 / 125 / 150 / 200% static equivalents · not exhaustive", 32, 72, fill="#C2BCAF", size=14)
    _text(root, "Resolved synthetic exemplar", 254, 106, fill="#F4EFE2", size=15, weight=600)
    _text(root, "Neutral fallback", 802, 106, fill="#F4EFE2", size=15, weight=600)

    for index, ((scale, portrait_width, portrait_height), y) in enumerate(zip(rows, y_positions)):
        row_height = portrait_height + 20
        _add(root, "rect", x=26, y=y - 10, width=1448, height=row_height, rx=6, fill="#18231F", stroke="#46534C")
        _text(root, scale, 58, y + 34, fill="#C2A86B", size=22, weight=600)
        _text(root, f"{portrait_width} × {portrait_height} physical px", 58, y + 61, fill="#C2BCAF", size=12)
        _asset(root, "master-source", 254, y, portrait_width, portrait_height, clip_id=f"resolved-{index}")
        _frame(root, 254, y, portrait_width, portrait_height)
        _asset(root, "fallback-source", 802, y, portrait_width, portrait_height, clip_id=f"fallback-{index}")
        _frame(root, 802, y, portrait_width, portrait_height)
        _text(root, "Portrait unavailable", 1110, y + min(60, portrait_height // 2), fill="#F4EFE2", size=13, weight=600)

    _text(root, "Static SVG sizing does not prove Windows DPR transitions, Qt raster loading, caching, or native accessibility.", 32, 1288, fill="#C2BCAF", size=12)
    return root


def _write_png(path: Path, root: ET.Element) -> None:
    inkscape = shutil.which("inkscape")
    if inkscape is None:
        raise RuntimeError("Inkscape is required to regenerate portrait evidence")
    with tempfile.TemporaryDirectory(prefix="woff-ui-portrait-evidence-") as temporary:
        svg_path = Path(temporary) / f"{path.stem}.svg"
        ET.ElementTree(root).write(svg_path, encoding="utf-8", xml_declaration=True)
        result = subprocess.run(
            [
                inkscape,
                str(svg_path),
                "--export-type=png",
                f"--export-filename={path}",
                "--export-overwrite",
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Inkscape evidence render failed")


def _write_checksums(paths: tuple[Path, ...]) -> None:
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(EVIDENCE_ROOT).as_posix()}"
        for path in paths
    ]
    (EVIDENCE_ROOT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> None:
    master = ASSET_ROOT / "ui_portrait_synthetic_aster_master.png"
    fallback = ASSET_ROOT / "ui_portrait_unavailable.svg"
    original_source = (
        EVIDENCE_ROOT / "source" / "ui_portrait_synthetic_aster_original.png"
    )
    for required in (master, fallback, original_source):
        if not required.is_file():
            raise FileNotFoundError(required.name)
    master_href = _data_uri(master, "image/png")
    fallback_href = _data_uri(fallback, "image/svg+xml")
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    contact_sheet = EVIDENCE_ROOT / "contact-sheet.png"
    scaling_matrix = EVIDENCE_ROOT / "scaling-matrix.png"
    _write_png(contact_sheet, _contact_sheet(master_href, fallback_href))
    _write_png(scaling_matrix, _scaling_matrix(master_href, fallback_href))
    _write_checksums((original_source, contact_sheet, scaling_matrix))


if __name__ == "__main__":
    main()
