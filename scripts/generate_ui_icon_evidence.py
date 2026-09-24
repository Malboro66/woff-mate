"""Generate deterministic static review surfaces for the UI V2 icon package."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = REPOSITORY_ROOT / "woff" / "assets" / "ui" / "icons"
EVIDENCE_ROOT = (
    REPOSITORY_ROOT / "docs" / "ui" / "evidence" / "ui-v2-icons-2026-09-24"
)
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def _svg_element(name: str, attributes: dict[str, object]) -> ET.Element:
    return ET.Element(
        f"{{{SVG_NS}}}{name}", {key: str(value) for key, value in attributes.items()}
    )


def _add(parent: ET.Element, name: str, **attributes: object) -> ET.Element:
    child = _svg_element(name, attributes)
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


def _icon(
    parent: ET.Element,
    semantic: str,
    size: int,
    style: str,
    x: float,
    y: float,
    rendered_size: float,
    color: str,
) -> None:
    source = ET.parse(
        ASSET_ROOT / f"ui_{semantic}_{size}_{style}.svg"
    ).getroot()
    nested = _add(
        parent,
        "svg",
        x=x,
        y=y,
        width=rendered_size,
        height=rendered_size,
        viewBox=source.attrib["viewBox"],
        color=color,
        **{"aria-hidden": "true"},
    )
    for child in source:
        nested.append(deepcopy(child))


def _manifest_icons() -> list[dict[str, object]]:
    payload = json.loads((ASSET_ROOT / "manifest.json").read_text(encoding="utf-8"))
    icons = payload["icons"]
    if not isinstance(icons, list):
        raise TypeError("manifest icons must be a list")
    return icons


def _state_color(icon_id: str) -> str:
    return {
        "state.information": "#77AFC2",
        "state.complete": "#82B58A",
        "state.partial": "#E0B65C",
        "state.stale": "#E0B65C",
        "state.error": "#D97872",
    }.get(icon_id, "#F4EFE2")


def _contact_sheet() -> ET.Element:
    width, height = 1580, 1010
    root = _svg_element(
        "svg",
        {
            "width": width,
            "height": height,
            "viewBox": f"0 0 {width} {height}",
        },
    )
    _add(root, "rect", width=width, height=height, fill="#0B0F0D")
    _text(
        root,
        "WoFF Mate · UI V2 core icons · Issue #129",
        28,
        36,
        fill="#F4EFE2",
        size=22,
        weight=600,
    )
    _text(
        root,
        "Native optical masters at 16 / 20 / 24 / 32 logical px · visible labels remain required",
        28,
        62,
        fill="#C2BCAF",
        size=13,
    )

    panels = (
        {
            "x": 20,
            "title": "V2 dark shell",
            "background": "#18231F",
            "foreground": "#F4EFE2",
            "muted": "#C2BCAF",
            "border": "#46534C",
            "selected_background": "#26332D",
            "selected_border": "#C2A86B",
            "selected_icon": "#C2A86B",
        },
        {
            "x": 800,
            "title": "V2 paper / light surface",
            "background": "#E7D8B8",
            "foreground": "#201D18",
            "muted": "#5B5345",
            "border": "#A99A7C",
            "selected_background": "#F0E4CA",
            "selected_border": "#5B5345",
            "selected_icon": "#201D18",
        },
    )
    icons = _manifest_icons()
    for panel in panels:
        panel_x = int(panel["x"])
        _add(
            root,
            "rect",
            x=panel_x,
            y=82,
            width=760,
            height=900,
            rx=6,
            fill=panel["background"],
            stroke=panel["border"],
        )
        _text(
            root,
            str(panel["title"]),
            panel_x + 20,
            116,
            fill=str(panel["foreground"]),
            size=18,
            weight=600,
        )
        for index, size in enumerate((16, 20, 24, 32)):
            _text(
                root,
                f"{size}px",
                panel_x + 335 + index * 70,
                143,
                fill=str(panel["muted"]),
                size=12,
                weight=600,
            )
        _text(
            root,
            "context",
            panel_x + 650,
            143,
            fill=str(panel["muted"]),
            size=12,
            weight=600,
        )

        for row_index, icon in enumerate(icons):
            row_y = 166 + row_index * 49
            icon_id = str(icon["id"])
            semantic = str(icon["semantic"])
            label = str(icon["display_purpose"])
            _text(
                root,
                icon_id,
                panel_x + 20,
                row_y + 17,
                fill=str(panel["foreground"]),
                size=13,
                weight=600,
            )
            _text(
                root,
                label if len(label) <= 37 else f"{label[:36]}…",
                panel_x + 20,
                row_y + 35,
                fill=str(panel["muted"]),
                size=10,
            )
            for size_index, size in enumerate((16, 20, 24, 32)):
                cell_x = panel_x + 320 + size_index * 70
                _add(
                    root,
                    "rect",
                    x=cell_x,
                    y=row_y,
                    width=48,
                    height=40,
                    rx=4,
                    fill="none",
                    stroke=panel["border"],
                )
                _icon(
                    root,
                    semantic,
                    size,
                    "regular",
                    cell_x + (48 - size) / 2,
                    row_y + (40 - size) / 2,
                    size,
                    str(panel["foreground"]),
                )

            context_x = panel_x + 635
            _add(
                root,
                "rect",
                x=context_x,
                y=row_y,
                width=108,
                height=40,
                rx=4,
                fill=panel["selected_background"],
                stroke=panel["selected_border"],
                **{"stroke-width": 2},
            )
            if icon_id.startswith("nav."):
                _icon(
                    root,
                    semantic,
                    24,
                    "filled",
                    context_x + 8,
                    row_y + 8,
                    24,
                    str(panel["selected_icon"]),
                )
                context_label = "Current"
            else:
                color = (
                    _state_color(icon_id)
                    if panel["title"] == "V2 dark shell"
                    else str(panel["foreground"])
                )
                _icon(
                    root,
                    semantic,
                    24,
                    "regular",
                    context_x + 8,
                    row_y + 8,
                    24,
                    color,
                )
                context_label = icon_id.split(".", 1)[1].title()
            _text(
                root,
                context_label,
                context_x + 40,
                row_y + 25,
                fill=str(panel["foreground"]),
                size=10,
                weight=600,
            )

    _text(
        root,
        "Static toolkit-independent review surface · not native Windows or PySide6 scaling/accessibility evidence",
        28,
        1000,
        fill="#C2BCAF",
        size=11,
    )
    return root


def _scaling_matrix() -> ET.Element:
    width, height = 1600, 660
    root = _svg_element(
        "svg",
        {
            "width": width,
            "height": height,
            "viewBox": f"0 0 {width} {height}",
        },
    )
    _add(root, "rect", width=width, height=height, fill="#111614")
    _text(
        root,
        "Static Windows scaling equivalents",
        28,
        38,
        fill="#F4EFE2",
        size=22,
        weight=600,
    )
    _text(
        root,
        "Each cell rasterizes a native optical master at logical size × profile scale; this is not a native DPI transition test.",
        28,
        64,
        fill="#C2BCAF",
        size=13,
    )
    _text(
        root,
        "Left to right: current Operations · Partial · Unavailable · Error",
        28,
        84,
        fill="#C2BCAF",
        size=11,
    )
    for size_index, size in enumerate((16, 20, 24, 32)):
        x = 205 + size_index * 345
        _text(
            root,
            f"{size} logical px",
            x,
            104,
            fill="#C2BCAF",
            size=13,
            weight=600,
        )

    representatives = (
        ("nav_operations", "filled", "#C2A86B", "Current"),
        ("state_partial", "regular", "#E0B65C", "Partial"),
        ("state_unavailable", "regular", "#F4EFE2", "Unavailable"),
        ("state_error", "regular", "#D97872", "Error"),
    )
    for row_index, (profile, scale) in enumerate(
        (("100%", 1.0), ("125%", 1.25), ("150%", 1.5), ("200%", 2.0))
    ):
        row_y = 126 + row_index * 126
        _text(
            root,
            profile,
            28,
            row_y + 28,
            fill="#F4EFE2",
            size=18,
            weight=600,
        )
        _text(
            root,
            "static equivalent",
            28,
            row_y + 49,
            fill="#C2BCAF",
            size=11,
        )
        for size_index, logical_size in enumerate((16, 20, 24, 32)):
            cell_x = 185 + size_index * 345
            physical_size = logical_size * scale
            _add(
                root,
                "rect",
                x=cell_x,
                y=row_y,
                width=325,
                height=106,
                rx=6,
                fill="#18231F",
                stroke="#46534C",
            )
            _text(
                root,
                f"{physical_size:g} physical px",
                cell_x + 12,
                row_y + 20,
                fill="#C2BCAF",
                size=10,
                weight=600,
            )
            cursor = cell_x + 14
            for semantic, style, color, _label in representatives:
                _icon(
                    root,
                    semantic,
                    logical_size,
                    style,
                    cursor,
                    row_y + 31,
                    physical_size,
                    color,
                )
                cursor += physical_size + 10

    _text(
        root,
        "Native Windows scaling, monitor transitions and assistive-technology behavior remain owned by Issue #82.",
        28,
        648,
        fill="#C2BCAF",
        size=11,
    )
    return root


def _write_svg(path: Path, root: ET.Element) -> None:
    ET.indent(root, space="  ")
    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "contact-sheet.svg": _contact_sheet(),
        "scaling-matrix.svg": _scaling_matrix(),
    }
    for filename, root in outputs.items():
        _write_svg(EVIDENCE_ROOT / filename, root)
    checksum_lines = []
    for filename in sorted(outputs):
        digest = hashlib.sha256((EVIDENCE_ROOT / filename).read_bytes()).hexdigest()
        checksum_lines.append(f"{digest}  {filename}")
    (EVIDENCE_ROOT / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n", encoding="ascii", newline="\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
