"""Keep all 46 native unit-cache slots separate from Korean menu glyphs.

This is a data-only successor286 specification. It composes the earlier X
repair against the immutable v0.81 baseline, then rebinds six scatter entries
and their exact BAT dependents. Neither pixels, machine code, native class
data, dialogue, nor the native cache's addressing rule are changed.
"""
import hashlib
import json
from pathlib import Path
import struct

import load_x_menu_tile as previous

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'analysis/successor286-menu-pool-physical-consumers.json'
AUDIT_SHA = 'F0A9262EEF92D1B718281832DA1960FB039ABCBE1A0A19EEF79EAE4FCE019FC7'
SLOTS_A = previous.SLOTS
SLOTS_C = tuple(p + 0x8000 for p in SLOTS_A)
SIZE = 1024
C_HEADER = bytes.fromhex('0d004353c33ca55a40bd1e004aa108f6')
C_SHA = '27273643568A9B80B0FCC9BD68BFF144F08944BEFFFC75A6186C24CA93A0B810'
REMAP = {0x96D: 0xEDA, 0x9AB: 0xEDB, 0x99B: 0xEDC,
         0x99C: 0xEDD, 0x9AC: 0xEDE, 0x9B3: 0xEDF}
A_UPLOAD = {154: 0x96D, 160: 0x9AB, 172: 0x99B, 174: 0x99C,
            176: 0x9AC, 178: 0x9B3}
A_BAT = {616: 0x96D, 668: 0x9AB}
C_BAT = {746: 0x99B, 830: 0x99B, 914: 0x99B,
         748: 0x99C, 832: 0x99C, 916: 0x99C,
         788: 0x9AC, 872: 0x9AC, 956: 0x9AC,
         790: 0x9B3, 874: 0x9B3, 958: 0x9B3}
UNIT_FIRST, UNIT_SLOTS, TILES_PER_UNIT = 0x8A0, 46, 9
UNIT_END = UNIT_FIRST + UNIT_SLOTS * TILES_PER_UNIT  # exclusive 0xA3E
MIRROR = 0x277DB000
NATIVE = ((0x13B08, 0x198,
           '673F54CE8C3144B34F30CE35DB1061B17FE72EE50D994ECF4BD500D143FF7E69'),
          (0x14100, 0xA8,
           '3BD10B08B1CA3EC21A5BDF7622BAF083EBB2EE7A1651D8A7D27924D391BAB858'))
sha = lambda b: hashlib.sha256(b).hexdigest().upper()
need = previous.need


def patch_words(source, owners, palette=0):
    out = bytearray(source)
    for offset, old in owners.items():
        need(struct.unpack_from('<H', source, offset)[0] == palette | old,
             f'Changed dependent at {offset:#x}')
        struct.pack_into('<H', out, offset, palette | REMAP[old])
    return bytes(out)


def patch_a(source):
    # Earlier X repair remains a first-class part of this composed writer.
    out = previous.patch_slot(source)
    codes = previous.structure(out)
    intersect = {c for c in codes if UNIT_FIRST <= c < UNIT_END}
    need(intersect == set(REMAP), 'Unexpected native-unit/menu overlap')
    need(not set(codes) & set(REMAP.values()), 'Reserved menu destination occupied')
    found = {}
    for row in range(10):
        for col in range(12):
            off = 180 + row * 50 + 26 + col * 2
            code = struct.unpack_from('<H', out, off)[0] & 0xFFF
            if code in REMAP:
                found[off] = code
    need(found == A_BAT, 'Menu BAT dependent population changed')
    out = patch_words(patch_words(out, A_UPLOAD), A_BAT, 0x4000)
    final = previous.structure(out)
    need(not any(UNIT_FIRST <= c < UNIT_END for c in final),
         'A menu upload still touches a native unit-cache slot')
    return out


def patch_c(source):
    need(len(source) == SIZE and sha(source) == C_SHA, 'Settings Slot-C identity')
    found = {off: struct.unpack_from('<H', source, off)[0] & 0xFFF
             for off in range(0, SIZE, 2)
             if struct.unpack_from('<H', source, off)[0] in
             {0x4000 | old for old in REMAP}}
    need(found == C_BAT, 'Settings BAT dependent population changed')
    return patch_words(source, C_BAT, 0x4000)


def population(image):
    previous.population(image)
    found, cursor = [], 0
    while (cursor := image.find(C_HEADER, cursor)) >= 0:
        found.append(cursor)
        cursor += len(C_HEADER)
    need(tuple(found) == SLOTS_C, 'Settings replica population changed')
    for bias in (0, MIRROR):
        for start, size, digest in NATIVE:
            need(sha(image[bias + start:bias + start + size]) == digest,
                 'Native unit cache allocation/loader code changed')
    return {'menu_replicas': len(SLOTS_A), 'settings_replicas': len(SLOTS_C),
            'native_loader_copies': 2, 'maximum_unit_cache_slots': UNIT_SLOTS,
            'tiles_per_slot': TILES_PER_UNIT, 'protected_tile_count': UNIT_END - UNIT_FIRST,
            'native_tile_range_inclusive': [hex(UNIT_FIRST), hex(UNIT_END - 1)]}


def reservation():
    raw = AUDIT.read_bytes()
    need(sha(raw) == AUDIT_SHA, 'Physical consumer audit identity')
    audit = json.loads(raw)
    need(audit['states_scanned'] == 7801 and audit['state_errors'] == 0,
         'Physical audit denominator changed')
    by_code = {int(row['tile'], 0): row for row in audit['tiles']}
    linear_paths = None
    for code in REMAP.values():
        row = by_code[code]
        need(row['physical_bat_refs'] == row['visible_refs'] == 0,
             'New destination has another physical BAT consumer')
        need(row['linear_states'] == 24, 'Linear consumer population changed')
        paths = set(row['state_paths'])
        if linear_paths is None:
            linear_paths = paths
        need(paths == linear_paths and len(paths) == 24, 'Linear lifetime differs')
    from verify_r80_scenario03_menu_return_thumbnail_deconflict_runtime_successor184 import values
    for path in sorted(linear_paths):
        ram = values(ROOT / path)['MAIN/RAM']
        need(ram[0x1D7608:0x1D7618] != bytes.fromhex('534b33450100010042000a0030003200'),
             f'Linear display coexists with menu resource: {path}')
    return {'audit_sha256': AUDIT_SHA, 'states_scanned': 7801,
            'other_physical_bat_consumers': 0, 'linear_nonfield_states': 24,
            'linear_state_paths': sorted(linear_paths),
            'scope': 'Field-menu lifetime. The 24 linear boot/title states have no Slot-A; checked by the independent verifier.'}


def plan(image):
    proof = population(image)
    writes = []
    for i, off in enumerate(SLOTS_A):
        before = image[off:off + SIZE]
        writes.append((off, before, patch_a(before), f'menu-unit/separate-scatter/{i}'))
    for i, off in enumerate(SLOTS_C):
        before = image[off:off + SIZE]
        writes.append((off, before, patch_c(before), f'menu-unit/separate-settings/{i}'))
    proof.update({'reservation': reservation(), 'remap': {hex(k): hex(v) for k, v in REMAP.items()},
                  'executable_or_glyph_payload_changes': False,
                  'includes_previous_load_x_repair': True})
    return sorted(writes), proof


def verify(before, after):
    writes, proof = plan(before)
    population(after)
    for off, _old, new, label in writes:
        need(after[off:off + SIZE] == new, f'Final menu reservation differs: {label}')
    proof['final_native_unit_intersections'] = 0
    return proof
