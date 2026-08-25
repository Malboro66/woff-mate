# PilotLog record format

This document describes only the layouts established by sanitized samples derived
from three PilotLog files. The original files are not fixtures and were not
inspected as part of this work.

## Record classification and normalization

PilotLog is semicolon-delimited and begins with a numeric record counter. A
counter is metadata, not a mission, and is ignored wherever it appears. A pilot
with no missions can contain the counter `0` followed by this ten-field header:

`Day;Month;Year;Hour;Minute;MissionRegion;MissionBase;Missiontype;AircraftName;Claims`

The header is also metadata and is ignored. Internal empty fields are
significant and are preserved. The fixed mission prefix is classified separately
from the free-form notes tail, so semicolons in notes are reconstructed rather
than mistaken for additional layout fields. If a physical line ends in a
semicolon, splitting it creates one final empty field; only that one field is
removed. Consequently, a verified mission has 21 raw fields when it has a
terminal semicolon and 20 logical fields after normalization. It also has 20
logical fields when no terminal semicolon is present.

Before a mission object is created, claim confirmations and metadata are
identified, and the fixed mission prefix and date/time are validated. A record
is then classified as a verified mission, incomplete, or malformed. One
rejected line does not prevent later lines from being processed.

## Verified 20-field mission layout

“High” confidence below means the position and use are demonstrated by every
sanitized mission sample. “Observed” means the position and value category are
preserved, but a more specific semantic interpretation has not been verified.
Names intentionally remain generic where the evidence is incomplete.

| Index | Field type | Sanitized example category | Confidence |
| ---: | --- | --- | --- |
| 0 | date component | day with optional `/` | High |
| 1 | date component | month with optional `/` | High |
| 2 | date component | four-digit year | High |
| 3 | time component | hour with optional `h` | High |
| 4 | time component | minute | High |
| 5 | text | region | High |
| 6 | text | base | High |
| 7 | text | mission type | High |
| 8 | text | aircraft display name | High |
| 9 | text, possibly empty | claim-related text | Observed |
| 10 | text/numeric | duration-like value | Observed |
| 11 | text/numeric | unverified numeric value | Observed |
| 12 | text | aircraft identifier | Observed |
| 13 | text | squadron | High |
| 14 | text | target category | Observed |
| 15 | text | target name/category instance | Observed |
| 16 | coordinate-like text | north/south coordinate | Observed |
| 17 | coordinate-like text | east/west coordinate | Observed |
| 18 | empty or reserved text | empty in real mission samples | High for position; semantics unknown |
| 19 | free-form text | complete mission report and notes | High |

Index 19 is exclusively `notes`, truncated to the application's existing
500-character maximum after all of its semicolon-delimited fragments have been
reconstructed. Index 18 remains independent and is not interpreted as
damage. The verified samples establish no fixed aircraft-damage or pilot-wound
positions, so both flags are `False`. In particular, phrases such as “Aircraft
Destroyed” in notes do not imply death, crash, damage, or wounds.

## Verified-layout priority

The verified layout has priority for every supported mission. Index 18 remains
reserved and independent, while notes are reconstructed from index 19 through
all remaining semicolon-delimited fragments.

An extended-looking record cannot be distinguished safely from a verified
record whose reserved field is non-empty and whose notes contain semicolons.
Field count and flag-like values such as `Damaged`, `Yes`, `No`, or `Wounded`
are not reliable layout markers. Consequently, PilotLog damage and wound flags
are not inferred: both values remain `False`.

Future support for an extended layout requires sanitized evidence establishing
its positions or a reliable external format marker. Until then, speculative
automatic extended-layout detection is intentionally disabled.

## Mission results

Result classification examines notes case-insensitively. `killed` produces the
existing `Shot Down — KIA` label and takes precedence if `crash` is also present.
Otherwise, `crash` produces `Crash Landing — Survived`; all other notes produce
`Completed`.

## Claim confirmations and rejected records

The sanitized evidence includes a claim-confirmation record with a verified
minimum structure of 26 fields whose sixth field (index 5) begins with
`Confirmation Received of Claim submitted on:`. The signature is detected
independently of field count and before mission classification. Signature-bearing
records with at least 26 fields are ignored as valid confirmations; this permits
semicolons in the free-form claim narrative to create additional fragments.
Signature-bearing records with fewer than 26 fields are logged as truncated and
skipped, so they can never fall through to mission parsing. Victory parsing and
the separate claims parser are outside this format change.

## Victory merge identity and claim-count consistency

Each accepted Claims row receives a `source-v1` identity derived from the
sanitized source basename and its physical record position. Only the SHA-256
digest is persisted; no campaign path or claim text is included. XML victory
records use the same contract with their deterministic document order. A new
position in the same source is a distinct occurrence even when date, minute,
and enemy aircraft are identical. Exact replay resolves the existing stable
row, and richer compatible data fills or corrects that row without changing its
ID or an existing mission association. Poorer or blank fields never erase
richer stored values. An ambiguous cross-source match is reported as
`ambiguous-occurrence` and is not guessed.

Mission `claimsCount` remains source evidence; victory ingestion does not
rewrite it. An unlinked victory is associated automatically only when exactly
one mission for the pilot and canonical date has a positive claim count and a
compatible start time. Existing explicit associations are preserved. When the
stored claim count and associated victory-row count differ, WoFF Mate retains
both records and emits the sanitized `count-mismatch` diagnostic. Merge logs
separately report `inserted`, `updated`, `unchanged`, and `unresolved` outcomes.

Records with too few fields are incomplete. A candidate mission with an invalid
fixed prefix or invalid date/time components is malformed. These records are
skipped without interrupting later valid missions.

Rejection logs contain only safe diagnostics: source filename, line number,
category, logical field count, and a rejection reason. They never contain the
complete source record or its free-form notes.

## Fixture and logging privacy

Regression fixtures must be minimal and sanitized. Do not commit original
PilotLog files, personal names, personal paths, installation paths, raw campaign
identifiers, or other campaign data. Logs follow the same minimization rule and
must not reproduce source lines. Future WoFF versions or layouts remain
unsupported until their positions can be verified without inventing semantics.
