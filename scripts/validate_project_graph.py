#!/usr/bin/env python3
"""Validate the repository-owned WoFF Mate project graph."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, cast

import yaml


DEFAULT_GRAPH_PATH = Path("docs/architecture/project-graph.yaml")
VALID_WORK_ITEM_STATES = {
    "backlog",
    "ready",
    "in_progress",
    "blocked",
    "done",
    "tracking",
}
VALID_DEPENDENCY_STATES = {"satisfied", "unsatisfied"}
VALID_CYCLE_STATES = {"planned", "active", "completed"}
VALID_EVAL_STATUSES = {"planned", "implemented"}


class GraphValidationError(ValueError):
    """Raised when the project graph violates its declared contract."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys recursively."""


def _construct_mapping_without_duplicate_keys(
    loader: _UniqueKeySafeLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> Mapping[object, object]:
    seen: set[object] = set()
    for key_node, _value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            location = (
                f"line {key_node.start_mark.line + 1}, "
                f"column {key_node.start_mark.column + 1}"
            )
            raise GraphValidationError(f"duplicate key {key!r} at {location}")
        seen.add(key)
    return cast(
        Mapping[object, object],
        yaml.SafeLoader.construct_mapping(loader, node, deep=deep),
    )


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_without_duplicate_keys,
)


def load_graph(path: Path) -> dict[str, object]:
    """Load a graph with PyYAML's safe loader while rejecting duplicate keys."""

    try:
        loaded = yaml.load(
            path.read_text(encoding="utf-8"),
            Loader=_UniqueKeySafeLoader,
        )
    except OSError as exc:
        raise GraphValidationError(f"cannot read project graph {path}: {exc}") from exc
    except GraphValidationError:
        raise
    except yaml.YAMLError as exc:
        raise GraphValidationError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise GraphValidationError("project graph root must be a mapping")
    return loaded


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GraphValidationError(f"{location} must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise GraphValidationError(f"{location} keys must be strings")
    return value


def _string_list(value: object, location: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise GraphValidationError(f"{location} must be a list")
    result = list(value)
    if not all(isinstance(item, str) and item for item in result):
        raise GraphValidationError(f"{location} must contain non-empty strings")
    if len(result) != len(set(result)):
        raise GraphValidationError(f"{location} contains duplicate values")
    return result


def _safe_pattern(pattern: str, location: str) -> None:
    parsed = PurePosixPath(pattern)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise GraphValidationError(
            f"{location} must stay within the repository: {pattern}"
        )


def _expand_patterns(
    repository_root: Path,
    patterns: list[str],
    location: str,
    *,
    require_match: bool,
) -> set[str]:
    matches: set[str] = set()
    for pattern in patterns:
        _safe_pattern(pattern, location)
        pattern_matches = {
            path.relative_to(repository_root).as_posix()
            for path in repository_root.glob(pattern)
            if path.is_file()
        }
        if require_match and not pattern_matches:
            raise GraphValidationError(
                f"{location} pattern does not match any file: {pattern}"
            )
        matches.update(pattern_matches)
    return matches


def _validate_module_dependencies(modules: Mapping[str, Any]) -> None:
    module_names = set(modules)
    dependency_graph: dict[str, list[str]] = {}

    for module_name, raw_module in modules.items():
        module = _mapping(raw_module, f"modules.{module_name}")
        dependencies = _string_list(
            module.get("may_depend_on", []),
            f"modules.{module_name}.may_depend_on",
        )
        forbidden = _string_list(
            module.get("forbidden_dependencies", []),
            f"modules.{module_name}.forbidden_dependencies",
        )
        for dependency in dependencies + forbidden:
            if dependency not in module_names:
                raise GraphValidationError(
                    f"modules.{module_name} references unknown module {dependency}"
                )
            if dependency == module_name:
                raise GraphValidationError(
                    f"modules.{module_name} cannot depend on itself"
                )
        overlap = sorted(set(dependencies) & set(forbidden))
        if overlap:
            raise GraphValidationError(
                f"modules.{module_name} both allows and forbids {overlap}"
            )
        dependency_graph[module_name] = dependencies

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module_name: str, trail: list[str]) -> None:
        if module_name in visiting:
            cycle = " -> ".join(trail + [module_name])
            raise GraphValidationError(f"module dependency cycle detected: {cycle}")
        if module_name in visited:
            return
        visiting.add(module_name)
        for dependency in dependency_graph[module_name]:
            visit(dependency, trail + [module_name])
        visiting.remove(module_name)
        visited.add(module_name)

    for module_name in dependency_graph:
        visit(module_name, [])


def _validate_source_coverage(
    repository_root: Path,
    graph: Mapping[str, Any],
    modules: Mapping[str, Any],
) -> None:
    source_files = _mapping(graph.get("source_files"), "source_files")
    includes = _string_list(source_files.get("include"), "source_files.include")
    excludes = _string_list(
        source_files.get("exclude", []), "source_files.exclude"
    )
    tracked = _expand_patterns(
        repository_root,
        includes,
        "source_files.include",
        require_match=True,
    )
    tracked -= _expand_patterns(
        repository_root,
        excludes,
        "source_files.exclude",
        require_match=False,
    )

    assignments: dict[str, str] = {}
    for module_name, raw_module in modules.items():
        module = _mapping(raw_module, f"modules.{module_name}")
        patterns = _string_list(
            module.get("paths"), f"modules.{module_name}.paths"
        )
        module_files = _expand_patterns(
            repository_root,
            patterns,
            f"modules.{module_name}.paths",
            require_match=True,
        )
        for path in module_files:
            previous = assignments.get(path)
            if previous is not None:
                raise GraphValidationError(
                    f"source file {path} is mapped to both {previous} and {module_name}"
                )
            assignments[path] = module_name

    mapped = set(assignments)
    missing = sorted(tracked - mapped)
    if missing:
        raise GraphValidationError(f"source files are not mapped: {missing}")
    outside = sorted(mapped - tracked)
    if outside:
        raise GraphValidationError(
            f"module paths map files outside source_files: {outside}"
        )


def _validate_existing_paths(
    repository_root: Path,
    patterns: object,
    location: str,
) -> None:
    declared = _string_list(patterns, location)
    _expand_patterns(
        repository_root,
        declared,
        location,
        require_match=True,
    )


def _validate_invariants(repository_root: Path, graph: Mapping[str, Any]) -> None:
    invariants = _mapping(graph.get("invariants"), "invariants")
    for invariant_id, raw_invariant in invariants.items():
        invariant = _mapping(raw_invariant, f"invariants.{invariant_id}")
        statement = invariant.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            raise GraphValidationError(
                f"invariants.{invariant_id}.statement must be a non-empty string"
            )
        enforced_by = _string_list(
            invariant.get("enforced_by"),
            f"invariants.{invariant_id}.enforced_by",
        )
        if not enforced_by:
            raise GraphValidationError(
                f"invariants.{invariant_id}.enforced_by must contain at least one path"
            )
        _validate_existing_paths(
            repository_root,
            enforced_by,
            f"invariants.{invariant_id}.enforced_by",
        )


def _validate_evals(
    repository_root: Path,
    graph: Mapping[str, Any],
    work_items: Mapping[str, Any],
) -> Mapping[str, Any]:
    evals = _mapping(graph.get("evals"), "evals")
    for eval_id, raw_eval in evals.items():
        evaluation = _mapping(raw_eval, f"evals.{eval_id}")
        owners = _string_list(
            evaluation.get("work_items"), f"evals.{eval_id}.work_items"
        )
        for owner in owners:
            if owner not in work_items:
                raise GraphValidationError(
                    f"evals.{eval_id} references unknown work item {owner}"
                )
        status = evaluation.get("status")
        if status not in VALID_EVAL_STATUSES:
            raise GraphValidationError(
                f"evals.{eval_id}.status must be one of {sorted(VALID_EVAL_STATUSES)}"
            )
        evidence = evaluation.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            raise GraphValidationError(
                f"evals.{eval_id}.evidence must be a non-empty string"
            )
        enforced_by = evaluation.get("enforced_by", [])
        if enforced_by:
            _validate_existing_paths(
                repository_root,
                enforced_by,
                f"evals.{eval_id}.enforced_by",
            )
    return evals


def _validate_eval_owners(evals: Mapping[str, Any]) -> None:
    for eval_id, raw_eval in evals.items():
        evaluation = _mapping(raw_eval, f"evals.{eval_id}")
        owners = _string_list(
            evaluation.get("work_items"), f"evals.{eval_id}.work_items"
        )
        if not owners:
            raise GraphValidationError(
                f"evals.{eval_id}.work_items must contain at least one work item"
            )


def _validate_gates(graph: Mapping[str, Any]) -> Mapping[str, Any]:
    gates = _mapping(graph.get("gates"), "gates")
    for gate_id, raw_gate in gates.items():
        gate = _mapping(raw_gate, f"gates.{gate_id}")
        description = gate.get("description")
        if not isinstance(description, str) or not description.strip():
            raise GraphValidationError(
                f"gates.{gate_id}.description must be a non-empty string"
            )
    return gates


def _declared_dependencies(item: Mapping[str, Any], item_id: str) -> list[str]:
    dependencies = item.get("depends_on", [])
    if not isinstance(dependencies, Sequence) or isinstance(
        dependencies,
        (str, bytes),
    ):
        raise GraphValidationError(f"work_items.{item_id}.depends_on must be a list")
    result: list[str] = []
    for index, raw_dependency in enumerate(dependencies):
        dependency = _mapping(
            raw_dependency,
            f"work_items.{item_id}.depends_on[{index}]",
        )
        dependency_id = dependency.get("id")
        if isinstance(dependency_id, str):
            result.append(dependency_id)
    return result


def _validate_work_item_dependency_cycles(work_items: Mapping[str, Any]) -> None:
    dependency_graph: dict[str, list[str]] = {}
    for item_id, raw_item in work_items.items():
        item = _mapping(raw_item, f"work_items.{item_id}")
        dependency_graph[item_id] = _declared_dependencies(item, item_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(item_id: str, trail: list[str]) -> None:
        if item_id in visiting:
            if item_id in trail:
                cycle_trail = trail[trail.index(item_id):] + [item_id]
            else:
                cycle_trail = trail + [item_id]
            cycle = " -> ".join(cycle_trail)
            raise GraphValidationError(f"work item dependency cycle detected: {cycle}")
        if item_id in visited:
            return
        visiting.add(item_id)
        for dependency_id in dependency_graph[item_id]:
            if dependency_id in dependency_graph:
                visit(dependency_id, trail + [item_id])
        visiting.remove(item_id)
        visited.add(item_id)

    for item_id in dependency_graph:
        visit(item_id, [])


def _validate_reciprocal_eval_ownership(
    work_items: Mapping[str, Any],
    evals: Mapping[str, Any],
    aggregate_eval_ids: set[str],
) -> None:
    for item_id, raw_item in work_items.items():
        item = _mapping(raw_item, f"work_items.{item_id}")
        for eval_id in _string_list(
            item.get("evals", []),
            f"work_items.{item_id}.evals",
        ):
            evaluation = _mapping(evals[eval_id], f"evals.{eval_id}")
            owners = _string_list(
                evaluation.get("work_items"),
                f"evals.{eval_id}.work_items",
            )
            if item_id not in owners:
                raise GraphValidationError(
                    f"work_items.{item_id} references eval {eval_id} "
                    f"but evals.{eval_id} omits {item_id}"
                )
    for eval_id, raw_eval in evals.items():
        if eval_id in aggregate_eval_ids:
            continue
        evaluation = _mapping(raw_eval, f"evals.{eval_id}")
        for item_id in _string_list(
            evaluation.get("work_items"),
            f"evals.{eval_id}.work_items",
        ):
            item = _mapping(work_items[item_id], f"work_items.{item_id}")
            item_evals = _string_list(
                item.get("evals", []),
                f"work_items.{item_id}.evals",
            )
            if eval_id not in item_evals:
                raise GraphValidationError(
                    f"evals.{eval_id} lists {item_id} "
                    f"but work_items.{item_id} omits {eval_id}"
                )


def _validate_completed_cycle_member_evidence(
    cycle_id: str,
    members: list[str],
    work_items: Mapping[str, Any],
    evals: Mapping[str, Any],
) -> None:
    for member in members:
        member_item = _mapping(work_items[member], f"work_items.{member}")
        for eval_id in _string_list(
            member_item.get("evals", []),
            f"work_items.{member}.evals",
        ):
            evaluation = _mapping(evals[eval_id], f"evals.{eval_id}")
            status = evaluation.get("status")
            if status != "implemented":
                raise GraphValidationError(
                    f"cycles.{cycle_id} completed member {member} "
                    f"eval {eval_id} is {status}"
                )
        dependencies = member_item.get("depends_on", [])
        if not isinstance(dependencies, Sequence) or isinstance(
            dependencies,
            (str, bytes),
        ):
            raise GraphValidationError(f"work_items.{member}.depends_on must be a list")
        for index, raw_dependency in enumerate(dependencies):
            dependency = _mapping(
                raw_dependency,
                f"work_items.{member}.depends_on[{index}]",
            )
            dependency_id = dependency.get("id")
            if dependency.get("status") != "satisfied":
                raise GraphValidationError(
                    f"cycles.{cycle_id} completed member {member} "
                    f"dependency {dependency_id} is {dependency.get('status')}"
                )


def _validate_done_work_item_evals(
    work_items: Mapping[str, Any],
    evals: Mapping[str, Any],
) -> None:
    for item_id, raw_item in work_items.items():
        item = _mapping(raw_item, f"work_items.{item_id}")
        if item.get("state") != "done":
            continue
        for eval_id in _string_list(
            item.get("evals", []),
            f"work_items.{item_id}.evals",
        ):
            evaluation = _mapping(evals[eval_id], f"evals.{eval_id}")
            if evaluation.get("status") != "implemented":
                raise GraphValidationError(
                    f"work_items.{item_id} is done but eval {eval_id} "
                    f"is {evaluation.get('status')}"
                )


def _validate_work_items(
    graph: Mapping[str, Any],
    modules: Mapping[str, Any],
    evals: Mapping[str, Any],
    gates: Mapping[str, Any],
) -> Mapping[str, Any]:
    work_items = _mapping(graph.get("work_items"), "work_items")
    for item_id, raw_item in work_items.items():
        item = _mapping(raw_item, f"work_items.{item_id}")
        module = item.get("module")
        if module not in modules:
            raise GraphValidationError(
                f"work_items.{item_id} references unknown module {module}"
            )
        state = item.get("state")
        if state not in VALID_WORK_ITEM_STATES:
            raise GraphValidationError(
                f"work_items.{item_id} has invalid state {state}"
            )
        for eval_id in _string_list(
            item.get("evals", []), f"work_items.{item_id}.evals"
        ):
            if eval_id not in evals:
                raise GraphValidationError(
                    f"work_items.{item_id} references unknown eval {eval_id}"
                )
        for gate_id in _string_list(
            item.get("gates", []), f"work_items.{item_id}.gates"
        ):
            if gate_id not in gates:
                raise GraphValidationError(
                    f"work_items.{item_id} references unknown gate {gate_id}"
                )

    for item_id, raw_item in work_items.items():
        item = _mapping(raw_item, f"work_items.{item_id}")
        dependencies = item.get("depends_on", [])
        if not isinstance(dependencies, Sequence) or isinstance(
            dependencies, (str, bytes)
        ):
            raise GraphValidationError(
                f"work_items.{item_id}.depends_on must be a list"
            )
        dependency_ids: set[str] = set()
        for index, raw_dependency in enumerate(dependencies):
            dependency = _mapping(
                raw_dependency,
                f"work_items.{item_id}.depends_on[{index}]",
            )
            dependency_id = dependency.get("id")
            dependency_state = dependency.get("status")
            if not isinstance(dependency_id, str) or not dependency_id:
                raise GraphValidationError(
                    f"work_items.{item_id}.depends_on[{index}].id must be a string"
                )
            if dependency_id not in work_items:
                raise GraphValidationError(
                    f"work_items.{item_id} depends on unknown work item "
                    f"{dependency_id}"
                )
            if dependency_id == item_id:
                raise GraphValidationError(
                    f"work_items.{item_id} cannot depend on itself"
                )
            if dependency_id in dependency_ids:
                raise GraphValidationError(
                    f"work_items.{item_id} repeats dependency {dependency_id}"
                )
            dependency_ids.add(dependency_id)
            if dependency_state not in VALID_DEPENDENCY_STATES:
                raise GraphValidationError(
                    f"work_items.{item_id} dependency {dependency_id} has invalid "
                    f"status {dependency_state}"
                )
            dependency_item = _mapping(
                work_items[dependency_id], f"work_items.{dependency_id}"
            )
            if (
                dependency_state == "satisfied"
                and dependency_item.get("state") != "done"
            ):
                raise GraphValidationError(
                    f"work_items.{item_id} dependency is marked satisfied but "
                    f"{dependency_id} is not done"
                )
    _validate_work_item_dependency_cycles(work_items)
    return work_items


def _validate_unsatisfied_dependencies_target_incomplete_work(
    work_items: Mapping[str, Any],
) -> None:
    for item_id, raw_item in work_items.items():
        item = _mapping(raw_item, f"work_items.{item_id}")
        for index, raw_dependency in enumerate(item.get("depends_on", [])):
            dependency = _mapping(
                raw_dependency,
                f"work_items.{item_id}.depends_on[{index}]",
            )
            dependency_id = dependency.get("id")
            assert isinstance(dependency_id, str)
            dependency_item = _mapping(
                work_items[dependency_id], f"work_items.{dependency_id}"
            )
            if (
                dependency.get("status") == "unsatisfied"
                and dependency_item.get("state") == "done"
            ):
                raise GraphValidationError(
                    f"work_items.{item_id} dependency {dependency_id} is marked "
                    "unsatisfied but the dependency is done"
                )


def _validate_cycles(
    graph: Mapping[str, Any],
    work_items: Mapping[str, Any],
    evals: Mapping[str, Any],
    gates: Mapping[str, Any],
) -> None:
    cycles = _mapping(graph.get("cycles"), "cycles")
    for cycle_id, raw_cycle in cycles.items():
        cycle = _mapping(raw_cycle, f"cycles.{cycle_id}")
        state = cycle.get("state")
        if state not in VALID_CYCLE_STATES:
            raise GraphValidationError(
                f"cycles.{cycle_id} has invalid state {state}"
            )
        tracker = cycle.get("tracker")
        if tracker is not None and tracker not in work_items:
            raise GraphValidationError(
                f"cycles.{cycle_id} references unknown tracker {tracker}"
            )
        members = _string_list(
            cycle.get("members"), f"cycles.{cycle_id}.members"
        )
        if not members:
            raise GraphValidationError(
                f"cycles.{cycle_id}.members must contain at least one work item"
            )
        if state == "completed" and tracker is not None and tracker not in members:
            tracker_item = _mapping(work_items[tracker], f"work_items.{tracker}")
            if tracker_item.get("state") != "done":
                raise GraphValidationError(
                    f"cycles.{cycle_id} completed tracker {tracker} "
                    f"is {tracker_item.get('state')}"
                )
        for member in members:
            if member not in work_items:
                raise GraphValidationError(
                    f"cycles.{cycle_id} references unknown member {member}"
                )
            member_item = _mapping(work_items[member], f"work_items.{member}")
            if state == "completed" and member_item.get("state") != "done":
                raise GraphValidationError(
                    f"cycles.{cycle_id} completed member {member} "
                    f"is {member_item.get('state')}"
                )
        aggregate_eval = cycle.get("aggregate_eval")
        if aggregate_eval is not None and aggregate_eval not in evals:
            raise GraphValidationError(
                f"cycles.{cycle_id} references unknown eval {aggregate_eval}"
            )
        if aggregate_eval is not None:
            evaluation = _mapping(evals[aggregate_eval], f"evals.{aggregate_eval}")
            if state == "completed" and evaluation.get("status") != "implemented":
                raise GraphValidationError(
                    f"cycles.{cycle_id} aggregate eval {aggregate_eval} "
                    f"is {evaluation.get('status')}"
                )
            aggregate_owners = set(
                _string_list(
                    evaluation.get("work_items"),
                    f"evals.{aggregate_eval}.work_items",
                )
            )
            for member in members:
                if member not in aggregate_owners:
                    raise GraphValidationError(
                        f"cycles.{cycle_id} aggregate eval {aggregate_eval} "
                        f"must include member {member}"
                    )
            if tracker is not None:
                if tracker not in aggregate_owners:
                    raise GraphValidationError(
                        f"cycles.{cycle_id} aggregate eval {aggregate_eval} "
                        f"must include tracker {tracker}"
                    )
                tracker_item = _mapping(work_items[tracker], f"work_items.{tracker}")
                tracker_evals = _string_list(
                    tracker_item.get("evals", []),
                    f"work_items.{tracker}.evals",
                )
                if aggregate_eval not in tracker_evals:
                    raise GraphValidationError(
                        f"cycles.{cycle_id} tracker {tracker} "
                        f"must reference aggregate eval {aggregate_eval}"
                    )
            allowed_owners = set(members) | (
                {tracker} if tracker is not None else set()
            )
            extra_owners = sorted(aggregate_owners - allowed_owners)
            if extra_owners:
                raise GraphValidationError(
                    f"cycles.{cycle_id} aggregate eval {aggregate_eval} "
                    f"lists unrelated work items {extra_owners}"
                )
        if state == "completed":
            _validate_completed_cycle_member_evidence(
                cycle_id,
                members,
                work_items,
                evals,
            )
        gate = cycle.get("gate")
        if gate is not None and gate not in gates:
            raise GraphValidationError(
                f"cycles.{cycle_id} references unknown gate {gate}"
            )
        if gate is not None:
            participants = [*members]
            if tracker is not None and tracker not in participants:
                participants.append(tracker)
            for participant in participants:
                participant_item = _mapping(
                    work_items[participant],
                    f"work_items.{participant}",
                )
                participant_gates = _string_list(
                    participant_item.get("gates", []),
                    f"work_items.{participant}.gates",
                )
                if gate not in participant_gates:
                    raise GraphValidationError(
                        f"cycles.{cycle_id} participant {participant} "
                        f"must reference gate {gate}"
                    )


def validate_graph(repository_root: Path, graph: Mapping[str, Any]) -> None:
    """Validate graph structure, paths, references, and dependency state."""

    repository_root = repository_root.resolve()
    if graph.get("version") != 1:
        raise GraphValidationError("project graph version must be 1")

    modules = _mapping(graph.get("modules"), "modules")
    _validate_module_dependencies(modules)
    _validate_source_coverage(repository_root, graph, modules)
    _validate_invariants(repository_root, graph)

    work_items = _mapping(graph.get("work_items"), "work_items")
    gates = _validate_gates(graph)
    evals = _validate_evals(repository_root, graph, work_items)
    work_items = _validate_work_items(graph, modules, evals, gates)
    cycles = _mapping(graph.get("cycles"), "cycles")
    aggregate_eval_ids = {
        aggregate_eval
        for raw_cycle in cycles.values()
        for aggregate_eval in [
            _mapping(raw_cycle, "cycles.<cycle>").get("aggregate_eval")
        ]
        if isinstance(aggregate_eval, str)
    }
    _validate_cycles(graph, work_items, evals, gates)
    _validate_unsatisfied_dependencies_target_incomplete_work(work_items)
    _validate_done_work_item_evals(work_items, evals)
    _validate_reciprocal_eval_ownership(work_items, evals, aggregate_eval_ids)
    _validate_eval_owners(evals)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "graph",
        nargs="?",
        type=Path,
        default=DEFAULT_GRAPH_PATH,
        help="project graph path relative to the repository root",
    )
    args = parser.parse_args(argv)
    repository_root = Path(__file__).resolve().parents[1]
    graph_path = args.graph
    if not graph_path.is_absolute():
        graph_path = repository_root / graph_path

    try:
        validate_graph(repository_root, load_graph(graph_path))
    except GraphValidationError as exc:
        print(f"project graph validation failed: {exc}", file=sys.stderr)
        return 1

    try:
        display_path = graph_path.relative_to(repository_root)
    except ValueError:
        display_path = graph_path
    print(f"project graph is valid: {display_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
