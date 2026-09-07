"""Normalize semantic Hangul owners, including legacy PUA and split words.

Codes, text records, widths, native instructions, and non-Hangul pixels are
immutable. Both MAIN copies share these fonts. Do not use a Unicode-only
manifest filter: four active name cells still carry historical PUA labels.
"""
from pathlib import Path
import hashlib,json,struct
from PIL import Image

from build_dense_charset_engine import dense_index
from korean_font_policy import unifont_cell_12,unifont_dense_12,verify_sources,UNIFONT_SHA256
from materialize_charset_glyphs import pack_cell
from native_name_widths import installed_names,FIRST_NAME_TABLE,REPLICAS

ROOT=Path(__file__).resolve().parents[1]
MIRROR=0x277DB000
CHARSET=ROOT/'analysis/hangul_charset_v342-r77-faction-unit-description-nul-safe.json'
CHARSET_SHA='9b48122f8c7ea06a065a9a7ff175a6cc5df14754eba2f9d41c3be60e86dd928e'
ALIASES=ROOT/'analysis/glyph_aliases_poc_v62.json'
ALIASES_SHA='4bb9185e6acf98320600adbd81776169b14d106bdfc267f7262e1a4128046a7a'
BANKS=((0x47384,405*18,'7878f87aa746aa6393b382e2d8c04824079f142e5d9ea4d52f4dfc9d742f8ffc'),
       (0x4F080,0x64E,'0036c749457203a737af6eb4e4cb5a7ce67065d628f7fa43480cc69469b190ff'))
# Adopted reclaimed-name specification and packed 78-name sequence agree.
RECLAIMED={0xF16F:'폴',0xF170:'돈',0xF171:'삼',0xF172:'손',0xF17D:'란'}
PACKED=dict(zip(range(0xF2AC,0xF2B3),'갈기남란밀탄눌'))
EXPECTED_BAD_FULL={0xF16F,0xF170,0xF171,0xF172,0xF17D,*PACKED}
# Remaining live PUA fragments: source words were split at a fixed 8px lead.
# Numeric fragments/columns must retain their native appearance.
FRAGMENTS={
    0xF180:'000003000001001007000001003003001000',
    0xF181:'000e802832800c1e82083f00187180f00000',
    0xF182:'000840f40040c40240e40040f40840840000',
    0xF183:'000007001001001003002004000000000000',
    0xF184:'000d43140140740947940543140140140000',
    0xF185:'000f80080080080fc0400f80080080080000',
    0xF186:'000000600e00200200200200200200000000',
    0xF18A:'000000e00900100300600400800f00000000',
    0xF18D:'000f80081081080fc0400f80081081080000',
    0xF18E:'000000c00200200c00600200600c00000000',
    0xF191:'000f80080080080fc0401f81080080080000',
    0xF192:'000000100300500900900f80100100000000',
    0xF193:'000003006004004004006003000000000000',
    0xF194:'000883c82482783480c87880083082083000',
    0xF195:'000f80000000f80000fc0400f80080f80000',
    0xF196:'000001001001001000007000003000000000',
    0xF197:'000f83000003f82403fc0001f81081081000',
    0xF198:'000e40240e40040f40000040fc0040fc0000',
    0xF1A0:'000e40241e41040f40000040fc1041fc0000',
}

def need(ok,message):
    if not ok:raise ValueError(message)

def sha(data):return hashlib.sha256(data).hexdigest()

def hangul(c):return len(c)==1 and 0xAC00<=ord(c)<=0xD7A3

def load_pinned(path,digest):
    data=path.read_bytes();need(sha(data)==digest,f'Font ownership input drift: {path.name}')
    return json.loads(data)

def location(code):
    if 0xF040<=code<=0xF25C:return 0x47384+dense_index(code)*18
    if 0xF25D<=code<=0xF2AB and code!=0xF27F:
        return 0x4F080+(code-0xF25D-(code>=0xF280))*18
    if code in PACKED:return 0x4F650+(code-0xF2AC)*18
    raise ValueError(f'Unproven resident code: {code:04X}')

def full_owners():
    rows=load_pinned(CHARSET,CHARSET_SHA)['mappings']
    owners={int(r['code'],0):r['character'] for r in rows if hangul(r['character'])}
    need(len(owners)==432,'Resident/full extension Hangul denominator')
    for code,c in {**RECLAIMED,**PACKED}.items():
        need(code not in owners,'Semantic owner collision');owners[code]=c
    # Bind the semantic interpretation to the consumed name table, not assets'
    # filenames or the stale PUA/extension labels in later metadata.
    name_codes={}
    for text,raw,_width in installed_names():
        need(len(text)*2==len(raw)-1,'Name character/code alignment')
        for i,c in enumerate(text):
            code=int.from_bytes(raw[i*2:i*2+2],'big')
            if c==' ':continue
            need(owners.get(code)==c,f'Name/font semantic disagreement {text}/{code:04X}')
            name_codes[code]=c
    need(len(name_codes)==123 and len(owners)==444,'Expanded semantic font denominator')
    return owners

def unpack(raw):
    need(len(raw)==18,'12x12 glyph extent')
    cell=Image.new('1',(12,12))
    for i in range(144):cell.putpixel((i%12,i//12),(raw[i//8]>>(7-i%8))&1)
    need(pack_cell(cell)==raw,'Unmodified bitmap round trip')
    return cell

def fragment_targets():
    rows=load_pinned(CHARSET,CHARSET_SHA)['mappings']
    aliases=load_pinned(ALIASES,ALIASES_SHA)
    bycode={int(r['code'],0):r['character'] for r in rows}
    result={}
    for code,oldhex in FRAGMENTS.items():
        desc=aliases[bycode[code]];tile=desc['tile_index'];lead=desc['leading_px']
        need(lead==8,'Split-word placement drift')
        before=bytes.fromhex(oldhex);cell=unpack(before);protected=set(range(12))
        for i,c in enumerate(desc['source_text']):
            if not hangul(c):continue
            x=lead+i*12-tile*12
            glyph=unifont_cell_12(c)
            for localx in range(max(x,0),min(x+12,12)):
                protected.discard(localx)
                for y in range(12):cell.putpixel((localx,y),glyph.getpixel((localx-x,y)))
        after=pack_cell(cell);oldcell=unpack(before)
        need(all(oldcell.getpixel((x,y))==cell.getpixel((x,y))
                 for x in protected for y in range(12)),'Numeric/spacing pixel corruption')
        result[code]=(before,after,desc,sorted(protected))
    need(sum(a!=b for a,b,_d,_p in result.values())==15,'Split Hangul writer denominator')
    return result

def verify_shared_consumers(image):
    # 09 xx tokens and speaker names all resolve into the same 105 replicas.
    rows=[raw for _text,raw,_width in installed_names()]
    original=b''.join(rows)
    need(rows[43]==bytes.fromhex('F26AF1E8F269F0F800'),'Gel name lineage')
    rows[43]=bytes.fromhex('F26AF1E8F088F0F800')  # User-adopted 겔 게더.
    updated=b''.join(rows)
    replica_offsets=[int(x,0) for x in json.loads(REPLICAS.read_text(encoding='utf8'))['replica_offsets']]
    need(len(replica_offsets)==105,'Name replica denominator')
    delta=FIRST_NAME_TABLE-replica_offsets[0]
    canonical=image[FIRST_NAME_TABLE:FIRST_NAME_TABLE+len(original)]
    need(canonical in (original,updated),'Unexpected adopted name bytes')
    for offset in replica_offsets:
        need(image[offset+delta:offset+delta+len(canonical)]==canonical,'Name replica divergence')
    names={'name_records':78,'replicas_verified':105,'semantic_table_bytes':len(canonical),
           'gel_name_user_correction':canonical==updated}
    import condition_menu_boundaries as cn
    catalog=json.loads(cn.CATALOG.read_text(encoding='utf8'))['resources']
    need(len(catalog)==105,'Common container denominator')
    # The two obsolete death-label fragments have no references in any of the
    # containers; their replaced middle slot F17D belongs to literal 란.
    for row in catalog:
        header=int(row['header'],0);count=len(row['section_offsets'])
        offsets=struct.unpack_from('<'+str(count)+'I',image,header)
        span=image[header+offsets[0]:header+offsets[-1]]
        need(all(c.to_bytes(2,'big') not in span for c in (0xF17C,0xF17D,0xF17E)),
             'Obsolete split-death phrase has acquired a consumer')
    return names

def plan(image):
    verify_sources();owners=full_owners();names=verify_shared_consumers(image)
    for bias in (0,MIRROR):
        for offset,length,digest in BANKS:
            need(sha(image[bias+offset:bias+offset+length])==digest,'Resident font preimage drift')
    writes=[];changed=[]
    for code,c in sorted(owners.items()):
        offset=location(code);before=image[offset:offset+18];after=unifont_dense_12(c)[0]
        if before==after:continue
        changed.append({'code':hex(code),'character':c,'offset':hex(offset),'before':before.hex(),'after':after.hex()})
        for bias in (0,MIRROR):writes.append((bias+offset,before,after,f'font12/full/{c}/{code:04X}/{bias:X}'))
    need({int(row['code'],0) for row in changed}==EXPECTED_BAD_FULL,'Unexpected font mismatch set')
    fragments=[]
    for code,(before,after,desc,protected) in fragment_targets().items():
        offset=location(code)
        for bias in (0,MIRROR):
            need(image[bias+offset:bias+offset+18]==before,'Split glyph preimage drift')
            if before!=after:writes.append((bias+offset,before,after,f'font12/split/{code:04X}/{bias:X}'))
        fragments.append({'code':hex(code),'source_text':desc['source_text'],'tile':desc['tile_index'],
                          'changed':before!=after,'protected_columns':protected})
    writes.sort()
    need(len(writes)==54,'Font write denominator')
    for a,b in zip(writes,writes[1:]):need(a[0]+18<=b[0],'Font owner overlap')
    return writes,{'font_sha256':UNIFONT_SHA256,'full_syllable_owners':len(owners),
        'full_syllable_mismatches':changed,'split_fragments':fragments,'main_copies':2,
        'name_consumers':names,'changed_cells':len(writes),
        'policy':'Canonical 12x12 Hangul; native numeral/space pixels preserved',
        'text_codes_records_pointers_and_machine_code_changed':False}

def verify(image):
    verify_sources();owners=full_owners();names=verify_shared_consumers(image)
    for code,c in owners.items():
        wanted=unifont_dense_12(c)[0];offset=location(code)
        for bias in (0,MIRROR):
            need(image[bias+offset:bias+offset+18]==wanted,f'Noncanonical final Hangul {c}/{code:04X}')
    for code,(_before,after,_desc,_protected) in fragment_targets().items():
        for bias in (0,MIRROR):
            offset=bias+location(code)
            need(image[offset:offset+18]==after,f'Final split-word mismatch {code:04X}')
    # The rest of the active 12x12 paths are audited, not rewritten.
    import early_dialogue_font as globalfont
    import build_r80_successor204_resource12_unifont_all_successor205 as atlas
    import build_successor252_item_font_runtime_safe as f8
    import condition_resident as condition
    import muscle_temple_dialogue as muscle
    import build_r80_scenario02_unifont12_dedicated_successor175 as s2
    import build_v342_shop_complete as shop
    rows,bank=atlas.rows_and_bank();tails=globalfont.resource12_tails(image)
    for tail in tails:
        need(image[tail+0x200:tail+0x200+len(bank)]==bank,'Global atlas Hangul drift')
        need(image[tail+f8.F8_SAFE_OFFSET:tail+f8.F8_SAFE_OFFSET+f8.PAGE_BYTES]==
             image[tail+f8.F8_SOURCE_OFFSET:tail+f8.F8_SOURCE_OFFSET+f8.PAGE_BYTES],'F8 clone drift')
        need(image[tail+condition.OFFSET:tail+condition.OFFSET+condition.BYTES]==condition.payload(),
             'Shared condition font drift')
        extra=muscle.mapping_and_font()[3]
        need(image[tail+muscle.NEW_GLYPH_OFFSET:tail+muscle.NEW_GLYPH_OFFSET+len(extra)]==extra,
             'Hidden dialogue extension font drift')
    characters=json.loads(s2.PLAN.read_text(encoding='utf8'))['glyphs']['missing_from_current_charset']
    decoded=s2.overlay.lzss_decompress(image[s2.COMPRESSED_COOKED:s2.COMPRESSED_COOKED+s2.COMPRESSED_CAPACITY],117*18)
    need(decoded==b''.join(unifont_dense_12(c)[0] for c in characters),'Scenario2 font drift')
    shop_count=0
    for first,builder in ((0xF29B,shop.build_no_category_tail_cells),
                          (0xF2A3,shop.build_cannot_equip_particle_cells),
                          (0xF2A5,shop.build_cannot_equip_tail_cells)):
        for i,cell in enumerate(builder()):
            offset=location(first+i)
            for bias in (0,MIRROR):need(image[bias+offset:bias+offset+18]==pack_cell(cell),'Shop split font drift')
            shop_count+=1
    return {'resident_full_syllable_cells':len(owners)*2,'canonical_name_codes':123,
        'name_table_records':names['name_records'],'name_table_replicas':names['replicas_verified'],
        'split_word_cells_checked':len(FRAGMENTS)*2,'shop_split_cells_checked':shop_count*2,
        'global_atlas_cells_checked':len(rows)*len(tails),'global_f8_clones':len(tails),
        'hidden_added_cells_checked':11*len(tails),'condition_cells_checked':8*len(tails),
        'scenario2_cells_checked':117,'mismatches':0}
