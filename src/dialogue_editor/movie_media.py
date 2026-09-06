"""Local-only movie catalogue. Media is a review derivative, never a build input."""
from __future__ import annotations

import hashlib
import bisect
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MEDIA = ROOT / 'work/editor-movies'
MEDIA_SCHEMA = 'langrisser-fx-editor-movies/v1'


def movie_titles() -> dict[int, str]:
    # One authority for Japanese catalogue order, also used by the game selector.
    data = json.loads((ROOT / 'analysis/av_qa_catalog.json').read_text(encoding='utf-8'))
    entries = data['sections']['movies']['entries']
    result = {int(r['selector_id']): str(r['label_ja']) for r in entries}
    from subtitle_core import load_subtitle_cues, MOVIE_COUNT
    from build_r80_movie_selector_titles_successor82 import MOVIE_TITLES
    if set(result) != set(range(MOVIE_COUNT)):
        raise ValueError('영상 목록은 000~029 전체여야 합니다.')
    if len(MOVIE_TITLES) != len(result):
        raise ValueError('게임/편집기 영상 목록 길이가 다릅니다.')
    result.update(enumerate(MOVIE_TITLES))
    for cue in load_subtitle_cues():
        result[cue.movie_id] = cue.movie_title
    result[0] = '오프닝 1 (대사 없음)'
    return result


def load_media(directory: Path = DEFAULT_MEDIA, *, verify_hashes=False) -> dict[int, dict]:
    path = directory / 'manifest.json'
    if not path.is_file():
        return {}
    doc = json.loads(path.read_text(encoding='utf-8'))
    if doc.get('schema') != MEDIA_SCHEMA:
        raise ValueError('지원하지 않는 영상 목록입니다.')
    result = {}
    for row in doc['movies']:
        mid = row['movie_id']
        if type(mid) is not int or not 0 <= mid < 30 or mid in result:
            raise ValueError('영상 ID가 중복되었거나 잘못되었습니다.')
        target = (directory / row['file']).resolve()
        if not target.is_relative_to(directory.resolve()) or not target.is_file():
            raise ValueError(f'영상 파일이 없습니다: {mid:03d}')
        if row['duration_seconds'] <= 0 or row['frames'] <= 0:
            raise ValueError(f'영상 길이가 잘못되었습니다: {mid:03d}')
        if verify_hashes:
            with target.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest.lower() != row['sha256'].lower():
                raise ValueError(f'영상 파일이 바뀌었습니다: {mid:03d}')
        if row.get('timing_version') == 2:
            clock_map = row['clock_map']
            if len(clock_map) != row['frames'] or clock_map[0][0] != 0:
                raise ValueError('영상/자막 시계 자료가 불완전합니다.')
            if any(len(v) != 2 or any(type(n) is not int or n < 0 for n in v) for v in clock_map):
                raise ValueError('영상 시계 자료 형식 오류')
            if any(a[0] >= b[0] or a[1] > b[1] for a,b in zip(clock_map, clock_map[1:])):
                raise ValueError('영상 시계가 뒤로 이동합니다.')
        result[mid] = dict(row, path=target,
                           _samples=[p[0] for p in row.get('clock_map', [])],
                           _clocks=[p[1] for p in row.get('clock_map', [])])
    return result


def cue_at(cues, movie_id: int, seconds: float):
    return next((cue for cue in cues if cue.movie_id == movie_id
                 and round(cue.start * 60) <= seconds * 60 < round(cue.end * 60)), None)


def subtitle_seconds(media, video_seconds):
    """Convert real audio/video time to the game's 60-count subtitle clock."""
    if media.get('_samples'):
        index = max(0, bisect.bisect_right(media['_samples'], round(video_seconds * media['sample_rate'])) - 1)
        return media['_clocks'][index] / 60
    return video_seconds + float(media.get('subtitle_clock_offset_seconds', 0))


def video_seconds(media, subtitle_time):
    if media.get('_clocks'):
        index = min(len(media['_clocks']) - 1, bisect.bisect_left(media['_clocks'], round(subtitle_time * 60)))
        return media['_samples'][index] / media['sample_rate']
    return max(0.0, subtitle_time - float(media.get('subtitle_clock_offset_seconds', 0)))
