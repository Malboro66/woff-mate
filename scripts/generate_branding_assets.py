"""Generate deterministic WoFF Mate identity, Windows icon, and review assets.

The generator deliberately uses only the Python standard library. Canonical
SVGs remain editable vector sources; PNG payloads are generated only for the
Windows ICO and composite review evidence.
"""

from __future__ import annotations

import argparse
import binascii
import math
import struct
import zlib
from pathlib import Path


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

WORDMARK_VIEWBOX = (768, 192)
SYMBOL_VIEWBOX = (256, 256)
APP_VIEWBOX = (1024, 1024)
ICO_SIZES = (16, 24, 32, 48, 256)
REVIEW_SIZES = (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256)

MASTER_W = ((200, 318), (272, 706), (352, 512), (432, 706), (496, 318))
MASTER_M = ((560, 706), (560, 318), (700, 548), (840, 318), (840, 706))
SMALL_W = ((176, 286), (250, 738), (348, 500), (446, 738), (512, 286))
SMALL_M = ((562, 738), (562, 286), (700, 526), (838, 286), (838, 738))


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


def _sample_app_icon(size: int, *, small: bool) -> Canvas:
    samples = 4
    output = Canvas(size, size, TRANSPARENT)
    w_points = SMALL_W if small else MASTER_W
    m_points = SMALL_M if small else MASTER_M
    stroke = 92 if small else 72
    outer = (64, 64, 960, 960, 172) if small else (72, 72, 952, 952, 150)
    inner = (96, 96, 928, 928, 126)
    for py in range(size):
        for px in range(size):
            totals = [0, 0, 0, 0]
            for sy in range(samples):
                for sx in range(samples):
                    x = (px + (sx + 0.5) / samples) * 1024 / size
                    y = (py + (sy + 0.5) / samples) * 1024 / size
                    color = TRANSPARENT
                    if _rounded_rect_contains(x, y, *outer):
                        color = AVIATION
                        if not small and not _rounded_rect_contains(x, y, *inner):
                            color = BRASS
                        for points in (w_points, m_points):
                            if any(
                                _distance_to_segment(x, y, *start, *end) <= stroke / 2
                                for start, end in zip(points, points[1:])
                            ):
                                color = ON_DARK
                        divider_width = 26 if small else 18
                        if 512 - divider_width / 2 <= x <= 512 + divider_width / 2 and 350 <= y <= 674:
                            color = BRASS
                    for channel in range(4):
                        totals[channel] += color[channel]
            count = samples * samples
            output.set(px, py, tuple(round(total / count) for total in totals))  # type: ignore[arg-type]
    return output


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)


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
            struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(png), offset)
        )
        payload.extend(png)
        offset += len(png)
    return bytes(directory + payload)


def _polyline_path(points: tuple[tuple[int, int], ...]) -> str:
    return "M " + " L ".join(f"{x} {y}" for x, y in points)


def _letter_paths(character: str, x: float, y: float, width: float, height: float) -> list[list[tuple[float, float]]]:
    left, right, top, bottom = x, x + width, y, y + height
    middle = y + height * 0.5
    if character == "W":
        return [[(left, top), (left + width * 0.22, bottom), (left + width * 0.5, middle), (left + width * 0.78, bottom), (right, top)]]
    if character == "O":
        return [[(left + width * 0.18, top), (right - width * 0.18, top), (right, top + height * 0.18), (right, bottom - height * 0.18), (right - width * 0.18, bottom), (left + width * 0.18, bottom), (left, bottom - height * 0.18), (left, top + height * 0.18), (left + width * 0.18, top)]]
    if character == "F":
        return [[(left, bottom), (left, top), (right, top)], [(left, middle), (right - width * 0.15, middle)]]
    if character == "M":
        return [[(left, bottom), (left, top), (left + width * 0.5, middle), (right, top), (right, bottom)]]
    if character == "A":
        return [[(left, bottom), (left + width * 0.5, top), (right, bottom)], [(left + width * 0.22, middle + height * 0.08), (right - width * 0.22, middle + height * 0.08)]]
    if character == "T":
        return [[(left, top), (right, top)], [(left + width * 0.5, top), (left + width * 0.5, bottom)]]
    if character == "E":
        return [[(right, top), (left, top), (left, bottom), (right, bottom)], [(left, middle), (right - width * 0.12, middle)]]
    raise ValueError(character)


def _svg_path(points: list[tuple[float, float]], *, color: str, width: float) -> str:
    coordinates = " L ".join(f"{x:g} {y:g}" for x, y in points)
    return (
        f'  <path d="M {coordinates}" fill="none" stroke="{color}" '
        f'stroke-width="{width:g}" stroke-linecap="round" stroke-linejoin="round"/>\n'
    )


def _symbol_svg(color: str, *, accent: str | None = None) -> str:
    divider = ""
    if accent:
        divider = f'  <rect x="128" y="82" width="8" height="92" rx="4" fill="{accent}"/>\n'
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="{SVG_NS}" width="256" height="256" viewBox="0 0 256 256">\n'
        f'  <path d="M 24 48 L 48 208 L 72 126 L 96 208 L 120 48" fill="none" stroke="{color}" stroke-width="22" stroke-linecap="round" stroke-linejoin="round"/>\n'
        f'  <path d="M 144 208 L 144 48 L 188 132 L 232 48 L 232 208" fill="none" stroke="{color}" stroke-width="22" stroke-linecap="round" stroke-linejoin="round"/>\n'
        f"{divider}</svg>\n"
    )


def _wordmark_svg(color: str, *, accent: str | None = None) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        f'<svg xmlns="{SVG_NS}" width="768" height="192" viewBox="0 0 768 192">\n',
        '  <g transform="translate(16 16) scale(0.625)">\n',
        f'    <path d="M 24 48 L 48 208 L 72 126 L 96 208 L 120 48" fill="none" stroke="{color}" stroke-width="22" stroke-linecap="round" stroke-linejoin="round"/>\n',
        f'    <path d="M 144 208 L 144 48 L 188 132 L 232 48 L 232 208" fill="none" stroke="{color}" stroke-width="22" stroke-linecap="round" stroke-linejoin="round"/>\n',
        "  </g>\n",
    ]
    divider_color = accent or color
    parts.append(f'  <rect x="188" y="34" width="8" height="124" rx="4" fill="{divider_color}"/>\n')
    for character, x in zip("WOFF", (224, 314, 404, 494)):
        for points in _letter_paths(character, x, 30, 62, 76):
            parts.append(_svg_path(points, color=color, width=13))
    for character, x in zip("MATE", (228, 310, 392, 474)):
        for points in _letter_paths(character, x, 126, 46, 38):
            parts.append(_svg_path(points, color=color, width=9))
    parts.append(f'  <path d="M 548 145 L 716 145" fill="none" stroke="{divider_color}" stroke-width="5" stroke-linecap="round"/>\n')
    parts.append(f'  <rect x="724" y="139" width="12" height="12" rx="3" fill="{divider_color}"/>\n')
    parts.append("</svg>\n")
    return "".join(parts)


def _app_svg(*, small: bool) -> str:
    if small:
        outer = '  <rect x="64" y="64" width="896" height="896" rx="172" fill="#18231F"/>\n'
        w_path = _polyline_path(SMALL_W)
        m_path = _polyline_path(SMALL_M)
        stroke = 92
        divider_width = 26
    else:
        outer = (
            '  <rect x="72" y="72" width="880" height="880" rx="150" fill="#18231F" stroke="#C2A86B" stroke-width="24"/>\n'
        )
        w_path = _polyline_path(MASTER_W)
        m_path = _polyline_path(MASTER_M)
        stroke = 72
        divider_width = 18
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="{SVG_NS}" width="1024" height="1024" viewBox="0 0 1024 1024">\n'
        + outer
        + f'  <path d="{w_path}" fill="none" stroke="#F4EFE2" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round"/>\n'
        + f'  <path d="{m_path}" fill="none" stroke="#F4EFE2" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round"/>\n'
        + f'  <rect x="{512 - divider_width // 2}" y="350" width="{divider_width}" height="324" rx="{divider_width // 2}" fill="#C2A86B"/>\n'
        + "</svg>\n"
    )


def _render_symbol(width: int, height: int, *, color: tuple[int, int, int, int], accent: tuple[int, int, int, int] | None = None) -> Canvas:
    scale = 4
    high = Canvas(width * scale, height * scale, TRANSPARENT)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        return point[0] / 256 * width * scale, point[1] / 256 * height * scale

    _draw_polyline(high, [transform(point) for point in ((24, 48), (48, 208), (72, 126), (96, 208), (120, 48))], 22 / 256 * width * scale, color)
    _draw_polyline(high, [transform(point) for point in ((144, 208), (144, 48), (188, 132), (232, 48), (232, 208))], 22 / 256 * width * scale, color)
    if accent:
        high.fill_rect(round(128 / 256 * width * scale), round(82 / 256 * height * scale), max(1, round(8 / 256 * width * scale)), round(92 / 256 * height * scale), accent)
    return _downsample(high, width, height, scale)


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


def _downsample(high: Canvas, width: int, height: int, scale: int) -> Canvas:
    output = Canvas(width, height, TRANSPARENT)
    count = scale * scale
    for y in range(height):
        for x in range(width):
            totals = [0, 0, 0, 0]
            for dy in range(scale):
                for dx in range(scale):
                    offset = high._offset(x * scale + dx, y * scale + dy)
                    for channel in range(4):
                        totals[channel] += high.pixels[offset + channel]
            output.set(x, y, tuple(round(value / count) for value in totals))  # type: ignore[arg-type]
    return output


def _render_wordmark(width: int, height: int, *, color: tuple[int, int, int, int], accent: tuple[int, int, int, int] | None = None) -> Canvas:
    scale = 4
    high = Canvas(width * scale, height * scale, TRANSPARENT)
    sx = width * scale / WORDMARK_VIEWBOX[0]
    sy = height * scale / WORDMARK_VIEWBOX[1]
    symbol = _render_symbol(round(160 * sx), round(160 * sy), color=color, accent=None)
    high.paste(symbol, round(16 * sx), round(16 * sy))
    divider_color = accent or color
    high.fill_rect(round(188 * sx), round(34 * sy), max(1, round(8 * sx)), round(124 * sy), divider_color)
    for character, x in zip("WOFF", (224, 314, 404, 494)):
        for points in _letter_paths(character, x, 30, 62, 76):
            transformed = [(px * sx, py * sy) for px, py in points]
            _draw_polyline(high, transformed, 13 * min(sx, sy), color)
    for character, x in zip("MATE", (228, 310, 392, 474)):
        for points in _letter_paths(character, x, 126, 46, 38):
            transformed = [(px * sx, py * sy) for px, py in points]
            _draw_polyline(high, transformed, 9 * min(sx, sy), color)
    _draw_polyline(high, [(548 * sx, 145 * sy), (716 * sx, 145 * sy)], 5 * min(sx, sy), divider_color)
    high.fill_rect(round(724 * sx), round(139 * sy), max(1, round(12 * sx)), max(1, round(12 * sy)), divider_color)
    return _downsample(high, width, height, scale)


def _brand_review() -> Canvas:
    canvas = Canvas(1600, 1000, GRAPHITE)
    canvas.text("WOFF MATE PRODUCT IDENTITY - ISSUE #132", 36, 28, ON_DARK, 4)
    canvas.text("PLOT + LEDGER / ORIGINAL CUSTOM VECTOR LETTERING", 36, 68, MUTED_DARK, 2)

    canvas.fill_rect(28, 110, 1544, 330, AVIATION)
    canvas.frame(28, 110, 1544, 330, BRASS, 2)
    canvas.text("DARK SHELL / LIMITED COLOR", 56, 136, BRASS, 3)
    canvas.paste(_render_wordmark(720, 180, color=ON_DARK, accent=BRASS), 74, 205)
    canvas.paste(_render_symbol(180, 180, color=ON_DARK, accent=BRASS), 1100, 194)
    canvas.text("MONO LIGHT ON DARK", 810, 340, ON_DARK, 2)

    canvas.fill_rect(28, 466, 1544, 286, PAPER)
    canvas.frame(28, 466, 1544, 286, MUTED_INK, 2)
    canvas.text("PAPER / MONO DARK ON LIGHT", 56, 492, INK, 3)
    canvas.paste(_render_wordmark(640, 160, color=INK), 72, 552)
    canvas.paste(_render_symbol(150, 150, color=INK), 1115, 540)

    canvas.fill_rect(28, 778, 1544, 184, FELT)
    canvas.frame(28, 778, 1544, 184, (70, 83, 76, 255), 2)
    canvas.text("CLEAR SPACE", 56, 804, BRASS, 2)
    canvas.frame(54, 840, 224, 88, BRASS, 2)
    canvas.paste(_render_wordmark(160, 40, color=ON_DARK), 86, 864)
    canvas.text("MIN 160 PX WORDMARK", 322, 866, ON_DARK, 2)
    canvas.frame(720, 824, 104, 104, BRASS, 2)
    canvas.paste(_render_symbol(24, 24, color=ON_DARK), 760, 864)
    canvas.text("MIN 24 PX SYMBOL", 858, 866, ON_DARK, 2)
    canvas.text("STATIC TOOLKIT-INDEPENDENT EVIDENCE", 1120, 930, MUTED_DARK, 2)
    return canvas


def _windows_review() -> Canvas:
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
        small = size <= 40
        icon = _sample_app_icon(size, small=small)
        canvas.fill_rect(x, y, 168, 120, PAPER_RAISED if (index + row) % 2 == 0 else PAPER)
        canvas.frame(x, y, 168, 120, MUTED_INK, 1)
        canvas.paste(icon, x + 12, y + (120 - size) // 2)
        canvas.text(f"{size} PX", x + 104, y + 48, INK, 1)
        canvas.text("SMALL" if small else "MASTER", x + 104, y + 68, MUTED_INK, 1)

    canvas.fill_rect(1396, 154, 344, 312, PAPER_RAISED)
    canvas.frame(1396, 154, 344, 312, MUTED_INK, 1)
    canvas.paste(_sample_app_icon(256, small=False), 1440, 174)
    canvas.text("256 PX / MASTER", 1460, 446, INK, 2)

    canvas.fill_rect(24, 522, 1040, 646, AVIATION)
    canvas.frame(24, 522, 1040, 646, (70, 83, 76, 255), 2)
    canvas.text("PIXEL CLOSE REVIEW - 16 / 20 / 24 / 32", 50, 548, BRASS, 3)
    for index, size in enumerate((16, 20, 24, 32)):
        x = 52 + index * 252
        natural = _sample_app_icon(size, small=True)
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
    canvas.paste(_sample_app_icon(64, small=False), 1144, 656)
    canvas.text("WOFF MATE", 1234, 678, INK, 3)

    canvas.text("TASKBAR", 1120, 784, ON_DARK, 2)
    canvas.fill_rect(1120, 814, 620, 64, GRAPHITE)
    canvas.fill_rect(1308, 822, 48, 48, FELT)
    canvas.paste(_sample_app_icon(32, small=True), 1316, 830)

    canvas.text("WINDOW / APP ICON", 1120, 920, ON_DARK, 2)
    canvas.fill_rect(1120, 950, 620, 54, PAPER_RAISED)
    canvas.paste(_sample_app_icon(20, small=True), 1138, 967)
    canvas.text("WOFF MATE", 1174, 966, INK, 2)
    canvas.text("STATIC EVIDENCE / DEFER NATIVE WINDOWS TO ISSUE #82", 1120, 1084, MUTED_DARK, 1)
    return canvas


def _write_outputs(root: Path) -> None:
    asset_root = root / "woff" / "assets" / "ui" / "branding"
    evidence_root = root / "docs" / "ui" / "evidence" / "ui-v2-branding-2026-09-24"
    asset_root.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)

    svg_outputs = {
        "woff_mate_wordmark_dark.svg": _wordmark_svg("#201D18"),
        "woff_mate_wordmark_light.svg": _wordmark_svg("#F4EFE2"),
        "woff_mate_wordmark_v2.svg": _wordmark_svg("#F4EFE2", accent="#C2A86B"),
        "woff_mate_symbol_dark.svg": _symbol_svg("#201D18"),
        "woff_mate_symbol_light.svg": _symbol_svg("#F4EFE2"),
        "woff_mate_symbol_v2.svg": _symbol_svg("#F4EFE2", accent="#C2A86B"),
        "woff_mate_app_icon_master.svg": _app_svg(small=False),
        "woff_mate_app_icon_small.svg": _app_svg(small=True),
    }
    for filename, payload in svg_outputs.items():
        (asset_root / filename).write_text(payload, encoding="utf-8", newline="\n")

    icon_entries = []
    for size in ICO_SIZES:
        canvas = _sample_app_icon(size, small=size <= 32)
        icon_entries.append((size, _png_bytes(canvas)))
    (asset_root / "woff_mate_app.ico").write_bytes(_ico_bytes(icon_entries))
    (evidence_root / "brand-review.png").write_bytes(_png_bytes(_brand_review()))
    (evidence_root / "windows-icon-review.png").write_bytes(_png_bytes(_windows_review()))


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
