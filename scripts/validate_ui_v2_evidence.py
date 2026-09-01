"""Replay the measured Issue #79 acceptance contract (Python 3.10+, stdlib).

This validates an immutable browser capture, not the current mutable Site.
Fresh Site revisions must rerun the pinned browser driver before archiving.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/ui/evidence/ui-v2-site-2026-09-01-audit-4"
SCREENS = ("APP-00", "SEL-01", "OPR-01", "DOS-01", "DOS-02", "DOS-03", "DOS-04", "MIS-01", "MIS-02", "SQD-01", "SQD-02", "JRN-01", "RPT-01", "RPT-02", "SYS-01")
STATES = ("complete", "loading", "empty", "partial", "no-career", "missing", "truncated", "unsupported", "unreadable", "error", "stale", "zeroes", "unknown", "unavailable")
PROFILES = {"desktop-100": (1440, 1024, 256), "desktop-125": (1152, 819, 232), "desktop-150": (960, 683, 232), "desktop-200": (720, 512, 184)}
STATUS_LABELS = {"Active": "Active", "KIA": "Killed in Action (KIA)", "PoW": "Prisoner of War (PoW)", "MIA": "Missing in Action (MIA)", "Invalided Out": "Invalided Out", "Survived War": "Survived War", "Lightly Wounded": "Lightly Wounded", "Seriously Wounded": "Seriously Wounded", "missing": "Unknown", "blank": "Unknown", "unavailable": "Unknown", "future": "Transferred (future)"}
INTENTS = {"skip", "select-career", "navigate", "open-record", "filter", "preview-fixture", "request-snapshot"}
DOSSIER_LINKS = ["Open Career Record", "Open Victories & Claims", "Open Decorations"]
RETURNS = {"DOS-02": "← Return to Pilot Dossier", "DOS-03": "← Return to Pilot Dossier", "DOS-04": "← Return to Pilot Dossier", "MIS-02": "← Return to Mission Log", "SQD-02": "← Return to Squadron Roster", "RPT-02": "← Return to Reports Library"}
MAIN_COUNTS = {"APP-00": 0, "SEL-01": 2, "OPR-01": 6, "DOS-01": 3, "DOS-02": 1, "DOS-03": 1, "DOS-04": 1, "MIS-01": 9, "MIS-02": 1, "SQD-01": 15, "SQD-02": 1, "JRN-01": 9, "RPT-01": 8, "RPT-02": 1, "SYS-01": 5}
FILTERS = {"MIS-01": ["All sorties", "Completed", "Victories", "Damaged"], "SQD-01": ["All aircrew", "A Flight", "B Flight", "Unavailable"], "JRN-01": ["All entries", "Sorties", "Combat", "Squadron"], "RPT-01": ["All reports", "Career", "Missions", "Unit"], "SYS-01": ["All checks", "Healthy", "Attention", "Stale", "Unavailable"]}
RECORDS = {
    "OPR-01": ["Line Patrol", "Balloon Defense", "Offensive Patrol", "Capt. Edward Collins", "Lt. René Fournier", "2Lt. James Clarke"],
    "MIS-01": [f"Open report for {name}, {date} AUG 1917" for name, date in (("Line Patrol", "15"), ("Balloon Defense", "14"), ("Offensive Patrol", "13"), ("Escort Duty", "08"), ("Airfield Defense", "04"))],
    "SQD-01": [f"Open aircrew profile for {name}" for name in ("Maj. William Harcourt", "Capt. Edward Collins", "Lt. Arthur Bennett", "Lt. René Fournier", "2Lt. James Clarke", "Lt. Harold Mitchell", "Capt. Charles Mercer", "Lt. Thomas Reed", "2Lt. Albert Walker", "Lt. George Hale", "2Lt. Peter Lang")],
    "JRN-01": ["Open linked mission report"] * 5,
    "RPT-01": ["Open field report"] * 4,
}
SOURCE_FILES = {
    "app/page.tsx", "app/globals.css", "app/view-models.ts", "app/layout.tsx", "package.json",
    "tests/browser-acceptance.mjs", "tests/browser-acceptance-contract.test.mjs",
    "tests/paint-observations.mjs", "tests/contrast_bounds.py", "tests/presentation-contract.test.mjs",
    "tests/rendered-html.test.mjs", "tests/fixtures/dossier-observation.json",
    "tests/tsconfig.acceptance.json", "tests/README.md",
}
FORBIDDEN = re.compile(r"\b(?:create|edit|delete|save|import|export|repair|reset|launch|regenerate|generate|start session|stop session|confirm claim)\b", re.I)
PRIVATE = re.compile(r"(?:[A-Z]:\\|/Users/|/home/|Traceback|SELECT\s+\*\s+FROM|password\s*=|api_key\s*=)", re.I)


class EvidenceError(ValueError):
    """Missing observations or a measured contract violation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def number(value: Any) -> float:
    require(type(value) in (int, float) and math.isfinite(value), "finite numeric measurement required")
    return float(value)


def unique(rows: list[dict[str, Any]], key: Any, expected: set[Any], label: str) -> None:
    actual = [key(row) for row in rows]
    require(len(actual) == len(expected) and set(actual) == expected, f"{label}: exact coverage required")


def main_actions(sample: dict[str, Any]) -> list[str]:
    return [control["name"] for control in sample["controls"] if control["inMain"]]


def surface(sample: dict[str, Any], *, focus: bool = True) -> None:
    require(sample["screen"] in SCREENS and sample["state"] in STATES, "unknown surface/state")
    require(sample["profile"] in PROFILES, "unknown profile")
    require(sample["headingTabIndex"] == -1, "heading must not be a Tab stop")
    if focus:
        require(sample["headingFocused"] is True, "destination heading focus")
    for region in ("shell", "main"):
        require(number(sample[region]["clientWidth"]) > 0, "empty measured region")
        require(sample[region]["scrollWidth"] == sample[region]["clientWidth"], "horizontal overflow")
    width, height, rail = PROFILES[sample["profile"]]
    require(abs(number(sample["canvas"]["width"]) - min(width, number(sample["viewport"]["width"]))) <= 1, "actual canvas width must follow profile")
    require(abs(number(sample["canvas"]["height"]) - min(height, number(sample["viewport"]["height"]))) <= 1, "actual canvas height must follow profile")
    require(sample["rail"]["width"] == rail, "navigation rail reflow")
    require(number(sample["fonts"]["minimum"]) >= 12 and number(sample["fonts"]["measured"]) > 0 and not sample["fonts"]["failures"], "meaningful type size")
    require(len(sample["controls"]) >= 10, "missing shell control inventory")
    require(not PRIVATE.search(sample["mainText"] + sample["headerText"]), "private diagnostic in UI")
    for control in sample["controls"]:
        require(control["name"] != "" and not FORBIDDEN.search(control["name"]), "prohibited or unnamed control")
        require(control["intent"] in INTENTS, "unreviewed action intent")
        require(control["role"] in ("button", "link", "option", "combobox"), "unreviewed interactive role")
        require(control["tabIndex"] in (-1, 0), "positive tabindex changes reading order")
        require(control["href"] in (None, "#main-content"), "unexpected external action")
        require(type(control["primary"]) is bool and type(control["disabled"]) is bool, "explicit control flags")
        require(not control["disabled"], "required read-only control disabled")
        require(number(control["rect"]["width"]) >= 32, "pointer target width")
        require(number(control["rect"]["height"]) >= (40 if control["primary"] else 32), "pointer target height")
    shell = [c for c in sample["controls"] if not c["inMain"]]
    require(len(shell) == 10, "complete shell inventory")
    require([c["intent"] for c in shell] == ["skip", "select-career"] + ["navigate"] * 7 + ["preview-fixture"], "shell action intent/order")
    require(all(c["primary"] for c in shell[1:8]), "primary selector/navigation target classification")


def complete(sample: dict[str, Any]) -> None:
    surface(sample)
    require(sample["state"] == "complete", "complete capture required")
    actions = main_actions(sample)
    screen = sample["screen"]
    require(len(actions) == MAIN_COUNTS[screen], f"{screen}: incomplete read-only inventory")
    if screen in RETURNS:
        require(actions == [RETURNS[screen]], "contextual return action")
    if screen in FILTERS:
        require(actions == FILTERS[screen] + RECORDS.get(screen, []), "filter/record reading order")
    if screen == "OPR-01":
        require(actions == RECORDS[screen], "Operations read-only record inventory")
    for control in (c for c in sample["controls"] if c["inMain"]):
        expected_intent = "select-career" if screen == "SEL-01" else "navigate" if screen in RETURNS or screen == "DOS-01" else "filter" if control["name"] in FILTERS.get(screen, []) else "open-record"
        require(control["intent"] == expected_intent, "read-only control purpose")
    if screen == "DOS-01":
        require(actions == DOSSIER_LINKS, "Dossier links")
        columns = {"desktop-100": 6, "desktop-125": 3, "desktop-150": 3, "desktop-200": 2}
        require(sample["statsColumns"] == columns[sample["profile"]], "Dossier statistics reflow")
        require(sample["sideAfterLedger"] is (sample["profile"] != "desktop-100"), "side column must move below ledger")


def semantic(sample: dict[str, Any], *, focus: bool = True) -> None:
    surface(sample, focus=focus)
    require(sample["screen"] == "DOS-01", "representative state surface")
    state, fields, counts = sample["state"], sample["fields"], sample["counts"]
    actions, text = main_actions(sample), sample["mainText"]
    absent = state in ("loading", "no-career", "missing", "truncated", "unsupported", "unreadable", "error", "unavailable")
    if absent:
        require(fields == [] and counts["events"] == counts["victories"] == counts["emptyCollections"] == 0, "unavailable state borrowed data or valid-empty collection")
        require(not re.search(r"Balloon Defense|Observation balloon|Sopwith Camel|Albatros", text), "previous values in unavailable state")
    else:
        require(len(fields) == 6, "six typed fields required")
    if state == "loading":
        require(counts["busy"] == 1 and not actions, "loading geometry/actions")
    if state == "complete":
        require([field["display"] for field in fields] == ["27", "46.3 h", "8", "11", "73", "61"], "complete field values")
        require(all(field["state"] == "known" for field in fields), "complete field provenance")
        require(actions == DOSSIER_LINKS, "complete links")
    if state == "empty":
        require(counts["events"] == counts["victories"] == 0 and counts["emptyCollections"] == 2, "collection-specific empty state")
        require(fields[0]["display"] == "27" and re.search(r"read successfully.*validly empty", text, re.I) is not None, "empty must not manufacture zero totals")
    if state == "partial":
        require([field["state"] for field in fields] == ["known", "unavailable", "known", "unknown", "invalid", "unavailable"], "partial field states")
        require([field["display"] for field in fields] == ["27", "Not available", "8", "Unknown", "Invalid", "Not available"], "partial display values")
    if state == "zeroes":
        require(all(f["state"] == "zero" and re.fullmatch(r"0(?:\.0 h)?", f["display"]) for f in fields), "authoritative zero must remain a value")
    if state == "unknown":
        require(all(f["state"] == "unknown" and f["display"] == "Unknown" for f in fields) and counts["unknownCollections"] == 1, "unknown must not become zero or empty")
    if state == "no-career":
        require("NO CAREER SELECTED" in sample["headerText"] and "Arthur Bennett" not in sample["headerText"], "no-career identity leakage")
    labels = {"missing": "Pilot Dossier source", "truncated": "unvalidated values stay hidden", "unsupported": "not recognized", "unreadable": "could not be read", "unavailable": "Not available"}
    if state in labels:
        require(labels[state].lower() in text.lower(), "state-specific explanation")
    if state == "stale":
        require("14 AUG 1917 · 23:41" in text and "not current data" in text and fields[0]["display"] == "27", "stale snapshot/freshness provenance")
    expected = {"complete": DOSSIER_LINKS, "empty": DOSSIER_LINKS, "zeroes": DOSSIER_LINKS, "loading": [], "no-career": ["Select career"], "error": ["Retry view", "View data status"], "stale": DOSSIER_LINKS + ["Refresh snapshot", "View data status"], "partial": DOSSIER_LINKS + ["View data status"], "unknown": DOSSIER_LINKS + ["View data status"]}.get(state, ["View data status"])
    require(actions == expected, "state-specific permitted actions")
    for control in (c for c in sample["controls"] if c["inMain"]):
        intent = "request-snapshot" if control["name"] in ("Retry view", "Refresh snapshot") else "select-career" if control["name"] == "Select career" else "navigate"
        require(control["intent"] == intent, "state action purpose")


def contrast_ratio(rgb: Sequence[float], bounds: Sequence[Sequence[float]]) -> float:
    def luminance(channels: Sequence[float]) -> float:
        normalized = [number(c) / 255 for c in channels]
        require(len(normalized) == 3 and all(0 <= c <= 1 for c in normalized), "RGB bounds")
        return sum((c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4) * w for c, w in zip(normalized, (.2126, .7152, .0722)))
    require(len(bounds) == 3 and all(len(c) == 2 and c[0] <= c[1] for c in bounds), "ordered RGB bounds")
    fg = luminance(rgb)
    lo, hi = (luminance([c[i] for c in bounds]) for i in (0, 1))
    return (lo + .05) / (fg + .05) if fg < lo else (fg + .05) / (hi + .05) if fg > hi else 1.0


def focus_ring(shadow: str) -> None:
    rings = re.fullmatch(r"rgb\((\d+), (\d+), (\d+)\) 0px 0px 0px (\d+)px, rgb\((\d+), (\d+), (\d+)\) 0px 0px 0px (\d+)px", shadow)
    require(rings is not None, "measured two-ring focus geometry")
    assert rings is not None
    values = [int(value) for value in rings.groups()]
    require(values[3] >= 3 and values[7] - values[3] >= 3, "focus ring thickness")
    require(contrast_ratio(values[:3], [[v, v] for v in values[4:7]]) >= 3, "focus ring contrast")


def validate_evidence(document: dict[str, Any]) -> None:
    try:
        _validate(document)
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise EvidenceError(f"missing or malformed observation: {error}") from error


def _validate(document: dict[str, Any]) -> None:
    require(document["schemaVersion"] == 4, "evidence schema revision")
    require(document["evidenceRevision"] == "UIV2-SITE-2026-09-01-AUDIT-4", "immutable revision")
    require(re.fullmatch(r"[0-9a-f]{40}", document["deployment"]["sourceCommit"]) is not None, "pinned source commit")
    deployment = document["deployment"]
    require(deployment["status"] == "succeeded" and deployment["savedVersion"] == 18, "verified saved deployment")
    require(deployment["url"] == "https://woff-mate-ui-v2.pilotohans.chatgpt.site", "published source URL")
    require(deployment["id"] == "appgdep_6a96d56b15608191b13155cbcb7f7204", "verified deployment identity")
    require(deployment["savedVersionId"] == "appgprj_6a8baac178c88191acc54dde62e1870d~appgver_659eb3bc64f081919436991e057f63a7", "saved version identity")
    require(set(document["sourceFiles"]) == SOURCE_FILES, "complete source/collector snapshot")
    require(all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in document["sourceFiles"].values()), "source content hashes")
    data = document["rendered"]
    unique(data["surfaces"], lambda s: (s["screen"], s["profile"]), {(s, p) for s in SCREENS for p in PROFILES}, "screen/profile")
    for sample in data["surfaces"]:
        complete(sample)
    unique(data["states"], lambda s: s["state"], set(STATES), "semantic states")
    for sample in data["states"]:
        semantic(sample)
    unique(data["statuses"], lambda s: s["case"], set(STATUS_LABELS), "pilot statuses")
    for sample in data["statuses"]:
        surface(sample)
        status, label = sample["status"], STATUS_LABELS[sample["case"]]
        require(status["visible"] == status["accessible"] == label and status["displayText"].casefold() == label.casefold(), "lossless visible/accessibility status label")
        require(bool(status["notice"]) is (sample["case"] == "future"), "unsupported mapping notice")
        if sample["case"] == "future":
            require(status["notice"] == "Unsupported status mapping · authoritative value retained", "future status lossless explanation")
        expected_input = "Transferred (future)" if sample["case"] == "future" else "" if sample["case"] in ("missing", "blank", "unavailable") else sample["case"]
        require(status["input"] == expected_input, "status input provenance")
    expected_keyboard = {(screen, "complete") for screen in SCREENS} | {("DOS-01", state) for state in STATES}
    unique(data["keyboard"], lambda k: (k["screen"], k["state"]), expected_keyboard, "complete keyboard sequences")
    for sequence in data["keyboard"]:
        require(sequence["profile"] == "desktop-200", "keyboard reflow profile")
        sample = next(s for s in (data["surfaces"] if sequence["state"] == "complete" else data["states"]) if s["screen"] == sequence["screen"] and s["state"] == sequence["state"] and (s["profile"] == "desktop-200" or sequence["state"] != "complete"))
        expected = [c["name"] for c in sample["controls"] if c["tabIndex"] >= 0 and not c["disabled"]]
        # The trigger label includes the profile; all other control names and
        # order are profile-independent. Exceptional states were measured at
        # 100% for semantics and traversed at 200% for keyboard reflow.
        expected = [name.replace("· 100%", "· 200%") for name in expected]
        require(sequence["expected"] == expected and [stop["name"] for stop in sequence["stops"]] == expected, "Tab must reach every contextual/main/action control")
        require(expected[0] == "Skip to main content" and expected[2:8] == ["Operations", "Pilot Dossier", "Missions", "Squadron", "War Diary", "Reports"], "normative shell Tab order")
        for stop in sequence["stops"]:
            require(stop["visibleFocus"] is True and stop["inViewport"] is True and stop["tag"] != "h1", "visible sequential focus")
            focus_ring(stop["boxShadow"])
    actions = data["actions"]
    unique(actions, lambda a: a["action"], {"Retry view", "Refresh snapshot", "View data status", "Select career"}, "state action outcomes")
    for action in actions:
        semantic(action["before"])
        require(action["before"]["state"] == {"Retry view": "error", "Refresh snapshot": "stale", "View data status": "missing", "Select career": "no-career"}[action["action"]], "state action starting context")
        if action["action"] in ("Retry view", "Refresh snapshot"):
            require(action["loading"]["state"] == "loading", "retry must expose cleared loading state")
            semantic(action["loading"])
            semantic(action["after"])
            require(action["after"]["state"] == "complete", "retry completion")
            require("RFC-14A-08F2" in action["after"]["headerText"], "retry changed career")
        elif action["action"] == "Select career":
            semantic(action["after"], focus=False)
            require(action["after"]["state"] == "complete" and "RFC-14A-08F2" in action["after"]["headerText"], "career selection recovery")
        else:
            require(action["after"]["screen"] == "SYS-01" and action["after"]["state"] == "complete", "status action destination")
            surface(action["after"])
    dialog = data["dialog"]
    require(len(dialog["controls"]) == 36 and len(dialog["stops"]) == 36, "complete dialog control inventory")
    require([c["name"] for c in dialog["controls"]] == [s["name"] for s in dialog["stops"]], "complete dialog Tab order")
    for control in dialog["controls"]:
        require(number(control["width"]) >= 32 and number(control["height"]) >= 40, "dialog pointer target")
        require(not FORBIDDEN.search(control["name"]) and control["tag"] in ("button", "select"), "read-only dialog controls")
    for stop in dialog["stops"]:
        require(stop["visibleFocus"] is True, "dialog visible focus")
        focus_ring(stop["boxShadow"])
    require(dialog["backward"] == "Apply desktop preview" and dialog["forward"] == dialog["first"], "dialog focus wrap")
    require(dialog["statusFocus"]["visible"] is True and dialog["statusFocus"]["label"] == "Pilot status fixture", "status picker keyboard focus")
    focus_ring(dialog["statusFocus"]["shadow"])
    require(dialog["restored"].startswith("Fixture matrix"), "Escape focus restoration")
    isolation = data["isolation"]
    unique(isolation["contexts"], lambda c: c["screen"], {"MIS-02", "SQD-02", "RPT-02"}, "career isolation contexts")
    for context in isolation["contexts"]:
        require(context["oldReference"] in context["before"]["mainText"] + context["before"]["headerText"], "old detail must first be visible")
        for phase in ("after", "reopened"):
            require(context["oldReference"] not in context[phase]["mainText"] + context[phase]["headerText"], "old detail leaked after career switch")
        require("RAF-41B-22C1" in context["after"]["headerText"] and "WoFF Pilot 2" in context["after"]["mainText"], "new stable career identity")
    sparse = main_actions(isolation["sparse"])
    require(len(sparse) == 2 and sparse[0].startswith("WoFF Pilot 2") and sparse[1].startswith("WoFF Pilot 3") and not any("WoFF Pilot 1" in label for label in sparse), "sparse slots were renumbered")
    paints = document["contrast"]["text"]
    expected_paints = {("surface", s, p, "complete", None) for s in SCREENS for p in PROFILES} | {("state", "DOS-01", "desktop-100", s, None) for s in STATES} | {("status", "DOS-01", "desktop-100", "complete", s) for s in STATUS_LABELS}
    unique(paints, lambda p: (p["captureKind"], p["screen"], p["profile"], p["state"], p.get("case")), expected_paints, "text contrast capture coverage")
    for paint in paints:
        require(number(paint["measured"]) > 0 and not paint["failures"] and not paint["unsupported"], "unverified paint operation")
        require(number(paint["minimum"]) >= 4.5 and len(paint["lowest"]) == 5, "text contrast lower bound")
        require(paint["minimum"] == min(low["ratioLowerBound"] for low in paint["lowest"]), "recorded contrast minimum")
        for low in paint["lowest"]:
            actual = contrast_ratio(low["color"], low["backgroundBounds"])
            require(low["required"] in (3, 4.5) and abs(actual - number(low["ratioLowerBound"])) < 1e-8 and actual >= low["required"], "recomputed text contrast")
    boundaries = document["contrast"]["boundaries"]
    unique(boundaries, lambda b: b["screen"], set(SCREENS), "non-text surface coverage")
    for paint in boundaries:
        require(paint["profile"] == "desktop-200" and paint["state"] == "complete", "non-text capture profile")
        require(paint["boundaries"] and not paint["boundaryFailures"] and not paint["unsupported"], "missing boundary measurements")
        for edge in paint["boundaries"]:
            actual = min(contrast_ratio(edge["color"], edge["insideBounds"]), contrast_ratio(edge["color"], edge["outsideBounds"]))
            require(actual >= 3 and abs(actual - number(edge["ratioLowerBound"])) < 1e-8, "recomputed non-text contrast")


def verify_manifest(root: Path = EVIDENCE) -> str:
    """Verify immutable bytes and exact source membership; return set digest."""
    lines = (root / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    filenames: set[str] = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, "malformed checksum line")
        assert match is not None
        digest, filename = match.groups()
        require(filename not in filenames and not Path(filename).is_absolute() and ".." not in Path(filename).parts, "unsafe or duplicate checksum entry")
        filenames.add(filename)
        require(hashlib.sha256((root / filename).read_bytes()).hexdigest() == digest, f"checksum mismatch: {filename}")
    require(filenames == {"conformance-measurements.json"} | {f"source/{name}" for name in SOURCE_FILES}, "checksum manifest coverage")
    document = json.loads((root / "conformance-measurements.json").read_text(encoding="utf-8"))
    validate_evidence(document)
    for name, digest in document["sourceFiles"].items():
        require(hashlib.sha256((root / "source" / name).read_bytes()).hexdigest() == digest, f"source snapshot mismatch: {name}")
    return hashlib.sha256("".join(f"{line}\n" for line in lines).encode("ascii")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=EVIDENCE / "conformance-measurements.json")
    args = parser.parse_args(argv)
    try:
        validate_evidence(json.loads(args.path.read_text(encoding="utf-8")))
        verify_manifest(args.path.parent)
    except (OSError, json.JSONDecodeError, EvidenceError) as error:
        print(f"UI V2 evidence invalid: {error}")
        return 1
    print("UI V2 evidence valid: 60 screen/profile captures, 14 states, 12 statuses, 28 complete keyboard sequences")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
