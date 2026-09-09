"""Apply one selected S15 particle without moving any native record boundary."""
import json,struct
from dataclasses import replace
from pathlib import Path
import dialogue_core as dialogue
import condition_native_codec as native
import presentation_dictionary as dictionary
from scenario_dialogue_review import read_cooked,protected_signature,sha
from muscle_temple_dialogue import split_rows,SELECTOR,MIRROR

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'dialogue_editor/user_dialogue_edits_successor293.json'
SOURCE=ROOT/'analysis/scenario15_dialogue_source_v157.json'
KEY='scenario15/dialogue/022'
HEADER,DICT,START,END,COUNT=0x1967C8,0x1997D4,0x19A070,0x19BBD8,144
POOL_SHA='CD54AE8B49F95B794F5E7A7AF4317AC4647788DA7E92A7051199461543EA62CE'
DICT_SHA='D5E47467F3E13A17D6EB4E2BAF50A168BBEC08FD4B2D697A352A32D72179D024'
JP_POOL_SHA='4BB988B9FCD5AC414E7FCDDC39CC0B840EEA5DBD392DB0C8323F532D71D0A844'
JP_DICT_SHA='A58A6F23CCEA3AA9571562C9C508686C7878D9EB51034F8CCA19A9613114AE50'
OLD_ROW=bytes.fromhex('0404048404060802f4400404f1e8f46f0404080901f560f1e804c9f779f4be0444f1ba')
need=dialogue.need

def selected_text():
    doc=json.loads(INPUT.read_text(encoding='utf8'))
    need(set(doc)=={'schema','status','source_snapshot','source_snapshot_sha256','edit_ids'},'S15 selection fields')
    need(doc['schema']=='langrisser-fx-selected-user-dialogue-snapshot/v1'
         and doc['status']=='user_authored_apply_requested' and doc['edit_ids']==[KEY],'S15 selection scope')
    raw=(ROOT/doc['source_snapshot']).read_bytes()
    need(sha(raw)==doc['source_snapshot_sha256'],'S15 snapshot identity')
    return json.loads(raw)['dialogue_edits'][KEY]

def apply_to_editor(records):
    need(sum(r.id==KEY for r in records)==1,'S15 editor identity')
    text=selected_text()
    return [replace(r,base_text=text) if r.id==KEY else r for r in records]

def replace_glyph(row,local,literal,position,expected,replacement):
    need(len(expected)==len(replacement)==2 and row[position:position+2]==expected,'Direct glyph preimage')
    boundaries=[];offset=0
    for token in native.units(row):
        boundaries.append(offset);offset+=len(token)
    need(position in boundaries,'Direct glyph boundary')
    after=row[:position]+replacement+row[position+2:]
    need(native.expand(after,local)==literal,'Exact selected wording mismatch')
    need(protected_signature(native.expand(row,local)+b'\0')==protected_signature(literal+b'\0'),
         'Page/name controls changed')
    return after

def plan(image,original):
    need(sha(image[START:END])==POOL_SHA and sha(image[DICT:START])==DICT_SHA,'S15 immutable pool/dictionary')
    offsets=struct.unpack_from('<9I',image,HEADER)
    need(tuple(HEADER+offsets[i] for i in (4,5,6))==(DICT,START,END),'S15 section boundaries')
    for bias in (0,MIRROR):
        need(image[bias+0x714C:bias+0x714C+len(SELECTOR)]==SELECTOR,'S15 native ordinal selector')
    catalog=json.loads(SOURCE.read_text(encoding='utf8'))['dialogue']
    source=read_cooked(original,START,END-START)
    jpdict=read_cooked(original,DICT,START-DICT)
    need(len(catalog)==COUNT and sha(source)==JP_POOL_SHA and sha(jpdict)==JP_DICT_SHA,'S15 original identity')
    cursor=START
    for i,r in enumerate(catalog):
        raw=bytes.fromhex(r['raw_hex'])
        need(r['id']==f'scenario15/dialogue/{i:03d}' and int(r['cooked_offset'],0)==cursor
             and source[cursor-START:cursor-START+len(raw)]==raw,'S15 original record population')
        cursor+=len(raw)
    need(cursor==END,'S15 original pool extent')
    text=selected_text();layout=dialogue.portrait_layout_inspection(text)
    need(not layout['failures'] and not dialogue._unknown_tokens(text),'S15 layout/control syntax')
    mapping=dialogue.with_native_ascii(dialogue.all_dialogue_private_mapping())
    literal,missing=dialogue.encode_plain(text,mapping)
    need(not missing and b'\0' not in literal,'S15 glyph coverage/NUL')
    jp=native.expand(bytes.fromhex(catalog[22]['raw_hex']),dictionary._split_dictionary(jpdict))
    need(protected_signature(literal+b'\0')==protected_signature(jp),'S15 original page/name controls')
    rows=split_rows(image[START:END],COUNT)
    need(rows[22]==OLD_ROW,'S15 selected record preimage')
    local=dictionary._split_dictionary(image[DICT:START])
    changed=replace_glyph(rows[22],local,literal,8,mapping['가'],mapping['이'])
    address=START+sum(len(r)+1 for r in rows[:22])+8
    audit={'id':KEY,'text':text,'source_snapshot_sha256':json.loads(INPUT.read_text(encoding='utf8'))['source_snapshot_sha256'],
           'write_address':hex(address),'old_hex':mapping['가'].hex(),'new_hex':mapping['이'].hex(),
           'record_before_hex':rows[22].hex(),'record_after_hex':changed.hex(),
           'unchanged_other_records':143,'record_boundaries_unchanged':True,'new_glyphs':0,
           'layout':layout,'original_page_wait_name_controls_preserved':True}
    return [(address,mapping['가'],mapping['이'],'user-dialogue/scenario15-022-particle')],audit

def verify(source,target,original):
    writes,audit=plan(source,original)
    position,before,after,_=writes[0]
    need(target[position:position+2]==after,'S15 final glyph')
    expected=bytearray(source[START:END]);expected[position-START:position-START+2]=after
    need(target[START:END]==expected,'S15 unselected pool bytes changed')
    local=dictionary._split_dictionary(target[DICT:START])
    rows=split_rows(target[START:END],COUNT)
    literal,missing=dialogue.encode_plain(selected_text(),dialogue.with_native_ascii(dialogue.all_dialogue_private_mapping()))
    need(not missing and native.expand(rows[22],local)==literal,'S15 final selected wording')
    audit['verified_after_last_writer']=True
    return audit
