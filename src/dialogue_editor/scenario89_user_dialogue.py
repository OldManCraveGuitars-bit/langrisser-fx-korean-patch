"""Exact user-authored S8/S9 voice edits, within existing ordinal pools only.

The pinned source population excludes CN and presentation sections. All
unselected raw records, section addresses, dictionaries, and fonts stay intact.
"""
import json
import struct
from pathlib import Path

import dialogue_core as dialogue
import condition_native_codec as native
import presentation_dictionary as dictionary
from muscle_temple_dialogue import split_rows, SELECTOR, MIRROR
from scenario7_user_dialogue import topology, sha

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'dialogue_editor/user_dialogue_edits_successor284.json'
# header, section 5 start/end, source record population, immutable pool/source SHA
PROFILES = {
    8: (0x164D9C, 0x168644, 0x1697AC, 116,
        'A659AFD2EA45A7D87191750CA070FED2A682DB1A95501F4AB7B56806F493F25D',
        '8BF3CF26DB53AEA1CB0285AFE92B126C43A26890AD018642F478C5610843A04D'),
    9: (0x16B8E4, 0x16F18C, 0x170A2C, 174,
        '53A0C0E10F2FD2E3ED61E87B02BE25482EA764A8A1202DBEAAA20922D72616EF',
        '26E65315D52925AAC9F96723EAAE2522495FA91A892F3404BA47DEADB95B22A2'),
}
IDS = ('scenario08/dialogue/011', 'scenario08/dialogue/092',
       'scenario08/dialogue/093', 'scenario09/dialogue/023')
INPUT_285 = ROOT / 'dialogue_editor/user_dialogue_edits_successor285.json'
EXTRA_IDS_285 = tuple(f'scenario09/dialogue/{i:03d}' for i in (105, 146, 150, 152, 154, 161))
IDS_285 = IDS + EXTRA_IDS_285
need = dialogue.need


def selection_profile(revision):
    need(revision in (284, 285), 'Unknown user selection revision')
    return (INPUT, IDS) if revision == 284 else (INPUT_285, IDS_285)


def selected_texts(revision=284):
    path, ids = selection_profile(revision)
    doc = json.loads(path.read_text(encoding='utf8'))
    need(doc['schema'] == 'langrisser-fx-selected-user-dialogue-snapshot/v1'
         and doc['status'] == 'user_authored_apply_requested', 'User input policy')
    raw = (ROOT / doc['source_snapshot']).read_bytes()
    need(sha(raw) == doc['source_snapshot_sha256'], 'User snapshot identity')
    need(tuple(doc['edit_ids']) == ids, 'Selected S8/S9 edit population')
    edits = json.loads(raw)['dialogue_edits']
    selected = {key: edits[key] for key in ids}
    if revision == 285:
        previous = selected_texts(284)
        need(all(selected[key] == value for key, value in previous.items()),
             'Previously selected wording changed outside the six requested records')
    return selected


def pack(before, local, scenario, texts, revision=284):
    _, ids = selection_profile(revision)
    expected = [key for key in ids if key.startswith(f'scenario{scenario:02d}/')]
    need(set(texts) == set(expected), 'Unexpected selected edit IDs')
    count = PROFILES[scenario][3]
    original = split_rows(before, count)
    rows = original.copy()
    mapping = dialogue.with_native_ascii(dialogue.all_dialogue_private_mapping())
    audit = []
    for key, text in texts.items():
        index = int(key.rsplit('/', 1)[1])
        need(not dialogue._unknown_tokens(text), key + ' unknown control')
        layout = dialogue.portrait_layout_inspection(text)
        need(not layout['failures'], key + ' layout overflow')
        raw, missing = dialogue.encode_plain(text, mapping)
        need(not missing and b'\0' not in raw, key + ' unrepresentable glyph/NUL')
        previous = rows[index]
        plain = native.expand(previous, local)
        need(topology(plain) == topology(raw), key + ' page/name topology changed')
        need(native.expand(raw, local) == raw, key + ' unexpected phrase dependency')
        rows[index] = raw
        audit.append({'id': key, 'selected_text': text,
                      'before_raw_hex': previous.hex(), 'before_plain_hex': plain.hex(),
                      'after_raw_hex': raw.hex(), 'layout': layout,
                      'pages_and_names_preserved': True})
    packed = b''.join(row + b'\0' for row in rows)
    need(len(packed) <= len(before), 'Native dialogue pool capacity overflow')
    after = packed.ljust(len(before), b'\0')
    need(split_rows(after, count) == rows, 'Ordinal re-extraction mismatch')
    changed = [i for i, pair in enumerate(zip(original, rows)) if pair[0] != pair[1]]
    need(changed == sorted(int(key.rsplit('/', 1)[1]) for key in texts),
         'Changed record population differs from exact user selection')
    return after, {'scenario': scenario, 'records': audit,
                   'unchanged_records': count - len(texts), 'changed_ordinals': changed,
                   'pool_capacity': len(before), 'pool_used': len(packed),
                   'remaining_padding': len(before) - len(packed),
                   'new_glyphs': 0, 'dictionary_or_section_writes': False}


def plan(image, revision=284):
    path, ids = selection_profile(revision)
    texts = selected_texts(revision)
    for bias in (0, MIRROR):
        need(image[bias + 0x714C:bias + 0x714C + len(SELECTOR)] == SELECTOR,
             'Native ordinal consumer changed')
    writes, audit = [], []
    for scenario, (header, start, end, count, pre_sha, source_sha) in PROFILES.items():
        need(sha(image[start:end]) == pre_sha, 'Immutable dialogue preimage')
        offsets = struct.unpack_from('<9I', image, header)
        need(header + offsets[5] == start and header + offsets[6] == end,
             'Native section boundary changed')
        source = json.loads((ROOT / f'analysis/scenario{scenario:02d}_dialogue_source_original.json')
                            .read_text(encoding='utf8'))
        records = [r for r in source['dialogue'] if int(r['cooked_offset'], 0) < end]
        need(len(records) == count and
             sha(b''.join(bytes.fromhex(r['raw_hex']) for r in records)) == source_sha,
             'Source record population/bytes changed')
        local = dictionary._split_dictionary(image[header + offsets[4]:start])
        chosen = {key: text for key, text in texts.items()
                  if key.startswith(f'scenario{scenario:02d}/')}
        after, result = pack(image[start:end], local, scenario, chosen, revision)
        writes.append((start, image[start:end], after,
                       f'user-dialogue/scenario{scenario:02d}-selected-successor{revision}'))
        audit.append(result)
    return writes, {'input_manifest': str(path.relative_to(ROOT)),
                    'snapshot_sha256': json.loads(path.read_text(encoding='utf8'))['source_snapshot_sha256'],
                    'selected_records': len(ids), 'scenarios': audit}


def verify(before, after, revision=284):
    writes, audit = plan(before, revision)
    for offset, original, expected, owner in writes:
        need(after[offset:offset + len(original)] == expected, 'Final user bytes: ' + owner)
    return audit


def verify_complement(before, after):
    need(len(before) == len(after), 'Disc extent changed')
    verify(before, after)
    end_previous, changed_bytes, sectors = 0, 0, set()
    def identical(start, end):
        return all(before[a:min(a + (1 << 20), end)] == after[a:min(a + (1 << 20), end)]
                   for a in range(start, end, 1 << 20))
    for scenario, (_, start, end, count, _, _) in PROFILES.items():
        need(identical(end_previous, start),
             'Unrelated disc bytes changed')
        old = split_rows(before[start:end], count)
        new = split_rows(after[start:end], count)
        expected = [int(k.rsplit('/', 1)[1]) for k in IDS
                    if k.startswith(f'scenario{scenario:02d}/')]
        need([i for i in range(count) if old[i] != new[i]] == expected,
             'Unselected dialogue changed')
        positions = [start + i for i, (a, b) in enumerate(zip(before[start:end], after[start:end])) if a != b]
        changed_bytes += len(positions)
        sectors.update(p // 2048 for p in positions)
        end_previous = end
    need(identical(end_previous, len(before)), 'Unrelated trailing disc bytes changed')
    return {'selected_records_changed': list(IDS), 'other_records_identical': 286,
            'all_other_disc_bytes_identical': True, 'changed_bytes': changed_bytes,
            'changed_sectors': sorted(sectors)}
