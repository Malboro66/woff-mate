# Bounded UI Adoption Readiness — Issue #177

Implementation in progress from verified main
`741bad8192517c4ade38e9e718845f086beff849` after #175 / PR #176.

This candidate validates PySide6 + Qt Widgets 6.11.2 with deterministic synthetic
fixtures. The UI toolkit ADR remains **Proposed**. Historical first R2 remains
**HOLD / Conditional No-Go for production retention**. P1 is not authorized and
Product Gates A, B, C and D remain unapproved. #96/#142 remain Gate A/P1 blockers,
not toolkit-retention blockers.

## Evaluation contract

- `EVAL-UI-ADOPTION-MATRIX-001`: real Python 3.10–3.14 source/UI smoke,
  optional dependency isolation and exactly one Qt binding.
- `EVAL-UI-ADOPTION-PACKAGE-001`: separate fixture-only candidate packaging,
  representative startup, keyboard/focus/accessibility and proportional physical
  Windows 10 launch/basic UIA delta.
- `EVAL-UI-ADOPTION-LICENSE-001`: actual bundle inventory, hashes, origins and
  engineering licensing disposition; remove Qt Virtual Keyboard and unnecessary
  modules/plugins and prevent their reintroduction.

Evidence is pending until executed and revision-bound. Linux offscreen and hosted
Windows CI cannot substitute for the maintainer's physical Windows 10 delta.
Unchanged P0 rendering/scaling evidence may be reused with explicit source hashes.

## Decision sequence and exclusions

Implementation → future integration into main → mandatory new revision-bound R2
Full Application Review → explicit maintainer ADR decision. No repeated R2 is
performed in this initial implementation pass.

Physical Windows 11, clean-machine/installer/updater/install-update-rollback,
signing, public provenance/distribution/release SBOM, Narrator/NVDA speech,
live SQLite/WoFF/parser/watchdog/query-service/network integration and P1 are
outside this issue. This work is engineering evidence, not legal certification.
