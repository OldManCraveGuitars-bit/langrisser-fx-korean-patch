"""The user-selected 256x240 title still, in the existing RAINBOW slot.

This is an asset-format conversion, not an image retouch.  All 61,440 source
pixels are supplied to the encoder without resizing, masks, or filtering.
The menu sprites and every preceding opening frame are protected.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/title-inputs/der_langrisser_fx_rainbow_preprocessed.png'
SOURCE_SHA256 = 'C3C3127689061AF66DE3EA6ACC6476CABE4B2E3668B92FC758F497C6D88321AE'
OFFSET = 187180 * 2048
SLOT_BYTES = 26950
SOURCE_SLOT_SHA256 = '906F3ABFA042588E1E362251F1D0B8486D558F65D2C3AEC591DFAED56B6FC14D'
STREAM_SHA256 = '3C28223B0F9F44FE71EF21705A1F68FC5CA3C043B39D4B0332550B5944B4D80C'
CODEC_HASHES = {
    'gen_pcfx_rainbow_bg.py': 'BA26F4560A384E0A923F9B52CDFFBA9DD95A8F479C0A63E59E9F275323FF784E',
    'rainbow_refdec.py': 'A5E9FDE9828922B1918E34BDBDE55655CBDAFAB4624B892FAC050EF0365063EF',
}
LUMA_REFINE = 4
CHROMA_REFINE = 16
MAX_STRIP_SIZE = 2304


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError('타이틀 이미지: ' + message)


def validate_stream(stream: bytes) -> list[dict]:
    require(len(stream) <= SLOT_BYTES, '원본 저장 영역 초과')
    position = 0
    strips = []
    for index in range(15):
        require(position + 4 <= len(stream), '잘린 블록 헤더')
        require(stream[position:position+2] == (b'\xff\xff' if index == 0 else b'\xff\xf8'),
                '블록 순서 또는 형식 변경')
        size = int.from_bytes(stream[position+2:position+4], 'big')
        require((130 if index == 0 else 2) <= size <= MAX_STRIP_SIZE and size % 2 == 0,
                '블록 크기 또는 정렬 오류')
        end = position + size + 2
        require(end + 8 <= len(stream) and stream[end:end+8] == bytes(8),
                '블록 경계 또는 패딩 오류')
        strips.append(dict(index=index, offset=position, size_field=size))
        position = end + 8
    require(position == len(stream), '15개 블록 이후 알 수 없는 데이터')
    return strips


def codec(name: str):
    directory = Path(os.environ.get('LANGRISSER_RAINBOW_TOOLS',
                                   ROOT.parent / '.tool-cache/doompcfx-simp/tools'))
    path = directory / name
    require(path.is_file(), f'변환 도구 없음: {path}')
    require(sha(path.read_bytes()) == CODEC_HASHES[name], f'변환 도구 버전 변경: {name}')
    spec = importlib.util.spec_from_file_location('title_' + path.stem, path)
    require(spec is not None and spec.loader is not None, '변환 도구 로드 실패')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compile_asset() -> tuple[bytes, Image.Image, dict]:
    source = Path(os.environ.get('LANGRISSER_TITLE_PNG', SOURCE))
    require(source.is_file(), f'사용자가 선택한 원본 파일 없음: {source}')
    require(sha(source.read_bytes()) == SOURCE_SHA256, '승인된 원본 파일 해시 변경')
    with Image.open(source) as original:
        require(original.mode == 'RGB' and original.size == (256, 240),
                'RGB 256x240 원본이어야 함; 자동 크기 변경 금지')
    encoder = codec('gen_pcfx_rainbow_bg.py')
    encoder.LUMA_Q = [min(254, max(1, (v+LUMA_REFINE-1)//LUMA_REFINE))
                      for v in encoder.LUMA_Q_RETAIL]
    encoder.CHROMA_Q = [min(254, max(1, (v+CHROMA_REFINE-1)//CHROMA_REFINE))
                        for v in encoder.CHROMA_Q_RETAIL]
    stream = encoder.encode_frame(source)
    strips = validate_stream(stream)
    require(sha(stream) == STREAM_SHA256, '고정 원본의 변환 결과가 달라짐')
    decoder = codec('rainbow_refdec.py')
    preview = Image.fromarray(decoder.to_rgb(*decoder.decode_stream(stream, 240)))
    return stream, preview, dict(
        source=str(source), source_sha256=SOURCE_SHA256, source_size=[256, 240],
        profile=f'luma-refine-{LUMA_REFINE}/chroma-refine-{CHROMA_REFINE}',
        codec_hashes=CODEC_HASHES, stream_sha256=sha(stream), stream_bytes=len(stream),
        slot_bytes=SLOT_BYTES, remaining_bytes=SLOT_BYTES-len(stream), strips=strips,
        source_resized=False, source_retouch=False, lossy_format_conversion=True,
        title_menu_sprites_changed=False, movie_frames_before_final_still_changed=False,
    )


def plan_writes(source_image: bytes, stream: bytes) -> list[dict]:
    validate_stream(stream)
    require(sha(stream) == STREAM_SHA256, '다른 이미지 변환 데이터')
    require(len(source_image) >= OFFSET+SLOT_BYTES, '디스크 영역 없음')
    expected = source_image[OFFSET:OFFSET+SLOT_BYTES]
    require(sha(expected) == SOURCE_SLOT_SHA256, '기준판 타이틀 저장 영역 변경')
    return [dict(id='title-screen/user-native-rainbow-20260903', offset=OFFSET,
                 expected=expected, replacement=stream+bytes(SLOT_BYTES-len(stream)))]


def verify_final(image: bytes, stream: bytes) -> dict:
    validate_stream(stream)
    require(sha(stream) == STREAM_SHA256, '최종 변환 데이터 해시 변경')
    require(image[OFFSET:OFFSET+SLOT_BYTES] == stream+bytes(SLOT_BYTES-len(stream)),
            '최종 디스크의 타이틀 그림이 다름')
    return dict(offset=hex(OFFSET), bytes=SLOT_BYTES, stream_sha256=sha(stream),
                verified_after_last_writer=True)
