"""Contracts for revision-bound reviews and the fixture-backed product path."""

from copy import deepcopy
from pathlib import Path
import re
from typing import Any, cast

import pytest

from scripts.validate_project_graph import GraphValidationError, load_graph, validate_graph


ROOT = Path(__file__).resolve().parents[2]
POLICY = "docs/engineering/product-milestones.md"


def _graph() -> dict[str, Any]:
    return cast(dict[str, Any], load_graph(ROOT / "docs/architecture/project-graph.yaml"))


def _text(path: str) -> str:
    return " ".join((ROOT / path).read_text(encoding="utf-8").split())


def test_authoritative_product_gates_require_review_and_demonstrability() -> None:
    graph = _graph()
    q5 = graph["gates"]["Q5"]
    assert q5["policy"] == POLICY
    assert set(q5["required_evidence"]) == {
        "full_application_review", "product_demonstrability", "revision_scope_impact"
    }
    gates = _text("docs/engineering/quality-gates.md")
    q5_text = gates.split("## Q5:", 1)[1].split("## Q6-", 1)[0]
    for phrase in ("Full Application Review", "product-demonstrability record",
                   "exact audited `main` commit SHA", "product-milestones.md"):
        assert phrase in q5_text
    for name in ("A. Reliable data", "B. Viable launcher", "C. Social RPG", "D. Public release"):
        assert name in q5_text
    assert POLICY in _text("README.md")


@pytest.mark.parametrize("field", ["policy", "required_evidence"])
def test_validator_rejects_missing_q5_policy_contract(field: str) -> None:
    graph = deepcopy(_graph())
    graph["gates"]["Q5"].pop(field, None)
    with pytest.raises(GraphValidationError, match="gates.Q5"):
        validate_graph(ROOT, graph)


@pytest.mark.parametrize("missing", [
    "full_application_review", "product_demonstrability", "revision_scope_impact"
])
def test_validator_rejects_omitted_product_gate_evidence(missing: str) -> None:
    graph = deepcopy(_graph())
    graph["gates"]["Q5"]["required_evidence"] = [
        item for item in ("full_application_review", "product_demonstrability", "revision_scope_impact")
        if item != missing
    ]
    with pytest.raises(GraphValidationError, match="gates.Q5"):
        validate_graph(ROOT, graph)


def test_product_path_and_cycle_ownership_are_executable() -> None:
    graph = _graph()
    items, evals, cycles = graph["work_items"], graph["evals"], graph["cycles"]
    expected = {
        "issue-82": {"issue-56", "issue-80", "issue-81"},
        "issue-140": {"issue-79", "issue-80", "issue-81", "issue-82", "issue-139"},
        "review-r2": {"issue-81", "issue-82", "issue-140"},
    }
    for item_id, dependencies in expected.items():
        item = items[item_id]
        assert {dep["id"] for dep in item["depends_on"]} == dependencies
        assert {"Q0", "Q1"} <= set(item["gates"])
        for eval_id in item["evals"]:
            assert item_id in evals[eval_id]["work_items"]
            assert evals[eval_id]["status"] == "planned"
    assert {"Q4", "Q6-CYCLE-3.4.0"} <= set(items["issue-140"]["gates"])
    assert "Q5-UI-ARCHITECTURE" in items["review-r2"]["gates"]
    assert "Q5-UI-ARCHITECTURE" not in items["issue-140"]["gates"]
    members = set(cycles["cycle-3.4.0"]["members"])
    assert {"issue-136", "issue-139", "issue-140", "issue-81", "issue-82"} <= members
    assert len(members) == 20
    assert set(evals["EVAL-CYCLE-340-001"]["work_items"]) == members
    assert "issue-82" not in cycles["cycle-3.5.0"]["members"]
    assert "All twenty 3.4.0 work items" in graph["gates"]["Q6-CYCLE-3.4.0"]["description"]
    quality = _text("docs/engineering/quality-gates.md").split("## Q6-CYCLE-3.4.0:", 1)[1]
    catalog = _text("docs/engineering/evals.md").split("## Active cycle 3.4.0", 1)[1]
    for item_id in members:
        number = item_id.removeprefix("issue-")
        assert re.search(rf"#{number}\b", quality)
        assert f"| #{number} |" in catalog
    validate_graph(ROOT, graph)


def test_unimplemented_nation_contract_cannot_be_closed_by_github_status() -> None:
    graph = _graph()
    nation = graph["work_items"]["issue-136"]
    assert nation["state"] == "backlog"
    assert {"id": "issue-136", "status": "unsatisfied"} in graph["work_items"]["issue-81"]["depends_on"]
    for eval_id in nation["evals"]:
        assert graph["evals"][eval_id]["status"] == "planned"
        assert not graph["evals"][eval_id].get("enforced_by")
    assert "#136 closure discrepancy" in _text("docs/engineering/evals.md")
    graph["work_items"]["issue-136"]["state"] = "done"
    with pytest.raises(GraphValidationError):
        validate_graph(ROOT, graph)


def test_review_revision_and_priority_contract() -> None:
    policy = _text(POLICY)
    for phrase in ("exact audited `main` commit SHA", "gate-decision commit SHA",
                   "intervening changes", "scope-impact determination",
                   "rerun the affected review scope", "documentation-only",
                   "priority:P0", "priority:P1"):
        assert phrase in policy
    assert not re.search(r"(?<!priority:)P0/P1 (?:defect|finding)", policy)
    assert "No AI model is part of WoFF Mate runtime" in policy


def test_r2_follows_p0_before_retained_production_work() -> None:
    policy = _text(POLICY)
    sequence = policy.split("## Near-term WoFF Mate sequence", 1)[1].split("## P0 boundary", 1)[0]
    steps = re.findall(r"\d+\. (.*?)(?= \d+\. |$)", sequence)
    positions = [next(i for i, step in enumerate(steps) if token in step)
                 for token in ("**#81**", "**#82**", "**#140", "**R2", "**P1")]
    assert positions == sorted(set(positions))
    adr = _text("docs/architecture/adr-ui-toolkit.md")
    assert "R2" in adr and "#140" in adr and "Status: Proposed" in adr
    assert "Q5-UI-ARCHITECTURE" in _text("docs/engineering/quality-gates.md")
    assert "neither #82 nor P0 accepts a production toolkit" in policy


def test_p0_evidence_preserves_fixture_boundary() -> None:
    graph = _graph()
    evidence = " ".join(graph["evals"][eval_id]["evidence"]
                        for eval_id in graph["work_items"]["issue-140"]["evals"])
    for phrase in ("seven", "two synthetic careers", "immutable", "keyboard",
                   "scaling", "SQLite", "WoFF", "network", "launcher", "AI",
                   "product-demonstrability record"):
        assert phrase in evidence
