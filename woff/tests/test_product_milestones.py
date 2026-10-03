"""Contracts for revision-bound reviews and the fixture-backed product path."""

import ast
from copy import deepcopy
from pathlib import Path
import re
from typing import Any, cast

import pytest

from scripts.validate_project_graph import GraphValidationError, load_graph, validate_graph


ROOT = Path(__file__).resolve().parents[2]
POLICY = "docs/engineering/product-milestones.md"
R1_RECORD = "docs/engineering/r1-integrity-baseline.md"
R2_RECORD = "docs/engineering/r2-ui-architecture-review.md"
SECURITY_BASELINE_RECORD = "docs/engineering/security-baseline-2026-09-10.md"
MAIN_PROTECTION_RECORD = "docs/engineering/main-protection-2026-09-27.md"


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
            expected_status = (
                "implemented" if item_id in {"issue-82", "issue-140"} else "planned"
            )
            assert evals[eval_id]["status"] == expected_status
    assert items["issue-82"]["state"] == "done"
    assert items["issue-140"]["state"] == "done"
    assert items["review-r2"]["state"] == "backlog"
    assert {"Q4-P0-PROTOTYPE", "Q6-CYCLE-3.4.0"} <= set(items["issue-140"]["gates"])
    assert "Q4" not in items["issue-140"]["gates"]
    assert "Q5-UI-ARCHITECTURE" in items["review-r2"]["gates"]
    assert "Q5-UI-ARCHITECTURE" not in items["issue-140"]["gates"]
    assert items["issue-139"]["state"] == "done"
    assert {"id": "issue-139", "status": "satisfied"} in items["issue-140"]["depends_on"]
    assert {"id": "issue-81", "status": "satisfied"} in items["issue-140"]["depends_on"]
    assert all(dep["status"] == "satisfied" for dep in items["issue-140"]["depends_on"])
    assert items["review-r2"]["depends_on"] == [
        {"id": "issue-81", "status": "satisfied"},
        {"id": "issue-82", "status": "satisfied"},
        {"id": "issue-140", "status": "satisfied"},
    ]
    members = set(cycles["cycle-3.4.0"]["members"])
    assert {"issue-136", "issue-139", "issue-140", "issue-81", "issue-82"} <= members
    assert len(members) == 20
    assert set(evals["EVAL-CYCLE-340-001"]["work_items"]) == members
    assert cycles["cycle-3.4.0"]["state"] == "active"
    assert evals["EVAL-CYCLE-340-001"]["status"] == "planned"
    assert {items[item_id]["state"] for item_id in {
        "issue-44", "issue-43", "issue-76", "issue-96"
    }} == {"backlog"}
    assert items["issue-101"]["state"] == "blocked"
    assert "issue-82" not in cycles["cycle-3.5.0"]["members"]
    assert "All twenty 3.4.0 work items" in graph["gates"]["Q6-CYCLE-3.4.0"]["description"]
    quality = _text("docs/engineering/quality-gates.md").split("## Q6-CYCLE-3.4.0:", 1)[1]
    catalog = _text("docs/engineering/evals.md").split("## Active cycle 3.4.0", 1)[1]
    for item_id in members:
        number = item_id.removeprefix("issue-")
        assert re.search(rf"#{number}\b", quality)
        assert f"| #{number} |" in catalog
    validate_graph(ROOT, graph)


def test_p0_prototype_packaging_gate_is_bounded_and_does_not_replace_q4() -> None:
    graph = _graph()
    gates = graph["gates"]
    assert gates["Q4"]["description"] == (
        "Windows and packaging changes pass supported Python, smoke, build, "
        "install, upgrade, and rollback checks."
    )
    bounded = gates["Q4-P0-PROTOTYPE"]["description"]
    for phrase in (
        "approved Windows development/test environment",
        "prototype PyInstaller folder build",
        "physical 100/125/150/200% scaling",
        "synthetic fixture-only boundary",
        "prototype/not-installer labeling",
        "does not satisfy or replace Q4",
        "clean-machine production validation",
        "upgrade/rollback",
        "release checksum/signing/provenance",
        "production-distribution",
        "approves no Product Gate",
    ):
        assert phrase in bounded

    quality = _text("docs/engineering/quality-gates.md")
    bounded_quality = quality.split(
        "### Q4-P0-PROTOTYPE: experimental P0 demonstrability", 1
    )[1].split("## Q5:", 1)[0]
    for phrase in (
        "prototype, not installer",
        "does not satisfy, replace or weaken Q4",
        "clean-machine production validation",
        "installation/update/rollback",
        "release checksums/signing/provenance",
        "production distribution",
        "approves no Product Gate",
    ):
        assert phrase in bounded_quality


def test_nation_contract_is_integrated_before_ui_contract_completion() -> None:
    graph = _graph()
    nation = graph["work_items"]["issue-136"]
    assert nation["state"] == "done"
    assert {"id": "issue-136", "status": "satisfied"} in graph["work_items"]["issue-81"]["depends_on"]
    for eval_id in nation["evals"]:
        assert graph["evals"][eval_id]["status"] == "implemented"
        assert graph["evals"][eval_id]["enforced_by"] == ["woff/tests/test_nation_domain.py"]
    assert "#136 closure discrepancy" in _text("docs/engineering/evals.md")
    graph["evals"]["EVAL-NATION-DOMAIN-001"]["status"] = "planned"
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
    assert items["issue-136"]["state"] == "done"
    assert {"id": "issue-136", "status": "satisfied"} in items["issue-81"]["depends_on"]


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
            "done",
            "implemented",
        ),
        "issue-144": (
            {"issue-42", "issue-75"},
            {"EVAL-LIVE-COMPLETENESS-001"},
            "done",
            "implemented",
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
    expected: dict[
        str,
        tuple[str, set[str], str, set[tuple[str, str]], str, str],
    ] = {
        "issue-151": (
            "platform",
            {"Q0", "Q1", "Q3", "Q4", "Q5"},
            "EVAL-OUTPUT-PATH-ISOLATION-001",
            {
                ("issue-45", "satisfied"),
                ("issue-157", "satisfied"),
            },
            "done",
            "implemented",
        ),
        "issue-152": (
            "governance", {"Q0", "Q1", "Q5"},
            "EVAL-MAIN-PROTECTION-001", set(), "done", "implemented",
        ),
        "issue-153": (
            "governance", {"Q0", "Q1", "Q4", "Q5"},
            "EVAL-SUPPLY-CHAIN-001", set(), "backlog", "planned",
        ),
        "issue-154": (
            "governance", {"Q0", "Q1", "Q5"},
            "EVAL-SECURITY-GOVERNANCE-001", set(), "backlog", "planned",
        ),
        "issue-155": (
            "governance",
            {"Q0", "Q1", "Q4", "Q5"},
            "EVAL-RELEASE-PROVENANCE-001",
            {
                ("issue-152", "satisfied"),
                ("issue-153", "unsatisfied"),
                ("issue-154", "unsatisfied"),
            },
            "backlog",
            "planned",
        ),
    }
    cycle_members = {
        member for cycle in cycles.values() for member in cycle["members"]
    }

    for item_id, (
        module,
        gates,
        eval_id,
        dependencies,
        item_state,
        eval_status,
    ) in expected.items():
        item = items[item_id]
        assert item["state"] == item_state
        assert item["module"] == module
        assert set(item["gates"]) == gates
        assert item["evals"] == [eval_id]
        assert {
            (dependency["id"], dependency["status"])
            for dependency in item["depends_on"]
        } == dependencies
        assert item_id not in cycle_members
        assert evals[eval_id]["work_items"] == [item_id]
        assert evals[eval_id]["status"] == eval_status
        assert bool(evals[eval_id].get("enforced_by")) == (
            eval_status == "implemented"
        )

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
    output_eval = evals["EVAL-OUTPUT-PATH-ISOLATION-001"]
    assert output_eval["enforced_by"] == [
        "woff/tests/test_output_path_isolation.py",
        "woff/tests/test_config.py",
        "woff/tests/test_handler_integration.py",
        ".github/workflows/ci.yml",
    ]
    for evidence_path in output_eval["enforced_by"]:
        assert (ROOT / evidence_path).is_file()
    assert "#151 must be resolved" not in quality
    assert "#151 is now implemented" in quality
    assert "still-open GitHub issue" in quality
    assert "#142, #96" in quality
    assert "The #152 repository-protection guardrail is complete" in quality
    assert "#153 and #154 remain staged P3 work" in quality
    assert "#155 is pre-release work" in quality
    assert "Product Gate A remains unapproved." in quality
    assert "Treat #151's real-root output/input isolation as implemented" in policy
    assert "open GitHub issue awaits maintainer reconciliation" in policy
    assert "#152's repository controls are also enforced and recorded" in policy
    assert "#153 supply-chain hardening and #154 permanent security-governance" in policy
    assert "#155 remains pre-release work" in policy
    assert "The newly reproduced P2 output/input path-isolation defect is owned by #151" in record
    assert "complete before Gate A can claim safe operation against real WoFF roots" in record
    current_governance = " ".join((quality, catalog, policy, _text(R2_RECORD)))
    for stale_current_claim in (
        "#151 must be resolved",
        "Production implementation of #151 still requires",
        "#151 is an outstanding Gate A implementation blocker",
    ):
        assert stale_current_claim not in current_governance
    validate_graph(ROOT, graph)


def test_main_protection_evidence_contract_is_recorded_without_approving_gate_a() -> None:
    graph = _graph()
    items, evals = graph["work_items"], graph["evals"]

    assert items["issue-152"]["state"] == "done"
    evaluation = evals["EVAL-MAIN-PROTECTION-001"]
    assert evaluation["status"] == "implemented"
    assert evaluation["enforced_by"] == ["woff/tests/test_product_milestones.py"]
    assert {"id": "issue-152", "status": "satisfied"} in (
        items["issue-155"]["depends_on"]
    )

    evidence = _text(MAIN_PROTECTION_RECORD)
    for phrase in (
        "74d3576e87efb112b1f42cc07100d496ff66bcd1",
        "24065034",
        "Protect main and require CI",
        "Tests (Python 3.10)",
        "Tests (Python 3.14)",
        "Pyright",
        "Windows smoke test",
        "GitHub Actions",
        "15368",
        "Required approving reviews | `0`",
        "Branch up to date before merge | Not required",
        "Force pushes | Blocked",
        "Branch deletion | Blocked",
        "No configured bypass actors",
        "Product Gate A remains NOT APPROVED",
    ):
        assert phrase in evidence

    workflow = _text(".github/workflows/ci.yml")
    for phrase in (
        "name: Tests (Python ${{ matrix.python-version }})",
        'python-version: ["3.10", "3.14"]',
        "name: Pyright",
        "name: Windows smoke test",
    ):
        assert phrase in workflow

    baseline = _text(SECURITY_BASELINE_RECORD)
    assert "The audit found no active branch protection or ruleset for `main`" in baseline
    assert "Remediation verified on 2026-09-27" in baseline
    assert Path(MAIN_PROTECTION_RECORD).name in baseline
    assert "Product Gate A and public distribution remain unapproved" in baseline


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

    flow = graph["evals"]["EVAL-P0-FLOW-001"]["evidence"]
    for automated_claim in (
        "routing/navigation calls",
        "state transitions",
        "focus results",
        "rail/layout behavior",
        "career isolation",
        "close/reopen",
    ):
        assert automated_claim in flow
    for physical_claim in (
        "Tab/Shift+Tab",
        "rail-arrow",
        "Enter/Space",
        "selector interaction",
        "does not synthesize those key events",
    ):
        assert physical_claim in flow
    assert "automated keyboard" not in flow

    catalog = _text("docs/engineering/evals.md")
    assert "they do not synthesize Tab/Shift+Tab, rail arrows, Enter/Space or selector keys" in catalog
    assert "maintainer-observed Windows walkthrough supplies those physical keyboard/selector" in catalog


def test_keyboard_walkthrough_is_bound_to_the_audited_revision() -> None:
    physical_revision = "46b18097be490f1741f5792c84d945f6077c465b"
    audited_revision = "bfa7647ac94cafba658a077e52a55a3c2240a4dd"
    source_path = "woff/p0_desktop/window.py"

    def keyboard_blocks(source: str) -> tuple[dict[str, str], bool]:
        tree = ast.parse(source)
        window = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "P0Window"
        )
        methods = {
            node.name: node
            for node in window.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        init = methods["__init__"]
        render = methods["_render"]

        def dump(nodes: list[ast.stmt]) -> str:
            return "\n".join(
                ast.dump(node, include_attributes=False) for node in nodes
            )

        selected = {
            "skip_focus": dump(
                [node for node in init.body if "self.skip" in ast.unparse(node)]
            ),
            "navigation_construction": dump(
                [
                    node
                    for node in init.body
                    if "self.nav_buttons" in ast.unparse(node)
                    or "self._nav_button" in ast.unparse(node)
                ]
            ),
            "career_selector": dump(
                [node for node in init.body if "self.career" in ast.unparse(node)]
            ),
            "tab_order": dump(
                [
                    node
                    for node in init.body
                    if "setTabOrder" in ast.unparse(node)
                    or (
                        isinstance(node, ast.AnnAssign)
                        and ast.unparse(node.target) == "previous"
                    )
                ]
            ),
            "_nav_button": dump([methods["_nav_button"]]),
            "eventFilter": dump([methods["eventFilter"]]),
            "navigate": dump([methods["navigate"]]),
            "heading_focus_transfer": dump(
                [
                    node
                    for node in render.body
                    if "self.heading" in ast.unparse(node)
                ]
            ),
        }
        return selected, "keyPressEvent" in methods

    current_source = (ROOT / source_path).read_text(encoding="utf-8")
    current_blocks, current_override = keyboard_blocks(current_source)
    expected_hashes = {
        "skip_focus": "5b0208b742b72a02d03a84629440cb6b7835c8dfdb84ce926e9255b2d602daa0",
        "navigation_construction": "df1ba6b540424425d1694da5493dbbf52979d5af2ff0a578549d6fa56b85ec3f",
        "career_selector": "0b52289aa2eb51eff11540507c59584d9d6a1d60aa3a1bea8d0951837f42984c",
        "tab_order": "7002e860eaed6b70eb7310369c183f18fad85bf296f158b1958387006ed511b1",
        "_nav_button": "6d14a9df962da5c518a8dd833eef28175921c6d004f248d48fdf91de2ed80105",
        "eventFilter": "02b5c428c3a5e20f124e9b447b9726cb129792fbf455690d0cc86d6d75372277",
        "navigate": "dc9d8d54947b3c3a27b546b8e900f5cc00c3393495fc78ef1ccf4e40376cbae7",
        "heading_focus_transfer": "74320a54eac8767efd9c634dca019eaf93dfc27248aded48e519da0994c14f39",
    }
    assert set(current_blocks) == set(expected_hashes)
    assert all(current_blocks.values())
    assert not current_override
    for construct in (
        'self.skip = QPushButton("Skip to content")',
        "self.skip.clicked.connect(lambda: self.heading.setFocus())",
        "self.nav_buttons: dict[str, QPushButton] = {}",
        "button = self._nav_button(screen, title, icon)",
        "self.career = QComboBox()",
        "QWidget.setTabOrder(self.skip, self.career)",
        "QWidget.setTabOrder(previous, self.nav_buttons[screen])",
        "button = QPushButton(title.replace(\"&\", \"&&\"))",
        "button.installEventFilter(self)",
        "Qt.Key.Key_Up, Qt.Key.Key_Down",
        "self.navigate(target)",
        "self.heading.setFocus()",
    ):
        assert construct in current_source

    record = _text(R2_RECORD)
    p0_record = _text("docs/ui/p0-functional-desktop.md")
    for evidence in (
        physical_revision,
        audited_revision,
        "RESULT: 8/8 keyboard-relevant AST blocks identical",
        "The whole `window.py` file is not identical",
        "no new physical keyboard walkthrough was required",
    ):
        assert evidence in record
    for name, digest in expected_hashes.items():
        assert f"{name}: IDENTICAL sha256={digest}" in record
    for unrelated_change in (
        "destination-specific empty messages",
        "standard rail width `224` → `256`",
        "muted selector-label styling",
        "warning/failure message de-duplication",
        "stale Operations Retry availability",
        "Operations latest-mission card",
    ):
        assert unrelated_change in record
    assert "original 2026-09-29 run" in p0_record
    assert "is not claimed to be wholly identical" in p0_record
    assert "no physical rerun was required" in p0_record


def test_post_p0_r2_hold_is_revision_bound_without_authorizing_adoption() -> None:
    graph = _graph()
    items, evals, cycles = graph["work_items"], graph["evals"], graph["cycles"]
    audited_sha = "bfa7647ac94cafba658a077e52a55a3c2240a4dd"

    assert items["issue-140"]["state"] == "done"
    assert all(
        evals[eval_id]["status"] == "implemented"
        for eval_id in items["issue-140"]["evals"]
    )
    assert {"id": "issue-140", "status": "satisfied"} in (
        items["review-r2"]["depends_on"]
    )
    assert items["review-r2"]["state"] == "backlog"
    assert evals["EVAL-R2-REVIEW-001"]["status"] == "planned"
    assert cycles["cycle-3.4.0"]["state"] == "active"
    assert evals["EVAL-CYCLE-340-001"]["status"] == "planned"

    record = _text(R2_RECORD)
    for phrase in (
        audited_sha,
        "HOLD / Conditional No-Go for production retention",
        "PySide6 + Qt Widgets 6.11.2",
        "No new UI `priority:P0` or `priority:P1` defect was found",
        "fixture-only/runtime dependency boundary passed",
        "P1 remains unauthorized",
        "no Product Gate A, B, C or D is approved",
        "Windows 11 execution",
        "remaining supported Python/package matrix",
        "clean-machine validation",
        "final-P0 UI accessibility/UIA evidence",
        "production optional-dependency and entry-point policy",
        "representative production packaging and startup behavior",
        "bundle inventory, SBOM and licensing route",
        "Qt Virtual Keyboard",
        "R2 Full Application Review **MUST** be performed",
    ):
        assert phrase in record

    for command_or_result in (
        "git rev-parse HEAD",
        "git rev-parse origin/main",
        "python scripts/validate_project_graph.py",
        "1025 passed in 21.65s",
        "UI fixtures valid: 30 synthetic cases, 6 shared states.",
        "6 passed, 3 skipped in 0.04s",
        "sha256sum --check docs/ui/evidence/issue-140-p0/SHA256SUMS",
        "1927 passed, 7 skipped, 1 deselected, 175 subtests passed",
        "8 errors, 0 warnings, 0 informations",
        "git diff --check",
        "CI #303 was not an R2 audit command",
    ):
        assert command_or_result in record

    for scope in (
        "Architecture/module dependencies",
        "Career/slot/campaign/wingman identity",
        "Transactions/rollback/atomicity",
        "Ingestion/retry/coalescing/startup/shutdown",
        "Data preservation/authority/provenance",
        "Schema migration/backward compatibility",
        "Parser known/missing/unsupported/invalid semantics",
        "SQLite/concurrency behavior",
        "Privacy/local-only/credential exclusions",
        "CLI/editor/presentation contracts",
        "Windows packaging and supported Python compatibility",
        "Test/eval blind spots",
        "Project graph/gates/issues/docs/code consistency",
        "Residual risks and explicit maintainer decisions",
    ):
        assert scope in record

    for blocker in ("#142", "#96"):
        assert blocker in record
    assert "#151 is not a current technical blocker" in record
    assert "governance drift discovered by R2" in record
    assert "Issue #151 remains open" in record
    assert "14 passed, 4 skipped in 0.08s" in record
    assert "122 passed in 9.90s" in record
    assert "issue151_ancestor_exit=0" in record

    for revision_or_tree in (
        "64710a0b1bc46c19f267db10e4168403ce974066",
        "691749ce3e2c9e9c807142c1c6b326846c4bc269",
        "6927873b08f3867fa3d43bb620f1de9910b4e560",
        "git diff --exit-code 64710a0b1bc46c19f267db10e4168403ce974066",
        "git diff --name-only 64710a0b1bc46c19f267db10e4168403ce974066",
        "This does not relabel the run as post-merge execution",
    ):
        assert revision_or_tree in record

    assert "R2 Full Application Review **MUST** be performed" in record
    assert "it cannot replace the mandatory repeat R2" in record

    adr = (ROOT / "docs/architecture/adr-ui-toolkit.md").read_text(encoding="utf-8")
    assert re.search(r"^Status:\s*Proposed\s*$", adr, re.MULTILINE)

    reconciled_docs = " ".join(
        _text(path)
        for path in (
            "docs/engineering/evals.md",
            "docs/engineering/quality-gates.md",
            POLICY,
            "docs/ui/p0-functional-desktop.md",
        )
    )
    for stale_claim in (
        "#140 remains pending",
        "P0 completion remains pending",
        "R2 still awaits #140 evidence",
        "Issue #140 and its graph dependency into R2 remain pending",
        "experimental implementation on Issue #140 Draft PR",
    ):
        assert stale_claim not in reconciled_docs
    assert "repeat review or scope-impact determination" not in reconciled_docs
    assert "scope-impact determination may cover only unrelated, non-material" in reconciled_docs


def test_post_spike_authorization_is_revision_bound_and_limited_to_p0() -> None:
    adr = _text("docs/architecture/adr-ui-toolkit.md")
    decision = adr.split("## Post-spike P0 authorization (2026-09-28)", 1)[1].split(
        "## Adoption gates", 1
    )[0]
    for phrase in (
        "20f742868a71e2092b8a82397304fef668638bed",
        "PR #165", "Completed", "Conditional Go",
        "Authorize PySide6 + Qt Widgets 6.11.2 for the experimental P0 fixture-backed",
        "desktop prototype in Issue #140",
        "ADR remains **Proposed** until the post-P0 R2 review",
        "adoption gates are satisfied",
        "does not authorize P1 or retained production architecture",
        "SQLite or live WoFF data access",
        "parser, repository, watchdog, launcher or session integration",
        "campaign/configuration mutation",
        "mandatory Qt production dependencies outside the approved P0 boundary",
        "public distribution; Product Gate approval; or ADR acceptance",
        "P3 asset work is not a dependency of #140",
        "does not authorize additional Narrator/NVDA, VM, Windows 11, clean-machine, DPI or cold-start evidence work",
        "evidence-status.json", "measurements, hashes and provenance remain unchanged",
    ):
        assert phrase in decision
    graph = _graph()
    assert graph["evals"]["EVAL-CYCLE-340-001"]["status"] == "planned"
