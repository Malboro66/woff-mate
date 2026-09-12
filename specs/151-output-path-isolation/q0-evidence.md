# Issue #151 Q0 reproduction evidence

| Field | Value |
|---|---|
| Producer | VS Code Work Q0 execution session |
| Date | 2026-09-12 (America/Sao_Paulo) |
| Repository | `Malboro66/woff-mate` |
| Issue | [#151 — `[P2] Prevent output paths from overlapping monitored WoFF inputs`](https://github.com/Malboro66/woff-mate/issues/151) |
| Exact current `main` | `9601ec29dc6640e1c932d156c9860406a0775205` |
| Tested checkout | `spec/issue-151-output-path-isolation` at `9601ec29dc6640e1c932d156c9860406a0775205` |
| Q0 classification | **Reproduced** |

## Baseline binding

The investigation started before any artifact was created. The checkout was
clean, and `HEAD`, local `main`, local `origin/main`, the merge base, and the
GitHub Branch API result for current `main` all matched the required full SHA.
The topic branch has no commit beyond `main`.

Commands and results:

```powershell
git status --short --branch
# ## spec/issue-151-output-path-isolation

git rev-parse HEAD
# 9601ec29dc6640e1c932d156c9860406a0775205

git rev-parse main
# 9601ec29dc6640e1c932d156c9860406a0775205

git log -1 --format="%H %D %s" main
# 9601ec29dc6640e1c932d156c9860406a0775205 HEAD -> spec/issue-151-output-path-isolation, origin/main, origin/HEAD, main docs: reconcile SDD governance after issue 157 (#159)

git merge-base HEAD main
# 9601ec29dc6640e1c932d156c9860406a0775205

curl.exe -L --fail --silent --show-error https://api.github.com/repos/Malboro66/woff-mate/branches/main
# parsed .name = main
# parsed .commit.sha = 9601ec29dc6640e1c932d156c9860406a0775205
```

Because every baseline check matched, Q0 reproduction proceeded. No fetch,
checkout, reset, commit, push, pull-request operation, or GitHub mutation was
performed.

## Repository instructions and contracts inspected

- `AGENTS.md`, including exact-current-main historical checking, deterministic
  reproduction, synthetic-data safety, regression expectations, and repository
  hygiene.
- `docs/engineering/spec-driven-development.md`, especially the baseline-bound
  Q0 handoff and prohibition on specification work before adequate evidence.
- `docs/engineering/quality-gates.md`: Q0 historical/current/reproduction
  evidence; Q1 tests, static analysis, diff, and privacy requirements; Q3 file
  and concurrency evidence; Q4 native Windows evidence; Q5 revision-bound
  product-gate evidence.
- `docs/architecture/project-graph.yaml`:
  - `issue-151` is a `platform` backlog item;
  - its gates are Q0/Q1/Q3/Q4/Q5;
  - dependencies on `issue-45` and `issue-157` are `satisfied`;
  - `EVAL-OUTPUT-PATH-ISOLATION-001` is planned and requires canonical Windows
    path/case isolation, pre-open rejection, and unchanged synthetic source
    bytes.
- `docs/engineering/evals.md`, including the planned
  `EVAL-OUTPUT-PATH-ISOLATION-001` contract and the SDD/Q0-only state unlocked
  after Issue #157.
- `docs/engineering/security-baseline-2026-09-10.md`, which assigns the
  reproduced P2 data-safety finding to #151 and keeps Product Gate A
  unapproved.
- `docs/engineering/product-milestones.md`, which requires #151 before Gate A
  may claim safe operation against real WoFF roots.
- `docs/security/privacy-and-local-data.md`, including local-only operation,
  synthetic/sanitized discovery evidence, approved preview filenames, and the
  read-only WoFF boundary.
- `docs/architecture/modular-monolith.md`, including `DATA-001` and the recorded
  scope of Issue #45.

Contract clarification for the later specification: the graph and modular
monolith define `DATA-001` specifically as cross-pilot isolation (no operation
may delete or modify data belonging to another pilot). It is a relevant
data-safety invariant, but it does not by itself state the output-path rule.
The specific current authority for keeping outputs out of monitored WoFF roots
is Issue #151 together with `EVAL-OUTPUT-PATH-ISOLATION-001`; the privacy
contract separately says the companion reads game data and maintains its own
local state separately. This evidence does not silently reinterpret
`DATA-001` as a broader filesystem contract.

## Issue and history review

Issue #151 was read completely through the GitHub REST API. It is open, has no
comments, and describes the earlier audit reproduction at
`736c43df86d686c07aadd549c14105feaf59f89d`. Its required behavior is output
isolation and rejection before SQLite/log creation or source mutation.

Read-only GitHub retrieval used these endpoints:

```text
GET /repos/Malboro66/woff-mate/issues/151
GET /repos/Malboro66/woff-mate/issues/151/timeline
GET /repos/Malboro66/woff-mate/issues/45
GET /repos/Malboro66/woff-mate/issues/45/comments
GET /repos/Malboro66/woff-mate/issues/45/timeline
GET /repos/Malboro66/woff-mate/issues/48
GET /repos/Malboro66/woff-mate/issues/48/comments
GET /repos/Malboro66/woff-mate/issues/48/timeline
GET /repos/Malboro66/woff-mate/pulls/60
GET /repos/Malboro66/woff-mate/pulls/60/commits
GET /repos/Malboro66/woff-mate/pulls/156
GET /repos/Malboro66/woff-mate/pulls/158
GET /repos/Malboro66/woff-mate/pulls/159
```

Related evidence checked:

| Reference | Result for duplication/prior-fix analysis |
|---|---|
| Issue #45, `[P1] Validate and honor watchdog configuration before startup` | Closed. It covers field type/domain validation and runtime wiring, not relationships between output paths and watched roots. |
| PR #60 / merge `76f91df7333e7bb4ada5afae6f3cb05aa34a7dd9` | Integrated #45. Its three commits were `2b42a3ae6819a59b735b72ad54dc4a18246cf554`, `d8fbec5e97e94b0131bbb32616e0b414216342a2`, and `8db6828310a0b289beb48716fde3e3cd542247b7`. The implementation validates output values only as nonblank strings and therefore fixes only the earlier general-validation scope. |
| Issue #48, `[P2] Bound discovery log size and retention` | Still open. It concerns size, retention, rotation, coalescing, and concurrency, not placement relative to monitored inputs. No implementation PR is linked in its timeline. |
| PR #156 / merge `cdc2e3909c5683724762d308de010d07c05d17c6` | Governance-only registration of the Security Baseline and #151–#155. It explicitly did not implement #151. |
| Issue #157 and PR #158 / merge `6d136097c80a3aad9b7a6c339746a7ee28a1168f` | SDD governance foundation only; no production behavior changed. |
| PR #159 / merge and current baseline `9601ec29dc6640e1c932d156c9860406a0775205` | Reconciled the graph after #157 and unlocked only #151 specification/Q0 work; no #151 implementation. |
| Issue #151 timeline | Contains only cross-references from #156, #157, #158, and #159; no implementation PR, closing event, or implementing commit is linked. |
| Local history searches | `git log --all -S"discovery_log_path" -- woff` and `git log --all -S"export_path" -- woff/config.py woff/woff_watchdog.py` found the history above plus older introduction/cleanup changes, but no path-isolation implementation. |

The four commits after the earlier audit baseline and through current `main`
were PR #150 (native validation infrastructure), PR #156 (Security Baseline
governance), PR #158 (SDD governance), and PR #159 (SDD reconciliation).
Inspection of their stats and current affected code found no intervening output
path isolation change.

Conclusion of the historical check: #151 is not a duplicate of #45 or #48, is
not obsolete, and was not already or partially fixed by a later production
change. #45 is relevant prior partial infrastructure only: validation now runs
before startup work, but it lacks the cross-path rule required by #151.

## Current implementation evidence

Observed current behavior, without inferring a future design:

- `woff/config.py:62-109`: `WatchdogConfig.validate()` canonicalizes and rejects
  duplicate/overlapping entries within `watch_paths`, but checks `export_path`
  and `discovery_log_path` only for type and nonblank content. It performs no
  output-to-watch-root comparison.
- `woff/woff_watchdog.py:113-130`: `WoFFWatchdog.__init__()` calls validation,
  immediately constructs `DatabaseManager`, optionally creates an export
  backup, and then constructs `DiscoveryLogger` in discovery mode.
- `woff/database.py:197-245` and `851+`: `DatabaseManager` creates the output
  parent and opens/migrates the configured SQLite path during construction.
- `woff/discovery.py:49-63`: `DiscoveryLogger.__init__()` opens its configured
  path in `a` mode and appends a session header during construction. Its
  `log_file()` method also opens the same path in append mode for event output.
- `woff/campaign_namespace.py:25-38`: `canonical_windows_path()` performs lexical
  Windows normalization by removing supported extended prefixes, making a path
  absolute when needed, normalizing separators/dot segments, and applying
  `ntpath.normcase()`. That helper is currently used for watched-root identity,
  not output-path isolation.

Applicable tests inspected:

- `woff/tests/test_config.py`
- `woff/tests/test_campaign_namespace.py`
- `woff/tests/test_handler_integration.py`
- `woff/tests/test_privacy_contracts.py`
- `woff/tests/test_command_contracts.py`
- `woff/tests/test_version_consistency.py`

The current tests verify general pre-start validation, watched-root overlap,
Windows spelling normalization, configuration preservation, and discovery
privacy. They do not assert that persistent outputs are outside watched roots.
Several watchdog/handler tests currently place a synthetic database inside the
single watched temporary root, which current validation accepts.

## Definitive synthetic reproduction procedure

Environment reported by the executed interpreter:

```text
Python 3.10.11
Windows-10-10.0.19045-SP0
os.name = nt
```

The command transported an in-memory UTF-8 Python payload as Base64 so no
reproduction script was written to the repository:

```powershell
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
.\.venv\Scripts\python.exe -c 'import sys,base64;exec(base64.b64decode(sys.argv[1]))' $encoded
```

The payload performed this exact deterministic procedure:

1. Enter `tempfile.TemporaryDirectory(prefix="woff-mate-151-q0-")`.
2. Create only the synthetic layout shown below.
3. Write the exact 30 bytes
   `SYNTHETIC-WOFF-MISSION-INPUT\r\n` to `Mission.log`.
4. Configure its case-only filesystem alias `MISSION.LOG` as
   `discovery_log_path`, with the containing synthetic directory as the sole
   watched root and an external temporary SQLite output. Set
   `backup_export=False`.
5. Construct `WatchdogConfig`, explicitly call `validate()` again, record
   `Path.samefile()` and `canonical_windows_path()` comparisons, and snapshot
   the source bytes.
6. Construct `WoFFWatchdog(..., discovery=True)`, snapshot the source again
   immediately after output construction, invoke
   `watchdog.discovery.log_file(original_mission_path, "modified")` to simulate
   one accepted discovery event, close the temporary database, and take the
   final byte snapshot.
7. Create an empty synthetic `Pilot1Dossier.txt` in a second sole watched root.
8. Configure its case-only filesystem alias `PILOT1DOSSIER.TXT` as
   `export_path`, with an external temporary unused discovery-log path and
   `backup_export=False`.
9. Construct `WatchdogConfig`, explicitly call `validate()` again, record
   `Path.samefile()` and canonical comparisons, and snapshot the source bytes.
10. Construct `WoFFWatchdog(..., discovery=False)`, close its database manager,
    and record the resulting bytes, SHA-256, prefix, and size.
11. Exit `TemporaryDirectory` and verify that its path no longer exists.

Synthetic fixture layout (personal/system temporary prefix intentionally
redacted from repository evidence):

```text
<SYSTEM_TEMP>\woff-mate-151-q0-bxwe9656\
├── external-outputs\
│   ├── discovery-case.sqlite
│   └── unused-discovery.log        # configured but not created
├── synthetic-woff-discovery\       # sole watched root for case 1
│   └── Mission.log                 # output alias configured as MISSION.LOG
└── synthetic-woff-export\          # sole watched root for case 2
    └── Pilot1Dossier.txt           # output alias configured as PILOT1DOSSIER.TXT
```

No call to `WoFFWatchdog.start()` was necessary: both mutations occur in
`WoFFWatchdog.__init__()` before observers, workers, or startup reconciliation
are started. The explicit discovery event demonstrates the additional mutation
available after the already-mutating discovery output construction.

## Observed current behavior

### Case 1 — supported `Mission.log` used as `discovery_log_path`

The configured output used different case from the existing source filename.
On the tested Windows filesystem, `Path.samefile(Mission.log, MISSION.LOG)` was
`True`. Both spellings canonicalized to the same lowercase Windows identity,
and that identity was beneath the canonical watched root.

| Check | Observed result |
|---|---|
| Configuration rejected before output creation | **No** — `WatchdogConfig` construction and explicit `validate()` both accepted it without error |
| Existing source before construction | 30 bytes; SHA-256 `31e64979506c71614389b36a4312a3bd96c2dda185f69142b97ca1af4e11c44e`; hex `53594e5448455449432d574f46462d4d495353494f4e2d494e5055540d0a` |
| Immediately after `WoFFWatchdog`/`DiscoveryLogger` construction | 450 bytes; SHA-256 `523f1a2610410a39e43062cb916220c59c7b0a5ef9b594ec6bf05b5d8f31b53f`; **420 bytes appended during output creation** |
| After one synthetic `modified` discovery event | 1,453 bytes; SHA-256 `3bfd9adce52901273f98155a40206b9f513291dc990da7023e70216a02a7ae6f`; another 1,003 bytes appended; total append 1,423 bytes |
| Original prefix retained | Yes |
| Source mutated | **Yes** |
| Defect reproduction | **PASS — reproduced** |
| Desired #151 isolation behavior | **FAIL — not present on current `main`** |

The discovery log contains timestamps and the synthetic absolute path, so its
post-mutation SHA-256 is an observation bound to this run rather than an
expected constant for future runs. The invariant reproduction is acceptance
before open followed by append mutation of the same case-aliased file.

### Case 2 — supported `Pilot1Dossier.txt` used as `export_path`

The configured output again used different case from the existing source
filename. `Path.samefile(Pilot1Dossier.txt, PILOT1DOSSIER.TXT)` was `True`.
Both spellings canonicalized to the same Windows identity beneath the watched
root.

| Check | Observed result |
|---|---|
| Configuration rejected before output creation | **No** — `WatchdogConfig` construction and explicit `validate()` both accepted it without error |
| Existing source before construction | 0 bytes; SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; empty hex payload |
| After `WoFFWatchdog`/`DatabaseManager` construction and close | 159,744 bytes; SHA-256 `b91a36fc185eeddbb851108e913e73028649ab946584bef621dd7fe6e4e4bb96`; first 16 bytes hex `53514c69746520666f726d6174203300` (`SQLite format 3\0`) |
| Source mutated | **Yes; the empty supported input path became a SQLite database** |
| Defect reproduction | **PASS — reproduced** |
| Desired #151 isolation behavior | **FAIL — not present on current `main`** |

### Windows path/case evidence

- The native Windows filesystem resolved both case-only aliases to their
  existing synthetic source (`Path.samefile() == True`).
- Current `canonical_windows_path()` produced identical keys for each original
  spelling and its case-only output spelling.
- Existing `test_equivalent_windows_root_spellings_share_one_namespace`
  additionally covers drive-letter/name case, forward vs backslashes, a dot
  segment, and the `\\?\C:\...` prefix at the lexical identity layer.
- Current validation applies this canonical logic among watched roots only; it
  never compares either output path with a watched root. The successful native
  case-alias mutations establish that this is a current behavior defect, not
  only a theoretical string-comparison gap.

## Desired Issue #151 behavior (not current behavior)

Issue #151 and `EVAL-OUTPUT-PATH-ISOLATION-001` require persistent output paths
at or beneath watched roots, including Windows path/case aliases, to be rejected
before database/log opening, creation, or mutation, while valid external output
locations continue to work. They also require an explicit symlink/reparse-point
policy. None of those statements is claimed as implemented by this artifact.

This is evidence only. It does not select an implementation mechanism, define
diagnostic wording, or broaden #151 into #48 retention work, generic path
refactoring, installer layout, or release provenance.

## Q0 classification

**Reproduced.** Both minimum overlap scenarios are accepted on exact current
`main`, and both mutate a synthetic supported monitored input through a native
Windows case-only alias. Issue #151 is therefore still current and distinct;
it is not already fixed, obsolete, or duplicated. Prior Issue #45 supplies
early validation infrastructure but only partially overlaps the code path, not
the missing behavior.

## Evidence gaps

- No symlink, directory junction, mount point, or other reparse point was
  created or traversed. Physical alias behavior is therefore **not established**
  by this Q0 run. Current `canonical_windows_path()` is visibly lexical and does
  not itself resolve reparse targets; the specification must preserve this as
  an explicit evidence/policy question rather than infer support.
- No live UNC share was available or used. The code path for stripping a
  `\\?\UNC\` prefix was inspected, but native UNC alias behavior was not executed.
- No 8.3 short-name alias was used; its availability is volume/system dependent.
- The reproduction proves existing-file case aliasing and containment beneath a
  watched root. It does not attempt every possible Windows filesystem alias.

These gaps do not weaken the reproduced direct/case-overlap defect. They limit
what this evidence can claim about additional physical alias classes.

## Validation evidence

Commands run after inspection/reproduction used only repository tests and
external temporary directories:

```powershell
.\.venv\Scripts\python.exe -m pytest woff/tests/test_config.py woff/tests/test_campaign_namespace.py woff/tests/test_privacy_contracts.py -q --basetemp <SYSTEM_TEMP>\woff-mate-151-focused -p no:cacheprovider
# 34 passed in 0.98s

.\.venv\Scripts\python.exe scripts\validate_project_graph.py
# project graph is valid: docs\architecture\project-graph.yaml

.\.venv\Scripts\python.exe -m pytest -q --basetemp <UNIQUE_SYSTEM_TEMP> -p no:cacheprovider
# 1263 passed, 1 skipped, 145 subtests passed in 152.04s (0:02:32)

.\.venv\Scripts\pyright.exe
# 0 errors, 0 warnings, 0 informations

git diff --check
# no output

git status --short --untracked-files=all
# ?? specs/151-output-path-isolation/q0-evidence.md

git status --short
# ?? specs/151-output-path-isolation/
```

Final artifact audit requirements:

- baseline is bound to exact GitHub/current local `main`
  `9601ec29dc6640e1c932d156c9860406a0775205`;
- no production file was changed;
- no test was changed;
- no governance, dependency, configuration, schema, or GitHub state was changed;
- no `spec.md`, `plan.md`, or `tasks.md` was created;
- temporary reproduction directory removal was verified
  (`exists_after_temporary_directory_exit == False`);
- only this Q0 evidence artifact is intended to appear in repository status.

## Data-safety statement

**No real WoFF installation, campaign directory, campaign file, database,
configuration, log, registry value, or personal WoFF data was accessed,
enumerated, modified, or depended upon.** All filesystem mutation used only the
two explicitly created synthetic filenames and companion outputs inside a
self-cleaning system temporary directory. Repository tests used their existing
synthetic/sanitized fixtures and external temporary bases.

---

## Reparse-point follow-up — Draft Q-01 approval evidence

| Field | Value |
|---|---|
| Producer | Codex evidence-only Windows execution session |
| Date | 2026-09-12 (America/Sao_Paulo) |
| Repository | `Malboro66/woff-mate` |
| Exact authoritative `main` baseline | `9601ec29dc6640e1c932d156c9860406a0775205` |
| Tested checkout | `spec/issue-151-output-path-isolation` at `9601ec29dc6640e1c932d156c9860406a0775205` |
| Runtime | CPython 3.10.11, Windows 10.0.19045, `os.name == "nt"` |
| Scope | Temporary synthetic directory junction, attempted directory symbolic link, and broken junction; no real WoFF data |

This is a bounded follow-up to the preserved Q0 evidence above. It supplies
native Windows evidence for the Draft specification's blocking Q-01; it does
not implement Issue #151 or change the specification.

### Baseline and read-only context verification

Immediately before the investigation, the following commands were run:

```powershell
git status --short --branch
# ## spec/issue-151-output-path-isolation
# ?? specs/151-output-path-isolation/

git rev-parse HEAD
# 9601ec29dc6640e1c932d156c9860406a0775205

git rev-parse main
# 9601ec29dc6640e1c932d156c9860406a0775205

git rev-parse origin/main
# 9601ec29dc6640e1c932d156c9860406a0775205

git merge-base HEAD main
# 9601ec29dc6640e1c932d156c9860406a0775205

git branch --show-current
# spec/issue-151-output-path-isolation
```

Thus the topic branch still had no commit beyond the exact authoritative
baseline. The two existing specification artifacts were already untracked;
their presence does not represent a branch commit beyond `main`.

Issue #151 was read through the read-only GitHub REST endpoint
`GET /repos/Malboro66/woff-mate/issues/151`. It remained open with no comments,
and its acceptance criteria still expressly required a defined and practically
tested symlink/reparse-point policy. `AGENTS.md`,
`docs/engineering/spec-driven-development.md`, the complete original
`q0-evidence.md`, and the complete current Draft `spec.md` were read before the
native experiment. The specification was read-only; its pre-investigation
SHA-256 was
`70e20b12ce86f044bd9ce20534099a4197d912ae64a3ac3dd03d92fc9ff466c4`.

The current affected code was also inspected:

- `woff/config.py`: `WatchdogConfig.validate()` compares canonicalized watched
  roots only with one another. It checks `export_path` and
  `discovery_log_path` only for string type and nonblank content.
- `woff/campaign_namespace.py`: `canonical_windows_path()` removes supported
  extended prefixes, makes relative paths absolute, applies `ntpath.normpath`,
  and applies Windows `normcase`. It performs no filesystem target resolution.
- `woff/woff_watchdog.py`, `woff/database.py`, and `woff/discovery.py`: after
  validation, watchdog construction creates/opens SQLite and, in discovery
  mode, opens the discovery log in append mode and writes a session header.

### Commands and deterministic procedure

The experiment used the repository's Python 3.10 virtual environment. An
in-memory UTF-8 Python payload was Base64-transported to `python -c`; no script,
configuration, database, or log was written to the repository:

```powershell
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
.\.venv\Scripts\python.exe -c `
  'import sys,base64;exec(base64.b64decode(sys.argv[1]))' $encoded
```

The payload performed this bounded procedure:

1. Enter `TemporaryDirectory(prefix="woff-mate-151-reparse-")` in the system
   temporary directory.
2. Create a synthetic monitored root, an alias directory outside that root,
   and a separate external-output directory.
3. Run the built-in Windows command
   `cmd.exe /d /c mklink /J <junction-alias> <monitored-root>` without
   elevation.
4. Inspect the junction with `os.path.lexists`, `Path.exists`,
   `os.path.islink`, `Path.is_symlink`, `Path.lstat`, `os.path.realpath`,
   `Path.resolve`, and `Path.samefile`.
5. Resolve both existing targets and a not-yet-created child through the
   junction. Compare the repository's lexical `canonical_windows_path()`
   result before and after native filesystem resolution.
6. Create an empty synthetic dossier and a 28-byte synthetic mission file in
   the monitored target. Use paths through the outside junction as,
   respectively, `export_path` and `discovery_log_path` in separate
   `WatchdogConfig`/`WoFFWatchdog` constructions. Keep the other output external
   and set `backup_export=False`.
7. Record validation results and exact target bytes before and after output
   construction. No observer or watchdog worker was started.
8. Attempt `os.symlink(..., target_is_directory=True)` once. On failure, record
   only the exception type/error codes; do not elevate or change Developer
   Mode, registry, privilege, or policy.
9. Create a second junction whose target deliberately does not exist. Inspect
   default and strict resolution, `samefile`, validation, and one bounded
   watchdog-construction attempt. Verify that the absent target was not
   created.
10. Explicitly remove each alias entry, exit `TemporaryDirectory`, and verify
    that the temporary root no longer exists.

### Synthetic layout

The random and personal system-temporary prefix is intentionally redacted:

```text
<SYSTEM_TEMP>\woff-mate-151-reparse-<random>\
├── aliases\
│   ├── junction-alias\             # junction -> monitored-junction-target
│   ├── symlink-alias\              # attempted; not created on this host
│   └── broken-junction\            # junction -> absent missing-junction-target
├── monitored-junction-target\
│   ├── junction-Mission.log        # 28-byte synthetic input
│   └── junction-Pilot2Dossier.txt  # empty synthetic input
├── monitored-symlink-target\       # empty; no symlink scenario ran
├── external-outputs\
│   ├── junction-discovery.sqlite
│   └── junction-unused-discovery.log  # configured but not created
└── missing-junction-target\        # deliberately absent throughout
```

All names and bytes were synthetic. No WoFF path was discovered, enumerated,
or used.

### Junction creation and classification result

`mklink /J` returned exit code `0`, and `os.path.lexists(junction_alias)` was
`True`. Creation required neither elevation nor a host-policy change.

The created alias was specifically an ordinary directory junction:

| Observation | Result |
|---|---|
| `Path.lstat().st_file_attributes` | `0x410` (`DIRECTORY` plus `REPARSE_POINT`) |
| `Path.lstat().st_reparse_tag` | `0xA0000003` |
| `stat.IO_REPARSE_TAG_MOUNT_POINT` | `0xA0000003` — exact match |
| `os.path.islink(junction_alias)` | `False` |
| `Path.is_symlink()` | `False` |
| `Path.is_junction` availability | Not present in Python 3.10.11 |

This distinguishes the exercised junction from an ordinary symbolic link.
The runtime's `stat.IO_REPARSE_TAG_SYMLINK` constant is `0xA000000C`, but no
object with that tag could be created in this environment.

The Python 3.10 standard-library documentation states that Windows
`os.path.realpath()` resolves symbolic links and junctions (since Python 3.8),
that `Path.resolve()` resolves links as far as possible unless strict behavior
raises, and that `samefile()` requires both paths to be stat-able. Microsoft
documents a reparse tag as the discriminator for reparse-point type and the
name-surrogate bit as identifying an entry representing another named entity.
These references were used only to interpret the native observations:

- <https://docs.python.org/3.10/library/os.path.html#os.path.realpath>
- <https://docs.python.org/3.10/library/os.path.html#os.path.samefile>
- <https://docs.python.org/3.10/library/pathlib.html#pathlib.Path.resolve>
- <https://docs.python.org/3.10/library/pathlib.html#pathlib.Path.samefile>
- <https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-point-tags>

### Path-resolution observations

| Primitive/check | Existing junction alias | Not-yet-created child through existing junction |
|---|---|---|
| `os.path.realpath()` | Resolved to the physical monitored target | Resolved the junction prefix and produced the physical target spelling plus the missing leaf |
| `Path.resolve(strict=False)` | Resolved to the physical monitored target | Resolved the junction prefix and appended the missing leaf |
| `Path.resolve(strict=True)` | Resolved existing alias/targets | Raised `FileNotFoundError`, `errno=2`, `winerror=2` for the missing leaf |
| `Path.samefile(alias, target)` | `True` for the directory and existing mission file | Raised `FileNotFoundError`, as one or both final paths did not exist |
| `canonical_windows_path(alias)` | Retained the lexical `aliases\junction-alias\...` identity | Same lexical behavior |
| Lexical repository identity beneath physical monitored root | `False` | `False` |
| `canonical_windows_path(os.path.realpath(alias))` beneath physical root | `True` | `True` for the resolved target spelling |

`os.path.realpath`, `Path.resolve`, and `Path.samefile` therefore expose
physical identity that `canonical_windows_path()` does not. `samefile()` is a
strong existing-object identity check but cannot cover a persistent output
that has not yet been created. On this host, non-strict resolution did cover an
existing junction ancestor while retaining the absent final component. The
`strict` argument was available, but `os.path.ALLOW_MISSING` was not present in
the executed Python 3.10.11 runtime (that sentinel was added only in later
Python 3.10 maintenance releases), so it is not an available project-wide
Python 3.10 primitive for this baseline.

### Current validation and mutation through the junction

Both aliased output configurations were accepted by `WatchdogConfig`
construction and by an additional explicit `validate()` call.

#### `export_path`

The configured output was
`junction-alias\junction-Pilot2Dossier.txt`, whose physical target was the
empty synthetic dossier inside the monitored root.

| Check | Result |
|---|---|
| Current validation | **Accepted** |
| `Path.samefile(alias, target)` after construction | `True` |
| Before construction | 0 bytes; SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `WoFFWatchdog(..., discovery=False)` | Constructed successfully |
| After construction and database close | 159,744 bytes; SHA-256 `b91a36fc185eeddbb851108e913e73028649ab946584bef621dd7fe6e4e4bb96` |
| First 16 bytes after | `53514c69746520666f726d6174203300` (`SQLite format 3\0`) |
| Physical monitored target mutated | **Yes** |

#### `discovery_log_path`

The configured output was `junction-alias\junction-Mission.log`, whose physical
target initially contained exactly the ASCII bytes
`SYNTHETIC-JUNCTION-MISSION\r\n`.

| Check | Result |
|---|---|
| Current validation | **Accepted** |
| `Path.samefile(alias, target)` before/after | `True` |
| Before construction | 28 bytes; SHA-256 `b75f295995cfffc272c4ebaba0c25b768f61eebefc49360c073295a2b3a26825` |
| `WoFFWatchdog(..., discovery=True)` | Constructed successfully |
| Immediately after construction | 448 bytes; SHA-256 `8c8591ac37f0bbe2efe03d5ea2a251e60520b86db089f51bd96a4ae69a6a5c01` |
| Bytes appended by `DiscoveryLogger` construction | 420 |
| Original 28-byte prefix retained | `True` |
| Physical monitored target mutated | **Yes** |

The discovery post-write hash is specific to this run because the appended
header contains a timestamp. The stable evidence is validation acceptance,
same-file identity, retained original prefix, and a 420-byte append during
construction. In both cases mutation occurred before any observer or worker
was started.

### Ordinary directory-symbolic-link result

The single bounded call
`os.symlink(synthetic_target, symlink_alias, target_is_directory=True)` failed
with `OSError`, `errno=22`, `winerror=1314` (`ERROR_PRIVILEGE_NOT_HELD`). No
symbolic link was created, and no symbolic-link output scenario was run. The
session did not request elevation, enable Developer Mode, change registry or
policy, or retry through a privileged mechanism.

Consequently, native mutation evidence is established for an ordinary
directory junction but remains unavailable for an ordinary directory symbolic
link on this host. The documented Python primitive covers symbolic links in
principle, but documentation is not substituted for the missing native Q4
execution result.

### Broken/non-resolvable alias behavior

`mklink /J` also successfully created `broken-junction` pointing to a target
directory that never existed. This was an ordinary mount-point-tag junction,
not a fabricated generic reparse point.

| Check | Result |
|---|---|
| `os.path.lexists(broken_junction)` | `True` |
| `Path.exists()` | `False` |
| Reparse tag | `0xA0000003` (`IO_REPARSE_TAG_MOUNT_POINT`) |
| `os.path.realpath(candidate)` default | Returned the absent target spelling plus `unreachable.db` |
| `Path.resolve(strict=False)` | Returned the same absent target spelling |
| `os.path.realpath(..., strict=True)` | Raised `FileNotFoundError`, `errno=2`, `winerror=3` |
| `Path.resolve(strict=True)` | Raised `FileNotFoundError`, `errno=2`, `winerror=3` |
| `Path.samefile()` | Raised `FileNotFoundError`, `errno=2`, `winerror=3` |
| Current `WatchdogConfig.validate()` | **Accepted** the broken-junction `export_path` |
| Watchdog construction | Later raised `FileExistsError`, `errno=17`, `winerror=183` while preparing the output parent |
| Missing junction target created | `False` |

This is important fail-closed evidence: non-strict resolution can return a
plausible physical spelling after suppressing a failure, while strict
resolution and `samefile()` cannot validate an absent final target. Current
configuration validation does not classify the ambiguity; it accepts the
configuration and permits the failure to escape later from output
construction. No SQLite or log bytes were created in the broken target case.

No inaccessible-ACL or explicit looping alias was created. Creating a denial
ACL would add an unnecessary temporary-permission recovery risk, and the broken
junction already safely exercised the required unresolved/error distinction.

### Junction, symbolic-link, and generic-reparse distinction

The evidence supports these bounded classifications:

1. **Ordinary directory junction (`IO_REPARSE_TAG_MOUNT_POINT`)** — natively
   created and traversed without elevation. `realpath` and `resolve` reached the
   target; existing-object `samefile` confirmed identity; current validation
   missed the alias; both output constructors mutated the monitored target.
2. **Ordinary symbolic link (`IO_REPARSE_TAG_SYMLINK`)** — Python exposes the
   creation/resolution API and documents Windows resolution, but native creation
   was unavailable here with error 1314. No local behavior beyond the failed
   creation attempt is claimed.
3. **Other/generic reparse tags** — not created or traversed. A generic
   `FILE_ATTRIBUTE_REPARSE_POINT` flag alone does not establish target or
   name-surrogate semantics; the tag and successful, unambiguous OS resolution
   matter. This follow-up does not infer that junction results apply to every
   Windows reparse tag and does not attempt exhaustive tag testing.

### Policy evidence conclusion

The proposed policy is **supported, with explicit qualification**:

> A persistent output whose filesystem-resolved path is equal to or contained
> by a monitored WoFF root must be rejected even when the overlap is introduced
> through a supported symbolic-link or junction alias. If filesystem alias
> resolution required to establish safety fails or remains ambiguous,
> validation fails closed before SQLite/log creation or mutation.

Direct native evidence strongly supports rejection through ordinary directory
junctions: current validation accepted both aliases, the standard-library
resolvers identified the physical monitored target, and both persistent-output
constructors mutated it. The broken-junction result also supports failing
closed during validation rather than accepting an unresolved alias and failing
later in output construction.

The qualification is that this host did not permit ordinary symbolic-link
creation, so equivalent native symlink mutation evidence remains unexecuted.
Python's documented Windows behavior supports treating ordinary symbolic links
as resolvable aliases, but a later implementation claim should retain a native
symlink test that skips with the recorded environment limitation when creation
is unavailable. The policy must also define “supported” by bounded alias
classes; it must not claim every reparse tag.

The evidence additionally shows that `realpath(..., strict=False)` or
`Path.resolve(strict=False)` returning a string is not, by itself, proof that
resolution established safety: default behavior may preserve or synthesize an
unverified remainder after an error. Conversely, requiring the final output to
exist under strict resolution would conflict with the Draft's valid
not-yet-created-output scenario. The future validation design therefore needs
to resolve the filesystem-dependent existing portion, account for the missing
output suffix, and fail closed when alias resolution needed for the safety
decision errors or remains ambiguous. This is evidence about the policy
boundary, not an implementation change.

### Remaining evidence gaps

- Native ordinary-directory-symlink creation and traversal could not be tested
  on this host without a privilege or policy change, which was prohibited.
- No other name-surrogate or generic reparse tag, volume mount point, cloud
  placeholder, application execution link, live UNC path, or 8.3 alias was
  exercised. Their semantics are not inferred from the junction result.
- No inaccessible-ACL or explicit link-loop fixture was created. The broken
  junction covered default-versus-strict error handling without host ACL
  changes; additional hostile filesystem races and time-of-check/time-of-use
  behavior remain implementation/review concerns.
- The experiment establishes available primitives and the current defect. It
  does not select diagnostic wording, an implementation algorithm, or the
  definitive supported-tag allowlist; those remain specification/maintainer
  decisions.

### Follow-up cleanup and safety result

All three attempted alias paths reported `lexists == False` after explicit
cleanup, and the `TemporaryDirectory` root reported `exists == False` after
context exit. No elevation, Developer Mode, registry, policy, dependency,
configuration, GitHub mutation, or tool installation occurred. No real WoFF
installation, campaign root, campaign file, database, log, or personal WoFF
data was accessed or modified.
