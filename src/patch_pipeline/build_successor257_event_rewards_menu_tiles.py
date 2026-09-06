"""Data-only successor256 fixes: event reward terminator, Leard, menu tiles.

The shared native reward formatter does not accept ASCII 0x21 as punctuation.
Its seven-byte record cannot grow without moving unrelated common entries.
Use the already supported line-end control 08 after '입수'; do not introduce
an additional NUL, 05 filler, new dictionary slot, or executable hook.
Menu cells are rebound only in their existing owner and dependent BAT rows.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'dialogue_editor'),str(ROOT/'tools')]
import dialogue_core as dialogue

SOURCE_STEM='r80-successor252-item-font-kram-s1-movie-latch-successor256'
STEM='r80-successor256-event-reward-menu-tiles-successor257'
SOURCE=ROOT/'work'/SOURCE_STEM
OUT=ROOT/'work'/STEM
SOURCE_SHA={
    'cooked':'1B599EDE45BEFC468479802E6043F64774938CA99CF8B2003B158D750F4263EB',
    'raw':'91632937F7BD36DD379F750D42BD6CA457B9F316689010535DF2B0273FD992C3',
    'cue':'7E1992295EE34F2E22A0A1A2CF565F784C1E812CD6B5F7169F9360ACD4ED1225',
}
REWARD_OFFSETS=tuple(int(x,16) for x in '''
12f37a 137316 13e506 14637a 14dc12 1569ea 15d5aa 16500e 16bb56 1728fa
1793de 18111e 1873ee 18f01e 196a3a 19f8f2 1a6522 1ac872 1b2a9a 1ba23e
1c0942 1c6fc2 1cc91e 1d30d2 1d98c2 1e06b6 1e61ee 1ee082 1f4fa6 1fba62
20360a 2097c6 20f626 2157c6 21b13a 2218e2 2283b2 230122 23687a 23d52e
245b92 24db8a 2550ae 25b9ea 262ac2 269b06 27213a 27877e 27f1f2 285ab6
28c806 29325e 29afde 2a113a 2a7a96 2ae8f6 2b4f7e 2bb086 2c193e 2c8286
2cf062 2d511e 2db902 2e2812 2e89c2 2ef202 2f57c6 2fb92a 3021ce 3093f2
310762 3166e6 31c12a 322932 328f8e 32f9de 3362b2 33d29a 34430e 34cb76
354ad2 35bd5e 36285a 368b5e 36fdfe 377282 37f136 3869be 38ebbe 396ff2
39d38e 3a338e 3a938e 3af38e 3b538e 3bb38e 3c138e 3c7bd2 3cfefa 3d54de
3ddb0e 3e4c96 3ed39e 3f5b66 3fcb66
'''.split())
REWARD_BEFORE=bytes.fromhex('02F1DFF0E62100')
REWARD_AFTER=bytes.fromhex('02F1DFF0E60800')
SLOT_OFFSETS=(0x0192AE08,0x019AEE08,0x2731FE08,0x273ABE08,
              0x2742A608,0x274BE608,0x27549E08,0x275FDE08)
SLOT_SHA='84B9583F1AC2F862123C8CC6B2AC3CC6EB482CA77E6B7FAB4A79B137C3BE73E8'
MENU_REBIND={0x59B:0xED7,0x8EA:0xED8}

def sha(data): return hashlib.sha256(data).hexdigest().upper()
def file_sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest().upper()
def need(ok,message):
    if not ok: raise RuntimeError(message)

def rebind_menu(data, mapping=MENU_REBIND):
    need(len(data)==1024,'menu extent')
    h=struct.unpack_from('<12I',data)
    need(h[0]==0x45334B53 and h[2]==0x000A0042 and h[3]==0x00320030,
         'menu structural profile')
    codes=struct.unpack_from('<66H',data,48)
    need(len(set(codes))==66 and not set(mapping.values())&set(codes),
         'menu destination ownership')
    output=bytearray(data)
    for old,new in mapping.items():
        need(codes.count(old)==1,'menu source ownership')
        struct.pack_into('<H',output,48+codes.index(old)*2,new)
        hits=0
        for row in range(10):
            for col in range(12):
                off=48+66*2+row*50+26+col*2
                word=struct.unpack_from('<H',data,off)[0]
                if word&4095==old:
                    struct.pack_into('<H',output,off,(word&0xf000)|new)
                    hits+=1
        need(hits==1,f'menu dependent owner count {old:X}: {hits}')
    return bytes(output)

def planned_writes(source):
    writes=[]
    def add(off,before,after,owner):
        need(len(before)==len(after) and source[off:off+len(before)]==before,
             f'preimage {owner}@{off:X}')
        writes.append((off,before,after,owner))
    need(len(REWARD_OFFSETS)==105 and len(set(REWARD_OFFSETS))==105,'reward population')
    for ordinal,off in enumerate(REWARD_OFFSETS):
        add(off,REWARD_BEFORE,REWARD_AFTER,f'event/item-acquired/replica/{ordinal:03d}')
    for i,off in enumerate(SLOT_OFFSETS):
        pre=source[off:off+1024]
        need(sha(pre)==SLOT_SHA,f'menu replica {i} identity')
        add(off,pre,rebind_menu(pre),f'menu/tile-owners/{i}')
    corrections=dialogue.load_json(ROOT/'dialogue_editor/dialogue_user_corrections.json')['corrections']
    records={r.id:r for r in dialogue.load_records()}
    cursor=dialogue.S2_DIALOGUE_START
    rows=[]
    for i in range(dialogue.S2_DIALOGUE_RECORDS):
        end=source.index(0,cursor,dialogue.S2_DIALOGUE_END)
        rows.append((cursor,source[cursor:end]));cursor=end+1
    for key,change in corrections.items():
        record=records[key]; index=int(key.rsplit('/',1)[1])
        old=dialogue.encode_for_record(record,change['before'],source)
        new=dialogue.encode_for_record(record,change['after'],source)
        offset,current=rows[index]
        need(current==old,f'{key}: ordinal boundary / encoding')
        add(offset,old,new,key)
    writes.sort()
    for a,b in zip(writes,writes[1:]):
        need(a[0]+len(a[1])<=b[0],'overlapping owners')
    return writes

def main():
    need(not OUT.exists(),'immutable output already exists')
    files={'cooked':SOURCE/f'track02-{SOURCE_STEM}.iso',
           'raw':SOURCE/f'Track-2.{SOURCE_STEM}.bin',
           'cue':SOURCE/f'Langrisser-FX-KR-{SOURCE_STEM}.cue'}
    for role,path in files.items(): need(file_sha(path)==SOURCE_SHA[role],f'source identity {role}')
    source=files['cooked'].read_bytes()
    writes=planned_writes(source)
    image=bytearray(source)
    expected=set()
    for off,old,new,owner in writes:
        image[off:off+len(old)]=new
        expected.update(off+i for i,(a,b) in enumerate(zip(old,new)) if a!=b)
    # Chunked full-image diff independently excludes all unplanned changes.
    actual=set(); step=1<<20
    for base in range(0,len(source),step):
        a=source[base:base+step];b=image[base:base+step]
        if a!=b: actual.update(base+i for i,(x,y) in enumerate(zip(a,b)) if x!=y)
    need(actual==expected and len(source)==len(image),'full diff does not equal write plan')
    OUT.mkdir(parents=True)
    cooked=OUT/f'track02-{STEM}.iso';raw=OUT/f'Track-2.{STEM}.bin';cue=OUT/f'Langrisser-FX-KR-{STEM}.cue'
    cooked.write_bytes(image)
    sectors=sorted({o//2048 for o in expected})
    raw_audit=dialogue._repair_raw(cooked,files['raw'],raw,sectors)
    for name in ['Track-1.bin','Track-3.bin','subtitle-payload.bin']:
        shutil.copyfile(SOURCE/name,OUT/name)
        need(file_sha(SOURCE/name)==file_sha(OUT/name),f'protected {name}')
    cue.write_text(files['cue'].read_text(encoding='ascii').replace(files['raw'].name,raw.name),
                   encoding='ascii',newline='')
    report={
        'schema':'langrisser-fx-successor257-event-fixes/v1','status':'BUILT_STATIC_RUNTIME_REQUIRED',
        'source':SOURCE_SHA,'source_stem':SOURCE_STEM,
        'changed_bytes':len(actual),'changed_sectors':sectors,'raw_audit':raw_audit,
        'writes':[{'offset':o,'bytes':len(a),'owner':n,'before_sha256':sha(a),'after_sha256':sha(b)}
                  for o,a,b,n in writes],
        'hidden_event_catalog':{
            'id':'text/66b7b221a39662f9','kind':'dynamic_item_acquisition',
            'replicas':105,'scope':'all item IDs, enemy drops and event rewards through common record 48',
            'before_hex':REWARD_BEFORE.hex(),'after_hex':REWARD_AFTER.hex(),
            'text':'{item} 입수','native_line_end_control':8,'nul_count_unchanged':True,
            'following_common_records_unchanged':True,
            'separate_from_shop_tooltips':True,
        },
        'menu_rebind':{f'{a:03X}':f'{b:03X}' for a,b in MENU_REBIND.items()},
        'protected':{'executable_code_byte_exact':True,'movie_payload_byte_exact':True,
                     'shop_names_and_tooltips_byte_exact':True,'glyph_bitmaps_byte_exact':True,
                     'unrelated_dialogue_byte_exact':True},
        'outputs':{k:{'path':p.name,'sha256':file_sha(p)} for k,p in
                   [('cue',cue),('cooked',cooked),('raw',raw)]},
        'runtime_verified':False,
    }
    (OUT/'event-fixes-build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'cue':str(cue),'changed_bytes':len(actual)},ensure_ascii=False))

if __name__=='__main__':main()
