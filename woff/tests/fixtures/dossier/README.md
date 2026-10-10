# Sanitized Dossier fixtures

These fixtures contain synthetic decoded records. Unless explicitly noted,
they use one logical record per physical line. Tests apply the filename-derived
WoFF obfuscation before passing the bytes to the production parser. No raw
campaign file, personal pilot identity, private path, or game narrative is
stored here.

| Fixture | Records | Contract exercised |
| --- | ---: | --- |
| `current_full_sanitized.txt` | 105 | Current `fixed-index-v1` fixed fields and optional roster data |
| `short_valid_sanitized.txt` | 50 | Valid identity, unavailable optional fields, and enough synthetic text to distinguish the complete key |
| `short_ambiguous_sanitized.txt` | 50 | Valid identity whose short records cannot distinguish two filename-derived keys and must fail closed |
| `long_corrupt_sanitized.txt` | 51 | Sufficient length without required identity |
| `truncated_sanitized.txt` | 5 | Content ending before the final required identity field |
| `blank_line_parity_sanitized.txt` | 3 logical / 4 physical | Internal blank physical line advances XOR key parity without creating a decoded record; the following synthetic roster-shaped record must remain decodable |

These legacy fixtures define nonauthoritative diagnostic decoding coverage,
not verified simulator output or runtime admission. The maintainer-attested
source captures come from BH&H II base v1.38; their observed runtime family has
161 physical positions and marker `160`. Synthetic reconstructions of that
family live in `test_issue96_observed_partial_roster.py` and `dossier_support.py`.
The attestation does not prove that every v1.38 file uses that family.

Runtime tests reconstruct physical slots and occupancy, rather than padding
legacy files. Complete historical roster tests stipulate membership through
`CompleteRosterDomainHarness`, which calls the real engine interface explicitly.
They preserve transaction, identity and event contracts without claiming a
complete census from partial game details. Legacy 50/105-record automatic
runtime admission is withdrawn; diagnostic and independent functional coverage
remains.

The full and short valid fixtures place the nation/service observation at
zero-based index 1, also exercised by the existing #38 alias tests. #136 uses
that field in `fixed-index-v1`, preserving unsupported text and the `Null`
missing sentinel without scanning names or birthplaces for country aliases.

The blank-line parity fixture is synthetic and preserves only the physical-line
shape required by #180. It is not copied from a user campaign file and carries
no real roster identity or narrative.
