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
- Only a human maintainer with repository approval authority can approve a
  specification revision.
- Production implementation requires the complete deterministic approval
  contract, not `Status: Approved` alone. The approval record binds the spec
  path and revision to its full Git commit and a maintainer-authored GitHub
  approval link.
- `plan.md` explains how to implement the approved behavior without redefining it.
- `tasks.md` decomposes the plan into small executable units and validation steps.
- If a requirement or approval payload changes, stop the affected implementation
  path, return the spec to `Draft`, increment `Revision`, clear the prior approval
  record, and obtain new maintainer approval rather than guessing.
- `Status: Implemented` is recorded only after integration evidence exists.
- Official Independent Reviewer passes start in a fresh isolated session with
  the clean evidence bundle defined by the policy; they precede and do not
  replace any required Codex Review.

See `docs/engineering/spec-driven-development.md` for the authoritative pilot process.
