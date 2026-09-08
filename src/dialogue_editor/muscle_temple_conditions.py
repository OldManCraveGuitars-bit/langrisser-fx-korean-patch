"""Repair resource 71's CN consumer without editing any shared dictionary.

Original CN row 4 refers to dictionary 0D, whose patched nested 36 now means
"겠습니까?". Row 3 still contains Japanese. Reuse the Korean condition words
already present in this resource's presentation; retain the native dynamic
protagonist token 02. Only the CN and its own section-7 post-terminator capacity
are owned by this writer. Never change dictionary, dialogue, font or game code.
"""
import hashlib
import struct

import condition_menu_boundaries as boundaries
import condition_native_codec as native
import presentation_dictionary as dictionary

RESOURCE=71
HEADER=0x3104F0
SECTIONS=(0x310514,0x310BB4,0x310EA0,0x3119F0,0x3134FC,
          0x313D98,0x3149A4,0x3149BC,0x314AAC)
SOURCE=bytes.fromhex('041c00041d000581450282cc8e80965300040d0000000000')
# The established condition atlas: 적[space]전멸 / [space]사망.
VICTORY=bytes.fromhex('f0d6f1e8f0a4f1bf')
DEATH=bytes.fromhex('f1e8f069f065')
ROWS=(b'\x04\x1c',b'\x04\x1d',b'\x05\x81\x45\x02'+DEATH,
      b'\x05\x81\x45'+VICTORY,b'',b'',b'',b'')

def need(ok,message):
    if not ok:raise ValueError(message)

def encoded_rows():
    return b''.join(r+b'\0' for r in ROWS)

def replacement(block,presentation):
    need(block==SOURCE,'Hidden CN preimage differs; do not overwrite another edit')
    literal=encoded_rows()
    growth=(max(0,len(literal)-len(block))+3)&~3
    live=presentation.rstrip(b'\0')
    need(live.endswith(b'\x06\x07'),'Unknown presentation termination')
    need(len(presentation)-len(live)>=growth+1,'Presentation has insufficient inert capacity')
    need(VICTORY in live and DEATH in live,'Existing Korean condition provenance differs')
    cn=literal.ljust(len(block)+growth,b'\0')
    shifted=presentation[:-growth] if growth else presentation
    need(shifted[:len(live)+1]==presentation[:len(live)+1],'Live presentation was truncated')
    need(tuple(boundaries.required_rows(cn,8))==ROWS,'Native eight-row semantics')
    return growth,cn+shifted

def plan(image):
    need(tuple(HEADER+x for x in struct.unpack_from('<9I',image,HEADER))==SECTIONS,
         'Resource 71 section preimage')
    a,b,c=SECTIONS[6:9]
    growth,payload=replacement(image[a:b],image[b:c])
    need(growth==12,'Unexpected condition extension')
    writes=[(HEADER+28,struct.pack('<I',b-HEADER),struct.pack('<I',b-HEADER+growth),
             'hidden-condition/section7-pointer/71'),
            (a,image[a:c],payload,'hidden-condition/literal-cn-and-preserved-presentation/71')]
    return writes,{'resource':RESOURCE,'user_reported_scenario':22,
        'victory':'적 전멸','defeat':'{raw:02} 사망','dynamic_protagonist_preserved':True,
        'native_records':8,'growth':growth,'section7_to':hex(b+growth),
        'section8_unchanged':hex(c),'presentation_live_sha256':
            hashlib.sha256(image[b:c].rstrip(b'\0')+b'\0').hexdigest(),
        'dictionary_dialogue_font_code_unchanged':True}

def verify(image):
    expected=list(SECTIONS)
    expected[7]+=12
    need(tuple(HEADER+x for x in struct.unpack_from('<9I',image,HEADER))==tuple(expected),
         'Final hidden condition section boundaries')
    a,b,c=expected[6:9]
    need(image[a:b]==encoded_rows().ljust(b-a,b'\0'),'Final native condition payload')
    local=dictionary._split_dictionary(image[expected[4]:expected[5]])
    need(native.expand(ROWS[0],local)==bytes.fromhex('8196f051f04ff052f04e'),
         'Final victory heading dictionary owner')
    need(native.expand(ROWS[1],local)==bytes.fromhex('8196f053f050f052f04e'),
         'Final defeat heading dictionary owner')
    for row in ROWS[2:]:
        need(native.expand(row,local)==row,'Condition body acquired a dictionary dependency')
    need(VICTORY in image[b:c] and DEATH in image[b:c],'Presentation conditions missing')
    return {'native_records':8,'victory_literal_verified':True,'defeat_dynamic_name_verified':True,
            'dictionary_dependencies_in_bodies':0,'section7':hex(b)}

def verify_complement(before,after):
    """Exact 98-field comparison to the frozen immediate predecessor, not v0.81."""
    need(len(before)==len(after),'Output extent changed')
    expected=bytearray(before)
    writes,_=plan(before)
    changed=[]
    for offset,old,new,owner in writes:
        need(expected[offset:offset+len(old)]==old,owner)
        expected[offset:offset+len(new)]=new
        changed.extend(offset+i for i,(a,b) in enumerate(zip(old,new)) if a!=b)
    need(expected==after,'Change outside the declared condition repair')
    verify(after)
    for old,new in zip(boundaries.containers(before),boundaries.containers(after)):
        if old[0]==RESOURCE:continue
        need(old==new,'Another field header changed')
        _,h,o,a,b,c=old
        need(before[h:c]==after[h:c],f'Another field resource changed: {old[0]}')
    return {'compared_field_tables':98,'other_field_tables_byte_identical':97,
            'whole_disc_protected_complement_identical':True,'changed_bytes':len(changed),
            'changed_sectors':sorted({x//2048 for x in changed})}
