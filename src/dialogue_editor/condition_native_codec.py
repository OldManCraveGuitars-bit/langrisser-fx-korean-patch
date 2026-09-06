"""Lossless condition encoding against the active resource, never phrase labels.

F486/F4F2 read control bytes 00..09, special spaces 20/21, or exactly two
glyph bytes.  CP932 halfwidth characters are not a supported native grammar.
"""
from __future__ import annotations

from functools import lru_cache


def units(raw: bytes) -> tuple[bytes, ...]:
    result = []
    cursor = 0
    while cursor < len(raw):
        value = raw[cursor]
        size = 2 if value in (4, 9) or value >= 10 and value not in (0x20, 0x21) else 1
        token = raw[cursor:cursor + size]
        if len(token) != size:
            raise ValueError(f"truncated native token at {cursor:#x}: {raw.hex()}")
        if value >= 10 and value not in (0x20, 0x21):
            if not (0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC):
                raise ValueError(f"unsupported native glyph lead {value:#x} at {cursor:#x}")
            if not (0x40 <= token[1] <= 0xFC and token[1] != 0x7F):
                raise ValueError(f"unsupported native glyph trail {token.hex()} at {cursor:#x}")
        result.append(token)
        cursor += size
    return tuple(result)


def expand(raw: bytes, rows: tuple[bytes, ...], stack: tuple[int, ...] = ()) -> bytes:
    result = bytearray()
    for token in units(raw):
        if token[0] == 4:
            code = token[1]
            if code == 0:
                continue
            if code in stack or len(stack) >= 16 or code > len(rows):
                raise ValueError(f"invalid dictionary dependency: {stack + (code,)}")
            result.extend(expand(rows[code - 1], rows, stack + (code,)))
        else:
            result.extend(token)
    return bytes(result)


@lru_cache(maxsize=192)
def candidates(rows: tuple[bytes, ...]) -> tuple[tuple[tuple[bytes, ...], int], ...]:
    found: dict[tuple[bytes, ...], int] = {}
    for code, row in enumerate(rows[:239], 1):
        try:
            payload = units(expand(row, rows, (code,)))
        except ValueError:
            continue
        # Never insert a hidden page wait, terminator or arbitrary command.
        if sum(map(len, payload)) <= 2 or any(t[0] in (0, 1, 3, 6, 7) for t in payload):
            continue
        found.setdefault(payload, code)
    return tuple(sorted(found.items(), key=lambda item: (-sum(map(len, item[0])), item[1])))


def compress(literal: bytes, rows: tuple[bytes, ...]) -> bytes:
    source = units(literal)
    if any(t[0] == 4 for t in source):
        raise ValueError("compression input must be expanded, not a phrase label")
    choices = candidates(rows)
    best = [b""] * (len(source) + 1)
    for index in range(len(source) - 1, -1, -1):
        selected = source[index] + best[index + 1]
        for payload, code in choices:
            end = index + len(payload)
            if source[index:end] == payload:
                trial = bytes((4, code)) + best[end]
                if len(trial) < len(selected):
                    selected = trial
        best[index] = selected
    result = best[0]
    if expand(result, rows) != literal:
        raise ValueError("native condition round-trip differs from authored bytes")
    return result
