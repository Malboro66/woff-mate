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
| Primary game reference | **Maintainer-attested** | WOFF BH&H II base v1.38, without additional DLC or expansions; provenance of the supplied Pilot1/Pilot2 captures |

Automatic CI coverage is not a statement that Linux is a supported end-user platform. It checks portability and the endpoints of the supported Python range. Versions between those endpoints remain supported even when they do not have a dedicated CI job.

WOFF BH&H II base v1.38 is the primary reference installation. The maintainer attests that the previously supplied Pilot1/Pilot2 captures came from that installation and were not manually modified. Their physical structure was examined in the earlier source investigations; the installation/build provenance is a separate maintainer attestation. This does not establish that every v1.38 Dossier has one layout. Older, alternate and future formats require separate structural evidence.

## Categorical normalization

Nation aliases match complete, case-insensitive values. Short aliases such as
`us`, `fr`, and `de` never match inside another word. RFC, RNAS, and RAF remain
separate canonical services.

Mission and victory aliases match only explicit tokens or phrases. They never
match arbitrary substrings inside unrelated words. A missing categorical value
remains empty. An unrecognized value from an explicit XML or PilotLog field is
trimmed and preserved verbatim instead of becoming a known category.

The fixture-backed Dossier `fixed-index-v1` reads nation/service evidence at
decoded index 1. XML, Mission.log and Dossier preserve that evidence and use
`NationService` with the exact alias authority in `woff/maps.py`. Supported
codes are exactly GB, FR, DE, US and BE; RFC/RNAS/RAF are distinct British
services. Missing and unsupported values remain distinct and unsupported text
is recoverable in storage. No other Dossier record is scanned for nationality.
New aliases/layouts require representative sanitized evidence. See the
[nation/service contract](architecture/nation-service.md) for independent
presentation labels, deprecated raw `nation`, and schema-3.4 compatibility.

## Claim confirmation and mission duration

Confirmation is a four-state source contract: explicit positive, explicit
negative, missing, or unknown. PilotClaims supports only the verified trailing
`Confirmed` and `Unconfirmed` markers (including their parenthesized forms).
Structured XML confirmation accepts exact `true`, `1`, `yes`, and `confirmed`
positive values and exact `false`, `0`, `no`, and `unconfirmed` negative values.
`none` represents missing evidence. Case and surrounding whitespace do not
matter, but substrings never do. Missing and unknown confirmation persist as
SQL `NULL`; explicit negative persists as `0`. Unknown values produce a bounded
category-only diagnostic without logging claim text.

Mission start time and duration are separate. In XML, a clock-shaped `Time` is
the mission start time. The fixture-backed `Duration` element and the decimal
`Time` form retained by the canonical temporal contract are duration sources;
when an explicit start-time field is present, only a decimal generic `Time` can
act as duration. `FlightTime`, `Hours`, and `Dauer` have no sanitized
representative evidence and are ignored with a bounded diagnostic until such
evidence exists. In the verified PilotLog fixed layout, the date/time components
and the observed duration-like field at index 10 remain independent.

## Dossier runtime admission and diagnostic decoding

Authoritative Dossier ingestion accepts the observed 161-physical-position
family from the maintainer-attested BH&H II base v1.38 captures. Index 0 must
contain `160`; pilot detail slots are 63-78 and observer detail slots 113-128.
Index 112 is contextual, not a roster record. Physical blank positions retain
their indices and advance filename-derived XOR alternation. Pilot-detail
occupancy at index 81 and the established 36/32-field record widths are checked.
Malformed recognized slots, invalid required status and decoding/identity
failures reject the generation; they are never silently omitted.

These detailed records are **partial observations, not a complete active
squadron census**. Omission cannot prove departure, transfer or death. Partial
observations preserve trusted complete historical baselines and existing absence
candidates; they cannot confirm those candidates or produce roster arrival or
absence events. Persistent identities, historical personality/memory and
field-presence semantics remain intact.

`FileProcessor` explicitly requires verified structure through the parser's
shared admission rule. Decodable unverified layouts, including synthetic
50/105-record fixtures, return permanent `unsupported-layout` before persistence
or generation acknowledgment. They cannot alter bindings, digests, provenance,
roster state or diary entries. This is deterministic format rejection, not a
transient snapshot failure. A later supported generation may still be processed.
The restriction may reject legitimate older or alternate inputs until their
formats are separately verified; no exhaustive simulator-version claim is made.

Legacy `fixed-index-v1` decoding remains available through `parse`/`parse_bytes`
for explicitly nonauthoritative diagnostics, including `--parse-file` and
`woff-report`. Those interfaces label Dossier output as diagnostic and distinguish
verified structure from unverified legacy structure. They do not persist it or
assert a complete roster. The legacy variable-tail ambiguity, including six-field
prose recognition, has not been universally solved; runtime ingestion never
enters that fallback for an unverified layout.

Diagnostic `supported-full` means fixed pilot fields through index 100 are
addressable; `supported-partial` means later optional pilot fields are absent.
Neither classification grants runtime admission or complete-roster authority.
Short diagnostic inputs retain the 128-key ambiguity checks, printable-text
validation and required identity at indices 4/5. Invalid markers in 161-position
payloads remain unsupported even in diagnostics. Filename-key collisions remain
indistinguishable without external evidence; this is not authenticated encryption.

The prior automatic admission of short partial Dossiers is withdrawn. The
independent field-presence contract remains: missing optional values do not erase
richer persisted values, missing numeric observations remain SQL `NULL`, and
explicit authoritative zero stays distinct. These guarantees are tested using
admitted runtime structure and independent model/repository/engine contracts.

All source fixtures are synthetic or sanitized structural reconstructions.
Synthetic legacy decoding behavior is not verified simulator output. Complete
roster scenarios in domain tests stipulate completeness explicitly; they do not
attribute it to the simulator's partial Dossier family. No schema change or
historical-data removal is part of this admission policy.

Diagnostics expose only bounded categories, layout information and source
basenames, never raw campaign records. Future runtime format families require
separate documented evidence and regression coverage.

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
