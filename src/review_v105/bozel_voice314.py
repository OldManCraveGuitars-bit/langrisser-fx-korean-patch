"""Keep resource60/135's two screens on its single original Bozel recording."""
from dataclasses import replace
import hashlib

import dialogue_continuation_resident as continuation
import early_dialogue_font as font

BASE_SHA = '518735404B8E399E171D3545C2861B12287B53FBF22F195913FE9B35FCEC19AB'
RECORD_ID = 'scenario60/dialogue/135'
POOL_START, POOL_END, ORDINAL = 2930876, 2938484, 135
EXPECTED_ROW = bytes.fromhex(
    'f5bdf691f1e8f58af4a8f665f1b9f1e8f444f5c8f56008f8a6f779f4be0418'
    'f1e8f58af5eef58af5eef77af1e8049808f474f67ef68ef1e8f4b2f8c7f1e8'
    '040d04890607f569f6f8f49af1e8042508f780f59f0440')
BEFORE = ('빛의 무녀여, 감사를\n표한다. 이 무시무시할 정도의\n'
          '기운을 느낄 수 있겠지.{page}마침내 알하자드는\n해방되었다!')
AFTER = BEFORE.replace('{page}', '{visual}')


def verify_helper(image):
    # Later append-only fonts legitimately occupy former padding after the
    # 204-byte helper. Verify its owned instructions, not the obsolete 512-byte
    # zero-padding contract; never overwrite those glyphs.
    tails = font.resource12_tails(image)
    assert len(tails) == 15
    for tail in tails:
        code = image[tail+continuation.OFFSET:tail+continuation.OFFSET+continuation.HELPER_BYTES]
        assert hashlib.sha256(code).hexdigest().upper() == continuation.HELPER_SHA256
    for address, (_, replacement) in continuation.DISPATCH.items():
        raw = bytes.fromhex(replacement)
        assert image[address-0x7000:address-0x7000+len(raw)] == raw
    return dict(physical_helper_replicas=15, existing_helper_and_dispatch_unchanged=True)


def plan(image):
    assert hashlib.sha256(image).hexdigest().upper() == BASE_SHA, 'Expected exact successor313'
    helper = verify_helper(image)
    pool = bytes(image[POOL_START:POOL_END])
    cursor = 0
    for _ in range(ORDINAL):
        cursor = pool.index(0, cursor)+1
    end = pool.index(0, cursor)
    assert pool[cursor:end] == EXPECTED_ROW, 'Bozel dialogue preimage changed'
    assert EXPECTED_ROW.count(b'\x06\x07') == 1
    at = POOL_START+cursor+EXPECTED_ROW.index(b'\x06\x07')
    return [(at, b'\x06', b'\x0a', 'bozel314/resource60-dialogue135/visual-only-page')], dict(
        **helper, record=RECORD_ID, offset=hex(at), before='06', after='0A',
        changed_bytes=1, screens=2, voice_recordings=1,
        correct_bozel_voice=3186, following_dark_princess_voice=3187,
        wording_and_linebreaks_unchanged=True, original_audio_bytes_unchanged=True,
        event_voice_numbers_unchanged=True, auxiliary_resource86_untouched=True)


def apply_to_editor(records):
    result = []
    seen = 0
    for row in records:
        if row.id == RECORD_ID:
            assert row.base_text in (BEFORE, AFTER), 'Bozel editor default changed'
            row = replace(row, base_text=AFTER)
            seen += 1
        result.append(row)
    assert seen == 1
    return result
