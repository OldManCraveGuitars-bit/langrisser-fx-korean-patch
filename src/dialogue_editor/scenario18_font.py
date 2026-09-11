"""Append one S18 syllable to the reserved, already resident 12x12 tail.

F9DC extends the existing final segment from +5FC6 by one 18-byte cell.
It occupies +5FEA..5FFC inside the owned +5F00..6000 reservation, after
all previous cells; no code moves and no old glyph changes. The only helper
change is its exclusive bound, with the matching router/dispatcher bounds.
"""
import json,struct
from dataclasses import replace
import hidden_x_font as old
import v810_profile_codec as isa
from korean_font_policy import unifont_dense_12,verify_sources,UNIFONT_SHA256
ROOT=old.ROOT
UPPER=0xF9DD
OFFSET=0x5FEA
need=old.need

def addition():
    rows=json.loads((ROOT/'dialogue_editor/scenario18_repair.json').read_bytes())['font_additions']
    need(rows=={'흥':'F9DC'},'S18 append-only glyph profile drift')
    return next(iter(rows)),int(next(iter(rows.values())),16)

def build_helper():
    raw=old.build_helper()
    ins=isa.decode(raw,4,old.font.atlas.TAIL_RAM+4)
    need(ins.opcode==0x28 and ins.immediate==old.UPPER and ins.low==10 and ins.high==10,'S18 original upper instruction')
    encoded=isa.encode(replace(ins,immediate=UPPER))
    need(len(encoded)==4,'S18 fixed instruction width')
    return raw[:4]+encoded+raw[8:]

def contract(raw):
    character,code=addition();prior=old.build_helper();checked=0
    need(raw[:4]==prior[:4] and raw[8:]==prior[8:],'S18 helper changed outside fixed bound')
    for lead in (*range(0x81,0xA0),*range(0xE0,0xFD)):
        for trail in range(0x40,0xFD):
            if trail==0x7F:continue
            value=lead*256+trail
            if value==code:continue
            pc,r=old.execute(raw,value);op,orr=old.execute(prior,value)
            need((pc,r[6])==(op,orr[6]),f'S18 changed previous glyph route {value:04X}')
            checked+=1
    pc,r=old.execute(raw,code)
    need(pc==old.font.atlas.GLYPH_RENDERER_RAM and r[6]==old.font.atlas.TAIL_RAM+OFFSET,'S18 new glyph destination')
    return {'unchanged_valid_glyph_routes':checked,'new_glyph':character,'code':hex(code),'ram':hex(r[6]),'bytes':18}

def mapping():return old.mapping()

def plan(source):
    verify_sources();character,code=addition();cell,meta=unifont_dense_12(character)
    need(len(cell)==18 and any(cell),'S18 missing/empty 12x12 glyph')
    writes,audit=old.plan(source);helper=build_helper();check=contract(helper)
    result=[]
    for at,before,after,owner in writes:
        if owner.startswith('hidden-x/font-helper/'):
            need(after==old.build_helper(),'S18 helper composition');after=helper
        elif owner.startswith('hidden-x/router/'):
            need(after==old.router.build(old.UPPER),'S18 router composition');after=old.router.build(UPPER)
        elif owner.startswith('hidden-x/dispatcher/'):
            expected=bytes.fromhex('6ba1')+struct.pack('<H',old.UPPER-old.font.HANDLER_BASE_VALUE)
            need(after==expected,'S18 dispatcher composition')
            after=bytes.fromhex('6ba1')+struct.pack('<H',UPPER-old.font.HANDLER_BASE_VALUE)
        result.append((at,before,after,owner))
    for i,tail in enumerate(old.font.resource12_tails(source)):
        at=tail+OFFSET
        need(source[at:at+18]==bytes(18) and OFFSET+18<=0x6000,'S18 reserved cell ownership')
        result.append((at,bytes(18),cell,f'scenario18/new-glyph/{i}'))
    return sorted(result),{**audit,'scenario18_append':check,'glyph_source':{
        'source_sha256':UNIFONT_SHA256,'cell':[12,12],'ink_bbox':meta.getbbox(),
        'encoded_sha256':old.base.sha(cell)},'replicas':15}

def verify(image):
    helper=build_helper();audit=contract(helper);cell,_=unifont_dense_12(addition()[0])
    for tail in old.font.resource12_tails(image):
        need(image[tail:tail+0x100]==helper,'S18 final helper')
        need(image[tail+OFFSET:tail+OFFSET+18]==cell,'S18 final appended cell')
        for c,code in old.ADDITIONS:
            first,end,offset=next(s for s in old.SEGMENTS if s[0]<=code<s[1])
            at=tail+offset+(code-first)*18
            need(image[at:at+18]==unifont_dense_12(c)[0],'S18 changed existing X glyph')
    return {**audit,**old.font.verify_final_router_contract(image)}
