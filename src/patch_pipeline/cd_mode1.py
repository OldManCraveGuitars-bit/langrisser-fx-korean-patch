#!/usr/bin/env python3
"""Minimal CD-ROM Mode 1 EDC/ECC helpers for 2352-byte raw sectors."""

from __future__ import annotations

SECTOR_SIZE = 2352
USER_OFFSET = 16
USER_SIZE = 2048


def _tables() -> tuple[list[int], list[int], list[int]]:
    edc = []
    for value in range(256):
        result = value
        for _ in range(8):
            result = (result >> 1) ^ (0xD8018001 if result & 1 else 0)
        edc.append(result)
    forward = []
    backward = [0] * 256
    for value in range(256):
        result = value << 1
        if result & 0x100:
            result ^= 0x11D
        forward.append(result)
        backward[value ^ result] = value
    return edc, forward, backward


EDC_LUT, ECC_F_LUT, ECC_B_LUT = _tables()


def compute_edc(data: bytes | bytearray) -> int:
    result = 0
    for value in data:
        result = (result >> 8) ^ EDC_LUT[(result ^ value) & 0xFF]
    return result


def compute_ecc(
    source: bytes | bytearray,
    major_count: int,
    minor_count: int,
    major_mult: int,
    minor_inc: int,
) -> bytes:
    size = major_count * minor_count
    out = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        ecc_a = 0
        ecc_b = 0
        for _ in range(minor_count):
            value = source[index]
            index += minor_inc
            if index >= size:
                index -= size
            ecc_a ^= value
            ecc_b ^= value
            ecc_a = ECC_F_LUT[ecc_a]
        ecc_a = ECC_B_LUT[ECC_F_LUT[ecc_a] ^ ecc_b]
        out[major] = ecc_a
        out[major + major_count] = ecc_a ^ ecc_b
    return bytes(out)


def repair_mode1_sector(sector: bytearray) -> None:
    if len(sector) != SECTOR_SIZE:
        raise ValueError("raw sector must be 2352 bytes")
    if sector[15] != 1:
        raise ValueError(f"not a Mode 1 sector (mode={sector[15]})")
    sector[2064:2068] = compute_edc(sector[:2064]).to_bytes(4, "little")
    sector[2068:2076] = b"\x00" * 8
    sector[2076:2248] = compute_ecc(sector[12:2076], 86, 24, 2, 86)
    sector[2248:2352] = compute_ecc(sector[12:2248], 52, 43, 86, 88)


def verify_mode1_sector(sector: bytes) -> bool:
    rebuilt = bytearray(sector)
    repair_mode1_sector(rebuilt)
    return rebuilt == sector
