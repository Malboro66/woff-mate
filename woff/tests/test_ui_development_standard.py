from __future__ import annotations

from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
STANDARD_PATH = REPOSITORY_ROOT / "docs" / "ui" / "ui-development-standard.md"
GRAPH_PATH = REPOSITORY_ROOT / "docs" / "architecture" / "project-graph.yaml"
EVALS_PATH = REPOSITORY_ROOT / "docs" / "engineering" / "evals.md"


def _standard() -> str:
    return STANDARD_PATH.read_text(encoding="utf-8")


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _graph() -> dict[str, object]:
    graph = yaml.safe_load(GRAPH_PATH.read_text(encoding="utf-8"))
    assert isinstance(graph, dict)
    return graph


def test_ui_development_standard_exists_and_preserves_repository_authority() -> None:
    standard = _standard()

    assert "## Authority hierarchy" in standard
    assert "External references are advisory" in standard
    hierarchy = standard.split("## Authority hierarchy", 1)[1].split(
        "### Closed-issue safety", 1
    )[0]
    normalized_hierarchy = _normalized(hierarchy)
    assert normalized_hierarchy.index(
        "Repository instructions and governance requirements"
    ) < (
        normalized_hierarchy.index(
            "Current `main` and deterministically tested behavior"
        )
    )
    assert "Python 3.10" in normalized_hierarchy
    assert (
        "historical, current-main, and reproduction evidence" in normalized_hierarchy
    )
    assert (
        "never authorizes violating the normative rules above" in normalized_hierarchy
    )
    assert "current `main` and its CI still define the final technical state" in (
        normalized_hierarchy
    )
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
    assert (
        "status is always expressed with visible text plus an icon, never color alone"
        in _normalized(standard)
    )
    assert "real player or campaign data" in standard
    assert "activation/license information" in standard
    assert "unredacted screenshots" in standard


def test_ui_standard_records_bounded_machine_readable_token_follow_up() -> None:
    standard = _standard()

    assert "## Machine-readable design-token assessment" in standard
    assert "## Q0: machine-readable design tokens" not in standard
    assert "not a dedicated machine-readable token artifact" in standard
    assert "does **not** introduce a token pipeline" in standard
    assert "separate narrowly scoped follow-up is recommended" in " ".join(
        standard.split()
    )


def test_ui_standard_keeps_component_research_toolkit_independent() -> None:
    standard = _standard()

    assert "## Component research record" in standard
    assert "toolkit-independent behavior" in standard
    assert "external implementation -> user behavior -> states -> semantics -> accessibility -> toolkit-independent contract" in standard
    assert "## Project-graph and release-gate boundary" in standard
    assert "does not add #135 to an aggregate release cycle" in _normalized(standard)


def test_ui_policy_is_registered_without_becoming_a_cycle_member() -> None:
    graph = _graph()
    invariants = graph["invariants"]
    evals = graph["evals"]
    work_items = graph["work_items"]
    cycles = graph["cycles"]
    assert isinstance(invariants, dict)
    assert isinstance(evals, dict)
    assert isinstance(work_items, dict)
    assert isinstance(cycles, dict)

    assert invariants["UI-GOV-001"] == {
        "statement": (
            "UI research, design, review, and agent-assisted work remains "
            "subordinate to repository governance and preserves the approved "
            "accessibility, privacy, provenance, reduced-motion, and runtime "
            "dependency boundaries."
        ),
        "enforced_by": ["woff/tests/test_ui_development_standard.py"],
    }
    assert evals["EVAL-UI-POLICY-001"] == {
        "work_items": ["issue-135"],
        "status": "implemented",
        "evidence": (
            "The canonical UI development standard preserves repository "
            "authority, V2 accessibility, privacy, provenance, reduced motion, "
            "and toolkit-independent runtime boundaries."
        ),
        "enforced_by": ["woff/tests/test_ui_development_standard.py"],
    }
    assert work_items["issue-135"] == {
        "title": "Establish WoFF Mate UI/UX reference stack and agent-skill policy",
        "module": "governance",
        "state": "done",
        "evals": ["EVAL-UI-POLICY-001"],
        "gates": ["Q0", "Q1"],
        "depends_on": [
            {"id": "issue-79", "status": "satisfied"},
            {"id": "issue-80", "status": "satisfied"},
        ],
    }
    for cycle in cycles.values():
        assert isinstance(cycle, dict)
        assert "issue-135" not in cycle.get("members", [])

    eval_catalog = EVALS_PATH.read_text(encoding="utf-8")
    assert "`EVAL-UI-POLICY-001` | #135 | Implemented" in eval_catalog
