"""Page-faithful, source-bound Scenario 13 review input and product writer.

One complete ordinal pool owner supersedes the earlier one-row correction.
Japanese page/wait/name/variable order is the hard constraint, never a prior
Korean reflow. Shared dictionaries, code, fonts and pool bounds stay untouched.
"""
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import dialogue_core as dialogue
import condition_native_codec as native
import presentation_dictionary as dictionary
import dialogue_wording_corrections as predecessor
from muscle_temple_dialogue import split_rows, SELECTOR, MIRROR

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT/'dialogue_editor/scenario13_review.json'
SOURCE_CATALOG = ROOT/'analysis/scenario13_fixed_records_v78.json'
START, END, COUNT = predecessor.START, predecessor.END, predecessor.COUNT
JP_POOL_SHA = '97CF746257864501D8B0F5B5586D1CD69D6B57C05667F6BCB0EC7F5258A1F8A2'
JP_DICT_SHA = '1896240B59AA7E3D535EDC003D006D49DAA64DAAA8293AECAF596C261D6445A4'
need = dialogue.need
sha = predecessor.sha


def selected_texts():
    doc = json.loads(INPUT.read_text(encoding='utf8'))
    need(set(doc)=={'schema','scope','status','distribution_allowed','authority',
                   'source_catalog','page_policy','records'}, 'Scenario review fields')
    need(doc['schema']=='langrisser-fx-scenario-page-faithful-review/v1'
         and doc['scope']=='scenario13' and doc['status']=='development_review_requested'
         and doc['distribution_allowed'] is False, 'Scenario review input policy')
    need(doc['page_policy']=='exact_original_page_wait_and_page_local_dynamic_tokens',
         'Original page policy changed')
    need(doc['source_catalog']==str(SOURCE_CATALOG.relative_to(ROOT)).replace('\\','/'),
         'Scenario source catalog changed')
    need(isinstance(doc['records'],dict) and len(doc['records'])==COUNT
         and all(isinstance(k,str) and isinstance(v,str) and v for k,v in doc['records'].items()),
         'Scenario review text population')
    need(doc['records'][predecessor.KEY]=='네가 {name:15}로구나!',
         'Previously approved duplication repair changed')
    return doc['records']


def apply_to_editor(records):
    selected = selected_texts()
    need(set(selected)=={row.id for row in records if row.scenario==13},
         'Editor/review scenario population differs')
    return [replace(row,base_text=selected[row.id]) if row.id in selected else row
            for row in records]


def read_cooked(original,start,length):
    result=bytearray()
    with Path(original).open('rb') as f:
        while length:
            count=min(length,2048-start%2048)
            f.seek((225+start//2048)*2352+16+start%2048)
            part=f.read(count)
            need(len(part)==count,'Truncated original sector payload')
            result.extend(part)
            start+=count
            length-=count
    return bytes(result)


def original_rows(original):
    rows=json.loads(SOURCE_CATALOG.read_text(encoding='utf8'))['edits']
    need(len(rows)==COUNT and len({r['id'] for r in rows})==COUNT,'Original catalog population')
    rows=sorted(rows,key=lambda r:int(r['cooked_offset'],0))
    payload=b''.join(bytes.fromhex(r['expected_hex']) for r in rows)
    need(sha(payload)==JP_POOL_SHA and len(payload)==END-START,'Original pool identity')
    need(read_cooked(original,START,END-START)==payload,'Catalog/Japanese disc mismatch')
    local=read_cooked(original,predecessor.DICT,START-predecessor.DICT)
    need(sha(local)==JP_DICT_SHA and local[0]==0,'Japanese dictionary identity')
    dictionaries=dictionary._split_dictionary(local[1:])
    cursor=START
    result=[]
    for row in rows:
        raw=bytes.fromhex(row['expected_hex'])
        need(int(row['cooked_offset'],0)==cursor and raw.endswith(b'\0'),
             'Original record boundary')
        result.append((row['id'],native.expand(raw,dictionaries)))
        cursor+=len(raw)
    need(cursor==END,'Original ordinal extent')
    return result


def protected_signature(raw):
    """Exact low controls including page/wait and dynamic arguments, excluding BR.

    Counting pages alone is insufficient: 02 or 09 NN moved across 06 07 is
    a different signature and must fail, as must missing wait or added commands.
    """
    return tuple(token for token in native.units(raw) if token[0]<10 and token!=b'\x08')


def pack(before,local,original,selected):
    need(set(selected)=={key for key,_ in original},'Selected source IDs differ')
    old=split_rows(before,COUNT)
    mapping=dialogue.with_native_ascii(dialogue.all_dialogue_private_mapping())
    rows=[]
    audit=[]
    for ordinal,(key,jp) in enumerate(original):
        text=selected[key]
        need(not dialogue._unknown_tokens(text),key+' unknown controls')
        layout=dialogue.portrait_layout_inspection(text)
        need(not layout['failures'],key+': '+str(layout['failures']))
        literal,missing=dialogue.encode_plain(text,mapping)
        need(not missing and b'\0' not in literal,key+' unmapped character/NUL: '+str(missing))
        need(protected_signature(jp)==protected_signature(literal+b'\0'),
             key+' Japanese page/wait/dynamic token order differs')
        pages=sum(token==b'\x06' for token in native.units(jp))+1
        need(layout['screens']==layout['voice_pages']==pages,key+' extra/empty visual page')
        encoded=native.compress(literal,local)
        need(native.expand(encoded,local)==literal,key+' compression roundtrip')
        rows.append(encoded)
        audit.append({'ordinal':ordinal,'id':key,'text':text,'pages':pages,'layout':layout,
            'original_expanded_sha256':sha(jp),'selected_expanded_sha256':sha(literal),
            'before_hex':old[ordinal].hex(),'after_hex':encoded.hex(),
            'exact_original_controls':True})
    packed=b''.join(row+b'\0' for row in rows)
    need(len(packed)<=len(before),'Scenario 13 pool overflow')
    output=packed.ljust(len(before),b'\0')
    need(split_rows(output,COUNT)==rows,'Scenario 13 ordinal reparse')
    return output,{'records':audit,'reviewed_records':COUNT,
        'total_pages':sum(x['pages'] for x in audit),'pool_capacity':len(before),
        'pool_used':len(packed),'new_glyphs':0,'dictionary_or_code_changed':False,
        'source_sha256':JP_POOL_SHA,'selection_sha256':sha(INPUT.read_bytes()),
        'distribution_allowed':False}


def plan(image,original):
    need(sha(image[START:END])==predecessor.POOL_SHA,'Immutable scenario pool preimage')
    need(sha(image[predecessor.DICT:START])==predecessor.DICT_SHA,'Active dictionary preimage')
    for bias in (0,MIRROR):
        need(image[bias+0x714C:bias+0x714C+len(SELECTOR)]==SELECTOR,'Native ordinal selector')
    local=dictionary._split_dictionary(image[predecessor.DICT+1:START])
    after,audit=pack(image[START:END],local,original_rows(original),selected_texts())
    return [(START,image[START:END],after,'scenario13/page-faithful-review')],audit


def verify(source,target,original):
    writes,audit=plan(source,original)
    need(target[START:END]==writes[0][2],'Final reviewed scenario bytes differ')
    audit['verified_after_last_writer']=True
    return audit
