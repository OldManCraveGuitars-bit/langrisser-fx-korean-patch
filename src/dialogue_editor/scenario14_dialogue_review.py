"""Source-bound S14 prose review; preserve the native 104-row ordinal pool."""
import json
from dataclasses import replace
from pathlib import Path
import dialogue_core as dialogue
import condition_native_codec as native
import presentation_dictionary as dictionary
from scenario_dialogue_review import read_cooked, protected_signature, sha
from muscle_temple_dialogue import split_rows, SELECTOR, MIRROR

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'dialogue_editor/scenario14_review.json'
CATALOG=ROOT/'analysis/scenario14_source_v79.json'
START,END,DICT,COUNT=0x192654,0x193644,0x191DB7,104
JP_POOL_SHA='E18158F1DAE383C0B5C16C07BF25E9C8D566FFBD0AF32B2B9035661812A85CBD'
JP_DICT_SHA='1896240B59AA7E3D535EDC003D006D49DAA64DAAA8293AECAF596C261D6445A4'
POOL_SHA='E83310E2B865CA700E623B494DE19169D5B64BF201FE23DED755010A7647C334'
DICT_SHA='FE52C3628A34E31700438D8A1D75F6265F6453DC0CEF8A48B82C85CBD355700A'
need=dialogue.need


def selected_texts():
    doc=json.loads(INPUT.read_text(encoding='utf8'))
    need(set(doc)=={'schema','scope','status','distribution_allowed','authority',
                   'source_catalog','page_policy','records'},'S14 review fields')
    need(doc['schema']=='langrisser-fx-scenario-page-faithful-review/v1'
         and doc['scope']=='scenario14' and doc['status']=='development_review_requested'
         and doc['distribution_allowed'] is False,'S14 development review policy')
    need(doc['page_policy']=='exact_original_page_wait_and_page_local_dynamic_tokens'
         and doc['source_catalog']=='analysis/scenario14_source_v79.json','S14 source/page policy')
    need(isinstance(doc['records'],dict) and set(doc['records'])==
         {f'scenario14/dialogue/{i:03d}' for i in range(COUNT)}
         and all(isinstance(v,str) and v for v in doc['records'].values()),'S14 review population')
    return doc['records']


def apply_to_editor(records):
    selected=selected_texts()
    need(set(selected)=={r.id for r in records if r.scenario==14},'S14 editor population')
    return [replace(r,base_text=selected[r.id]) if r.id in selected else r for r in records]


def original_rows(original):
    rows=json.loads(CATALOG.read_text(encoding='utf8'))['dialogue']
    raw=read_cooked(original,START,END-START)
    local=read_cooked(original,DICT,START-DICT)
    need(len(rows)==COUNT and sha(raw)==JP_POOL_SHA and sha(local)==JP_DICT_SHA,
         'S14 Japanese source identity')
    need(local[0]==0,'S14 dictionary sentinel')
    dictionaries=dictionary._split_dictionary(local[1:])
    cursor=START
    result=[]
    for i,row in enumerate(rows):
        payload=bytes.fromhex(row['raw_hex'])
        need(row['id']==f'scenario14/dialogue/{i:03d}'
             and int(row['cooked_offset'],0)==cursor
             and payload==raw[cursor-START:cursor-START+len(payload)]
             and payload[-1:]==b'\0','S14 catalog/raw identity')
        result.append((row['id'],native.expand(payload,dictionaries)))
        cursor+=len(payload)
    need(cursor==END,'S14 source extent')
    return result


def pack(before,local,original,selected):
    need(len(original)==COUNT and set(selected)=={k for k,_ in original},'S14 selected IDs')
    old=split_rows(before,COUNT)
    mapping=dialogue.with_native_ascii(dialogue.all_dialogue_private_mapping())
    rows=[]; audit=[]
    for ordinal,(key,jp) in enumerate(original):
        text=selected[key]
        need(not dialogue._unknown_tokens(text),key+' unknown controls')
        literal,missing=dialogue.encode_plain(text,mapping)
        need(not missing and b'\0' not in literal,key+' unmapped glyph/NUL: '+str(missing))
        need(protected_signature(jp)==protected_signature(literal+b'\0'),key+' original controls differ')
        layout=dialogue.portrait_layout_inspection(text)
        pages=1+sum(t==b'\x06' for t in native.units(jp))
        need(not layout['failures'] and layout['screens']==layout['voice_pages']==pages,
             key+' invalid page geometry: '+str(layout['failures']))
        encoded=native.compress(literal,local)
        need(native.expand(encoded,local)==literal,key+' roundtrip')
        rows.append(encoded)
        audit.append({'ordinal':ordinal,'id':key,'text':text,'pages':pages,'layout':layout,
                      'before_hex':old[ordinal].hex(),'after_hex':encoded.hex(),
                      'original_expanded_sha256':sha(jp),'selected_expanded_sha256':sha(literal),
                      'exact_original_controls':True})
    packed=b''.join(row+b'\0' for row in rows)
    need(len(packed)<=len(before),'S14 ordinal pool overflow')
    after=packed.ljust(len(before),b'\0')
    need(split_rows(after,COUNT)==rows,'S14 ordinal reparse')
    return after,{'records':audit,'reviewed_records':COUNT,'total_pages':sum(r['pages'] for r in audit),
                  'pool_capacity':len(before),'pool_used':len(packed),'new_glyphs':0,
                  'dictionary_or_code_changed':False,'source_sha256':JP_POOL_SHA,
                  'selection_sha256':sha(INPUT.read_bytes()),'distribution_allowed':False}


def plan(image,original):
    need(sha(image[START:END])==POOL_SHA and sha(image[DICT:START])==DICT_SHA,'S14 immutable preimage')
    for bias in (0,MIRROR):
        need(image[bias+0x714C:bias+0x714C+len(SELECTOR)]==SELECTOR,'S14 native ordinal consumer')
    local=dictionary._split_dictionary(image[DICT+1:START])
    after,audit=pack(image[START:END],local,original_rows(original),selected_texts())
    return [(START,image[START:END],after,'scenario14/page-faithful-review')],audit


def verify(source,target,original):
    writes,audit=plan(source,original)
    need(target[START:END]==writes[0][2],'S14 final writer changed selected text')
    audit['verified_after_last_writer']=True
    return audit
