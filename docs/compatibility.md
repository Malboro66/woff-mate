# Compatibility

This guide distinguishes what WoFF Mate supports from what the project actually validates. A supported combination is expected to work; automatic validation or sample verification provides the stronger evidence described below.

## Compatibility status

| Area | Status | Scope |
| --- | --- | --- |
| Operating system | **Supported** | Windows 10 64-bit and Windows 11 64-bit |
| Python runtime | **Supported** | Python 3.10 through 3.14 |
| Linux CI | **Automatically validated** | Python 3.10 and 3.14 on Linux |
| Windows smoke test | **Automatically validated** | Python 3.10 on `windows-latest` |
| Game data | **Verified by sanitized samples** | WOFF BH&H II formats confirmed by sanitized samples and regression fixtures |
| Game build | **Unconfirmed** | The exact WoFF build is unconfirmed |

Automatic CI coverage is not a statement that Linux is a supported end-user platform. It checks portability and the endpoints of the supported Python range. Versions between those endpoints remain supported even when they do not have a dedicated CI job.

WOFF BH&H II support is limited to formats confirmed by sanitized samples and regression fixtures. Do not infer compatibility with a new or altered format solely from the game name. Because the exact WoFF build is unconfirmed, reports about an unknown format help establish compatibility without making an unsupported build claim.

## Reporting a compatibility problem safely

Include only the minimum technical context needed to reproduce the problem:

- Windows version and architecture, for example `Windows 11 64-bit`;
- Python version, if running from source;
- WoFF Mate version, obtained with `woff-watchdog --version`;
- the exact command, with user names and local paths replaced by neutral labels;
- a sanitized error message or traceback; and
- a sanitized input structure: field names, ordering, delimiters, and the smallest synthetic values needed to demonstrate an unknown format.

State whether the problem is repeatable and what result was expected. If a WoFF build identifier is available without exposing private data, report it as unconfirmed context rather than as a compatibility guarantee.

Never attach or paste:

- `config.json` or configuration values;
- SQLite databases, migration backups, or database contents;
- complete PilotLog records;
- mission notes or narratives; or
- personal paths, user names, pilot identities, or other personal data.

Replace sensitive values with clearly synthetic placeholders. Preserve only the structural details required to diagnose the format; a compatibility report does not require campaign data.
