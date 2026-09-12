# Specification

Issue: #151
Status: Draft
Revision: 1
Baseline: 9601ec29dc6640e1c932d156c9860406a0775205
Owner: maintainer

## Problem

WoFF Mate monitors configured WoFF roots as read-only sources, but the current
configuration contract accepts a persistent SQLite export or discovery log
whose path is the same as, or lies beneath, a monitored root. Startup then
opens or creates that output and can mutate the monitored source. A
case-insensitive Windows alias can make two differently spelled paths refer to
the same source.

This is a P2 data-safety defect within Issue #151. It is separate from Issue
#45's general configuration validation and Issue #48's discovery-log size and
retention policy.

## Goal

Make every configured monitored WoFF root read-only with respect to persistent
WoFF Mate outputs. Invalid output placement must be rejected deterministically
before SQLite or discovery-log output activity begins, while existing valid
output locations outside all monitored roots continue to work.

## Current evidence

The authoritative Q0 record is
`specs/151-output-path-isolation/q0-evidence.md`, produced by the separately
authorized Q0 execution session on 2026-09-12. It binds the reproduction to
exact `main` commit `9601ec29dc6640e1c932d156c9860406a0775205` and classifies it
as **reproduced**.

On Windows 10 with Python 3.10.11, using only synthetic files in temporary
directories:

- A case-only alias of `Mission.log` accepted as `discovery_log_path` was
  opened and appended to during `WoFFWatchdog` construction and a simulated
  discovery event.
- A case-only alias of an empty `Pilot1Dossier.txt` accepted as `export_path`
  was replaced by a SQLite database during watchdog construction.
- In both cases, configuration construction and an explicit `validate()` call
  accepted the configuration; `Path.samefile()` and
  `canonical_windows_path()` identified the source and output as equivalent
  beneath the watched root.

The current code validates watched-root overlap with other watched roots but
does not compare either output field with those roots. `WoFFWatchdog` then
constructs `DatabaseManager` and, in discovery mode, `DiscoveryLogger`; those
constructors create/open and mutate their configured paths.

The appended reparse-point follow-up in the same Q0 artifact, executed against
the same baseline on Windows 10 with Python 3.10.11, established that an
ordinary directory junction (`IO_REPARSE_TAG_MOUNT_POINT`) can be created
without elevation. Paths through that junction passed current validation,
while `os.path.realpath()` and `Path.resolve()` reached the monitored target
and `Path.samefile()` confirmed identity for existing paths. Both an aliased
`export_path` and an aliased `discovery_log_path` then mutated synthetic files
in the monitored target. A broken junction demonstrated that strict
resolution and `samefile()` can fail while non-strict resolution returns an
unverified spelling; current validation accepts that ambiguity and fails later
during output construction. Native symbolic-link creation failed with
`WinError 1314`, so no symlink traversal or mutation is claimed. Generic
reparse tags were not characterized.

Q0 also confirmed that #151 was not duplicated, obsoleted, or implemented by
#45, #48, or the later governance changes. Issue #45 is relevant prior
validation infrastructure only.

## Required behavior

The following requirements define the desired behavior without selecting an
implementation mechanism.

### R-01 — Read-only monitored roots

For every configured `watch_paths` root, neither `export_path` nor
`discovery_log_path` may identify a location at or below that root. No normal
WoFF Mate operation may use either persistent output as a target inside a
monitored WoFF source tree.

### R-02 — Both persistent output fields are covered

The isolation rule applies independently to `export_path` and
`discovery_log_path`, including when only one of the fields overlaps. It
applies whether the candidate output already exists or would be created.

### R-03 — Equality and containment are rejected

Configuration is invalid when an output path is equal to a watched root or is
contained beneath a watched root. Containment is component-boundary aware: a
similarly prefixed sibling path is not beneath the root merely because its
text starts with the root text.

### R-04 — Supported Windows canonical aliases are rejected

For the supported Windows path identity used by the repository, comparisons
must account deterministically for absolute path resolution, separator and
dot-segment normalization, supported extended-path prefix normalization, and
case-insensitive identity. An output spelled as a case-only or otherwise
supported canonical alias of a watched root or descendant must be rejected.
The contract covers both equality and containment and must not depend on the
output file already existing.

When a supported filesystem alias is present, the comparison must use its
filesystem-resolved identity as well as lexical identity. This includes
ordinary directory junctions and symbolic links when the operating system can
resolve them successfully and unambiguously. The policy is bounded by the
alias classes and reparse tags whose semantics are established by repository
evidence; it does not claim that every Windows reparse tag is equivalent.

If resolving an alias needed to establish output/source safety fails, is
ambiguous, or cannot distinguish an absent output suffix safely, validation
must fail closed before persistent output activity. A non-strict resolved
string alone is not sufficient evidence of safe identity.

### R-05 — Pre-open and pre-mutation validation

The complete output-isolation check must finish and reject the configuration
before any configured SQLite database or discovery log is opened, created,
appended, migrated, backed up, or otherwise mutated. Rejection must also occur
before watchdog startup work that could cause such output activity.

### R-06 — Valid external outputs remain valid

A configuration whose export and discovery-log paths are outside every
monitored root remains usable under the existing configuration contract. This
includes output paths that do not yet exist, provided they satisfy all other
existing validation rules. The change must not relocate or rewrite existing
valid output files.

### R-07 — Safe, privacy-preserving diagnostics

An isolation rejection identifies the invalid configuration field and the
reason, and is deterministic enough for callers and tests to distinguish it
from unrelated invalid configuration. Diagnostics must not include raw WoFF
campaign content, discovery previews, or unnecessary personal absolute paths.
Where a path or root must be referenced, use the repository's existing
sanitized identity/label conventions or an equivalently non-sensitive
representation. The local-only and offline contracts remain unchanged.

### R-08 — No source mutation on rejection

Rejecting a configuration must not modify, replace, truncate, append to, or
create output files at the rejected location, and must not alter bytes of any
synthetic or real monitored source. A regression test must compare source
bytes before and after rejection and cover both output fields.

### R-09 — Supported WoFF filenames remain protected

The approved WoFF-generated names used by discovery privacy policy, including
`Mission.log` and `Pilot{N}Dossier.txt`, cannot be selected as persistent
output targets at or beneath a monitored root, including through supported
Windows case aliases. This requirement is a consequence of R-01 through R-04,
not permission to broaden discovery preview or retention behavior.

### R-10 — Verification obligations

Implementation evidence must satisfy the planned
`EVAL-OUTPUT-PATH-ISOLATION-001`: canonical Windows path and case aliases do
not place SQLite or discovery-log outputs at or beneath a monitored WoFF root,
rejection precedes output creation/opening, and synthetic source bytes remain
unchanged. The issue's applicable gates are Q0, Q1, Q3, Q4, and Q5.

### R-11 — Junction and symbolic-link safety policy

An output reached through an ordinary directory junction or ordinary symbolic
link is invalid when its filesystem-resolved identity equals or is contained
by a monitored root. The same invariant applies whether the output already
exists or would be created beneath an existing alias. A resolution failure or
ambiguous alias identity is itself an invalid configuration and must be
reported before SQLite or discovery-log creation, opening, or mutation.

The implementation and regression evidence must distinguish supported junction
and symbolic-link semantics from other reparse-point tags. It must not treat
the `REPARSE_POINT` attribute alone as proof that all such entries have the
same target behavior.

## Invariants

- The monitored WoFF boundary remains read-only; local monitoring and local
  processing permitted by `PRIV-001` remain available.
- `DATA-001` remains intact: no operation may modify data belonging to another
  pilot. This specification adds output/source isolation and does not redefine
  `DATA-001` as a general filesystem rule.
- `PRIV-001`, `NET-001`, and `LIC-001` remain unchanged. No output-isolation
  diagnostic may transmit data or expose forbidden credentials.
- Discovery raw previews remain limited by the existing explicit filename
  allowlist and size policy. Issue #48 retention and concurrency behavior is
  out of scope.
- Configuration validation remains compatible with Python 3.10 and supported
  Windows behavior.
- No database schema or persisted campaign-data migration is authorized by
  this issue. If an implementation were to introduce one despite this scope,
  the repository's DATA-002 backup, rollback, integrity, and reopen contract
  would apply and the specification would require maintainer clarification.

## Scenarios

### S-01 — Export path equals a watched root

Given one valid synthetic watched root and an `export_path` naming that root,
When the configuration is validated,
Then validation rejects `export_path` before SQLite is opened or created, and
the watched root and its contents are byte-for-byte unchanged.

### S-02 — Discovery log is beneath a watched root

Given one valid synthetic watched root and a `discovery_log_path` naming a
descendant output location,
When the configuration is validated or the watchdog is constructed,
Then validation rejects `discovery_log_path` before the discovery log is
opened or created, and no discovery header or event is written.

### S-03 — Export path is a case-only alias of a supported WoFF file

Given a synthetic `Pilot1Dossier.txt` in a watched root and an
`export_path` spelled as its Windows case-insensitive alias,
When the configuration is validated,
Then validation rejects the configuration before SQLite activity and the
source bytes, size, and identity remain unchanged.

### S-04 — Discovery log is a case-only alias of Mission.log

Given a synthetic `Mission.log` in a watched root and a `discovery_log_path`
spelled as its Windows case-insensitive alias,
When the configuration is validated,
Then validation rejects the configuration before discovery-log activity and
the source bytes, size, and identity remain unchanged, including if a
discovery event would otherwise be delivered.

### S-05 — Canonical Windows spellings are equivalent

Given a watched root and output candidates expressed with supported
combinations of drive/name case, slash direction, dot segments, or the
repository-supported extended-path prefix,
When the candidates resolve to the root or a descendant under the repository's
canonical Windows identity,
Then the same equality/containment rejection applies deterministically.

### S-06 — Junction alias resolves inside a watched root

Given a synthetic watched root, an outside directory junction targeting that
root, and an output path spelled through the junction to either an existing
supported WoFF file or a not-yet-created descendant,
When the configuration is validated,
Then filesystem resolution identifies the physical monitored root and
validation rejects the output before SQLite or discovery-log activity, with
the synthetic target bytes unchanged.

### S-07 — Ambiguous or unresolvable alias fails closed

Given a synthetic broken junction or another supported alias for which
resolution needed to decide overlap fails or remains ambiguous,
When the configuration is validated,
Then validation rejects the configuration before persistent output creation,
opening, or mutation. It does not accept a non-strict unresolved spelling as
proof of safety, and it does not defer the error to database or log setup.

### S-08 — External output locations continue to work

Given valid watched roots and export and discovery-log paths outside all of
them, including non-existing paths in an external temporary output directory,
When the watchdog is constructed under its existing modes,
Then the configuration remains accepted and the existing output lifecycle is
available without changing the watched source bytes.

### S-09 — Similar prefix is not containment

Given a watched root `C:\data\woff` and an external candidate such as
`C:\data\woff-backup\output.db`,
When canonical containment is evaluated,
Then the candidate is not rejected solely because its text shares a prefix;
component boundaries determine containment.

### S-10 — Rejected configuration preserves synthetic source bytes

Given synthetic monitored files and an output candidate rejected by direct,
case-alias, descendant, or junction-overlap validation,
When validation and the attempted watchdog construction are exercised,
Then every monitored source's bytes, size, and digest remain unchanged, no
rejected output file is created or mutated, and no discovery header or SQLite
signature appears at the rejected target.

### S-11 — Diagnostic is actionable but sanitized

Given an output candidate that overlaps a watched root,
When validation rejects it,
Then the error names the affected field and overlap reason without exposing
raw campaign content or unnecessary personal absolute paths, and repeated
validation of the same synthetic configuration produces the same diagnostic
class and field identification.

## Failure behavior

An overlapping output configuration is an invalid configuration and must fail
closed. Callers must receive the repository's invalid-configuration failure
contract rather than a later SQLite, file-open, watcher, or migration error.
Existing configuration files must not be rewritten as a side effect of this
rejection. No best-effort startup, auto-detection fallback, database creation,
log creation, backup, or source mutation may bypass R-05 or R-08.

Missing or non-existing candidate output paths are still compared using the
supported canonical path identity; absence is not a reason to skip isolation.
Other invalid path types or blank values continue to follow the existing
configuration validation contract.

## Compatibility and migration

This is a configuration and startup-safety behavior change, not a schema
change. No database migration, backup, rollback, or reopen procedure is
authorized by this specification. Existing valid external output locations
remain compatible. Existing configurations that place an output at or beneath
a monitored root become deterministically invalid and require the user to
choose an external location; WoFF source files must not be moved or rewritten
automatically.

The supported runtime remains Python 3.10 through the repository's declared
Python range, with native Windows path behavior covered by Q4. The required
regression fixtures and diagnostics use synthetic or sanitized data only.

## Out of scope

- Discovery-log size, retention, rotation, coalescing, or write concurrency
  (Issue #48).
- Generic path-library refactoring unrelated to output/source isolation.
- Installer layout, release provenance, network behavior, or telemetry.
- Changing watched-root overlap rules, campaign identity semantics, or
  source-file parsing.
- Relocating, deleting, repairing, or backing up a rejected source file.
- Defining equivalent semantics for reparse-point tags not established by
  repository evidence, including mount points other than the exercised
  ordinary directory junction and generic name-surrogate tags.
- Claiming native live UNC, 8.3 short-name, ACL-denied, alias-loop, or race
  behavior that is not covered by the evidence or implementation validation.

## Acceptance mapping

| Issue criterion | Spec requirement/scenario |
| --- | --- |
| Reject `export_path` equal to or contained by a watched root | R-01, R-03, S-01 |
| Reject `discovery_log_path` equal to or contained by a watched root | R-01, R-02, R-03, S-02 |
| Prevent supported WoFF input filenames from being persistent output targets inside monitored roots | R-09, S-03, S-04 |
| Cover Windows case-insensitive/canonical aliases deterministically | R-04, S-03, S-04, S-05 |
| Explicitly define and test symlink/reparse-point policy where practical | R-04, R-11, S-06, S-07; Q-01 and Q-02 preserve native symlink and unsupported-tag limitations |
| Validate before SQLite/log creation or mutation | R-05, R-08, R-11, S-01, S-02, S-06, S-07 |
| Preserve existing valid external output locations | R-06, S-08 |
| Reproduce audit scenarios with temporary/synthetic files and prove no source-byte changes | R-08, S-03, S-04, S-06, S-07, S-10 |
| Preserve Python 3.10 compatibility | R-10, Compatibility and migration |
| Pass focused/full tests, Pyright, graph validation, applicable gates/eval, and `git diff --check` | R-10 and Open questions / evidence gaps Q-06 |

## Open questions / evidence gaps

### Q-01 — Native symbolic-link execution (non-blocking if bounded)

The follow-up could not create an ordinary directory symbolic link:
`os.symlink()` failed with Windows `WinError 1314`
(`ERROR_PRIVILEGE_NOT_HELD`). No elevation, Developer Mode, registry,
privilege, or policy change was attempted. The desired policy is nevertheless
defined: when an ordinary symbolic link can be resolved successfully and
unambiguously, its filesystem identity follows the same equality/containment
safety rule as a junction; a resolution failure or ambiguity fails closed. A
future Windows regression environment should exercise native symlink traversal
where practical, but this Draft does not claim that execution evidence exists.

### Q-02 — Other reparse-point tags (non-blocking if bounded)

The evidence directly covers only an ordinary directory junction with
`IO_REPARSE_TAG_MOUNT_POINT`. Generic reparse tags were not characterized.
The specification deliberately does not infer equivalent semantics from the
reparse-point attribute or from the junction result. Implementations must
identify supported alias classes/tags and fail closed when an unclassified tag
prevents an unambiguous safety decision. Additional tag coverage is not
required for approval unless the implementation claims support for those tags.

### Q-03 — Live UNC behavior (non-blocking if bounded)

No live UNC share was available in Q0. Lexical handling of the supported
extended UNC prefix was inspected, but native UNC alias behavior was not
executed. A maintainer may bound live UNC as unsupported/unverified for this
issue, or require a separate sanitized Windows test environment. The spec
must not claim live UNC coverage without evidence.

### Q-04 — 8.3 short-name aliases (non-blocking if bounded)

No 8.3 alias was exercised; availability is volume/system dependent. A
maintainer may explicitly classify short-name physical aliases as unsupported
or unverified for this issue, or require targeted Windows evidence. The spec
must not claim that lexical canonicalization covers them.

### Q-05 — ACL denial, loops, and filesystem races (non-blocking evidence gaps)

No explicit ACL-denied fixture, alias loop, or filesystem race was exercised.
The broken junction establishes the required unresolved-alias distinction, but
it does not prove behavior under permission denial, cycles, or concurrent path
replacement. Such cases must fail closed when they make the overlap decision
unsafe; implementation validation should cover practical fixtures without
claiming exhaustive race prevention.

### Q-06 — Final executable evidence

The Q0 artifact records baseline-focused tests, full pytest, Pyright, graph
validation, and `git diff --check` before this specification existed. The
implementation must still provide issue-specific regression evidence and
revision-bound Q1/Q3/Q4/Q5 records, including the planned eval and applicable
privacy/security checks. No implementation or approval is implied by the
existing Q0 validation results.

## Approval record

Approved revision: —
Approved spec commit: —
Approved by: —
Approval evidence: —

For `Status: Approved`, replace every placeholder above. `Approved revision`
must equal `Revision`; `Approved spec commit` must be the full Git SHA containing
this revision's exact approval payload; and `Approval evidence` must link to a maintainer-authored GitHub
comment/review that explicitly approves this specification path, revision, and
commit. The canonical approval payload from current committed Git content must
remain exactly identical to the canonical payload at that commit, and the
specification path must have no uncommitted changes. See
`docs/engineering/spec-driven-development.md#approval-contract` for the exact
payload boundary, UTF-8/LF canonicalization, and lifecycle-only exclusions.

If the approval payload changes, set `Status: Draft`, increment `Revision`, and
clear the prior approval record before requesting new maintainer approval.

## Implementation record

Integrated revision/PR: —
Validation evidence: —
