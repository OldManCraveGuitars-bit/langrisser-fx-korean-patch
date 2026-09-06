#!/usr/bin/env python3
"""Canonical PC-FX V810 instruction codec used by generated patch code.

The codec deliberately models the complete *PC-FX* profile rather than the
Virtual Boy extensions.  It rejects undefined primary opcodes, non-PC-FX
EI/DI encodings, invalid bit-string/FPU suboperations, non-canonical reserved
bits, odd control-flow displacements, and truncated 32-bit instructions.

Coordinates are explicit: ``offset`` indexes the supplied byte string while
``pc`` is the runtime address used for relative control flow.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct


FORM_I = "I"
FORM_II = "II"
FORM_III = "III"
FORM_IV = "IV"
FORM_V = "V"
FORM_VIA = "VIa"
FORM_VIB = "VIb"
FORM_IX = "IX"
FORM_BSTR = "BSTR"
FORM_FPP = "FPP"

OPNAMES = {
    0x00: "mov", 0x01: "add", 0x02: "sub", 0x03: "cmp",
    0x04: "shl", 0x05: "shr", 0x06: "jmp", 0x07: "sar",
    0x08: "mul", 0x09: "div", 0x0A: "mulu", 0x0B: "divu",
    0x0C: "or", 0x0D: "and", 0x0E: "xor", 0x0F: "not",
    0x10: "mov.i", 0x11: "add.i", 0x12: "setf", 0x13: "cmp.i",
    0x14: "shl.i", 0x15: "shr.i", 0x17: "sar.i", 0x18: "trap",
    0x19: "reti", 0x1A: "halt", 0x1C: "ldsr", 0x1D: "stsr",
    0x1F: "bstr",
    0x28: "movea", 0x29: "addi", 0x2A: "jr", 0x2B: "jal",
    0x2C: "ori", 0x2D: "andi", 0x2E: "xori", 0x2F: "movhi",
    0x30: "ld.b", 0x31: "ld.h", 0x33: "ld.w",
    0x34: "st.b", 0x35: "st.h", 0x37: "st.w",
    0x38: "in.b", 0x39: "in.h", 0x3A: "caxi", 0x3B: "in.w",
    0x3C: "out.b", 0x3D: "out.h", 0x3E: "fpp", 0x3F: "out.w",
    0x40: "bv", 0x41: "bl", 0x42: "be", 0x43: "bnh",
    0x44: "bn", 0x45: "br", 0x46: "blt", 0x47: "ble",
    0x48: "bnv", 0x49: "bnl", 0x4A: "bne", 0x4B: "bh",
    0x4C: "bp", 0x4D: "nop", 0x4E: "bge", 0x4F: "bgt",
}

FORMS = {}
FORMS.update({opcode: FORM_I for opcode in range(0x00, 0x10)})
FORMS.update({opcode: FORM_II for opcode in
              (0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x17, 0x18,
               0x1C, 0x1D)})
FORMS.update({0x19: FORM_IX, 0x1A: FORM_IX, 0x1F: FORM_BSTR})
FORMS.update({opcode: FORM_III for opcode in range(0x40, 0x50)})
FORMS.update({0x2A: FORM_IV, 0x2B: FORM_IV})
FORMS.update({opcode: FORM_V for opcode in
              (0x28, 0x29, 0x2C, 0x2D, 0x2E, 0x2F)})
FORMS.update({opcode: FORM_VIA for opcode in
              (0x30, 0x31, 0x33, 0x38, 0x39, 0x3A, 0x3B)})
FORMS.update({opcode: FORM_VIB for opcode in
              (0x34, 0x35, 0x37, 0x3C, 0x3D, 0x3F)})
FORMS[0x3E] = FORM_FPP

BSTR_SUBOPS = frozenset((0, 1, 2, 3, 8, 9, 10, 11, 12, 13, 14, 15))
FPP_SUBOPS_PCFX = frozenset((0, 2, 3, 4, 5, 6, 7, 11))


class V810CodecError(ValueError):
    """Rejected instruction or operand in the declared PC-FX profile."""


def _signed(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _reg(value: int) -> int:
    if not 0 <= value < 32:
        raise V810CodecError(f"register out of range: {value}")
    return value


def _signed_range(value: int, bits: int, *, even: bool = False) -> int:
    if not -(1 << (bits - 1)) <= value < (1 << (bits - 1)):
        raise V810CodecError(f"signed {bits}-bit value out of range: {value}")
    if even and value & 1:
        raise V810CodecError(f"unaligned control-flow displacement: {value}")
    return value


@dataclass(frozen=True)
class Instruction:
    opcode: int
    form: str
    low: int = 0
    high: int = 0
    immediate: int | None = None
    displacement: int | None = None
    target: int | None = None
    subop: int | None = None
    mode: int | None = None
    size: int = 2

    @property
    def name(self) -> str:
        return OPNAMES[self.opcode]


def instruction(opcode: int, *, low: int = 0, high: int = 0,
                immediate: int | None = None,
                displacement: int | None = None,
                subop: int | None = None, mode: int | None = None) -> Instruction:
    if opcode not in FORMS:
        raise V810CodecError(f"opcode outside PC-FX profile: 0x{opcode:02X}")
    form = FORMS[opcode]
    low, high = _reg(low), _reg(high)
    if form == FORM_I:
        if opcode == 0x06 and high != 0:
            raise V810CodecError("JMP reserved high register field must be zero")
    elif form == FORM_II:
        if opcode == 0x12 and low >= 16:
            raise V810CodecError("SETF condition is four bits")
        if opcode == 0x18 and high != 0:
            raise V810CodecError("TRAP reserved high register field must be zero")
    elif form == FORM_IX:
        if low or high:
            raise V810CodecError("IX register fields are reserved")
        if mode not in (0, 1):
            raise V810CodecError("IX mode must be zero or one")
    elif form == FORM_BSTR:
        if high:
            raise V810CodecError("BSTR high field is reserved")
        if subop not in BSTR_SUBOPS or low != subop:
            raise V810CodecError("invalid BSTR suboperation")
    elif form == FORM_III:
        low = high = 0
        if displacement is None:
            raise V810CodecError("branch displacement missing")
        _signed_range(displacement, 9, even=True)
    elif form == FORM_IV:
        low = high = 0
        if displacement is None:
            raise V810CodecError("JR/JAL displacement missing")
        _signed_range(displacement, 26, even=True)
    elif form in (FORM_V, FORM_VIA, FORM_VIB):
        if immediate is None or not -0x8000 <= immediate <= 0xFFFF:
            raise V810CodecError("16-bit immediate missing or out of range")
        immediate &= 0xFFFF
    elif form == FORM_FPP:
        if subop not in FPP_SUBOPS_PCFX:
            raise V810CodecError("invalid PC-FX FPP suboperation")
    size = 4 if form in (FORM_IV, FORM_V, FORM_VIA, FORM_VIB, FORM_FPP) else 2
    return Instruction(opcode, form, low, high, immediate, displacement,
                       None, subop, mode, size)


def encode(ins: Instruction) -> bytes:
    checked = instruction(ins.opcode, low=ins.low, high=ins.high,
                          immediate=ins.immediate,
                          displacement=ins.displacement,
                          subop=ins.subop, mode=ins.mode)
    form = checked.form
    if form == FORM_III:
        half = (checked.opcode << 9) | (checked.displacement & 0x1FE)
        return struct.pack("<H", half)
    if form == FORM_IV:
        value = checked.displacement & ((1 << 26) - 1)
        return bytes(((value >> 16) & 0xFF,
                      0xA8 | ((checked.opcode - 0x2A) << 2) | ((value >> 24) & 3),
                      value & 0xFF, (value >> 8) & 0xFF))
    half = (checked.opcode << 10) | (checked.high << 5) | checked.low
    if form == FORM_IX:
        half |= checked.mode
    if form in (FORM_V, FORM_VIA, FORM_VIB):
        return struct.pack("<HH", half, checked.immediate & 0xFFFF)
    if form == FORM_FPP:
        return struct.pack("<HH", half, checked.subop << 10)
    return struct.pack("<H", half)


def decode(data: bytes, offset: int = 0, pc: int = 0) -> Instruction:
    if offset < 0 or offset + 2 > len(data):
        raise V810CodecError("truncated 16-bit instruction")
    half = struct.unpack_from("<H", data, offset)[0]
    high_byte = half >> 8
    opcode = high_byte >> 1 if (high_byte & 0xE0) == 0x80 else high_byte >> 2
    if opcode not in FORMS:
        raise V810CodecError(f"invalid PC-FX opcode 0x{opcode:02X}")
    form = FORMS[opcode]
    low, high = half & 31, (half >> 5) & 31
    kwargs = {"low": low, "high": high}
    target = None
    if form == FORM_III:
        displacement = _signed(half & 0x1FF, 9)
        kwargs.update(low=0, high=0, displacement=displacement)
        target = (pc + displacement) & 0xFFFFFFFF
    elif form == FORM_IV:
        if offset + 4 > len(data):
            raise V810CodecError("truncated 32-bit JR/JAL")
        b0, b1, b2, b3 = data[offset:offset + 4]
        raw = ((b1 & 3) << 24) | (b0 << 16) | (b3 << 8) | b2
        displacement = _signed(raw, 26)
        kwargs.update(low=0, high=0, displacement=displacement)
        target = (pc + displacement) & 0xFFFFFFFF
    elif form in (FORM_V, FORM_VIA, FORM_VIB):
        if offset + 4 > len(data):
            raise V810CodecError("truncated 32-bit immediate instruction")
        kwargs.update(immediate=struct.unpack_from("<H", data, offset + 2)[0])
    elif form == FORM_IX:
        if half & 0x3FE:
            raise V810CodecError("non-canonical IX reserved bits")
        kwargs.update(low=0, high=0, mode=half & 1)
    elif form == FORM_BSTR:
        kwargs.update(subop=low)
    elif form == FORM_FPP:
        if offset + 4 > len(data):
            raise V810CodecError("truncated 32-bit FPP")
        second = struct.unpack_from("<H", data, offset + 2)[0]
        if second & 0x03FF:
            raise V810CodecError("non-canonical FPP reserved bits")
        kwargs.update(subop=second >> 10)
    checked = instruction(opcode, **kwargs)
    return Instruction(checked.opcode, checked.form, checked.low, checked.high,
                       checked.immediate, checked.displacement, target,
                       checked.subop, checked.mode, checked.size)


def encode_rr(opcode: int, source: int, destination: int) -> bytes:
    return encode(instruction(opcode, low=source, high=destination))


def encode_imm5(opcode: int, value: int, destination: int = 0) -> bytes:
    if not -16 <= value <= 31:
        raise V810CodecError(f"imm5 out of range: {value}")
    return encode(instruction(opcode, low=value & 31, high=destination))


def encode_v(opcode: int, immediate: int, base: int, other: int) -> bytes:
    return encode(instruction(opcode, low=base, high=other, immediate=immediate))


def encode_branch(pc: int, target: int, condition: int) -> bytes:
    return encode(instruction(condition, displacement=target - pc))


def encode_jump(pc: int, target: int, opcode: int) -> bytes:
    return encode(instruction(opcode, displacement=target - pc))


def encode_jal(pc: int, target: int) -> bytes:
    return encode_jump(pc, target, 0x2B)


def format_instruction(ins: Instruction) -> str:
    if ins.form in (FORM_III, FORM_IV):
        return f"{ins.name} 0x{ins.target:08X}"
    if ins.form in (FORM_V, FORM_VIA, FORM_VIB):
        return f"{ins.name} 0x{ins.immediate:04X},r{ins.low},r{ins.high}"
    if ins.form in (FORM_BSTR, FORM_FPP):
        return f"{ins.name}.{ins.subop:02X} r{ins.low},r{ins.high}"
    if ins.form == FORM_IX:
        return f"{ins.name} mode={ins.mode}"
    return f"{ins.name} r{ins.low},r{ins.high}"
