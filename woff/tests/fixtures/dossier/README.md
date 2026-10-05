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

The exact WoFF build remains unconfirmed. These fixtures define regression
coverage for the existing supported layout and do not authorize inference of
another layout.

The full and short valid fixtures place the nation/service observation at
zero-based index 1, also exercised by the existing #38 alias tests. #136 uses
that field in `fixed-index-v1`, preserving unsupported text and the `Null`
missing sentinel without scanning names or birthplaces for country aliases.

The blank-line parity fixture is synthetic and preserves only the physical-line
shape required by #180. It is not copied from a user campaign file and carries
no real roster identity or narrative.
