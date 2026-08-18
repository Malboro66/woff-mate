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
    main,
    validate_graph,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = REPOSITORY_ROOT / "docs" / "architecture" / "project-graph.yaml"
_REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _imports_forbidden_runtime_dependency(source: str) -> bool:
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
        or (
            isinstance(node, ast.Import)
            and any(
                alias.name == "scripts.validate_project_graph"
                for alias in node.names
            )
        )
        or (
            isinstance(node, ast.ImportFrom)
            and (
                node.module == "scripts.validate_project_graph"
                or (
                    node.module == "scripts"
                    and any(
                        alias.name == "validate_project_graph"
                        for alias in node.names
                    )
                )
            )
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


def _set_issue_34_incomplete_state(
    graph: dict[str, object], state: str
) -> None:
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    assert isinstance(issue_34, dict)
    issue_34["state"] = state

    for dependent_id in ("issue-37", "issue-43"):
        dependent = work_items[dependent_id]
        assert isinstance(dependent, dict)
        dependencies = dependent["depends_on"]
        assert isinstance(dependencies, list)
        issue_34_dependency = next(
            dependency
            for dependency in dependencies
            if isinstance(dependency, dict)
            and dependency.get("id") == "issue-34"
        )
        issue_34_dependency["status"] = "unsatisfied"


def test_project_graph_is_valid() -> None:
    validate_graph(REPOSITORY_ROOT, _graph())


@pytest.mark.parametrize("version", [True, 1.0, "1"])
def test_project_graph_rejects_non_integer_version_one(version: object) -> None:
    graph = _graph()
    graph["version"] = version

    with pytest.raises(
        GraphValidationError,
        match="project graph version must be 1",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


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


@pytest.mark.parametrize(
    "pattern",
    [
        "C:/tmp/evidence.py",
        r"C:\tmp\evidence.py",
        r"\\server\share\evidence.py",
        "/tmp/evidence.py",
        "../evidence.py",
        r"..\evidence.py",
    ],
)
def test_project_graph_rejects_unsafe_patterns_in_either_path_syntax(
    pattern: str,
) -> None:
    graph = _graph()
    invariant = graph["invariants"]["DATA-001"]  # type: ignore[index]
    invariant["enforced_by"] = [pattern]  # type: ignore[index]

    with pytest.raises(
        GraphValidationError,
        match="invariants.DATA-001.enforced_by must stay within the repository",
    ):
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


@pytest.mark.parametrize("invariant_id", ["DATA-001", "DATA-002"])
def test_project_graph_requires_data_safety_invariants(invariant_id: str) -> None:
    graph = _graph()
    invariants = graph["invariants"]
    assert isinstance(invariants, dict)
    del invariants[invariant_id]

    with pytest.raises(
        GraphValidationError,
        match=rf"invariants must include required invariants.*{invariant_id}",
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


@pytest.mark.parametrize("module", [None, "", ["persistence"]])
def test_project_graph_rejects_a_malformed_work_item_module(module: object) -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    assert isinstance(issue_34, dict)
    issue_34["module"] = module

    with pytest.raises(
        GraphValidationError,
        match="work_items.issue-34.module must be a non-empty string",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_rejects_an_eval_without_owners() -> None:
    graph = _graph()
    evals = graph["evals"]
    work_items = graph["work_items"]
    assert isinstance(evals, dict) and isinstance(work_items, dict)
    evaluation = evals["EVAL-DB-001"]
    issue_34 = work_items["issue-34"]
    assert isinstance(evaluation, dict) and isinstance(issue_34, dict)
    evaluation["work_items"] = []
    item_evals = issue_34["evals"]
    assert isinstance(item_evals, list)
    item_evals.remove("EVAL-DB-001")

    with pytest.raises(
        GraphValidationError,
        match="evals.EVAL-DB-001.work_items must contain at least one work item",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


@pytest.mark.parametrize("enforced_by", [None, []])
def test_implemented_eval_requires_enforcement_paths(
    enforced_by: list[str] | None,
) -> None:
    graph = _graph()
    evals = graph["evals"]
    assert isinstance(evals, dict)
    evaluation = evals["EVAL-GOV-001"]
    assert isinstance(evaluation, dict)
    if enforced_by is None:
        evaluation.pop("enforced_by")
    else:
        evaluation["enforced_by"] = enforced_by

    with pytest.raises(
        GraphValidationError,
        match=(
            "evals.EVAL-GOV-001.enforced_by must contain at least one path "
            "when status is implemented"
        ),
    ):
        validate_graph(REPOSITORY_ROOT, graph)


@pytest.mark.parametrize("enforced_by", [None, []])
def test_planned_eval_may_omit_enforcement_paths(
    enforced_by: list[str] | None,
) -> None:
    graph = _graph()
    evals = graph["evals"]
    assert isinstance(evals, dict)
    evaluation = evals["EVAL-LINT-001"]
    assert isinstance(evaluation, dict)
    if enforced_by is None:
        evaluation.pop("enforced_by", None)
    else:
        evaluation["enforced_by"] = enforced_by

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


def test_project_graph_rejects_a_work_item_without_quality_gates() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_51 = work_items["issue-51"]
    assert isinstance(issue_51, dict)
    issue_51["gates"] = []

    with pytest.raises(
        GraphValidationError,
        match=(
            "work_items.issue-51.gates must contain at least one quality gate"
        ),
    ):
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


def test_unsatisfied_dependency_rejects_a_completed_work_item() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    assert isinstance(issue_34, dict)
    dependencies = issue_34["depends_on"]
    assert isinstance(dependencies, list)
    dependency = dependencies[0]
    assert isinstance(dependency, dict)
    dependency["status"] = "unsatisfied"

    with pytest.raises(
        GraphValidationError,
        match=(
            "work_items.issue-34 dependency issue-26 is marked unsatisfied "
            "but the dependency is done"
        ),
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_done_work_item_rejects_an_unsatisfied_dependency() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_51 = work_items["issue-51"]
    assert isinstance(issue_51, dict)
    issue_51["depends_on"] = [{"id": "issue-30", "status": "unsatisfied"}]

    with pytest.raises(
        GraphValidationError,
        match=(
            "work_items.issue-51 is done but dependency issue-30 is unsatisfied"
        ),
    ):
        validate_graph(REPOSITORY_ROOT, graph)


@pytest.mark.parametrize("state", ["ready", "in_progress"])
def test_implementation_work_item_requires_evals(state: str) -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    assert isinstance(issue_34, dict)
    _set_issue_34_incomplete_state(graph, state)
    issue_34["evals"] = []

    with pytest.raises(
        GraphValidationError,
        match=f"work_items.issue-34 is {state} but has no evals",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


@pytest.mark.parametrize("state", ["ready", "in_progress"])
def test_implementation_work_item_rejects_unsatisfied_dependency(
    state: str,
) -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    assert isinstance(issue_34, dict)
    _set_issue_34_incomplete_state(graph, state)
    issue_34["depends_on"] = [
        {"id": "issue-36", "status": "unsatisfied"}
    ]

    with pytest.raises(
        GraphValidationError,
        match=(
            f"work_items.issue-34 is {state} but dependency "
            "issue-36 is unsatisfied"
        ),
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_blocked_work_item_accepts_unsatisfied_dependency() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    assert isinstance(issue_34, dict)
    _set_issue_34_incomplete_state(graph, "blocked")
    issue_34["depends_on"] = [
        {"id": "issue-36", "status": "unsatisfied"}
    ]

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


def test_cycle_rejects_an_empty_member_list() -> None:
    graph = _graph()
    cycles = graph["cycles"]
    assert isinstance(cycles, dict)
    cycle = cycles["cycle-3.4.0"]
    assert isinstance(cycle, dict)
    cycle["members"] = []

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.4.0.members must contain at least one work item",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


@pytest.mark.parametrize("participant", ["issue-34", "issue-50"])
def test_cycle_requires_its_gate_on_every_participant(participant: str) -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    item = work_items[participant]
    assert isinstance(item, dict)
    gates = item["gates"]
    assert isinstance(gates, list)
    gates.remove("Q6-CYCLE-3.3.0")

    with pytest.raises(
        GraphValidationError,
        match=(
            f"cycles.cycle-3.3.0 participant {participant} "
            "must reference gate Q6-CYCLE-3.3.0"
        ),
    ):
        validate_graph(REPOSITORY_ROOT, graph)


@pytest.mark.parametrize("cycle_id", ["cycle-3.2.1", "cycle-3.3.0"])
def test_non_planned_cycle_requires_a_gate(cycle_id: str) -> None:
    graph = _graph()
    cycles = graph["cycles"]
    assert isinstance(cycles, dict)
    cycle = cycles[cycle_id]
    assert isinstance(cycle, dict)
    cycle.pop("gate")

    with pytest.raises(
        GraphValidationError,
        match=rf"cycles\.{re.escape(cycle_id)}\.gate must be a non-empty string",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_planned_cycle_may_omit_its_gate() -> None:
    graph = _graph()
    cycles = graph["cycles"]
    assert isinstance(cycles, dict)
    cycle = cycles["cycle-3.4.0"]
    assert isinstance(cycle, dict)
    cycle.pop("gate", None)

    validate_graph(REPOSITORY_ROOT, graph)


def test_pyyaml_remains_a_development_dependency() -> None:
    pyproject = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_section, optional_section = pyproject.split(
        "[project.optional-dependencies]", maxsplit=1
    )

    assert "PyYAML" not in project_section
    assert '"PyYAML>=6.0"' in optional_section


def test_runtime_modules_do_not_import_governance_dependencies() -> None:
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
        if _imports_forbidden_runtime_dependency(path.read_text(encoding="utf-8")):
            offenders.append(path.relative_to(REPOSITORY_ROOT).as_posix())

    assert offenders == []


@pytest.mark.parametrize(
    "source",
    [
        "import scripts.validate_project_graph",
        "from scripts.validate_project_graph import validate_graph",
        "def validate():\n    from scripts import validate_project_graph\n",
    ],
)
def test_governance_import_detection_covers_direct_and_nested_forms(
    source: str,
) -> None:
    assert _imports_forbidden_runtime_dependency(source)


@pytest.mark.parametrize(
    "source",
    ["import yaml", "import yaml.loader", "from yaml.loader import SafeLoader"],
)
def test_governance_import_detection_preserves_yaml_prohibition(source: str) -> None:
    assert _imports_forbidden_runtime_dependency(source)


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


def test_project_graph_loader_rejects_unhashable_mapping_key(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.yaml"
    graph_path.write_text("? [module, name]\n: value\n", encoding="utf-8")

    with pytest.raises(
        GraphValidationError,
        match=r"mapping key \['module', 'name'\].*must be hashable",
    ):
        load_graph(graph_path)


def test_cli_reports_unhashable_mapping_key_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    graph_path = tmp_path / "graph.yaml"
    graph_path.write_text("? [module, name]\n: value\n", encoding="utf-8")

    assert main([str(graph_path)]) == 1
    captured = capsys.readouterr()
    assert "mapping key ['module', 'name']" in captured.err
    assert "Traceback" not in captured.err


def test_project_graph_loader_accepts_valid_yaml(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.yaml"
    graph_path.write_text("version: 1\nroot:\n  nested: value\n", encoding="utf-8")

    assert load_graph(graph_path) == {"version": 1, "root": {"nested": "value"}}


def test_cli_prints_a_valid_absolute_graph_path_outside_repository(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    graph_path = tmp_path / "project-graph.yaml"
    graph_path.write_text(GRAPH_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    assert not graph_path.is_relative_to(REPOSITORY_ROOT)

    assert main([str(graph_path)]) == 0
    assert f"project graph is valid: {graph_path}" in capsys.readouterr().out


def test_cli_rejects_windows_absolute_pattern_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    graph_text = GRAPH_PATH.read_text(encoding="utf-8").replace(
        "      - woff/tests/test_woff_editor.py\n",
        r"      - C:\tmp\evidence.py" + "\n",
        1,
    )
    graph_path = tmp_path / "malformed-graph.yaml"
    graph_path.write_text(graph_text, encoding="utf-8")

    assert main([str(graph_path)]) == 1
    captured = capsys.readouterr()
    assert "must stay within the repository" in captured.err
    assert "Traceback" not in captured.err


def test_cli_rejects_malformed_tracker_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    graph_text = GRAPH_PATH.read_text(encoding="utf-8").replace(
        "    tracker: issue-50\n",
        "    tracker: []\n",
        1,
    )
    graph_path = tmp_path / "malformed-graph.yaml"
    graph_path.write_text(graph_text, encoding="utf-8")

    assert main([str(graph_path)]) == 1
    captured = capsys.readouterr()
    assert "cycles.cycle-3.3.0.tracker must be a non-empty string" in captured.err
    assert "Traceback" not in captured.err


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


@pytest.mark.parametrize("status", [None, "", [], {}])
def test_project_graph_rejects_malformed_eval_status_types(status: object) -> None:
    graph = _graph()
    evaluation = graph["evals"]["EVAL-DB-001"]  # type: ignore[index]
    evaluation["status"] = status  # type: ignore[index]

    with pytest.raises(
        GraphValidationError,
        match="evals.EVAL-DB-001.status must be a non-empty string",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


@pytest.mark.parametrize("state", [None, "", [], {}])
def test_project_graph_rejects_malformed_work_item_states(state: object) -> None:
    graph = _graph()
    item = graph["work_items"]["issue-30"]  # type: ignore[index]
    item["state"] = state  # type: ignore[index]

    with pytest.raises(
        GraphValidationError,
        match="work_items.issue-30.state must be a non-empty string",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


@pytest.mark.parametrize("status", [None, "", [], {}])
def test_project_graph_rejects_malformed_dependency_statuses(status: object) -> None:
    graph = _graph()
    item = graph["work_items"]["issue-27"]  # type: ignore[index]
    dependency = item["depends_on"][0]  # type: ignore[index]
    dependency["status"] = status

    with pytest.raises(
        GraphValidationError,
        match=r"work_items.issue-27.depends_on\[0\].status must be a non-empty string",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


@pytest.mark.parametrize("state", [None, "", [], {}])
def test_project_graph_rejects_malformed_cycle_states(state: object) -> None:
    graph = _graph()
    cycle = graph["cycles"]["cycle-3.4.0"]  # type: ignore[index]
    cycle["state"] = state  # type: ignore[index]

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.4.0.state must be a non-empty string",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_cli_rejects_malformed_enum_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    graph_text = GRAPH_PATH.read_text(encoding="utf-8").replace(
        "    status: planned\n",
        "    status: []\n",
        1,
    )
    graph_path = tmp_path / "malformed-graph.yaml"
    graph_path.write_text(graph_text, encoding="utf-8")

    assert main([str(graph_path)]) == 1
    captured = capsys.readouterr()
    assert "must be a non-empty string" in captured.err
    assert "Traceback" not in captured.err


def test_project_graph_rejects_missing_depends_on() -> None:
    graph = _graph()
    item = graph["work_items"]["issue-30"]  # type: ignore[index]
    del item["depends_on"]  # type: ignore[attr-defined]

    with pytest.raises(
        GraphValidationError,
        match="work_items.issue-30.depends_on must be a list",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_project_graph_accepts_explicit_empty_depends_on() -> None:
    graph = _graph()
    item = graph["work_items"]["issue-30"]  # type: ignore[index]
    item["depends_on"] = []  # type: ignore[index]

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


def test_done_work_item_rejects_an_empty_eval_list() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    evals = graph["evals"]
    assert isinstance(work_items, dict) and isinstance(evals, dict)
    issue_51 = work_items["issue-51"]
    assert isinstance(issue_51, dict)
    issue_51["evals"] = []
    del evals["EVAL-GOV-001"]

    with pytest.raises(
        GraphValidationError,
        match="work_items.issue-51 is done but has no evals",
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
        assert _imports_forbidden_runtime_dependency(source)
    assert not _imports_forbidden_runtime_dependency(
        "import json\nfrom pathlib import Path"
    )


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


@pytest.mark.parametrize("tracker", [[], {}, True, ""])
def test_cycle_rejects_malformed_tracker_types(tracker: object) -> None:
    graph = _graph()
    cycle = graph["cycles"]["cycle-3.4.0"]  # type: ignore[index]
    cycle["tracker"] = tracker  # type: ignore[index]

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.4.0.tracker must be a non-empty string",
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_cycle_allows_null_tracker_where_optional() -> None:
    graph = _graph()
    cycle = graph["cycles"]["cycle-3.4.0"]  # type: ignore[index]
    cycle["tracker"] = None  # type: ignore[index]

    validate_graph(REPOSITORY_ROOT, graph)


def test_cycle_preserves_unknown_tracker_diagnostic_for_valid_strings() -> None:
    graph = _graph()
    cycle = graph["cycles"]["cycle-3.4.0"]  # type: ignore[index]
    cycle["tracker"] = "issue-unknown"  # type: ignore[index]

    with pytest.raises(
        GraphValidationError,
        match="cycles.cycle-3.4.0 references unknown tracker issue-unknown",
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


def test_project_graph_rejects_member_assigned_to_multiple_cycles() -> None:
    graph = _graph()
    cycles = graph["cycles"]
    assert isinstance(cycles, dict)
    cycle_350 = cycles["cycle-3.5.0"]
    assert isinstance(cycle_350, dict)
    members = cycle_350["members"]
    assert isinstance(members, list)
    members.append("issue-41")

    with pytest.raises(
        GraphValidationError,
        match=(
            "work item issue-41 is a member of both "
            "cycles.cycle-3.4.0 and cycles.cycle-3.5.0"
        ),
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_cycle_tracker_may_also_be_a_member_of_the_same_cycle() -> None:
    graph = _graph()
    cycles = graph["cycles"]
    assert isinstance(cycles, dict)
    cycle = cycles["cycle-3.2.1"]
    assert isinstance(cycle, dict)
    assert cycle["tracker"] in cycle["members"]

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


def test_completed_cycle_requires_aggregate_eval() -> None:
    graph = _graph()
    cycles = graph["cycles"]
    assert isinstance(cycles, dict)
    cycle = cycles["cycle-3.2.1"]
    assert isinstance(cycle, dict)
    cycle.pop("aggregate_eval")

    with pytest.raises(
        GraphValidationError,
        match=(
            "cycles.cycle-3.2.1.aggregate_eval must be a non-empty string"
        ),
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_planned_cycle_may_omit_aggregate_eval() -> None:
    graph = _graph()
    cycles = graph["cycles"]
    assert isinstance(cycles, dict)
    cycle = cycles["cycle-3.4.0"]
    assert isinstance(cycle, dict)
    cycle.pop("aggregate_eval", None)

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
