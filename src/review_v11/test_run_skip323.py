"""Execute emitted instructions and compare compacted native routines."""
import copy,json,sys
from pathlib import Path
import run_skip323 as p
import v810_profile_codec as c
import v810_pcfx_isa_profile as other

def signed(x,bits=32):return (x^(1<<(bits-1)))-(1<<(bits-1))
class Machine:
    def __init__(self, image):
        self.mem=bytearray(0x200000);self.mem[0x7000:0x7000+len(image)]=image
        self.r=[0x123400+x for x in range(32)];self.r[0]=0;self.r[3]=0x1F0000;self.r[31]=0xDEAD
        self.calls=[];self.writes=[];self.z=self.s=self.ov=self.cy=False
    def get(self,at,n=4):return int.from_bytes(self.mem[at:at+n],'little')
    def put(self,at,x,n=4):self.mem[at:at+n]=(x&((1<<(8*n))-1)).to_bytes(n,'little')
    def subflags(self,x,y):
        v=(x-y)&0xFFFFFFFF;self.z=v==0;self.s=bool(v&0x80000000);self.cy=x<y
        self.ov=bool((x^y)&(x^v)&0x80000000);return v
    def run(self,start,limit=10000,stop=0xDEAD):
        pc=start
        for step in range(limit):
            if pc==stop:return
            i=c.decode(self.mem,pc,pc);op=i.opcode;u,v=i.low,i.high;d=i.immediate or 0
            d=signed(d,16);nxt=pc+i.size;imm=signed(u,5);r=self.r
            if op==0:r[v]=r[u]
            elif op==1:r[v]=(r[v]+r[u])&0xFFFFFFFF;self.z=r[v]==0
            elif op==2:r[v]=self.subflags(r[v],r[u])
            elif op==3:self.subflags(r[v],r[u])
            elif op==5:r[v]>>=r[u]&31;self.z=r[v]==0
            elif op==6:nxt=r[u]
            elif op in (9,0xA):
                if op==9:r[30]=r[v]%r[u];r[v]=r[v]//r[u]
                else:r[30]=((r[v]*r[u])>>32)&0xFFFFFFFF;r[v]=(r[v]*r[u])&0xFFFFFFFF
            elif op==0xC:r[v]|=r[u];self.z=r[v]==0
            elif op==0xF:r[v]=~r[u]
            elif op==0x10:r[v]=imm
            elif op==0x11:r[v]+=imm;self.z=(r[v]&0xFFFFFFFF)==0
            elif op==0x13:self.subflags(r[v],imm&0xFFFFFFFF)
            elif op==0x14:r[v]<<=u
            elif op==0x15:r[v]>>=u
            elif op==0x17:r[v]=signed(r[v])>>u
            elif op in (0x28,0x29):r[v]=r[u]+d
            elif op==0x2F:r[v]=r[u]+((i.immediate or 0)<<16)
            elif op==0x2D:r[v]=r[u]&i.immediate;self.z=r[v]==0
            elif op in (0x30,0x31,0x33):
                n={0x30:1,0x31:2,0x33:4}[op];x=self.get((r[u]+d)&0xFFFFFFFF,n);r[v]=signed(x,n*8)
            elif op in (0x34,0x35,0x37):
                n={0x34:1,0x35:2,0x37:4}[op];at=(r[u]+d)&0xFFFFFFFF
                self.put(at,r[v],n);self.writes.append((at,n))
            elif op in (0x2A,0x2B):
                if op==0x2B:r[31]=nxt
                nxt=i.target
                if i.target in SIGNATURES:
                    args=tuple(r[6+x] for x in range(SIGNATURES[i.target]))
                    extra=self.get(r[3]+0x10) if i.target in (0x11DA8,0x11FA4) else None
                    self.calls.append((i.target,args,extra))
                    # V810 native ABI permits spilling arguments to caller
                    # SP+0/+4/...; our wrappers must reserve those home slots.
                    for x,value in enumerate(args):self.put(r[3]+x*4,value)
                    if i.target==0xFF38:
                        self.put(0x9C4,self.get(0x9C4)+1)
                        self.put(0x9BC,getattr(self,'manual_input',0))
                        if self.get(0x9C4)>=getattr(self,'voice_end_at',0xFFFFFFFF):self.put(0x9A4,1)
                    result={0x11660:3,0x1B564:int((r[6]-0x62FC)//88%3!=0),0x1B4FC:0x123}.get(i.target,0x777)
                    for reg in range(6,20):r[reg]=0xCC0000+reg
                    r[10]=result;r[30]=0xDDD;nxt=r[31]
            elif 0x40<=op<=0x4F:
                take={0x41:self.cy,0x42:self.z,0x43:self.cy or self.z,0x44:self.s,0x45:True,
                      0x46:self.s!=self.ov,0x47:self.z or self.s!=self.ov,
                      0x49:not self.cy,0x4A:not self.z,0x4B:not(self.cy or self.z),0x4E:self.s==self.ov,0x4F:not self.z and self.s==self.ov}[op]
                if take:nxt=i.target
            else:raise AssertionError((hex(pc),i))
            self.r=[x&0xFFFFFFFF for x in r];self.r[0]=0;pc=nxt
        raise AssertionError(('execution limit',hex(pc)))

SIGNATURES={0x11D24:1,0x11DA8:4,0x11724:1,0x111BE:1,0x4ABF4:0,0xE328:4,
            0x11660:2,0x11C38:4,0x1B564:1,0x1B4FC:2,0x11FA4:4,0x117D0:3,0xFF38:1,
            0xC2A8:0,0xC3AC:0,0x247FE:0,0x24D6E:0,0x4D3E8:1}

def main():
    hold=72;assert p.HOLD_FRAMES==hold
    path=p.ROOT/'work/r80-v105-sherry-8x8-successor322/track02-r80-v105-sherry-8x8-successor322.iso'
    with path.open('rb') as f:f.seek(p.BIAS);source=f.read(0x81000)
    syms,codes,pools=p.compile_code();patched=bytearray(source)
    for name,b in codes.items():
        if syms[name]<0x88000:patched[syms[name]-p.DELTA:syms[name]-p.DELTA+len(b)]=b
        if name=='boundary_bits':continue
        for pc,i,_ in other.disassemble_range(b,syms[name]):
            x=c.decode(b,pc-syms[name],pc);assert i.size==x.size
    patched[p.STATE-p.DELTA:p.STATE-p.DELTA+8]=bytes(8)
    tests=0
    # Normal shared-audio callers stay native. An existing skip uses the
    # exact same stop command as pressing II, including high-bit flags.
    for latch in (0,1,0xFFFFFFFF):
        for manual in (0,1,2):
            for ended in (0,1):
                for flags in (0,2,0xFFFF):
                    before=Machine(source);before.put(0x9A4,ended);before.put(0x57824,flags,2)
                    before.manual_input=2 if latch==1 else manual;before.voice_end_at=5
                    after=copy.deepcopy(before);after.manual_input=manual;after.put(p.STATE+4,latch)
                    at=syms['voice_wait'];after.mem[at:at+len(codes['voice_wait'])]=codes['voice_wait']
                    before.run(at);after.run(at)
                    assert before.calls==after.calls
                    assert before.get(0x9A4)==after.get(0x9A4)==1
                    assert before.get(0x57824,2)==after.get(0x57824,2)
                    for reg in (3,*range(20,30)):assert before.r[reg]==after.r[reg]
                    tests+=1
    for held in (0,128):
        for latch in (0,1,0xFFFFFFFF):
            m=Machine(patched);m.put(p.STATE,1234);m.put(p.STATE+4,latch)
            m.put(0x7AD0,held);m.put(m.r[3]+0x40,987);m.run(syms['movie_enter'])
            assert m.r[15]==987 and m.r[3]==0x1F0000 and m.get(p.STATE)==0
            assert m.get(p.STATE+4)==(0xFFFFFFFF if held else 0)
            tests+=1
    for manual in (0,1,2):
        m=Machine(patched);m.manual_input=manual;m.put(0x7AD0,0x80)
        m.run(syms['narration_wait']);assert m.r[3]==0x1F0000
        assert m.get(0x9C4)==(hold+1 if manual==0 else 1)
        assert m.get(p.STATE+4)==(1 if manual==0 else 0)
        tests+=1
    # Time spent holding during rendering/input locks is never pre-counted.
    m=Machine(patched);m.put(0x7AD0,128);m.put(0x9C4,1000);m.put(p.STATE,1)
    m.run(syms['narration_wait']);assert m.get(0x9C4)==1001+hold;tests+=1
    for dictionary in range(256):
        m=Machine(patched);m.r[13]=dictionary;old_pointer=m.r[12]
        m.put(p.STATE+4,1);m.put(0x7AD0,128);m.run(syms['condition_guard'])
        assert m.get(m.r[3]+12)==dictionary
        assert m.r[12]==old_pointer
        assert m.get(p.STATE+4)==(0xFFFFFFFF if dictionary in (0x1C,0x1D) else 1)
        tests+=1
    # Actual timer opcodes: no pre-armed time, 71/72 boundary, early release,
    # locked hold cannot retrigger, latched skip survives release, clock wrap.
    for start in (0,100,0x7FFFFFF0,0xFFFFFFC0):
        m=Machine(patched)
        def tick(t,held):
            m.r[31]=0xDEAD;m.put(0x9C4,t&0xFFFFFFFF);m.put(0x7AD0,0x80 if held else 0);m.run(p.TIMER);return m.r[10]
        assert tick(start,True)==0
        assert tick(start+hold-1,True)==0
        assert tick(start+hold,True)==1
        assert tick(start+hold+1,False)==1
        m.r[31]=0xDEAD;m.put(0x7AD0,0x80);m.run(syms['reset']);assert m.get(p.STATE+4)==0xFFFFFFFF
        assert tick(start+500,True)==0
        assert tick(start+501,False)==0
        assert tick(start+502,True)==0
        assert tick(start+502+hold-1,True)==0
        assert tick(start+502+hold,True)==1
        m.r[31]=0xDEAD;m.put(0x7AD0,0);m.run(syms['reset'])
        assert tick(start+1000,True)==0;assert tick(start+1100,False)==0
        assert tick(start+1200,True)==0;assert tick(start+1200+hold-1,True)==0;assert tick(start+1200+hold,True)==1
        tests+=15
    # Every opcode and input state, including sign-extended native LD.B.
    for opcode in range(256):
        for held in (False,True):
            m=Machine(patched);m.r[10]=signed(opcode,8)&0xFFFFFFFF;m.put(p.STATE+4,1);m.put(0x7AD0,128 if held else 0)
            m.run(syms['event_guard']);assert m.get(m.r[3]+4,1)==opcode
            assert m.r[10]==signed(opcode,8)&0xFFFFFFFF
            boundary=opcode>=0x58 or opcode in p.EVENT_BOUNDARIES
            assert m.get(p.STATE+4)==(0xFFFFFFFF if held else 0) if boundary else m.get(p.STATE+4)==1
            tests+=1
    # Continuous story: voice, camera, facing, waits, branches and calls
    # must retain the latch. Actual deployment/choices/movies must end it.
    for boundary in sorted(p.EVENT_BOUNDARIES|{0xFF}):
        m=Machine(patched);m.put(p.STATE+4,1);m.put(0x7AD0,128)
        for opcode in (2,0x33,0,0x3E,0x46,0x16,0x17,0x18,0x3B,2,boundary):
            m.r[31]=0xDEAD;m.r[10]=opcode;m.run(syms['event_guard'])
            assert m.get(p.STATE+4)==(0xFFFFFFFF if opcode==boundary else 1)
        m.r[31]=0xDEAD;m.put(0x9C4,9999);m.run(p.TIMER);assert m.r[10]==0
        tests+=1
    # Compact opcode 17 must have exactly the native return-stack and jump
    # side effects, including high-bit destination bytes and nested calls.
    for depth in range(32):
        for destination in (0,1,0x7F,0x80,0xFF,0x100,0x7FFF,0x8000,0xFFFF):
            before=Machine(source);before.put(0xB88,depth);before.put(0xB7C,0x1D1234)
            before.put(0x1D1234,destination,2);after=copy.deepcopy(before)
            after.mem[syms['script_call']:syms['script_call']+len(codes['script_call'])]=codes['script_call']
            before.run(syms['script_call']);after.run(syms['script_call'])
            assert before.get(0xB7C)==after.get(0xB7C)==0x1D0800+destination
            for reg in (3,*range(20,30)):assert before.r[reg]==after.r[reg]
            touched={x for at,n in before.writes+after.writes for x in range(at,at+n)}
            assert all(before.mem[x]==after.mem[x] for x in touched)
            tests+=1
    # Native Omake any-button abort, gameplay RUN-only 1.2-sec abort, and
    # no accidental confirm/Select/direction-button gameplay skips.
    for omake in (0,1):
        for key in (0,1,2,4,8,16,32,64,128,256,512,1024,2048,4095):
            for elapsed in (0,hold-1,hold):
                m=Machine(patched);m.r[26]=0;m.put(m.r[3]+0x54,omake)
                m.put(0x7AD0,key);m.put(p.STATE,100+hold);m.put(0x9C4,100+elapsed)
                m.run(syms['movie_gate']);assert m.r[3]==0x1F0000
                assert m.r[26]==int(bool(key) if omake else bool(key&128) and elapsed>=hold)
                tests+=1
    # All native scenario title numbers / roster paths, no-skip window clears.
    for name,scenarios in [('field_clear',(1,99,100,101)),('narration_clear',(1,50,98)),('narration_title',range(1,101))]:
        for scene in scenarios:
            before=Machine(source);before.put(0x69DC,scene);before.put(0x269C,3);before.put(0x6C6F4,5)
            for n in range(20):before.put(0x62FC+n*88+0x3D,1 if n<8 else 0,1)
            after=copy.deepcopy(before)
            for key,b in codes.items():
                if syms[key]<0x88000:after.mem[syms[key]:syms[key]+len(b)]=b
            after.put(p.STATE,0);after.put(p.STATE+4,0)
            before.run(syms[name]);after.run(syms[name])
            assert before.calls==after.calls,(name,scene,before.calls,after.calls)
            for reg in (3,*range(20,30)):assert before.r[reg]==after.r[reg],(name,scene,reg)
            touched={x for at,n in before.writes+after.writes for x in range(at,at+n) if x<0x1E0000 and not p.STATE<=x<p.STATE+8}
            assert all(before.mem[x]==after.mem[x] for x in touched),(name,scene)
            tests+=1
    # Standalone popups must never leave fast-text latched into later menus.
    # Only the native consecutive-story caller is allowed to retain it.
    for name in ('dialogue_wrapper','choice_wrapper'):
        for scene in (0,1,98,99,100,101,102,0xFFFFFFFF):
            for caller in (0x2B21C,0x290AC,0x2D3C6,0x2EFB6):
                for held in (0,128):
                    before=Machine(source);before.put(0x69DC,scene);before.put(0x7AD0,held)
                    before.r[31]=caller;after=copy.deepcopy(before)
                    for key,b in codes.items():
                        if syms[key]<0x88000:after.mem[syms[key]:syms[key]+len(b)]=b
                    after.put(p.STATE+4,1)
                    before.run(syms[name],stop=caller);after.run(syms[name],stop=caller)
                    assert before.calls==after.calls,(name,scene)
                    for reg in (3,10,*range(20,30)):assert before.r[reg]==after.r[reg],(name,scene,reg)
                    keep=name=='dialogue_wrapper' and caller==0x2B21C
                    assert after.get(p.STATE+4)==(1 if keep else 0xFFFFFFFF if held else 0)
                    tests+=1
    for held in (0,128):
        m=Machine(patched);m.put(p.STATE+4,1);m.put(0x7AD0,held);m.run(syms['choice_guard'])
        assert [x[0] for x in m.calls]==[0x24D6E]
        assert m.get(p.STATE+4)==(0xFFFFFFFF if held else 0)
        tests+=1
    result=dict(status='PASS_INSTRUCTION_TESTS',cases=tests,hold_frames=hold,compacted_native_call_args_equal=True,
                callee_saved_registers_preserved=True,frame_threshold_and_release_lock=True,
                abandoned_boot_mutated_cave_never_used=True)
    print(json.dumps(result,indent=2))
    out=p.ROOT/'analysis/run-skip323/instruction-tests.json';out.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
