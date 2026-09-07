"""Apply the two user-selected edits without rebuilding any other dialogue."""
from pathlib import Path
import hashlib,json
import dialogue_core as dialogue
from muscle_temple_dialogue import split_rows

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'dialogue_editor/user_dialogue_edits_successor278.json'
POOLS=(
    (2,164,0x13A94C,0x13C33A,174,'F13D2B1178A20FF29A503381B8DD50F19C8751DDDF32C81C9822A66EDF4F7ACC'),
    (6,118,0x15A020,0x15B808,123,'5FE6F4FF0A81CB19727A58BB2E9CA3CE38AA19902809113B0CE085CA8D59404C'),
)

def plan(image):
    document=json.loads(INPUT.read_text(encoding='utf8'))
    snapshot=(ROOT/document['source_snapshot']).read_bytes()
    need=dialogue.need
    need(hashlib.sha256(snapshot).hexdigest().upper()==document['source_snapshot_sha256'],
         'User editor snapshot changed')
    saved=json.loads(snapshot)['dialogue_edits']; edits=document['edits']
    need(set(edits)=={'scenario02/dialogue/164','scenario06/dialogue/118'},'User edit scope changed')
    writes=[];audit=[]
    for scenario,index,start,end,count,digest in POOLS:
        before=image[start:end]
        need(hashlib.sha256(before).hexdigest().upper()==digest,'User-edit native pool preimage')
        key=f'scenario{scenario:02d}/dialogue/{index:03d}'
        text=edits[key];need(saved[key]==text,'User-selected wording mismatch')
        need(not dialogue.portrait_layout_inspection(text)['failures'],'User edit layout overflow')
        mapping=dialogue.with_native_ascii(dialogue._s2_encoding_resources()[0]
                     if scenario==2 else dialogue.all_dialogue_private_mapping())
        raw,missing=dialogue.encode_plain(text,mapping)
        need(not missing and b'\0' not in raw,'User edit missing encoding/NUL')
        rows=split_rows(before,count);old=rows[index]; rows[index]=raw
        packed=b''.join(r+b'\0' for r in rows)
        need(len(packed)<=len(before),'User edit pool capacity')
        after=packed.ljust(len(before),b'\0')
        need(split_rows(after,count)==rows,'User edit ordinal round trip')
        writes.append((start,before,after,'user-dialogue/'+key))
        audit.append({'id':key,'text':text,'old_hex':old.hex(),'new_hex':raw.hex(),
                      'other_records_byte_identical':count-1,'pool_bytes':len(packed),
                      'pool_capacity':len(before),'all_dictionaries_untouched':True})
    return writes,audit

def verify(source,target):
    writes,audit=plan(source)
    for offset,before,after,name in writes:
        dialogue.need(target[offset:offset+len(after)]==after,name+' final bytes')
    return audit
