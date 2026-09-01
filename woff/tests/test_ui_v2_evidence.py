"""Replay real Audit 4 observations and reject the six reviewed regressions.

These tests never claim to browse the public Site. The pinned browser driver
produces fresh observations; this suite verifies their semantics and hashes.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scripts.validate_ui_v2_evidence import (
    EVIDENCE,
    EvidenceError,
    PROFILES,
    SCREENS,
    STATES,
    STATUS_LABELS,
    contrast_ratio,
    main,
    validate_evidence,
    verify_manifest,
)


@pytest.fixture(scope="module")
def recorded() -> dict[str, Any]:
    return json.loads((EVIDENCE / "conformance-measurements.json").read_text(encoding="utf-8"))


@pytest.fixture
def capture(recorded: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(recorded)


def state(capture: dict[str, Any], name: str) -> dict[str, Any]:
    return next(row for row in capture["rendered"]["states"] if row["state"] == name)


def screen(capture: dict[str, Any], name: str = "DOS-01", profile: str = "desktop-200") -> dict[str, Any]:
    return next(row for row in capture["rendered"]["surfaces"] if row["screen"] == name and row["profile"] == profile)


def reject(capture: dict[str, Any], reason: str) -> None:
    with pytest.raises(EvidenceError, match=reason):
        validate_evidence(capture)


def test_real_rendered_observations_and_source_hashes(recorded: dict[str, Any]) -> None:
    validate_evidence(recorded)
    assert len(verify_manifest()) == 64
    assert main([]) == 0


@pytest.mark.parametrize("profile", tuple(PROFILES))
@pytest.mark.parametrize("measurement", ("width", "height", "rail", "columns", "side"))
def test_rejects_inert_or_incorrect_scale(capture: dict[str, Any], profile: str, measurement: str) -> None:
    row = screen(capture, profile=profile)
    if measurement in ("width", "height"):
        row["canvas"][measurement] += 100
    elif measurement == "rail":
        row["rail"]["width"] += 24
    elif measurement == "columns":
        row["statsColumns"] = 1
    else:
        row["sideAfterLedger"] = not row["sideAfterLedger"]
    reject(capture, "canvas|reflow|column")


@pytest.mark.parametrize("collection", ("surfaces", "states", "statuses", "keyboard"))
@pytest.mark.parametrize("duplicate", (False, True))
def test_requires_exact_case_coverage(capture: dict[str, Any], collection: str, duplicate: bool) -> None:
    rows = capture["rendered"][collection]
    if duplicate:
        rows[-1] = deepcopy(rows[0])
    else:
        rows.pop()
    reject(capture, "coverage")


@pytest.mark.parametrize("screen_id", SCREENS)
def test_every_screen_rejects_forbidden_control(capture: dict[str, Any], screen_id: str) -> None:
    control = deepcopy(screen(capture, screen_id)["controls"][-1])
    control.update(name="Delete campaign", intent="navigate")
    screen(capture, screen_id)["controls"].append(control)
    reject(capture, "prohibited")


@pytest.mark.parametrize("name", ("Edit settings", "Import file", "Reset configuration", "Launch simulator", "Start session", "Stop session", "Save record", "Export report", "Repair database", "Confirm claim", "Regenerate report"))
def test_rejects_each_prohibited_action_class(capture: dict[str, Any], name: str) -> None:
    screen(capture)["controls"][-1]["name"] = name
    reject(capture, "prohibited")


@pytest.mark.parametrize("field,value", (("intent", "unknown"), ("role", "textbox"), ("href", "https://example.invalid/write"), ("tabIndex", 1), ("disabled", True)))
def test_rejects_unreviewed_control(capture: dict[str, Any], field: str, value: Any) -> None:
    screen(capture)["controls"][-1][field] = value
    reject(capture, "control|action|role|tabindex")


@pytest.mark.parametrize("profile", tuple(PROFILES))
@pytest.mark.parametrize("kind", ("narrow", "short", "primary", "unclassified"))
def test_measures_every_profile_target(capture: dict[str, Any], profile: str, kind: str) -> None:
    row = screen(capture, profile=profile)
    control = row["controls"][1] if kind in ("primary", "unclassified") else row["controls"][-1]
    if kind == "unclassified":
        control["primary"] = False
    else:
        control["rect"]["width" if kind == "narrow" else "height"] = 39 if kind == "primary" else 31
    reject(capture, "target")


@pytest.mark.parametrize("value", (True, None, float("nan"), float("inf"), "40"))
def test_target_requires_real_finite_number(capture: dict[str, Any], value: Any) -> None:
    screen(capture)["controls"][1]["rect"]["height"] = value
    reject(capture, "numeric")


@pytest.mark.parametrize("screen_id", ("DOS-01", "MIS-01", "MIS-02", "SQD-01", "SQD-02", "RPT-01", "RPT-02"))
def test_tab_must_continue_past_shell_through_final_control(capture: dict[str, Any], screen_id: str) -> None:
    sequence = next(k for k in capture["rendered"]["keyboard"] if k["screen"] == screen_id and k["state"] == "complete")
    sequence["stops"] = sequence["stops"][:10]
    reject(capture, "Tab")


@pytest.mark.parametrize("kind", ("reordered", "invisible", "offscreen", "heading", "thin", "low-contrast"))
def test_keyboard_order_focus_and_geometry(capture: dict[str, Any], kind: str) -> None:
    stops = capture["rendered"]["keyboard"][3]["stops"]
    if kind == "reordered":
        stops[-2], stops[-1] = stops[-1], stops[-2]
    elif kind == "invisible":
        stops[-1]["visibleFocus"] = False
    elif kind == "offscreen":
        stops[-1]["inViewport"] = False
    elif kind == "heading":
        stops[-1]["tag"] = "h1"
    elif kind == "thin":
        stops[-1]["boxShadow"] = stops[-1]["boxShadow"].replace("3px", "1px")
    else:
        stops[-1]["boxShadow"] = stops[-1]["boxShadow"].replace("125, 90, 24", "247, 242, 230")
    reject(capture, "Tab|focus")


@pytest.mark.parametrize("screen_id", ("OPR-01", "MIS-01", "SQD-01", "JRN-01", "RPT-01"))
def test_inventory_cannot_replace_or_omit_record(capture: dict[str, Any], screen_id: str) -> None:
    screen(capture, screen_id)["controls"][-1]["name"] = "Unreviewed read-only shortcut"
    reject(capture, "inventory|reading order")


@pytest.mark.parametrize("state_id", ("loading", "no-career", "missing", "truncated", "unsupported", "unreadable", "error", "unavailable"))
def test_absent_states_never_borrow_values(capture: dict[str, Any], state_id: str) -> None:
    state(capture, state_id)["fields"] = deepcopy(state(capture, "complete")["fields"])
    reject(capture, "borrowed data")


@pytest.mark.parametrize("state_id", STATES)
def test_every_state_rejects_private_diagnostics(capture: dict[str, Any], state_id: str) -> None:
    state(capture, state_id)["mainText"] += " Traceback C:\\private\\Pilot1Dossier.txt"
    reject(capture, "private diagnostic")


@pytest.mark.parametrize("kind", ("empty-as-missing", "false-zero", "unknown-as-zero", "partial", "no-retry", "stale-as-current", "missing-as-empty"))
def test_state_specific_semantics(capture: dict[str, Any], kind: str) -> None:
    if kind == "empty-as-missing":
        state(capture, "empty")["mainText"] = "Record missing"
    elif kind == "false-zero":
        state(capture, "empty")["fields"][0]["display"] = "0"
    elif kind == "unknown-as-zero":
        state(capture, "unknown")["fields"][0]["display"] = "0"
    elif kind == "partial":
        state(capture, "partial")["fields"][4]["state"] = "known"
    elif kind == "no-retry":
        state(capture, "error")["controls"].pop(-2)
    elif kind == "stale-as-current":
        state(capture, "stale")["mainText"] = state(capture, "stale")["mainText"].replace("14 AUG 1917", "15 AUG 1917")
    else:
        state(capture, "missing")["counts"]["emptyCollections"] = 1
    reject(capture, "empty|zero|unknown|partial|actions|snapshot|borrowed")


@pytest.mark.parametrize("case", tuple(STATUS_LABELS))
@pytest.mark.parametrize("field", ("visible", "accessible", "displayText"))
def test_lossless_status_label_on_screen_and_accessibility(capture: dict[str, Any], case: str, field: str) -> None:
    row = next(s for s in capture["rendered"]["statuses"] if s["case"] == case)
    row["status"][field] = "Wounded" if "Wounded" in case else "Unrecognized"
    reject(capture, "status label")


def test_future_status_requires_explanation(capture: dict[str, Any]) -> None:
    capture["rendered"]["statuses"][-1]["status"]["notice"] = "Information"
    reject(capture, "future status")


@pytest.mark.parametrize("action", ("Retry view", "Refresh snapshot", "View data status", "Select career"))
def test_action_must_reach_correct_destination(capture: dict[str, Any], action: str) -> None:
    row = next(a for a in capture["rendered"]["actions"] if a["action"] == action)
    row["after"]["screen"] = "MIS-01"
    reject(capture, "surface|destination")


@pytest.mark.parametrize("kind", ("short", "invisible", "order", "wrap", "restore"))
def test_entire_fixture_dialog(capture: dict[str, Any], kind: str) -> None:
    dialog = capture["rendered"]["dialog"]
    if kind == "short":
        dialog["controls"][-1]["height"] = 39
    elif kind == "invisible":
        dialog["stops"][-1]["visibleFocus"] = False
    elif kind == "order":
        dialog["stops"].pop()
    elif kind == "wrap":
        dialog["forward"] = "Outside dialog"
    else:
        dialog["restored"] = "Operations"
    reject(capture, "dialog|restoration")


@pytest.mark.parametrize("index", (0, 1, 2))
@pytest.mark.parametrize("phase", ("after", "reopened"))
def test_contextual_identity_isolation(capture: dict[str, Any], index: int, phase: str) -> None:
    row = capture["rendered"]["isolation"]["contexts"][index]
    row[phase]["mainText"] += " " + row["oldReference"]
    reject(capture, "old detail leaked")


def test_sparse_slot_does_not_derive_from_list_index(capture: dict[str, Any]) -> None:
    sparse = capture["rendered"]["isolation"]["sparse"]
    next(c for c in sparse["controls"] if c["inMain"])["name"] = "WoFF Pilot 1"
    reject(capture, "renumbered")


@pytest.mark.parametrize("kind", ("duplicate", "bounds", "minimum", "unmeasured", "non-text"))
def test_contrast_replay_rejects_false_pass(capture: dict[str, Any], kind: str) -> None:
    paints = capture["contrast"]["text"]
    if kind == "duplicate":
        paints[-1] = deepcopy(paints[0])
    elif kind == "bounds":
        paints[0]["lowest"][0]["backgroundBounds"] = [[244, 244], [239, 239], [226, 226]]
    elif kind == "minimum":
        paints[0]["minimum"] = 20
    elif kind == "unmeasured":
        paints[0]["measured"] = 0
    else:
        capture["contrast"]["boundaries"][0]["boundaries"][0]["ratioLowerBound"] = 21
    reject(capture, "contrast|paint")


def test_contrast_calculation_is_not_a_stored_pass_flag() -> None:
    assert contrast_ratio([0, 0, 0], [[255, 255]] * 3) == 21
    assert contrast_ratio([128, 128, 128], [[0, 255]] * 3) == 1
    with pytest.raises(EvidenceError):
        contrast_ratio([256, 0, 0], [[255, 255]] * 3)


@pytest.mark.parametrize("kind", ("source", "revision", "deployment", "missing"))
def test_published_source_provenance(capture: dict[str, Any], kind: str) -> None:
    if kind == "source":
        capture["sourceFiles"]["app/page.tsx"] = "not-a-hash"
    elif kind == "revision":
        capture["evidenceRevision"] = "AUDIT-3"
    elif kind == "deployment":
        capture["deployment"]["status"] = "pending"
    else:
        del capture["rendered"]["surfaces"][0]["canvas"]
    reject(capture, "source|revision|deployment|malformed")


def test_manifest_rejects_corrupt_bytes(tmp_path: Path) -> None:
    (tmp_path / "payload").write_text("tampered", encoding="ascii")
    (tmp_path / "SHA256SUMS").write_text("0" * 64 + "  payload\n", encoding="ascii")
    with pytest.raises(EvidenceError, match="checksum mismatch"):
        verify_manifest(tmp_path)


def test_manifest_rejects_path_escape(tmp_path: Path) -> None:
    (tmp_path / "SHA256SUMS").write_text("0" * 64 + "  ../payload\n", encoding="ascii")
    with pytest.raises(EvidenceError, match="unsafe"):
        verify_manifest(tmp_path)
