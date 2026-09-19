"""Repair inventory prompts within the five existing NUL-delimited roots.

Native 05 advances without clearing a glyph. The previous final root included
05 as byte-allocation filler: the CN mapper exposed stale graphics at that
position. All new spaces are drawable resident F1E8; no padding is rendered.
Names, item IDs, native ordinals, subsequent roots and the 89-byte scope stay.
"""
import inventory_full_prompts as prior
import dialogue_core as d
import condition_native_codec as nc

TEXTS=('아이템이 가득합니다','하나 버려주세요','버릴 것을 고르세요',
       '{item} 버립니다.','{item} 버렸습니다.')

def compiled():
    rows=[]
    for text in TEXTS:
        chunks=[]
        for part in text.split('{item}'):
            raw,missing=d.encode_plain(part,d.with_native_ascii(d.all_dialogue_private_mapping()))
            d.need(not missing,'Inventory glyphs '+str(missing));chunks.append(raw)
        row=b'\x02'.join(chunks)
        d.need(all(t[0] not in (0,1,3,4,5,6,7,8,9) for t in nc.units(row)),'Inventory control')
        rows.append(row)
    result=b'\0'.join(rows)+b'\0'
    d.need(len(result)==89 and result.count(0)==5,'Inventory exact allocation')
    return result,rows

def plan(image):
    before=prior.compiled()[0];after,rows=compiled();positions=[];at=0
    while (at:=image.find(before,at))>=0:positions.append(at);at+=len(before)
    d.need(len(positions)==105,'Inventory replicas expected 105, got '+str(len(positions)))
    return [(p,before,after,f'inventory-discard-safe/{i:03d}') for i,p in enumerate(positions)],dict(
        replicas=105,roots_per_replica=5,allocation=89,texts=TEXTS,control05_removed=True,
        final_padding_removed=True,dynamic_item_tokens=2,game_logic_changed=False,
        rows_hex=[r.hex() for r in rows],positions=positions)
