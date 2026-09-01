"""Conservative rendered text contrast, including texture crops and overlays.

Reads DOM observations from stdin and project-owned textures from disk. The
result is a lower bound, not a claim to exact anti-aliased screenshot pixels.
Unsupported paint operations fail closed. Requires Pillow for RGB extrema.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TEXTURES = {
    name: Image.open(ROOT / "public" / "textures" / name).convert("RGB")
    for name in ("sidebar-wood.webp", "workspace-felt.webp", "card-paper.webp")
}


class NotPainted(ValueError):
    """A scroll-clipped text node has no painted pixel in this surface."""


def color(value):
    match = re.fullmatch(r"rgba?\(([^)]+)\)", value.strip())
    if not match:
        raise ValueError(f"unsupported color: {value}")
    components = [float(v.strip()) for v in match[1].split(",")]
    return components[:3], components[3] if len(components) == 4 else 1.0


def split_layers(value):
    result, start, depth = [], 0, 0
    for i, char in enumerate(value):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            result.append(value[start:i].strip())
            start = i + 1
    result.append(value[start:].strip())
    return result


def blend(bounds, rgba):
    rgb, alpha = rgba
    return [[channel * alpha + low * (1 - alpha), channel * alpha + high * (1 - alpha)]
            for (low, high), channel in zip(bounds, rgb)]


def envelope(candidates):
    return [[min(c[i][0] for c in candidates), max(c[i][1] for c in candidates)] for i in range(3)]


def texture_bounds(layer, text_rect, filename, size, position):
    if size != "cover" or position not in ("50% 50%", "center center"):
        raise ValueError(f"unsupported texture placement: {size} / {position}")
    image = TEXTURES[filename]
    x, y, width, height = layer["rect"]
    left, top, right, bottom = layer["border"]
    x += left
    y += top
    width -= left + right
    height -= top + bottom
    scale = max(width / image.width, height / image.height)
    x += (width - image.width * scale) / 2
    y += (height - image.height * scale) / 2
    tx, ty, tw, th = text_rect
    crop = (max(0, math.floor((tx - x) / scale) - 1),
            max(0, math.floor((ty - y) / scale) - 1),
            min(image.width, math.ceil((tx + tw - x) / scale) + 1),
            min(image.height, math.ceil((ty + th - y) / scale) + 1))
    if crop[0] >= crop[2] or crop[1] >= crop[3]:
        raise NotPainted("text outside texture coverage (scroll-clipped)")
    return [list(pair) for pair in image.crop(crop).getextrema()]


def rivets_clear(layer, text_rect):
    x, y, w, h = layer["rect"]
    tx, ty, tw, th = text_rect
    return all(cx + 5 < tx or cx - 5 > tx + tw or cy + 5 < ty or cy - 5 > ty + th
               for cx in (x + 11, x + w - 11) for cy in (y + 11, y + h - 11))


def surface(observation, index, text_rect):
    if index is None:
        return [[255, 255]] * 3
    layer = observation["layers"][index]
    if float(layer["opacity"]) != 1 or layer["filter"] != "none" or any(v != "normal" for v in split_layers(layer["blend"])):
        raise ValueError(f"unsupported compositing: {layer['selector']}")
    base_color = color(layer["background"])
    result = [[v, v] for v in base_color[0]] if base_color[1] == 1 else blend(surface(observation, layer["parent"], text_rect), base_color)
    images = split_layers(layer["image"])
    sizes = split_layers(layer["size"])
    positions = split_layers(layer["position"])
    for i in reversed(range(len(images))):
        image = images[i]
        if image == "none":
            continue
        if image.startswith('url('):
            filename = image.rsplit('/', 1)[-1].rstrip('\")')
            if filename not in TEXTURES:
                raise ValueError(f"unknown background asset: {filename}")
            result = texture_bounds(layer, text_rect, filename, sizes[i % len(sizes)], positions[i % len(positions)])
        elif "gradient(" in image:
            if "riveted" in layer["selector"]:
                if not rivets_clear(layer, text_rect):
                    raise ValueError("rivet overlaps text bounds")
                continue
            stops = re.findall(r"rgba?\([^)]+\)", image)
            if not stops:
                raise ValueError("gradient without recognized stops")
            result = envelope([blend(result, color(stop)) for stop in stops])
        else:
            raise ValueError(f"unsupported background: {image}")
    for shadow in split_layers(layer["shadow"]):
        if "inset" not in shadow:
            continue
        match = re.search(r"rgba?\([^)]+\)", shadow)
        if not match:
            raise ValueError("unrecognized inset shadow")
        result = envelope([result, blend(result, color(match[0]))])
    return result


def luminance(rgb):
    linear = [v / 255 / 12.92 if v / 255 <= .04045 else ((v / 255 + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))


def ratio_bound(rgb, bounds):
    fg = luminance(rgb)
    low, high = (luminance([channel[i] for channel in bounds]) for i in (0, 1))
    return (low + .05) / (fg + .05) if fg < low else (fg + .05) / (high + .05) if fg > high else 1.0


def evaluate(observation):
    results, unsupported, clipped = [], [], []
    for item in observation["text"]:
        try:
            rgb, alpha = color(item["color"])
            if alpha != 1:
                raise ValueError("translucent foreground")
            bounds = surface(observation, item["layer"], item["rect"])
            ratio = ratio_bound(rgb, bounds)
            required = 3 if item["size"] >= 24 or item["size"] >= 18.66 and int(item["weight"]) >= 700 else 4.5
            results.append({"text": item["text"], "color": rgb, "backgroundBounds": bounds, "ratioLowerBound": ratio, "required": required})
        except NotPainted as error:
            clipped.append({"text": item["text"], "reason": str(error)})
        except (ValueError, IndexError, KeyError) as error:
            unsupported.append({"text": item["text"], "reason": str(error)})
    boundaries = []
    for control in observation.get("controls", []):
        try:
            rgb, alpha = color(control["color"])
            if alpha != 1:
                raise ValueError("translucent border")
            inside = surface(observation, control["layer"], control["rect"])
            outside = surface(observation, observation["layers"][control["layer"]]["parent"], control["rect"])
            boundaries.append({"name": control["name"], "color": rgb, "insideBounds": inside, "outsideBounds": outside,
                               "ratioLowerBound": min(ratio_bound(rgb, inside), ratio_bound(rgb, outside)), "required": 3})
        except NotPainted as error:
            clipped.append({"text": control["name"], "reason": str(error)})
        except (ValueError, IndexError, KeyError) as error:
            unsupported.append({"text": control["name"], "reason": str(error)})
    return {"screen": observation["screen"], "state": observation["state"], "profile": observation["profile"],
            "measured": len(results), "minimum": min((r["ratioLowerBound"] for r in results), default=None),
            "lowest": sorted(results, key=lambda r: r["ratioLowerBound"])[:5],
            "failures": [r for r in results if r["ratioLowerBound"] < r["required"]], "unsupported": unsupported, "clipped": clipped,
            "boundaries": boundaries, "boundaryFailures": [r for r in boundaries if r["ratioLowerBound"] < 3]}


if __name__ == "__main__":
    source = json.load(sys.stdin)
    print(json.dumps([evaluate(item) for item in source] if isinstance(source, list) else evaluate(source)))
