# Privacy and local-data security contract

## Purpose

WoFF Mate is a local, read-only companion for Wings Over Flanders Fields: Between Heaven & Hell II. Its core function is to read game-generated data from a legitimate local WoFF installation, derive companion information, persist that information locally, and present it locally.

This document defines the security boundary for user data, WoFF data, activation credentials, registry access, discovery logs, and network communication.

## PRIV-001: Local Data Only

WoFF-derived data and user-local data remain on the user's machine by default.

Core WoFF Mate must not transmit any of the following to WoFF Mate infrastructure or third parties:

- pilot or campaign data
- mission, claim, squadron, dossier, diary, RPG, or statistic data
- WoFF-derived identifiers
- local configuration values
- local filesystem paths
- discovery or diagnostic log content
- SQLite data
- installation metadata beyond what is processed locally

WoFF Mate has no telemetry, analytics, tracking, automatic upload, or automatic crash-report transmission in the core runtime.

Local files created by WoFF Mate, including its SQLite database and logs, remain local artifacts. A user explicitly copying or sharing one of those files is outside automatic application behavior.

## LIC-001: Activation Credentials Are Forbidden Data

WoFF Mate does not need the WoFF activation key, serial, product key, license credential, token, or equivalent secret to provide companion functionality.

Those values are forbidden data. WoFF Mate must not intentionally:

- read them
- search for them
- enumerate registry values to locate them
- store them
- copy them
- hash or transform them for identification
- display them
- write them to logs
- include them in diagnostics or backups
- export them
- transmit them

This rule applies even to temporary collection performed only for diagnostics.

### Registry boundary

Current WoFF auto-discovery reads one Windows registry value:

```text
HKCU\Software\VB and VBA Program Settings\OFFManager4\Settings
value: CFS3Path
```

`CFS3Path` is used only to locate the local WoFF installation. Registry access remains read-only.

Future work under Issue #49 may support additional explicitly approved WoFF manager keys. It may still query only the approved installation-path value. Arbitrary registry enumeration is outside the security contract.

## NET-001: Offline Core Operation

Core WoFF Mate functionality must operate without Internet access.

The core runtime must not introduce network-client imports for telemetry, analytics, upload, synchronization, tracking, or remote diagnostics.

A future network feature requires a separate tracked decision that explicitly defines:

1. the user-visible purpose
2. the exact data involved
3. whether any WoFF-derived or user data leaves the machine
4. explicit consent behavior where applicable
5. retention and deletion behavior
6. security controls
7. updated project-graph invariants and evals
8. maintainer approval before release

A future network feature must not silently weaken `LIC-001`.

## Discovery-mode privacy

Discovery mode exists to help maintainers understand supported WoFF-generated file formats. It is not permission to copy arbitrary text-like files into `woff_discovery.log`.

Raw previews use an explicit filename allowlist. Current approved preview patterns are:

```text
mission.log
Pilot{N}Log.txt
Pilot{N}Claims.txt
Pilot{N}Squads.txt
Pilot{N}Dossier.txt
```

Unknown `.txt`, `.log`, `.xml`, `.ini`, `.cfg`, `.csv`, or other files receive metadata-only handling. A supported extension by itself never authorizes raw preview.

Files of 1,000,000 bytes or more remain preview-disabled. Approved previews remain capped at 12,000 bytes.

Discovery fixtures and repository evidence must be synthetic or sanitized.

## Read-only WoFF boundary

WoFF Mate must not modify WoFF or CFS3 executables, DLLs, activation systems, DRM, or license state. The companion reads the game data required for its features and maintains its own local state separately.

## Verification

The executable evidence for this contract lives in:

- `woff/tests/test_privacy_contracts.py`
- `woff/tests/test_architecture_contracts.py`
- `docs/architecture/project-graph.yaml`

The privacy/security tests verify the registry-value allowlist, absence of network-client imports in core source, absence of credential-like persistence fields, and discovery preview restrictions.

Public-release evidence must include these checks. A green build that violates these invariants is not release-ready.
