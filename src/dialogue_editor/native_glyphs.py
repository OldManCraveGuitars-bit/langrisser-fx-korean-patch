"""BIOS-backed printable pairs for the F486 text consumer.

Only 20/21 and control bytes are single-byte native tokens. ASCII is an
editor notation, not a byte encoding for this consumer. Keep private glyph
owners intact and use the existing JIS full-cell equivalents for ASCII.
"""
from __future__ import annotations

import re


# JIS X 0208 uses these punctuation forms instead of their Unicode fullwidth
# ASCII compatibility characters. No new font cells or aliases are allocated.
ASCII_PUNCTUATION = {'"': '″', "'": '′', '-': '−', '~': '〜'}


def paired_glyph(character: str, mapping: dict[str, bytes]) -> bytes:
    if len(character) != 1:
        raise ValueError('Expected one printable character')
    if character == '･':
        character = '・'
    if character in mapping:
        encoded = mapping[character]
    else:
        if '!' <= character <= '~':
            character = ASCII_PUNCTUATION.get(character, chr(ord(character) + 0xFEE0))
        encoded = character.encode('shift_jis')
    if len(encoded) != 2:
        raise ValueError(f'Not a native two-byte glyph: {character!r}')
    return encoded


def with_native_ascii(mapping: dict[str, bytes]) -> dict[str, bytes]:
    """Add the fixed BIOS repertoire; do not mutate a private font manifest."""
    result = dict(mapping)
    for code in range(33, 127):
        character = chr(code)
        result.setdefault(character, paired_glyph(character, mapping))
    return result


def native_phrase_resources(mapping: dict[str, bytes], phrases: dict[str, int]):
    """Pair root ASCII without reinterpreting an unchanged on-disc dictionary.

    Phrase plans were encoded with their original private mapping. If such a
    phrase contains unowned printable ASCII, its payload contains bare bytes
    that F486 consumes as a different pair. Do not reference that phrase;
    emit its unchanged text directly with the paired BIOS repertoire instead.
    Never relabel a dictionary code without also rewriting its payload.
    """
    def safe(text):
        plain = re.sub(r'\{[^}]*\}', '', text)
        return not any('!' <= ch <= '~' and ch not in mapping for ch in plain)
    return with_native_ascii(mapping), {text: code for text, code in phrases.items() if safe(text)}
