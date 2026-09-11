"""Contracts for revision-bound reviews and the fixture-backed product path."""

from copy import deepcopy
from pathlib import Path
import re
from typing import Any, cast

import pytest

from scripts.validate_project_graph import GraphValidationError, load_graph, validate_graph


ROOT = Path(__file__).resolve().parents[2]
POLICY = "docs/engineering/product-milestones.md"
R1_RECORD = "docs/engineering/r1-integrity-baseline.md"
SECURITY_BASELINE_RECORD = "docs/engineering/security-baseline-2026-09-10.md"


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
    assert items["issue-139"]["state"] == "done"
    assert {"id": "issue-139", "status": "satisfied"} in items["issue-140"]["depends_on"]
    assert {"id": "issue-81", "status": "unsatisfied"} in items["issue-140"]["depends_on"]
    assert {"id": "issue-82", "status": "unsatisfied"} in items["issue-140"]["depends_on"]
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


def test_first_r1_record_and_gate_a_disposition_are_revision_bound() -> None:
    graph = _graph()
    items, evals = graph["work_items"], graph["evals"]
    record = _text(R1_RECORD)
    record_source = (ROOT / R1_RECORD).read_text(encoding="utf-8")
    classification_by_finding = {
        finding: " ".join(classification.split())
        for finding, classification in re.findall(
            r"^\s*\|\s*(R1-\d{3})\s*\|\s*([^|]+?)\s*\|",
            record_source,
            flags=re.MULTILINE,
        )
    }
    recorded_result_by_command = {
        " ".join(command.split()): " ".join(result.replace("`", "").split())
        for command, result in re.findall(
            r"^\s*\|\s*`([^`]+)`[^|]*\|\s*([^|]+?)\s*\|",
            record_source,
            flags=re.MULTILINE,
        )
    }
    policy = _text(POLICY)
    quality = _text("docs/engineering/quality-gates.md")
    audited_sha = "f8da6c3d4da3264c025303d851f8bd2fcf1d8f4b"
    expected_classifications = {
        "R1-001": "VERIFIED DEFECT",
        "R1-002": "VERIFIED DEFECT",
        "R1-003": "VERIFIED DEFECT",
        "R1-004": "VERIFIED DEFECT",
        "R1-005": "VERIFIED DEFECT",
        "R1-006": "VERIFIED DEFECT",
        "R1-007": "EVIDENCE GAP",
        "R1-008": "EVIDENCE GAP",
        "R1-009": "EVIDENCE GAP",
        "R1-010": "VERIFIED DEFECT",
        "R1-011": "VERIFIED DEFECT",
        "R1-012": "STRUCTURAL RISK",
        "R1-013": "VERIFIED DEFECT",
        "R1-014": "STRUCTURAL RISK",
        "R1-015": "STRUCTURAL RISK",
        "R1-016": "STRUCTURAL RISK",
        "R1-017": "VERIFIED DEFECT",
        "R1-018": "VERIFIED DEFECT",
        "R1-019": "EVIDENCE GAP",
        "R1-020": "INTENTIONALLY DEFERRED WORK",
    }
    expected_recorded_validation = {
        r".venv\Scripts\python.exe scripts/validate_project_graph.py": "PASS, exit 0",
        r".venv\Scripts\python.exe -m pytest woff/tests/test_architecture_contracts.py -q": "123 passed",
        r".venv\Scripts\python.exe -m pytest woff/tests/test_privacy_contracts.py -q": "10 passed",
        r".venv\Scripts\python.exe -m pytest woff/tests/test_pilot_vacancy.py -q": "38 passed",
        r".venv\Scripts\python.exe -m pytest -q": (
            "15 failed, 1233 passed, 1 skipped, 23 warnings; 145 subtests passed"
        ),
        r".venv\Scripts\pyright.exe": "FAIL: 28 errors, 3 warnings",
        "git diff --check": "PASS, exit 0",
        r".venv\Scripts\pyright.exe --pythonpath .venv\Scripts\python.exe": (
            "1 error, 0 warnings: os.O_ACCMODE at "
            "woff/tests/test_command_contracts.py:778"
        ),
        (
            r".venv\Scripts\python.exe -m pytest "
            "woff/tests/test_command_contracts.py woff/tests/test_woff_query.py -q"
        ): (
            "1 failed, 65 passed; the remaining failure was the "
            "os.O_ACCMODE portability defect"
        ),
    }

    for source, text in {
        R1_RECORD: record,
        POLICY: policy,
        "docs/engineering/quality-gates.md": quality,
    }.items():
        assert audited_sha in text
        assert "FAIL — confirmed blocking defects exist" in text
        assert "Product Gate A is not approved." in text, source
    assert "CI success alone" in record
    assert classification_by_finding == expected_classifications
    assert recorded_result_by_command == expected_recorded_validation
    assert "PermissionError: [WinError 5]" in record
    assert "environment preparation context, not a product defect" in record
    assert "did not run or establish a passing native-Windows full suite" in record

    assert items["review-r1"]["state"] == "done"
    assert items["issue-148"]["state"] == "done"
    for eval_id in ("EVAL-R1-REVIEW-001", "EVAL-R1-GOVERNANCE-001"):
        assert evals[eval_id]["status"] == "implemented"
        assert evals[eval_id]["enforced_by"] == ["woff/tests/test_product_milestones.py"]

    assert items["issue-122"]["state"] == "done"
    assert all(evals[eval_id]["status"] == "implemented"
               for eval_id in items["issue-122"]["evals"])
    assert items["issue-87"]["state"] == "blocked"
    assert evals["EVAL-CAREER-REUSE-EVIDENCE-001"]["status"] == "planned"
    assert graph["cycles"]["cycle-3.3.0"]["state"] == "active"
    assert evals["EVAL-CYCLE-330-001"]["status"] == "planned"
    assert items["issue-136"]["state"] == "backlog"
    assert {"id": "issue-136", "status": "unsatisfied"} in items["issue-81"]["depends_on"]


def test_r1_follow_ups_are_registered_without_implicit_cycle_membership() -> None:
    graph = _graph()
    items, evals, cycles = graph["work_items"], graph["evals"], graph["cycles"]
    expected = {
        "issue-142": (
            {"issue-42", "issue-122"},
            {"EVAL-STARTUP-RECURSIVE-001"},
            "backlog",
            "planned",
        ),
        "issue-143": (
            {"issue-34"},
            {"EVAL-TXN-INTERRUPT-001"},
            "backlog",
            "planned",
        ),
        "issue-144": (
            {"issue-42", "issue-75"},
            {"EVAL-LIVE-COMPLETENESS-001"},
            "backlog",
            "planned",
        ),
        "issue-145": (
            set(),
            {"EVAL-WINDOWS-VALIDATION-001", "EVAL-EVIDENCE-BYTES-001"},
            "done",
            "implemented",
        ),
        "issue-146": (
            {"issue-34", "issue-39", "issue-95"},
            {"EVAL-DERIVED-RECOVERY-001"},
            "backlog",
            "planned",
        ),
        "issue-147": (
            {"issue-27", "issue-42"},
            {"EVAL-SNAPSHOT-BOUNDS-001"},
            "backlog",
            "planned",
        ),
    }
    cycle_members = {
        member for cycle in cycles.values() for member in cycle["members"]
    }
    for item_id, (dependencies, eval_ids, state, eval_status) in expected.items():
        item = items[item_id]
        assert item["state"] == state
        assert set(item["evals"]) == eval_ids
        assert "Q5" in item["gates"]
        assert {dep["id"] for dep in item["depends_on"]} == dependencies
        assert all(dep["status"] == "satisfied" for dep in item["depends_on"])
        assert item_id not in cycle_members
        for eval_id in eval_ids:
            assert evals[eval_id]["status"] == eval_status
            assert bool(evals[eval_id].get("enforced_by")) == (
                eval_status == "implemented"
            )
            assert evals[eval_id]["work_items"] == [item_id]

    record = _text(R1_RECORD)
    assert "not members of cycles 3.3.0 or 3.4.0" in record
    assert "Gate A disposition and engineering-cycle membership are separate decisions" in record


def test_security_baseline_ownership_and_scheduling_are_reconciled() -> None:
    graph = _graph()
    items, evals, cycles = graph["work_items"], graph["evals"], graph["cycles"]
    expected: dict[str, tuple[str, set[str], str, set[tuple[str, str]]]] = {
        "issue-151": (
                "platform",
                {"Q0", "Q1", "Q3", "Q4", "Q5"},
                "EVAL-OUTPUT-PATH-ISOLATION-001",
                {
                    ("issue-45", "satisfied"),
                    ("issue-157", "unsatisfied"),
                },
            ),
        "issue-152": (
            "governance", {"Q0", "Q1", "Q5"},
            "EVAL-MAIN-PROTECTION-001", set(),
        ),
        "issue-153": (
            "governance", {"Q0", "Q1", "Q4", "Q5"},
            "EVAL-SUPPLY-CHAIN-001", set(),
        ),
        "issue-154": (
            "governance", {"Q0", "Q1", "Q5"},
            "EVAL-SECURITY-GOVERNANCE-001", set(),
        ),
        "issue-155": (
            "governance",
            {"Q0", "Q1", "Q4", "Q5"},
            "EVAL-RELEASE-PROVENANCE-001",
            {
                ("issue-152", "unsatisfied"),
                ("issue-153", "unsatisfied"),
                ("issue-154", "unsatisfied"),
            },
        ),
    }
    cycle_members = {
        member for cycle in cycles.values() for member in cycle["members"]
    }

    for item_id, (module, gates, eval_id, dependencies) in expected.items():
        item = items[item_id]
        assert item["state"] == "backlog"
        assert item["module"] == module
        assert set(item["gates"]) == gates
        assert item["evals"] == [eval_id]
        assert {
            (dependency["id"], dependency["status"])
            for dependency in item["depends_on"]
        } == dependencies
        assert item_id not in cycle_members
        assert evals[eval_id]["work_items"] == [item_id]
        assert evals[eval_id]["status"] == "planned"
        assert not evals[eval_id].get("enforced_by")

    record = _text(SECURITY_BASELINE_RECORD)
    quality = _text("docs/engineering/quality-gates.md")
    catalog = _text("docs/engineering/evals.md")
    policy = _text(POLICY)
    audited_sha = "736c43df86d686c07aadd549c14105feaf59f89d"
    for phrase in (
        "2026-09-10",
        audited_sha,
        "None confirmed",
        "P1 adversarial-security defects",
        "#96, #74, and #142",
        "local-only privacy controls remained effective",
        "no live credentials",
        "Product Gate A and public distribution remain unapproved",
    ):
        assert phrase in record
    for issue_number in range(151, 156):
        assert f"#{issue_number}" in record
        assert f"#{issue_number}" in catalog
    assert "not added to a q6 cycle" in record.lower()
    assert "#151 must be resolved" in quality
    assert "#152 must be enforced and verified" in quality
    assert "#153 and #154 remain staged P3 work" in quality
    assert "#155 is pre-release work" in quality
    assert "Product Gate A remains unapproved." in quality
    assert "After the existing P1 correction order, resolve #151" in policy
    assert "enforce #152's repository controls" in policy
    assert "#153 supply-chain hardening and #154 permanent security-governance" in policy
    assert "#155 remains pre-release work" in policy
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
