"""Preserve the empty CN records that the native condition window still reads.

The native caller reads one-based rows 1,4,5,6,2,3,7,8; its alternate branch
uses 9..13 for scenarios 21,55,60. E14C scans NULs without a section bound.
Missing empty records therefore expose the following presentation's controls.
Grow only the condition section into the presentation's post-terminator
padding, using the existing forward-repack policy. Preserve every script byte
through its terminator and every section-8-and-later address.
"""
from pathlib import Path
import hashlib, json, struct

ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/'analysis/r80-field-load-popup-resource-discovery-20260817.json'
ALTERNATE_SCENARIOS=frozenset((21,55,60))
CALLER_OFFSET=0x1C8A8
CALLER_SIZE=0x16E
CALLER_SHA='97d36eb91d549f9f341651448f6d3c20a2d9eb53920c4f940aba2fa54a6a40bb'
MIRROR=0x277DB000

def required_records(scenario):
    return 13 if scenario in ALTERNATE_SCENARIOS else 8

def need(ok,message):
    if not ok: raise ValueError(message)

def containers(image):
    rows=json.loads(CATALOG.read_text(encoding='utf8'))['resources']
    need(len(rows)==105,'Resource population drift')
    for index,row in enumerate(rows[:98],1):
        header=int(row['header'],0)
        offsets=struct.unpack_from('<9I',image,header)
        need(offsets[0]==0x24 and all(x<=y for x,y in zip(offsets,offsets[1:])),
             f'Field container {index}')
        a,b,c=(header+offsets[n] for n in (6,7,8))
        need(image[a:a+2] in (b'\x04\x1c',b'\x04\x02'),f'Condition header {index}')
        yield index,header,offsets,a,b,c
    # Last seven catalog members have different roles: two 8-section ending
    # containers and five special partial containers, not the field CN family.
    need(all(len(row['section_offsets'])==8 for row in rows[98:100]),'Ending containers')
    need(all(row['section_offsets'][1]==row['section_offsets'][2]
             for row in rows[100:]),'Partial container exclusions')

def required_rows(block,number):
    """Model the native one-based NUL scan; do not count padding as optional."""
    rows=[];start=0
    for index in range(number):
        end=block.find(b'\0',start)
        need(end>=0,f'Native row {index+1} reads beyond CN section')
        rows.append(block[start:end]);start=end+1
    return rows

def repack(block,presentation,minimum):
    need(block.endswith(b'\0'),'Condition record terminator')
    missing=max(0,minimum-block.count(0))
    if not missing: return 0,presentation
    growth=(missing+3)&~3
    # PAGE 06 07, then presentation terminator 00, then inert zeros. No
    # removed byte may be part of a page, token, or visible spacing glyph.
    live=presentation.rstrip(b'\0')
    need(live.endswith(b'\x06\x07'),'Unrecognized presentation suffix')
    need(len(presentation)-len(live)>=growth+1,'No post-terminator capacity')
    shifted=bytes(growth)+presentation[:-growth]
    need(shifted[growth:][:len(live)+1]==presentation[:len(live)+1],
         'Presentation control/text bytes changed')
    required_rows(block+bytes(growth),minimum)
    return growth,shifted

def verify(image):
    for bias in (0,MIRROR):
        code=image[bias+CALLER_OFFSET:bias+CALLER_OFFSET+CALLER_SIZE]
        need(hashlib.sha256(code).hexdigest()==CALLER_SHA,'Native row-selector changed')
    checked=[]
    for scenario,header,offsets,start,end,limit in containers(image):
        required_rows(image[start:end],required_records(scenario))
        checked.append(scenario)
    return {'condition_tables':len(checked),'normal_one_based_rows':[1,4,5,6,2,3,7,8],
            'alternate_one_based_rows':[1,9,10,11,2,3,12,13],
            'alternate_scenarios':sorted(ALTERNATE_SCENARIOS),'out_of_section_reads':0}

def plan(image):
    # Pin the consumer that owns the record count before planning data writes.
    for bias in (0,MIRROR):
        need(hashlib.sha256(image[bias+CALLER_OFFSET:bias+CALLER_OFFSET+CALLER_SIZE]).hexdigest()
             ==CALLER_SHA,'Native row-selector preimage')
    writes=[];changed=[]
    for scenario,header,offsets,start,end,limit in containers(image):
        block=image[start:end];presentation=image[end:limit]
        growth,replacement=repack(block,presentation,required_records(scenario))
        if not growth:continue
        writes.append((header+28,struct.pack('<I',offsets[7]),
            struct.pack('<I',offsets[7]+growth),f'condition/section7-pointer/{scenario:02d}'))
        writes.append((end,presentation,replacement,f'condition/empty-records-and-presentation/{scenario:02d}'))
        changed.append({'scenario':scenario,'records_before':block.count(0),
            'required_records':required_records(scenario),'restored_empty_bytes':growth,
            'section7_from':hex(end),'section7_to':hex(end+growth),
            'section8_unchanged':hex(limit),'preserved_live_presentation_bytes':len(presentation.rstrip(b'\0'))+1})
    writes.sort()
    for a,b in zip(writes,writes[1:]):
        need(a[0]+len(a[1])<=b[0],'Overlapping condition writers')
    return writes,{'changed_tables':changed,'code_or_font_changes':False,
        'section5_and_condition_text_unchanged':True,'all_visible_presentation_bytes_unchanged':True}
