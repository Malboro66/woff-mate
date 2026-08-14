from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.validate_project_graph import (
    GraphValidationError,
    load_graph,
    validate_graph,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = REPOSITORY_ROOT / "docs" / "architecture" / "project-graph.yaml"


def _graph() -> dict[str, object]:
    return deepcopy(load_graph(GRAPH_PATH))


def test_project_graph_is_valid() -> None:
    validate_graph(REPOSITORY_ROOT, _graph())


def test_project_graph_rejects_a_missing_declared_path() -> None:
    graph = _graph()
    modules = graph["modules"]
    assert isinstance(modules, dict)
    foundation = modules["foundation"]
    assert isinstance(foundation, dict)
    paths = foundation["paths"]
    assert isinstance(paths, list)
    paths.append("woff/does_not_exist.py")

    with pytest.raises(GraphValidationError, match="does not match any file"):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_rejects_an_unmapped_source_file() -> None:
    graph = _graph()
    modules = graph["modules"]
    assert isinstance(modules, dict)
    presentation = modules["presentation"]
    assert isinstance(presentation, dict)
    paths = presentation["paths"]
    assert isinstance(paths, list)
    paths.remove("diagnostico.py")

    with pytest.raises(GraphValidationError, match="source files are not mapped"):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_rejects_an_unknown_module_dependency() -> None:
    graph = _graph()
    modules = graph["modules"]
    assert isinstance(modules, dict)
    application = modules["application"]
    assert isinstance(application, dict)
    dependencies = application["may_depend_on"]
    assert isinstance(dependencies, list)
    dependencies.append("unknown-module")

    with pytest.raises(GraphValidationError, match="unknown module"):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_rejects_an_unknown_eval_reference() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    assert isinstance(issue_34, dict)
    evals = issue_34["evals"]
    assert isinstance(evals, list)
    evals.append("EVAL-UNKNOWN-001")

    with pytest.raises(GraphValidationError, match="unknown eval"):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_rejects_an_unknown_gate_reference() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    assert isinstance(issue_34, dict)
    gates = issue_34["gates"]
    assert isinstance(gates, list)
    gates.append("Q-UNKNOWN")

    with pytest.raises(GraphValidationError, match="unknown gate"):
        validate_graph(REPOSITORY_ROOT, graph)


def test_satisfied_dependency_requires_a_completed_work_item() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_26 = work_items["issue-26"]
    assert isinstance(issue_26, dict)
    issue_26["state"] = "in_progress"

    with pytest.raises(
        GraphValidationError,
        match="marked satisfied but issue-26 is not done",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_cycle_rejects_a_member_missing_from_work_items() -> None:
    graph = _graph()
    cycles = graph["cycles"]
    assert isinstance(cycles, dict)
    cycle = cycles["cycle-3.3.0"]
    assert isinstance(cycle, dict)
    members = cycle["members"]
    assert isinstance(members, list)
    members.append("issue-999")

    with pytest.raises(GraphValidationError, match="unknown member"):
        validate_graph(REPOSITORY_ROOT, graph)


def test_pyyaml_remains_a_development_dependency() -> None:
    pyproject = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_section, optional_section = pyproject.split(
        "[project.optional-dependencies]", maxsplit=1
    )

    assert "PyYAML" not in project_section
    assert '"PyYAML>=6.0"' in optional_section


def test_runtime_modules_do_not_import_yaml() -> None:
    runtime_paths = [
        *REPOSITORY_ROOT.glob("*.py"),
        *(
            path
            for path in (REPOSITORY_ROOT / "woff").rglob("*.py")
            if "tests" not in path.parts
        ),
    ]
    offenders: list[str] = []
    for path in runtime_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports_yaml = any(
            (
                isinstance(node, ast.Import)
                and any(alias.name == "yaml" for alias in node.names)
            )
            or (isinstance(node, ast.ImportFrom) and node.module == "yaml")
            for node in ast.walk(tree)
        )
        if imports_yaml:
            offenders.append(path.relative_to(REPOSITORY_ROOT).as_posix())

    assert offenders == []
