"""Compose the saved S15 layout edits with the prior particle in one pool owner.

Native ordinal selection and the fixed pool/dictionary extents were established
by the S15 profile. Unselected compressed records are retained byte-for-byte;
only selected rows are recompressed. No dictionary, font or event code changes.
"""
import json
from dataclasses import replace
import dialogue_core as dialogue
import condition_native_codec as native
import presentation_dictionary as dictionary
import scenario15_user_dialogue as prior

ROOT=prior.ROOT
INPUT=ROOT/'dialogue_editor/user_dialogue_edits_successor294.json'
KEYS=('scenario15/dialogue/116','scenario15/dialogue/131')
need=dialogue.need


def selected_texts():
    doc=json.loads(INPUT.read_text(encoding='utf8'))
    need(set(doc)=={'schema','status','source_snapshot','source_snapshot_sha256','edit_ids'},
         'S15 additional selection fields')
    need(doc['schema']=='langrisser-fx-selected-user-dialogue-snapshot/v1'
         and doc['status']=='user_authored_apply_requested' and doc['edit_ids']==list(KEYS),
         'S15 additional selection scope')
    raw=(ROOT/doc['source_snapshot']).read_bytes()
    need(prior.sha(raw)==doc['source_snapshot_sha256'],'S15 additional snapshot identity')
    edits=json.loads(raw)['dialogue_edits']
    need(all(isinstance(edits.get(k),str) and edits[k] for k in KEYS),'S15 additional text missing')
    return {k:edits[k] for k in KEYS}


def apply_to_editor(records):
    selected=selected_texts()
    need(all(sum(r.id==k for r in records)==1 for k in selected),'S15 additional editor IDs')
    return [replace(r,base_text=selected[r.id]) if r.id in selected else r for r in records]


def pack_selected(before,local,count,selected,original_controls):
    """Repack established ordinal rows; reject controls, overflow and lost rows."""
    rows=prior.split_rows(before,count)
    need(set(selected)==set(original_controls),'Selected controls denominator')
    need(all(type(i) is int and 0<=i<count for i in selected),'Selected ordinal out of range')
    result=list(rows)
    for i,literal in selected.items():
        need(b'\0' not in literal,'Selected text includes NUL')
        need(prior.protected_signature(literal+b'\0')==prior.protected_signature(original_controls[i]),
             f'S15 original page/name controls: {i}')
        result[i]=native.compress(literal,local)
        need(native.expand(result[i],local)==literal,f'S15 selected round trip: {i}')
    packed=b''.join(r+b'\0' for r in result)
    need(len(packed)<=len(before),'S15 ordinal pool overflow')
    after=packed.ljust(len(before),b'\0')
    need(prior.split_rows(after,count)==result,'S15 native ordinal reparse')
    for i,(a,b) in enumerate(zip(rows,result)):
        if i not in selected:
            need(a==b,f'S15 unselected record changed: {i}')
    return after


def plan(image,original):
    # The predecessor is a declared derivation, not an old product input. Fold
    # it into the final pool owner before registering any cumulative write.
    old_writes,previous_audit=prior.plan(image,original)
    before=image[prior.START:prior.END]
    composed=bytearray(before)
    for address,expected,value,_ in old_writes:
        start=address-prior.START
        need(0<=start and start+len(value)<=len(before) and composed[start:start+len(expected)]==expected,
             'S15 predecessor composition')
        composed[start:start+len(expected)]=value
    catalog=json.loads(prior.SOURCE.read_text(encoding='utf8'))['dialogue']
    jpdict=dictionary._split_dictionary(prior.read_cooked(original,prior.DICT,prior.START-prior.DICT))
    local=dictionary._split_dictionary(image[prior.DICT:prior.START])
    mapping=dialogue.with_native_ascii(dialogue.all_dialogue_private_mapping())
    selected={};controls={};records=[]
    for key,text in selected_texts().items():
        i=int(key.rsplit('/',1)[1])
        need(not dialogue._unknown_tokens(text),key+' unknown token')
        literal,missing=dialogue.encode_plain(text,mapping)
        need(not missing,key+' missing glyphs: '+str(missing))
        jp=native.expand(bytes.fromhex(catalog[i]['raw_hex']),jpdict)
        layout=dialogue.portrait_layout_inspection(text)
        pages=1+sum(t==b'\x06' for t in native.units(jp))
        need(not layout['failures'] and layout['screens']==layout['voice_pages']==pages,
             key+' page geometry: '+str(layout['failures']))
        selected[i]=literal;controls[i]=jp
        records.append({'id':key,'text':text,'layout':layout,'original_pages':pages,
                        'expanded_sha256':prior.sha(literal),'original_controls_preserved':True})
    after=pack_selected(bytes(composed),local,prior.COUNT,selected,controls)
    rows=prior.split_rows(after,prior.COUNT)
    old_literal,missing=dialogue.encode_plain(prior.selected_text(),mapping)
    need(not missing and native.expand(rows[22],local)==old_literal,'S15 prior edit lost')
    audit={'records':records,'preserved_predecessor':previous_audit,'records_in_pool':prior.COUNT,
           'unselected_records_preserved_from293':prior.COUNT-len(selected),
           'pool_capacity':len(before),'pool_used':sum(len(r)+1 for r in rows),
           'new_glyphs':0,'dictionary_or_font_or_code_changed':False,
           'input_sha256':prior.sha(INPUT.read_bytes()),'distribution_allowed':False}
    return [(prior.START,before,after,'scenario15/selected-user-dialogue-pool')],audit


def verify(source,target,original):
    writes,audit=plan(source,original)
    need(target[prior.START:prior.END]==writes[0][2],'S15 final selected pool differs')
    need(target[prior.DICT:prior.START]==source[prior.DICT:prior.START],'S15 dictionary changed')
    audit['verified_after_last_writer']=True
    return audit
