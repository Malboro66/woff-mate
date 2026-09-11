# WoFF Mate SDD Specifications

This directory contains specifications only for issues explicitly selected for the Spec-Driven Development pilot.

Historical issues are not retrofitted automatically.

## Per-issue layout

```text
specs/<issue>-<slug>/
  spec.md
  plan.md
  tasks.md
```

## Lifecycle

- `spec.md` starts as `Draft`.
- Only the maintainer can approve a specification revision.
- Production implementation requires `Status: Approved`.
- `plan.md` explains how to implement the approved behavior without redefining it.
- `tasks.md` decomposes the plan into small executable units and validation steps.
- If implementation evidence contradicts the approved behavior, stop the affected path and return the spec to Draft rather than guessing.
- `Status: Implemented` is recorded only after integration evidence exists.

See `docs/engineering/spec-driven-development.md` for the authoritative pilot process.
