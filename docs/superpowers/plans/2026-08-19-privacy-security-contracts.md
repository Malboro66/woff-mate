# Privacy and Activation-Key Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce WoFF Mate's local-only privacy model, forbid activation/license credential handling, preserve offline core operation, and restrict discovery previews to approved WoFF-generated files.

**Architecture:** Keep the security boundary small and explicit. Registry discovery remains in `platform`, discovery preview policy remains in `ingestion`, and governance uses deterministic structural tests plus project-graph invariants. No network runtime feature is added.

**Tech Stack:** Python 3.10-3.14, pytest, PyYAML project graph validation, GitHub Actions CI.

**Spec:** GitHub Issue #65.

## Global Constraints

- WoFF Mate remains read-only with respect to WoFF/CFS3.
- WoFF-derived and user data remains local by default.
- Activation keys, serials, product keys, license credentials, tokens, and equivalent secrets are forbidden data.
- Core runtime remains offline and contains no telemetry, analytics, tracking, or automatic upload.
- Registry discovery remains narrow, read-only, deterministic, and compatible with Issue #49.
- Discovery fixtures and logs use only synthetic or sanitized data.
- No modification of WoFF executables, DLLs, DRM, or activation systems.

---

### Task 1: Add executable privacy and registry contracts

**Files:**
- Create: `woff/tests/test_privacy_contracts.py`
- Modify: `woff/win_registry.py`

**Interfaces:**
- Consumes: current `get_woff_install_path() -> Optional[str]`.
- Produces: `ALLOWED_WOFF_REGISTRY_VALUES: frozenset[str]` containing only `CFS3Path`; structural tests for forbidden network imports and forbidden persisted credential names.

- [ ] **Step 1: Write failing tests**

```python
def test_registry_value_allowlist_is_explicit():
    from woff import win_registry
    assert win_registry.ALLOWED_WOFF_REGISTRY_VALUES == frozenset({"CFS3Path"})


def test_core_runtime_has_no_network_client_imports():
    # Parse production Python AST and reject imports rooted at socket, urllib,
    # http, requests, httpx, aiohttp, websockets, telemetry, or analytics SDKs.
    ...
```

- [ ] **Step 2: Run focused CI and confirm RED**

Open a draft PR containing tests only. Confirm the privacy test fails because the explicit allowlist/security contract is absent.

- [ ] **Step 3: Add minimal implementation**

```python
ALLOWED_WOFF_REGISTRY_VALUES = frozenset({"CFS3Path"})
WOFF_REG_VALUE = "CFS3Path"
```

Keep `get_woff_install_path()` querying only `WOFF_REG_VALUE` and never enumerate registry values.

- [ ] **Step 4: Run focused CI and confirm GREEN**

Expected: privacy structural tests pass on Python 3.10 and 3.14 and Windows smoke remains unchanged.

- [ ] **Step 5: Commit**

Commit only the focused contract and test changes.

### Task 2: Restrict discovery previews to approved WoFF files

**Files:**
- Modify: `woff/discovery.py`
- Modify: `woff/tests/test_privacy_contracts.py`

**Interfaces:**
- Produces: `is_preview_allowed(path: str | Path) -> bool` used before reading raw file content.

- [ ] **Step 1: Write failing tests**

```python
def test_discovery_never_previews_activation_like_file(tmp_path):
    sensitive = tmp_path / "activation_key.txt"
    sensitive.write_text("SECRET", encoding="utf-8")
    # log_file must record metadata only and never include SECRET.


def test_discovery_previews_known_pilot_log(tmp_path):
    pilot_log = tmp_path / "Pilot1Log.txt"
    pilot_log.write_text("sanitized campaign data", encoding="utf-8")
    # Known WoFF generated file remains previewable.
```

- [ ] **Step 2: Verify RED through PR CI**

Expected: current extension-only policy exposes the synthetic secret from `activation_key.txt`.

- [ ] **Step 3: Implement minimal allowlist**

Approved preview names/patterns are restricted to files already consumed by WoFF Mate:

```text
mission.log
Pilot{N}Log.txt
Pilot{N}Claims.txt
Pilot{N}Squads.txt
Pilot{N}Dossier.txt
Pilot{N}*.xml only when explicitly recognized by the campaign-file policy
```

Unknown `.txt`, `.log`, `.xml`, `.ini`, `.cfg`, and `.csv` files receive metadata-only logging.

- [ ] **Step 4: Verify GREEN**

Run privacy tests, handler integration tests, full suite, and Windows smoke in CI.

- [ ] **Step 5: Commit**

Commit discovery hardening separately from governance documentation where practical.

### Task 3: Register invariants, evals, and release gate

**Files:**
- Modify: `docs/architecture/project-graph.yaml`
- Modify: `docs/engineering/evals.md`
- Modify: `docs/engineering/quality-gates.md`
- Create: `docs/security/privacy-and-local-data.md`
- Modify: `woff/tests/test_architecture_contracts.py` only if required by graph schema validation.

**Interfaces:**
- Produces invariants `PRIV-001`, `LIC-001`, `NET-001`.
- Produces deterministic evals `EVAL-PRIV-001`, `EVAL-LIC-001`, `EVAL-NET-001`, and `EVAL-DISC-PRIV-001` owned by `issue-65`.

- [ ] **Step 1: Add graph entries and documentation**

```yaml
PRIV-001:
  statement: WoFF-derived and user data remains local by default and is not transmitted to third parties.
  enforced_by: [woff/tests/test_privacy_contracts.py]
LIC-001:
  statement: WoFF activation and license credentials are forbidden data and are never intentionally read, stored, logged, exported, or transmitted.
  enforced_by: [woff/tests/test_privacy_contracts.py]
NET-001:
  statement: Core WoFF Mate functionality operates offline without telemetry, analytics, tracking, or automatic upload.
  enforced_by: [woff/tests/test_privacy_contracts.py]
```

- [ ] **Step 2: Add Issue #65 work item**

Register `issue-65` in the owning modules/governance contract with Q0, Q1, Q3, and Q4 evidence. Do not add it to cycle 3.3.0 unless the approved cycle scope changes.

- [ ] **Step 3: Update human-readable contracts**

Document local processing, forbidden credential handling, registry allowlisting, discovery metadata-only fallback, offline operation, and the process required before any future network feature.

- [ ] **Step 4: Validate graph**

Run through CI:

```bash
python scripts/validate_project_graph.py
python -m pytest woff/tests/test_architecture_contracts.py -q
```

Expected: PASS.

### Task 4: Final verification and PR evidence

**Files:**
- No new production files unless validation reveals a scoped defect.

- [ ] **Step 1: Run all required CI evidence**

```bash
python scripts/validate_project_graph.py
python -m pytest woff/tests/test_privacy_contracts.py -q
python -m pytest woff/tests/test_architecture_contracts.py -q
python -m pytest -q
pyright
git diff --check
```

Windows CI must also pass import, entry-point, launcher, PyInstaller build, and packaged executable smoke checks.

- [ ] **Step 2: Review complete diff**

Confirm no personal data, activation material, generated logs, or WoFF assets entered the branch.

- [ ] **Step 3: Update draft PR evidence**

Record Q0 history, RED result, GREEN result, eval IDs, gate results, privacy impact, and compatibility with Issue #49.

- [ ] **Step 4: Do not merge**

Leave the PR ready for independent review and maintainer approval.
