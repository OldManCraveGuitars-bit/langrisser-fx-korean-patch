"""Apply the four exact user-authored S7 records; preserve all shared owners."""
from pathlib import Path
import hashlib,json,struct
import dialogue_core as dialogue
import condition_native_codec as native
import presentation_dictionary as dictionary
from muscle_temple_dialogue import split_rows,SELECTOR,MIRROR

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'dialogue_editor/user_dialogue_edits_successor281.json'
HEADER=0x15D338
START,END,COUNT=0x160BE0,0x1635EC,242
PREIMAGE_SHA='D490438EA78C02E49A5EE4AF30C32D57281ABB3AF0CCB6D9FBC7F19CEE6A06D6'
SOURCE=ROOT/'analysis/scenario07_dialogue_source_original.json'
SOURCE_SHA='D0746C3218171B7B2449DB7C403BFE3CE2A0D506497D7250128D2381B0B08BBD'
IDS=tuple(f'scenario07/dialogue/{n:03d}' for n in (187,189,193,200))
need=dialogue.need
sha=lambda raw:hashlib.sha256(raw).hexdigest().upper()

def selected_texts():
    doc=json.loads(INPUT.read_text(encoding='utf8'))
    need(doc['schema']=='langrisser-fx-selected-user-dialogue-snapshot/v1'
         and doc['status']=='user_authored_apply_requested','User input policy')
    raw=(ROOT/doc['source_snapshot']).read_bytes()
    need(sha(raw)==doc['source_snapshot_sha256'],'User snapshot identity')
    need(tuple(doc['edit_ids'])==IDS,'Selected S7 edit population')
    edits=json.loads(raw)['dialogue_edits']
    return {key:edits[key] for key in IDS}

def topology(raw):
    pages=[[]]
    for token in native.units(raw):
        if token==b'\x06':pages.append([])
        elif token[0] in (2,9):pages[-1].append(token.hex())
    return pages

def pack(before,local,texts):
    need(set(texts)==set(IDS),'Unexpected user edit IDs')
    rows=split_rows(before,COUNT)
    mapping=dialogue.with_native_ascii(dialogue.all_dialogue_private_mapping())
    audit=[]
    for key,text in texts.items():
        index=int(key.rsplit('/',1)[1])
        need(not dialogue._unknown_tokens(text),key+' unknown control')
        layout=dialogue.portrait_layout_inspection(text)
        need(not layout['failures'],key+' layout overflow')
        raw,missing=dialogue.encode_plain(text,mapping)
        need(not missing and b'\0' not in raw,key+' unrepresentable glyph/NUL')
        previous=rows[index]
        plain=native.expand(previous,local)
        need(topology(plain)==topology(raw),key+' voice-page/dynamic-name topology changed')
        need(native.expand(raw,local)==raw,key+' unexpected phrase dependency')
        rows[index]=raw
        audit.append({'id':key,'selected_text':text,'before_raw_hex':previous.hex(),
            'before_plain_hex':plain.hex(),'after_raw_hex':raw.hex(),'layout':layout,
            'pages_and_names_preserved':True})
    packed=b''.join(r+b'\0' for r in rows)
    need(len(packed)<=len(before),'S7 native pool capacity overflow')
    after=packed.ljust(len(before),b'\0')
    need(split_rows(after,COUNT)==rows,'S7 ordinal re-extraction mismatch')
    return after,{'records':audit,'unchanged_records':COUNT-len(texts),
        'pool_capacity':len(before),'pool_used':len(packed),'remaining_padding':len(before)-len(packed),
        'new_glyphs':0,'dictionary_or_section_writes':False}

def plan(image):
    need(sha(image[START:END])==PREIMAGE_SHA,'S7 immutable pool preimage')
    offsets=struct.unpack_from('<9I',image,HEADER)
    need(HEADER+offsets[5]==START and HEADER+offsets[6]==END,'S7 section boundary')
    for bias in (0,MIRROR):
        need(image[bias+0x714C:bias+0x714C+len(SELECTOR)]==SELECTOR,'Native ordinal consumer')
    source=json.loads(SOURCE.read_text(encoding='utf8'))
    original=[r for r in source['dialogue'] if int(r['cooked_offset'],0)<END]
    need(len(original)==COUNT and sha(b''.join(bytes.fromhex(r['raw_hex']) for r in original))==SOURCE_SHA,
         'S7 source population/bytes changed')
    local=dictionary._split_dictionary(image[HEADER+offsets[4]:START])
    after,audit=pack(image[START:END],local,selected_texts())
    return [(START,image[START:END],after,'user-dialogue/scenario07-selected-four')],audit

def verify(before,after):
    writes,audit=plan(before)
    need(after[START:END]==writes[0][2],'Final selected S7 bytes')
    return audit

def verify_complement(before,after):
    need(len(before)==len(after),'Disc extent changed')
    verify(before,after)
    need(before[:START]==after[:START] and before[END:]==after[END:],
         'Data outside S7 dialogue pool changed')
    old=split_rows(before[START:END],COUNT);new=split_rows(after[START:END],COUNT)
    changed=[i for i in range(COUNT) if old[i]!=new[i]]
    need(changed==[187,189,193,200],'Another S7 record changed')
    byte_changes=[START+i for i,(x,y) in enumerate(zip(before[START:END],after[START:END])) if x!=y]
    return {'records_changed':changed,'other_records_identical':COUNT-4,
        'all_other_disc_bytes_identical':True,'changed_bytes':len(byte_changes),
        'changed_sectors':sorted({x//2048 for x in byte_changes})}
