"""Source-verified additions and explicitly non-distributable translation inputs."""
from pathlib import Path
from functools import lru_cache
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'dialogue_editor/presentation_catalog_extension.json'
TRANSLATIONS = ROOT / 'dialogue_editor/missing_presentation_translations.json'
SOURCE_SHA = '66CA5B976762CD8B5FD7430142B450BF327A11720A85763CD727D93834F802E7'
INDICES = frozenset((96, 97, 98))


@lru_cache(maxsize=1)
def source_rows() -> tuple[dict, ...]:
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest().upper() != SOURCE_SHA:
        raise ValueError('추가 나레이션의 보호된 원문 자료가 변경되었습니다.')
    doc = json.loads(raw)
    if doc['schema'] != 'langrisser-fx-presentation-catalog-extension/v1':
        raise ValueError('추가 나레이션 원문 형식 오류')
    rows = tuple(doc['presentations'])
    if {r['presentation_index'] for r in rows} != INDICES:
        raise ValueError('추가 나레이션의 고정 ID가 변경되었습니다.')
    for row in rows:
        region = bytes.fromhex(row['source_region_hex'])
        if hashlib.sha256(region).hexdigest().upper() != row['source_region_sha256']:
            raise ValueError('추가 나레이션 원문 바이트 불일치')
        if not region.startswith(b''.join(bytes.fromhex(f['raw_hex']) for f in row['frames'])):
            raise ValueError('추가 나레이션 원문 프레임 경계 불일치')
    return rows


def load_catalog(base_path: Path) -> dict:
    base = json.loads(base_path.read_text(encoding='utf-8'))
    old_ids = {r['presentation_index'] for r in base['presentations']}
    if old_ids & INDICES:
        raise ValueError('기존 편집 ID와 추가 나레이션 ID 충돌')
    return {**base, 'presentations': base['presentations'] + list(source_rows())}


@lru_cache(maxsize=1)
def draft() -> dict:
    doc = json.loads(TRANSLATIONS.read_text(encoding='utf-8'))
    if (doc.get('schema') != 'langrisser-fx-missing-presentation-translations/v1'
            or doc.get('input_policy') != 'development-only'
            or doc.get('distribution_eligible') is not False
            or doc.get('status') != 'needs_human_review'):
        raise ValueError('추가 번역의 검토용·비배포 입력 표시가 필요합니다.')
    expected = {'narrations': set(), 'conditions': set(), 'titles': set()}
    for row in source_rows():
        owner = f'presentation{row["presentation_index"]:03d}'
        expected['titles'].add(owner + '/title')
        ordinal = 0
        for frame in row['frames']:
            if frame['kind'] == 'narration':
                ordinal += 1
                expected['narrations'].add(f'{owner}/narration/{ordinal:03d}')
            elif frame['kind'].endswith('-condition'):
                expected['conditions'].add(f'{owner}/condition/{frame["kind"].split("-")[0]}')
    for kind, keys in expected.items():
        if set(doc[kind]) != keys or not all(isinstance(v, str) and v for v in doc[kind].values()):
            raise ValueError(f'추가 번역 {kind} 항목 누락/중복/알 수 없는 ID')
    return doc


def verify_source_region(index: int, raw: bytes) -> None:
    row = next(r for r in source_rows() if r['presentation_index'] == index)
    if raw != bytes.fromhex(row['source_region_hex']):
        raise ValueError(f'추가 연출 {index}: 기준판이 일본판 원문과 일치하지 않습니다.')


def display_label(index: int) -> str:
    caption = draft()['titles'][f'presentation{index:03d}/title']
    return f'추가 연출 {index} · {caption} (검토용)'


def original_prefix_matches(anchor: int, prefix: bytes) -> bool:
    for row in source_rows():
        if anchor == int(row['cooked_offset'], 0):
            header = bytes.fromhex(row['frames'][0]['raw_hex']).split(b'\x08', 1)[0] + b'\x08'
            return prefix.startswith(header)
    return False


def verify_final_titles(image: bytes) -> dict:
    # Imports are local to keep source-catalogue access free of compiler cycles.
    import narration_core as n
    import presentation_dictionary as p
    import condition_core as c
    verified = []
    for row in source_rows():
        resource = p.locate_resource(image, int(row['cooked_offset'], 0), allow_authored_title=True)
        frames, _ = c.split_frames(image[resource.presentation_offset:resource.presentation_offset + resource.presentation_allocation])
        expected = n.missing_presentation_title(row['presentation_index'], bytes.fromhex(row['frames'][0]['raw_hex']))
        if frames[0] != expected:
            raise ValueError(f'{row["presentation_index"]}: 추가 연출 제목의 최종 바이트 불일치')
        verified.append(row['presentation_index'])
    return {'titles_verified': verified, 'input_policy': draft()['input_policy'],
            'distribution_eligible': False, 'source_sha256': SOURCE_SHA,
            'draft_sha256': hashlib.sha256(TRANSLATIONS.read_bytes()).hexdigest().upper()}
