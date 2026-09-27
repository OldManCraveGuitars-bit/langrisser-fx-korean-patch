"""Correct Sherry's shared 8x8 label without reindexing any HUD record.

The historical alphabet has one dedicated '쉐' glyph, referenced only by
record145 (native name ID4). Replace its seven Galmuri rows in all15 banks.
Bottom HUD, recruitment, combat and reports retain their shared IDs/renderer.
"""
import struct
import hud_font_galmuri as font
from bdf_bitmap_glyphs import load_bdf_cell

GLYPH_ID, RECORD_ID, NAME_ID = 170, 145, 4
OFFSET = font.GLYPH1 + (GLYPH_ID-font.SPLIT)*font.ROWS
BEFORE = bytes.fromhex('4A4AAA0AEA5A4A')
AFTER = bytes.fromhex('4A5A4AAABAAA0A')
NAME = '셰리'


def check_payload(payload, expected):
    assert struct.unpack_from('<I',payload,0x29C)[0] == (0x1E23A3<<8)|167
    assert struct.unpack_from('<I',payload,0x2A0)[0] == (0x1E244A<<8)|197
    assert payload[0x3A3+NAME_ID] == RECORD_ID
    records=payload[font.RECORDS:font.RECORDS+font.RECORD_BYTES].split(b'\xff')
    assert len(records)==198 and records[-1]==b''
    assert records[RECORD_ID]==bytes([GLYPH_ID,0x35])
    assert [i for i,r in enumerate(records) if GLYPH_ID in r]==[RECORD_ID]
    assert payload[OFFSET:OFFSET+7]==expected


def plan(image):
    assert font.sha(font.FONT.read_bytes())==font.FONT_SHA
    for char,expected in [('쉐',BEFORE),('셰',AFTER)]:
        rows,_=load_bdf_cell(font.FONT,ord(char),8,8,7,True)
        assert bytes(rows)==expected+b'\0'
    writes=[]
    for i,start in enumerate(font.hud.resource_starts(image)):
        base=start+font.hud.PRIVATE
        check_payload(image[base:base+0x8000],BEFORE)
        writes.append((base+OFFSET,BEFORE,AFTER,f'hud322/sherry/replica/{i:02}'))
    assert len(writes)==15
    return writes


def verify(image):
    starts=font.hud.resource_starts(image)
    for start in starts:
        base=start+font.hud.PRIVATE
        check_payload(image[base:base+0x8000],AFTER)
    return dict(name=NAME,native_name_id=NAME_ID,record_id=RECORD_ID,glyph_id=GLYPH_ID,
        copies=len(starts),font='Galmuri7',font_sha256=font.FONT_SHA,
        other_records_and_glyph_ids_unchanged=True,
        shared_consumers=['bottom HUD','recruitment','combat','battle report'])
