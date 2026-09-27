"""Generate deterministic derivatives from canonical WoFF Mate branding SVGs.

The generator deliberately uses only the Python standard library. It validates
and consumes the committed SVG artwork without rewriting it, then emits the
Windows ICO, composite review evidence, and checksum inventories.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import math
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


INK = (32, 29, 24, 255)
GRAPHITE = (17, 22, 20, 255)
AVIATION = (24, 35, 31, 255)
FELT = (38, 51, 45, 255)
PAPER = (231, 216, 184, 255)
PAPER_RAISED = (240, 228, 202, 255)
BRASS = (194, 168, 107, 255)
ON_DARK = (244, 239, 226, 255)
MUTED_DARK = (194, 188, 175, 255)
MUTED_INK = (91, 83, 69, 255)
TRANSPARENT = (0, 0, 0, 0)
SVG_NS = "http://www.w3.org/2000/svg"
SVG_TAG = f"{{{SVG_NS}}}svg"
ICO_SIZES = (16, 24, 32, 48, 256)
REVIEW_SIZES = (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256)
CANONICAL_SVG_NAMES = (
    "woff_mate_wordmark_dark.svg",
    "woff_mate_wordmark_light.svg",
    "woff_mate_wordmark_v2.svg",
    "woff_mate_symbol_dark.svg",
    "woff_mate_symbol_light.svg",
    "woff_mate_symbol_v2.svg",
    "woff_mate_app_icon_master.svg",
    "woff_mate_app_icon_small.svg",
)
PACKAGE_CHECKSUM_NAMES = (
    "README.md",
    "manifest.json",
    "woff_mate_app.ico",
    "woff_mate_app_icon_master.svg",
    "woff_mate_app_icon_small.svg",
    "woff_mate_symbol_dark.svg",
    "woff_mate_symbol_light.svg",
    "woff_mate_symbol_v2.svg",
    "woff_mate_wordmark_dark.svg",
    "woff_mate_wordmark_light.svg",
    "woff_mate_wordmark_v2.svg",
)
NUMBER_PATTERN = r"-?(?:\d+(?:\.\d*)?|\.\d+)"


class SvgValidationError(ValueError):
    """Raised when canonical artwork leaves the supported, fail-closed subset."""


@dataclass(frozen=True)
class SvgPath:
    points: tuple[tuple[float, float], ...]
    stroke: tuple[int, int, int, int]
    stroke_width: float
    linecap: str
    linejoin: str


@dataclass(frozen=True)
class SvgRect:
    x: float
    y: float
    width: float
    height: float
    radius: float
    fill: tuple[int, int, int, int]


@dataclass(frozen=True)
class SvgArtwork:
    viewbox_width: float
    viewbox_height: float
    shapes: tuple[SvgPath | SvgRect, ...]


FONT = {
    " ": ("000",) * 7,
    "A": ("010", "101", "101", "111", "101", "101", "101"),
    "B": ("110", "101", "101", "110", "101", "101", "110"),
    "C": ("011", "100", "100", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "101", "101", "110"),
    "E": ("111", "100", "100", "110", "100", "100", "111"),
    "F": ("111", "100", "100", "110", "100", "100", "100"),
    "G": ("011", "100", "100", "101", "101", "101", "011"),
    "H": ("101", "101", "101", "111", "101", "101", "101"),
    "I": ("111", "010", "010", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "001", "101", "101", "010"),
    "K": ("101", "101", "110", "100", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "100", "100", "111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "11001", "10101", "10011", "10011", "10001"),
    "O": ("010", "101", "101", "101", "101", "101", "010"),
    "P": ("110", "101", "101", "110", "100", "100", "100"),
    "Q": ("010", "101", "101", "101", "101", "011", "001"),
    "R": ("110", "101", "101", "110", "110", "101", "101"),
    "S": ("011", "100", "100", "010", "001", "001", "110"),
    "T": ("111", "010", "010", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "101", "101", "010"),
    "V": ("101", "101", "101", "101", "101", "101", "010"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("101", "101", "010", "010", "010", "101", "101"),
    "Y": ("101", "101", "101", "010", "010", "010", "010"),
    "Z": ("111", "001", "001", "010", "100", "100", "111"),
    "0": ("111", "101", "101", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "010", "010", "111"),
    "2": ("110", "001", "001", "010", "100", "100", "111"),
    "3": ("110", "001", "001", "010", "001", "001", "110"),
    "4": ("101", "101", "101", "111", "001", "001", "001"),
    "5": ("111", "100", "100", "110", "001", "001", "110"),
    "6": ("011", "100", "100", "110", "101", "101", "010"),
    "7": ("111", "001", "001", "010", "010", "010", "010"),
    "8": ("010", "101", "101", "010", "101", "101", "010"),
    "9": ("010", "101", "101", "011", "001", "001", "110"),
    "-": ("000", "000", "000", "111", "000", "000", "000"),
    "/": ("001", "001", "001", "010", "100", "100", "100"),
    ":": ("0", "1", "0", "0", "1", "0", "0"),
    ".": ("0", "0", "0", "0", "0", "0", "1"),
    "%": ("10001", "00010", "00100", "01000", "10000", "00000", "10001"),
    "#": ("01010", "11111", "01010", "01010", "11111", "01010", "01010"),
    "+": ("000", "010", "010", "111", "010", "010", "000"),
}


class Canvas:
    def __init__(self, width: int, height: int, color: tuple[int, int, int, int]) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(color * (width * height))

    def _offset(self, x: int, y: int) -> int:
        return (y * self.width + x) * 4

    def set(self, x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        source_alpha = color[3]
        offset = self._offset(x, y)
        if source_alpha == 255:
            self.pixels[offset : offset + 4] = bytes(color)
            return
        if source_alpha == 0:
            return
        destination_alpha = self.pixels[offset + 3]
        out_alpha = source_alpha + destination_alpha * (255 - source_alpha) // 255
        for channel in range(3):
            source = color[channel]
            destination = self.pixels[offset + channel]
            numerator = source * source_alpha + destination * destination_alpha * (255 - source_alpha) // 255
            self.pixels[offset + channel] = numerator // max(out_alpha, 1)
        self.pixels[offset + 3] = out_alpha

    def fill_rect(
        self, x: int, y: int, width: int, height: int, color: tuple[int, int, int, int]
    ) -> None:
        for row in range(max(0, y), min(self.height, y + height)):
            for column in range(max(0, x), min(self.width, x + width)):
                self.set(column, row, color)

    def frame(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: tuple[int, int, int, int],
        thickness: int = 2,
    ) -> None:
        self.fill_rect(x, y, width, thickness, color)
        self.fill_rect(x, y + height - thickness, width, thickness, color)
        self.fill_rect(x, y, thickness, height, color)
        self.fill_rect(x + width - thickness, y, thickness, height, color)

    def paste(self, other: "Canvas", x: int, y: int, scale: int = 1) -> None:
        for source_y in range(other.height):
            for source_x in range(other.width):
                offset = other._offset(source_x, source_y)
                color = tuple(other.pixels[offset : offset + 4])
                for delta_y in range(scale):
                    for delta_x in range(scale):
                        self.set(x + source_x * scale + delta_x, y + source_y * scale + delta_y, color)  # type: ignore[arg-type]

    def text(
        self,
        value: str,
        x: int,
        y: int,
        color: tuple[int, int, int, int],
        scale: int = 2,
    ) -> None:
        cursor = x
        for character in value.upper():
            pattern = FONT.get(character, FONT[" "])
            glyph_width = len(pattern[0])
            for row, row_bits in enumerate(pattern):
                for column, bit in enumerate(row_bits):
                    if bit == "1":
                        self.fill_rect(
                            cursor + column * scale,
                            y + row * scale,
                            scale,
                            scale,
                            color,
                        )
            cursor += (glyph_width + 1) * scale


def _distance_to_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return math.hypot(px - ax, py - ay)
    position = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_squared))
    return math.hypot(px - (ax + position * dx), py - (ay + position * dy))


def _rounded_rect_contains(
    x: float, y: float, left: float, top: float, right: float, bottom: float, radius: float
) -> bool:
    if not (left <= x <= right and top <= y <= bottom):
        return False
    nearest_x = min(max(x, left + radius), right - radius)
    nearest_y = min(max(y, top + radius), bottom - radius)
    return math.hypot(x - nearest_x, y - nearest_y) <= radius


def _number(value: str, *, context: str) -> float:
    if re.fullmatch(NUMBER_PATTERN, value) is None:
        raise SvgValidationError(f"unsupported numeric value for {context}: {value!r}")
    return float(value)


def _color(value: str, *, context: str) -> tuple[int, int, int, int]:
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", value) is None:
        raise SvgValidationError(f"unsupported color for {context}: {value!r}")
    return (
        int(value[1:3], 16),
        int(value[3:5], 16),
        int(value[5:7], 16),
        255,
    )


def _attributes(
    element: ET.Element, expected: set[str], *, context: str
) -> dict[str, str]:
    actual = set(element.attrib)
    if actual != expected:
        raise SvgValidationError(
            f"unsupported attributes for {context}: expected {sorted(expected)}, "
            f"found {sorted(actual)}"
        )
    return element.attrib


def _transform(value: str) -> tuple[float, float, float]:
    match = re.fullmatch(
        rf"\s*translate\(\s*({NUMBER_PATTERN})[\s,]+({NUMBER_PATTERN})\s*\)"
        rf"\s*scale\(\s*({NUMBER_PATTERN})\s*\)\s*",
        value,
    )
    if match is None:
        raise SvgValidationError(
            "unsupported transform; expected translate(x y) scale(uniform)"
        )
    translate_x, translate_y, scale = (float(part) for part in match.groups())
    if scale <= 0:
        raise SvgValidationError("SVG scale must be positive")
    return scale, translate_x, translate_y


def _path_points(value: str) -> tuple[tuple[float, float], ...]:
    remainder = re.sub(NUMBER_PATTERN, "", value)
    if re.sub(r"[ML,\s]", "", remainder):
        raise SvgValidationError(f"unsupported path syntax: {value!r}")
    commands = re.findall(r"[A-Za-z]", value)
    numbers = [float(part) for part in re.findall(NUMBER_PATTERN, value)]
    if not commands or commands[0] != "M" or any(command != "L" for command in commands[1:]):
        raise SvgValidationError("only one M followed by L path commands is supported")
    if len(numbers) != len(commands) * 2:
        raise SvgValidationError("every supported path command must contain one x/y pair")
    points = tuple(zip(numbers[::2], numbers[1::2]))
    if len(points) < 2:
        raise SvgValidationError("canonical paths require at least two points")
    return points


def _parse_svg(path: Path) -> SvgArtwork:
    payload = path.read_text(encoding="utf-8")
    lowered = payload.lower()
    for forbidden in ("<!doctype", "<!entity", "<script", "<image", "<text"):
        if forbidden in lowered:
            raise SvgValidationError(f"unsupported SVG structure in {path.name}: {forbidden}")

    root = ET.fromstring(payload)
    if root.tag != SVG_TAG:
        raise SvgValidationError(f"{path.name} must use the SVG namespace")
    root_attributes = _attributes(
        root, {"width", "height", "viewBox"}, context=f"{path.name} root"
    )
    viewbox = root_attributes["viewBox"].split()
    if len(viewbox) != 4:
        raise SvgValidationError(f"{path.name} viewBox must contain four numbers")
    origin_x, origin_y, viewbox_width, viewbox_height = (
        _number(value, context=f"{path.name} viewBox") for value in viewbox
    )
    if origin_x != 0 or origin_y != 0 or viewbox_width <= 0 or viewbox_height <= 0:
        raise SvgValidationError(f"{path.name} requires a positive zero-origin viewBox")
    declared_width = _number(root_attributes["width"], context=f"{path.name} width")
    declared_height = _number(root_attributes["height"], context=f"{path.name} height")
    if (declared_width, declared_height) != (viewbox_width, viewbox_height):
        raise SvgValidationError(
            f"{path.name} width/height must match its viewBox dimensions"
        )
    if root.text and root.text.strip():
        raise SvgValidationError(f"unsupported text content in {path.name}")

    shapes: list[SvgPath | SvgRect] = []

    def visit(parent: ET.Element, inherited: tuple[float, float, float]) -> None:
        inherited_scale, inherited_x, inherited_y = inherited
        for element in parent:
            if element.text and element.text.strip():
                raise SvgValidationError(f"unsupported text content in {path.name}")
            if element.tail and element.tail.strip():
                raise SvgValidationError(f"unsupported text tail in {path.name}")
            namespace_prefix = f"{{{SVG_NS}}}"
            if not isinstance(element.tag, str) or not element.tag.startswith(
                namespace_prefix
            ):
                raise SvgValidationError(
                    f"unsupported non-SVG element in {path.name}: {element.tag!r}"
                )
            local_name = element.tag[len(namespace_prefix) :]
            if local_name == "g":
                attributes = _attributes(
                    element, {"transform"}, context=f"{path.name} group"
                )
                local_scale, local_x, local_y = _transform(attributes["transform"])
                visit(
                    element,
                    (
                        inherited_scale * local_scale,
                        inherited_x + inherited_scale * local_x,
                        inherited_y + inherited_scale * local_y,
                    ),
                )
                continue
            if local_name == "path":
                attributes = element.attrib
                required_path_attributes = {
                    "d",
                    "fill",
                    "stroke",
                    "stroke-width",
                    "stroke-linecap",
                }
                actual_path_attributes = set(attributes)
                if not required_path_attributes.issubset(actual_path_attributes) or (
                    actual_path_attributes - required_path_attributes
                ) - {"stroke-linejoin"}:
                    raise SvgValidationError(
                        f"unsupported attributes for {path.name} path: "
                        f"found {sorted(actual_path_attributes)}"
                    )
                if attributes["fill"] != "none":
                    raise SvgValidationError("canonical paths must use fill=none")
                if attributes["stroke-linecap"] != "round":
                    raise SvgValidationError("canonical paths require round line caps")
                points_untransformed = _path_points(attributes["d"])
                linejoin = attributes.get("stroke-linejoin")
                if linejoin not in (None, "round"):
                    raise SvgValidationError("canonical paths require round line joins")
                if linejoin is None and len(points_untransformed) != 2:
                    raise SvgValidationError(
                        "stroke-linejoin may be omitted only for a two-point path"
                    )
                points = tuple(
                    (
                        inherited_x + inherited_scale * x,
                        inherited_y + inherited_scale * y,
                    )
                    for x, y in points_untransformed
                )
                stroke_width = _number(
                    attributes["stroke-width"], context="stroke width"
                )
                if stroke_width <= 0:
                    raise SvgValidationError("canonical path stroke width must be positive")
                shapes.append(
                    SvgPath(
                        points=points,
                        stroke=_color(attributes["stroke"], context="path stroke"),
                        stroke_width=stroke_width * inherited_scale,
                        linecap="round",
                        linejoin=linejoin or "round",
                    )
                )
                continue
            if local_name == "rect":
                attributes = _attributes(
                    element,
                    {"x", "y", "width", "height", "rx", "fill"},
                    context=f"{path.name} rect",
                )
                width = _number(attributes["width"], context="rect width")
                height = _number(attributes["height"], context="rect height")
                radius = _number(attributes["rx"], context="rect radius")
                if width <= 0 or height <= 0 or radius < 0:
                    raise SvgValidationError("rectangle dimensions must be valid")
                if radius > min(width, height) / 2:
                    raise SvgValidationError("rectangle radius exceeds half its short side")
                shapes.append(
                    SvgRect(
                        x=(
                            inherited_x
                            + inherited_scale * _number(attributes["x"], context="rect x")
                        ),
                        y=(
                            inherited_y
                            + inherited_scale * _number(attributes["y"], context="rect y")
                        ),
                        width=width * inherited_scale,
                        height=height * inherited_scale,
                        radius=radius * inherited_scale,
                        fill=_color(attributes["fill"], context="rect fill"),
                    )
                )
                continue
            raise SvgValidationError(
                f"unsupported SVG element in {path.name}: <{local_name}>"
            )

    visit(root, (1.0, 0.0, 0.0))
    if not shapes:
        raise SvgValidationError(f"{path.name} contains no supported geometry")
    return SvgArtwork(viewbox_width, viewbox_height, tuple(shapes))


def _draw_polyline(canvas: Canvas, points: list[tuple[float, float]], width: float, color: tuple[int, int, int, int]) -> None:
    radius = width / 2
    for start, end in zip(points, points[1:]):
        left = max(0, math.floor(min(start[0], end[0]) - radius))
        right = min(canvas.width - 1, math.ceil(max(start[0], end[0]) + radius))
        top = max(0, math.floor(min(start[1], end[1]) - radius))
        bottom = min(canvas.height - 1, math.ceil(max(start[1], end[1]) + radius))
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                if _distance_to_segment(x + 0.5, y + 0.5, *start, *end) <= radius:
                    canvas.set(x, y, color)


def _draw_rounded_rect(
    canvas: Canvas,
    left: float,
    top: float,
    right: float,
    bottom: float,
    radius: float,
    color: tuple[int, int, int, int],
) -> None:
    for y in range(max(0, math.floor(top)), min(canvas.height, math.ceil(bottom))):
        for x in range(max(0, math.floor(left)), min(canvas.width, math.ceil(right))):
            if _rounded_rect_contains(
                x + 0.5, y + 0.5, left, top, right, bottom, radius
            ):
                canvas.set(x, y, color)


def _render_artwork(artwork: SvgArtwork, width: int, height: int) -> Canvas:
    supersample = 4
    high = Canvas(width * supersample, height * supersample, TRANSPARENT)
    scale_x = high.width / artwork.viewbox_width
    scale_y = high.height / artwork.viewbox_height
    stroke_scale = min(scale_x, scale_y)
    for shape in artwork.shapes:
        if isinstance(shape, SvgPath):
            _draw_polyline(
                high,
                [(x * scale_x, y * scale_y) for x, y in shape.points],
                shape.stroke_width * stroke_scale,
                shape.stroke,
            )
        else:
            _draw_rounded_rect(
                high,
                shape.x * scale_x,
                shape.y * scale_y,
                (shape.x + shape.width) * scale_x,
                (shape.y + shape.height) * scale_y,
                shape.radius * stroke_scale,
                shape.fill,
            )
    return _downsample(high, width, height, supersample)


def _downsample(high: Canvas, width: int, height: int, scale: int) -> Canvas:
    output = Canvas(width, height, TRANSPARENT)
    count = scale * scale
    for y in range(height):
        for x in range(width):
            alpha_total = 0
            rgb_alpha_totals = [0, 0, 0]
            for dy in range(scale):
                for dx in range(scale):
                    offset = high._offset(x * scale + dx, y * scale + dy)
                    alpha = high.pixels[offset + 3]
                    alpha_total += alpha
                    for channel in range(3):
                        rgb_alpha_totals[channel] += high.pixels[offset + channel] * alpha
            output.set(
                x,
                y,
                _straight_alpha_average(rgb_alpha_totals, alpha_total, count),
            )
    return output


def _straight_alpha_average(
    rgb_alpha_totals: list[int], alpha_total: int, sample_count: int
) -> tuple[int, int, int, int]:
    """Return straight-alpha RGBA from alpha-weighted supersample totals."""

    if alpha_total == 0:
        return TRANSPARENT
    return (
        round(rgb_alpha_totals[0] / alpha_total),
        round(rgb_alpha_totals[1] / alpha_total),
        round(rgb_alpha_totals[2] / alpha_total),
        round(alpha_total / sample_count),
    )


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = binascii.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def _png_bytes(canvas: Canvas) -> bytes:
    rows = bytearray()
    stride = canvas.width * 4
    for row in range(canvas.height):
        rows.append(0)
        start = row * stride
        rows.extend(canvas.pixels[start : start + stride])
    header = struct.pack(">IIBBBBB", canvas.width, canvas.height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _png_chunk(b"IEND", b"")
    )


def _ico_bytes(entries: list[tuple[int, bytes]]) -> bytes:
    directory = bytearray(struct.pack("<HHH", 0, 1, len(entries)))
    payload = bytearray()
    offset = 6 + 16 * len(entries)
    for size, png in entries:
        dimension = 0 if size == 256 else size
        directory.extend(
            struct.pack(
                "<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(png), offset
            )
        )
        payload.extend(png)
        offset += len(png)
    return bytes(directory + payload)


def _brand_review(sources: dict[str, SvgArtwork]) -> Canvas:
    canvas = Canvas(1600, 1000, GRAPHITE)
    canvas.text("WOFF MATE PRODUCT IDENTITY - ISSUE #132", 36, 28, ON_DARK, 4)
    canvas.text("PLOT + LEDGER / ORIGINAL CUSTOM VECTOR LETTERING", 36, 68, MUTED_DARK, 2)

    canvas.fill_rect(28, 110, 1544, 330, AVIATION)
    canvas.frame(28, 110, 1544, 330, BRASS, 2)
    canvas.text("DARK SHELL / V2 LIMITED COLOR + MONOCHROME", 56, 136, BRASS, 3)
    canvas.paste(
        _render_artwork(sources["woff_mate_wordmark_v2.svg"], 720, 180), 74, 205
    )
    canvas.text("V2 LIMITED COLOR", 74, 388, MUTED_DARK, 2)
    canvas.paste(
        _render_artwork(sources["woff_mate_symbol_light.svg"], 180, 180),
        1100,
        194,
    )
    canvas.text("MONO LIGHT ON DARK", 810, 340, ON_DARK, 2)

    canvas.fill_rect(28, 466, 1544, 286, PAPER)
    canvas.frame(28, 466, 1544, 286, MUTED_INK, 2)
    canvas.text("PAPER / MONO DARK ON LIGHT", 56, 492, INK, 3)
    canvas.paste(
        _render_artwork(sources["woff_mate_wordmark_dark.svg"], 640, 160), 72, 552
    )
    canvas.paste(
        _render_artwork(sources["woff_mate_symbol_dark.svg"], 150, 150),
        1115,
        540,
    )

    canvas.fill_rect(28, 778, 1544, 184, FELT)
    canvas.frame(28, 778, 1544, 184, (70, 83, 76, 255), 2)
    canvas.text("CLEAR SPACE", 56, 804, BRASS, 2)
    canvas.frame(54, 840, 224, 88, BRASS, 2)
    canvas.paste(
        _render_artwork(sources["woff_mate_wordmark_light.svg"], 160, 40),
        86,
        864,
    )
    canvas.text("MIN 160 PX WORDMARK", 322, 866, ON_DARK, 2)
    canvas.frame(720, 824, 104, 104, BRASS, 2)
    canvas.paste(
        _render_artwork(sources["woff_mate_symbol_light.svg"], 24, 24), 760, 864
    )
    canvas.text("MIN 24 PX SYMBOL", 858, 866, ON_DARK, 2)
    canvas.text("STATIC TOOLKIT-INDEPENDENT EVIDENCE", 1120, 930, MUTED_DARK, 2)
    return canvas


def _windows_review(master: SvgArtwork, small: SvgArtwork) -> Canvas:
    canvas = Canvas(1800, 1200, GRAPHITE)
    canvas.text("WOFF MATE WINDOWS ICON - STATIC REVIEW", 32, 24, ON_DARK, 4)
    canvas.text("TARGET SIZES ARE REVIEW EXPORTS / ICO EMBEDS 16 24 32 48 256", 32, 64, MUTED_DARK, 2)

    canvas.fill_rect(24, 104, 1752, 390, PAPER)
    canvas.frame(24, 104, 1752, 390, BRASS, 2)
    canvas.text("TARGET SIZE MATRIX", 48, 128, INK, 3)
    cell_width = 190
    for index, size in enumerate(REVIEW_SIZES[:-1]):
        row, column = divmod(index, 7)
        x = 46 + column * cell_width
        y = 176 + row * 146
        use_small = size <= 40
        icon = _render_artwork(small if use_small else master, size, size)
        canvas.fill_rect(x, y, 168, 120, PAPER_RAISED if (index + row) % 2 == 0 else PAPER)
        canvas.frame(x, y, 168, 120, MUTED_INK, 1)
        canvas.paste(icon, x + 12, y + (120 - size) // 2)
        canvas.text(f"{size} PX", x + 104, y + 48, INK, 1)
        canvas.text(
            "SMALL" if use_small else "MASTER", x + 104, y + 68, MUTED_INK, 1
        )

    canvas.fill_rect(1396, 154, 344, 312, PAPER_RAISED)
    canvas.frame(1396, 154, 344, 312, MUTED_INK, 1)
    canvas.paste(_render_artwork(master, 256, 256), 1440, 174)
    canvas.text("256 PX / MASTER", 1460, 446, INK, 2)

    canvas.fill_rect(24, 522, 1040, 646, AVIATION)
    canvas.frame(24, 522, 1040, 646, (70, 83, 76, 255), 2)
    canvas.text("PIXEL CLOSE REVIEW - 16 / 20 / 24 / 32", 50, 548, BRASS, 3)
    for index, size in enumerate((16, 20, 24, 32)):
        x = 52 + index * 252
        natural = _render_artwork(small, size, size)
        canvas.text(f"{size} PX NATURAL", x, 602, ON_DARK, 2)
        canvas.paste(natural, x, 636)
        canvas.text("8X", x, 688, MUTED_DARK, 2)
        canvas.paste(natural, x, 724, 8)
        canvas.frame(x - 1, 723, size * 8 + 2, size * 8 + 2, BRASS, 1)
    canvas.text("ONE SMALL OPTICAL MASTER / WIDER STROKES / OPEN COUNTERS / NO BORDER", 52, 1118, MUTED_DARK, 2)

    canvas.fill_rect(1090, 522, 686, 646, FELT)
    canvas.frame(1090, 522, 686, 646, BRASS, 2)
    canvas.text("STATIC CONTEXT", 1118, 548, BRASS, 3)
    canvas.text("SHORTCUT", 1120, 606, ON_DARK, 2)
    canvas.fill_rect(1120, 636, 620, 106, PAPER_RAISED)
    canvas.paste(_render_artwork(master, 64, 64), 1144, 656)
    canvas.text("WOFF MATE", 1234, 678, INK, 3)

    canvas.text("TASKBAR", 1120, 784, ON_DARK, 2)
    canvas.fill_rect(1120, 814, 620, 64, GRAPHITE)
    canvas.fill_rect(1308, 822, 48, 48, FELT)
    canvas.paste(_render_artwork(small, 32, 32), 1316, 830)

    canvas.text("WINDOW / APP ICON", 1120, 920, ON_DARK, 2)
    canvas.fill_rect(1120, 950, 620, 54, PAPER_RAISED)
    canvas.paste(_render_artwork(small, 20, 20), 1138, 967)
    canvas.text("WOFF MATE", 1174, 966, INK, 2)
    canvas.text("STATIC EVIDENCE / DEFER NATIVE WINDOWS TO ISSUE #82", 1120, 1084, MUTED_DARK, 1)
    return canvas


def _write_outputs(root: Path) -> None:
    asset_root = root / "woff" / "assets" / "ui" / "branding"
    evidence_root = root / "docs" / "ui" / "evidence" / "ui-v2-branding-2026-09-24"
    asset_root.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)

    sources = {
        filename: _parse_svg(asset_root / filename)
        for filename in CANONICAL_SVG_NAMES
    }
    master = sources["woff_mate_app_icon_master.svg"]
    small = sources["woff_mate_app_icon_small.svg"]

    icon_entries = []
    for size in ICO_SIZES:
        canvas = _render_artwork(small if size <= 32 else master, size, size)
        icon_entries.append((size, _png_bytes(canvas)))
    (asset_root / "woff_mate_app.ico").write_bytes(_ico_bytes(icon_entries))
    (evidence_root / "brand-review.png").write_bytes(
        _png_bytes(_brand_review(sources))
    )
    (evidence_root / "windows-icon-review.png").write_bytes(
        _png_bytes(_windows_review(master, small))
    )
    _write_checksums(asset_root / "SHA256SUMS", asset_root, PACKAGE_CHECKSUM_NAMES)
    _write_checksums(
        evidence_root / "SHA256SUMS",
        evidence_root,
        ("brand-review.png", "windows-icon-review.png"),
    )


def _write_checksums(path: Path, root: Path, names: tuple[str, ...]) -> None:
    lines = [
        f"{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}\n"
        for name in names
    ]
    path.write_text("".join(lines), encoding="ascii", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository-shaped output root (defaults to the current repository).",
    )
    arguments = parser.parse_args()
    _write_outputs(arguments.output_root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
