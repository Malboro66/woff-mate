"""Governance contracts for maintainer-available UI adoption evidence."""

from pathlib import Path
import subprocess
from typing import Any, cast

from scripts.validate_project_graph import load_graph


ROOT = Path(__file__).resolve().parents[2]
R2_RECORD = Path("docs/engineering/r2-ui-architecture-review.md")
R2_RECORD_BLOB = "a0ed5a8c06e6a38945bda9fddda5b7fe6b431485"
R2_REPEAT = "docs/engineering/r2-ui-architecture-review-repeat.md"
R2_AUDITED_SHA = "f394ece9d139b9af1a0ae14faea5d7982816a33a"
R2_AUDITED_TREE = "30ff40214a23d46776c5b74b29e3b2227f2065ef"
R2_EVIDENCE_HEAD = "e70c040b82496f1108d34a914885f9e5fb04799c"


def _text(path: str | Path) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _normalized_text(path: str | Path) -> str:
    return " ".join(_text(path).split())


def _graph() -> dict[str, Any]:
    return cast(dict[str, Any], load_graph(ROOT / "docs/architecture/project-graph.yaml"))


def _git_blob_id(path: Path) -> str:
    completed = subprocess.run(
        ["git", "hash-object", str(path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_ui_toolkit_retention_is_separate_from_p1_live_gates() -> None:
    graph = _graph()
    gate = graph["gates"]["Q5-UI-ARCHITECTURE"]["description"]

    assert "Toolkit retention requires the bounded UI adoption-readiness contract" in gate
    assert "Windows 11 absence" in gate
    assert "clean-machine release validation do not block toolkit retention" in gate
    assert "Product Gates A/B remain separate prerequisites for P1/live integration" in gate
    assert "does not approve those gates or authorize live data" in gate

    assert graph["work_items"]["review-r2"]["state"] == "done"
    assert graph["evals"]["EVAL-R2-REVIEW-001"]["status"] == "implemented"
    assert graph["work_items"]["issue-96"]["state"] == "backlog"
    assert graph["work_items"]["issue-142"]["state"] == "backlog"
    assert graph["evals"]["EVAL-WINGMAN-IDENTITY-001"]["status"] == "planned"
    assert graph["evals"]["EVAL-STARTUP-RECURSIVE-001"]["status"] == "planned"


def test_adr_records_maintainer_available_platform_scope_without_claiming_windows11() -> None:
    adr = _normalized_text("docs/architecture/adr-ui-toolkit.md")

    assert "Status: Proposed" in adr
    assert "Windows 10 is the physically validated maintainer reference platform" in adr
    assert "Windows 11 remains a target/upstream-compatible platform but is **not**" in adr
    assert "physically validated by WoFF Mate" in adr
    assert "its absence does not block toolkit retention" in adr
    assert "Product Gates A and B remain authoritative" in adr
    assert "not prerequisites to the narrower PySide6 retention decision" in adr
    assert "Accepting this ADR in a later decision would therefore select a production UI" in adr
    assert "It would **not** authorize P1" in adr
    assert "explicit approval of every applicable Product Gate A/B decision under Q5" in adr
    assert "satisfying a gate's technical conditions" in adr
    assert "is insufficient" in adr


def test_live_r2_eval_catalog_matches_the_rescoped_decision_path() -> None:
    catalog = _normalized_text("docs/engineering/evals.md")

    assert "EVAL-R2-REVIEW-001" in catalog
    assert "Physical Windows 11 and clean-machine end-user execution are not toolkit-retention prerequisites" in catalog
    assert "P1/live integration remains separately blocked until every applicable Product Gate A/B decision is explicitly approved under Q5" in catalog
    assert "first R2 HOLD -> bounded UI adoption-readiness -> repeated revision-bound R2 -> explicit toolkit ADR decision" in catalog
    assert "P1/live integration is a separate subsequent transition" in catalog
    assert "existing adoption gates" not in catalog.split("EVAL-R2-REVIEW-001", 1)[1].split("The [#82 exploratory report]", 1)[0]
    assert "retained production architecture/P1" not in catalog


def test_p0_record_requires_explicit_gate_approvals_before_p1() -> None:
    p0 = _normalized_text("docs/ui/p0-functional-desktop.md")

    blockers = p0.split("Actual blockers to **P1 — Read-only Vertical Slice**:", 1)[1]
    assert "explicit maintainer acceptance of the UI toolkit ADR" in blockers
    assert "explicit approval of every applicable Product Gate A/B decision under Q5" in blockers
    assert "revision-valid Full Application Review" in blockers
    assert "product-demonstrability record" in blockers
    assert "maintainer approval for each applicable gate" in blockers
    assert "Toolkit retention alone does not authorize P1/live integration" in blockers


def test_clean_machine_and_release_obligations_remain_deferred_not_waived() -> None:
    quality = _normalized_text("docs/engineering/quality-gates.md")
    policy = _normalized_text("docs/engineering/product-milestones.md")

    q4 = quality.split("## Q4: Windows and packaging", 1)[1].split(
        "### Q4-P0-PROTOTYPE", 1
    )[0]
    assert "a machine without the development environment is tested" in q4
    assert "installation, upgrade, and rollback are exercised" in q4

    ui_gate = quality.split(
        "### Q5-UI-ARCHITECTURE: R2 toolkit-retention decision", 1
    )[1].split("### Privacy and security release evidence", 1)[0]
    assert "Windows 11" in ui_gate
    assert "does not block toolkit retention" in ui_gate
    assert "clean-machine" in ui_gate
    assert "full-Q4/release/Product-Gate-D evidence" in ui_gate
    assert "Product Gate A and Product Gate B remain fully authoritative and unapproved" in ui_gate
    assert "#96 and #142 remain valid Gate A/P1 blockers" in ui_gate
    assert "explicit approval of every applicable Product Gate A/B decision under Q5" in ui_gate

    assert "Physical Windows 11 and clean-machine end-user execution are not prerequisites to toolkit retention" in policy
    assert "clean-machine remains later full-Q4/release/Gate-D evidence" in policy
    assert "every applicable Product Gate A/B decision is explicitly approved under Q5" in policy
    assert "Toolkit retention does not authorize P1/live integration or approve Product Gate A/B" in policy


def test_first_r2_record_is_byte_for_byte_pinned_after_rescope() -> None:
    assert _git_blob_id(R2_RECORD) == R2_RECORD_BLOB

    record = _normalized_text(R2_RECORD)
    quality = _normalized_text("docs/engineering/quality-gates.md")
    policy = _normalized_text("docs/engineering/product-milestones.md")

    assert "HOLD / Conditional No-Go for production retention" in record
    assert "Windows 11 execution" in record
    assert "clean-machine validation" in record

    assert "this later re-scope does not rewrite the audit" in quality
    assert "does not rewrite the historical R2 HOLD" in policy
    assert "new revision-bound R2 Full Application Review **MUST** be performed" in quality
    assert "new revision-bound R2 Full Application Review **MUST** be performed" in policy


def test_repeated_r2_is_bound_to_integrated_main_without_deleted_branch_dependency() -> None:
    graph = _graph()
    record = _normalized_text(R2_REPEAT)
    evaluation = graph["evals"]["EVAL-R2-REVIEW-001"]
    for identity in (R2_AUDITED_SHA, R2_AUDITED_TREE, R2_EVIDENCE_HEAD):
        assert identity in record
        assert identity in evaluation["evidence"]
    # The integrated main commit is durable history. Never require the old PR
    # commit to remain fetchable after squash or reconstruct an artificial ref.
    actual_tree = subprocess.run(
        ["git", "rev-parse", f"{R2_AUDITED_SHA}^{{tree}}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert actual_tree == R2_AUDITED_TREE
    assert R2_REPEAT in evaluation["enforced_by"]
    assert "GO / Recommend Retain — PySide6 + Qt Widgets 6.11.2" in record
    assert "not formal ADR acceptance" in record
    assert "P1: **not authorized**" in record
    assert "Product Gates A, B, C and D: **not approved**" in record
    assert "Status: Proposed" in _text("docs/architecture/adr-ui-toolkit.md")
    assert all(
        dependency["status"] == "satisfied"
        for dependency in graph["work_items"]["review-r2"]["depends_on"]
    )


def test_repeated_r2_retains_all_review_categories_and_residual_dispositions() -> None:
    historical = _text(R2_RECORD).split("| Policy category |", 1)[1].split("\n## ", 1)[0]
    repeated = _text(R2_REPEAT).split("| Policy category |", 1)[1].split("\n### ", 1)[0]
    historical_categories = {
        line.split("|")[1].strip()
        for line in historical.splitlines()
        if line.startswith("| ")
    }
    repeated_categories = {
        line.split("|")[1].strip()
        for line in repeated.splitlines()
        if line.startswith("| ")
    }
    assert len(historical_categories) == 14
    assert repeated_categories == historical_categories
    record = _normalized_text(R2_REPEAT)
    for boundary in (
        "100%, 125%, 150%, 200%",
        "Windows 10 Pro, version 10.0.19045, build 19045",
        "Qt Virtual Keyboard excluded",
        "not relabeled successful",
        "Real keyboard focus and selector operation passed **independently**",
        "#96 and #142",
        "not toolkit-retention blockers",
        "separate explicit maintainer decision",
        "reviewed and integrated",
    ):
        assert boundary in record


def test_live_r2_status_documents_link_the_repeat_without_pending_integration_claims() -> None:
    for path in (
        "docs/architecture/adr-ui-toolkit.md",
        "docs/engineering/evals.md",
        "docs/engineering/product-milestones.md",
        "docs/engineering/quality-gates.md",
        "docs/ui/p0-functional-desktop.md",
        "docs/ui/ui-adoption-readiness.md",
    ):
        current = _normalized_text(path)
        assert "r2-ui-architecture-review-repeat.md" in current
        assert R2_AUDITED_SHA in current
        for stale in (
            "integration remains pending",
            "Integration, repeated R2 and the explicit ADR decision remain future steps",
            "`review-r2` and `EVAL-R2-REVIEW-001` remain pending",
            "`review-r2` remains backlog",
        ):
            assert stale not in current
