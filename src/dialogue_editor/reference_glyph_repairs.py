"""Source-bound repairs of inherited SFC decoder placeholders, not prose edits.

Only the adopted base corpus is repaired. Saved user overrides are applied by
the editor later and are never passed to this function. Historical extraction,
adoption, layout and dictionary plans remain immutable.
"""
from dataclasses import replace
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

PLAN = Path(__file__).with_name('dialogue_reference_glyph_repairs_20260904.json')
MARKER = re.compile(r'\[\s*(\d[\d\s]*):([\d\s]+)\]')
TOKEN = re.compile(r'\{[^}]*\}')


def require(condition, message):
    if not condition:
        raise ValueError('참고 글리프 복원: ' + message)


def slot_key(text):
    left, right = text.split(':')
    return int(''.join(left.split())), int(''.join(right.split()))


@lru_cache(maxsize=1)
def plan():
    document = json.loads(PLAN.read_text(encoding='utf-8'))
    require(document['schema'] == 'langrisser-fx-reference-glyph-repairs/v1'
            and document['status'] == 'source-verified-technical-repair', '계획 형식 오류')
    symbols = {}
    for decision in document['evidence']['decisions']:
        character = decision['character']
        require(len(character) == 1
                and character.encode('shift_jis').hex().upper() == decision['native_hex'],
                '네이티브 글리프 불일치')
        for slot in decision['slots']:
            key = slot_key(slot)
            require(key not in symbols, '슬롯 소유 중복')
            symbols[key] = character
    rows = document['records']
    require(len(rows) == len({row['id'] for row in rows}) == 17, '레코드 분모 오류')
    for row in rows:
        for variant in ('pre_layout', 'layout'):
            before, after = row[variant]['before'], row[variant]['after']
            matches = list(MARKER.finditer(before))
            require(bool(matches), row['id'] + ': 원래 표기 없음')
            expected = MARKER.sub(lambda m: symbols[slot_key(m[1] + ':' + m[2])], before)
            require(after == expected and not MARKER.search(after),
                    row['id'] + ': 복원 기호 이외의 문장 변경')
            require(TOKEN.findall(before) == TOKEN.findall(after),
                    row['id'] + ': 이름/페이지/제어 순서 변경')
    require(len(document['scenario01_dictionary']) == 2, '1화 사전 분모 오류')
    for entry in document['scenario01_dictionary']:
        row = next(row for row in rows if row['id'] == entry['record_id'])
        require(row['layout'] == {key: entry[key] for key in ('before', 'after')},
                '본문/사전 복원 문구 불일치')
    return document


def apply_to_adopted_records(records, *, layout):
    """Fail on a changed source/default rather than overwrite new user prose."""
    repairs = {row['id']: row for row in plan()['records']}
    result, seen = [], set()
    variant = 'layout' if layout else 'pre_layout'
    for record in records:
        repair = repairs.get(record.id)
        if repair is None:
            result.append(record)
            continue
        require(record.id not in seen, record.id + ': 중복 ID')
        seen.add(record.id)
        require(record.source_text == repair['source'], record.id + ': 원문 변경')
        require(record.base_text == repair[variant]['before'], record.id + ': 채택 문구 변경')
        result.append(replace(record, base_text=repair[variant]['after']))
    require(seen == set(repairs), '일부 복원 대상 누락')
    return result


def scenario01_phrase(code, original):
    for row in plan()['scenario01_dictionary']:
        if int(row['code'], 0) == code:
            require(original == row['before'], f'사전 {code:02X} 기준 문구 변경')
            return row['after']
    return original


def scenario01_payload(payload, encode_plain):
    """Compose with the verified 200 plan in its original 241-row extent.

    Codes 02/03 and the existing F1 filler are the only logical writers.
    Preserve every other row byte-for-byte, including external consumers.
    The caller must verify the immutable 200 plan before calling this.
    """
    original = payload.split(b'\0')
    require(len(original) == 242 and original[-1] == b'', '사전 241행 종단 오류')
    original = original[:-1]
    require(original[0xF1-1] == b'\x05' * len(original[0xF1-1]), '기존 채움 행 오류')
    records = original.copy()
    changes = []
    for row in plan()['scenario01_dictionary']:
        code = int(row['code'], 0)
        require(code in (2, 3), '허용되지 않은 사전 쓰기')
        before = encode_plain(row['before'])
        after = encode_plain(row['after'])
        require(records[code-1] == before, f'사전 {code:02X} 기준 인코딩 불일치')
        require(b'\0' not in after, '사전 본문 내부 종단')
        records[code-1] = after
        changes.append(dict(code=row['code'], before_hex=before.hex(), after_hex=after.hex()))
    saved = sum(map(len, original)) - sum(map(len, records))
    require(saved >= 0, '기존 사전 범위 초과')
    records[0xF1-1] += b'\x05' * saved
    for code, (before, after) in enumerate(zip(original, records, strict=True), 1):
        require(before == after or code in (2, 3, 0xF1), f'사전 {code:02X} 비소유 행 변경')
    result = b'\0'.join(records) + b'\0'
    require(len(result) == len(payload), '사전 물리 범위 변경')
    return result, dict(records=241, changed_codes=['0x02', '0x03'],
                        filler_growth=saved, changes=changes,
                        plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest().upper())
