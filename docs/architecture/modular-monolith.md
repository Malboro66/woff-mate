# Modular monolith architecture

## Purpose

WoFF Mate remains one Windows application with one SQLite database. The code is
split into logical modules so changes have explicit ownership and dependency
direction without requiring a distributed system or a full rewrite.

The executable module map lives in
[`project-graph.yaml`](project-graph.yaml). This document explains the intent
behind that graph.

## Source-of-truth order

1. The `main` branch and its GitHub Actions workflow define the final technical
   state.
2. `project-graph.yaml` defines module ownership, invariants, work dependencies,
   eval references, and gates.
3. The engineering documents define evaluation, gate, and autonomy policy.
4. GitHub issues and pull requests hold implementation evidence and review.
5. GitHub Projects provides the operational view. It does not replace repository
   contracts.

## Current logical modules

| Module | Responsibility | Main paths |
|---|---|---|
| `foundation` | Package identity and canonical versions | `woff/__init__.py`, `woff/version.py` |
| `domain` | Campaign entities, normalization, RPG rules, and narratives | `woff/models.py`, `woff/normalization.py`, `woff/rpg_system.py` |
| `persistence` | SQLite lifecycle, schema, transactions, and repositories | `woff/database.py`, `woff/repositories/` |
| `platform` | Local configuration and Windows integration | `woff/config.py`, `woff/win_registry.py` |
| `ingestion` | Decode, parse, catalog, and observe WoFF files | `woff/parsers/`, `woff/decode/`, catalogers |
| `application` | Coordinate campaign processing and watchdog activity | `woff/campaign_engine.py`, `woff/handler.py`, `woff/woff_watchdog.py` |
| `presentation` | Commands, reports, diagnostics, and diary editing | root CLIs and `woff/gerar_relatorio.py` |
| `governance` | Validate repository-owned engineering contracts | `scripts/validate_project_graph.py` |

Every production Python file included by the graph belongs to exactly one
logical module. Tests remain enforcement evidence and are not runtime modules.

## Dependency direction

The intended direction is:

```text
foundation
    ↓
domain       platform
    ↓           ↓
persistence   ingestion
       ↘       ↙
       application
            ↓
       presentation
```

`governance` is independent from runtime modules. Runtime modules must never
import the validator or PyYAML.

The graph records allowed and forbidden module dependencies. Its first version
validates declared relationships and source ownership. Static import enforcement
may be added later in a separate, reviewed change.

## Safety invariants

### DATA-001: pilot isolation

No operation may delete or modify data belonging to another pilot.

Current enforcement evidence:

- `woff/tests/test_career_selection.py`
- `woff/tests/test_woff_editor.py`

### DATA-002: recoverable schema changes

Every schema change requires a validated backup, migration checks, rollback,
and a reopen test.

Current enforcement evidence:

- `woff/tests/test_database_manager.py`
- `woff/tests/test_numeric_fields_migration.py`

## Change rules

Update `project-graph.yaml` when a pull request:

- creates, removes, or moves a production Python file
- changes a file's logical module
- changes an allowed or forbidden module dependency
- creates or changes a safety invariant
- changes a dependency between tracked work items
- adds, removes, or renames an eval or quality gate
- changes cycle membership or its official tracker

An internal change that preserves these relationships does not need a graph
edit.

## Known architectural work

The graph describes current ownership and intended dependency direction. It does
not declare open design debt solved. Examples remain tracked in GitHub:

- Issue #29 centralizes SQLite connections used by catalogers.
- Issue #34 introduces transaction composition across repositories.
- Issue #36 bounds event scheduling.
- Issue #45 validates configuration before startup.

These issues must update the graph only when their implementation changes a
declared relationship, invariant, eval, gate, or dependency.

## Validation

Run:

```bash
python scripts/validate_project_graph.py
python -m pytest woff/tests/test_architecture_contracts.py -q
```

Validation fails for missing paths, unmapped production files, duplicate
ownership, unknown modules, dependency cycles, invalid eval or gate references,
inconsistent satisfied dependencies, and invalid cycle membership.
