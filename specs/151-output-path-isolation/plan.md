# Issue #151 Implementation Plan

Approved specification: Revision 1
Approved spec commit: 241f050abbbdf2f71f13549ac0b5214144ab2bca

## Strategy

1. Add a focused filesystem-identity validation helper at the configuration boundary. It will compare each persistent output with every configured watched root using component-aware canonical identities, resolve supported existing aliases on both sides, and fail closed when an identity decision is unavailable or ambiguous.
2. Invoke that validation after the existing field and watched-root validation, before watchdog construction can create or open SQLite or discovery-log outputs.
3. Add synthetic regression coverage for both output fields, equality, descendants, canonical/case aliases, junction aliases where available, unresolved aliases, external non-existing outputs, sibling prefixes, sanitized diagnostics, and unchanged source bytes.
4. Keep supported alias policy bounded to the evidence-backed filesystem behavior and preserve Python 3.10 compatibility.

## Validation

- Focused Issue #151 regression tests and related configuration/watchdog tests.
- `EVAL-OUTPUT-PATH-ISOLATION-001` evidence from synthetic outputs and source-byte snapshots.
- `python scripts/validate_project_graph.py`
- `python -m pytest -q`
- `pyright`
- `git diff --check`