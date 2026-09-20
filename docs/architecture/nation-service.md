# Playable nation and military service (#136)

## Q0 and implementation plan

Remote default branch `main` was verified at
`0c8a3d3c8afd4a9addae1cd5902faa79aa4f7445`. On that revision,
`normalize_nation("Britain")` returned `RFC` and
`hasattr(WoFFPilot(nation="RFC"), "nation_code")` was false. The new
`woff/tests/test_nation_domain.py` failed before implementation: the closed
domain and separate properties did not exist.

Issue #38 / PR #120 (merge `1d6bdd8a757cf362fa8710e306fd77cb0e1e1d34`)
fixed matching/fallbacks. #35 / PR #125 established Dossier validation.
Neither supplied this domain. PR #137 only registered governance; R1's #136
reopening records the missing implementation. This scope does not repeat #38
or implement #81.

Plan: establish failing domain/parser/storage/presentation tests; define one
closed value and alias authority; preserve evidence through ingestion/storage;
update consumers; promote the five evals with executable evidence; run all
local gates and open a draft PR.

## Representation and authority

`NationCode` contains exactly `GB`, `FR`, `DE`, `US`, `BE`. `ServiceCode`
contains only `RFC`, `RNAS`, `RAF`. All #38 aliases remain in immutable
`woff.maps.NATION_MAP`, resolving exact case-insensitive text to
`(nation, service)`. `GB`/`BE` complete the required code domain. No additional
source alias/service was invented. British country-only evidence has no
service; `USAS` establishes `US` without inventing another service code.

`NationService` is frozen, with one input, `nation_raw`, and read-only
`nation_code`, `service_code`, `nation_state` (`known`, `missing`, `unsupported`)
and `service_state` (`known`, `missing_or_unknown`). Raw text is preserved after
trimming surrounding whitespace. Evidence normalization is separate from
recognition/validation; no substring or fallback identity is allowed.

`WoFFPilot.affiliation` returns this value; convenience properties expose the
codes, raw evidence and nation state. **`WoFFPilot.nation` is deprecated as a
semantic API** and retained only as the source-evidence constructor/storage
field. It is not a second canonical authority. Rules, identity and labels must
use the canonical projection. `normalize_nation` remains a compatibility text
normalizer (code or trimmed unknown text), not validation or a storage encoder:
using it for storage would lose service evidence.

## Source boundaries

XML's existing Nation/Country/Side/Service/Pays field and Mission.log's player
formation Country retain source evidence. Dossier `fixed-index-v1` reads index
1, already represented in `current_full_sanitized.txt`,
`short_valid_sanitized.txt`, #38 alias tests and status-merge fixtures. This
replaces scanning every record: names, ranks, squadron names and birthplaces
cannot establish nationality. Dossier `Null` is missing; other unsupported
index-1 values survive in both the pilot and `raw_strings`.

This is bounded to the existing fixture-backed layout, not a new layout or
real-build certification. Unsupported dual-field XML layouts and additional
services are not inferred. XML/Mission.log still cannot establish live career
identity or persist through the watcher; that safety boundary is unchanged.

## Persistence: no schema migration

Schema 3.4's `pilots.nation TEXT` can preserve every supported source observation
and legacy value. Its immutable interpretation independently exposes nation,
service and state. Additional mutable code/raw/state columns would duplicate
information and require unnecessary migration. There is no new DDL, JSON
encoding, metadata side channel, trigger, write-on-read or bulk campaign update.

`PilotRepository.get_nation_service` and
`DatabaseManager.get_pilot_nation_service` read this value by stable career ID.
Writes use the existing transaction and nonempty-field merge policy: missing
partial input retains stored evidence; explicit unsupported input replaces the
observation and remains unsupported. Changing that observation cannot retain a
stale service. General provenance/source-authority work in #99 is out of scope.

Legacy `RFC`, `RNAS`, `RAF` decode to `GB` plus their respective services;
`French`, `German`, `American`, `Belgian` decode to `FR`, `DE`, `US`, `BE`.
Unknown legacy values are never guessed or rewritten; SQL NULL/blank is missing.
Historically fabricated RFC cannot be distinguished from genuine RFC without
original evidence; this change does not pretend to restore already lost data.

Tests persist parsed Dossiers alongside unchanged legacy rows, reopen, compare
the complete schema, check integrity/foreign keys, and inject a composing
transaction failure. Career/root identity is unchanged. Rollback is a code
revert; no database downgrade/restore is needed. An old binary still has its
old recognition/display semantics. Normal export backups remain applicable;
tests only use synthetic temporary databases.

## Presentation and consumer audit

`NationService.presentation()` returns frozen `NationServicePresentation`:
independent codes/states and `nation_label` / `service_label`. Unsupported
evidence has no code and displays `Unsupported nation`; missing has no label.
Raw evidence/private paths never enter this presentation value. Labels cannot
establish business identity.

This replaces `serviceOrNationLabel` in new #81 contracts. Historical UI V2
evidence stays immutable; no production UI is implemented. Future nation
selectors must enumerate `NationCode`; service is a separate controlled choice
limited to evidence-backed `ServiceCode`. Date eligibility and pilot creation
remain outside #136.

CLI pilot details, extraction reports and watchdog parse diagnostics now use
separate canonical labels. The audit also covered ranks, medals, squadron
terminology, portraits/uniforms, NPC names, historical rules, narratives and
transfers. Current RPG/narrative/transfer code has no nation/service lookup.
Dossier ranks are a source-layout lexicon; portraits retain source photo IDs.
Medal catalog `country` is a raw filename category used for catalog identity,
not a playable-nation identity; no rule joins it to pilot nationality. Future
rules must use canonical codes rather than independently guessing from those
filename categories or display labels.

## Evidence

`woff/tests/test_nation_domain.py` enforces the five #136 evals.
`EVAL-NATION-MIGRATION-001` covers the legacy compatibility decision,
deterministic interpretation without mutation, reopen and rollback; it does
not claim that a schema migration exists. Existing normalization/parser tests
also assert canonical codes. #81 and integrated product approvals are separate.
