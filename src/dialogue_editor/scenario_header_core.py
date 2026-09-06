"""Center every SCENARIO-number row without changing its native number token.

Dictionary labels can include two native 12px blanks; literal labels do not.
Measure their expansion rather than assuming both consumers start at the same x.
Only header whitespace and, if capacity demands it, its own literal dictionary
storage may change. Captions, narration, conditions and section offsets do not.
"""
from __future__ import annotations

import condition_core as conditions
import condition_native_codec as codec
import dialogue_core as dialogue
import narration_core as narration
import presentation_dictionary as resources
import scenario_title_core as titles

BLANKS = (b"\x05", titles.SPACE4, titles.SPACE8)
# Native title setup 4ACFA..4AD2A indexes RAM52205 by resource number-1,
# then puts the chapter in5A9A8 for control03/F5E2. The same immutable
# table has its unique cooked owner at4B205. In particular resources37/38
# display chapters8/9, not37/38; resource70 displays21.
DISPLAY_TABLE_OFFSET = 0x4B205
DISPLAY_NUMBERS = bytes.fromhex(
    "0102030405060708090a0b0c0d0e0f1011121314151314150e0f100f1011121312131415"
    "08090a0b0c0d0e0f10111213141511121314150c0d0e0f1011121314151112131415"
)


def trim_padding(raw: bytes) -> tuple[int, bytes]:
    width = 0
    for offset, token in titles.tokens(raw):
        if token not in BLANKS:
            return width, raw[offset:]
        width += titles.advance(token)
    return width, b""


def center_frame(frame: bytes, scenario: int, dictionary: tuple[bytes, ...],
                 *, label_code: int | None = None) -> tuple[bytes, dict]:
    dialogue.need(1 <= scenario <= 70, "시나리오 번호 정렬 대상 범위 오류")
    header, caption = titles.split_title(frame)
    _, first = trim_padding(header)
    dialogue.need(first.startswith(b"\x08") and first.endswith(b"\x08"),
                  "SCENARIO 번호 줄 경계 변경")
    outer_indent, row = trim_padding(first[1:-1])
    padded_suffix = narration.TITLE_DYNAMIC_SUFFIX
    bare_suffix = padded_suffix[-1:]
    dialogue.need(
        row.endswith(padded_suffix) or row.endswith(bare_suffix),
        "SCENARIO 동적 번호 제어 토큰 변경",
    )
    input_suffix = padded_suffix if row.endswith(padded_suffix) else bare_suffix
    label = row[:-len(input_suffix)]
    dialogue.need(label == narration.TITLE_LITERAL
                  or (len(label) == 2 and label[0] == 4),
                  "SCENARIO 번호 줄의 알 수 없는 본문")
    expanded = codec.expand(label, dictionary)
    inner_indent, visible = trim_padding(expanded)
    dialogue.need(visible == narration.TITLE_LITERAL,
                  "SCENARIO 사전 참조가 다른 문구를 가리킵니다.")
    # Control03 prints the complete decimal display number.  The original
    # fullwidth zero is therefore padding only for one-digit chapters; keeping
    # it on chapters10+ produces SCENARIO-010, SCENARIO-012, and so on.
    # Resource indexes are NOT displayed chapter numbers after branch selection.
    display_number = DISPLAY_NUMBERS[scenario - 1]
    output_suffix = padded_suffix if display_number < 10 else bare_suffix
    leading_zero_cells = int(display_number < 10)
    width = (len(visible) // 2 + leading_zero_cells
             + len(str(display_number))) * 12
    inset = ((titles.PANEL_WIDTH - width + titles.QUANTUM)
             // (2 * titles.QUANTUM)) * titles.QUANTUM
    if label_code is not None:
        label = bytes((4, label_code))
        dialogue.need(dictionary[label_code - 1] == narration.TITLE_LITERAL,
                      "SCENARIO 전용 사전 본문 불일치")
        inner_indent = 0
    dialogue.need(inset >= inner_indent, "SCENARIO 사전 내부 공백이 중앙 여백 초과")
    old_indent = outer_indent + trim_padding(expanded)[0]
    # Keep already-centered headers byte-exact (including the invisible
    # blank preceding their first newline), minimizing native changes.
    if old_indent == inset and label_code is None and input_suffix == output_suffix:
        centered = frame
    else:
        centered = (b"\x08" + titles.padding(inset - inner_indent) + label
                    + output_suffix + b"\x08" + caption + titles.PAGE)
    dialogue.need(titles.split_title(centered)[1] == caption,
                  "SCENARIO 번호 정렬 중 아래 제목 변경")
    return centered, {
        "scenario": scenario, "display_number": display_number,
        "width_px": width, "old_indent_px": old_indent,
        "indent_px": inset, "center_error_px": inset + width / 2 - titles.PANEL_WIDTH / 2,
        "dynamic_number_token_preserved": True, "caption_preserved": True,
        "leading_zero_cell": bool(leading_zero_cells),
        "input_had_leading_zero_cell": input_suffix == padded_suffix,
        "number_format": f"{display_number:02d}",
        "label_dictionary_code": label[1] if label[0] == 4 else None,
    }


def plan_writes(image: bytes | bytearray) -> tuple[list[dict], list[dict]]:
    dialogue.need(image[DISPLAY_TABLE_OFFSET:DISPLAY_TABLE_OFFSET + 70] == DISPLAY_NUMBERS,
                  "SCENARIO 실제 장 번호 표 변경: 정렬 규칙 재검토 필요")
    writes, audit = [], []
    for state in conditions.load_condition_data()[1]:
        match = narration.SCENARIO.match(state.label)
        if not match:
            continue
        scenario = int(match[1])
        resource = resources.locate_resource(image, state.offset, allow_authored_title=True)
        start, size = resource.presentation_offset, resource.presentation_allocation
        before = bytes(image[start:start + size])
        frames, suffix = conditions.split_frames(before)
        dialogue.need(not any(suffix), f"{scenario}화 번호 뒤 비문자 영역 침범")
        header, row = center_frame(frames[0], scenario, resource.dictionary_rows)
        packed = header + b"".join(frames[1:])
        # Preserve the native stream terminator; do not consume its last NUL.
        terminal_bytes = 1 if suffix else 0
        dictionary_code = None
        if len(packed) + terminal_bytes > size:
            owner = f"scenario-number/{scenario:02d}"
            plan = resources.build_dictionary_plan(
                image, resource, ((owner, narration.TITLE_LITERAL),),
                preserve_all_source_rows=True,
            )
            dialogue.need(not plan.cleared_codes, "번호 정렬에 다른 사전 행 삭제 금지")
            dictionary_code = dict(plan.assignments)[owner]
            dictionary = resources._split_dictionary(plan.replacement)
            dialogue.need(all(a == b for i, (a, b) in enumerate(
                zip(resource.dictionary_rows, dictionary), 1) if i != dictionary_code),
                "번호 정렬에서 비소유 사전 행 변경")
            header, row = center_frame(frames[0], scenario, dictionary,
                                       label_code=dictionary_code)
            packed = header + b"".join(frames[1:])
            writes.append({"id": owner + "/dictionary", "offset": resource.dictionary_offset,
                           "expected": bytes(image[resource.dictionary_offset:
                                                   resource.dictionary_offset + resource.dictionary_allocation]),
                           "replacement": plan.replacement})
        dialogue.need(len(packed) + terminal_bytes <= size,
                      f"{scenario}화 번호 정렬 공간 부족: 문구/종단 보존 불가")
        after = packed + bytes(size - len(packed))
        after_frames, after_suffix = conditions.split_frames(after)
        dialogue.need(after_frames[1:] == frames[1:], f"{scenario}화 번호 외 프레임 변경")
        dialogue.need(bool(after_suffix) == bool(suffix) or bool(after_suffix),
                      "SCENARIO 번호 정렬에서 종단 NUL 소실")
        row.update({"offset": start, "allocation": size,
                    "non_title_frames_preserved": True,
                    "dedicated_dictionary_allocated": dictionary_code,
                    "zero_tail_bytes": len(after_suffix)})
        audit.append(row)
        if after != before:
            writes.append({"id": f"scenario-number/{scenario:02d}/header", "offset": start,
                           "expected": before, "replacement": after})
    dialogue.need([row["scenario"] for row in audit] == list(range(1, 71)),
                  "SCENARIO 번호 정렬 대상은 1~70화여야 합니다.")
    return writes, audit


def verify(image: bytes | bytearray) -> list[dict]:
    writes, audit = plan_writes(image)
    dialogue.need(not writes, "최종 디스크의 SCENARIO 번호 중앙 정렬 불일치")
    return audit
