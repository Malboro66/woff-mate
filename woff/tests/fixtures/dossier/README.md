# Sanitized Dossier fixtures

These fixtures contain synthetic decoded records, one record per line. Tests
apply the filename-derived WoFF obfuscation before passing the bytes to the
production parser. No raw campaign file, personal pilot identity, private
path, or game narrative is stored here.

| Fixture | Records | Contract exercised |
| --- | ---: | --- |
| `current_full_sanitized.txt` | 105 | Current `fixed-index-v1` fixed fields and optional roster data |
| `short_valid_sanitized.txt` | 50 | Valid identity with unavailable optional fields |
| `long_corrupt_sanitized.txt` | 51 | Sufficient length without required identity |
| `truncated_sanitized.txt` | 5 | Content ending before the final required identity field |

The exact WoFF build remains unconfirmed. These fixtures define regression
coverage for the existing supported layout and do not authorize inference of
another layout.
