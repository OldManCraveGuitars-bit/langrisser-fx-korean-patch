"""Restore the sole hand-redrawn HUD syllable to the adopted Galmuri7 font.

Same fixed glyph ID, seven rows, split-bank addresses and consumers. No
renderer, text, slot, palette or spacing changes. Source is the immutable
v0.81 specification reconstructed by the primary product builder.
"""
import hashlib
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import hud_commander_class_restore as hud
from bdf_bitmap_glyphs import load_bdf_cell

FONT = ROOT / 'assets/fonts/galmuri-v2.40.4/Galmuri7.bdf'
FONT_SHA = '2A6FD090AC6D24F7392D6CC49DB02CE54B9D1C01048BF8C97CBCDBC5A885CB15'
GLYPH0, GLYPH1 = 0x79C, 0x1328
COUNT, SPLIT, ROWS = 201, 128, 7
RO_ID = 30
RO_BEFORE = bytes.fromhex('7C047C407C107C')
RECORDS, RECORD_BYTES = 0x44A, 850
need = hud.need
sha = lambda data: hashlib.sha256(data).hexdigest().upper()


def normalize_bank(actual, canonical, index=RO_ID):
    need(len(actual) == len(canonical) == COUNT * ROWS, 'HUD bank extent')
    start = index * ROWS
    need(actual[start:start+ROWS] == RO_BEFORE, 'HUD 로 preimage')
    need(actual[:start] == canonical[:start] and actual[start+ROWS:] == canonical[start+ROWS:],
         'Another HUD glyph differs; do not silently normalize unrelated letters')
    return actual[:start] + canonical[start:start+ROWS] + actual[start+ROWS:]


def canonical_profile(image):
    need(sha(FONT.read_bytes()) == FONT_SHA, 'Adopted Galmuri7 input changed')
    _, classes = hud.expected_class_map(image)
    native = hud.names.decode_name_table(image)
    names = [hud.names.NAME_TRANSLATIONS.get(n) if n else None for n in native]
    labels = list(dict.fromkeys(s for s in [*classes, *names] if s))
    chars = list(dict.fromkeys(''.join(labels)))
    need(len(labels) == 197 and len(chars) == COUNT and chars[RO_ID] == '로',
         'Stable HUD label/alphabet identity')
    data = bytearray()
    for ch in chars:
        rows, _ = load_bdf_cell(FONT, ord(ch), 8, 8, 7, True)
        need(len(rows) == 8 and rows[7] == 0 and any(rows[:7]), 'Galmuri cell bounds/coverage')
        data.extend(rows[:7])
    return bytes(data), labels, chars


def bank(payload):
    return payload[GLYPH0:GLYPH0+SPLIT*ROWS] + payload[GLYPH1:GLYPH1+(COUNT-SPLIT)*ROWS]


def plan(image):
    canonical, labels, chars = canonical_profile(image)
    expected_records = [bytes(chars.index(c) for c in label) for label in labels]
    offsets = hud.resource_starts(image)
    need(len(offsets) == 15, 'Complete field font replica population')
    writes = []
    for i, start in enumerate(offsets):
        base = start + hud.PRIVATE
        payload = image[base:base+0x8000]
        need(struct.unpack_from('<I', payload, 0x2A0)[0] == (0x1E244A << 8) | 197,
             'HUD record descriptor')
        need(payload[RECORDS:RECORDS+RECORD_BYTES].split(b'\xff') == expected_records + [b''],
             'Baseline label/glyph identity')
        updated = normalize_bank(bank(payload), canonical)
        need(updated == canonical, 'Canonical glyph verification')
        off = base + GLYPH0 + RO_ID * ROWS
        writes.append((off, RO_BEFORE, updated[RO_ID*ROWS:(RO_ID+1)*ROWS],
                       f'hud-font/galmuri-ro/replica/{i:02d}'))
    return writes, {'font': str(FONT.relative_to(ROOT)), 'font_sha256': FONT_SHA,
        'glyph': '로', 'glyph_id': RO_ID, 'font_replicas': len(offsets),
        'all_glyphs_checked_per_replica': COUNT, 'glyph_changes': 1,
        'shared_labels': [s for s in labels if '로' in s],
        'cell_width': 8, 'cell_height': 8, 'ascent': 7,
        'code_text_spacing_palette_and_other_glyphs_unchanged': True}


def verify(source, target):
    writes, proof = plan(source)
    canonical, _, _ = canonical_profile(source)
    for start in hud.resource_starts(target):
        base = start + hud.PRIVATE
        need(bank(target[base:base+0x8000]) == canonical, 'Final active HUD font bank differs')
    for off, before, after, owner in writes:
        need(target[off:off+len(before)] == after, 'Missing final glyph: ' + owner)
    return proof
