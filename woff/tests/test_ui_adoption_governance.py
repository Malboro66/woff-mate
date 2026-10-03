"""Governance contracts for maintainer-available UI adoption evidence."""

from pathlib import Path
from typing import Any, cast

from scripts.validate_project_graph import load_graph


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _graph() -> dict[str, Any]:
    return cast(dict[str, Any], load_graph(ROOT / "docs/architecture/project-graph.yaml"))


def test_ui_toolkit_retention_is_separate_from_p1_live_gates() -> None:
    graph = _graph()
    gate = graph["gates"]["Q5-UI-ARCHITECTURE"]["description"]

    assert "Toolkit retention requires the bounded UI adoption-readiness contract" in gate
    assert "Windows 11 absence" in gate
    assert "clean-machine release validation do not block toolkit retention" in gate
    assert "Product Gates A/B remain separate prerequisites for P1/live integration" in gate
    assert "does not approve those gates or authorize live data" in gate

    assert graph["work_items"]["review-r2"]["state"] == "backlog"
    assert graph["evals"]["EVAL-R2-REVIEW-001"]["status"] == "planned"
    assert graph["work_items"]["issue-96"]["state"] == "backlog"
    assert graph["work_items"]["issue-142"]["state"] == "backlog"
    assert graph["evals"]["EVAL-WINGMAN-IDENTITY-001"]["status"] == "planned"
    assert graph["evals"]["EVAL-STARTUP-RECURSIVE-001"]["status"] == "planned"


def test_adr_records_maintainer_available_platform_scope_without_claiming_windows11() -> None:
    adr = _text("docs/architecture/adr-ui-toolkit.md")

    assert "Status: Proposed" in adr
    assert "Windows 10 is the physically validated maintainer reference platform" in adr
    assert "Windows 11 remains a target/upstream-compatible platform but is **not**" in adr
    assert "physically validated by WoFF Mate" in adr
    assert "its absence does not block toolkit retention" in adr
    assert "Product Gates A and B remain authoritative" in adr
    assert "they are not toolkit-retention prerequisites" in adr
    assert "Accepting this ADR in a later decision would therefore select a production UI" in adr
    assert "It would **not** authorize P1" in adr


def test_clean_machine_and_release_obligations_remain_deferred_not_waived() -> None:
    quality = _text("docs/engineering/quality-gates.md")
    policy = _text("docs/engineering/product-milestones.md")

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

    assert "Physical Windows 11 and clean-machine end-user execution are not prerequisites to toolkit retention" in policy
    assert "clean-machine remains later full-Q4/release/Gate-D evidence" in policy
    assert "Only after the toolkit is retained **and** all applicable Product Gate A/B conditions are satisfied" in policy
    assert "Toolkit retention does not authorize P1/live integration or approve Product Gate A/B" in policy


def test_first_r2_record_remains_historically_truthful_after_rescope() -> None:
    record = _text("docs/engineering/r2-ui-architecture-review.md")
    quality = _text("docs/engineering/quality-gates.md")
    policy = _text("docs/engineering/product-milestones.md")

    assert "HOLD / Conditional No-Go for production retention" in record
    assert "Windows 11 execution" in record
    assert "clean-machine validation" in record

    assert "this later re-scope does not rewrite the audit" in quality
    assert "does not rewrite the historical R2 HOLD" in policy
    assert "new revision-bound R2 Full Application Review **MUST** be performed" in quality
    assert "new revision-bound R2 Full Application Review **MUST** be performed" in policy
