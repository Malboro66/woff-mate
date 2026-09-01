"""UI fixture contracts run independently of woff/tests/conftest.py and SQLite."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

import pytest

from scripts.validate_ui_fixtures import (
    FixtureError,
    SCREENS,
    WARNING_TEXT,
    load_catalog,
    main,
    validate_catalog,
    validate_case,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "woff" / "tests" / "fixtures" / "ui_states"
SHARED_STATES = {"loading", "ready", "empty", "missing", "stale/unavailable", "error"}
DETAIL_CASES = (
    ("mission-detail-ready", "MIS-02", "synthetic-mission-02"),
    ("aircrew-detail-ready", "SQD-02", "synthetic-wingman-02"),
    ("report-detail-ready", "RPT-02", "synthetic-report-01"),
)
NO_PAYLOAD_CASES = (
    "loading", "error-query", "missing-source", "source-truncated",
    "source-unreadable", "source-unsupported", "unavailable-source",
)
LIST_CASES = (
    ("missions-ready", "MIS-01", "synthetic-mission-02"),
    ("squadron-ready", "SQD-01", "synthetic-wingman-02"),
    ("reports-ready", "RPT-01", "synthetic-report-01"),
)


def test_catalog_covers_shared_states_and_primary_screens() -> None:
    catalog = json.loads((FIXTURES / "catalog.json").read_text(encoding="utf-8"))
    assert {case["state"] for case in catalog["fixtures"]} == SHARED_STATES
    ready_screens = {
        screen
        for case in catalog["fixtures"] if case["state"] == "ready"
        for screen in case["screens"]
    }
    assert {"OPR-01", "DOS-01", "MIS-01", "JRN-01", "SQD-01", "SYS-01", "RPT-01"} <= ready_screens
    assert any(len(case["warnings"]) > 1 for case in catalog["fixtures"])


@pytest.fixture
def catalog() -> dict[str, Any]:
    return json.loads((FIXTURES / "catalog.json").read_text(encoding="utf-8"))


def case(catalog: dict[str, Any], name: str) -> dict[str, Any]:
    return next(row for row in catalog["fixtures"] if row["id"] == name)


def warning(code: str) -> dict[str, str]:
    return {"code": code, "message": WARNING_TEXT[code]}


def test_catalog_and_standalone_entry_point(catalog: dict[str, Any]) -> None:
    validate_catalog(catalog)
    assert load_catalog() == catalog
    assert main([]) == 0


def test_zero_partial_conflict_and_unknown_freshness_remain_distinct(catalog: dict[str, Any]) -> None:
    partial = case(catalog, "pilot-partial-conflict")
    assert partial["state"] == "ready"
    fields = partial["data"]["fields"]
    assert fields["confirmed_victories"] == {"value": 0, "unavailable_reason": None}
    assert fields["service"] == {"value": None, "unavailable_reason": "source_conflict"}
    assert fields["status"] == {"value": None, "unavailable_reason": "unknown"}
    assert fields["flight_minutes"] == {"value": None, "unavailable_reason": "not_supplied"}
    assert {item["code"] for item in partial["warnings"]} == {"partial_record", "source_conflict"}
    unknown = case(catalog, "pilot-unknown-freshness")
    assert unknown["state"] == "ready" and unknown["observed_at"] is None
    assert unknown["freshness"] == "unknown"
    assert unknown["warnings"] == [warning("freshness_unknown")]


def test_privacy_safe_settings_and_sparse_same_name_careers(catalog: dict[str, Any]) -> None:
    careers = case(catalog, "careers-ready")["data"]["records"]
    assert [row["id"] for row in careers] == ["synthetic-career-02", "synthetic-career-03"]
    assert [row["fields"]["source_slot"]["value"] for row in careers] == [2, 3]
    assert len({row["fields"]["display_name"]["value"] for row in careers}) == 1
    settings = case(catalog, "settings-ready")
    assert settings["career_id"] is None
    for name in ("installation_path", "database_path"):
        assert settings["data"]["fields"][name] == {"value": None, "unavailable_reason": "redacted"}
    for name in ("watchdog_running", "database_connected", "last_sync"):
        assert settings["data"]["fields"][name] == {"value": None, "unavailable_reason": "not_supplied"}


@pytest.mark.parametrize(("name", "path", "value", "rule"), [
    ("loading", ("state",), "partial", "shared state"),
    ("loading", ("synthetic",), False, "synthetic labeling"),
    ("loading", ("label",), "Live", "synthetic labeling"),
    ("loading", ("contract_version",), "production-v1", "contract version"),
    ("pilot-ready", ("source_authority",), "unresolved", "source authority"),
    ("pilot-ready", ("data", "fields", "missions", "value"), True, "numeric value"),
    ("pilot-ready", ("data", "fields", "missions", "value"), -1, "numeric value"),
    ("pilot-ready", ("data", "fields", "missions", "value"), None, "unavailable reason"),
    ("pilot-ready", ("data", "fields", "source_slot", "value"), 1, "persistent synthetic slot"),
    ("pilot-ready", ("data", "fields", "source_slot", "value"), 3, "snapshot slot identity"),
    ("pilot-partial-conflict", ("data", "fields", "service", "value"), "RFC", "must not carry a value"),
    ("pilot-partial-conflict", ("warnings",), [warning("partial_record")], "conflict warning"),
    ("pilot-unknown-freshness", ("warnings",), [], "unknown freshness warning"),
    ("pilot-stale", ("observed_at",), None, "stale timestamp"),
    ("pilot-stale", ("observed_at",), "2026-01-01T11:59:30Z", "stale timestamp"),
    ("pilot-stale", ("warnings",), [], "unavailable warning"),
    ("pilot-ready", ("observed_at",), "2025-12-31T12:00:00Z", "current freshness"),
    ("pilot-ready", ("observed_at",), "2026-01-02T12:00:00Z", "safe observation time"),
    ("pilot-ready", ("observed_at",), "2026-01-01T11:59:30", "UTC timestamp"),
    ("pilot-ready", ("observed_at",), "2026-02-30T11:59:30Z", "UTC timestamp"),
    ("missing-source", ("state",), "empty", "successful snapshot state"),
    ("missing-source", ("state",), "error", "sanitized query error"),
    ("error-query", ("reason",), "source_missing", "sanitized query error"),
    ("missing-career", ("career_id",), "synthetic-career-02", "does not require a career"),
    ("missions-ready", ("career_id",), "synthetic-career-03", "cross-career record"),
    ("diary-ready", ("data", "records", 0, "fields", "mission_id", "value"), "synthetic-mission-99", "mission ownership"),
])
def test_rejects_state_identity_and_freshness_regressions(catalog: dict[str, Any], name: str, path: tuple[Any, ...], value: Any, rule: str) -> None:
    target = case(catalog, name)
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(FixtureError, match=rule):
        validate_catalog(catalog)


def test_loading_cannot_reuse_payload_and_empty_requires_zero_records(catalog: dict[str, Any]) -> None:
    case(catalog, "loading")["data"] = deepcopy(case(catalog, "pilot-ready")["data"])
    with pytest.raises(FixtureError, match="no borrowed snapshot"):
        validate_catalog(catalog)
    case(catalog, "loading")["data"] = None
    case(catalog, "empty-records")["data"] = deepcopy(case(catalog, "missions-ready")["data"])
    with pytest.raises(FixtureError, match="empty means"):
        validate_catalog(catalog)


def test_expired_empty_collection_remains_stale(catalog: dict[str, Any]) -> None:
    retained = case(catalog, "pilot-stale")
    retained["data"] = deepcopy(case(catalog, "empty-records")["data"])
    validate_catalog(catalog)
    retained["state"] = "empty"
    retained["reason"] = None
    with pytest.raises(FixtureError, match="successful snapshot state"):
        validate_catalog(catalog)


@pytest.mark.parametrize("screen", ("MIS-02", "SQD-02", "RPT-02"))
@pytest.mark.parametrize("name", ("empty-records", "pilot-stale", "pilot-ready", "diary-ready"))
def test_detail_payload_requires_matching_subject_records(catalog: dict[str, Any], screen: str, name: str) -> None:
    detail = deepcopy(case(catalog, name))
    detail["screens"] = [screen]
    detail["subject_id"] = next(subject for _, target, subject in DETAIL_CASES if target == screen)
    if name == "pilot-stale":
        detail["data"] = deepcopy(case(catalog, "empty-records")["data"])
    with pytest.raises(FixtureError, match="detail screen requires an established subject"):
        validate_case(detail)


def test_generic_empty_fixture_does_not_target_subject_detail_screens(catalog: dict[str, Any]) -> None:
    assert not {"MIS-02", "SQD-02", "RPT-02"}.intersection(case(catalog, "empty-records")["screens"])


@pytest.mark.parametrize(("name", "screen", "subject_id"), DETAIL_CASES)
def test_retained_detail_preserves_subject_and_owner_field_scope(catalog: dict[str, Any], name: str, screen: str, subject_id: str) -> None:
    retained = case(catalog, "pilot-stale")
    retained["screens"] = [screen]
    retained["data"] = deepcopy(case(catalog, name)["data"])
    retained["subject_id"] = subject_id
    if name == "aircrew-detail-ready":
        retained["warnings"].insert(0, warning("partial_record"))
    validate_catalog(catalog)
    retained["data"]["records"][0]["fields"]["service"] = {"value": "RAF", "unavailable_reason": None}
    with pytest.raises(FixtureError, match="owner identity fields belong to payload"):
        validate_catalog(catalog)


@pytest.mark.parametrize(("name", "screen", "subject_id"), DETAIL_CASES)
def test_detail_selection_is_explicit_and_resolves_by_id(catalog: dict[str, Any], name: str, screen: str, subject_id: str) -> None:
    detail = case(catalog, name)
    assert screen in detail["screens"]
    assert detail.get("subject_id") == subject_id
    records = {record["id"]: record for record in detail["data"]["records"]}
    assert records[subject_id]["career_id"] == detail["career_id"]
    if len(records) > 1:
        assert subject_id != detail["data"]["records"][0]["id"]


@pytest.mark.parametrize(("name", "screen", "subject_id"), DETAIL_CASES)
def test_detail_rejects_absent_or_unmatched_selection(catalog: dict[str, Any], name: str, screen: str, subject_id: str) -> None:
    detail = deepcopy(case(catalog, name))
    detail["subject_id"] = None
    with pytest.raises(FixtureError, match="selected detail subject required"):
        validate_case(detail)
    detail["subject_id"] = subject_id.rsplit("-", 1)[0] + "-99"
    with pytest.raises(FixtureError, match="selected subject is not in payload"):
        validate_case(detail)


@pytest.mark.parametrize("name", NO_PAYLOAD_CASES)
@pytest.mark.parametrize("screen", ("OPR-01", "MIS-02"))
def test_selected_screen_transients_cannot_lose_career(catalog: dict[str, Any], name: str, screen: str) -> None:
    transient = deepcopy(case(catalog, name))
    transient["screens"] = [screen]
    with pytest.raises(FixtureError, match="selected-career context identity"):
        validate_case(transient)


@pytest.mark.parametrize("name", NO_PAYLOAD_CASES)
def test_global_and_selected_transients_have_distinct_context(catalog: dict[str, Any], name: str) -> None:
    global_case = case(catalog, name)
    assert set(global_case["screens"]) == {"APP-00", "SEL-01", "SYS-01"}
    assert global_case["career_id"] is None and global_case["data"] is None
    selected = case(catalog, name + "-selected")
    assert selected["career_id"] == "synthetic-career-02" and selected["data"] is None
    assert set(case(catalog, "empty-records")["screens"]) <= set(selected["screens"])
    assert not {"APP-00", "SEL-01", "SYS-01"}.intersection(selected["screens"])


@pytest.mark.parametrize("name", NO_PAYLOAD_CASES + ("careers-ready", "empty-global", "settings-ready"))
def test_global_screens_reject_selected_career(catalog: dict[str, Any], name: str) -> None:
    case(catalog, name)["career_id"] = "synthetic-career-02"
    with pytest.raises(FixtureError, match="global screen requires no selected career"):
        validate_catalog(catalog)


@pytest.mark.parametrize("screen", ("APP-00", "SEL-01", "SYS-01"))
def test_selected_snapshots_cannot_also_target_global_screens(catalog: dict[str, Any], screen: str) -> None:
    selected = case(catalog, "pilot-ready")
    selected["screens"] = [target for target in SCREENS if target in selected["screens"] or target == screen]
    with pytest.raises(FixtureError, match="global screen requires no selected career"):
        validate_catalog(catalog)


@pytest.mark.parametrize(("name", "screen", "subject_id"), LIST_CASES)
@pytest.mark.parametrize("include_detail", (False, True))
def test_primary_screens_reject_detail_subject(catalog: dict[str, Any], name: str, screen: str, subject_id: str, include_detail: bool) -> None:
    listing = deepcopy(case(catalog, name))
    listing["screens"] = [screen, screen.replace("01", "02")] if include_detail else [screen]
    listing["subject_id"] = subject_id
    with pytest.raises(FixtureError, match="subject requires"):
        validate_case(listing)


@pytest.mark.parametrize(("name", "screen", "subject_id"), LIST_CASES)
def test_lists_and_details_have_separate_selection_context(catalog: dict[str, Any], name: str, screen: str, subject_id: str) -> None:
    listing = case(catalog, name)
    assert listing["screens"] == [screen] and listing["subject_id"] is None
    detail_name = next(name for name, _, subject in DETAIL_CASES if subject == subject_id)
    detail = case(catalog, detail_name)
    assert detail["screens"] == [screen.replace("01", "02")]
    assert detail["subject_id"] == subject_id
    assert detail["career_id"] == listing["career_id"]
    assert detail["data"] == listing["data"]


def test_each_fixture_applies_to_each_intended_screen(catalog: dict[str, Any]) -> None:
    for fixture in catalog["fixtures"]:
        for screen in fixture["screens"]:
            applied = deepcopy(fixture)
            applied["screens"] = [screen]
            validate_case(applied)


@pytest.mark.parametrize("name", ("missions-ready", "squadron-ready", "reports-ready", "diary-ready", "settings-ready"))
@pytest.mark.parametrize(("field", "value"), (
    ("service", "RAF"), ("source_slot", 3), ("squadron", "Synthetic Squadron Cedar"),
))
def test_nested_records_reject_owner_identity_fields(catalog: dict[str, Any], name: str, field: str, value: Any) -> None:
    case(catalog, name)["data"]["records"][0]["fields"][field] = {"value": value, "unavailable_reason": None}
    with pytest.raises(FixtureError, match="owner identity fields belong to payload"):
        validate_catalog(catalog)


@pytest.mark.parametrize("name", ("missions-ready", "reports-ready", "diary-ready", "settings-ready"))
def test_non_roster_records_reject_nested_owner_name(catalog: dict[str, Any], name: str) -> None:
    case(catalog, name)["data"]["records"][0]["fields"]["display_name"] = {"value": "Synthetic Pilot Birch", "unavailable_reason": None}
    with pytest.raises(FixtureError, match="owner identity fields belong to payload"):
        validate_catalog(catalog)


@pytest.mark.parametrize(("name", "screen", "subject_id"), DETAIL_CASES)
@pytest.mark.parametrize("phase", ("loading", "error-query", "unavailable-source"))
def test_detail_transitions_preserve_selected_subject(catalog: dict[str, Any], name: str, screen: str, subject_id: str, phase: str) -> None:
    transient = case(catalog, phase)
    transient.update(screens=[screen], career_id=case(catalog, name)["career_id"], subject_id=subject_id)
    validate_catalog(catalog)
    assert transient["data"] is None and transient["observed_at"] is None
    transient["career_id"] = "synthetic-career-03"
    with pytest.raises(FixtureError, match="selected subject ownership"):
        validate_catalog(catalog)


@pytest.mark.parametrize(("name", "screen", "subject_id"), DETAIL_CASES)
def test_transient_subject_must_be_known_and_have_the_right_kind(catalog: dict[str, Any], name: str, screen: str, subject_id: str) -> None:
    transient = case(catalog, "loading")
    transient.update(screens=[screen], career_id=case(catalog, name)["career_id"], subject_id=subject_id.rsplit("-", 1)[0] + "-99")
    with pytest.raises(FixtureError, match="selected subject ownership"):
        validate_catalog(catalog)
    transient["subject_id"] = "synthetic-diary-01"
    with pytest.raises(FixtureError, match="synthetic identity"):
        validate_case(transient)


def test_record_selection_cannot_escape_its_detail_scope(catalog: dict[str, Any]) -> None:
    pilot = deepcopy(case(catalog, "pilot-ready"))
    pilot["subject_id"] = "synthetic-mission-02"
    with pytest.raises(FixtureError, match="subject requires detail-only screens"):
        validate_case(pilot)
    missing = deepcopy(case(catalog, "missing-career"))
    missing["screens"] = ["MIS-02"]
    missing["subject_id"] = "synthetic-mission-02"
    with pytest.raises(FixtureError, match="unselected career cannot carry a subject"):
        validate_case(missing)


@pytest.mark.parametrize("name", ("pilot-ready", "pilot-stale", "pilot-unknown-freshness", "empty-records"))
@pytest.mark.parametrize(("field", "value"), (
    ("service", "RNAS"), ("service", "RAF"),
    ("display_name", "Synthetic Pilot Birch"), ("source_slot", 3),
))
def test_known_career_identity_cannot_disagree_with_selector(catalog: dict[str, Any], name: str, field: str, value: Any) -> None:
    case(catalog, name)["data"]["fields"][field] = {"value": value, "unavailable_reason": None}
    with pytest.raises(FixtureError, match="career identity|snapshot slot identity"):
        validate_catalog(catalog)


def test_retained_selector_cannot_override_the_identity_anchor(catalog: dict[str, Any]) -> None:
    retained = case(catalog, "pilot-stale")
    retained.update(screens=["SEL-01"], career_id=None, data=deepcopy(case(catalog, "careers-ready")["data"]))
    retained["data"]["records"][0]["fields"]["service"]["value"] = "RNAS"
    with pytest.raises(FixtureError, match="career identity"):
        validate_catalog(catalog)


def test_selecting_another_career_keeps_its_own_identity(catalog: dict[str, Any]) -> None:
    pilot = case(catalog, "pilot-ready")
    pilot["career_id"] = "synthetic-career-03"
    pilot["data"]["fields"]["source_slot"]["value"] = 3
    pilot["data"]["fields"]["service"]["value"] = "RAF"
    validate_catalog(catalog)


def test_unavailable_source_can_retain_safe_time_but_never_claim_current(catalog: dict[str, Any]) -> None:
    retained = case(catalog, "pilot-stale")
    retained.update(reason="source_unavailable", observed_at="2026-01-01T11:59:30Z", freshness="unknown", warnings=[warning("freshness_unknown"), warning("source_unavailable")])
    validate_catalog(catalog)
    retained["freshness"] = "current"
    with pytest.raises(FixtureError, match="unavailable warning and freshness"):
        validate_catalog(catalog)


def test_old_ready_snapshot_cannot_hide_behind_unknown_freshness(catalog: dict[str, Any]) -> None:
    case(catalog, "pilot-ready").update(observed_at="2025-12-31T12:00:00Z", freshness="unknown", warnings=[warning("freshness_unknown")])
    with pytest.raises(FixtureError, match="expired successful snapshot"):
        validate_catalog(catalog)


@pytest.mark.parametrize(("observed", "valid"), (
    ("2026-01-01T12:00:00Z", True),
    ("2026-01-01T11:59:00Z", True),
    ("2026-01-01T11:58:59Z", False),
))
def test_freshness_boundary_uses_the_fixed_clock(catalog: dict[str, Any], observed: str, valid: bool) -> None:
    case(catalog, "pilot-ready")["observed_at"] = observed
    if valid:
        validate_catalog(catalog)
    else:
        with pytest.raises(FixtureError, match="current freshness"):
            validate_catalog(catalog)


def test_current_ready_data_cannot_display_a_stale_or_failed_warning(catalog: dict[str, Any]) -> None:
    case(catalog, "pilot-ready")["warnings"] = [warning("snapshot_expired")]
    with pytest.raises(FixtureError, match="warnings must match"):
        validate_catalog(catalog)


@pytest.mark.parametrize("service", ("RFC", "RNAS", "RAF"))
def test_supported_services_remain_distinct(catalog: dict[str, Any], service: str) -> None:
    pilot = case(catalog, "pilot-ready")
    pilot["data"]["fields"]["service"]["value"] = service
    validate_case(pilot)
    assert pilot["data"]["fields"]["service"]["value"] == service


@pytest.mark.parametrize("value", (
    "Unapproved Example Person", "Synthetic Unapproved Example Person",
    r"C:\Users\Example\WoFF", "/home/example/woff", r"\\example-host\game",
    "DEMO-ONLY-NOT-A-LICENSE", "<SyntheticWoFFPayload />", "U3ludGhldGlj",
))
def test_closed_text_vocabulary_rejects_unapproved_content(catalog: dict[str, Any], value: str) -> None:
    case(catalog, "pilot-ready")["data"]["fields"]["display_name"]["value"] = value
    with pytest.raises(FixtureError, match="unapproved display text"):
        validate_catalog(catalog)


@pytest.mark.parametrize("key", ("activation_key", "license", "raw_payload", "log", "database", "screenshot"))
def test_unknown_payload_fields_are_rejected_even_when_redacted(catalog: dict[str, Any], key: str) -> None:
    case(catalog, "pilot-ready")["data"]["fields"][key] = {"value": None, "unavailable_reason": "redacted"}
    with pytest.raises(FixtureError, match="unapproved field"):
        validate_catalog(catalog)


@pytest.mark.parametrize("location", ("envelope", "payload", "record", "field", "warning"))
def test_unknown_nested_keys_cannot_smuggle_raw_content(catalog: dict[str, Any], location: str) -> None:
    diary = case(catalog, "diary-ready")
    targets = {
        "envelope": diary,
        "payload": diary["data"],
        "record": diary["data"]["records"][0],
        "field": diary["data"]["records"][0]["fields"]["narrative"],
        "warning": case(catalog, "error-query")["warnings"][0],
    }
    targets[location]["raw_payload"] = "SYNTHETIC REJECTED PAYLOAD"
    with pytest.raises(FixtureError, match="shape"):
        validate_catalog(catalog)


@pytest.mark.parametrize("collection", ("fixtures", "records", "warnings"))
def test_order_and_duplicates_are_rejected(catalog: dict[str, Any], collection: str) -> None:
    if collection == "fixtures":
        rows = catalog["fixtures"]
    elif collection == "records":
        rows = case(catalog, "missions-ready")["data"]["records"]
    else:
        rows = case(catalog, "pilot-partial-conflict")["warnings"]
    rows.reverse()
    with pytest.raises(FixtureError, match="order"):
        validate_catalog(catalog)
    rows.reverse()
    rows[1] = deepcopy(rows[0])
    with pytest.raises(FixtureError, match="order"):
        validate_catalog(catalog)


@pytest.fixture
def fixture_copy(tmp_path: Path) -> Path:
    directory = tmp_path / "ui_states"
    shutil.copytree(FIXTURES, directory)
    return directory


@pytest.mark.parametrize("filename", ("campaign.db", "database.sqlite", "Mission.log", "Pilot1Dossier.txt", "capture.png", "raw.xml", "extra.json"))
def test_unapproved_files_are_rejected(fixture_copy: Path, filename: str) -> None:
    (fixture_copy / filename).write_bytes(b"SYNTHETIC INVALID ARTIFACT")
    with pytest.raises(FixtureError, match="unapproved fixture artifact"):
        load_catalog(fixture_copy)


def test_symlinked_catalog_is_rejected(fixture_copy: Path, tmp_path: Path) -> None:
    source = fixture_copy / "catalog.json"
    target = tmp_path / "target.json"
    source.rename(target)
    try:
        source.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")
    with pytest.raises(FixtureError, match="fixture files only"):
        load_catalog(fixture_copy)


@pytest.mark.parametrize(("content", "rule"), (
    (b"\xff", "UTF-8 JSON"),
    (b'{"catalog_version":1,"catalog_version":1}', "duplicate JSON key"),
    (b'{"value":NaN}', "non-finite JSON"),
    (b'{"value":Infinity}', "non-finite JSON"),
))
def test_invalid_encoding_and_json_are_rejected(fixture_copy: Path, content: bytes, rule: str) -> None:
    (fixture_copy / "catalog.json").write_bytes(content)
    with pytest.raises(FixtureError, match=rule):
        load_catalog(fixture_copy)


@pytest.mark.parametrize("content", (b"\xff", b"SYNTHETIC IMAGE RENAMED AS MARKDOWN"))
def test_inventory_must_be_utf8_text_not_a_renamed_binary(fixture_copy: Path, content: bytes) -> None:
    (fixture_copy / "README.md").write_bytes(content)
    with pytest.raises(FixtureError, match="inventory"):
        load_catalog(fixture_copy)


@pytest.mark.parametrize(("change", "rejected"), (
    ("append", "Unapproved Example Person"),
    ("append", r"C:\Users\Example\WoFF"),
    ("insert", "DEMO-ONLY-NOT-A-LICENSE"),
    ("insert", "<!-- SYNTHETIC UNREVIEWED RAW PAYLOAD -->"),
    ("replace", "Synthetic Unapproved Example Person"),
))
def test_entire_inventory_rejects_unapproved_text(fixture_copy: Path, capsys: pytest.CaptureFixture[str], change: str, rejected: str) -> None:
    path = fixture_copy / "README.md"
    approved = path.read_text(encoding="utf-8")
    if change == "append":
        candidate = approved + "\n" + rejected + "\n"
    elif change == "insert":
        heading, body = approved.split("\n", 1)
        candidate = heading + "\n" + rejected + "\n" + body
    else:
        candidate = approved.replace("Every envelope", rejected, 1)
    path.write_text(candidate, encoding="utf-8")
    with pytest.raises(FixtureError, match="inventory"):
        load_catalog(fixture_copy)
    assert main([str(fixture_copy)]) == 1
    output = capsys.readouterr()
    assert "inventory" in output.err
    assert rejected not in output.err + output.out
    assert str(fixture_copy) not in output.err + output.out


def test_inventory_cannot_omit_approved_privacy_guidance(fixture_copy: Path) -> None:
    path = fixture_copy / "README.md"
    approved = path.read_text(encoding="utf-8")
    path.write_text(approved.split("## Determinism and privacy", 1)[0], encoding="utf-8")
    with pytest.raises(FixtureError, match="inventory"):
        load_catalog(fixture_copy)


def test_inventory_accepts_windows_newlines(fixture_copy: Path, catalog: dict[str, Any]) -> None:
    path = fixture_copy / "README.md"
    approved = path.read_text(encoding="utf-8")
    path.write_bytes(approved.replace("\n", "\r\n").encode("utf-8"))
    assert load_catalog(fixture_copy) == catalog


def test_rejection_does_not_echo_paths_or_raw_diagnostics(catalog: dict[str, Any], fixture_copy: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rejected = "SYNTHETIC REJECTED VALUE C:\\Users\\Example\\WoFF"
    case(catalog, "error-query")["warnings"][0]["message"] = rejected
    (fixture_copy / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    assert main([str(fixture_copy)]) == 1
    output = capsys.readouterr()
    assert "unapproved diagnostic text" in output.err
    assert rejected not in output.err + output.out
    assert str(fixture_copy) not in output.err + output.out


def test_validator_runs_without_site_packages_database_network_or_application() -> None:
    driver = r'''
import runpy
import sys
class BlockIntegrations:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'sqlite3', '_sqlite3', 'socket', '_socket', 'http', 'woff', 'watchdog', 'PySide6', 'PyQt6', 'PySide2', 'PyQt5'} or fullname.startswith('urllib.request'):
            raise AssertionError('forbidden integration import')
def audit(event, args):
    if event.startswith(('socket.', 'sqlite3.')):
        raise AssertionError('forbidden integration event')
    if event == 'open' and isinstance(args[0], str) and args[0].lower().endswith(('.db', '.sqlite', '.log', '.xml', '.txt')):
        raise AssertionError('forbidden source file')
sys.meta_path.insert(0, BlockIntegrations())
sys.addaudithook(audit)
script = sys.argv[1]
sys.argv = [script]
runpy.run_path(script, run_name='__main__')
'''
    result = subprocess.run([sys.executable, "-I", "-S", "-c", driver, str(ROOT / "scripts" / "validate_ui_fixtures.py")], capture_output=True, text=True, cwd=ROOT, check=False)
    assert result.returncode == 0, result.stderr
    assert "30 synthetic cases, 6 shared states" in result.stdout


def table(text: str, marker: str) -> list[list[str]]:
    section = text.split(f"<!-- {marker}:start -->", 1)[1].split(f"<!-- {marker}:end -->", 1)[0]
    return [[cell.strip().strip('`') for cell in line.strip().strip('|').split('|')] for line in section.splitlines() if line.startswith('|')][2:]


def test_missing_career_guidance_covers_every_target_screen(catalog: dict[str, Any]) -> None:
    document = (ROOT / "docs" / "ui" / "screen-state-matrix.md").read_text(encoding="utf-8")
    missing = {row[0]: row[4] for row in table(document, "state-matrix")}
    for screen in case(catalog, "missing-career")["screens"]:
        assert "select a career" in missing[screen].lower(), screen
    assert "career_not_selected" in missing["SEL-01"]
    assert "source_missing" in missing["SEL-01"]
    assert "open data status" in missing["SEL-01"].lower()


def test_documented_matrix_inventory_and_archived_visual_aliases(catalog: dict[str, Any]) -> None:
    document = (ROOT / "docs" / "ui" / "screen-state-matrix.md").read_text(encoding="utf-8")
    matrix = table(document, "state-matrix")
    assert [row[0] for row in matrix] == list(SCREENS)
    assert all(len(row) == 7 and all(row) for row in matrix)
    assert "| `loading` | `ready` | `empty` | `missing` | `stale/unavailable` | `error` |" in document
    inventory = (FIXTURES / "README.md").read_text(encoding="utf-8")
    entries = [line for line in inventory.splitlines() if line.startswith('| `')]
    assert len(entries) == len(catalog["fixtures"])
    for fixture, line in zip(catalog["fixtures"], entries):
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        assert cells[0] == f"`{fixture['id']}`"
        assert cells[1] == ", ".join(f"`{screen}`" for screen in fixture["screens"])
        assert cells[2] == f"`{fixture['state']}`"
    aliases = {row[0]: row[1] for row in table(document, "visual-aliases")}
    source = (ROOT / "docs/ui/evidence/ui-v2-site-2026-09-01-audit-4/source/app/page.tsx").read_text(encoding="utf-8")
    scenarios = source.split("const fixtureScenarios:", 1)[1].split("const fixtureSurfaces:", 1)[0]
    assert set(aliases) == set(re.findall(r'id: "([a-z-]+)"', scenarios))
    assert set(aliases.values()) == SHARED_STATES
    assert aliases["partial"] == aliases["unknown"] == aliases["zeroes"] == "ready"
    assert aliases["stale"] == "stale/unavailable"
    assert "Synthetic" in source
