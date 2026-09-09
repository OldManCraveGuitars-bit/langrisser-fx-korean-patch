"""One approved confrontation correction; preserve all other ordinal records.

Reported after Scenario 12; the historical catalog calls this block scenario13.
Wording authority is dialogue_user_corrections.json, also used by the editor.
Never pad an individual shortened row or change a shared dictionary phrase.
"""
import hashlib
import json
from pathlib import Path

import dialogue_core as dialogue
import condition_native_codec as native
import presentation_dictionary as dictionary
from muscle_temple_dialogue import split_rows, SELECTOR, MIRROR
from scenario7_user_dialogue import topology

ROOT = Path(__file__).resolve().parents[1]
KEY = 'scenario13/confrontation/ledin-identifies-bernhardt'
START, END, COUNT, ORDINAL = 0x18AA24, 0x18C793, 174, 7
DICT = 0x18A187
POOL_SHA = '46BAEEDCEDE8DB9A86C6205536BC52FD405B44AF2F14435C2071DA8AD6476A62'
DICT_SHA = 'BA8122EBB2E05042E816EA55767B615352EA9B9109AFDFAB0C3094C14EBC2294'
SOURCE_OFFSET = 0x18AB36
SOURCE_RAW = bytes.fromhex('82A8914F82AA0882A8914F82AA091582BE82C8814900')
BEFORE_RAW = bytes.fromhex('04D0F1E804D0F1E80915F550043B8149')
need = dialogue.need


def sha(data):
    return hashlib.sha256(data).hexdigest().upper()


def replace_ordinal(pool, count, index, expected, replacement):
    need(0 <= index < count, 'Correction ordinal outside population')
    need(replacement and b'\0' not in replacement, 'Correction contains NUL/empty row')
    old = split_rows(pool, count)
    need(old[index] == expected, 'Correction record preimage differs')
    rows = old.copy()
    rows[index] = replacement
    packed = b''.join(row + b'\0' for row in rows)
    need(len(packed) <= len(pool), 'Correction pool capacity overflow')
    after = packed.ljust(len(pool), b'\0')
    parsed = split_rows(after, count)
    need(parsed == rows, 'Correction ordinal roundtrip failed')
    need(all(parsed[i] == old[i] for i in range(count) if i != index),
         'Unselected dialogue changed')
    return after, len(packed)


def plan(image, original_track2):
    document = json.loads((ROOT/'dialogue_editor/dialogue_user_corrections.json')
                          .read_text(encoding='utf8'))
    need(document['schema'] == 'langrisser-fx-user-dialogue-corrections/v1',
         'Correction schema differs')
    change = document['corrections'][KEY]
    need(set(change) == {'before', 'after'}, 'Correction fields differ')
    with Path(original_track2).open('rb') as source:
        source.seek((SOURCE_OFFSET // 2048 + 225) * 2352 + 16 + SOURCE_OFFSET % 2048)
        need(source.read(len(SOURCE_RAW)) == SOURCE_RAW, 'Japanese source record differs')
    need(sha(image[START:END]) == POOL_SHA, 'Correction pool preimage differs')
    need(sha(image[DICT:START]) == DICT_SHA, 'Active dictionary differs')
    for bias in (0, MIRROR):
        need(image[bias+0x714C:bias+0x714C+len(SELECTOR)] == SELECTOR,
             'Native ordinal selector differs')
    # This dictionary starts with a zero-code sentinel. Code 1 follows it.
    need(image[DICT] == 0, 'Dictionary zero-code sentinel differs')
    local = dictionary._split_dictionary(image[DICT+1:START])
    mapping = dialogue.with_native_ascii(dialogue.all_dialogue_private_mapping())
    plain = {}
    for kind, text in change.items():
        need(not dialogue._unknown_tokens(text), 'Correction has unknown controls')
        need(not dialogue.portrait_layout_inspection(text)['failures'],
             'Correction dialogue layout overflow')
        plain[kind], missing = dialogue.encode_plain(text, mapping)
        need(not missing and b'\0' not in plain[kind], 'Correction has missing encoding/NUL')
    need(native.expand(BEFORE_RAW, local) == plain['before'],
         'Correction authority does not match active dictionary expansion')
    need(topology(plain['before']) == topology(plain['after']),
         'Correction changed page/name/control topology')
    raw = native.compress(plain['after'], local)
    need(native.expand(raw, local) == plain['after'], 'Correction expansion mismatch')
    after, used = replace_ordinal(image[START:END], COUNT, ORDINAL, BEFORE_RAW, raw)
    audit = {'id': KEY, 'reported_scene': 'Scenario 12 throne-room confrontation',
        'before': change['before'], 'after': change['after'],
        'before_hex': BEFORE_RAW.hex(), 'after_hex': raw.hex(),
        'native_ordinal_zero_based': ORDINAL, 'pool_records': COUNT,
        'other_records_byte_identical': COUNT-1, 'pool_used': used,
        'pool_capacity': END-START, 'tokens_preserved': True,
        'dictionary_fonts_code_and_section_offsets_changed': False}
    return [(START, image[START:END], after, 'wording-correction/'+KEY)], audit


def verify(source, target, original_track2):
    writes, audit = plan(source, original_track2)
    for offset, before, expected, owner in writes:
        need(target[offset:offset+len(before)] == expected, 'Final correction mismatch: '+owner)
    audit['verified_after_last_writer'] = True
    return audit
