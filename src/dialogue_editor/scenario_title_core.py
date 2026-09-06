"""Center scenario captions within their native 192px presentation panel.

Only title frame 0 and inert trailing zeros may change. Shared dictionaries,
SCENARIO-number headers, narration/condition frames, and resource offsets do not.
"""
from __future__ import annotations

import json
from pathlib import Path

import condition_core as conditions
import dialogue_core as dialogue
import narration_core as narration
import presentation_dictionary as resources

PANEL_WIDTH = 192
SAFE_WIDTH = 184
QUANTUM = 4
OPEN = bytes.fromhex("8175")
CLOSE = bytes.fromhex("8176")
SPACE8 = bytes.fromhex("F1E6")
SPACE4 = bytes.fromhex("F1E8")
PAGE = bytes.fromhex("0607")
# This malformed frame is already present in the immutable successor190 base:
# the title loses its closing bracket and runs into duplicated narration.
# Pin the complete bad row rather than silently accepting any malformed title.
S12_BROKEN_ROW = bytes.fromhex(
    "05F1E6F1E6F1E6F1E6F1E68175F1EAF105F4F9F46FF568F5C8F560F1E8F65BF68D08"
    "F695F784F691F1E8F5C8F474F440F1E8F671F4F8F4BEF1BA08F548F692F443F4DDF5D5F68BF55008"
    "F463F457F68EF1E8F5EEF69DF783F4BEF1BA"
)


def tokens(data: bytes):
    cursor = 0
    while cursor < len(data):
        first = data[cursor]
        size = 2 if first in (4, 9) or 0x81 <= first <= 0x9F or 0xE0 <= first <= 0xFC else 1
        dialogue.need(cursor + size <= len(data), "시나리오 제목의 불완전한 문자")
        yield cursor, data[cursor:cursor + size]
        cursor += size


def advance(token: bytes) -> int:
    if token == b"\x05":
        return 12
    if token == SPACE8:
        return 8
    if token == SPACE4:
        return 4
    if len(token) == 2 and token[0] not in (4, 9):
        return 12
    raise dialogue.DialogueError(f"시나리오 제목의 비정규 1바이트 문자 {token.hex()}")


def paired_caption(caption: bytes) -> bytes:
    # Native F486 handles 20/21 specially, but every other printable byte
    # consumes a following byte before calling the full-cell glyph mapper
    # (F4F2..F516). Old GO! A HEAD / WANTED titles contain bare ASCII letters.
    # Keep the same letters and punctuation, encoded as native fullwidth pairs.
    output = bytearray()
    for _, token in tokens(caption):
        if len(token) == 2:
            output.extend(token)
        else:
            dialogue.need(0x20 <= token[0] <= 0x7E, "시나리오 제목 내부 제어 코드")
            output.extend(SPACE4 if token == b" " else chr(token[0] + 0xFEE0).encode("shift_jis"))
    return bytes(output)


def padding(width: int) -> bytes:
    dialogue.need(width >= 0 and width % QUANTUM == 0, "시나리오 제목 들여쓰기 단위 오류")
    full, remainder = divmod(width, 12)
    return b"\x05" * full + {0: b"", 4: SPACE4, 8: SPACE8}[remainder]


def s12_title() -> bytes:
    source = dialogue.ROOT / "analysis/translations_scenario12_title_poc_v16.json"
    text = json.loads(source.read_text(encoding="utf-8"))["scenario12/title"]
    dialogue.need(text == "철벽의 기사단", "12화 채택 제목 변경: 재검토 필요")
    mapping = narration.narration_mapping()
    return OPEN + b"".join(SPACE4 if char == " " else mapping[char] for char in text) + CLOSE


def split_title(frame: bytes) -> tuple[bytes, bytes]:
    dialogue.need(frame.endswith(PAGE), "시나리오 제목 페이지 종단 없음")
    breaks = [offset for offset, token in tokens(frame[:-2]) if token == b"\x08"]
    dialogue.need(len(breaks) >= 2, "시나리오 번호/제목 줄 경계 없음")
    boundary = breaks[1] + 1
    return frame[:boundary], frame[boundary:-2]


def center_frame(frame: bytes, scenario: int) -> tuple[bytes, dict]:
    header, row = split_title(frame)
    repaired_s12 = scenario == 12 and row == S12_BROKEN_ROW
    if repaired_s12:
        caption = s12_title()
        old_indent = None
    else:
        row_tokens = list(tokens(row))
        start = 0
        old_indent = 0
        while start < len(row_tokens) and row_tokens[start][1] in (b"\x05", SPACE8, SPACE4):
            old_indent += advance(row_tokens[start][1])
            start += 1
        dialogue.need(start < len(row_tokens), f"{scenario}화 제목 내용 없음")
        caption = row[row_tokens[start][0]:]
        dialogue.need(caption.startswith(OPEN) and caption.endswith(CLOSE),
                      f"{scenario}화 제목 괄호/프레임 경계 변경: 임의 복구 금지")
    original_caption = caption
    caption = paired_caption(caption)
    width = sum(advance(token) for _, token in tokens(caption))
    dialogue.need(0 < width <= SAFE_WIDTH,
                  f"{scenario}화 제목 폭 {width}/{SAFE_WIDTH}px 초과")
    indent = ((PANEL_WIDTH - width + QUANTUM) // (2 * QUANTUM)) * QUANTUM
    centered = header + padding(indent) + caption + PAGE
    dialogue.need(split_title(centered)[0] == header, "시나리오 번호 줄 변경")
    return centered, {
        "scenario": scenario, "caption_hex": caption.hex().upper(),
        "width_px": width, "old_indent_px": old_indent, "indent_px": indent,
        "center_error_px": indent + width / 2 - PANEL_WIDTH / 2,
        "s12_title_restored": repaired_s12, "number_header_preserved": True,
        "paired_ascii_normalized": caption != original_caption,
        "input_caption_hex": original_caption.hex().upper(),
    }


def plan_writes(image: bytes | bytearray) -> tuple[list[dict], list[dict]]:
    writes, audit = [], []
    for state in conditions.load_condition_data()[1]:
        match = narration.SCENARIO.match(state.label)
        if not match:
            continue
        scenario = int(match[1])
        resource = resources.locate_resource(image, state.offset, allow_authored_title=True)
        offset, length = resource.presentation_offset, resource.presentation_allocation
        before = bytes(image[offset:offset + length])
        frames, suffix = conditions.split_frames(before)
        dialogue.need(not any(suffix), f"{scenario}화 제목 뒤 비문자 영역 침범")
        title, row = center_frame(frames[0], scenario)
        packed = title + b"".join(frames[1:])
        dialogue.need(len(packed) <= length, f"{scenario}화 제목 공간 초과")
        after = packed + bytes(length - len(packed))
        after_frames, _ = conditions.split_frames(after)
        dialogue.need(after_frames[1:] == frames[1:], f"{scenario}화 제목 외 프레임 변경")
        row.update({"offset": offset, "allocation": length,
                    "non_title_frames_preserved": True, "frame_count": len(frames),
                    "zero_tail_bytes": length - len(packed)})
        audit.append(row)
        if after != before:
            writes.append({"id": f"scenario-titles/center-{scenario:02d}", "offset": offset,
                           "expected": before, "replacement": after})
    dialogue.need([row["scenario"] for row in audit] == list(range(1, 71)),
                  "시나리오 제목 검사 대상은 1~70화여야 합니다.")
    return writes, audit


def verify(image: bytes | bytearray) -> list[dict]:
    writes, audit = plan_writes(image)
    dialogue.need(not writes, "최종 디스크의 시나리오 제목 중앙 정렬 불일치")
    return audit
