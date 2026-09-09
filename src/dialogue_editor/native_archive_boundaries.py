"""Restore two terminal u32s damaged by obsolete subtitle-tail allocations.

Historical subtitle75 DATA_A/DATA_B started at the first zero *byte* of
the final native directory word, not after that complete word. The current
subtitle renderer is separately staged in KRAM and MAIN 0x1A8118. Preserve
that renderer, all current glyphs, and all resource bodies. Restore only
the two damaged high bytes and verify every interval in both directories.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct

# id, cooked header, entries including sentinel, native allocation, old high byte,
# SHA256 of the complete original Japanese directory, including its sentinel.
DIRECTORIES = (
    (13, 0x019FD800, 556, 0x6FE000, 0xBF,
     '9ff33f69c064d90a556111655e71ea98de446bbd29db9db7ee6ccd5e19713b0e'),
    (14, 0x020FB800, 75, 0x9B000, 0xFF,
     '60c21b928f0aa48f6f971c87b43166c147b81b0d123cea3d316edf6b5ac5eb67'),
)


def validate_directory(data: bytes, allocation: int) -> list[int]:
    if len(data) < 8 or len(data) % 4:
        raise ValueError('Native directory must contain complete u32 records')
    offsets = list(struct.unpack('<' + str(len(data)//4) + 'I', data))
    if offsets[0] < len(data) or offsets[-1] != allocation:
        raise ValueError('Directory extent or terminal sentinel mismatch')
    if any(x % 0x800 or x > allocation for x in offsets):
        raise ValueError('Unaligned or out-of-allocation native pointer')
    if any(a > b for a, b in zip(offsets, offsets[1:])):
        raise ValueError('Non-monotonic native directory')
    return offsets


def read_cooked(raw: Path, offset: int, length: int) -> bytes:
    result = bytearray()
    with raw.open('rb') as f:
        while length:
            sector, within = divmod(offset, 2048)
            count = min(length, 2048-within)
            f.seek((sector+225)*2352+16+within)
            block = f.read(count)
            if len(block) != count:
                raise ValueError('Original Track 2 directory is truncated')
            result.extend(block)
            offset += count
            length -= count
    return bytes(result)


def plan(image: bytes, original_track2: Path):
    writes, audit = [], []
    for number, header, count, allocation, bad, digest in DIRECTORIES:
        native = read_cooked(original_track2, header, count*4)
        if hashlib.sha256(native).hexdigest() != digest:
            raise ValueError(f'Japanese resource {number} directory identity')
        offsets = validate_directory(native, allocation)
        actual = image[header:header+count*4]
        expected = native[:-1] + bytes([bad])
        if actual != expected:
            raise ValueError(f'Unexpected directory drift: {number}')
        address = header+count*4-1
        writes.append((address, bytes([bad]), native[-1:],
                       f'native-directory/{number}/terminal-u32'))
        audit.append({'resource': number, 'header': hex(header),
            'native_entries': count-1, 'directory_bytes': count*4,
            'terminal_offset': hex(offsets[-1]), 'repair_cooked': hex(address),
            'native_sha256': digest,
            'largest_entry_sectors': max((b-a)//2048 for a,b in zip(offsets,offsets[1:])),
            'every_start_end_pair_checked': True})
    return writes, {'directories': audit, 'total_native_entries': 629,
                   'changed_bytes': 2, 'native_code_and_resource_bodies_changed': False,
                   'current_subtitle_payload_changed': False}


def verify(image: bytes):
    checked = 0
    for number, header, count, allocation, _bad, digest in DIRECTORIES:
        data = image[header:header+count*4]
        validate_directory(data, allocation)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f'Final directory {number} differs from Japanese')
        checked += count-1
    return {'native_entries': checked, 'all_directory_words_equal_japanese': True}
