"""Append-only X2/X3 font cells within explicitly reserved Resource-12 gaps.

No old glyph, F8 clone, matchup byte or continuation instruction is replaced.
The short Resource-12 family is excluded. This profile is a review input and
requires cold loader, residency and renderer evidence before completion.
"""
import json,struct
from pathlib import Path
import muscle_temple_dialogue as base
import early_dialogue_font as font
import resource12_router as router
import condition_resident as condition
import combat_matchup_resident as combat
import dialogue_continuation_resident as continuation
import build_successor252_item_font_runtime_safe as safe
from build_deployment_menu_hook import Assembler
import v810_profile_codec as v810
from korean_font_policy import unifont_dense_12

ROOT=Path(__file__).resolve().parents[1]
need=base.need
# Each new owner is after the pinned F9D1 boundary; never re-sort later builds.
ADDITIONS=tuple(zip('댕딴땡믹쟤줌챔컬쿤흔',range(0xF9D2,0xF9DC)))
# Six cells after the finite 18x18x2 combat table, two after the 204-byte
# continuation helper, two after the existing eleven-glyph extension.
SEGMENTS=((0xF9C7,0xF9D2,0x5F00),(0xF9D2,0xF9D8,0x5D88),
          (0xF9D8,0xF9DA,0x5ECC),(0xF9DA,0xF9DC,0x5FC6))
UPPER=0xF9DC

def mapping():
    result=base.mapping_and_font()[0]
    for c,n in condition.GLYPH_ROWS:result.setdefault(c,n.to_bytes(2,'big'))
    for c,n in ADDITIONS:
        need(c not in result and n.to_bytes(2,'big') not in result.values(),'X glyph identity collision')
        result[c]=n.to_bytes(2,'big')
    return result

def build_helper():
    a=Assembler(font.atlas.TAIL_RAM)
    a.load_address(UPPER,10);a.reg(3,10,6);a.branch(0x4E,'original')
    # Select only the appended region before calculating the ordinary atlas.
    for first,end,offset in reversed(SEGMENTS):
        a.load_address(first,10);a.reg(3,10,6);a.branch(0x4E,f'new_{first:X}')
    a.mov(6,10);a.imm5(0x15,8,10)
    a.movea(0xF4,0,11);a.reg(3,11,10);a.branch(0x46,'original')
    a.movea(0xF8,0,11);a.reg(3,11,10);a.branch(0x42,'f8')
    # r6 = valid-trail ordinal + 188*(lead-F4), with only the original
    # helper's scratch registers r10/r11. No multiply/r30 side effect.
    a.addi(-0xF4,10,10)
    a.fmt_v(0x2D,0xFF,6,6);a.addi(-0x40,6,6)
    a.movea(0x40,0,11);a.reg(3,11,6);a.branch(0x46,'trail_ready')
    a.add_i(-1,6)
    a.label('trail_ready')
    a.mov(10,11);a.imm5(0x14,6,11) # lead*64
    a.imm5(0x14,2,10);a.reg(2,10,6) # subtract lead*4
    a.mov(11,10);a.imm5(0x14,1,10);a.reg(1,11,10) # lead*192
    a.reg(1,10,6)
    a.load_address(font.atlas.TAIL_RAM+0x200,10);a.branch(0x45,'index_ready')
    a.label('f8')
    a.fmt_v(0x2D,0xFF,6,6);a.addi(-0x40,6,6)
    a.movea(0x40,0,11);a.reg(3,11,6);a.branch(0x46,'f8_ready')
    a.add_i(-1,6)
    a.label('f8_ready');a.load_address(safe.F8_SAFE_RAM,10);a.branch(0x45,'index_ready')
    for first,end,offset in SEGMENTS:
        a.label(f'new_{first:X}')
        # r10 still holds first on the taken comparison branch.
        a.reg(2,10,6);a.load_address(font.atlas.TAIL_RAM+offset,10)
        a.branch(0x45,'index_ready')
    a.label('index_ready')
    a.mov(6,11);a.imm5(0x14,4,6);a.imm5(0x14,1,11)
    a.reg(1,11,6);a.reg(1,10,6)
    a.code.extend(font.atlas.encode_jr(a.pc,font.atlas.GLYPH_RENDERER_RAM))
    a.label('original');a.load_address(0x10000,10);a.movea(0xF040,10,10)
    a.code.extend(font.atlas.encode_jr(a.pc,font.atlas.ORIGINAL_THIRD_RAM))
    raw=a.finish();need(len(raw)<=0x100,f'X helper overflow {len(raw)}')
    p=0
    while p<len(raw):
        ins=v810.decode(raw,p,font.atlas.TAIL_RAM+p)
        need(v810.encode(ins)==raw[p:p+ins.size],'X helper ISA roundtrip')
        p+=ins.size
    return raw.ljust(0x100,b'\0')

def execute(raw,character):
    r=[0]*32;r[6]=character;pc=font.atlas.TAIL_RAM;comparison=0
    signed=lambda x:x if x<0x80000000 else x-0x100000000
    for _ in range(128):
        if not font.atlas.TAIL_RAM<=pc<font.atlas.TAIL_RAM+0x100:return pc,r
        ins=v810.decode(raw,pc-font.atlas.TAIL_RAM,pc);op=ins.opcode;lo,hi=ins.low,ins.high
        imm=ins.immediate;simm=None if imm is None else imm if imm<0x8000 else imm-0x10000
        if op==0x2F:r[hi]=(r[lo]+(imm<<16))&0xFFFFFFFF
        elif op in (0x28,0x29):r[hi]=(r[lo]+simm)&0xFFFFFFFF
        elif op==0x2D:r[hi]=r[lo]&imm
        elif op==0:r[hi]=r[lo]
        elif op==1:r[hi]=(r[hi]+r[lo])&0xFFFFFFFF
        elif op==2:r[hi]=(r[hi]-r[lo])&0xFFFFFFFF
        elif op==3:comparison=signed(r[hi])-signed(r[lo])
        elif op==0x11:r[hi]=(r[hi]+(lo if lo<16 else lo-32))&0xFFFFFFFF
        elif op==0x14:r[hi]=(r[hi]<<lo)&0xFFFFFFFF
        elif op==0x15:r[hi]>>=lo
        elif op==0x2A:pc=ins.target;continue
        elif op in (0x42,0x45,0x46,0x4E):
            if op==0x45 or op==0x42 and comparison==0 or op==0x46 and comparison<0 or op==0x4E and comparison>=0:
                pc=ins.target;continue
        else:raise ValueError(f'Unexpected X helper operation {ins}')
        r[0]=0;pc+=ins.size
    raise ValueError('X helper did not terminate')

def contract(raw):
    # Exhaustively compare every prior valid two-byte glyph input, not just
    # characters appearing in the new draft. Other input branches stay native.
    old=base.build_helper();tested=0
    for lead in range(0x81,0xFD):
        if not (lead<=0x9F or lead>=0xE0):continue
        for trail in range(0x40,0xFD):
            if trail==0x7F:continue
            code=lead*256+trail
            if 0xF9D2<=code<UPPER:continue
            pc,r=execute(raw,code);oldpc,oldr=base.helper_result(old,code)
            need((pc,r[6])==(oldpc,oldr[6]),f'Prior glyph route changed {code:04X}')
            tested+=1
    for c,code in ADDITIONS:
        first,end,offset=next(s for s in SEGMENTS if s[0]<=code<s[1])
        pc,r=execute(raw,code)
        need(pc==font.atlas.GLYPH_RENDERER_RAM and
             r[6]==font.atlas.TAIL_RAM+offset+(code-first)*18,'New glyph address')
    return {'prior_valid_glyph_inputs_compared':tested,'new_cells':len(ADDITIONS)}

def plan(source):
    helper=build_helper();audit=contract(helper);writes=[]
    before=safe.build_helper(safe.F8_SAFE_RAM)
    for i,tail in enumerate(font.resource12_tails(source)):
        need(base.sha(source[tail+combat.OFFSET:tail+combat.OFFSET+combat.SIZE])==combat.TABLE_SHA,'Combat owner drift')
        need(base.sha(source[tail+continuation.OFFSET:tail+continuation.OFFSET+continuation.HELPER_BYTES])==continuation.HELPER_SHA256,'Continuation owner drift')
        writes.append((tail,before,helper,f'hidden-x/font-helper/{i}'))
        writes.append((tail+0x100,router.build(0xF9C7),router.build(UPPER),f'hidden-x/router/{i}'))
        for c,code in ADDITIONS:
            first,end,offset=next(s for s in SEGMENTS if s[0]<=code<s[1])
            at=tail+offset+(code-first)*18
            need(source[at:at+18]==bytes(18),'Reserved font suballocation has another owner')
            writes.append((at,bytes(18),unifont_dense_12(c)[0],f'hidden-x/new-glyph/{i}/{c}'))
    for bias in (0,base.MIRROR):
        encode=lambda n:bytes.fromhex('6ba1')+struct.pack('<H',n-font.HANDLER_BASE_VALUE)
        writes.append((bias+font.HANDLER_COOKED+font.HANDLER_UPPER_MOVEA_OFFSET,
                       encode(0xF9C7),encode(UPPER),f'hidden-x/dispatcher/{bias:X}'))
    return sorted(writes),{**audit,'new_glyphs':[(c,hex(n)) for c,n in ADDITIONS],
        'segments':SEGMENTS,'ning_reuses_existing_condition_code':'F2C1',
        'all_old_glyph_bytes_and_other_owner_bytes_preserved':True}

def verify(image):
    helper=build_helper();audit=contract(helper)
    for tail in font.resource12_tails(image):
        need(image[tail:tail+0x100]==helper,'Final X glyph helper')
        for c,code in ADDITIONS:
            first,end,offset=next(s for s in SEGMENTS if s[0]<=code<s[1])
            at=tail+offset+(code-first)*18
            need(image[at:at+18]==unifont_dense_12(c)[0],'Final X glyph bytes')
    return {**audit,**font.verify_final_router_contract(image)}
