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

## Categorical normalization

Nation aliases match complete, case-insensitive values. Short aliases such as
`us`, `fr`, and `de` never match inside another word. RFC, RNAS, and RAF remain
separate canonical services.

Mission and victory aliases match only explicit tokens or phrases. They never
match arbitrary substrings inside unrelated words. A missing categorical value
remains empty. An unrecognized value from an explicit XML or PilotLog field is
trimmed and preserved verbatim instead of becoming a known category.

The Dossier format has no confirmed field marker for nation values, so its
scanner assigns a nation only when the complete decoded value is a supported
exact alias. Unrecognized decoded values remain available in the parser's raw
strings and are not guessed as a nation. All parser paths use the alias tables
in `woff/maps.py`; new aliases require a sanitized representative sample or an
existing regression fixture that establishes the value.

## Dossier layout validation

WoFF Mate names the existing fixed-index contract `fixed-index-v1`. This name
documents the parser behavior already covered by sanitized regression data. It
does not identify a WoFF build and does not claim compatibility with another
layout.

The supported layout requires a nonempty first name at decoded index 4 and a
nonempty surname at decoded index 5. Both fields must contain alphabetic text
and only name-compatible separators. The parser validates these identity
fields before reading optional statistics or constructing a pilot.

Every decoded record must also contain only printable text. A replacement
character or embedded control character is treated as evidence that the
filename-derived XOR key did not decode the input safely. This is a structural
guard, not a cryptographic integrity check; the confirmed format provides no
authenticated marker or checksum.

Decoded input receives one structural classification:

| Classification | Policy |
| --- | --- |
| `supported-full` | Required identity is valid and every fixed field through index 100 is addressable. |
| `supported-partial` | Required identity is valid, but one or more later fixed fields are unavailable. Present optional fields are parsed independently. |
| `truncated` | Input ends before the required identity positions are complete. It is rejected. |
| `unsupported-layout` | Required positions exist, but identity fields are missing or semantically invalid. It is rejected. |
| `decryption-failed` | No decoded fields are produced, or any decoded record contains evidence of the wrong key or invalid decoded text. It is rejected. |

Missing optional string sentinels are normalized to absent values before a
pilot is constructed. Missing optional numeric values remain unknown. A new
partial Dossier stores missing numeric values as SQL `NULL`, and a later
partial update does not replace an existing authoritative string or numeric
value. Explicit numeric zero remains distinct and writable.

Dossier acceptance and structural-rejection diagnostics contain only the
source basename, classification, layout name, and decoded record count.
Numeric-field diagnostics add the field name and sanitized failure reason.
Neither form logs pilot identity or campaign fields. Future layout variants
require separate identifiers and sanitized representative evidence. Fixed
indexes must not shift silently.

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
