"""Entirely fabricated preview dataset; never derived from private R0 bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def squads(index: int, *, empty_rank: bool = False) -> bytes:
    def row(day: int, suffix: str) -> str:
        values = [str(day), "4", "1917", "8", "25", f"Fictional sector {index}",
                  f"Fictional aerodrome {index}", f"Fictional squadron {index}{suffix}",
                  f"Fictional aircraft {index}", "unused",
                  "No supported rank" if empty_rank else f"Rank: Fictional rank {index}.", "unused"]
        return ";".join(values) + ";\r\n"
    return ("2\r\n" + row(1, " earlier") + row(2, "") + "bad;record;\r\n").encode("cp1252")


def mission(formation: int = 5, waypoints: int = 6, *, weather: bool = True,
            time: bool = True, player: bool = True, result: bool = True) -> bytes:
    attributes = (' Time="8:25"' if time else '') + (' Weather="OFFDynamicMissionWeather.xml"' if weather else '')
    units = ''.join(f'<Unit Type="Fictional aircraft" PilotFirstName="Fictional{i}" PilotLastName="Tester"'
                    + (' IsPlayer="y"' if i == 0 and player else '') + '/>' for i in range(formation))
    route = ''.join(f'<Waypoint Type="Fictional route {i}" Alt="1500" Lat="N50 00" Lon="E2 00"/>'
                    for i in range(waypoints))
    return (f'<Mission><Params Date="4/2/1917"{attributes}/>'
            f'<AirFormation SquadName="Fictional independent mission squadron">{units}'
            f'<Route>{route}</Route></AirFormation></Mission>'
            + ('\nMissionEnded' if result else '')).encode()


def rejected_dossier(basename: str) -> bytes:
    # Independent encoder for a fabricated 161-position envelope with incorrect
    # occupancy, not a sanitized real roster. The production decoder must reject.
    plain = "78CrztPRVzYQpYu90MnyW"
    total = sum(map(ord, basename.removesuffix(".txt"))) % 128
    pos, length = total % 10 or 9, total % 12 or 4
    key = plain[pos - 1:pos - 1 + length] + chr(total) + plain + plain[length - 1:length - 1 + pos]
    lines = [""] * 161
    lines[0], lines[4], lines[5] = "160", "Fictional", "Tester"
    lines[63], lines[81] = "Fictional unsupported roster", "0"
    encoded = []
    for line in lines:
        encoded.append(''.join(f'{ord(char) ^ ord(key[i % len(key)]):02X}z' for i, char in enumerate(line)))
        key = key[::-1]
    return ('\r\n'.join(encoded) + '\r\n').encode('cp1252')


def write_dataset(root: Path) -> Path:
    records = []
    for family, category, suffix in (("S", "PilotSquads", "Squads.txt"),
                                      ("M", "Mission.log", ""),
                                      ("D", "Dossier", "Dossier.txt"),
                                      ("C", "PilotClaims", "Claims.txt")):
        for index in range(1, 2 if family == "M" else 7):
            alias = f"{family}-{index:02d}"
            basename = "Mission.log" if family == "M" else f"Pilot{index}{suffix}"
            path = root / "inputs" / alias / basename
            path.parent.mkdir(parents=True)
            data = (squads(index, empty_rank=index == 5) if family == "S" else
                    mission() if family == "M" else rejected_dossier(basename) if family == "D" else
                    b"0\r\nDay;Month;Year;Hour;Minute;FictionalSector;Field;Squad;Aircraft;Unused;Type;Result;Note;\r\n")
            path.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            records.append({"alias": alias, "category": category, "copied_input": str(path),
                            "basename": basename, "actual_source": str(root / "forbidden-originals" / basename),
                            "sha256_before": digest, "sha256_after": digest, "copy_sha256": digest,
                            "stable_acquisition": True, "copy_integrity": True,
                            "basename_preserved": True, "readable": True})
    manifest = root / "manifest.private.json"
    manifest.write_text(json.dumps(records), encoding="utf-8")
    return manifest


def replace_source(manifest: Path, alias: str, data: bytes) -> None:
    records = json.loads(manifest.read_text(encoding="utf-8"))
    record = next(record for record in records if record["alias"] == alias)
    Path(record["copied_input"]).write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    for key in ("sha256_before", "sha256_after", "copy_sha256"):
        record[key] = digest
    manifest.write_text(json.dumps(records), encoding="utf-8")
