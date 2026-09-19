"""Fix obsolete Charm labels without modifying spell IDs or glyph ownership."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'analysis/super-mode-review')]
import font_candidate
from build_r80_successor49_canonical_magic_names import CANONICAL

OLD=bytes.fromhex('f0d981408140814000')
NEW=bytes.fromhex('f6df81408140814000')
AV=(0x13103b,0x345fcf,0x3d1bbb)

def offsets(image):
    signature=bytes.fromhex(CANONICAL[0x2b][1]);bases=[];at=0
    while (at:=image.find(signature,at))>=0:
        bases.append(at-0x2b);at+=len(signature)
    assert len(bases)==105,'Common magic table population'
    authority=json.loads((ROOT/'analysis/common_dictionary_replicas_v340_audit.json').read_bytes())
    assert bases==[int(p,0) for p in authority['replica_offsets']]
    return bases

def plan(image):
    assert font_candidate.mapping()['참']==NEW[:2]
    bases=offsets(image)
    for base in bases:
        for rel,(label,h) in CANONICAL.items():
            raw=bytes.fromhex(h)
            assert image[base+rel:base+rel+len(raw)]==raw,(hex(base),label)
    places=sorted([base+0x133 for base in bases]+list(AV))
    found=[];at=0
    while (at:=image.find(OLD,at))>=0:found.append(at);at+=len(OLD)
    assert found==places,'Unexpected legacy Charm record'
    assert len(NEW)==len(OLD) and NEW.count(0)==OLD.count(0)==1
    return [(p,OLD,NEW,f'magic-charm-name/{i:03d}') for i,p in enumerate(places)],dict(
        common_tables=105,magic_names_per_table=26,av_records=3,changed_records=108,
        old_code='F0D9 (증)',new_code='F6DF (참)',japanese='チャーム',
        spell_id_or_learning_logic_changed=False,font_changed=False,
        locations=places,old_hex=OLD.hex(),new_hex=NEW.hex())

def verify(image):
    bases=offsets(image)
    for base in bases:
        for rel,(name,h) in CANONICAL.items():
            raw=NEW if name=='참' else bytes.fromhex(h)
            assert image[base+rel:base+rel+len(raw)]==raw,(hex(base),name)
    for at in AV:assert image[at:at+len(NEW)]==NEW
    assert image.find(OLD)<0
    return {'magic_records_checked':105*26,'av_records_checked':3,'obsolete_charm_records':0}
