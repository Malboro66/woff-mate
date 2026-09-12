# Issue #151 Implementation Tasks

Approved specification: Revision 1

- [x] T1 [R-01,R-02,R-03,R-04] Add failing configuration tests for output equality, descendant overlap, case/canonical aliases, component-aware siblings, and both persistent output fields.
  - Validate with the focused configuration test module.
- [x] T2 [R-04,R-11] Add failing synthetic alias tests for ordinary directory junctions on the output side and watched-root side, plus unresolved/broken supported aliases failing closed where the Windows environment permits.
  - Validate with the focused Issue #151 test module and record bounded unsupported-tag/symlink limitations.
- [x] T3 [R-05,R-08,R-09] Add failing watchdog regressions proving rejection precedes SQLite/discovery-log activity and preserves synthetic source bytes, including `Mission.log` and `Pilot{N}Dossier.txt` aliases.
  - Validate with the focused Issue #151 test module.
- [x] T4 [R-06,R-07,R-10] Add failing acceptance tests for valid external outputs, deterministic sanitized diagnostics, and Python 3.10-compatible public behavior.
  - Validate with focused and related configuration/watchdog tests.
- [x] T5 [R-01..R-11] Implement the smallest configuration-boundary filesystem identity check and wire it before output construction.
  - Validate by rerunning T1-T4 focused tests.
- [ ] T6 [R-10] Run the planned eval and repository gates: project graph, focused/related/full pytest, Pyright, and diff hygiene.
  - Record results in the completion report without changing the normative specification.