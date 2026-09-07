"""Bind subtitles to the common native movie call, not event/stack leftovers.

Native A7D8 receives physical movie 0..29 in r6, saves it at SP+34,
derives its stream start from the native size table, and calls D750 at A8A0.
The wrapper leaves SP and all five decoder arguments intact. Its return shim
clears the owned latch before continuing A8A4; it preserves decoder r10.
"""
from __future__ import annotations
import hashlib
from build_deployment_menu_hook import Assembler, encode_jal
from build_dense_charset_engine import encode_jr
import build_successor254_kram_disc_subtitles as kram
import subtitle_bootstrap as boot
import subtitle_return_anchor as old_bridge
import v810_pcfx_isa_profile as isa

MIRROR=0x277DB000
HELPER_RAM=0x87774
HELPER_OFFSET=0x80774
HELPER_BYTES=0x160
PREFIX_BYTES=0x8C
LATCH=0x878D0
CALL_RAM=0xA8A0
CALL_OFFSET=0x38A0
DECODER=0xD750
RETURN=0xA8A4
RESIDENT_SHA='c048f5f283fbb9ce6f922c2f619364b0ff3375c2efad11b2d82c5f3286f2343a'


def make_resident(prefix):
    if len(prefix)!=PREFIX_BYTES:raise ValueError('Protected KRAM helper extent')
    a=Assembler(HELPER_RAM)
    a.code.extend(prefix)
    a.label('route_guard')
    # Both branches own the same stack shape. Restore exact interrupted
    # command/argument values; no hardcoded scenario event restoration.
    a.addi(-8,3,3)
    for native,stack in ((0x1A0,0),(0x1A4,4)):
        a.load(0x33,native,0,11);a.store(0x37,stack,3,11)
    a.load_address(LATCH,10);a.load(0x33,0,10,11)
    a.add_i(-1,11)
    a.movea(30,0,17);a.reg(0x03,17,11)
    a.branch(0x49,'cleanup_return')  # unsigned id >= 30, including empty -1
    a.movea(0x120,0,17);a.store(0x37,0x1A0,0,17)
    a.store(0x37,0x1A4,0,11)
    a.code.extend(encode_jr(a.pc,boot.BOOT_B_RAM))
    a.label('cleanup_return')
    for native,stack in ((0x1A0,0),(0x1A4,4)):
        a.load(0x33,stack,3,11);a.store(0x37,native,0,11)
    a.addi(8,3,3)
    a.load(0x33,0x09C4,0,17)
    for offset,register in ((8,11),(4,10),(0,31)):
        a.load(0x33,offset,3,register)
    a.addi(12,3,3);a.add_i(2,31);a.reg(0x06,31,0)
    a.label('movie_enter')
    # Tail chaining is deliberate: pushing would move the fifth native
    # decoder argument (at caller SP+10) and corrupt playback.
    a.load(0x33,0x34,3,10)
    a.add_i(1,10)
    a.load_address(LATCH,11);a.store(0x37,0,11,10)
    exit_ram=a.pc+12  # load-address r31 (8), JR decoder (4)
    a.load_address(exit_ram,31)
    a.code.extend(encode_jr(a.pc,DECODER))
    a.label('movie_exit')
    if a.pc!=exit_ram:raise ValueError('Native return shim anchor')
    a.load_address(LATCH,11);a.store(0x37,0,11,0)
    a.load_address(RETURN,31);a.reg(0x06,31,0)
    code=a.finish()
    if a.pc>LATCH:raise ValueError(f'Resident code overlaps latch: {a.pc:#x}')
    isa.disassemble_range(code,HELPER_RAM)
    return code.ljust(HELPER_BYTES,b'\0'),dict(a.labels)


def plan(image):
    resident=image[HELPER_OFFSET:HELPER_OFFSET+HELPER_BYTES]
    if hashlib.sha256(resident).hexdigest()!=RESIDENT_SHA:
        raise ValueError('Pinned old resident identity')
    if image.count(resident)!=2:raise ValueError('Resident copy denominator')
    generated,_=kram.build_resident(0x31BC,0x3800)
    if generated!=resident[:PREFIX_BYTES]:raise ValueError('KRAM prefix changed')
    native=encode_jal(CALL_RAM,DECODER)
    if image.count(native)!=2:raise ValueError('Native decoder call denominator')
    code,symbols=make_resident(generated)
    a,b,_=boot.build_kram_staged_latched(HELPER_RAM,symbols['route_guard'],
        symbols['cleanup_return'],boot.TARGET_RAM,0xFFB4A463)
    if image[MIRROR+boot.BOOT_A_COOKED:MIRROR+boot.BOOT_A_COOKED+len(a)]!=a:
        raise ValueError('Protected VBlank entry changed')
    if image[old_bridge.OFFSET:old_bridge.OFFSET+96]!=old_bridge.BEFORE:
        raise ValueError('Frozen old bridge mismatch')
    if any(image[boot.BOOT_B_COOKED:boot.BOOT_B_COOKED+96]):
        raise ValueError('Unexpected executable primary B')
    writes=[]
    for bias in (0,MIRROR):
        for offset,before,after,owner in (
            (HELPER_OFFSET,resident,code,'resident-movie-lifecycle'),
            (CALL_OFFSET,native,encode_jal(CALL_RAM,symbols['movie_enter']),'native-decoder-call')):
            if image[bias+offset:bias+offset+len(before)]!=before:
                raise ValueError(f'Unexpected source copy {owner}')
            writes.append((bias+offset,before,after,f'subtitle/{owner}/{bias:#x}'))
    writes.append((old_bridge.OFFSET,old_bridge.BEFORE,b,'subtitle/bootstrap-lifecycle-cleanup'))
    return sorted(writes),{
        'physical_movie_namespace':[0,29], 'native_call':'0xA8A0',
        'native_decoder':'0xD750','native_continuation':'0xA8A4',
        'event_argument_exceptions':False,'stack_marker_used_for_routing':False,
        'payload_and_cues_unchanged':True,'kram_upload_restore_prefix_unchanged':True,
        'decoder_call_copies':2,'resident_copies':2,
        'labels':{k:hex(v) for k,v in symbols.items()},
        'code_end':hex(symbols['movie_exit']+22),'latch':hex(LATCH),
    }


def verify(image):
    protected,_=kram.build_resident(0x31BC,0x3800)
    code,symbols=make_resident(protected)
    for bias in (0,MIRROR):
        if image[bias+HELPER_OFFSET:bias+HELPER_OFFSET+HELPER_BYTES]!=code:
            raise ValueError('Final lifecycle helper mismatch')
        if image[bias+CALL_OFFSET:bias+CALL_OFFSET+4]!=encode_jal(CALL_RAM,symbols['movie_enter']):
            raise ValueError('Final decoder call mismatch')
    _a,b,_=boot.build_kram_staged_latched(HELPER_RAM,symbols['route_guard'],
        symbols['cleanup_return'],boot.TARGET_RAM,0xFFB4A463)
    if image[old_bridge.OFFSET:old_bridge.OFFSET+96]!=b:
        raise ValueError('Final bridge mismatch')
