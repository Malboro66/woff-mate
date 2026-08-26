"""Shared helpers for decoding obfuscated WoFF text files."""

HEX_DIGITS = set(b"0123456789ABCDEF")


def unscramble(raw: bytes) -> bytes:
    """Remove the WoFF hex+counter obfuscation layer and return real bytes.

    CR and LF bytes are ignored. Every other non-uppercase-hex byte ends a
    token, empty tokens decode to NUL, and values above one byte raise
    ``ValueError``.
    """
    decoded = bytearray()
    value = 0
    has_digits = False

    for b in raw:
        if b in (0x0D, 0x0A):
            continue
        if b in HEX_DIGITS:
            has_digits = True
            if value <= 0xFF:
                digit = b - 0x30 if b <= 0x39 else b - 0x37
                value = (value << 4) | digit
            continue

        decoded.append(value if has_digits else 0)
        value = 0
        has_digits = False

    if has_digits:
        decoded.append(value)

    return bytes(decoded)
