"""Vendor the pinned, minimally adapted UI V2 icon subset.

This is intentionally a source-specific reproduction helper, not a general
asset pipeline. It requires a local checkout of Microsoft Fluent System Icons
at the exact revision recorded below and performs one adaptation only:
``#212121`` becomes ``currentColor``.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path


UPSTREAM_REVISION = "8ab43f850c7e8858edf9cb848ba2376f30b7faa3"
SIZES = (16, 20, 24, 32)
ICON_SOURCES = {
    "nav_operations": ("Board", "board", ("regular", "filled")),
    "nav_pilot_dossier": ("Contact Card", "contact_card", ("regular", "filled")),
    "nav_missions": ("Airplane", "airplane", ("regular", "filled")),
    "nav_squadron": ("People Team", "people_team", ("regular", "filled")),
    "nav_war_diary": ("Book Open", "book_open", ("regular", "filled")),
    "nav_reports": ("Document Data", "document_data", ("regular", "filled")),
    "nav_system_status": ("Database", "database", ("regular", "filled")),
    "state_information": ("Info", "info", ("regular",)),
    "state_complete": ("Checkmark Circle", "checkmark_circle", ("regular",)),
    "state_partial": ("Warning", "warning", ("regular",)),
    "state_stale": ("Clock", "clock", ("regular",)),
    "state_error": ("Dismiss Circle", "dismiss_circle", ("regular",)),
    "state_unavailable": ("Subtract Circle", "subtract_circle", ("regular",)),
    "action_retry": ("Arrow Clockwise", "arrow_clockwise", ("regular",)),
    "action_back": ("Arrow Left", "arrow_left", ("regular",)),
    "action_disclosure": ("Chevron Right", "chevron_right", ("regular",)),
}


def _git_output(source: Path, object_name: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(source), "show", object_name],
        check=True,
        capture_output=True,
    ).stdout


def _verify_source(source: Path) -> None:
    revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="ascii",
    ).stdout.strip()
    if revision != UPSTREAM_REVISION:
        raise SystemExit(
            f"expected Fluent System Icons {UPSTREAM_REVISION}, found {revision}"
        )


def _adapt_svg(payload: bytes, source_path: str) -> bytes:
    text = payload.decode("utf-8")
    if "#212121" not in text:
        raise SystemExit(f"expected upstream foreground color in {source_path}")
    adapted = text.replace('fill="#212121"', 'fill="currentColor"')
    if "#212121" in adapted:
        raise SystemExit(f"unadapted foreground color remains in {source_path}")
    return adapted.encode("utf-8")


def vendor(source: Path, destination: Path) -> None:
    _verify_source(source)
    destination.mkdir(parents=True, exist_ok=True)
    license_directory = destination / "LICENSES"
    license_directory.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for semantic, (directory, upstream_name, styles) in ICON_SOURCES.items():
        for size in SIZES:
            for style in styles:
                source_path = (
                    f"assets/{directory}/SVG/"
                    f"ic_fluent_{upstream_name}_{size}_{style}.svg"
                )
                payload = _git_output(
                    source, f"{UPSTREAM_REVISION}:{source_path}"
                )
                target = destination / f"ui_{semantic}_{size}_{style}.svg"
                target.write_bytes(_adapt_svg(payload, source_path))
                written.append(target)

    license_path = license_directory / "FLUENT-SYSTEM-ICONS-LICENSE.txt"
    notice_path = license_directory / "FLUENT-SYSTEM-ICONS-NOTICE.txt"
    license_path.write_bytes(_git_output(source, f"{UPSTREAM_REVISION}:LICENSE"))
    notice_path.write_bytes(_git_output(source, f"{UPSTREAM_REVISION}:NOTICE"))
    written.extend((license_path, notice_path))
    for repository_authored in (destination / "manifest.json", destination / "README.md"):
        if repository_authored.is_file():
            written.append(repository_authored)

    checksum_lines = []
    for path in sorted(written):
        relative = path.relative_to(destination).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksum_lines.append(f"{digest}  {relative}")
    (destination / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n", encoding="ascii", newline="\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="local Fluent System Icons checkout at the pinned revision",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path("woff/assets/ui/icons"),
    )
    arguments = parser.parse_args()
    vendor(arguments.source.resolve(), arguments.destination.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
