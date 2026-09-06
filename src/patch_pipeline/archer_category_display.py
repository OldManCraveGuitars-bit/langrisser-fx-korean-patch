"""Display-only category contract; native unit types and combat parameters stay intact.

Evidence: analysis/successor260-archer-baseline-session. Native E14C counts
every NUL. Gel's extra NUL shifted native categories 113..121 by one.
The private F2B3/F2B4 route now terminates in absent MAIN 1E40C0, while the
canonical resident F17A/F17B cells are loaded and match their pinned rasters.
"""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_SHA = '816B0D8A0FE6CAAFE54EF91A0F2AD8EF892A00B5D8E362D953509A007BA01B9A'
GEL_RELATIVE = 0x4BF
GEL_BEFORE = bytes.fromhex('F0D7050000')
GEL_AFTER = bytes.fromhex('F0D7F1E800')  # one trailing half-width blank, ONE terminator
CATEGORY_FIRST = 0x497
CATEGORY_SOURCE = bytes.fromhex(
    '95E095BA0095E095BA0092B79184008B52946E008B52946E0094F295BA00'
    '95E095BA00908595BA008351838B00968291B000908595BA0095E095BA00'
    '95E095BA0095738E800095738E80008B7C95BA008B7C95BA0097B391B000')
RESIDENT = {
    0xF17A: (0x484D0, bytes.fromhex('3FE0020020027FF0200203FE2022021FC000')),
    0xF17B: (0x484E2, bytes.fromhex('3C27E20831826620020003FE2022021FC000')),
}
TOOLTIP_RELATIVE = 0x11B13  # full R12 subentry + EXT(11800) +313
TOOLTIP_BEFORE = bytes.fromhex('F2B3F09800F095F24E00F051F09800F2B4F09800')
TOOLTIP_AFTER = bytes.fromhex('F17AF09800F095F24E00F051F09800F17BF09800')
ARCHER_UNITS = {
    144:'엘프',145:'엘프',146:'엘프',147:'다크 엘프',
    148:'하이 엘프',149:'하이 엘프',150:'하이 엘프',151:'윗치',
    152:'바리스타',153:'바리스타',154:'바리스타',155:'바리스타',
}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def repair_gel(data):
    need(data == GEL_BEFORE, 'Gel preimage changed')
    need(len(GEL_AFTER) == len(data) and GEL_AFTER.count(0) == 1 and GEL_AFTER[-1] == 0,
         'Gel record boundary contract')
    return GEL_AFTER


def repair_tooltips(data):
    need(data == TOOLTIP_BEFORE, 'Tooltip preimage changed')
    need(len(data) == len(TOOLTIP_AFTER) and
         [i for i,b in enumerate(data) if b == 0] ==
         [i for i,b in enumerate(TOOLTIP_AFTER) if b == 0], 'Tooltip record boundaries')
    return TOOLTIP_AFTER


def roots():
    path = ROOT/'analysis/common_dictionary_replicas_v340_audit.json'
    need(hashlib.sha256(path.read_bytes()).hexdigest().upper() == CATALOG_SHA, 'Common catalog identity')
    doc = json.loads(path.read_text(encoding='utf-8'))
    result = tuple(int(x,16) for x in doc['replica_offsets'])
    need(len(result) == 105 and doc['long_replicas'] == 100, 'Common denominator')
    return result


def resource_starts(image):
    entries = struct.unpack_from('<17I',image,0x1903800)
    lengths = [b-a for a,b in zip(entries,entries[1:])]
    need(lengths.count(0x18800) == 15 and lengths.count(0x2000) == 1, 'Resource-12 loader extent')
    return tuple(0x1903800+a for a,n in zip(entries,lengths) if n == 0x18800)


def plan(image):
    original = (ROOT/'assets/blocks/common-dictionary-source-v340.bin').read_bytes()
    need(original[CATEGORY_FIRST:CATEGORY_FIRST+90] == CATEGORY_SOURCE, 'Japanese category boundary identity')
    writes=[]
    for index,root in enumerate(roots()):
        pos=root+GEL_RELATIVE
        before=image[pos:pos+5]
        writes.append((pos,before,repair_gel(before),f'categories/gel-delimiter/{index:03d}'))
        # A shared first-pool repair, not a change to a troop or a scenario ID.
        cats=bytearray(image[root+CATEGORY_FIRST:root+CATEGORY_FIRST+90])
        rel=GEL_RELATIVE-CATEGORY_FIRST
        cats[rel:rel+5]=GEL_AFTER
        need([i for i,v in enumerate(cats) if v==0] ==
             [i for i,v in enumerate(CATEGORY_SOURCE) if v==0], 'Native category ordinals')
        need(bytes(cats[75:85]) == bytes.fromhex('F17AF09800F17AF09800'), 'Both native archer records')
        need(bytes(cats[65:75]) == bytes.fromhex('F044F06900F044F06900'), 'Undead categories preserved')
        # Before category block, ordinal count already matches Japanese source.
        need(image[root:root+CATEGORY_FIRST].count(0) == original[:CATEGORY_FIRST].count(0),
             'Earlier common record count drift')
    for code,(offset,raster) in RESIDENT.items():
        need(image[offset:offset+18]==raster, f'Resident glyph {code:X} identity')
    for index,start in enumerate(resource_starts(image)):
        pos=start+TOOLTIP_RELATIVE
        before=image[pos:pos+20]
        writes.append((pos,before,repair_tooltips(before),f'categories/resident-tooltip/{index:02d}'))
    return writes


def verify(image):
    for root in roots():
        need(image[root+GEL_RELATIVE:root+GEL_RELATIVE+5] == GEL_AFTER, 'Final Gel delimiter')
    for start in resource_starts(image):
        need(image[start+TOOLTIP_RELATIVE:start+TOOLTIP_RELATIVE+20] == TOOLTIP_AFTER, 'Final tooltip glyph routing')
    for code,(offset,raster) in RESIDENT.items():
        need(image[offset:offset+18]==raster, f'Final resident glyph {code:X}')
    return {'common_copies':105,'active_resource12_copies':15,
            'glyph_bitmaps_changed':False,'executable_code_changed':False,
            'unit_category_and_combat_parameters_changed':False}
