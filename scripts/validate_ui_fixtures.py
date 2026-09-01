"""Validate the closed, synthetic UI catalog; no application or GUI imports.

This is a test-data contract, not the production query/view-model API (#81).
Free text is deliberately allowlisted: a synthetic marker alone cannot prove
that a name, narrative, diagnostic, or path is safe to publish.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "woff" / "tests" / "fixtures" / "ui_states"
# Pin the entire reviewed README, not just its heading or selected sections.
# read_text normalizes newlines. Update only after reviewing all invented text;
# candidate fixture files must never supply their own expected digest.
APPROVED_INVENTORY_SHA256 = "02df1ceddac3b6291249ea1831544549ab6dd906973ef126c36bc70748f25b2a"
VERSION = "synthetic-ui-v1"
REFERENCE_TIME = "2026-01-01T12:00:00Z"
MAX_AGE_SECONDS = 60
STATES = ("loading", "ready", "empty", "missing", "stale/unavailable", "error")
SCREENS = (
    "APP-00", "SEL-01", "OPR-01", "DOS-01", "DOS-02", "DOS-03", "DOS-04",
    "MIS-01", "MIS-02", "SQD-01", "SQD-02", "JRN-01", "RPT-01", "RPT-02", "SYS-01",
)
GLOBAL_SCREENS = {"APP-00", "SEL-01", "SYS-01"}
CASE_IDS = frozenset({
    "careers-ready", "diary-ready", "empty-global", "empty-records", "error-query",
    "error-query-selected", "loading", "loading-selected", "missing-career",
    "missing-source", "missing-source-selected", "missions-ready",
    "pilot-partial-conflict", "pilot-ready", "pilot-stale", "pilot-unknown-freshness",
    "reports-ready", "settings-ready", "source-truncated", "source-unreadable",
    "source-truncated-selected", "source-unreadable-selected",
    "source-unsupported", "source-unsupported-selected", "squadron-ready",
    "unavailable-source", "unavailable-source-selected",
})
AUTHORITIES = {"synthetic-records", "synthetic-derived", "synthetic-settings", "synthetic-query", "unresolved"}
FIELD_REASONS = {"unknown", "not_supplied", "source_conflict", "redacted", "unsupported", "unreadable", "truncated"}
WARNING_TEXT = {
    "freshness_unknown": "Observation freshness is unknown; do not describe this snapshot as current.",
    "partial_record": "Some fields are unavailable; known values remain visible.",
    "query_failed": "The view could not be loaded. Retry the view or open Data & System Status.",
    "redacted_fields": "Installation details are hidden in this synthetic example.",
    "snapshot_expired": "This snapshot is old. Its observation time is shown; it is not current.",
    "source_conflict": "Sources disagree. The affected value is unavailable; no winner is inferred.",
    "source_truncated": "The source is incomplete. Unvalidated values are hidden.",
    "source_unavailable": "The source cannot answer now. No current value is inferred.",
    "source_unreadable": "The source could not be read safely. No raw diagnostic is displayed.",
    "source_unsupported": "The source format is unsupported by this example contract.",
}
# A closed vocabulary makes arbitrary personal names and diagnostic text fail
# validation even if they have no recognizable path, credential, or log syntax.
TEXT_VALUES = {
    "display_name": {"Synthetic Pilot Aster", "Synthetic Pilot Birch"},
    "squadron": {"Synthetic Squadron Cedar"},
    "service": {"RFC", "RNAS", "RAF"},
    "status": {"Active", "KIA", "PoW", "MIA", "Invalided Out", "Survived War", "Lightly Wounded", "Seriously Wounded"},
    "title": {"Synthetic dawn patrol", "Synthetic evening patrol", "Synthetic career report"},
    "result": {"Returned"},
    "role": {"Synthetic flight leader", "Synthetic wingman"},
    "transfer_status": {"Confirmed"},
    "narrative": {
        "Synthetic diary: the demonstration patrol returned safely.",
        "Synthetic diary: a second invented patrol ended without incident.",
        "Synthetic report: this text describes an invented career only.",
    },
    "profile": {"Synthetic read-only profile"},
    "example_path": {"synthetic://installation"},
    "diagnostic": {"Synthetic diagnostic: no live service is connected."},
}
NUMBER_FIELDS = {"missions", "flight_minutes", "claims", "confirmed_victories", "skill", "reputation"}
UNAVAILABLE_ONLY = {"installation_path", "database_path", "watchdog_running", "database_connected", "last_sync"}
COLLECTIONS = {"careers", "missions", "diary", "roster", "reports", "diagnostics", "records"}
ID_PREFIX = {"careers": "career", "missions": "mission", "diary": "diary", "roster": "wingman", "reports": "report", "diagnostics": "diagnostic"}
DETAIL_COLLECTIONS = {"MIS-02": "missions", "SQD-02": "roster", "RPT-02": "reports"}
REQUIRED_RECORD_FIELDS = {
    "careers": {"display_name", "source_slot", "service", "squadron"},
    "missions": {"title", "result", "claims", "confirmed_victories"},
    "diary": {"mission_id", "narrative"},
    "roster": {"display_name", "role", "transfer_status"},
    "reports": {"title", "narrative"},
    "diagnostics": {"diagnostic"},
}


class FixtureError(ValueError):
    """A safe, fixed diagnostic; never includes rejected input."""


def require(condition: bool, rule: str) -> None:
    if not condition:
        raise FixtureError(rule)


def shape(value: Any, keys: set[str], rule: str) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == keys, rule)
    return value


def choice(value: Any, values: Any, rule: str) -> None:
    require(isinstance(value, str) and value in values, rule)


def identifier(value: Any, kind: str) -> None:
    require(isinstance(value, str) and re.fullmatch(rf"synthetic-{kind}-[0-9]{{2}}", value) is not None, "synthetic identity")


def timestamp(value: Any) -> datetime:
    require(isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value) is not None, "UTC timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise FixtureError("UTC timestamp") from None


def fields(value: Any) -> set[str]:
    require(isinstance(value, dict), "field map")
    reasons: set[str] = set()
    for name, raw in value.items():
        choice(name, set(TEXT_VALUES) | NUMBER_FIELDS | UNAVAILABLE_ONLY | {"source_slot", "mission_id"}, "unapproved field")
        field = shape(raw, {"value", "unavailable_reason"}, "field shape")
        actual, reason = field["value"], field["unavailable_reason"]
        if reason is not None:
            choice(reason, FIELD_REASONS, "unavailable reason")
            require(actual is None, "unavailable field must not carry a value")
            reasons.add(reason)
            if name in {"installation_path", "database_path"}:
                require(reason == "redacted", "redacted settings")
            continue
        require(actual is not None and name not in UNAVAILABLE_ONLY, "missing unavailable reason")
        if name in NUMBER_FIELDS:
            require(type(actual) is int and 0 <= actual <= 500, "synthetic numeric value")
        elif name == "source_slot":
            require(type(actual) is int and actual in {2, 3}, "persistent synthetic slot")
        elif name == "mission_id":
            identifier(actual, "mission")
        else:
            choice(actual, TEXT_VALUES[name], "unapproved display text")
    return reasons


def payload(case: dict[str, Any]) -> set[str]:
    data = shape(case["data"], {"collection", "fields", "records"}, "payload shape")
    collection = data["collection"]
    if collection is not None:
        choice(collection, COLLECTIONS, "collection kind")
    records = data["records"]
    require(isinstance(records, list) and len(records) <= 8, "small record collection")
    require(collection is not None or not records, "singleton cannot carry records")
    require(collection != "records" or not records, "generic empty collection")
    # v1 supplies detail subjects through typed records, not child collections.
    # A career ID alone cannot establish a mission, member, or report identity.
    for screen in case["screens"]:
        if screen in DETAIL_COLLECTIONS:
            require(collection == DETAIL_COLLECTIONS[screen] and bool(records), "detail screen requires an established subject")
    reasons = fields(data["fields"])
    keys = []
    ids = []
    for raw in records:
        if not isinstance(collection, str) or collection not in ID_PREFIX:
            raise FixtureError("record collection kind")
        record = shape(raw, {"id", "career_id", "occurred_at", "fields"}, "record shape")
        identifier(record["id"], ID_PREFIX[collection])
        event_time = timestamp(record["occurred_at"])
        require(event_time.year == 1917, "invented event time")
        if collection == "careers":
            require(case["career_id"] is None and record["career_id"] == record["id"], "career selector identity")
        else:
            require(record["career_id"] == case["career_id"], "cross-career record")
        reasons.update(fields(record["fields"]))
        require(REQUIRED_RECORD_FIELDS[collection] <= set(record["fields"]), "required record fields")
        ids.append(record["id"])
        keys.append((event_time, record["id"]))
    require(len(ids) == len(set(ids)) and keys == sorted(keys), "deterministic record order")
    if any(screen in DETAIL_COLLECTIONS for screen in case["screens"]):
        require(case["subject_id"] in ids, "selected subject is not in payload")
    if case["state"] == "empty":
        require(collection is not None and not records, "empty means successful zero-item collection")
    elif collection is not None:
        require(bool(records) or case["state"] == "stale/unavailable", "ready collection must contain records")
    else:
        require(bool(data["fields"]), "ready singleton must contain fields")
    return reasons


def validate_case(raw: Any) -> None:
    case = shape(raw, {
        "id", "screens", "synthetic", "label", "contract_version", "state", "reason",
        "career_id", "subject_id", "source_authority", "observed_at", "freshness", "warnings", "data",
    }, "envelope shape")
    choice(case["id"], CASE_IDS, "fixture identity")
    screens = case["screens"]
    require(isinstance(screens, list) and bool(screens), "screen inventory")
    for screen in screens:
        choice(screen, SCREENS, "screen inventory")
    require(len(screens) == len(set(screens)) and screens == [screen for screen in SCREENS if screen in screens], "screen inventory order")
    require(case["synthetic"] is True and case["label"] == "Synthetic", "synthetic labeling")
    require(case["contract_version"] == VERSION, "fixture contract version")
    choice(case["state"], STATES, "shared state")
    choice(case["source_authority"], AUTHORITIES, "source authority")
    choice(case["freshness"], {"current", "stale", "unknown"}, "freshness")
    if case["career_id"] is not None:
        identifier(case["career_id"], "career")
    observed = case["observed_at"]
    age = None if observed is None else (timestamp(REFERENCE_TIME) - timestamp(observed)).total_seconds()
    require(age is None or 0 <= age <= 172800, "safe observation time")
    freshness = case["freshness"]
    if freshness == "current":
        require(age is not None and age <= MAX_AGE_SECONDS, "current freshness")
    if freshness == "stale":
        require(age is not None and age > MAX_AGE_SECONDS, "stale timestamp")
    warnings = case["warnings"]
    require(isinstance(warnings, list), "warning list")
    codes = []
    for raw_warning in warnings:
        warning = shape(raw_warning, {"code", "message"}, "warning shape")
        choice(warning["code"], WARNING_TEXT, "warning code")
        require(warning["message"] == WARNING_TEXT[warning["code"]], "unapproved diagnostic text")
        codes.append(warning["code"])
    require(codes == sorted(set(codes)), "deterministic warning order")
    state, reason, data = case["state"], case["reason"], case["data"]
    subject = case["subject_id"]
    if state == "missing" and reason == "career_not_selected":
        require(subject is None, "unselected career cannot carry a subject")
    elif any(screen not in GLOBAL_SCREENS for screen in screens):
        require(case["career_id"] is not None, "selected-career context identity")
    detail_kinds = {DETAIL_COLLECTIONS[screen] for screen in screens if screen in DETAIL_COLLECTIONS}
    if subject is not None:
        require(len(detail_kinds) == 1, "subject requires one detail kind")
        identifier(subject, ID_PREFIX[next(iter(detail_kinds))])
    elif detail_kinds and state != "missing":
        raise FixtureError("selected detail subject required")
    field_reasons: set[str] = set()
    if state in {"ready", "empty"}:
        require(reason is None and data is not None and freshness != "stale", "successful snapshot state")
        require(age is None or age <= MAX_AGE_SECONDS, "expired successful snapshot")
        require(freshness == ("unknown" if observed is None else "current"), "successful freshness evidence")
        require(case["source_authority"] not in {"unresolved", "synthetic-query"}, "successful source authority")
        field_reasons = payload(case)
    elif state == "stale/unavailable":
        choice(reason, {"snapshot_expired", "source_unavailable", "source_truncated", "source_unsupported", "source_unreadable"}, "unavailable state reason")
        require(reason in codes and freshness != "current", "unavailable warning and freshness")
        if data is not None:
            require(reason in {"snapshot_expired", "source_unavailable"} and observed is not None, "safe retained snapshot")
            require(reason != "snapshot_expired" or freshness == "stale", "expired snapshot freshness")
            require(case["source_authority"] not in {"unresolved", "synthetic-query"}, "retained source authority")
            field_reasons = payload(case)
        else:
            require(reason != "snapshot_expired" and observed is None and freshness == "unknown", "unavailable without snapshot")
    else:
        require(data is None and observed is None and freshness == "unknown", "no borrowed snapshot")
        if state == "loading":
            require(reason == "request_pending" and not warnings, "loading request")
        elif state == "missing":
            choice(reason, {"career_not_selected", "source_missing"}, "missing prerequisite")
            require(case["source_authority"] == "unresolved", "missing source authority")
            if reason == "career_not_selected":
                require(case["career_id"] is None and "SYS-01" not in screens, "global status does not require a career")
        else:
            require(reason == "query_failed" and codes == ["query_failed"], "sanitized query error")
    if data is not None:
        if age is not None and age > MAX_AGE_SECONDS:
            require(freshness == "stale", "expired retained freshness")
        if freshness == "unknown":
            require("freshness_unknown" in codes, "unknown freshness warning")
        if freshness == "stale":
            require("snapshot_expired" in codes, "retained stale warning")
        if field_reasons - {"redacted"}:
            require("partial_record" in codes, "partial fields warning")
        if "source_conflict" in field_reasons:
            require("source_conflict" in codes, "source conflict warning")
        if "redacted" in field_reasons:
            require("redacted_fields" in codes, "redacted fields warning")
    expected_warnings = set()
    if state in {"stale/unavailable", "error"}:
        expected_warnings.add(reason)
    if data is not None:
        if freshness == "unknown":
            expected_warnings.add("freshness_unknown")
        elif freshness == "stale":
            expected_warnings.add("snapshot_expired")
        if field_reasons - {"redacted"}:
            expected_warnings.add("partial_record")
        if "source_conflict" in field_reasons:
            expected_warnings.add("source_conflict")
        if "redacted" in field_reasons:
            expected_warnings.add("redacted_fields")
    require(set(codes) == expected_warnings, "warnings must match snapshot evidence")


def validate_career_fields(actual: dict[str, Any], career_id: Any, careers: dict[str, Any]) -> None:
    for name in REQUIRED_RECORD_FIELDS["careers"]:
        field = actual.get(name)
        if field and field["value"] is not None:
            rule = "snapshot slot identity" if name == "source_slot" else "career identity fields must match selector"
            require(career_id in careers and field == careers[career_id]["fields"][name], rule)


def validate_catalog(raw: Any) -> None:
    catalog = shape(raw, {"catalog_version", "reference_time", "fixtures"}, "catalog shape")
    require(type(catalog["catalog_version"]) is int and catalog["catalog_version"] == 1, "catalog version")
    require(catalog["reference_time"] == REFERENCE_TIME, "fixed reference clock")
    cases = catalog["fixtures"]
    require(isinstance(cases, list) and len(cases) == len(CASE_IDS), "fixture inventory coverage")
    for case in cases:
        validate_case(case)
    require([case["id"] for case in cases] == sorted(CASE_IDS), "fixture inventory order")
    require({case["state"] for case in cases} == set(STATES), "shared state coverage")
    require({screen for case in cases for screen in case["screens"]} == set(SCREENS), "screen coverage")
    require(any(len(case["warnings"]) >= 2 for case in cases), "multiple warnings coverage")
    # Named reference cases establish identity; a later retained scenario must
    # not overwrite the selector or make a foreign subject appear local.
    by_id = {case["id"]: case for case in cases}
    selector = by_id["careers-ready"]["data"]
    if selector is None or selector["collection"] != "careers":
        raise FixtureError("career identity anchor")
    careers = {record["id"]: record for record in selector["records"]}
    missions = {}
    subjects = {}
    for name, collection in (("missions-ready", "missions"), ("squadron-ready", "roster"), ("reports-ready", "reports")):
        anchor = by_id[name]["data"]
        if anchor is None or anchor["collection"] != collection:
            raise FixtureError("subject identity anchor")
        owners = {record["id"]: record["career_id"] for record in anchor["records"]}
        subjects.update(owners)
        if collection == "missions":
            missions.update(owners)
    require(set(careers) == {"synthetic-career-02", "synthetic-career-03"}, "distinct career identities")
    require([careers[key]["fields"]["source_slot"]["value"] for key in sorted(careers)] == [2, 3], "sparse slot preservation")
    require(len({record["fields"]["display_name"]["value"] for record in careers.values()}) == 1, "same-name career coverage")
    for case in cases:
        require(case["career_id"] is None or case["career_id"] in careers, "known career identity")
        subject = case["subject_id"]
        if subject is not None:
            require(subject in subjects and subjects[subject] == case["career_id"], "selected subject ownership")
        data = case["data"]
        if data:
            validate_career_fields(data["fields"], case["career_id"], careers)
            for record in data["records"]:
                if data["collection"] == "careers":
                    require(record["id"] in careers, "known career identity")
                    validate_career_fields(record["fields"], record["id"], careers)
                elif data["collection"] in DETAIL_COLLECTIONS.values():
                    require(record["id"] in subjects and subjects[record["id"]] == record["career_id"], "record subject ownership")
                link = record["fields"].get("mission_id")
                if link and link["value"] is not None:
                    require(link["value"] in missions and missions[link["value"]] == record["career_id"], "diary mission ownership")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def invalid_constant(_: str) -> None:
    raise FixtureError("non-finite JSON number")


def load_catalog(directory: Path = FIXTURES) -> dict[str, Any]:
    entries = list(directory.iterdir())
    require({entry.name for entry in entries} == {"README.md", "catalog.json"}, "unapproved fixture artifact")
    require(not directory.is_symlink() and all(entry.is_file() and not entry.is_symlink() for entry in entries), "fixture files only")
    inventory_path = directory / "README.md"
    require(inventory_path.stat().st_size <= 16384, "small UTF-8 inventory")
    try:
        inventory = inventory_path.read_text(encoding="utf-8")
    except UnicodeError:
        raise FixtureError("valid UTF-8 inventory required") from None
    require(hashlib.sha256(inventory.encode("utf-8")).hexdigest() == APPROVED_INVENTORY_SHA256, "approved fixture inventory text required")
    path = directory / "catalog.json"
    require(path.stat().st_size <= 65536, "small UTF-8 catalog")
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise FixtureError("valid UTF-8 JSON required") from None
    validate_catalog(catalog)
    return catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=FIXTURES)
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog(args.directory)
    except FixtureError as error:
        print(f"UI fixture validation failed: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("UI fixture validation failed: fixture files unavailable", file=sys.stderr)
        return 1
    print(f"UI fixtures valid: {len(catalog['fixtures'])} synthetic cases, {len(STATES)} shared states.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
