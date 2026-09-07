"""Targeted Gel Gather display repair; no gameplay or hook changes.

Current compact mode reuses record 10 for the four lower-HUD name IDs, without
changing either font bank. Historical noncompact mode remains reproducible,
but its attempt to blank glyph 196 addressed a stale linear copy instead of
the active split bank. It must not be used for new deliverables; see the
successor276 consumer investigation and the builder's compact option.
"""
from __future__ import annotations

import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import hud_commander_class_restore as hud
import build_r80_packed_complete_global_names_successor as packed

LABELS = Path(__file__).with_suffix('.json')
NAME_RELATIVE = 0x726
CLASS_RELATIVE = 0x2062
MAIN_CLASS = (0x4D058, 0x27828058)
RECORDS = 0x44A
GLYPHS = 0x79C
NAME_ID = 181
CLASS_ID = 10
BLANK_ID = 196


def need(value, message):
    if not value:
        raise RuntimeError(message)


def plan(image: bytes, *, compact: bool = False):
    approved = json.loads(LABELS.read_text(encoding='utf-8'))
    need((approved['character_name'], approved['class_name']) == ('겔 게더', '겔게더'),
         'Changed wording requires renewed encoding/consumer review')
    if compact:
        need(approved['compact_name'] == approved['class_name'], 'Compact shared label')
    common = json.loads(packed.COMMON.read_text(encoding='utf-8'))
    starts = [int(x, 0) for x in common['replica_offsets']]
    need(len(starts) == 105 and common['long_replicas'] == 100, 'Common population')
    writes = []

    def add(offset, before, after, owner):
        need(len(before) == len(after), f'Fixed extent changed: {owner}')
        need(image[offset:offset+len(before)] == before, f'Preimage mismatch: {owner}')
        writes.append((offset, before, after, owner))

    # Name table is ordinal/NUL-delimited: same eight bytes, same terminator.
    for i, start in enumerate(starts):
        add(start + NAME_RELATIVE, bytes.fromhex('F26AF1E8F269F0F800'),
            bytes.fromhex('F26AF1E8F088F0F800'), f'name/common/{i:03d}')
    for i, start in enumerate(starts[:100]):
        add(start + CLASS_RELATIVE, bytes.fromhex('F26A8140F269F0F881408140814000'),
            bytes.fromhex('F26AF088F0F8814081408140814000'), f'class/common/{i:03d}')
    # Keep both the primary and the boot-selected relocated MAIN class pool.
    for offset in MAIN_CLASS:
        add(offset, bytes.fromhex('F26AF1E6F269F0F800'),
            bytes.fromhex('F26AF088F0F8F1E600'), f'class/main/{offset:08x}')

    _expected_map, classes = hud.expected_class_map(image)
    native_names = hud.names.decode_name_table(image)
    names = [hud.names.NAME_TRANSLATIONS.get(x) if x else None for x in native_names]
    labels = list(dict.fromkeys(x for x in [*classes, *names] if x))
    need(len(labels) == 197 and labels[CLASS_ID] == '겔개더'
         and labels[NAME_ID] == '게르갸저', 'HUD stable record identities')
    need([i for i,n in enumerate(native_names) if n == 'ゲルギャザー'] == [63,64,65,66],
         'HUD target name-ID population')
    reference_records = None
    for replica, start in enumerate(hud.resource_starts(image)):
        base = start + hud.PRIVATE
        tail = image[base:base+0x1000]
        need(struct.unpack_from('<I', tail, 0x2A0)[0] == (0x1E244A << 8) | 197,
             f'HUD descriptor {replica}')
        rows = tail[RECORDS:].split(b'\xff')[:197]
        need(sum(len(x)+1 for x in rows) == 850, 'HUD fixed record extent')
        if reference_records is None:
            reference_records = rows
        need(rows == reference_records, 'HUD replica record divergence')
        char_ids = {}
        for label, row in zip(labels, rows):
            need(len(label) == len(row), 'HUD text/record width')
            for ch, code in zip(label, row):
                need(ch not in char_ids or char_ids[ch] == code, 'HUD encoding ambiguity')
                char_ids[ch] = code
        need(len(char_ids) == 201 and char_ids['갸'] == BLANK_ID, 'HUD glyph population')
        need([i for i,row in enumerate(rows) if BLANK_ID in row] == [NAME_ID],
             'Reclaimed blank glyph still consumed by another label')
        need(tail[0x3A3+63:0x3A3+67] == bytes([NAME_ID])*4, 'HUD name lookup')
        if compact:
            # Both renderers walk FF-delimited records. Reuse the existing
            # three-glyph class record, preserving all record boundaries and
            # BOTH font banks (bank 1 starts at PRIVATE+0x1328, not +0xB1C).
            # Historical 273/275 mode below is retained only for reproduction.
            need(image[base+0x1758+16] == CLASS_ID, 'Combat class 16 lookup')
            offset = base + RECORDS + sum(len(row)+1 for row in rows[:CLASS_ID])
            add(offset, rows[CLASS_ID], bytes(char_ids[ch] for ch in approved['class_name']),
                f'hud-and-combat/shared-class-record/replica/{replica:02d}')
            add(base+0x3A3+63, bytes([NAME_ID])*4, bytes([CLASS_ID])*4,
                f'hud/compact-name-map/replica/{replica:02d}')
            continue
        char_ids[' '] = BLANK_ID
        for index, text in ((CLASS_ID, approved['class_name']),
                            (NAME_ID, approved['character_name'])):
            before = rows[index]
            after = bytes(char_ids[ch] for ch in text)
            offset = base + RECORDS + sum(len(row)+1 for row in rows[:index])
            add(offset, before, after, f'hud/record/{index}/replica/{replica:02d}')
        # Verify source font pixels against the declared Galmuri7 input.
        pixel_rows, _ = hud.names.load_bdf_cell(hud.names.GALMURI7, ord('갸'),
            cell_width=8, cell_height=8, ascent=7, center_x=True)
        add(base + GLYPHS + BLANK_ID*7, bytes(pixel_rows[:7]), bytes(7),
            f'hud/exclusively-released-gya-to-space/{replica:02d}')
    writes.sort()
    for left, right in zip(writes, writes[1:]):
        need(left[0]+len(left[1]) <= right[0], 'Overlapping display writers')
    return writes, {
        'approved': approved, 'name_copies':105, 'class_copies':100,
        'resident_main_copies':2, 'hud_copies':15, 'hud_records_checked_per_copy':197,
        'hud_name_ids':[63,64,65,66], 'compact':compact,
        'reclaimed_glyph_id':None if compact else BLANK_ID,
        'both_font_banks_unchanged':compact,
        'all_other_hud_records_and_glyph_ids_unchanged':True,
        'no_gameplay_or_executable_code_changes':True,
    }
