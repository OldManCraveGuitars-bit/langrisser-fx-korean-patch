"""Keep the seven condition glyphs beside the already-loaded Resource-12 router.

Successor236's native selector84 proves that the old 0x7DB8 helper and 0x7E00
glyph bank are absent from RAM. The caller still jumps there for F2C2..F2C8.
Use the atlas's explicitly reserved 0x200-byte helper header, after its 36-byte
router, in every full Resource-12 replica. Do not infer free game memory from
zeros, change text/code assignments, enlarge resources, or inject runtime RAM.
"""
from __future__ import annotations

import hashlib

import early_dialogue_font as font
import build_r80_full_conditions_successor203 as old
import v810_profile_codec as v810

OFFSET = font.ROUTER_OFFSET + font.ROUTER_BYTES  # 0x124, after the live router.
RAM = font.atlas.TAIL_RAM + OFFSET
HANDLER_CAPACITY = old.LOW_HANDLER_CAPACITY
GLYPH_RAM = RAM + HANDLER_CAPACITY
BYTES = HANDLER_CAPACITY + 7 * old.GLYPH_BYTES


def build_handler() -> bytes:
    # Same range tests, registers and fallback targets as successor203. Only
    # the helper's execution address and seven-glyph source address change.
    a = old.Assembler(RAM)
    a.movhi(1, 0, 10)
    a.movea(old.SPECIAL_FIRST - 0x10000, 10, 11)
    a.reg(0x03, 11, 6)
    a.branch(0x46, 'special')
    a.movea(old.NEW_FIRST - old.SPECIAL_FIRST, 11, 11)
    a.reg(0x03, 11, 6)
    a.branch(0x46, 'native')
    a.movea(old.NEW_UPPER_EXCLUSIVE - old.NEW_FIRST, 11, 12)
    a.reg(0x03, 12, 6)
    a.branch(0x4E, 'native')
    a.reg(0x02, 11, 6)
    a.mov(6, 11)
    a.imm5(0x14, 4, 6)
    a.imm5(0x14, 1, 11)
    a.reg(0x01, 11, 6)
    a.load_address(GLYPH_RAM, 10)
    a.reg(0x01, 10, 6)
    a.code.extend(old.encode_jr(a.pc, old.GLYPH_RENDERER_RAM))
    a.label('special')
    a.code.extend(old.encode_jr(a.pc, old.SPECIAL_TARGET_RAM))
    a.label('native')
    a.code.extend(old.encode_jr(a.pc, old.NATIVE_TARGET_RAM))
    result = a.finish()
    if len(result) > HANDLER_CAPACITY or OFFSET + BYTES > font.atlas.ATLAS_OFFSET:
        raise ValueError('Condition helper exceeds its owned Resource-12 header')
    return result


def payload() -> bytes:
    glyphs, _ = old.glyph_payload()
    result = build_handler().ljust(HANDLER_CAPACITY,b'\0') + glyphs
    if len(result) != BYTES:
        raise ValueError('Seven-glyph condition bank size changed')
    return result


def execute(code: bytes, base: int, character: int) -> tuple[int, tuple[int,...]]:
    """Bounded independent instruction decoding for this helper's ABI proof."""
    registers = [0x13570000+i for i in range(32)]
    registers[0], registers[6] = 0, character
    pc, less = base, False
    for _ in range(40):
        if not base <= pc < base+len(code):
            return pc, tuple(registers)
        ins = v810.decode(code,pc-base,pc)
        sign = lambda n: n if n < 0x80000000 else n-0x100000000
        if ins.opcode == 0x2F:  # MOVHI
            registers[ins.high] = registers[ins.low]+(ins.immediate<<16)
        elif ins.opcode == 0x28:  # MOVEA
            immediate = ins.immediate if ins.immediate < 0x8000 else ins.immediate-0x10000
            registers[ins.high] = registers[ins.low]+immediate
        elif ins.opcode == 0x03:
            less = sign(registers[ins.high]) < sign(registers[ins.low])
        elif ins.opcode in (0x46,0x4E):
            if less == (ins.opcode == 0x46):
                pc = ins.target
                continue
        elif ins.opcode == 0x00:  # MOV reg
            registers[ins.high] = registers[ins.low]
        elif ins.opcode == 0x01:  # ADD reg
            registers[ins.high] += registers[ins.low]
        elif ins.opcode == 0x02:  # SUB reg
            registers[ins.high] -= registers[ins.low]
        elif ins.opcode == 0x14:  # SHL immediate
            registers[ins.high] <<= ins.low
        elif ins.opcode == 0x2A:
            pc = ins.target
            continue
        else:
            raise ValueError(f'Unmodelled condition helper opcode {ins.name}')
        registers[ins.high] &= 0xFFFFFFFF
        registers[0] = 0
        pc += ins.size
    raise ValueError('Condition helper did not return')


def verify_machine() -> dict:
    code, inherited = build_handler(), old.build_low_handler()
    offset = 0
    while offset < len(code):
        ins = v810.decode(code,offset,RAM+offset)
        if v810.encode(ins) != code[offset:offset+ins.size]:
            raise ValueError('Condition helper instruction round trip')
        offset += ins.size
    for character in range(0x10000):
        before_target, before_regs = execute(inherited,old.LOW_HANDLER_RAM,character)
        target, regs = execute(code,RAM,character)
        expected = list(before_regs)
        if old.NEW_FIRST <= character < old.NEW_UPPER_EXCLUSIVE:
            expected[6] += GLYPH_RAM-old.LOW_GLYPH_RAM
            expected[10] = GLYPH_RAM
            if target != old.GLYPH_RENDERER_RAM or regs[6] != GLYPH_RAM+(character-old.NEW_FIRST)*18:
                raise ValueError('Condition glyph source calculation')
        if target != before_target or regs != tuple(expected):
            raise ValueError(f'Condition helper ABI difference {character:#x}')
    return {'unsigned_code_values_checked':65536,'instruction_roundtrip':True,
            'fallback_targets_and_live_registers_preserved':True,
            'helper_ram':hex(RAM),'glyph_ram':hex(GLYPH_RAM),'reserved_header_bytes':BYTES}


def plan_writes(image: bytes) -> tuple[list[dict],dict]:
    expected_jump = old.encode_jr(old.MAIN_SPECIAL_JR_RAM,old.LOW_HANDLER_RAM)
    target = old.MAIN_SPECIAL_JR_COOKED
    if image[target:target+4] != expected_jump:
        raise ValueError('Condition dispatcher source changed')
    data = payload()
    writes = [dict(id='conditions/resident-dispatch',offset=target,expected=expected_jump,
                   replacement=old.encode_jr(old.MAIN_SPECIAL_JR_RAM,RAM))]
    tails = font.resource12_tails(image)
    for ordinal,tail in enumerate(tails):
        start = tail+OFFSET
        if image[start:start+BYTES] != bytes(BYTES):
            raise ValueError(f'Condition header overlaps another writer in replica {ordinal}')
        writes.append(dict(id=f'conditions/resident-bank/{ordinal:02d}',offset=start,
                           expected=bytes(BYTES),replacement=data))
    return writes, {**verify_machine(),'replicas':len(tails),
                    'payload_sha256':hashlib.sha256(data).hexdigest().upper(),
                    'resource_extents_changed':False,'character_codes_changed':False,
                    'old_low_bank_retained_unreferenced':True}


def verify_final(image: bytes) -> dict:
    target = old.MAIN_SPECIAL_JR_COOKED
    if image[target:target+4] != old.encode_jr(old.MAIN_SPECIAL_JR_RAM,RAM):
        raise ValueError('Final condition dispatcher targets absent low memory')
    expected = payload()
    tails = font.resource12_tails(image)
    for tail in tails:
        if image[tail+OFFSET:tail+OFFSET+BYTES] != expected:
            raise ValueError('Final condition resident bank differs')
    return {**verify_machine(),'replicas':len(tails),'verified_after_last_writer':True}
