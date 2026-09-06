"""Keep the resident dispatcher and Resource-12 router bounds in agreement.

Entry ABI: r6=unsigned private character, r10=0x10000, r11=the
dispatcher's exclusive upper bound.  The inherited 36-byte router was
built for F7AB.  Preserving that immediate while raising r11 redirected
F4 characters to the scenario-local F3 helper (not resident in narration).
"""

from __future__ import annotations

import v810_profile_codec as v810


RAM = 0x001E4100
BYTES = 36
S2_FIRST = 0xF340
S2_UPPER = 0xF3B6
PRIVATE_FIRST = 0xF440
S2_HELPER = 0x001A6A50
GLOBAL_HELPER = 0x001E4000
ORIGINAL_RESUME = 0x0008674C
INHERITED_UPPER = 0xF7AB
INHERITED = bytes.fromhex(
    "6BA10BFC CB0C 0E8C 6BA18A00 CB0C 0E8C FFABF0FE "
    "4BA18AFF FCAB3829 4AA140F0 EAAB2C26"
)


def build(upper: int) -> bytes:
    if not PRIVATE_FIRST < upper <= 0xFA00:
        raise ValueError(f"invalid atlas upper bound {upper:#x}")
    first = v810.encode(v810.instruction(
        0x28, low=11, high=11, immediate=S2_UPPER - upper,
    ))
    return first + INHERITED[4:]


def route(code: bytes, character: int, upper: int) -> tuple[int, tuple[int, ...]]:
    """Execute this short router using the complete PC-FX codec for decoding.

    This is a bounded semantic check of the router's implemented opcodes,
    not a general CPU emulator or evidence of runtime asset residency.
    """
    registers = [0] * 32
    registers[6], registers[10], registers[11] = character, 0x10000, upper
    pc, less = RAM, False
    for _ in range(16):
        if not RAM <= pc < RAM + len(code):
            return pc, tuple(registers)
        ins = v810.decode(code, pc - RAM, pc)
        if ins.opcode == 0x28:
            immediate = (ins.immediate if ins.immediate < 0x8000 else
                         ins.immediate - 0x10000)
            registers[ins.high] = (registers[ins.low] + immediate) & 0xFFFFFFFF
        elif ins.opcode == 0x03:
            signed = lambda n: n if n < 0x80000000 else n - 0x100000000
            less = signed(registers[ins.high]) < signed(registers[ins.low])
        elif ins.opcode == 0x46:
            if less:
                pc = ins.target
                continue
        elif ins.opcode == 0x2A:
            pc = ins.target
            continue
        else:
            raise ValueError(f"unmodelled router opcode {ins.name}")
        pc += ins.size
    raise ValueError("router did not terminate")


def verify(code: bytes, upper: int) -> dict:
    if len(code) != BYTES or code != build(upper):
        raise ValueError("Resource-12 router/dispatcher upper bounds disagree")
    offset = 0
    while offset < len(code):
        ins = v810.decode(code, offset, RAM + offset)
        if v810.encode(ins) != code[offset:offset + ins.size]:
            raise ValueError("router instruction round-trip failed")
        offset += ins.size
    for char in range(S2_FIRST, upper):
        target, registers = route(code, char, upper)
        expected = (S2_HELPER if char < S2_UPPER else
                    ORIGINAL_RESUME if char < PRIVATE_FIRST else GLOBAL_HELPER)
        if target != expected or registers[6] != char:
            raise ValueError(f"router wrong destination/live-out at {char:#x}")
        expected_r10 = S2_FIRST if target == S2_HELPER else (
            0xF040 if target == ORIGINAL_RESUME else 0x10000)
        if registers[10] != expected_r10:
            raise ValueError(f"router r10 ABI mismatch at {char:#x}")
    return {"upper": f"0x{upper:04X}", "bytes": BYTES,
            "checked_character_values": upper - S2_FIRST,
            "instruction_roundtrip": True, "destinations_and_live_outs": True}
