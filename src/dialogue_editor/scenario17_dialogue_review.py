"""Apply the individually reviewed S17 expressions, without page reflow."""
import json
from dataclasses import replace
from pathlib import Path
import dialogue_core as d
import condition_native_codec as native
import presentation_dictionary as dictionary
from scenario_dialogue_review import read_cooked,protected_signature,sha
from muscle_temple_dialogue import split_rows,SELECTOR,MIRROR
ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'dialogue_editor/scenario17_review.json'
CATALOG=ROOT/'analysis/scenario17_dialogue_source_v165.json'
START,END,DICT,COUNT=0x1A9B58,0x1AA850,0x1A92BC,129
POOL_SHA='005B52EA4EB46026E0AD98B74D5F7C607081FF67113F6240D28D094403B6CC8B'
DICT_SHA='8F83A36A911DE48E369176E2FB8086AAB99AD016F788B2627C8D741A012FAB08'
JP_POOL_SHA='524E305290476D25D3550600340BAE42D1E9EA6FA6C4F5B304723D0FC849A8E9'
JP_DICT_SHA='A58A6F23CCEA3AA9571562C9C508686C7878D9EB51034F8CCA19A9613114AE50'
need=d.need

def selected_texts():
    doc=json.loads(INPUT.read_bytes())
    need(doc['schema']=='langrisser-fx-scenario17-adopted-review/v1' and doc['scope']=='scenario17','S17 selection identity')
    need(doc['page_policy']=='exact_original_page_wait_and_page_local_dynamic_tokens','S17 page policy')
    selected=doc['records']
    need(set(selected)=={f'scenario17/dialogue/{i:03d}' for i in range(COUNT)},'S17 selected population')
    review=json.loads((ROOT/doc['review_evidence']).read_bytes())
    need(selected=={r['id']:r.get('proposal',r['before']) for r in review['records']},'S17 reviewed selection drift')
    return selected

def apply_to_editor(records):
    selected=selected_texts()
    need(set(selected)=={r.id for r in records if r.scenario==17},'S17 editor population')
    return [replace(r,base_text=selected[r.id]) if r.id in selected else r for r in records]

def original_rows(original):
    raw=read_cooked(original,START,END-START);local=read_cooked(original,DICT,START-DICT)
    need(sha(raw)==JP_POOL_SHA and sha(local)==JP_DICT_SHA,'S17 Japanese source identity')
    rows=json.loads(CATALOG.read_bytes())['dialogue']
    need(b''.join(bytes.fromhex(r['raw_hex']) for r in rows)==raw and len(rows)==COUNT,'S17 original ordinal reassembly')
    dictionaries=dictionary._split_dictionary(local[1:])
    return [(r['id'],native.expand(bytes.fromhex(r['raw_hex']),dictionaries)) for r in rows]

def plan(image,original):
    before=bytes(image[START:END])
    need(sha(before)==POOL_SHA and sha(image[DICT:START])==DICT_SHA,'S17 immutable baseline')
    for bias in (0,MIRROR):need(image[bias+0x714C:bias+0x714C+len(SELECTOR)]==SELECTOR,'S17 ordinal selector')
    local=dictionary._split_dictionary(image[DICT+1:START]);old=split_rows(before,COUNT)
    selected=selected_texts();mapping=d.with_native_ascii(d.all_dialogue_private_mapping())
    out=[];audit=[]
    for i,(key,jp) in enumerate(original_rows(original)):
        text=selected[key];need(not d._unknown_tokens(text),key+' unknown control')
        literal,missing=d.encode_plain(text,mapping)
        need(not missing and b'\0' not in literal,key+' encoding')
        need(protected_signature(jp)==protected_signature(literal+b'\0'),key+' Japanese control topology')
        layout=d.portrait_layout_inspection(text)
        pages=1+sum(u==b'\x06' for u in native.units(jp))
        need(not layout['failures'] and layout['screens']==layout['voice_pages']==pages,key+' page geometry')
        encoded=native.compress(literal,local);need(native.expand(encoded,local)==literal,key+' roundtrip')
        # Keep unchanged encoded records byte-exact, not merely equivalent.
        if native.expand(old[i],local)==literal:encoded=old[i]
        out.append(encoded)
        audit.append({'id':key,'changed':encoded!=old[i],'pages':pages,'text':text,'layout':layout,
                      'original_controls_exact':True,'before_hex':old[i].hex(),'after_hex':encoded.hex()})
    packed=b''.join(x+b'\0' for x in out);need(len(packed)<=len(before),'S17 pool capacity')
    after=packed.ljust(len(before),b'\0');need(split_rows(after,COUNT)==out,'S17 final ordinal population')
    need(sum(r['changed'] for r in audit)==28,'S17 approved change count')
    return [(START,before,after,'scenario17/page-faithful-review')],{
        'reviewed':COUNT,'changed':28,'pages':sum(r['pages'] for r in audit),'records':audit,
        'held_unchanged':[112,126,127,128],'new_glyphs':0,'pool_capacity':len(before),'pool_used':len(packed),
        'selection_sha256':sha(INPUT.read_bytes()),'dictionary_or_code_changed':False}

def verify(source,target,original):
    writes,audit=plan(source,original)
    need(target[START:END]==writes[0][2],'S17 final consumer bytes')
    audit['verified_after_last_writer']=True
    return audit
