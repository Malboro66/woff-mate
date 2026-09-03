from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
STANDARD_PATH = REPOSITORY_ROOT / "docs" / "ui" / "ui-development-standard.md"


def _standard() -> str:
    return STANDARD_PATH.read_text(encoding="utf-8")


def test_ui_development_standard_exists_and_preserves_repository_authority() -> None:
    standard = _standard()

    assert "## Authority hierarchy" in standard
    assert "External references are advisory" in standard
    assert "## Closed-issue safety" in standard
    assert "does not reopen" in standard
    assert "#79" in standard
    assert "#80" in standard


def test_ui_reference_stack_is_classified_without_authorizing_runtime_adoption() -> None:
    standard = _standard()

    for reference in (
        "designsystems.one",
        "designsystemchecklist.com",
        "open-props.style",
        "utopia.fyi",
        "component.gallery",
        "coss.com",
        "reui.io",
        "interface.rauno.me",
        "ui-skills.com",
        "vibeprompts.dev",
        "iconcreator.dev",
        "kinetics.colorion.co",
        "motion-primitives.com",
        "bg.ibelick.com",
    ):
        assert reference in standard

    assert "## Runtime and dependency guard" in standard
    for forbidden_implicit_adoption in (
        "React",
        "Tailwind",
        "shadcn",
        "PySide6",
        "PyQt",
    ):
        assert forbidden_implicit_adoption in standard

    assert "proposed, not accepted" in standard


def test_ui_standard_preserves_state_accessibility_motion_and_privacy_contracts() -> None:
    standard = _standard()

    for state in (
        "`loading`",
        "`ready`",
        "`empty`",
        "`missing`",
        "`stale/unavailable`",
        "`error`",
    ):
        assert state in standard

    assert "4.5:1" in standard
    assert "3:1" in standard
    assert "100%, 125%, 150%, and 200%" in standard
    assert "reduced-motion" in standard
    assert "real player or campaign data" in standard
    assert "activation/license information" in standard
    assert "unredacted screenshots" in standard


def test_ui_standard_records_bounded_machine_readable_token_follow_up() -> None:
    standard = _standard()

    assert "## Q0: machine-readable design tokens" in standard
    assert "not a dedicated machine-readable token artifact" in standard
    assert "does **not** introduce a token pipeline" in standard
    assert "separate narrowly scoped follow-up is recommended" in standard


def test_ui_standard_keeps_component_research_toolkit_independent() -> None:
    standard = _standard()

    assert "## Component research record" in standard
    assert "toolkit-independent behavior" in standard
    assert "external implementation -> user behavior -> states -> semantics -> accessibility -> toolkit-independent contract" in standard
    assert "## Project-graph and release-gate boundary" in standard
    assert "does not add #135" in standard
