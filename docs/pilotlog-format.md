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

Before a mission object is created, a record is classified as a counter, the
zero-mission header, a verified mission, an extended legacy mission, a claim
confirmation, incomplete, malformed, or unsupported/unknown. One rejected line
does not prevent later lines from being processed.

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

## Extended legacy layout

An explicit 21-logical-field legacy layout remains supported:

- indexes 0–17 retain the common mission prefix;
- index 18 is the independent aircraft-damage flag;
- index 19 is the independent pilot-wound flag; and
- index 20 is notes.

The extended form is explicitly distinguished from a verified record with
semicolon-containing notes by a non-empty, recognized damage flag at index 18
and a recognized wound flag at index 19. Thus a verified report whose notes
begin with `No;`, `Yes;`, or another flag-like token remains a verified report.
As with the verified layout, a terminal semicolon adds one raw trailing empty
field and does not change the logical layout. The extended form is accepted only
when both flag positions use strictly recognized tokens. Matching ignores case
and surrounding whitespace.

| Boolean | Recognized tokens |
| --- | --- |
| False | empty string, `0`, `No`, `False`, `None`, `Undamaged` |
| True | `1`, `Yes`, `True`, `Damage`, `Damaged`, `Wound`, `Wounded`, `Injured` |

Unknown non-empty text has no truth value; it is never converted with Python's
`bool(value)`. An extended record containing such text is ambiguous and is
rejected as unsupported.

## Mission results

Result classification examines notes case-insensitively. `killed` produces the
existing `Shot Down — KIA` label and takes precedence if `crash` is also present.
Otherwise, `crash` produces `Crash Landing — Survived`; all other notes produce
`Completed`.

## Claim confirmations and rejected records

The sanitized evidence includes a 26-field claim-confirmation record whose sixth
field begins with `Confirmation Received of Claim submitted on:`. It is
recognized within PilotLog and ignored; it is not a mission. Victory parsing and
the separate claims parser are outside this format change.

Records with too few fields are incomplete. Unsupported field counts are
unknown, an extended layout with invalid flags is ambiguous, and a candidate
mission with invalid date/time components is malformed. These records are
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
