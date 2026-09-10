"""Repair the Holy Rod transfer's formatter inside its existing function.

No cave or extra resident allocation: shrink exact movhi-zero/movea pairs,
reuse three already-computed RAM addresses, and relocate original control flow.
Inventory effects and recipient selection remain equivalent; only dead volatile
registers differ at three joins. A finite differential runner checks these effects.
The
native transfer always installs item 14; the message nevertheless reads the
actual equipment field, not a literal Korean item name.
"""
from dataclasses import replace
import hashlib,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import v810_profile_codec as v
from build_deployment_menu_hook import Assembler
from muscle_temple_dialogue import MIRROR
from native_name_widths import installed_names

BEGIN,FORMAT,CONTINUE,END=0x2D0F8,0x2D368,0x2D3D0,0x2D3F8
DELTA=0x7000
need=lambda ok,msg: None if ok else (_ for _ in ()).throw(ValueError(msg))
sha=lambda b:hashlib.sha256(b).hexdigest().upper()

def mask():
    # F8E6 / E14C: default player=0; table name i uses parameter i+2.
    result=bytearray(10);audit=[]
    for i,(name,raw,width) in enumerate(installed_names()):
        final=name.strip()[-1]
        need('가'<=final<='힣','Unresolved final syllable: '+name)
        consonant=(ord(final)-0xAC00)%28!=0
        for param in ([0,2] if i==0 else [i+2]):
            if consonant:result[param//8]|=1<<(param%8)
        audit.append({'name_id':i,'name':name,'parameter':i+2,
                      'particle':'이' if consonant else '가','width':width})
    return bytes(result),audit

def formatter(base,template_address,mask_address):
    a=Assembler(base)
    a.load(0x30,0x37,28,6);a.fmt_v(0x2D,255,6,6);a.jal(0xF8E6)
    a.mov(10,26);a.mov(10,7)
    # Native raw02 rule: zero parameter selects the player-name buffer.
    a.movea(0xC5C,0,10);a.imm5(0x13,0,7);a.branch(0x42,'name')
    a.mov_i(1,6);a.jal(0xE14C)
    a.label('name')
    a.movea(0x2470,0,27);a.mov_i(8,11);a.store(0x34,0,27,11);a.add_i(1,27)
    a.jal('copy')
    a.mov(26,6);a.imm5(0x15,3,6)
    a.movhi((mask_address+0x8000)>>16,6,7)
    a.load(0x30,mask_address&0xFFFF,7,10)
    a.fmt_v(0x2D,7,26,6);a.reg(0x05,6,10);a.fmt_v(0x2D,1,10,10)
    a.movea(0x45,0,11);a.branch(0x42,'particle');a.movea(0x82,0,11)
    a.label('particle')
    a.movea(0xF0,0,12);a.store(0x34,0,27,12);a.store(0x34,1,27,11)
    a.mov_i(8,11);a.store(0x34,2,27,11);a.add_i(3,27)
    # Native producer has just assigned item14, a positive signed byte.
    a.mov_i(2,6);a.load(0x30,0x38,28,7);a.add_i(-1,7);a.jal(0xE14C)
    a.jal('copy')
    a.load_address(template_address,10);a.jal('copy');a.branch(0x45,'done')
    # Trim only transient trailing F1E6/F1E8 cells, never source records.
    # Byte accesses are intentional: the initial newline makes text unaligned.
    a.label('copy')
    a.load(0x30,0,10,11);a.store(0x34,0,27,11)
    a.imm5(0x13,0,11);a.branch(0x42,'trim')
    a.add_i(1,10);a.add_i(1,27);a.branch(0x45,'copy')
    a.label('trim')
    a.load(0x30,-2,27,11);a.imm5(0x13,-15,11);a.branch(0x4A,'return')
    a.load(0x30,-1,27,11);a.addi(26,11,11);a.branch(0x42,'blank')
    a.add_i(-2,11);a.branch(0x4A,'return')
    a.label('blank');a.add_i(-2,27);a.branch(0x45,'trim')
    a.label('return');a.store(0x34,0,27,0);a.reg(0x06,31,0)
    a.label('done')
    return a.finish()

def assemble(original):
    need(len(original)==END-BEGIN,'Native function extent')
    instructions={};pc=BEGIN
    while pc<END:
        ins=v.decode(original,pc-BEGIN,pc)
        need(v.encode(ins)==original[pc-BEGIN:pc-BEGIN+ins.size],'Native codec roundtrip')
        instructions[pc]=ins;pc+=ins.size
    # Only these adjacent pairs change: both instructions leave flags alone,
    # and their final register values equal a single sign-safe movea.
    # 2D1E4: r17 already equals 6A6A+2*r29; r10/r11 are dead at 2D202.
    # 2D2FA: r10 already equals 62FC+58*r29; r10/14/15/16/17/19 are
    # dead before reuse on BOTH outgoing loop edges. Keep r12/r18 results.
    reuse1=Assembler(0);reuse1.store(0x34,0,17,0)
    reuse2=Assembler(0);reuse2.movea(0x22,0,18);reuse2.store(0x34,0x3C,10,18)
    reuse2.load(0x30,0x37,28,12);reuse2.store(0x34,0x3E,10,12)
    # 2D25A: r14 already equals 6A6A+2*r29; r10/r19 are dead at 2D280.
    reuse3=Assembler(0);reuse3.movea(255,0,11);reuse3.store(0x34,1,14,11)
    replacements={0x2D1E4:(0x2D1F6,reuse1.finish()),0x2D2FA:(0x2D328,reuse2.finish()),
                  0x2D25A:(0x2D270,reuse3.finish()),0x2D2F0:(0x2D2F4,b'')}
    # AND FF followed immediately by AND 0C equals just AND 0C,
    # including its final flags, for either sign-extended input.
    units=[];skipped=set();compacted=0;pc=BEGIN
    while pc<END:
        if pc==FORMAT:
            units.append((pc,'formatter',None));pc=CONTINUE;continue
        if pc in replacements:
            end,chunk=replacements[pc]
            units.append((pc,'reuse',chunk))
            skipped.update(q for q in instructions if pc<q<end)
            pc=end;continue
        ins=instructions[pc];next_ins=instructions.get(pc+ins.size)
        if (ins.opcode==0x2F and ins.low==0 and ins.immediate==0 and next_ins
            and next_ins.opcode==0x28 and next_ins.low==ins.high==next_ins.high
            and next_ins.immediate<0x8000):
            units.append((pc,'compact',replace(next_ins,low=0)))
            skipped.add(pc+4);pc+=8;compacted+=1
        else:units.append((pc,'native',ins));pc+=ins.size
    for old,ins in instructions.items():
        if ins.target is not None and not FORMAT<=old<CONTINUE:
            need(ins.target not in skipped,'Branch into compacted pair')
            need(not FORMAT<ins.target<CONTINUE,'Branch into retired formatter')
    sizes={'formatter':len(formatter(0,0,0))}
    locations={};pc=BEGIN
    for old,kind,ins in units:
        locations[old]=pc
        pc+=sizes['formatter'] if kind=='formatter' else len(ins) if kind=='reuse' else ins.size
    code_end=pc
    template=bytes.fromhex('F04808F043F0E4F1E3F08DF1BA00')
    # F045=가, F048=를 in the resident legacy charset, not shop glyphs.
    charset=json.loads((ROOT/'analysis/hangul_charset_v342-r77-faction-unit-description-nul-safe.json').read_bytes())
    cm={row['character']:int(row['code'],0).to_bytes(2,'big') for row in charset['mappings']}
    need(template==cm['를']+b'\x08'+b''.join(cm[c] for c in '장비했다.')+b'\0','Template resident glyph ownership')
    need(cm['가']==bytes.fromhex('F045'),'Vowel particle ownership')
    need(cm['이']==bytes.fromhex('F082'),'Subject-particle glyph ownership')
    bits,names=mask();data=template+bits
    need(code_end+len(data)<=END,f'In-function storage overflow: {code_end+len(data)-END}')
    out=bytearray();rows=[]
    for old,kind,ins in units:
        pos=BEGIN+len(out)
        if kind=='formatter':chunk=formatter(pos,code_end,code_end+len(template))
        elif kind=='reuse':chunk=ins
        elif ins.target is not None:
            target=locations.get(ins.target,ins.target)
            chunk=v.encode(replace(ins,displacement=target-pos,target=target))
        else:chunk=v.encode(ins)
        out.extend(chunk);rows.append({'before_pc':hex(old),'after_pc':hex(pos),'kind':kind,'bytes':len(chunk)})
    need(BEGIN+len(out)==code_end,'Code extent')
    starts=set();branches=[];pos=0;dis=[]
    while pos<len(out):
        ins=v.decode(out,pos,BEGIN+pos);need(v.encode(ins)==out[pos:pos+ins.size],'Final ISA roundtrip')
        starts.add(BEGIN+pos)
        if ins.target is not None:branches.append(ins.target)
        dis.append({'pc':hex(BEGIN+pos),'asm':v.format_instruction(ins)})
        pos+=ins.size
    need(all(t in starts for t in branches if BEGIN<=t<END),'Final branch/data boundary')
    out.extend(data);out.extend(bytes(END-BEGIN-len(out)))
    return bytes(out),{'code_end':hex(code_end),'template':template.hex(),'mask':bits.hex(),
        'compacted_pairs':compacted,'address_reuse_blocks':3,'redundant_mask_removed':1,
        'relocation':rows,'disassembly':dis,'names':names,
        'storage':'retired bytes inside the same native function; no new RAM owner',
        'scope':'native item-14 transfer; actual recipient selected by unchanged game code',
        'custom_renamed_player_particle_verified':False}

def plan(image,original=None):
    before=bytes(image[BEGIN-DELTA:END-DELTA])
    need(sha(before)=='7609932903A571B7D558E97DD173EE817B0B96F28A146D1B976CB30AFC29BB84','Pinned native function preimage')
    # Immutable Japanese function, including literal item14 and parameter13.
    if original:
        from scenario_dialogue_review import read_cooked
        need(read_cooked(original,BEGIN-DELTA,len(before))==before,'Native function not immutable Japanese')
    need(before[0x2D348-BEGIN:0x2D34E-BEGIN]==bytes.fromhex('8E419CD13800'),'Native item14 assignment')
    after,audit=assemble(before);writes=[]
    for bias in (0,MIRROR):
        off=bias+BEGIN-DELTA
        need(image[off:off+len(before)]==before,'Native executable mirror differs')
        writes.append((off,before,after,f'event-equipment-formatter/mirror/{bias:X}'))
    audit.update(before_sha256=sha(before),after_sha256=sha(after),replicas=2)
    return writes,audit

def verify(source,target,original):
    writes,audit=plan(source,original)
    for off,old,new,owner in writes:need(target[off:off+len(new)]==new,owner+' final bytes')
    audit['verified_after_last_writer']=True
    return audit
