#!/usr/bin/env python3
"""Find V810 code sequences that construct and write the KING K-RAM port."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


OPNAMES = {
    0x00: "mov", 0x01: "add", 0x02: "sub", 0x03: "cmp", 0x04: "shl", 0x05: "shr",
    0x06: "jmp", 0x07: "sar", 0x0C: "or", 0x0D: "and", 0x0E: "xor", 0x0F: "not",
    0x10: "mov", 0x11: "add", 0x13: "cmp", 0x28: "movea", 0x29: "addi", 0x2A: "jr", 0x2B: "jal",
    0x2C: "ori", 0x2D: "andi", 0x2E: "xori", 0x2F: "movhi",
    0x30: "ld.b", 0x31: "ld.h", 0x33: "ld.w", 0x34: "st.b", 0x35: "st.h",
    0x37: "st.w", 0x38: "in.b", 0x39: "in.h", 0x3B: "in.w", 0x3C: "out.b",
    0x3D: "out.h", 0x3F: "out.w",
    0x40: "bv", 0x41: "bl", 0x42: "be", 0x43: "bnh",
    0x44: "bn", 0x45: "br", 0x46: "blt", 0x47: "ble",
    0x48: "bnv", 0x49: "bnl", 0x4A: "bne", 0x4B: "bh",
    0x4C: "bp", 0x4D: "nop", 0x4E: "bge", 0x4F: "bgt",
}


def decode(data: bytes, pc: int) -> dict:
    hw0 = struct.unpack_from("<H", data, pc)[0]
    low, high = hw0 & 0xFF, hw0 >> 8
    opcode = high >> 2
    if (high & 0xE0) == 0x80:
        opcode = high >> 1
    arg1 = (low >> 5) + ((high & 3) << 3)
    arg2 = low & 0x1F
    size = 4 if opcode in set(range(0x28, 0x40)) else 2
    imm = struct.unpack_from("<H", data, pc + 2)[0] if size == 4 and pc + 4 <= len(data) else None
    target = None
    if opcode in (0x2A, 0x2B) and pc + 4 <= len(data):
        low_b, high_b, low_b2, high_b2 = data[pc:pc + 4]
        displacement = ((high_b & 3) << 24) | (low_b << 16) | (high_b2 << 8) | low_b2
        if displacement & (1 << 25):
            displacement -= 1 << 26
        target = (pc + displacement) & 0xFFFFFFFF
    elif 0x40 <= opcode <= 0x4F:
        displacement = hw0 & 0x01FF
        if displacement & 0x0100:
            displacement -= 0x0200
        target = (pc + displacement) & 0xFFFFFFFF
    return {"pc": pc, "opcode": opcode, "name": OPNAMES.get(opcode, f"op{opcode:02X}"), "r1": arg1, "r2": arg2, "imm": imm, "size": size, "target": target}


def text(ins: dict) -> str:
    if ins.get("target") is not None:
        return f'{ins["name"]} 0x{ins["target"]:08X}'
    if ins["size"] == 4:
        return f'{ins["name"]} 0x{ins["imm"]:04X}, r{ins["r2"]}, r{ins["r1"]}'
    return f'{ins["name"]} r{ins["r2"]}, r{ins["r1"]}'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ram", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--window", type=int, default=16)
    args = parser.parse_args()
    data = args.ram.read_bytes()
    hits = []
    for pc in range(0, len(data) - 4, 2):
        first = decode(data, pc)
        if first["opcode"] != 0x2F or first["imm"] != 0xBC00 or first["r2"] != 0:
            continue
        base_reg = first["r1"]
        context = [{"pc": f"0x{pc:X}", "text": text(first)}]
        cursor = pc + 4
        writes = []
        for _ in range(args.window):
            ins = decode(data, cursor)
            context.append({"pc": f"0x{cursor:X}", "text": text(ins)})
            if ins["opcode"] in (0x34, 0x35, 0x37) and ins["r2"] == base_reg:
                writes.append({"pc": f"0x{cursor:X}", "kind": ins["name"], "offset": f"0x{ins['imm']:04X}", "value_reg": ins["r1"]})
            cursor += ins["size"]
        hits.append({"constant_pc": f"0x{pc:X}", "base_reg": base_reg, "writes": writes, "context": context})
    result = {"schema": 1, "ram": str(args.ram), "hits": hits}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"constants={len(hits)} direct_write_sequences={sum(bool(hit['writes']) for hit in hits)}")
    for hit in hits:
        if hit["writes"]:
            print(hit["constant_pc"], f"r{hit['base_reg']}", hit["writes"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
