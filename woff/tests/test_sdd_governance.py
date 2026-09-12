"""Structural contracts for the repository SDD/custom-agent pilot."""

from pathlib import Path
from typing import Any, cast

import yaml

from scripts.validate_project_graph import load_graph


ROOT = Path(__file__).resolve().parents[2]
SDD_POLICY = ROOT / "docs" / "engineering" / "spec-driven-development.md"
SPEC_TEMPLATE = ROOT / "specs" / "_template" / "spec.md"
AGENTS = ROOT / ".github" / "agents"
READ_ONLY_GITHUB_TOOLS = [
    "github/issue_read",
    "github/search_issues",
    "github/pull_request_read",
    "github/search_pull_requests",
    "github/get_commit",
    "github/search_commits",
]
KNOWN_GITHUB_MUTATION_TOOLS = {
    "github/create_pull_request",
    "github/merge_pull_request",
    "github/pull_request_review_write",
    "github/update_pull_request",
    "github/update_pull_request_branch",
    "github/issue_write",
    "github/create_branch",
    "github/create_or_update_file",
    "github/delete_file",
    "github/delete_repository",
    "github/push_files",
}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter(path: Path) -> dict[str, Any]:
    parts = _text(path).split("---", 2)
    assert len(parts) == 3
    return cast(dict[str, Any], yaml.safe_load(parts[1]))


def _github_tools(frontmatter: dict[str, Any]) -> set[str]:
    return {
        tool
        for tool in cast(list[str], frontmatter["tools"])
        if tool.startswith("github/")
    }


def _canonical_committed_payload(content: bytes) -> str:
    return content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


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
    policy = " ".join(_text(SDD_POLICY).split())
    template = _text(SPEC_TEMPLATE)
    implementation = " ".join(
        _text(AGENTS / "woff-implementation.agent.md").split()
    )

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
        "current committed specification",
        "committed Git content",
        "Strictly decode each as UTF-8",
        "normalize CRLF and lone CR line endings to LF",
        "Do not trim or collapse whitespace",
        "no staged or unstaged uncommitted changes",
        "self-referential commit",
        "must not infer approval",
    ):
        assert required_contract in policy

    assert "no staged or unstaged uncommitted changes" in implementation
    assert "current checked-out commit" in implementation


def test_approval_payload_canonicalization_is_only_eol_insensitive() -> None:
    lf = b"Issue: #151\nRevision: 1\n## Required behavior\nMust isolate output.\n"
    crlf = lf.replace(b"\n", b"\r\n")
    cr = lf.replace(b"\n", b"\r")

    assert _canonical_committed_payload(lf) == _canonical_committed_payload(crlf)
    assert _canonical_committed_payload(lf) == _canonical_committed_payload(cr)
    assert _canonical_committed_payload(lf) != _canonical_committed_payload(
        lf.replace(b"Must isolate", b"May isolate")
    )
    assert _canonical_committed_payload(lf) != _canonical_committed_payload(
        lf.replace(b"output.", b"output. ")
    )


def test_defect_specs_require_external_baseline_bound_q0_evidence() -> None:
    policy = " ".join(_text(SDD_POLICY).split())
    architect = _text(AGENTS / "woff-spec-architect.agent.md")
    template = " ".join(_text(SPEC_TEMPLATE).split())

    for required_evidence in (
        "separately authorized execution session",
        "exact full `main` commit SHA tested",
        "command or deterministic procedure",
        "observed result",
        "repository evidence location and producer",
        "must stop and leave the specification in `Draft`",
    ):
        assert required_evidence in policy

    assert "Do not execute the reproduction" in architect
    assert "exact full `main` commit SHA" in template
    assert "execute" not in _frontmatter(
        AGENTS / "woff-spec-architect.agent.md"
    )["tools"]


def test_custom_agent_tool_boundaries_use_supported_allowlists() -> None:
    architect = _frontmatter(AGENTS / "woff-spec-architect.agent.md")
    implementation = _frontmatter(AGENTS / "woff-implementation.agent.md")
    reviewer = _frontmatter(AGENTS / "woff-independent-reviewer.agent.md")

    assert architect["tools"] == [
        "read",
        "search",
        "edit",
        *READ_ONLY_GITHUB_TOOLS,
    ]
    assert implementation["tools"] == [
        "read",
        "search",
        "edit",
        "execute",
        *READ_ONLY_GITHUB_TOOLS,
    ]
    assert reviewer["tools"] == ["read", "search", *READ_ONLY_GITHUB_TOOLS]
    assert "issue/PR identifiers" in reviewer["argument-hint"]

    for profile in (architect, implementation, reviewer):
        tools = cast(list[str], profile["tools"])
        assert all(not tool.endswith("/*") for tool in tools)

    assert _github_tools(architect) == set(READ_ONLY_GITHUB_TOOLS)
    assert _github_tools(implementation) == set(READ_ONLY_GITHUB_TOOLS)
    assert _github_tools(reviewer) == set(READ_ONLY_GITHUB_TOOLS)
    for profile in (architect, implementation, reviewer):
        assert KNOWN_GITHUB_MUTATION_TOOLS.isdisjoint(_github_tools(profile))

    assert {"edit", "execute", "agent"}.isdisjoint(reviewer["tools"])
    assert "identifier- or link-only" in _text(
        AGENTS / "woff-independent-reviewer.agent.md"
    )
    assert "execute" not in architect["tools"]
    assert "agent" not in implementation["tools"]


def test_sdd_policy_requires_capability_enforcement_not_only_prose() -> None:
    policy = " ".join(_text(SDD_POLICY).split())

    for required_policy in (
        "Role prohibitions must also be reflected in tool capabilities",
        "Server-wide wildcards such as `github/*` are prohibited",
        "Prose restrictions remain defense in depth",
        "must not expose maintainer-capable GitHub credentials",
    ):
        assert required_policy in policy


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
