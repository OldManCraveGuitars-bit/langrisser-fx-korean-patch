"""Native X2/X3 (72/73) bounded dialogue and battle-menu localization.

Ordinal selectors, page waits, choices, event bytes and all outer offsets are
preserved. The already approved narration and presentation stay byte-exact.
"""
from pathlib import Path
import json,re,struct
import dialogue_core as d
import muscle_temple_dialogue as base
import hidden_x_font as fonts
import presentation_dictionary as pd
import condition_native_codec as nc
import condition_menu_boundaries as boundaries
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'analysis/hidden-x2-x3-source-original-282.json'
PROFILES={72:(0x316474,'6709CF783D907374F769A207E3E40BE4B821547D55B9CD0E7981C1B4615BA599',
 '60C59919094518364FCD0BEA205B6D567A91295D1621A13D2FF8A322017F4613',97,0x4B),
 73:(0x31BEB8,'428B47447F5A89DEB96FA8C260C788B89D1AC7183A2C56A42F5D815D5E9A286A',
 '53DAA799F74C9EF0F0F0B6AB5C2A5EB7961387AD3325B0C0923424532CF8A0CD',148,0x3B)}
PHRASES={72:('문제예요!','문제입니다!','딩동댕!','땡.','메사이얀 퀴즈','잘 있거라!',
 '모두 맞혔','틀렸다','숨겨진 스테이지','우키.','그럼,','안녕!',
 '문제','패키지','정답','메사이야','살펴보세요!'),
 73:('숨겨진 스테이지','마니아','잘 가라,','이렇게 된 이상','손가락 하나',
 '황금의 마계 주니어','이것이 신기에 가까운 방어다!','비장의','타이푼 볼트!',
 '스워드','제극계','‥‥.','녀석들','그러니까','기술을','모두들','쓰러뜨',
 '네 공격','뒤는 부탁한다','이런 곳에서','다니!','여동생','그럼,','어쩔 수 없',
 '아가씨','가까운','힘을','보여 주마!','얕보지 마!')}

def input_rows(n,mapping):
    profile=PROFILES[n];doc=json.loads((ROOT/f'dialogue_editor/hidden_x{n-70}_dialogue_successor283.json').read_text(encoding='utf8'))
    source=next(r for r in json.loads(SOURCE.read_text(encoding='utf8'))['resources'] if r['resource_id']==n)
    d.need(doc['schema']=='langrisser-fx-hidden-dialogue-translation/v1' and
           doc['status']=='needs_human_review' and doc['non_distribution'] is True,'X draft policy')
    d.need(doc['source_dialogue_sha256']==profile[1]==source['original_dialogue_sha256'],'X source identity')
    d.need(base.sha(b''.join(bytes.fromhex(r['raw_hex']) for r in source['records']))==profile[1],'X protected source bytes')
    texts=doc['records'];d.need(list(texts)==[r['id'] for r in source['records']] and len(texts)==profile[3],'X ordinal population')
    plains=[];layouts=[]
    for original in source['records']:
        key=original['id'];text=texts[key]
        d.need(not d._unknown_tokens(text),key+' unknown token')
        oldpages=original['expanded_text'].split('\f');newpages=text.split('{page}')
        d.need(len(oldpages)==len(newpages),key+' native page count changed')
        for old,new in zip(oldpages,newpages):
            tokens=lambda s:re.findall(r'\{(?:name|raw):[0-9a-fA-F]{2}\}',s)
            d.need(tokens(old)==tokens(new),key+' protected token order')
        d.need(bool(text)==(original['raw_hex']!='00'),key+' empty slot changed')
        layout=d.portrait_layout_inspection(text)
        d.need(not layout['failures'],f"{key}: {layout['failures']}")
        raw,missing=d.encode_plain(text,mapping)
        d.need(not missing and b'\0' not in raw,f'{key}: missing glyph/NUL {missing}')
        nc.units(raw)
        plains.append(raw);layouts.append({'id':key,**layout})
    return source,texts,plains,layouts

def condition_rows(n,mapping):
    # Preserve original dynamic protagonist and the original victory target.
    # Name 4B=ウッキー/우키, 3B=魔女/마녀 in both original and installed tables.
    enc=lambda t:d.encode_plain(t,mapping)[0]
    return (b'\x04\x1c',b'\x04\x1d',b'\x05\x81\x45\x02'+enc(' 사망'),
            b'\x05\x81\x45\x09'+bytes((PROFILES[n][4],))+enc(' 격파'),b'',b'',b'',b'')

def plan(image):
    mapping=fonts.mapping();writes=[];audits=[]
    for n,(header,digest,dictsha,count,_name) in PROFILES.items():
        original,texts,plains,layouts=input_rows(n,mapping)
        sections=tuple(int(s,0) for s in original['sections'])
        d.need(tuple(header+x for x in struct.unpack_from('<9I',image,header))==sections,'X section layout')
        ds,de=sections[5:7]
        d.need(base.sha(image[ds:de])==digest,'X dialogue preimage')
        d.need(base.sha(image[sections[4]:ds])==dictsha,'X dictionary preimage')
        resource=pd.locate_resource(image,sections[7],allow_authored_title=True)
        payloads=tuple((p,d.encode_plain(p,mapping)[0]) for p in PHRASES[n])
        # This writer replaces the complete native ordinal pool atomically.
        # Its old high dictionary references have no remaining consumer.
        # Retire ONLY that text span for allocation; common text, CN,
        # narration and all low/runtime dictionary owners remain scanned.
        retired=bytearray(image[:sections[8]])
        retired[ds:de]=bytes(de-ds)
        dictionary=pd.build_dictionary_plan(retired,resource,payloads)
        phrases=dict(dictionary.assignments)
        encoded=[d.encode_compressed(d.engine_text(t),mapping,phrases,de-ds,prefer_parity=False)[0] for t in texts.values()]
        blob=b''.join(r+b'\0' for r in encoded)
        d.need(len(blob)<=de-ds,f'X{n-70} dialogue capacity {len(blob)}/{de-ds}')
        blob=blob.ljust(de-ds,b'\0')
        rows=base.split_rows(blob,count);dr=pd._split_dictionary(dictionary.replacement)
        d.need([base.expand(r,dr) for r in rows]==plains,'X lossless dictionary roundtrip')
        cnrows=condition_rows(n,mapping);cn=b''.join(r+b'\0' for r in cnrows)
        d.need(len(cn)<=sections[7]-de,'X CN capacity')
        cn=cn.ljust(sections[7]-de,b'\0')
        d.need(boundaries.required_rows(cn,8)==list(cnrows),'X native CN denominator')
        for code in dictionary.preserved_codes:
            d.need(dr[code-1]==resource.dictionary_rows[code-1],'X protected dictionary dependency')
        for at,before,after,owner in ((sections[4],image[sections[4]:ds],dictionary.replacement,'dictionary'),
            (ds,image[ds:de],blob,'dialogue'),(de,image[de:sections[7]],cn,'conditions')):
            writes.append((at,before,after,f'hidden-x/{n}/{owner}'))
        audits.append({'native_resource':n,'records':count,'nonempty':sum(bool(t) for t in texts.values()),
            'dialogue_used':sum(len(r)+1 for r in encoded),'capacity':de-ds,
            'dictionary_assignments':dictionary.assignments,'dictionary_cleared_codes':dictionary.cleared_codes,
            'dictionary_preserved_codes':dictionary.preserved_codes,'layouts':layouts,
            'condition_rows':8,'victory':'우키 격파' if n==72 else '마녀 격파','defeat':'{raw:02} 사망',
            'source_sha256':digest,'draft_sha256':base.sha((ROOT/f'dialogue_editor/hidden_x{n-70}_dialogue_successor283.json').read_bytes()),
            'original_page_tokens_names_choices_and_all_section_offsets_preserved':True,
            'presentation_unchanged':True})
    return sorted(writes),{'status':'NON_DISTRIBUTION_TRANSLATION_REVIEW','resources':audits}

def verify(image):
    mapping=fonts.mapping();result=[]
    for n,profile in PROFILES.items():
        original,texts,plains,layouts=input_rows(n,mapping)
        s=[int(v,0) for v in original['sections']]
        d.need(tuple(profile[0]+v for v in struct.unpack_from('<9I',image,profile[0]))==tuple(s),'Final X offsets')
        local=pd._split_dictionary(image[s[4]:s[5]])
        rows=base.split_rows(image[s[5]:s[6]],profile[3])
        d.need([base.expand(r,local) for r in rows]==plains,'Final X authored bytes')
        cn=boundaries.required_rows(image[s[6]:s[7]],8)
        d.need(cn==list(condition_rows(n,mapping)),'Final X condition bodies')
        for r in cn:nc.expand(r,local)
        result.append({'resource':n,'lossless_records':len(rows),'layouts_passed':len(layouts),'condition_rows':len(cn)})
    return result
