"""Separate SYSTEM MENU '턴' from the native 16x16 X bottom-right tile.

No bitmap or executable changes. Rebind one scatter owner and its one BAT
dependent in all ten resident Slot-A replicas, including the two current
Resource-12 loader targets. The
native X1/X2/X3 cell, title numeric formatting and save data remain untouched.
"""
from pathlib import Path
import hashlib, json, struct

ROOT=Path(__file__).resolve().parents[1]
SLOTS=(0x0192AE08,0x019AEE08,0x2731FE08,0x273ABE08,
       0x2742A608,0x274BE608,0x27549E08,0x275FDE08,0x276A1608,0x27765608)
SIZE=1024
PREIMAGE_SHA='3CAF0726EBA02E48CBB1D9CF2FCCDA30DAC791D155A910ABD1423C8541939EF9'
OLD,NEW=0x697,0xED9
OWNER,DEPENDENT=150,658
AUDIT=ROOT/'analysis/successor281-load-x-ed9-consumers.json'
AUDIT_SHA='30EF9A872D2A75931BB25615B3BF3E61AFC282025BE754A01D0E04FDF91BEDD4'
sha=lambda b:hashlib.sha256(b).hexdigest().upper()

def need(ok,message):
    if not ok:raise RuntimeError(message)

def structure(slot):
    need(len(slot)==SIZE,'Menu slot extent')
    h=struct.unpack_from('<12I',slot)
    need(h[:4]==(0x45334B53,0x10001,0xA0042,0x320030),'Menu structure profile')
    codes=struct.unpack_from('<66H',slot,48)
    need(len(set(codes))==66,'Duplicate menu upload owner')
    return codes

def patch_slot(slot):
    codes=structure(slot)
    need(codes[51]==OLD and codes.count(OLD)==1,'X-overlapping menu owner changed')
    need(NEW not in codes,'Destination already allocated')
    hits=[]
    for row in range(10):
        for col in range(12):
            off=180+row*50+26+col*2
            if struct.unpack_from('<H',slot,off)[0]&0xFFF==OLD:hits.append((row,col,off))
    need(hits==[(9,1,DEPENDENT)],'Menu dependent population changed')
    need(sha(slot)==PREIMAGE_SHA,'Menu slot preimage identity')
    out=bytearray(slot)
    struct.pack_into('<H',out,OWNER,NEW)
    struct.pack_into('<H',out,DEPENDENT,0x4000|NEW)
    need([i for i,(a,b) in enumerate(zip(slot,out)) if a!=b]==
         [OWNER,OWNER+1,DEPENDENT,DEPENDENT+1],'Unexpected menu write')
    need(OLD not in structure(out) and structure(out).count(NEW)==1,'Final owner uniqueness')
    return bytes(out)

def population(image):
    # Magic alone is not a table: require the exact native header geometry.
    header=bytes.fromhex('534B33450100010042000A0030003200')
    found=[];cursor=0
    while (cursor:=image.find(header,cursor))>=0:
        found.append(cursor);cursor+=len(header)
    need(tuple(found)==SLOTS,'Resident menu replica population changed')
    offsets=struct.unpack_from('<17I',image,0x1903800)
    for index,expected in ((2,0x276A1608),(10,0x27765608)):
        need(offsets[index+1]-offsets[index]==0x18800 and
             0x1903800+offsets[index]+0x5E08==expected,'Live Resource-12 menu loader changed')

def reservation():
    raw=AUDIT.read_bytes()
    need(sha(raw)==AUDIT_SHA,'Adopted physical ownership evidence changed')
    audit=json.loads(raw);row=audit['tiles'][0]
    need(audit['states_scanned']==7106 and audit['state_errors']==0,'Consumer audit coverage')
    need(row['tile']=='0xED9' and row['physical_bat_refs']==row['visible_refs']==0,
         'Destination has a BAT consumer')
    need(row['linear_states']==24,'Noncoexisting boot/title evidence changed')
    return {'code':hex(NEW),'audit_sha256':AUDIT_SHA,'states_scanned':7106,
            'physical_bat_references':0,'noncoexisting_boot_title_linear_states':24,
            'scope':'Field menu lifetime; all 24 linear states have no resident Slot-A.'}

def plan(image):
    population(image)
    proof=reservation()
    writes=[]
    for index,offset in enumerate(SLOTS):
        before=image[offset:offset+SIZE]
        writes.append((offset,before,patch_slot(before),f'load-x/menu-owner/{index}'))
    return writes,{'reservation':proof,'replicas':len(SLOTS),'changed_bytes':40,
        'old_owner':hex(OLD),'new_owner':hex(NEW),'menu_glyph':'턴 bottom-right',
        'native_x_bitmap_changed':False,'executable_changed':False,
        'title_load_22_preserved':True,'save_data_changed':False}

def verify(before,after):
    writes,audit=plan(before)
    population(after)
    for off,_,new,_ in writes:need(after[off:off+SIZE]==new,'Final menu slot mismatch')
    return audit
