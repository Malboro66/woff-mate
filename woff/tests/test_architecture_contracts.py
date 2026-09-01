from __future__ import annotations

import ast
import hashlib
import importlib
import json
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
from scripts.validate_ui_v2_evidence import (
    SCREENS,
    validate_evidence as validate_ui_evidence,
    verify_manifest,
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

    for dependent in work_items.values():
        assert isinstance(dependent, dict)
        dependencies = dependent["depends_on"]
        assert isinstance(dependencies, list)
        for dependency in dependencies:
            if (
                isinstance(dependency, dict)
                and dependency.get("id") == "issue-34"
            ):
                dependency["status"] = "unsatisfied"
                if dependent.get("state") in {"ready", "in_progress", "done"}:
                    dependent["state"] = "blocked"


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
    issue_30 = work_items["issue-30"]
    assert isinstance(issue_34, dict)
    assert isinstance(issue_30, dict)
    _set_issue_34_incomplete_state(graph, state)
    issue_30["state"] = "backlog"
    issue_34["depends_on"] = [
        {"id": "issue-30", "status": "unsatisfied"}
    ]

    with pytest.raises(
        GraphValidationError,
        match=(
            f"work_items.issue-34 is {state} but dependency "
            "issue-30 is unsatisfied"
        ),
    ):
        validate_graph(REPOSITORY_ROOT, graph)


def test_blocked_work_item_accepts_unsatisfied_dependency() -> None:
    graph = _graph()
    work_items = graph["work_items"]
    assert isinstance(work_items, dict)
    issue_34 = work_items["issue-34"]
    issue_30 = work_items["issue-30"]
    assert isinstance(issue_34, dict)
    assert isinstance(issue_30, dict)
    _set_issue_34_incomplete_state(graph, "blocked")
    issue_30["state"] = "backlog"
    issue_34["depends_on"] = [
        {"id": "issue-30", "status": "unsatisfied"}
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


@pytest.mark.parametrize(
    "cycle_id", ["cycle-3.2.1", "cycle-3.3.0", "cycle-3.4.0"]
)
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
    cycle["state"] = "planned"
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
        ("issue-27", "issue-42"),
        ("issue-42", "issue-48"),
        ("issue-48", "issue-27"),
    ):
        item = work_items[item_id]
        assert isinstance(item, dict)
        item["depends_on"] = [{"id": dependency_id, "status": "unsatisfied"}]

    with pytest.raises(
        GraphValidationError,
        match=(
            "work item dependency cycle detected: .*issue-27.*issue-42.*issue-48"
            "|work item dependency cycle detected: .*issue-48.*issue-27.*issue-42"
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
    evals = graph["evals"]
    assert isinstance(cycles, dict) and isinstance(evals, dict)
    cycle = cycles["cycle-3.4.0"]
    assert isinstance(cycle, dict)
    cycle["state"] = "planned"
    cycle.pop("aggregate_eval", None)
    del evals["EVAL-CYCLE-340-001"]

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


def test_ui_read_only_foundation_contract() -> None:
    adr_path = REPOSITORY_ROOT / "docs" / "architecture" / "adr-ui-toolkit.md"
    foundation_path = REPOSITORY_ROOT / "docs" / "ui" / "read-only-foundation.md"
    assert adr_path.is_file()
    assert foundation_path.is_file()

    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/architecture/adr-ui-toolkit.md" in readme
    assert "docs/ui/read-only-foundation.md" in readme

    adr = adr_path.read_text(encoding="utf-8")
    assert re.search(r"^Status:\s*Proposed\s*$", adr, re.MULTILINE)
    assert "PySide6 + Qt Widgets" in adr
    assert re.search(r"proposed direction", adr, re.IGNORECASE)

    foundation = foundation_path.read_text(encoding="utf-8")
    for state in ("loading", "ready", "empty", "missing", "stale/unavailable", "error"):
        assert re.search(rf"`{re.escape(state)}`", foundation, re.IGNORECASE)
    assert "presentation -> application query services -> repositories -> SQLite" in foundation
    assert re.search(r"Presentation must never execute SQL", foundation)
    assert re.search(r"must never read WoFF files directly", foundation)
    assert re.search(r"Diary.*strictly read-only", foundation, re.DOTALL)

    pyproject = _load_pyproject()
    project = pyproject["project"]
    assert isinstance(project, dict)
    dependencies = project.get("dependencies", [])
    assert isinstance(dependencies, list)
    runtime_names = {_requirement_name(dependency) for dependency in dependencies}
    assert runtime_names.isdisjoint({"pyside2", "pyside6", "pyqt5", "pyqt6"})

    graph = _graph()
    work_items = graph["work_items"]
    evals = graph["evals"]
    cycles = graph["cycles"]
    assert isinstance(work_items, dict) and isinstance(evals, dict)
    assert isinstance(cycles, dict)
    issue = work_items["issue-56"]
    assert issue == {
        "title": "Define the read-only UI foundation and proposed toolkit",
        "module": "presentation",
        "state": "done",
        "evals": ["EVAL-UI-FOUNDATION-001"],
        "gates": ["Q0", "Q1"],
        "depends_on": [],
    }
    ui_eval = evals["EVAL-UI-FOUNDATION-001"]
    assert ui_eval["status"] == "implemented"
    assert ui_eval["enforced_by"] == ["woff/tests/test_architecture_contracts.py"]
    for cycle in cycles.values():
        assert isinstance(cycle, dict)
        assert "issue-56" not in cycle.get("members", [])


def test_ui_state_fixture_gate_and_followup_dependencies() -> None:
    from scripts.validate_ui_fixtures import load_catalog

    assert len(load_catalog()["fixtures"]) == 30
    matrix = REPOSITORY_ROOT / "docs" / "ui" / "screen-state-matrix.md"
    assert matrix.is_file()
    for document in ("README.md", "docs/ui/read-only-foundation.md", "docs/engineering/evals.md"):
        assert "screen-state-matrix.md" in (REPOSITORY_ROOT / document).read_text(encoding="utf-8")
    graph = _graph()
    work_items, evals = graph["work_items"], graph["evals"]
    assert isinstance(work_items, dict) and isinstance(evals, dict)
    assert work_items["issue-80"]["state"] == "done"
    assert evals["EVAL-UI-STATES-001"]["status"] == "implemented"
    assert evals["EVAL-UI-STATES-001"]["enforced_by"] == [
        "scripts/validate_ui_fixtures.py",
        "tests/test_ui_state_fixtures.py",
        "woff/tests/test_architecture_contracts.py",
    ]
    for issue in ("issue-81", "issue-82"):
        assert work_items[issue]["state"] == "backlog"
        assert {"id": "issue-80", "status": "satisfied"} in work_items[issue]["depends_on"]
        for eval_id in work_items[issue]["evals"]:
            assert evals[eval_id]["status"] == "planned"
    assert evals["EVAL-CYCLE-340-001"]["status"] == "planned"


def test_ui_v2_reference_contract() -> None:
    ui_root = REPOSITORY_ROOT / "docs" / "ui"
    reference_path = ui_root / "ui-v2-reference.md"
    visual_system_path = ui_root / "ui-v2-visual-system.md"
    walkthrough_path = ui_root / "ui-v2-walkthrough.md"
    rendered_audit_path = ui_root / "ui-v2-rendered-audit.md"
    evidence_root = ui_root / "evidence" / "ui-v2-site-2026-09-01-audit-4"
    evidence_readme_path = evidence_root / "README.md"
    evidence_checksums_path = evidence_root / "SHA256SUMS"
    evidence_measurements_path = evidence_root / "conformance-measurements.json"
    predecessor_evidence_root = ui_root / "evidence" / "ui-v2-site-2026-08-31"
    predecessor_evidence_readme_path = predecessor_evidence_root / "README.md"
    predecessor_evidence_checksums_path = predecessor_evidence_root / "SHA256SUMS"
    legacy_evidence_root = ui_root / "evidence" / "ui-v2-site-2026-08-29"
    legacy_evidence_readme_path = legacy_evidence_root / "README.md"
    legacy_evidence_checksums_path = legacy_evidence_root / "SHA256SUMS"
    quality_gates_path = REPOSITORY_ROOT / "docs" / "engineering" / "quality-gates.md"
    evals_path = REPOSITORY_ROOT / "docs" / "engineering" / "evals.md"
    for path in (
        reference_path,
        visual_system_path,
        walkthrough_path,
        rendered_audit_path,
        evidence_readme_path,
        evidence_checksums_path,
        evidence_measurements_path,
        predecessor_evidence_readme_path,
        predecessor_evidence_checksums_path,
        legacy_evidence_readme_path,
        legacy_evidence_checksums_path,
    ):
        assert path.is_file()
    assert quality_gates_path.is_file()
    assert evals_path.is_file()

    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    for path in (
        reference_path,
        visual_system_path,
        walkthrough_path,
        rendered_audit_path,
    ):
        assert path.relative_to(REPOSITORY_ROOT).as_posix() in readme
    site_url = "https://woff-mate-ui-v2.pilotohans.chatgpt.site/"
    assert site_url in readme

    reference = reference_path.read_text(encoding="utf-8")
    assert site_url in reference
    assert "active rendered source and replaces Figma" in reference
    assert "Figma is not current acceptance evidence" in reference
    assert "published-site audit" in reference
    required_coverage = reference.split("## Required rendered coverage", 1)[1].split(
        "## Future-gated modules",
        1,
    )[0]
    for screen_id in (
        "APP-00",
        "SEL-01",
        "OPR-01",
        "DOS-01",
        "DOS-02",
        "DOS-03",
        "DOS-04",
        "MIS-01",
        "MIS-02",
        "SQD-01",
        "SQD-02",
        "JRN-01",
        "RPT-01",
        "RPT-02",
        "SYS-01",
    ):
        assert f"`{screen_id}`" in reference
        assert f"`{screen_id}`" in required_coverage
    assert "stable `career_id`" in reference
    assert "`PilotN` is a persistent simulator slot label" in reference
    assert "Slots may be sparse" in reference
    assert "new `career_id`" in reference
    assert re.search(
        r"Two careers with the same display\s+name remain separate",
        reference,
    )
    assert "RFC, RNAS, and RAF remain distinct" in reference
    assert "Missing status does not become" in reference
    assert "`SYS-01` remains available when no career is selected" in reference
    normalized_statuses = (
        "Active",
        "KIA",
        "PoW",
        "MIA",
        "Invalided Out",
        "Survived War",
        "Lightly Wounded",
        "Seriously Wounded",
    )
    for status in normalized_statuses:
        assert f"`{status}`" in reference
    assert "displays that value verbatim" in reference
    for state in (
        "Authoritative zero",
        "Unknown",
        "Not available",
        "None recorded",
        "Partial record",
        "Missing",
        "Truncated",
        "Unsupported",
        "Unreadable",
        "Error",
    ):
        assert state in reference

    visual_system = visual_system_path.read_text(encoding="utf-8")
    for token in (
        "color.shell.graphite",
        "color.surface.paper",
        "material.paper.subtle",
        "material.felt.matte",
        "material.canvas.quiet",
        "material.wood.restrained",
        "material.brass.aged",
    ):
        assert f"`{token}`" in visual_system
    assert "All beige cards use `material.paper.subtle`" in visual_system
    assert "WCAG AA" in visual_system
    assert "published Site conformance verified" in visual_system
    assert "published-site audit" in visual_system
    for scale in ("100%", "125%", "150%", "200%"):
        assert scale in visual_system
    assert "## Keyboard model" in visual_system
    assert "no horizontal scrollbar" in visual_system
    assert "Synthetic`, `Fixture-backed`, or `Unavailable`" in visual_system
    assert "Page headings are programmatic focus targets" in visual_system
    assert "never made generally tabbable" in visual_system
    assert "Page heading or back route" not in visual_system
    for status in normalized_statuses:
        assert f"`{status}`" in visual_system

    walkthrough = walkthrough_path.read_text(encoding="utf-8")
    assert "Status: Passed" in walkthrough
    assert "Eval: `EVAL-UI-DESIGN-001`" in walkthrough
    assert "without a dead end" in walkthrough
    assert "Result: Passed." in walkthrough
    assert "Issue #80: formal deterministic state fixtures" in walkthrough
    assert "`h1#screen-title`" in walkthrough
    assert re.search(r"not a sequential Tab\s+stop", walkthrough)
    assert "## Published Site interaction evidence" in walkthrough
    assert "Published Site result: Pass" in walkthrough
    assert re.search(r"same-name career isolation", walkthrough, re.IGNORECASE)
    assert site_url in walkthrough
    assert "Page heading or contextual back route" not in walkthrough
    assert re.search(r"\| Text and controls .* \| Pass \|", walkthrough)
    assert "`EVAL-UI-DESIGN-001` passes and is `implemented`" in walkthrough
    assert "Issue #79 is `done`" in walkthrough
    assert (
        "Deleting `Pilot1` would leave `Pilot2` and `Pilot3` unchanged"
        in walkthrough
    )
    for status in normalized_statuses:
        assert f"`{status}`" in walkthrough

    rendered_audit = rendered_audit_path.read_text(encoding="utf-8")
    assert "Status: Passed" in rendered_audit
    assert site_url in rendered_audit
    assert "Browser viewport width: 1363 CSS pixels" in rendered_audit
    assert "Changing from RFC career `RFC-14A-08F2`" in rendered_audit
    assert "`h1#screen-title`" in rendered_audit
    assert "`EVAL-UI-DESIGN-001` passes and is implemented" in rendered_audit
    deployment_id = "appgdep_6a96d56b15608191b13155cbcb7f7204"
    source_commit = "cf20ea65049682d2fb84f33f329213b93ba0575e"
    evidence_set_digest = "164aabda86d7a7766345c9715d46815ce9c5ec8a4ae7c2e6b30444aabd6d992d"
    for value in (deployment_id, source_commit, evidence_set_digest):
        assert value in rendered_audit
    assert "immutable historical evidence" in rendered_audit
    for screen_id in SCREENS:
        assert f"`{screen_id}`" in rendered_audit
    for ratio in ("3.12:1", "4.61:1", "5.62:1"):
        assert ratio in rendered_audit
    for scale in ("100%", "125%", "150%", "200%"):
        assert f"Desktop {scale}" in rendered_audit
    assert "not browser zoom labels or native Windows DPI certification" in rendered_audit
    assert "does not contact or" in rendered_audit

    evidence_readme = evidence_readme_path.read_text(encoding="utf-8")
    assert "Evidence revision: `UIV2-SITE-2026-09-01-AUDIT-4`" in evidence_readme
    for value in (deployment_id, source_commit, evidence_set_digest):
        assert value in evidence_readme
    assert "synthetic fixture data" in evidence_readme
    assert "`sparse-slots-2-3` fixture has no `Pilot1` option" in evidence_readme
    assert verify_manifest(evidence_root) == evidence_set_digest

    measurements = json.loads(evidence_measurements_path.read_text(encoding="utf-8"))
    assert measurements["deployment"] == {
        "id": deployment_id,
        "savedVersion": 18,
        "savedVersionId": (
            "appgprj_6a8baac178c88191acc54dde62e1870d~"
            "appgver_659eb3bc64f081919436991e057f63a7"
        ),
        "sourceCommit": source_commit,
        "url": "https://woff-mate-ui-v2.pilotohans.chatgpt.site",
        "status": "succeeded",
    }
    # Replay observations: geometry, values/absence, controls and full Tab
    # sequences. Negative tests mutate each reviewed contract separately.
    # This does not browse or certify a later revision of the live Site.
    validate_ui_evidence(measurements)

    # Audit 3 remains byte-identical history, not current acceptance evidence.
    audit3_root = ui_root / "evidence" / "ui-v2-site-2026-08-31-audit-3"
    audit3_manifest = (audit3_root / "SHA256SUMS").read_text(encoding="ascii")
    assert hashlib.sha256(audit3_manifest.encode("ascii")).hexdigest() == (
        "5ff88aa30e908c3af4049ecd5adf0bae37bf8cbfa34c27516c0ccbace273bfac"
    )
    for line in audit3_manifest.splitlines():
        digest, filename = line.split("  ", 1)
        assert hashlib.sha256((audit3_root / filename).read_bytes()).hexdigest() == digest

    predecessor_deployment_id = "appgdep_6a9555f927b081919b6cc2f33e9f3ffb"
    predecessor_evidence_set_digest = (
        "a64fd0e67383d3cf828ec33edc225fde18df1a710833b648a838222938ee5ce9"
    )
    predecessor_evidence_readme = predecessor_evidence_readme_path.read_text(
        encoding="utf-8"
    )
    assert "Evidence revision: `UIV2-SITE-2026-08-31-AUDIT-2`" in (
        predecessor_evidence_readme
    )
    assert predecessor_deployment_id in predecessor_evidence_readme
    assert predecessor_evidence_set_digest in predecessor_evidence_readme
    predecessor_checksum_entries = []
    for line in predecessor_evidence_checksums_path.read_text(
        encoding="ascii"
    ).splitlines():
        digest, filename = line.split("  ", 1)
        evidence_path = predecessor_evidence_root / filename
        assert evidence_path.is_file()
        assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == digest
        predecessor_checksum_entries.append(f"{digest}  {filename}\n")
    assert len(predecessor_checksum_entries) == 13
    assert (
        hashlib.sha256("".join(predecessor_checksum_entries).encode("ascii")).hexdigest()
        == predecessor_evidence_set_digest
    )

    legacy_deployment_id = "69c0abd6-d843-4646-b141-f76723098421"
    legacy_evidence_set_digest = (
        "ef028e0f8a49663c1a5b7d835b61f4c5128b238a7dde0df0e0f8633d0892b161"
    )
    legacy_evidence_readme = legacy_evidence_readme_path.read_text(encoding="utf-8")
    assert "Evidence revision: `UIV2-SITE-2026-08-29-AUDIT-1`" in (
        legacy_evidence_readme
    )
    assert legacy_deployment_id in legacy_evidence_readme
    assert legacy_evidence_set_digest in legacy_evidence_readme
    legacy_checksum_entries = []
    for line in legacy_evidence_checksums_path.read_text(
        encoding="ascii"
    ).splitlines():
        digest, filename = line.split("  ", 1)
        evidence_path = legacy_evidence_root / filename
        assert evidence_path.is_file()
        assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == digest
        legacy_checksum_entries.append(f"{digest}  {filename}\n")
    assert len(legacy_checksum_entries) == 13
    assert (
        hashlib.sha256("".join(legacy_checksum_entries).encode("ascii")).hexdigest()
        == legacy_evidence_set_digest
    )

    quality_gates = quality_gates_path.read_text(encoding="utf-8")
    assert (
        "Issues #28, #35, #38, #41, #75, #79, #80, and #97 are complete"
        in quality_gates
    )
    assert "published UI V2" in quality_gates
    assert "pass the recorded" in quality_gates
    assert "rendered WCAG AA contrast" in quality_gates

    eval_catalog = evals_path.read_text(encoding="utf-8")
    assert "Issue #79 is complete" in eval_catalog
    assert "`EVAL-UI-DESIGN-001` is implemented" in eval_catalog
    assert "UIV2-SITE-2026-09-01-AUDIT-4" in eval_catalog
    assert site_url in eval_catalog
    assert "Site version 18" in eval_catalog

    pyproject = _load_pyproject()
    project = pyproject["project"]
    assert isinstance(project, dict)
    dependencies = project.get("dependencies", [])
    assert isinstance(dependencies, list)
    runtime_names = {_requirement_name(dependency) for dependency in dependencies}
    assert runtime_names.isdisjoint({"pyside2", "pyside6", "pyqt5", "pyqt6"})

    graph = _graph()
    work_items = graph["work_items"]
    evals = graph["evals"]
    assert isinstance(work_items, dict) and isinstance(evals, dict)
    assert work_items["issue-79"] == {
        "title": "Consolidate the approved UI V2 reference and visual system",
        "module": "presentation",
        "state": "done",
        "evals": ["EVAL-UI-DESIGN-001"],
        "gates": ["Q0", "Q1", "Q6-CYCLE-3.4.0"],
        "depends_on": [{"id": "issue-56", "status": "satisfied"}],
    }
    ui_eval = evals["EVAL-UI-DESIGN-001"]
    assert ui_eval["status"] == "implemented"
    assert re.search(r"published UI V2 Site", ui_eval["evidence"], re.IGNORECASE)
    assert "pass all 15 screen IDs" in ui_eval["evidence"]
    assert "WCAG AA text and non-text contrast" in ui_eval["evidence"]
    assert "28 complete Tab sequences" in ui_eval["evidence"]
    assert "mission-aircrew-report career isolation" in ui_eval["evidence"]
    assert "actual sparse Pilot2/Pilot3 list" in ui_eval["evidence"]
    assert ui_eval["enforced_by"] == [
        "woff/tests/test_architecture_contracts.py",
        "woff/tests/test_ui_v2_evidence.py",
    ]
