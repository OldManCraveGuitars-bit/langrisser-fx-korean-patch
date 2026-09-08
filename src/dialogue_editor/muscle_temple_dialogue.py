"""Hidden resource 71 dialogue; bounded, lossless, non-distribution review input.

The user's scenario-22 save loads native field ID 0x47 at RAM 0x1A0000.
E14C selects section/one-based NUL ordinal; it does not retain old per-record
offsets. Section 4 remains 241 dictionary rows, section 5 remains 87 records.
Only unreferenced high dictionary rows are reclaimed by the established local
allocator. Existing glyph owners, section offsets and all script code survive.
"""
from pathlib import Path
import hashlib
import json
import re
import struct

import dialogue_core as dialogue
import early_dialogue_font as font
import presentation_dictionary as dictionary
import resource12_router as router
import v810_profile_codec as v810
import build_successor252_item_font_runtime_safe as safe_font
import dialogue_continuation_resident as continuation
from build_deployment_menu_hook import Assembler
from build_r80_successor204_resource12_unifont_all_successor205 import rows_and_bank
from korean_font_policy import verify_sources, unifont_dense_12, UNIFONT_SHA256

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / 'dialogue_editor/muscle_temple_dialogue_successor278.json'
SOURCE = ROOT / 'analysis/muscle-temple-source-original-277.json'
HEADER = 0x3104F0
SECTIONS = (0x310514,0x310BB4,0x310EA0,0x3119F0,0x3134FC,
            0x313D98,0x3149A4,0x3149BC,0x314AAC)
SOURCE_SHA = '1C28B77EBC4BD2937DABAC181FCA3266744043ACA53DE7BCE017873277FDBBA7'
DICTIONARY_SHA = 'ADAACCF3F09E76FD8141EBA861C65A447C37615AB26961AD348275F305D9DC14'
SELECTOR = bytes.fromhex(
    '63a4ecffc3dc1400e3dc1800e3df100063df0c0083df0800a3df0400c24000ac4255'
    'aa035d0163cd140062514b058acd00009d038c076003148adc018147eec10000efb5'
    'ff00e04df295614723ce18003f46710fe68d5c01e3cf100063cf0c0083cf0800a3cf'
    '040063a414001f18')
MIRROR = 0x277DB000
# Append-only code ownership. Never re-sort or renumber existing assignments.
ADDITIONS = tuple(zip('곰뗌랫센쇳씰엎윗읍쥬핥', range(0xF9C7,0xF9D2)))
# The ordinary atlas ends at 4D84, immediately followed by the LIVE F8 clone.
# Header 124..200 belongs to condition_resident. Neither is free. Suballocate
# the reserved continuation tail only AFTER its pinned 204-byte code (5E00..5ECC).
# Its former inert 5F00..6000 tail supplies 256 bytes; code/dispatch stay exact.
NEW_GLYPH_OFFSET = 0x5F00
# Storage-only phrases; expansion must reproduce the exact authored bytes.
PHRASES = ('세계멸망광선','시겠습니까?','포인트 상승했다!',
           '몸을 더 단련하란 말이다!','사람 모양 부조','이젠 안 되겠어',
           '‥‥.','형니임!','손에 넣었다!','‥‥틀렸다‥‥','부조가 침묵했다.')
need = dialogue.need


def sha(data):
    return hashlib.sha256(data).hexdigest().upper()


def mapping_and_font():
    verify_sources()
    old_rows, old_bank = rows_and_bank()
    need(old_rows[-1][1] == 0xF9C6, 'Current atlas ownership boundary changed')
    mapping = dialogue.with_native_ascii(dialogue.all_dialogue_private_mapping())
    for character, code in old_rows:
        mapping.setdefault(character, code.to_bytes(2,'big'))
    for character, code in ADDITIONS:
        need(character not in mapping and code.to_bytes(2,'big') not in mapping.values(),
             f'New glyph owner collision: {character}')
        mapping[character] = code.to_bytes(2,'big')
    new_bank = b''.join(unifont_dense_12(c)[0] for c,_ in ADDITIONS)
    need(len(new_bank)==len(ADDITIONS)*18 and all(any(new_bank[n:n+18])
         for n in range(0,len(new_bank),18)), 'Missing new font cell')
    return mapping, old_rows, old_bank, new_bank


def split_rows(raw, count):
    rows=[]; cursor=0
    for _ in range(count):
        end=raw.find(b'\0',cursor)
        need(end>=0,'Unterminated native ordinal')
        rows.append(raw[cursor:end]); cursor=end+1
    need(not any(raw[cursor:]), 'Unexpected native pool tail')
    return rows


def expand(raw, rows):
    """Independent token walker; dictionary output is literal, never recursive."""
    out=bytearray(); cursor=0
    while cursor<len(raw):
        value=raw[cursor]
        if value==4:
            need(cursor+1<len(raw) and 1<=raw[cursor+1]<=241,'Dictionary token')
            payload=rows[raw[cursor+1]-1]
            need(payload and not dictionary._references(payload),'Nested/empty phrase')
            out.extend(payload); cursor+=2
        elif value==9 or value==6 or 0x81<=value<=0x9F or 0xE0<=value<=0xFC:
            need(cursor+1<len(raw),'Truncated native token/glyph')
            if value==6: need(raw[cursor+1]==7,'Unknown page command')
            out.extend(raw[cursor:cursor+2]); cursor+=2
        else:
            need(value in (2,8,0x20,0x21),'Unexpected unpaired native byte')
            out.append(value); cursor+=1
    return bytes(out)


def draft_records(mapping):
    document=json.loads(DRAFT.read_text(encoding='utf8'))
    source=json.loads(SOURCE.read_text(encoding='utf8'))
    need(document['schema']=='langrisser-fx-hidden-dialogue-translation/v1'
         and document['status']=='needs_human_review' and document['non_distribution'] is True,
         'Only explicit non-distribution review input is eligible')
    need(document['source_dialogue_sha256']==SOURCE_SHA
         and source['original_dialogue_sha256']==SOURCE_SHA,'Translation source identity')
    records=document['records']; expected=[r['id'] for r in source['records']]
    need(list(records)==expected and len(records)==87,'Hidden dialogue population/order')
    need(sha(b''.join(bytes.fromhex(r['raw_hex']) for r in source['records']))==SOURCE_SHA,
         'Protected source records changed')
    plains=[]; layouts=[]
    for original in source['records']:
        key=original['id']; text=records[key]
        need(not dialogue._unknown_tokens(text),f'{key}: unknown token')
        pages=text.split('{page}')
        original_pages=original['expanded_text'].split('\f')
        need(len(pages)==len(original_pages),f'{key}: original page count changed')
        for old,new in zip(original_pages,pages):
            tokens=lambda s: re.findall(r'\{(?:name|raw):[0-9A-Fa-f]{2}\}',s)
            need(tokens(old)==tokens(new),f'{key}: dynamic-name/control sequence changed')
        need(bool(text)==bool(original['raw_hex']!='00'),f'{key}: empty/nonempty record changed')
        layout=dialogue.portrait_layout_inspection(text)
        need(not layout['failures'],f"{key}: {layout['failures']}")
        raw,missing=dialogue.encode_plain(text,mapping)
        need(not missing and b'\0' not in raw,f'{key}: missing glyph or NUL {missing}')
        plains.append(raw); layouts.append({'id':key,**layout})
    return records, plains, layouts


def build_helper():
    a=Assembler(font.atlas.TAIL_RAM)
    a.load_address(ADDITIONS[-1][1]+1,10)
    a.reg(3,10,6); a.branch(0x4E,'original')
    a.load_address(ADDITIONS[0][1],11)
    a.reg(3,11,6); a.branch(0x4E,'new_cells')
    a.mov(6,10); a.imm5(0x15,8,10)
    for lead in safe_font.LEADS:
        a.movea(lead,0,11); a.reg(3,11,10); a.branch(0x42,f'lead_{lead:X}')
    a.branch(0x45,'original')
    for page,lead in enumerate(safe_font.LEADS):
        a.label(f'lead_{lead:X}')
        address=(safe_font.F8_SAFE_RAM if lead==0xF8 else
                 font.atlas.TAIL_RAM+0x200+page*safe_font.PAGE_BYTES)
        a.load_address(address,10); a.branch(0x45,'trail')
    a.label('new_cells')
    a.load_address(font.atlas.TAIL_RAM+NEW_GLYPH_OFFSET,10)
    a.fmt_v(0x2D,0xFF,6,6); a.addi(-(ADDITIONS[0][1]&255),6,6)
    a.branch(0x45,'index_ready')
    a.label('trail')
    a.fmt_v(0x2D,0xFF,6,6); a.addi(-0x40,6,6)
    a.movea(0x40,0,11); a.reg(3,11,6); a.branch(0x46,'index_ready')
    a.add_i(-1,6)
    a.label('index_ready')
    a.mov(6,11); a.imm5(0x14,4,6); a.imm5(0x14,1,11)
    a.reg(1,11,6); a.reg(1,10,6)
    a.code.extend(font.atlas.encode_jr(a.pc,font.atlas.GLYPH_RENDERER_RAM))
    a.label('original')
    a.load_address(0x10000,10); a.movea(0xF040,10,10)
    a.code.extend(font.atlas.encode_jr(a.pc,font.atlas.ORIGINAL_THIRD_RAM))
    raw=a.finish(); need(len(raw)<=0x100,'Font helper capacity')
    cursor=0
    while cursor<len(raw):
        ins=v810.decode(raw,cursor,0x1E4000+cursor)
        need(v810.encode(ins)==raw[cursor:cursor+ins.size],'V810 helper round trip')
        cursor+=ins.size
    return raw.ljust(0x100,b'\0')


def helper_result(raw,character):
    """Bounded semantics, decoded by the project's full PC-FX ISA profile."""
    r=[0]*32; r[6]=character; pc=0x1E4000; comparison=0
    signed=lambda x: x if x<0x80000000 else x-0x100000000
    for _ in range(128):
        if not 0x1E4000<=pc<0x1E4100:return pc,r
        ins=v810.decode(raw,pc-0x1E4000,pc); op=ins.opcode
        lo,hi=ins.low,ins.high
        imm=ins.immediate
        simm=None if imm is None else (imm if imm<0x8000 else imm-0x10000)
        if op==0x2F:r[hi]=(r[lo]+(imm<<16))&0xFFFFFFFF
        elif op in (0x28,0x29):r[hi]=(r[lo]+simm)&0xFFFFFFFF
        elif op==0x2D:r[hi]=r[lo]&imm
        elif op==0:r[hi]=r[lo]
        elif op==1:r[hi]=(r[hi]+r[lo])&0xFFFFFFFF
        elif op==3:comparison=signed(r[hi])-signed(r[lo])
        elif op==0x11:r[hi]=(r[hi]+(lo if lo<16 else lo-32))&0xFFFFFFFF
        elif op==0x14:r[hi]=(r[hi]<<lo)&0xFFFFFFFF
        elif op==0x15:r[hi]>>=lo
        elif op==0x2A:pc=ins.target;continue
        elif op in (0x42,0x45,0x46,0x4E):
            take=(op==0x45 or op==0x42 and comparison==0
                  or op==0x46 and comparison<0 or op==0x4E and comparison>=0)
            if take:pc=ins.target;continue
        else:raise ValueError(f'Unexpected helper operation {ins}')
        r[0]=0; pc+=ins.size
    raise ValueError('Font helper did not terminate')


def helper_contract(raw,old_rows):
    for _character,code in old_rows:
        pc,r=helper_result(raw,code)
        expected=font.atlas.TAIL_RAM+safe_font.code_cell_offset(code,safe_font.F8_SAFE_OFFSET)
        need(pc==font.atlas.GLYPH_RENDERER_RAM and r[6]==expected,f'Existing glyph route {code:X}')
    for i,(_character,code) in enumerate(ADDITIONS):
        pc,r=helper_result(raw,code)
        need(pc==font.atlas.GLYPH_RENDERER_RAM
             and r[6]==font.atlas.TAIL_RAM+NEW_GLYPH_OFFSET+i*18,f'New glyph route {code:X}')
    for code in (0xF3FC,ADDITIONS[-1][1]+1,0xFA00):
        pc,r=helper_result(raw,code)
        need(pc==font.atlas.ORIGINAL_THIRD_RAM and r[6]==code,'Font fallback/live state')


def plan(image):
    need(tuple(HEADER+n for n in struct.unpack_from('<9I',image,HEADER))==SECTIONS,
         'Resource 71 section addresses changed')
    for bias in (0,MIRROR):
        need(image[bias+0x714C:bias+0x714C+len(SELECTOR)]==SELECTOR,'Native ordinal consumer changed')
    need(sha(image[SECTIONS[5]:SECTIONS[6]])==SOURCE_SHA,'Resource 71 source dialogue changed')
    need(sha(image[SECTIONS[4]:SECTIONS[5]])==DICTIONARY_SHA,'Resource 71 dictionary changed')
    mapping,old_rows,old_bank,new_bank=mapping_and_font()
    records,plains,layouts=draft_records(mapping)
    resource=dictionary.locate_resource(image,SECTIONS[7],allow_authored_title=True)
    payloads=tuple((p,dialogue.encode_plain(p,mapping)[0]) for p in PHRASES)
    dplan=dictionary.build_dictionary_plan(image,resource,payloads)
    phrases=dict(dplan.assignments)
    encoded=[dialogue.encode_compressed(dialogue.engine_text(t),mapping,phrases,
             SECTIONS[6]-SECTIONS[5],prefer_parity=False)[0] for t in records.values()]
    pool=b''.join(r+b'\0' for r in encoded)
    need(len(pool)<=SECTIONS[6]-SECTIONS[5],'Hidden dialogue pool overflow')
    packed=pool.ljust(SECTIONS[6]-SECTIONS[5],b'\0')
    need(split_rows(packed,87)==encoded,'Native ordinal repack round trip')
    drows=dictionary._split_dictionary(dplan.replacement)
    need([expand(r,drows) for r in encoded]==plains,'Lossless dictionary expansion failed')
    for code in dplan.preserved_codes:
        need(drows[code-1]==resource.dictionary_rows[code-1],f'Protected dictionary {code}')
    writes=[]
    def put(offset,before,after,owner):
        need(len(before)==len(after) and image[offset:offset+len(before)]==before,owner+' preimage')
        writes.append((offset,before,after,'muscle-temple/'+owner))
    put(SECTIONS[4],image[SECTIONS[4]:SECTIONS[5]],dplan.replacement,'local-dictionary')
    put(SECTIONS[5],image[SECTIONS[5]:SECTIONS[6]],packed,'dialogue-pool')
    before_helper=safe_font.build_helper(safe_font.F8_SAFE_RAM)
    after_helper=build_helper()
    helper_contract(after_helper,old_rows)
    old_upper=old_rows[-1][1]+1; upper=ADDITIONS[-1][1]+1
    route_before=router.build(old_upper); route_after=router.build(upper)
    router.verify(route_after,upper)
    glyph_offset=NEW_GLYPH_OFFSET
    need(continuation.OFFSET+continuation.HELPER_BYTES<=glyph_offset
         and glyph_offset+len(new_bank)<=continuation.OFFSET+continuation.SPAN,
         'New cells overlap continuation code or exceed its reserved tail')
    for i,tail in enumerate(font.resource12_tails(image)):
        need(image[tail+0x200:tail+0x200+len(old_bank)]==old_bank,'Existing glyph atlas changed')
        need(sha(image[tail+continuation.OFFSET:tail+continuation.OFFSET+continuation.HELPER_BYTES])
             ==continuation.HELPER_SHA256,'Continuation reserved-tail owner changed')
        need(image[tail:tail+len(before_helper)]==before_helper,'Existing helper changed')
        put(tail,before_helper,after_helper,f'helper/{i}')
        put(tail+0x100,route_before,route_after,f'router-bound/{i}')
        put(tail+glyph_offset,bytes(len(new_bank)),new_bank,f'new-glyphs/{i}')
    for bias in (0,MIRROR):
        instruction=lambda n: bytes.fromhex('6BA1')+struct.pack('<H',n-font.HANDLER_BASE_VALUE)
        put(bias+font.HANDLER_COOKED+font.HANDLER_UPPER_MOVEA_OFFSET,
            instruction(old_upper),instruction(upper),f'dispatcher-bound/{bias:X}')
    writes.sort()
    for a,b in zip(writes,writes[1:]):need(a[0]+len(a[1])<=b[0],'Overlapping hidden writers')
    return writes,{'status':'NON_DISTRIBUTION_TRANSLATION_REVIEW','records':87,
        'translated_nonempty_records':86,'dialogue_bytes':len(pool),'dialogue_capacity':len(packed),
        'original_source_sha256':SOURCE_SHA,'draft_sha256':sha(DRAFT.read_bytes()),
        'new_glyphs':[{'character':c,'code':f'{n:04X}'} for c,n in ADDITIONS],
        'existing_glyphs_preserved_per_replica':len(old_rows),'font_sha256':UNIFONT_SHA256,
        'dictionary_assignments':list(dplan.assignments),'dictionary_cleared_codes':dplan.cleared_codes,
        'dictionary_preserved_codes':dplan.preserved_codes,'dictionary_packed_bytes':dplan.packed_bytes,
        'layouts':layouts,'section_offsets_changed':False,'original_page_and_name_tokens_preserved':True}


def verify(image, *, condition_section7=None, font_profile=None):
    mapping,old_rows,old_bank,new_bank=mapping_and_font()
    records,plains,_=draft_records(mapping)
    expected_sections=list(SECTIONS)
    if condition_section7 is not None:
        import muscle_temple_conditions as conditions
        conditions.verify(image)
        need(condition_section7==SECTIONS[7]+12,'Undeclared condition extension')
        expected_sections[7]=condition_section7
    need(tuple(HEADER+n for n in struct.unpack_from('<9I',image,HEADER))==tuple(expected_sections),'Final resource header')
    drows=dictionary._split_dictionary(image[SECTIONS[4]:SECTIONS[5]])
    rows=split_rows(image[SECTIONS[5]:SECTIONS[6]],87)
    need([expand(r,drows) for r in rows]==plains,'Final dialogue text/control bytes differ')
    final_helper=build_helper() if font_profile is None else font_profile.build_helper()
    if font_profile is None:
        helper_contract(final_helper,old_rows)
    else:
        # The append-only profile proves every old valid glyph route,
        # including the eleven resource-71 additions, before final reads.
        font_profile.contract(final_helper)
    for tail in font.resource12_tails(image):
        need(image[tail:tail+len(final_helper)]==final_helper,'Final helper')
        need(image[tail+0x200:tail+0x200+len(old_bank)]==old_bank,'Final old font bytes')
        need(image[tail+NEW_GLYPH_OFFSET:tail+NEW_GLYPH_OFFSET+len(new_bank)]==new_bank,'Final new font bytes')
    return {'records_decoded':len(rows),'lossless_plain_byte_comparison':True,
            'existing_cells_preserved':len(old_rows)*15,'new_cells':len(ADDITIONS)*15,
            'router':font.verify_final_router_contract(image)}
