from __future__ import annotations

import ast
import importlib
import re
import sys
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
_REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _imports_yaml(source: str) -> bool:
    tree = ast.parse(source)
    return any(
        (
            isinstance(node, ast.Import)
            and any(
                alias.name == "yaml" or alias.name.startswith("yaml.")
                for alias in node.names
            )
        )
        or (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and (node.module == "yaml" or node.module.startswith("yaml."))
        )
        for node in ast.walk(tree)
    )


def _load_pyproject() -> dict[str, object]:
    if sys.version_info >= (3, 11):
        toml_module = importlib.import_module("tomllib")
    else:
        try:
            toml_module = importlib.import_module("tomli")
        except ModuleNotFoundError:
            toml_module = importlib.import_module("pip._vendor.tomli")

    loaded = toml_module.loads(
        (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert isinstance(loaded, dict)
    return loaded


def _requirement_name(requirement: object) -> str:
    match = _REQUIREMENT_NAME_RE.match(str(requirement))
    assert match is not None, f"invalid requirement entry: {requirement!r}"
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


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


def test_project_graph_rejects_an_invariant_without_enforcement_paths() -> None:
    graph = _graph()
    invariants = graph["invariants"]
    assert isinstance(invariants, dict)
    invariant = invariants["DATA-001"]
    assert isinstance(invariant, dict)
    invariant["enforced_by"] = []

    with pytest.raises(
        GraphValidationError,
        match="invariants.DATA-001.enforced_by must contain at least one path",
    ):
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
        if _imports_yaml(path.read_text(encoding="utf-8")):
            offenders.append(path.relative_to(REPOSITORY_ROOT).as_posix())

    assert offenders == []


def test_project_graph_loader_rejects_duplicate_root_mapping_key(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.yaml"
    graph_path.write_text("version: 1\nversion: 2\n", encoding="utf-8")

    with pytest.raises(GraphValidationError, match="duplicate key.*version"):
        load_graph(graph_path)


def test_project_graph_loader_rejects_duplicate_nested_mapping_key(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.yaml"
    graph_path.write_text("root:\n  nested: first\n  nested: second\n", encoding="utf-8")

    with pytest.raises(GraphValidationError, match="duplicate key.*nested"):
        load_graph(graph_path)


def test_project_graph_loader_accepts_valid_yaml(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.yaml"
    graph_path.write_text("version: 1\nroot:\n  nested: value\n", encoding="utf-8")

    assert load_graph(graph_path) == {"version": 1, "root": {"nested": "value"}}


@pytest.mark.parametrize("status", [None, "", "complete", "Implemented"])
def test_project_graph_rejects_invalid_eval_status(status: object) -> None:
    graph = _graph()
    evals = graph["evals"]
    assert isinstance(evals, dict)
    evaluation = evals["EVAL-DB-001"]
    assert isinstance(evaluation, dict)
    if status is None:
        evaluation.pop("status")
    else:
        evaluation["status"] = status

    with pytest.raises(GraphValidationError, match="evals.EVAL-DB-001.status"):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_accepts_valid_eval_statuses() -> None:
    graph = _graph()
    evals = graph["evals"]
    assert isinstance(evals, dict)
    for eval_id in ("EVAL-DB-001", "EVAL-GOV-001"):
        evaluation = evals[eval_id]
        assert isinstance(evaluation, dict)
        assert evaluation["status"] in {"planned", "implemented"}

    validate_graph(REPOSITORY_ROOT, graph)


def test_done_work_item_rejects_a_planned_eval_outside_completed_cycle() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_30 = work_items["issue-30"]
    assert isinstance(issue_30, dict)
    issue_30["state"] = "done"

    with pytest.raises(
        GraphValidationError,
        match="work_items.issue-30 is done but eval EVAL-LINT-001 is planned",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_preserves_specific_self_dependency_validation() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    assert isinstance(issue_34, dict)
    issue_34["depends_on"] = [{"id": "issue-34", "status": "unsatisfied"}]

    with pytest.raises(
        GraphValidationError,
        match="work_items.issue-34 cannot depend on itself",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_rejects_two_item_dependency_cycle() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    issue_45 = work_items["issue-45"]
    assert isinstance(issue_34, dict) and isinstance(issue_45, dict)
    issue_34["depends_on"] = [{"id": "issue-45", "status": "unsatisfied"}]
    issue_45["depends_on"] = [{"id": "issue-34", "status": "unsatisfied"}]

    with pytest.raises(
        GraphValidationError,
        match=(
            "work item dependency cycle detected: .*issue-34.*issue-45"
            "|work item dependency cycle detected: .*issue-45.*issue-34"
        ),
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_rejects_three_item_dependency_cycle() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    for item_id, dependency_id in (
        ("issue-34", "issue-45"),
        ("issue-45", "issue-36"),
        ("issue-36", "issue-34"),
    ):
        item = work_items[item_id]
        assert isinstance(item, dict)
        item["depends_on"] = [{"id": dependency_id, "status": "unsatisfied"}]

    with pytest.raises(
        GraphValidationError,
        match=(
            "work item dependency cycle detected: .*issue-34.*issue-45.*issue-36"
            "|work item dependency cycle detected: .*issue-36.*issue-34.*issue-45"
        ),
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_accepts_acyclic_work_item_dependencies() -> None:
    validate_graph(REPOSITORY_ROOT, _graph())


def test_yaml_import_detection_covers_yaml_and_submodules() -> None:
    for source in (
        "import yaml",
        "import yaml.loader",
        "from yaml import safe_load",
        "from yaml.loader import SafeLoader",
    ):
        assert _imports_yaml(source)
    assert not _imports_yaml("import json\nfrom pathlib import Path")


def test_completed_cycle_rejects_incomplete_member() -> None:
    graph = _graph()
    cycles = graph["cycles"]
    work_items = graph["work_items"]
    assert isinstance(cycles, dict) and isinstance(work_items, dict)
    cycle = cycles["cycle-3.2.1"]
    issue_26 = work_items["issue-26"]
    assert isinstance(cycle, dict) and isinstance(issue_26, dict)
    issue_26["state"] = "ready"
    issue_34 = work_items["issue-34"]
    assert isinstance(issue_34, dict)
    issue_34["depends_on"] = [{"id": "issue-26", "status": "unsatisfied"}]
    issue_51 = work_items["issue-51"]
    assert isinstance(issue_51, dict)
    issue_51["depends_on"] = [{"id": "issue-26", "status": "unsatisfied"}]

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.2.1 completed member issue-26 is ready",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_completed_cycle_rejects_incomplete_tracker() -> None:
    graph = _graph()
    cycles = graph["cycles"]
    assert isinstance(cycles, dict)
    cycle = cycles["cycle-3.3.0"]
    assert isinstance(cycle, dict)
    cycle["state"] = "completed"

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.3.0 completed tracker issue-50 is tracking",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_completed_cycle_accepts_done_members() -> None:
    validate_graph(REPOSITORY_ROOT, _graph())


def test_active_cycle_accepts_incomplete_members_when_otherwise_consistent() -> None:
    validate_graph(REPOSITORY_ROOT, _graph())


def test_planned_cycle_accepts_incomplete_members_when_otherwise_consistent() -> None:
    graph = _graph()
    cycles = graph["cycles"]
    assert isinstance(cycles, dict)
    cycle = cycles["cycle-3.3.0"]
    assert isinstance(cycle, dict)
    cycle["state"] = "planned"
    validate_graph(REPOSITORY_ROOT, graph)


def test_pyyaml_dependency_contract_is_structural() -> None:
    pyproject = _load_pyproject()
    project = pyproject["project"]
    assert isinstance(project, dict)
    dependencies = project.get("dependencies", [])
    assert isinstance(dependencies, list)
    dev_dependencies = project["optional-dependencies"]["dev"]  # type: ignore[index]
    assert isinstance(dev_dependencies, list)

    assert "pyyaml" not in {_requirement_name(dependency) for dependency in dependencies}
    assert "pyyaml" in {_requirement_name(dependency) for dependency in dev_dependencies}


def test_pyyaml_dependency_matching_rejects_prefix_collision() -> None:
    assert _requirement_name("PyYAML>=6.0") == "pyyaml"
    assert _requirement_name("PyYAML-extra>=1.0") == "pyyaml-extra"
    assert _requirement_name("PyYAML-extra>=1.0") != "pyyaml"


def test_project_graph_rejects_work_item_eval_missing_reciprocal_owner() -> None:
    graph = _graph()
    evals = graph["evals"]
    assert isinstance(evals, dict)
    evaluation = evals["EVAL-DB-001"]
    assert isinstance(evaluation, dict)
    evaluation["work_items"] = []

    with pytest.raises(
        GraphValidationError,
        match="work_items.issue-34 references eval EVAL-DB-001 but evals.EVAL-DB-001 omits issue-34",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_rejects_eval_owner_missing_work_item_reference() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    assert isinstance(issue_34, dict)
    issue_34["evals"] = ["EVAL-DB-002"]

    with pytest.raises(
        GraphValidationError,
        match="evals.EVAL-DB-001 lists issue-34 but work_items.issue-34 omits EVAL-DB-001",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_accepts_valid_reciprocal_eval_relationships() -> None:
    validate_graph(REPOSITORY_ROOT, _graph())


def test_cycle_aggregate_eval_rejects_unrelated_eval() -> None:
    graph = _graph()
    cycles = graph["cycles"]
    assert isinstance(cycles, dict)
    cycle = cycles["cycle-3.3.0"]
    assert isinstance(cycle, dict)
    cycle["aggregate_eval"] = "EVAL-GOV-001"

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.3.0 aggregate eval EVAL-GOV-001 must include member issue-34",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_cycle_aggregate_eval_rejects_missing_required_member() -> None:
    graph = _graph()
    evals = graph["evals"]
    assert isinstance(evals, dict)
    aggregate_eval = evals["EVAL-CYCLE-330-001"]
    assert isinstance(aggregate_eval, dict)
    work_items = aggregate_eval["work_items"]
    assert isinstance(work_items, list)
    work_items.remove("issue-34")

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.3.0 aggregate eval EVAL-CYCLE-330-001 must include member issue-34",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_cycle_aggregate_eval_rejects_missing_tracker_when_tracker_is_listed() -> None:
    graph = _graph()
    evals = graph["evals"]
    assert isinstance(evals, dict)
    aggregate_eval = evals["EVAL-CYCLE-330-001"]
    assert isinstance(aggregate_eval, dict)
    work_items = aggregate_eval["work_items"]
    assert isinstance(work_items, list)
    work_items.remove("issue-50")

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.3.0 aggregate eval EVAL-CYCLE-330-001 must include tracker issue-50",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_cycle_aggregate_eval_accepts_documented_members_and_tracker() -> None:
    validate_graph(REPOSITORY_ROOT, _graph())


def test_completed_cycle_rejects_planned_member_eval() -> None:
    graph = _graph()
    evals = graph["evals"]
    assert isinstance(evals, dict)
    evaluation = evals["EVAL-DIARY-002"]
    assert isinstance(evaluation, dict)
    evaluation["status"] = "planned"

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.2.1 completed member issue-26 eval EVAL-DIARY-002 is planned",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_completed_cycle_rejects_planned_aggregate_eval() -> None:
    graph = _graph()
    evals = graph["evals"]
    assert isinstance(evals, dict)
    evaluation = evals["EVAL-DIARY-001"]
    assert isinstance(evaluation, dict)
    evaluation["status"] = "planned"

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.2.1 aggregate eval EVAL-DIARY-001 is planned",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_completed_cycle_rejects_unsatisfied_member_dependency() -> None:
    graph = _graph()
    cycles = graph["cycles"]
    work_items = graph["work_items"]
    evals = graph["evals"]
    assert isinstance(cycles, dict)
    assert isinstance(work_items, dict)
    assert isinstance(evals, dict)
    cycle = cycles["cycle-3.2.1"]
    issue_26 = work_items["issue-26"]
    assert isinstance(cycle, dict)
    assert isinstance(issue_26, dict)
    cycle["members"] = ["issue-26", "issue-51"]
    issue_51 = work_items["issue-51"]
    assert isinstance(issue_51, dict)
    issue_51["state"] = "done"
    issue_51["depends_on"] = [{"id": "issue-26", "status": "unsatisfied"}]
    aggregate = evals["EVAL-DIARY-001"]
    assert isinstance(aggregate, dict)
    aggregate["work_items"] = ["issue-26", "issue-51"]

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.2.1 completed member issue-51 dependency issue-26 is unsatisfied",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_cycle_aggregate_eval_rejects_tracker_omitting_aggregate_eval() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_50 = work_items["issue-50"]
    assert isinstance(issue_50, dict)
    issue_50["evals"] = []

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.3.0 tracker issue-50 must reference aggregate eval EVAL-CYCLE-330-001",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_cycle_aggregate_eval_rejects_unrelated_owner() -> None:
    graph = _graph()
    evals = graph["evals"]
    assert isinstance(evals, dict)
    aggregate_eval = evals["EVAL-CYCLE-330-001"]
    assert isinstance(aggregate_eval, dict)
    work_items = aggregate_eval["work_items"]
    assert isinstance(work_items, list)
    work_items.append("issue-51")

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.3.0 aggregate eval EVAL-CYCLE-330-001 lists unrelated work items",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_cycle_330_aggregate_eval_does_not_require_member_eval_references() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    assert isinstance(issue_34, dict)
    assert "EVAL-CYCLE-330-001" not in issue_34["evals"]

    validate_graph(REPOSITORY_ROOT, graph)
