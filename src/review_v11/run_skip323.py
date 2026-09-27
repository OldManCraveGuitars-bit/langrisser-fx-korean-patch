"""Private RUN-hold prototype, pinned to successor322.

Never changes event PCs, rewards, scenario branches or decoder cleanup.
Resident code uses tails reclaimed
by semantically equivalent compact native window-clear routines. Field-only
code shares the Resource-12 atlas lifetime. No 88000 staging allocation.
"""
import hashlib
from pathlib import Path
from build_deployment_menu_hook import Assembler
import v810_profile_codec as c

ROOT = Path(__file__).resolve().parents[1]
BIAS = 0x277DB000
DELTA = 0x7000
STATE = 0x4ABA0  # deadline, latch: 0 idle, 1 active, -1 release required
TIMER = 0x4ABA8
HOLD_FRAMES = 72  # About 1.2 seconds at the game's native 59.94 Hz (V1.1).
# Native event commands which leave a connected conversation. Camera focus,
# voice/music setup, facing, delays, flags and script calls are NOT boundaries.
# 1D / 43 are the actual two/three-way choices; 30 invokes a movie.
EVENT_BOUNDARIES = frozenset((
    0x0D,0x0E,0x14,0x15,0x1D,0x1E,0x1F,0x21,0x22,0x24,0x25,0x26,
    0x28,0x2D,0x2E,0x2F,0x30,0x35,0x36,0x37,0x39,0x3F,0x43,0x44,
    0x45,0x47,0x48,0x4D,0x4F,0x50,0x51,0x52,0x53,0x54,0x57))
EXPECTED = 'C78B9294FA9DE028707CB681E32681106EE1A0ACAD15B72773145EB278DAE16D'
sha = lambda b: hashlib.sha256(b).hexdigest().upper()

def ld(a, at, base, dst): a.load(0x33,at,base,dst)
def st(a, at, base, src): a.store(0x37,at,base,src)
def ret(a): a.reg(6,31,0)
def jr(a, target): a.code.extend(c.encode_jump(a.pc,target,0x2A))
def cmpi(a, val, reg): a.imm5(0x13,val,reg)
def pro(a, size=4): a.addi(-size,3,3);st(a,size-4,3,31)
def epi(a, size=4): ld(a,size-4,3,31);a.addi(size,3,3);ret(a)
def prime(a): a.movhi(5,0,11);st(a,STATE&65535,11,0)

def timer(base, syms):
    a=Assembler(base)
    a.mov_i(0,10);a.movhi(5,0,11);ld(a,(STATE+4)&65535,11,12)
    cmpi(a,1,12);a.branch(0x42,'active')
    ld(a,0x7AD0,0,13);a.fmt_v(0x2D,0x80,13,13);a.branch(0x4A,'held')
    st(a,STATE&65535,11,0);st(a,(STATE+4)&65535,11,0);ret(a)
    a.label('held');cmpi(a,0,12);a.branch(0x46,'return')
    ld(a,STATE&65535,11,12);cmpi(a,0,12);a.branch(0x42,'start')
    ld(a,0x9C4,0,13);a.reg(2,12,13);a.branch(0x44,'return')
    a.label('active');a.mov_i(1,10);st(a,(STATE+4)&65535,11,10)
    a.label('return');ret(a)
    a.label('start');ld(a,0x9C4,0,13);a.addi(HOLD_FRAMES,13,13);st(a,STATE&65535,11,13);ret(a)
    return a.finish()

def reset(base, syms):
    # Leaf: clobbers only r11/r12. Preserve r10 (decoder result/opcode).
    a=Assembler(base);a.movhi(5,0,11);st(a,STATE&65535,11,0)
    ld(a,0x7AD0,0,12);a.fmt_v(0x2D,0x80,12,12)
    a.imm5(0x15,7,12);a.reg(0x0F,12,12);a.add_i(1,12)
    st(a,(STATE+4)&65535,11,12);ret(a)
    return a.finish()

def field_clear(base, syms):
    # 245C2: same eight cache resets and four 2C000/400/800/C00 writes.
    a=Assembler(base);pro(a,0x1C);st(a,0x14,3,29);a.mov_i(0,29)
    a.label('palette');a.addi(0x10,29,6);a.jal(0x11D24);a.add_i(1,29)
    cmpi(a,8,29);a.branch(0x46,'palette')
    ld(a,0x69DC,0,10);a.movea(100,0,11);a.reg(3,11,10);a.branch(0x4A,'finish')
    a.mov_i(0,29);a.label('rows');a.mov_i(15,10);st(a,0x10,3,10)
    a.mov(29,9);a.imm5(0x14,10,9);a.load_address(0x2C000,11);a.reg(1,11,9)
    a.mov(29,8);a.imm5(0x14,1,8);a.add_i(1,8);a.mov_i(4,7)
    a.movhi(7,0,11);ld(a,0xC6F4,11,6);a.jal(0x11DA8)
    a.add_i(1,29);cmpi(a,4,29);a.branch(0x46,'rows')
    a.label('finish');a.movhi(7,0,11);ld(a,0xC6F4,11,6);a.jal(0x11724)
    ld(a,0x14,3,29);epi(a,0x1C)
    return a.finish()

def narration_clear(base, syms):
    # 4AC24: same window metadata, four row writes, callbacks and E328.
    a=Assembler(base);pro(a,0x20);st(a,0x18,3,29)
    ld(a,0x269C,0,6);a.jal(0x111BE)
    a.load_address(0x5D4C8,11);ld(a,0x269C,0,10)
    a.movea(0x18,0,12);a.reg(0x0A,12,10);a.reg(1,10,11);a.store(0x34,10,11,0)
    a.mov_i(0,29);a.label('rows');a.movea(16,0,10);st(a,0x10,3,10)
    a.mov(29,9);a.imm5(0x14,10,9);a.load_address(0x2C000,11);a.reg(1,11,9)
    a.mov(29,8);a.imm5(0x14,1,8);a.mov_i(0,7);ld(a,0x269C,0,6);a.jal(0x11DA8)
    a.add_i(1,29);cmpi(a,4,29);a.branch(0x46,'rows');a.jal(0x4ABF4)
    a.store(0x34,0xA3D,0,0);a.mov_i(1,10);a.store(0x34,0xA3C,0,10)
    a.load_address(0x4AA30,12);a.movhi(6,0,11);st(a,0xA990,11,12)
    a.load_address(0x4ABF4,12);st(a,0xA994,11,12)
    ld(a,0x69DC,0,10);a.add_i(-1,10);a.load_address(0x52205,12);a.reg(1,10,12)
    a.load(0x30,0,12,10);a.fmt_v(0x2D,255,10,10)
    for off in (0xA9AE,0xA9AC,0xA9AA,0xA9A8):a.store(0x35,off,11,10)
    a.store(0x35,0xA99A,11,0)
    a.mov_i(2,9);a.mov_i(1,8);a.mov_i(7,7);a.load_address(0x2C000,6);a.jal(0xE328)
    a.jal(syms.get('reset',0));ld(a,0x18,3,29);epi(a,0x20)
    return a.finish()

def narration_title(base, syms):
    a=Assembler(base);pro(a,0x34)
    for r,off in ((27,0x2C),(29,0x24)):st(a,off,3,r)
    a.load_address(0x55E28,11)
    ld(a,0,11,10);st(a,0x14,3,10);a.load(0x31,4,11,10);a.store(0x35,0x18,3,10)
    ld(a,8,11,10);st(a,0x1C,3,10);ld(a,12,11,10);st(a,0x20,3,10)
    a.mov_i(8,7);a.movea(24,0,6);a.jal(0x11660);st(a,0x269C,0,10)
    a.load_address(0x52205,11);ld(a,0x69DC,0,10);a.reg(1,10,11)
    a.load(0x30,-1,11,27);a.fmt_v(0x2D,255,27,27)
    a.movea(22,0,11);a.reg(3,11,27);a.branch(0x46,'number')
    a.movea(0xA5,0,10);a.store(0x34,0x18,3,10);a.addi(0x4A,27,10);a.store(0x34,0x19,3,10)
    a.branch(0x45,'chars')
    a.label('number');a.mov(27,10);a.mov_i(10,11);a.reg(9,11,10)
    cmpi(a,10,27);a.branch(0x46,'units');a.addi(0x5F,10,10);a.store(0x34,0x18,3,10)
    a.label('units');a.addi(0x5F,30,10);a.store(0x34,0x19,3,10)
    a.label('chars');a.mov_i(0,29);a.label('charloop');a.addi(0x14,3,11);a.reg(1,29,11)
    a.load(0x30,0,11,9);a.fmt_v(0x2D,255,9,9);a.mov_i(1,8)
    a.mov(29,7);a.imm5(0x14,1,7);a.add_i(6,7);ld(a,0x269C,0,6);a.jal(0x11C38)
    a.add_i(1,29);cmpi(a,6,29);a.branch(0x46,'charloop')
    st(a,0x26AC,0,0);a.mov_i(0,29);a.movea(0x62FC,0,27)
    a.label('unitsloop')
    a.load(0x30,0x3D,27,10);cmpi(a,1,10);a.branch(0x4A,'nextunit')
    a.mov(27,6);a.jal(0x1B564);cmpi(a,0,10);a.branch(0x42,'nextunit')
    a.mov_i(0,7);a.mov(27,6);a.jal(0x1B4FC)
    a.mov(10,11);a.imm5(0x17,8,11);st(a,0x10,3,11)
    a.mov(10,9);a.mov_i(4,8);ld(a,0x26AC,0,10);a.addi(0x1C,3,11);a.reg(1,10,11)
    a.load(0x30,0,11,7);a.fmt_v(0x2D,255,7,7);ld(a,0x269C,0,6);a.jal(0x11FA4)
    ld(a,0x26AC,0,10);a.add_i(1,10);st(a,0x26AC,0,10)
    a.label('nextunit');a.addi(88,27,27);a.add_i(1,29);a.movea(20,0,10);a.reg(3,10,29);a.branch(0x46,'unitsloop')
    a.movea(19,0,8);a.mov_i(4,7);ld(a,0x269C,0,6);a.jal(0x117D0)
    for r,off in ((27,0x2C),(29,0x24)):ld(a,off,3,r)
    epi(a,0x34);return a.finish()

def wait(base, syms):
    # Used only by the proven field manual callback and narration callback.
    # FF38 spills r6 into its caller's SP+0 home slot. Keep the link at +4.
    a=Assembler(base);a.add_i(-8,3);st(a,4,3,31);st(a,0x9BC,0,0);prime(a)
    a.label('loop');a.mov_i(2,6);a.jal(0xFF38);a.jal(TIMER)
    cmpi(a,0,10);a.branch(0x4A,'done')
    ld(a,0x9BC,0,10);a.fmt_v(0x2D,3,10,10);a.branch(0x42,'loop')
    a.label('done');st(a,0x9BC,0,0);ld(a,4,3,31);a.add_i(8,3);ret(a)
    return a.finish()

def event_guard(base, syms):
    a=Assembler(base)
    a.store(0x34,4,3,10) # displaced opcode store, original interpreter frame
    a.fmt_v(0x2D,255,10,11);a.movea(0x58,0,12);a.reg(3,12,11)
    a.branch(0x49,'boundary') # end (FF) and reserved commands also disarm
    a.mov(11,12);a.imm5(0x15,5,12);a.imm5(0x14,2,12)
    a.load_address(syms.get('boundary_bits',0),13);a.reg(1,12,13)
    ld(a,0,13,12);a.reg(5,11,12);a.fmt_v(0x2D,1,12,12)
    a.branch(0x42,'done')
    a.label('boundary');jr(a,syms.get('reset',0));a.label('done');ret(a)
    return a.finish()

def boundary_bits(base, syms):
    return sum(1<<op for op in EVENT_BOUNDARIES).to_bytes(12,'little')

def script_call(base, syms):
    # Equivalent native opcode 17: preserve the return stack, then share
    # opcode 16's identical destination decoder. No event is bypassed.
    a=Assembler(base);st(a,0xB80,0,0);ld(a,0xB88,0,11)
    a.movea(0xAFC,0,12);a.mov(11,13);a.imm5(0x14,2,13);a.reg(1,13,12)
    ld(a,0xB7C,0,14);a.add_i(2,14);st(a,0,12,14)
    a.add_i(1,11);st(a,0xB88,0,11);jr(a,0x2C128)
    return a.finish()

def voice_wait(base, syms):
    # Native A734 with the same II-button cancellation / decoder cleanup.
    # An already active dialogue skip takes that same native cancel path;
    # this shared audio function never arms a skip in unrelated menus.
    a=Assembler(base);a.add_i(-8,3);st(a,4,3,31);st(a,0x9BC,0,0)
    a.branch(0x45,'check')
    a.label('loop');a.mov_i(2,6);a.jal(0xFF38)
    a.movhi(5,0,11);ld(a,(STATE+4)&65535,11,12);cmpi(a,1,12);a.branch(0x42,'cancel')
    ld(a,0x9BC,0,12);a.fmt_v(0x2D,2,12,12);a.branch(0x42,'check')
    a.label('cancel');a.load_address(0x57824,11);a.load(0x31,0,11,12)
    a.fmt_v(0x2D,0xFD,12,12);a.store(0x35,0,11,12);a.mov(11,6);a.jal(0x4D3E8)
    a.label('done');a.mov_i(1,10);st(a,0x9A4,0,10)
    ld(a,4,3,31);a.add_i(8,3);ret(a)
    a.label('check');ld(a,0x9A4,0,10);cmpi(a,0,10);a.branch(0x42,'loop');a.branch(0x45,'done')
    return a.finish()

def movie_gate(base, syms):
    # Called at DABA inside native decoder loop. The fifth arg is still at
    # decoder SP+54. r26 remains the native abort flag; cleanup is untouched.
    a=Assembler(base);ld(a,0x54,3,15);cmpi(a,1,15);a.branch(0x4A,'game')
    ld(a,0x7AD0,0,14);a.fmt_v(0x2D,0xFFF,14,14);a.branch(0x42,'done')
    a.mov_i(1,26);ret(a)
    a.label('game');pro(a);a.jal(TIMER);cmpi(a,0,10);a.branch(0x42,'restore')
    a.mov_i(1,26);a.label('restore');epi(a)
    a.label('done');ret(a)
    return a.finish()

def movie_enter(base, syms):
    # A held dialogue-skip must not automatically skip the following movie.
    # Release first, then a fresh hold can arm inside the native decoder.
    a=Assembler(base);a.mov(31,18);a.jal(syms.get('reset',0));a.mov(18,31)
    ld(a,0x40,3,15);ret(a) # displaced A88A load, no decoder SP change
    return a.finish()

def movie_exit(base, syms):
    a=Assembler(base);a.mov(10,25);a.jal(syms.get('reset',0))
    a.load_address(0xA8AA,31);jr(a,0x4CABC)
    return a.finish()

def fast_glyph(base, syms):
    a=Assembler(base);a.movhi(5,0,11);ld(a,(STATE+4)&65535,11,10);cmpi(a,1,10)
    a.branch(0x42,'done');jr(a,0x4E380);a.label('done');ret(a)
    return a.finish()

def condition_guard(base, syms):
    a=Assembler(base);st(a,0xC,3,13) # displaced F822, keep dictionary index
    a.addi(-0x1C,13,11);cmpi(a,1,11);a.branch(0x4B,'done')
    a.mov(12,18);a.mov(31,19);a.jal(syms.get('reset',0));a.mov(19,31);a.mov(18,12)
    a.label('done');ret(a)
    return a.finish()

def dialogue_wrapper(base, syms, choice=False):
    # Compact native 24C02/24BB6 without changing the audio bracketing.
    # Only opcode 02's caller may carry the latch to another dialogue.
    a=Assembler(base);a.add_i(-4,3);st(a,0,3,31)
    if choice:a.jal(syms.get('reset',0))
    a.movhi(7,0,11)
    if choice:a.mov_i(1,10);st(a,0xC6F0,11,10)
    else:st(a,0xC6F0,11,0)
    ld(a,0x69DC,0,10);a.addi(-99,10,10);cmpi(a,1,10);a.branch(0x43,'special')
    a.jal(0xC2A8);a.jal(0x247FE);a.jal(0xC3AC);a.branch(0x45,'finish')
    a.label('special');a.jal(0x247FE)
    a.label('finish');ld(a,0,3,31);a.add_i(4,3)
    if not choice:
        a.load_address(0x2B21C,11);a.reg(3,11,31);a.branch(0x42,'return')
        jr(a,syms.get('reset',0))
    a.label('return');ret(a)
    return a.finish()

def choice_wrapper(base, syms):return dialogue_wrapper(base,syms,True)

def choice_guard(base, syms):
    # Every native choice, including direct 247FE callers, disarms before
    # selection handling. RUN is never synthesized as a confirmation key.
    a=Assembler(base);a.mov(31,18);a.jal(syms.get('reset',0));a.mov(18,31);jr(a,0x24D6E)
    return a.finish()

def auto_wait(base, syms):
    # Preserve original timed-page behavior and poll only inside its wait.
    a=Assembler(base);pro(a,12);st(a,4,3,29);a.mov(6,29);prime(a)
    a.label('loop');a.mov_i(2,6);a.jal(0xFF38);a.jal(TIMER)
    cmpi(a,0,10);a.branch(0x4A,'done');a.add_i(-1,29);cmpi(a,1,29);a.branch(0x4F,'loop')
    a.label('done');ld(a,4,3,29);epi(a,12)
    return a.finish()

def visual_page(base, syms):
    # Compact the *existing* 204-byte helper, preserving its voice-free
    # behavior. The glyph bank immediately at +CC remains byte-exact.
    a=Assembler(base);a.add_i(-8,3);st(a,4,3,31)
    a.movhi(6,0,11);ld(a,0xA990,11,10);a.load_address(0x24556,12)
    a.reg(3,12,10);a.branch(0x42,'auto')
    st(a,0xAD70,11,0);st(a,0x9BC,0,0);a.mov_i(1,10);st(a,0xA58,0,10)
    a.load_address(0x12E88,6);a.jal(0xFDBC)
    a.movea(0x34,0,11);a.reg(0x0A,11,10);a.load_address(0x5AA48,11);a.reg(1,10,11)
    a.movhi(7,0,12);ld(a,0xC6F4,12,10);st(a,0,11,10)
    a.jal(0x4AA30);a.mov_i(1,10);a.movhi(6,0,11);st(a,0xAD70,11,10)
    st(a,0xA48,0,10);a.branch(0x45,'clear')
    a.label('auto');a.mov_i(1,10);st(a,0xA58,0,10)
    a.movhi(7,0,11);ld(a,0xC6EC,11,6);a.add_i(2,6);a.jal(syms.get('auto_wait',0))
    a.label('clear');st(a,0xA58,0,0);a.jal(0xF6C2)
    ld(a,4,3,31);a.add_i(8,3);ret(a)
    return a.finish()

def compile_code():
    syms={'timer':TIMER,'field_clear':0x245C2,'narration_clear':0x4AC24,'narration_wait':0x4AA30,'narration_title':0x4AA68}
    funcs={'timer':timer,'field_clear':field_clear,'narration_clear':narration_clear,'narration_wait':wait,'narration_title':narration_title}
    syms.update(dialogue_wrapper=0x24C02,choice_wrapper=0x24BB6,script_call=0x2C158,voice_wait=0xA734)
    funcs.update(dialogue_wrapper=dialogue_wrapper,choice_wrapper=choice_wrapper,script_call=script_call,voice_wait=voice_wait)
    assert len(voice_wait(0xA734,{}))<=0xA794-0xA734
    assert 0x24C02+len(dialogue_wrapper(0x24C02,{}))<=0x24C4A
    assert 0x4AA68+len(narration_title(0x4AA68,{}))==STATE
    # Reclaimed tails are past unconditional returns, not arbitrary zero RAM.
    pools=[[0x245C2+len(field_clear(0x245C2,{})),0x24682],
           [0x4AC24+len(narration_clear(0x4AC24,{})),0x4AD58],
           [0x24BB6+len(choice_wrapper(0x24BB6,{})),0x24C02],
           [0x2C158+len(script_call(0x2C158,{})),0x2C1A8]]
    resident={'reset':reset,'movie_gate':movie_gate,'movie_enter':movie_enter,'movie_exit':movie_exit,
              'fast_glyph':fast_glyph,'condition_guard':condition_guard,'event_guard':event_guard,
              'choice_guard':choice_guard,'boundary_bits':boundary_bits}
    for name,fn in sorted(resident.items(),key=lambda x:-len(x[1](0,{}))):
        n=len(fn(0,{}));align=4 if name=='boundary_bits' else 2
        fits=[p for p in pools if p[1]-((p[0]+align-1)&-align)>=n]
        assert fits,(name,n,pools)
        p=min(fits,key=lambda x:x[1]-x[0]);p[0]=(p[0]+align-1)&-align
        syms[name]=p[0];p[0]+=n;funcs[name]=fn
    syms['field_wait']=0x4AA30
    pos=0x1E9E00
    for name,fn in {'visual_page':visual_page,'auto_wait':auto_wait}.items():
        syms[name]=pos;pos+=len(fn(pos,{}));funcs[name]=fn
    assert pos<=0x1E9ECC,hex(pos)
    out={name:fn(syms[name],syms) for name,fn in funcs.items()}
    assert len(out['timer'])<=0x4C, len(out['timer'])
    assert len(out['narration_wait'])<=0x38,len(out['narration_wait'])
    return syms,out,pools

def plan(image):
    assert sha(image)==EXPECTED
    syms,code,pools=compile_code();writes=[]
    def main(at,data,name):
        for bias in (0,BIAS):
            off=bias+at-DELTA;writes.append((off,bytes(image[off:off+len(data)]),data,name+f'/{bias:X}'))
    # The discarded 55FB8 cave was observed being overwritten by startup
    # pointer initialization. Never change it, even if its disc bytes are 0.
    main(STATE,bytes(8),'run-hold-state')
    for name,data in code.items():
        if syms[name]<0x88000:main(syms[name],data,name)
    hooks={0x2450C:'field_wait',0x2456E:'auto_wait',0x2F0AC:'event_guard',
           0xA88A:'movie_enter',0xF516:'fast_glyph',0xF822:'condition_guard',0x24B60:'choice_guard'}
    for at,name in hooks.items():main(at,c.encode_jal(at,syms[name]),'hook/'+name)
    main(0xDABA,c.encode_jal(0xDABA,syms['movie_gate'])+c.encode_jump(0xDABE,0xDAD2,0x2A),'movie-native-abort-gate')
    main(0xA8A4,c.encode_jump(0xA8A4,syms['movie_exit'],0x2A)+bytes(2),'movie-exit-boundary')
    # Exact copies of the legacy 0A visual wait callsites, plus owned tail.
    import early_dialogue_font as font
    tails=font.resource12_tails(image);assert len(tails)==15
    for n,tail in enumerate(tails):
        start=tail+0x5E00;old=bytes(image[start:start+0x200]);data=bytearray(old)
        for name,b in code.items():
            if syms[name]>=0x1E9E00:
                at=syms[name]-0x1E9E00;data[at:at+len(b)]=b
        assert data[204:]==old[204:]
        writes.append((start,old,bytes(data),f'resource12/{n}'))
    writes.sort()
    for l,r in zip(writes,writes[1:]):assert l[0]+len(l[1])<=r[0],(l[3],r[3])
    return writes,dict(symbols={k:hex(v) for k,v in syms.items()},lengths={k:len(v) for k,v in code.items()},
        free_resident_tails=pools,hold_frames=HOLD_FRAMES,resource12_replicas=len(tails),experimental=True,
        event_boundary_opcodes=[f'{op:02X}' for op in sorted(EVENT_BOUNDARIES)],
        connected_dialogue_across_speakers_and_factions=True)

if __name__=='__main__':
    import json
    syms,out,pools=compile_code()
    print(json.dumps({'symbols':{k:hex(v) for k,v in syms.items()},'lengths':{k:len(v) for k,v in out.items()},'free':pools},indent=2))
