"""Structural contracts for the repository SDD/custom-agent pilot."""

from pathlib import Path
from typing import Any, cast

import yaml

from scripts.validate_project_graph import load_graph


ROOT = Path(__file__).resolve().parents[2]
SDD_POLICY = ROOT / "docs" / "engineering" / "spec-driven-development.md"
SPEC_TEMPLATE = ROOT / "specs" / "_template" / "spec.md"
AGENTS = ROOT / ".github" / "agents"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter(path: Path) -> dict[str, Any]:
    parts = _text(path).split("---", 2)
    assert len(parts) == 3
    return cast(dict[str, Any], yaml.safe_load(parts[1]))


def test_sdd_foundation_blocks_the_first_pilot_until_integration() -> None:
    graph = cast(
        dict[str, Any],
        load_graph(ROOT / "docs" / "architecture" / "project-graph.yaml"),
    )
    work_items = cast(dict[str, Any], graph["work_items"])
    evaluations = cast(dict[str, Any], graph["evals"])

    foundation = cast(dict[str, Any], work_items["issue-157"])
    pilot = cast(dict[str, Any], work_items["issue-151"])
    evaluation = cast(dict[str, Any], evaluations["EVAL-SDD-GOVERNANCE-001"])
    dependency = next(
        dependency
        for dependency in cast(list[dict[str, str]], pilot["depends_on"])
        if dependency["id"] == "issue-157"
    )

    assert foundation["module"] == "governance"
    assert foundation["evals"] == ["EVAL-SDD-GOVERNANCE-001"]
    assert {"Q0", "Q1"}.issubset(foundation["gates"])
    assert foundation["state"] in {"in_progress", "done"}
    assert dependency["status"] == (
        "satisfied" if foundation["state"] == "done" else "unsatisfied"
    )
    assert evaluation["work_items"] == ["issue-157"]
    assert evaluation["status"] == "implemented"
    assert evaluation["enforced_by"] == ["woff/tests/test_sdd_governance.py"]


def test_sdd_approval_is_bound_to_exact_spec_content_and_maintainer_evidence() -> None:
    policy = _text(SDD_POLICY)
    template = _text(SPEC_TEMPLATE)

    for field in (
        "Status",
        "Revision",
        "Approved revision",
        "Approved spec commit",
        "Approved by",
        "Approval evidence",
    ):
        assert f"`{field}`" in policy
        assert f"{field}:" in template

    for required_contract in (
        "full Git commit SHA",
        "human maintainer",
        "explicitly approves the specification",
        "current approval payload",
        "byte-for-byte identical",
        "self-referential commit",
        "must not infer approval",
    ):
        assert required_contract in policy


def test_custom_agent_tool_boundaries_use_supported_allowlists() -> None:
    architect = _frontmatter(AGENTS / "woff-spec-architect.agent.md")
    implementation = _frontmatter(AGENTS / "woff-implementation.agent.md")
    reviewer = _frontmatter(AGENTS / "woff-independent-reviewer.agent.md")

    assert architect["tools"] == ["read", "search", "edit", "github/*"]
    assert implementation["tools"] == [
        "read",
        "search",
        "edit",
        "execute",
        "github/*",
    ]
    assert reviewer["tools"] == ["read", "search"]
    assert {"edit", "execute", "agent"}.isdisjoint(reviewer["tools"])
    assert "execute" not in architect["tools"]
    assert "agent" not in implementation["tools"]


def test_independent_pre_review_requires_a_fresh_clean_context() -> None:
    policy = _text(SDD_POLICY)
    reviewer = _text(AGENTS / "woff-independent-reviewer.agent.md")
    implementation = _text(AGENTS / "woff-implementation.agent.md")

    for required_policy in (
        "must start in a new session",
        "clean, reproducible review bundle",
        "implementation chain-of-thought",
        "repository's pre-review control",
        "separate official Codex Review",
    ):
        assert required_policy in policy

    assert "must start in a new session" in reviewer
    assert "Do not invoke or hand off to the Independent Reviewer" in implementation
    assert "does not trigger, replace, or waive" in reviewer
