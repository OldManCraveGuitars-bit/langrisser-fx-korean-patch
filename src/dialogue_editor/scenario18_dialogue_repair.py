"""Complete S18 native NUL-ordinal pool, including non-prose entries.

The older editor excluded ten Latin/name/punctuation records. Repacking its
separate runs padded the first run with NULs, so native ordinals 73..96 read
empty strings instead of the following monster/death/turn dialogue. The
96 content entries and two original empty tail entries have one owner here.
Only the original section-5 allocation changes; no code, font or dictionary.
"""
import json
from dataclasses import replace
from pathlib import Path
import dialogue_core as d
import condition_native_codec as native
import presentation_dictionary as dictionary
from scenario_dialogue_review import read_cooked,protected_signature,sha
from muscle_temple_dialogue import split_rows,SELECTOR,MIRROR
ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'dialogue_editor/scenario18_repair.json'
CATALOG=ROOT/'analysis/scenario18_dialogue_source_v169.json'
START,END,DICT,COUNT=0x1AFEA8,0x1B0D2C,0x1AF60C,98
POOL_SHA='7B5E47DF0D6E42C3506412FD0A88A7CE81090EC3CD45664163BCF4A30FD7BFAF'
DICT_SHA='214BACDD4AC15C51ED22DBF6A97443C856898604BE2BB21609C428C9FD3D1A38'
JP_POOL_SHA='096F1EB26DA9D68645ADB9D9DEA4D9DF404CA83D61AFB7BEB0475C8601E1CF23'
JP_DICT_SHA='A58A6F23CCEA3AA9571562C9C508686C7878D9EB51034F8CCA19A9613114AE50'
need=d.need

def selected_texts():
    doc=json.loads(INPUT.read_bytes())
    need(doc['schema']=='langrisser-fx-scenario18-ordinal-repair/v1' and doc['scope']=='scenario18','S18 selection identity')
    need(doc['status']=='development_review_requested' and doc['distribution_allowed'] is False,'S18 input policy')
    need(doc['page_policy']=='exact_original_page_wait_and_page_local_dynamic_tokens','S18 page policy')
    selected=doc['records']
    need(set(selected)=={f'scenario18/dialogue/{i:03d}' for i in range(COUNT)},'S18 complete ordinal population')
    need(all(isinstance(v,str) and bool(v)==(int(k.rsplit('/',1)[1])<96) for k,v in selected.items()),'S18 missing/extra body')
    return selected

def apply_to_editor(records):
    selected=selected_texts()
    need(set(selected)=={r.id for r in records if r.scenario==18},'S18 editor omitted native records')
    return [replace(r,base_text=selected[r.id]) if r.id in selected else r for r in records]

def pack_complete_rows(rows,capacity):
    need(len(rows)==COUNT,'S18 missing native ordinal')
    need(all(isinstance(x,bytes) and b'\0' not in x for x in rows),'S18 embedded terminator')
    need(all(rows[:96]) and not any(rows[96:]),'S18 missing/extra native bodies')
    packed=b''.join(x+b'\0' for x in rows)
    need(len(packed)<=capacity,'S18 complete pool capacity')
    after=packed.ljust(capacity,b'\0')
    need(split_rows(after,COUNT)==rows,'S18 final native ordinal roundtrip')
    return after,len(packed)

def original_rows(original):
    raw=read_cooked(original,START,END-START);local=read_cooked(original,DICT,START-DICT)
    need(sha(raw)==JP_POOL_SHA and sha(local)==JP_DICT_SHA,'S18 original Japanese identity')
    rows=json.loads(CATALOG.read_bytes())['dialogue']
    need(len(rows)==COUNT and b''.join(bytes.fromhex(r['raw_hex']) for r in rows)==raw,'S18 source ordinal reassembly')
    jpdict=dictionary._split_dictionary(local[1:])
    return [(r['id'],native.expand(bytes.fromhex(r['raw_hex']),jpdict)) for r in rows]

def plan(image,original):
    before=bytes(image[START:END])
    need(sha(before)==POOL_SHA and sha(image[DICT:START])==DICT_SHA,'S18 immutable baseline')
    for bias in (0,MIRROR):need(image[bias+0x714C:bias+0x714C+len(SELECTOR)]==SELECTOR,'S18 native ordinal selector changed')
    local=dictionary._split_dictionary(image[DICT+1:START])
    # This historical preimage contains only two source-empty records, both
    # at the end. The exact pool hash and original reassembly bound this
    # recovery; never generalize nonempty filtering to another native pool.
    physical=[x for x in before.split(b'\0') if x]+[b'',b'']
    need(len(physical)==COUNT,'S18 preimage content population')
    selected=selected_texts();mapping=d.with_native_ascii(d.all_dialogue_private_mapping())
    out=[];audit=[]
    for i,(key,jp) in enumerate(original_rows(original)):
        text=selected[key];need(not d._unknown_tokens(text),key+' unknown control')
        literal,missing=d.encode_plain(text,mapping)
        need(not missing and b'\0' not in literal,key+' missing encoding/NUL')
        need(protected_signature(jp)==protected_signature(literal+b'\0'),key+' native control topology')
        layout=d.portrait_layout_inspection(text)
        pages=1+sum(u==b'\x06' for u in native.units(jp))
        need(not layout['failures'] and (i>=96 or layout['screens']==layout['voice_pages']==pages),key+' page geometry')
        if i<96:need(literal,key+' nonempty original body became empty')
        else:need(jp==b'\0' and not literal,key+' original empty tail changed')
        encoded=native.compress(literal,local)
        need(native.expand(encoded,local)==literal,key+' dictionary roundtrip')
        if native.expand(physical[i],local)==literal:encoded=physical[i]
        out.append(encoded)
        audit.append({'id':key,'text':text,'pages':pages if i<96 else 0,'layout':layout,
            'content_changed':encoded!=physical[i],'native_controls_exact':True,
            'before_physical_hex':physical[i].hex(),'after_hex':encoded.hex()})
    after,used=pack_complete_rows(out,len(before))
    return [(START,before,after,'scenario18/complete-native-ordinal-pool')],{
        'original_records':COUNT,'content_records':96,'original_empty_tail_records':2,
        'restored_native_body_ordinals_1_based':list(range(73,97)),
        'records':audit,'pool_capacity':len(before),'pool_used':used,
        'selection_sha256':sha(INPUT.read_bytes()),'dictionary_code_font_unchanged':True}

def verify(source,target,original):
    writes,audit=plan(source,original)
    need(target[START:END]==writes[0][2],'S18 final consumer bytes')
    need(target[DICT:START]==source[DICT:START],'S18 shared dictionary changed')
    audit['verified_after_last_writer']=True
    return audit
