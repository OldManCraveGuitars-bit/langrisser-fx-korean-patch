"""Teleport target troop idle fix, bounded to the native74-byte init block.

No new RAM/cave/stack/dispatcher. The first actor retains native magic;
remaining target actors have physical participation (+2) cleared only for
magic effect0x14. Native class handlers then enter completed/idle state3.
"""
import hashlib
from build_deployment_menu_hook import Assembler
import battle_report319 as prior
import v810_pcfx_isa_profile as isa

BASE_SHA = '932E88204EE3FFC3367F2DACB1489A3D6FD1A9CCE01AC19A699A3EA720B1E58E'
START, END = 0x35EDA, 0x35F24
RAM_DELTA, MAIN_MIRROR = 0x7000, 0x277DB000
BEFORE = bytes.fromhex('c0bd0700cea1d4d1f601e251cf050ece00003ca60400300651c200005dd2030040bd07006ace44f3604e208480bd07006ccd3cf3604d0c94c0a14a00dad103000a8a00a24b001ad20300')
sha = lambda b: hashlib.sha256(b).hexdigest().upper()


def build_code():
    a = Assembler(START)
    # Equivalent native handler lookup, using only scratch registers.
    a.mov(22, 18); a.imm5(0x14, 2, 18)
    a.movhi(7, 0, 12); a.reg(0x01, 18, 12)
    a.load(0x33, 0xD1D4, 12, 18); a.reg(0x01, 28, 18)
    a.load(0x30, 4, 18, 18); a.store(0x34, 3, 29, 18)
    a.movhi(7, 0, 10); a.load(0x33, 0xF344, 10, 19)
    a.imm5(0x13, 0, 19); a.branch(0x42, 'done')
    a.load(0x33, 0xF33C, 10, 11)
    a.movea(0x4A, 0, 16); a.imm5(0x13, 0, 11)
    a.branch(0x42, 'magic'); a.add_i(1, 16)
    a.label('magic'); a.store(0x34, 3, 26, 16)
    # Teleport only, target side only; preserve first actor's magic handler.
    a.movea(20, 0, 18); a.reg(0x03, 18, 11); a.branch(0x4A, 'done')
    a.imm5(0x13, 1, 22); a.branch(0x4A, 'done')
    a.reg(0x03, 26, 29); a.branch(0x42, 'done')
    a.store(0x34, 2, 29, 0)
    a.label('done')
    code = a.finish()
    assert len(code) == len(BEFORE) == END-START
    assert b''.join(raw for _, _, raw in isa.disassemble_range(code, START)) == code
    return code


def verify(image):
    prior.verify(image)
    for bias in (0, MAIN_MIRROR):
        at = bias + START-RAM_DELTA
        assert image[at:at+len(BEFORE)] == build_code()


def plan(image):
    assert sha(image) == BASE_SHA, 'Expected exact delivered319'
    prior.verify(image)
    writes = []
    for bias in (0, MAIN_MIRROR):
        at = bias+START-RAM_DELTA
        assert image[at:at+len(BEFORE)] == BEFORE
        writes.append((at, BEFORE, build_code(), f'teleport320/target-participation/{bias:#x}'))
    return writes
