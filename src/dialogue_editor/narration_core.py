#!/usr/bin/env python3
"""Editable narration frames in the adopted presentation catalogue.

The legacy 95-owner/450-body catalogue now includes three source-verified
additions (12 bodies), without changing any legacy ID. This is the established
resource shape's population, not proof that every possible text format is known.
The added wording remains explicitly non-distributable pending human review.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
from itertools import combinations
import json
import re

import condition_core as conditions
import dialogue_core as dialogue
import presentation_dictionary as presentation_dict
import missing_presentations
from native_glyphs import paired_glyph, with_native_ascii
from native_name_widths import name_width_px


CATALOG = dialogue.ROOT / "analysis/all_scenario_presentations_v84.json"
TRANSLATIONS = (
    dialogue.ROOT
    / "dialogue_editor/narration_translations_all_successor197.json"
)
READABILITY_LAYOUT_OVERRIDES = (
    dialogue.ROOT
    / "dialogue_editor/narration_layout_readability_overrides_successor244.json"
)
READABILITY_CAPACITY_EXCEPTIONS = (
    dialogue.ROOT
    / "dialogue_editor/narration_readability_capacity_exceptions_successor244.json"
)
PRESENTATION082_PHRASE_EXTENSION = (
    dialogue.ROOT
    / "dialogue_editor/presentation082_narration_phrase_extension_successor200.json"
)
PAGE = b"\x06\x07"
PREFIX = b"\x05"
TOKEN = re.compile(r"\{(name|raw|dict):([0-9A-Fa-f]{2})\}")
ANY_BRACE = re.compile(r"\{[^{}]*\}")
SCENARIO = re.compile(r"^scenario-(\d{2})$")
NARRATION_SAFE_WIDTH_PX = 188
NARRATION_MAX_LINES = 4
# Every encoded body starts with native 05, which advances one 12px cell.
# The first line must include that inset; native 08 restores the row origin.
# The blue text area is 192px wide. 188px keeps a visible 4px right margin and
# permits natural Korean clauses such as "리아나를 레이갈드 제국군에게서"
# on the first row. Spaces use the resident 4px advance and are never placed
# at a row end, so no trailing 12px cell reaches the frame.
NARRATION_INITIAL_INDENT_PX = 12
# Keep the existing 36px reserve for the supplied, unrenamed Elwin path.
# Its current C5C buffer consumes 28px (엘윈 + F1E8). Raw 02 is a separate
# event-argument resolver, not an indexed 09 name; arbitrary renamed saves
# and other argument types are not established by the installed name table.
PROTAGONIST_RESERVE_PX = 36

# Scenario presentation titles historically expanded dictionary entry 01
# to the original full-width ``SCENARIO-`` label.  That same dictionary is
# later repacked for field dialogue and conditions, so leaving the title as a
# 0401 reference makes an otherwise unrelated dictionary edit replace the
# title at runtime.  Store the original label literally in the presentation
# frame instead.  The aggregate has enough owned final-frame padding for the
# sixteen-byte growth and therefore neither needs nor receives a shared-code
# alias.
TITLE_DICTIONARY_TOKEN = bytes.fromhex("0401")
TITLE_LITERAL = "ＳＣＥＮＡＲＩＯ−".encode("shift_jis")
TITLE_DYNAMIC_SUFFIX = bytes.fromhex("824F03")
# The Scenario-02 label is 11 native 12px cells. Round the 26px inset in the
# 184px title text area to the existing 4px spacing quantum (28px). Do not
# alter the following Korean title's independent alignment or dynamic number.
# Two native 05 blanks (12px each) plus F1E8 (4px), after the row break.
# Omit the old blank *before* that break: it had no visible content and the
# compact prefix fits this presentation's three remaining storage bytes.
SCENARIO02_CENTERED_PREFIX = bytes.fromhex("080505F1E8")
# Compatibility names retained for the successor206 verifier and reports.
S2_TITLE_DICTIONARY_TOKEN = TITLE_DICTIONARY_TOKEN
S2_TITLE_LITERAL = TITLE_LITERAL
S2_TITLE_DYNAMIC_SUFFIX = TITLE_DYNAMIC_SUFFIX
LOCAL_TITLE_RECORD_ID = "__presentation_title__"
URL_PUNCTUATION_LAYOUT_OVERRIDES = frozenset({
    "presentation082/narration/043",
})


@dataclass(frozen=True)
class NarrationRecord:
    id: str
    presentation_index: int
    label: str
    scenario: int | None
    frame_index: int
    ordinal: int
    source_text: str
    disc_text: str
    base_text: str


@dataclass(frozen=True)
class BalancedPresentationPatch:
    """One exact variable-section repack inside a scenario resource."""

    patches: tuple[tuple[int, bytes, str], ...]
    audit: dict


def narration_mapping() -> dict[str, bytes]:
    # This is the encoding/ownership authority, not proof that its atlas is
    # resident during every presentation. The F4-F9 supply on narration entry
    # is unresolved (successor217-runtime-reassessment-20260903.json). Preserve
    # complete wording, including 에스톨, while investigating that runtime link;
    # never rebuild code assignments from mutable translation text.
    mapping = dict(dialogue.all_dialogue_private_mapping())
    dialogue.need_unique_mapping(mapping, "나레이션 전용 문자표")
    dialogue.need(mapping[" "] != mapping["\u2009"],
                  "나레이션 공백 글리프 중복")
    return mapping


def _display_label(index: int, inferred: str) -> str:
    if index in missing_presentations.INDICES:
        return missing_presentations.display_label(index)
    match = SCENARIO.match(inferred)
    if match:
        return f"시나리오 {int(match.group(1))}"
    if inferred in {"X1", "X2", "X3"}:
        return f"기타 연출 {inferred}"
    return f"기타 연출 {index}"


def _record_id(index: int, scenario: int | None, ordinal: int) -> str:
    # Keep the former Scenario-1 IDs compatible with already saved projects.
    owner = f"scenario{scenario:02d}" if scenario is not None else f"presentation{index:03d}"
    return f"{owner}/narration/{ordinal:03d}"


def _decode_frame(
    frame: bytes,
    reverse: dict[bytes, str],
    dictionary: dict[int, str] | None = None,
) -> str:
    dialogue.need(frame.endswith(PAGE), "나레이션 PAGE 종단 없음")
    body = frame[:-len(PAGE)]
    cursor = 1 if body.startswith(PREFIX) else 0
    output: list[str] = []
    while cursor < len(body):
        pair = body[cursor:cursor + 2]
        if pair in reverse:
            character = reverse[pair]
            output.append(" " if character == "\u2009" else character)
            cursor += 2
            continue
        value = body[cursor]
        if value == 0x08:
            output.append("\n")
            cursor += 1
        elif value == 0x09 and cursor + 1 < len(body):
            output.append(f"{{name:{body[cursor + 1]:02X}}}")
            cursor += 2
        elif value == 0x04 and cursor + 1 < len(body):
            code = body[cursor + 1]
            output.append(
                dictionary.get(code, f"{{dict:{code:02X}}}")
                if dictionary is not None
                else f"{{dict:{code:02X}}}"
            )
            cursor += 2
        elif value < 0x20:
            output.append(f"{{raw:{value:02X}}}")
            cursor += 1
        elif value < 0x80 or 0xA1 <= value <= 0xDF:
            output.append(bytes((value,)).decode("shift_jis"))
            cursor += 1
        else:
            dialogue.need(cursor + 1 < len(body), "나레이션 끝의 불완전한 문자")
            try:
                output.append(pair.decode("shift_jis"))
            except UnicodeDecodeError as exc:
                raise dialogue.DialogueError(
                    f"나레이션 미등록 코드: {pair.hex().upper()}"
                ) from exc
            cursor += 2
    return "".join(output)


def _source_text(row: dict) -> str:
    value = str(row.get("expanded_text") or row.get("source_text") or "")
    value = dialogue.ui_text(
        value.replace("{br}", "\n").replace("{end}", "")
    ).removesuffix("{page}")
    return re.sub(r"^\{raw:05\}", "", value)


def _narration_units(text: str) -> list[tuple[str, int]]:
    """Return indivisible display units with their real visible advances."""

    units: list[tuple[str, int]] = []
    cursor = 0
    while cursor < len(text):
        match = TOKEN.match(text, cursor)
        if match:
            kind, raw_value = match.groups()
            value = int(raw_value, 16)
            if kind == "name":
                try:
                    width = name_width_px(value)
                except ValueError as exc:
                    raise dialogue.DialogueError(str(exc)) from exc
            elif kind == "raw":
                advances = {0x02: PROTAGONIST_RESERVE_PX, 0x05: 12, 0x20: 8}
                dialogue.need(value in advances,
                              f"나레이션 폭을 계산할 수 없는 제어 토큰 {{raw:{value:02X}}}")
                width = advances[value]
            else:
                # Authored Korean narration never contains a raw dictionary
                # token.  Rejecting it here avoids guessing the expansion.
                raise dialogue.DialogueError(
                    "나레이션 폭을 계산할 수 없는 사전 토큰: "
                    f"{{dict:{value:02X}}}"
                )
            units.append((match.group(0), width))
            cursor = match.end()
            continue
        character = text[cursor]
        if character == " ":
            # _encode emits resident F1E8, not the dialogue F1E6 space.
            width = 4
        else:
            measured = dialogue.line_widths(character)
            dialogue.need(
                len(measured) == 1,
                f"나레이션 문자 폭 계산 실패: {character!r}",
            )
            width = measured[0]
        units.append((character, width))
        cursor += 1
    return units


def narration_line_widths(text: str) -> list[int]:
    """Consumed extent from the row origin, including automatic first 05."""
    return [
        sum(width for _unit, width in _narration_units(line))
        + (NARRATION_INITIAL_INDENT_PX if index == 0 else 0)
        for index, line in enumerate(text.split("\n"))
    ]


def _narration_break_penalty(
    units: list[tuple[str, int]],
    start: int,
    end: int,
    next_position: int,
) -> int:
    """Penalize readable-but-awkward Korean phrase separations."""

    if next_position >= len(units):
        return 0
    before = "".join(unit for unit, _width in units[start:end]).rstrip()
    after = "".join(unit for unit, _width in units[next_position:])
    previous_word = before.rsplit(" ", 1)[-1]
    next_word = after.split(" ", 1)[0]
    if not previous_word or not next_word:
        return 0
    if previous_word[-1] in ".!?。！？…‥":
        return 0
    if previous_word[-1] in ",，、;:；：":
        return 1
    fixed_pairs = {
        ("레이갈드", "제국"),
        ("제국", "군단"),
        ("제국", "기사단"),
        ("빛의", "대신전"),
        ("신전", "무녀"),
        ("신관", "전사"),
        ("살라스", "영주"),
        ("칼자스", "소녀"),
        ("광휘의", "후예"),
        ("어둠의", "왕자"),
        ("마음에", "들"),
        ("염룡병단", "정예부대"),
    }
    if any(
        previous_word == left and next_word.startswith(right)
        for left, right in fixed_pairs
    ):
        return 12
    dependent_starts = {
        "것", "곳", "수", "줄", "때", "듯", "채", "바", "중", "후", "뒤",
        "앞", "길", "만큼", "모양", "셈",
    }
    if any(next_word.startswith(word) for word in dependent_starts):
        return 10
    if next_word.startswith("{") and previous_word in {
        "맹장", "장군", "마법사", "부대장", "소녀", "왕", "황제",
    }:
        return 10
    modifier_endings = (
        "의", "인", "한", "한편", "하는", "하던", "할", "했던", "된", "되는",
        "되던", "될", "작은", "젊은", "어떤", "모든", "이런", "그런", "저런",
    )
    previous_lexeme = previous_word.rstrip(",.!?，。！？、;:；：…‥")
    if previous_lexeme.endswith(modifier_endings):
        return 8
    return 2


def reflow_narration_text(text: str, *, record: NarrationRecord | None = None) -> str:
    """Losslessly reflow one adopted record to the proven 184 px window."""

    normalized = re.sub(r"\s*\n\s*", " ", text.strip())
    normalized = re.sub(r" {2,}", " ", normalized)
    units = _narration_units(normalized)
    unit_count = len(units)
    compressed = record is not None and (
        record.presentation_index == 82
        or (record.scenario is not None and 1 <= record.scenario <= 12)
    )
    phrase_codes = {}
    if compressed:
        if record.presentation_index == 82:
            phrase_codes = {row['phrase']: int(row['code'], 0)
                            for row in _presentation082_plan()['dictionary']['assignments']}
        elif record.scenario == 1:
            phrase_codes = {phrase: code for phrase, code in dialogue._s1_phrase_codes().items()
                            if code <= presentation_dict.RUNTIME_SOURCE_PRESERVE_MAX}
        elif record.scenario == 2:
            phrase_codes = dialogue._s2_encoding_resources()[1]
        else:
            phrase_codes = dialogue._early_full_phrase_codes(record.scenario)
    # Precompute scalar costs instead of invoking the full encoder and its
    # round-trip decoder for every candidate line while opening the editor.
    # Final bodies still pass that actual encoder and native byte verifier.
    char_offsets = [0]
    for unit, _width in units:
        char_offsets.append(char_offsets[-1] + len(unit))
    unit_at = {offset: i for i, offset in enumerate(char_offsets)}
    edges = []
    for i, (unit, _width) in enumerate(units):
        options = [(i + 1, 1 if unit.startswith('{raw:') else 2)]
        if compressed:
            for phrase in phrase_codes:
                target = char_offsets[i] + len(phrase)
                if ('\n' not in phrase and target in unit_at
                        and normalized.startswith(phrase, char_offsets[i])):
                    options.append((unit_at[target], 2))
        edges.append(options)

    @lru_cache(maxsize=None)
    def costs_from(start: int):
        infinity = 1 << 30
        costs = [[infinity, infinity] for _ in range(unit_count + 1)]
        costs[start][0] = 0
        for position in range(start, unit_count):
            for target, size in edges[position]:
                for parity in (0, 1):
                    next_parity = (parity + size) & 1
                    costs[target][next_parity] = min(
                        costs[target][next_parity], costs[position][parity] + size)
        return costs

    @lru_cache(maxsize=None)
    def line_storage(start: int, end: int) -> int:
        if not compressed:
            return 0
        while end > start and units[end - 1][0] == ' ':
            end -= 1
        even, odd = costs_from(start)[end]
        # Preserve complete wording while avoiding cuts through an installed
        # dictionary phrase. A visually valid break can otherwise make the
        # fixed presentation larger by discarding that lossless compression.
        return min(even, odd) + 1

    @lru_cache(maxsize=None)
    def solve(position: int, remaining: int):
        while position < unit_count and units[position][0] == " ":
            position += 1
        if position == unit_count:
            return (0, 0, 0, 0, ())
        if remaining == 0:
            return None
        width = NARRATION_INITIAL_INDENT_PX if remaining == NARRATION_MAX_LINES else 0
        best = None
        for end in range(position, unit_count):
            width += units[end][1]
            visible_width = width - (
                units[end][1] if units[end][0] == " " else 0
            )
            if visible_width > NARRATION_SAFE_WIDTH_PX:
                break
            tail = solve(end + 1, remaining - 1)
            if tail is None:
                continue
            next_position = end + 1
            while (next_position < unit_count
                   and units[next_position][0] == " "):
                next_position += 1
            mid_word = int(
                next_position < unit_count
                and units[end][0] != " "
            )
            phrase_penalty = _narration_break_penalty(
                units, position, end + 1, next_position
            )
            score = (
                mid_word + tail[0],
                line_storage(position, end + 1) + tail[1],
                1 + tail[2],
                # Phrase boundaries matter, but must not dominate the actual
                # row geometry.  The old 10,000 multiplier preferred a comma
                # boundary even when that left an 88px first row in a 184px
                # box (for example Scenario 1's opening narration).  Keep the
                # linguistic preference while allowing visibly fuller,
                # balanced rows to win.
                phrase_penalty * 1_000
                + (NARRATION_SAFE_WIDTH_PX - visible_width) ** 2
                + tail[3],
                ((position, end + 1, visible_width),) + tail[4],
            )
            # Readability owns the visible layout.  Dictionary storage is a
            # capacity concern, not a reason to force an otherwise needless
            # extra line or an unbalanced phrase break.  The complete build
            # still validates the resulting packed presentation size.
            readable_key = (score[0], score[2], score[3], score[1])
            if best is None or readable_key < (
                best[0], best[2], best[3], best[1]
            ):
                best = score
        return best

    plan = solve(0, NARRATION_MAX_LINES)
    dialogue.need(
        plan is not None,
        "나레이션 전문을 184px/4줄 안에 배치할 수 없습니다: "
        + text.replace("\n", " / "),
    )
    lines = [
        "".join(unit for unit, _width in units[start:end]).strip()
        for start, end, _width in plan[4]
    ]
    result = "\n".join(lines)
    dialogue.need(
        max(narration_line_widths(result), default=0)
        <= NARRATION_SAFE_WIDTH_PX,
        "나레이션 자동 줄바꿈 폭 검증 실패",
    )
    return result


@lru_cache(maxsize=1)
def load_narration_records() -> tuple[NarrationRecord, ...]:
    catalog = missing_presentations.load_catalog(CATALOG)
    translation_document = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    dialogue.need(
        translation_document.get("schema")
        == "langrisser-fx-narration-translations/v1",
        "나레이션 번역 자료 형식 오류",
    )
    # Translation catalogues are written before their dedicated glyph banks
    # are necessarily installed.  A draft must remain visible to the build
    # work without making the editor impossible to open.  Only a catalogue
    # that has passed the font/capacity checks is allowed to become the
    # editor's restore-default text.
    adopted = (
        {
            str(key): str(value)
            for key, value in translation_document.get("records", {}).items()
        }
        if (
            translation_document.get("status")
            in {"adopted", "prepared-full-source-exact-pass"}
            and not translation_document.get("unresolved_records")
        )
        else {}
    )
    adopted.update(missing_presentations.draft()['narrations'])
    layout_document = json.loads(
        READABILITY_LAYOUT_OVERRIDES.read_text(encoding="utf-8")
    )
    dialogue.need(
        layout_document.get("schema")
        == "langrisser-fx-narration-layout-readability-overrides/v1"
        and layout_document.get("status") == "reviewed-for-layout",
        "나레이션 가독성 줄바꿈 예외 자료 형식 오류",
    )
    layout_overrides = {
        str(record_id): str(text)
        for record_id, text in layout_document.get("records", {}).items()
    }
    capacity_document = json.loads(
        READABILITY_CAPACITY_EXCEPTIONS.read_text(encoding="utf-8")
    )
    dialogue.need(
        capacity_document.get("schema")
        == "langrisser-fx-narration-readability-capacity-exceptions/v1"
        and capacity_document.get("status") == "reviewed-for-layout",
        "나레이션 가독성 용량 예외 자료 형식 오류",
    )
    capacity_exceptions = {
        str(record_id): str(text)
        for record_id, text in capacity_document.get("records", {}).items()
    }
    _condition_records, states = conditions.load_condition_data()
    state_by_index = {row.presentation_index: row for row in states}
    reverse = {code: character for character, code in narration_mapping().items()}
    records: list[NarrationRecord] = []
    for source in catalog["presentations"]:
        index = int(source["presentation_index"])
        inferred = str(source["inferred_label"])
        scenario_match = SCENARIO.match(inferred)
        scenario = int(scenario_match.group(1)) if scenario_match else None
        state = state_by_index[index]
        # Source logical identities define the editor population. The pinned
        # input lost S12's third paragraph; its condition shifted into index 3.
        # Do not misclassify or discard source text based on that damaged input.
        missing_indexes = conditions.validate_frame_population(
            index, state.frames, allow_missing_restorations=True,
        )
        narration_rows = [
            row for row in source["frames"]
            if row["kind"] == "narration"
        ]
        narration_indexes = [int(row["index"]) for row in narration_rows]
        dialogue.need(
            all(0 <= frame_index < len(state.frames)
                for frame_index in narration_indexes),
            f"{inferred}: 나레이션 프레임 인덱스 범위 오류",
        )
        dialogue.need(
            len(narration_rows) == len(narration_indexes),
            f"{inferred}: 나레이션 원문/프레임 수 불일치",
        )
        label = _display_label(index, inferred)
        presentation_dictionary: dict[int, str] | None = None
        if scenario is not None and 3 <= scenario <= 12:
            _plan, phrase_codes = dialogue._early_plan(scenario)
            presentation_dictionary = {
                code: phrase for phrase, code in phrase_codes.items()
            }
        for ordinal, (frame_index, source_row) in enumerate(
            zip(narration_indexes, narration_rows), start=1
        ):
            source_text = _source_text(source_row)
            try:
                disc_text = (
                    "" if frame_index in missing_indexes else _decode_frame(
                        state.frames[frame_index - sum(i < frame_index for i in missing_indexes)],
                        reverse, presentation_dictionary,
                    )
                )
            except dialogue.DialogueError:
                # Some untouched presentations use native game gaiji outside
                # Shift-JIS and outside the Korean atlas.  The catalogue's
                # expanded Japanese is the lossless editable display for them;
                # unchanged bytes are never re-encoded.
                disc_text = source_text
            record_id = _record_id(index, scenario, ordinal)
            if index in missing_presentations.INDICES:
                disc_text = source_text
            dialogue.need(frame_index not in missing_indexes or record_id in adopted,
                          f"{record_id}: 복구 문단 번역 입력 누락")
            base_text = capacity_exceptions.get(
                record_id, adopted.get(record_id, disc_text)
            )
            if record_id in capacity_exceptions:
                source_tokens = Counter(
                    match.group(0).lower()
                    for match in TOKEN.finditer(adopted[record_id])
                    if match.group(1) in {"name", "raw"}
                )
                exception_tokens = Counter(
                    match.group(0).lower()
                    for match in TOKEN.finditer(base_text)
                    if match.group(1) in {"name", "raw"}
                )
                dialogue.need(
                    exception_tokens == source_tokens,
                    f"{record_id}: 나레이션 용량 예외가 이름/제어 토큰을 바꿨습니다.",
                )
            record = NarrationRecord(
                id=record_id,
                presentation_index=index,
                label=label,
                scenario=scenario,
                frame_index=frame_index,
                ordinal=ordinal,
                source_text=source_text,
                disc_text=disc_text,
                base_text=base_text,
            )
            if record_id in adopted:
                record = replace(record, base_text=reflow_narration_text(base_text, record=record))
                if record_id in layout_overrides:
                    override = layout_overrides[record_id]
                    ordinary_equal = (
                        re.sub(r"\s+", " ", override.strip())
                        == re.sub(r"\s+", " ", base_text.strip())
                    )
                    url_punctuation_equal = (
                        record_id in URL_PUNCTUATION_LAYOUT_OVERRIDES
                        and re.sub(r"\s+", "", override)
                        == re.sub(r"\s+", "", base_text)
                        and override.splitlines()[:2] == ["htt://www.", "iijnet."]
                    )
                    dialogue.need(
                        ordinary_equal or url_punctuation_equal,
                        f"{record_id}: 나레이션 줄바꿈 예외가 문구를 바꿨습니다.",
                    )
                    record = replace(record, base_text=override)
            records.append(record)
    dialogue.need(len(records) == sum(
        row["kind"] == "narration" for source in catalog["presentations"] for row in source["frames"]
    ), "전체 원문 나레이션 레코드 수 불일치")
    dialogue.need(len({row.id for row in records}) == len(records),
                  "나레이션 ID 중복")
    dialogue.need(not (set(layout_overrides) - {row.id for row in records}),
                  "알 수 없는 나레이션 줄바꿈 예외 ID")
    dialogue.need(not (set(capacity_exceptions) - {row.id for row in records}),
                  "알 수 없는 나레이션 용량 예외 ID")
    dialogue.need(not (set(adopted) - {row.id for row in records}),
                  "알 수 없는 채택 나레이션 ID")
    dialogue.need(
        {row.scenario for row in records if row.scenario is not None}
        == set(range(1, 71)),
        "시나리오 1~70 나레이션이 불완전합니다.",
    )
    return tuple(records)


def missing_presentation_title(index: int, frame: bytes) -> bytes:
    """Translate the restored title caption, retaining its native number control."""
    from scenario_title_core import padding, OPEN, CLOSE
    row = next(r for r in missing_presentations.source_rows() if r['presentation_index'] == index)
    source = bytes.fromhex(row['frames'][0]['raw_hex'])
    number = source.split(b'\x08', 1)[0] + b'\x08'
    dialogue.need(frame.startswith(number), f'{index}: 추가 제목 번호 제어 변경')
    text = missing_presentations.draft()['titles'][f'presentation{index:03d}/title']
    encoded, absent = _encode(text)
    dialogue.need(not absent and not TOKEN.search(text) and '\n' not in text,
                  f'{index}: 추가 제목 문자/구조 오류')
    width = 24 + sum(w for _, w in _narration_units(text))
    dialogue.need(width <= NARRATION_SAFE_WIDTH_PX, f'{index}: 추가 제목 폭 초과')
    indent = ((192 - width + 4) // 8) * 4
    return number + padding(indent) + OPEN + encoded + CLOSE + PAGE


def _effective_edits(
    records: tuple[NarrationRecord, ...], edits: dict[str, str]
) -> dict[str, str]:
    result = {
        row.id: row.base_text for row in records
        if (
            row.base_text != row.disc_text
            # The successor188 3-12 presentation bytes directly reference
            # the mutable field-dialogue dictionary.  Rebuild them even when
            # their decoded text already matches so every narration gets an
            # independent literal local-dictionary owner.
            or (row.scenario is not None and 3 <= row.scenario <= 12)
        )
    }
    result.update(edits)
    return result


def verify_final_narration_population(image: bytes, edits: dict[str, str]) -> dict:
    """Check adopted-catalogue frames and expanded bodies after all writers."""
    records = load_narration_records()
    restored_records = []
    verified_records = []
    total = 0
    states = conditions.load_condition_data()[1]
    for state in states:
        resource = presentation_dict.locate_resource(image, state.offset, allow_authored_title=True)
        frames, _suffix = conditions.split_frames(image[
            resource.presentation_offset:resource.presentation_offset + resource.presentation_allocation
        ])
        conditions.validate_frame_population(state.presentation_index, frames)
        total += sum(conditions.frame_kind(i, f) == "narration" for i, f in enumerate(frames))
        for record in records:
            if record.presentation_index != state.presentation_index:
                continue
            text = edits.get(record.id, record.base_text)
            validate_narration_text(record, text)
            mapping = (dialogue._s2_encoding_resources()[0]
                       if record.scenario == 2 else narration_mapping())
            literal, missing = _encode(text, mapping)
            dialogue.need(not missing, f"{record.id}: 최종 나레이션 인코딩 실패")
            try:
                actual = conditions.native_codec.expand(frames[record.frame_index], resource.dictionary_rows)
            except ValueError as exc:
                raise dialogue.DialogueError(f"{record.id}: 최종 나레이션 문자 형식 오류: {exc}") from exc
            dialogue.need(actual == PREFIX + literal + PAGE,
                          f"{record.id}: 최종 나레이션 본문 불일치")
            verified_records.append(record.id)
            if state.presentation_index in conditions.RESTORED_NARRATION_FRAMES:
                restored_records.append(record.id)
    dialogue.need(total == len(records), "최종 원문/편집기/게임 나레이션 수 불일치")
    dialogue.need(len(verified_records) == len(records), "최종 나레이션 본문 검사 누락")
    return {"presentations": len(states), "source_narration_records": len(records),
            "final_narration_records": total, "restored_presentation_texts_verified": restored_records,
            "expanded_authored_texts_verified": verified_records,
            "verified_after_last_writer": True,
            "scope": "Adopted catalogue only: frame populations and byte-exact expanded authored bodies in their installed glyph family. Not whole-game extraction, layout, semantic or runtime verification."}


def _script_residuals(text: str) -> list[str]:
    result: list[str] = []
    for character in text:
        if character == "・":
            continue
        code = ord(character)
        if 0x3040 <= code <= 0x30FF or 0x3400 <= code <= 0x9FFF:
            result.append(character)
    return sorted(set(result))


def _encode(text: str, mapping: dict[str, bytes] | None = None) -> tuple[bytes, list[str]]:
    mapping = narration_mapping() if mapping is None else mapping
    output = bytearray()
    missing: list[str] = []
    cursor = 0
    while cursor < len(text):
        if text[cursor] == "\n":
            output.append(0x08)
            cursor += 1
            continue
        match = TOKEN.match(text, cursor)
        if match:
            kind, raw = match.groups()
            value = int(raw, 16)
            if kind == "name":
                output.extend((0x09, value))
            elif kind == "dict":
                output.extend((0x04, value))
            else:
                output.append(value)
            cursor = match.end()
            continue
        character = text[cursor]
        lookup = "\u2009" if character == " " else character
        if lookup in mapping:
            output.extend(mapping[lookup])
        else:
            try:
                output.extend(paired_glyph(character, mapping))
            except UnicodeEncodeError:
                missing.append(character)
        cursor += 1
    return bytes(output), sorted(set(missing))


def _encode_for_record(
    record: NarrationRecord, text: str
) -> tuple[bytes, list[str]]:
    """Encode one narration frame with its installed scenario dictionary.

    Scenario 1 and Scenario 2 can use their installed phrase tables because
    those payloads live directly in the presentation aggregate.  Scenarios
    3-12 are repacked into dedicated local-dictionary records; those records
    must be literal so they never contain a second ``04 NN`` expansion.
    Explicit ``{dict:XX}`` tokens and uncommon raw controls keep the original
    literal encoder path; the editor therefore never rewrites a user-selected
    code behind their back.
    """
    if record.presentation_index == 82:
        plan = _presentation082_plan()
        phrase_codes = {
            str(row["phrase"]): int(row["code"], 0)
            for row in plan["dictionary"]["assignments"]
        }
        private_mapping = with_native_ascii(narration_mapping())
        try:
            encoded, _used = dialogue.encode_compressed(
                dialogue.engine_text(text),
                private_mapping,
                phrase_codes,
                1 << 20,
                prefer_parity=False,
            )
        except ValueError as exc:
            raise dialogue.DialogueError(
                f"{record.id}: 82번 연출 나레이션 사전 압축 실패: {exc}"
            ) from exc
        reverse = {
            code: character for character, code in private_mapping.items()
        }
        dictionary = {
            code: phrase for phrase, code in phrase_codes.items()
        }
        dialogue.need(
            dialogue.decode_candidate(encoded, reverse, dictionary)
            == dialogue.engine_text(text),
            f"{record.id}: 82번 연출 나레이션 사전 압축 왕복 실패",
        )
        return encoded, []
    if record.scenario is not None and 3 <= record.scenario <= 12:
        dialogue.need(
            not any(match.group(1) == "dict" for match in TOKEN.finditer(text)),
            f"{record.id}: 독립 나레이션 본문에는 사전 토큰을 넣을 수 없습니다.",
        )
        private_mapping = with_native_ascii(narration_mapping())
        phrase_codes = dialogue._early_full_phrase_codes(record.scenario)
        try:
            encoded, _used = dialogue.encode_compressed(
                dialogue.engine_text(text),
                private_mapping,
                phrase_codes,
                1 << 20,
                prefer_parity=False,
            )
        except ValueError as exc:
            raise dialogue.DialogueError(
                f"{record.id}: 3~12화 나레이션 사전 압축 실패: {exc}"
            ) from exc
        reverse = {
            code: character for character, code in private_mapping.items()
        }
        dictionary = {
            code: phrase for phrase, code in phrase_codes.items()
        }
        dialogue.need(
            dialogue.decode_candidate(encoded, reverse, dictionary)
            == dialogue.engine_text(text),
            f"{record.id}: 3~12화 나레이션 사전 압축 왕복 실패",
        )
        return encoded, []
    if record.scenario is not None and 1 <= record.scenario <= 2:
        explicit_dictionary = any(
            match.group(1) == "dict" for match in TOKEN.finditer(text)
        )
        raw_values = {
            int(match.group(2), 16)
            for match in TOKEN.finditer(text)
            if match.group(1) == "raw"
        }
        if not explicit_dictionary and raw_values <= {0x02}:
            if record.scenario == 1:
                # Temporary experiment constraint, not an established native
                # limit: successor214 and 217 also freeze using this low range.
                # Glyph-bank selection has not yet been isolated from ordinal
                # lookup. See successor217-runtime-reassessment-20260903.json.
                phrase_codes = {
                    phrase: code
                    for phrase, code in dialogue._s1_phrase_codes().items()
                    if code <= presentation_dict.RUNTIME_SOURCE_PRESERVE_MAX
                }
                private_mapping = narration_mapping()
            elif record.scenario == 2:
                private_mapping, phrase_codes = (
                    dialogue._s2_encoding_resources()
                )
            private_mapping = with_native_ascii(private_mapping)
            try:
                encoded, _used = dialogue.encode_compressed(
                    dialogue.engine_text(text),
                    private_mapping,
                    phrase_codes,
                    1 << 20,
                    prefer_parity=False,
                )
            except ValueError as exc:
                raise dialogue.DialogueError(
                    f"{record.id}: 나레이션 사전 압축 실패: {exc}"
                ) from exc
            reverse = {
                code: character
                for character, code in private_mapping.items()
            }
            dictionary = {
                code: phrase for phrase, code in phrase_codes.items()
            }
            decoded = dialogue.decode_candidate(encoded, reverse, dictionary)
            dialogue.need(
                decoded == dialogue.engine_text(text),
                f"{record.id}: 나레이션 사전 압축 왕복 검증 실패",
            )
            return encoded, []
    return _encode(text)


@lru_cache(maxsize=1)
def _presentation082_plan() -> dict:
    plan = json.loads(
        PRESENTATION082_PHRASE_EXTENSION.read_text(encoding="utf-8")
    )
    dialogue.need(
        plan.get("schema")
        == "langrisser-fx-presentation082-narration-phrase-extension/v1"
        and plan.get("status") == "prepared"
        and int(plan.get("presentation_index", -1)) == 82,
        "82번 연출 나레이션 사전 계획 형식 오류",
    )
    rows = list(plan["dictionary"]["assignments"])
    codes = [int(row["code"], 0) for row in rows]
    phrases = [str(row["phrase"]) for row in rows]
    dialogue.need(
        len(codes) == len(set(codes))
        and len(phrases) == len(set(phrases))
        and not set(codes).intersection(
            int(value, 0) for value in plan["dictionary"]["preserved_codes"]
        ),
        "82번 연출 나레이션 사전 소유권 중복",
    )
    return plan


def _presentation082_native_dictionary() -> tuple[bytes, int]:
    """Re-encode only the plan's owned phrases, preserving code identities.

The older manifest serialized ASCII as one byte. Its selected phrases remain
inputs, but their serialized bytes must follow the current native contract.
Unowned rows and the dictionary's extent remain unchanged.
"""
    plan = _presentation082_plan()["dictionary"]
    original = bytes.fromhex(str(plan["payload_hex"]))
    rows = list(presentation_dict._split_dictionary(original))
    for assignment in plan["assignments"]:
        payload, missing = _encode(str(assignment["phrase"]))
        dialogue.need(not missing, "82번 연출 사전 문구 인코딩 실패")
        conditions.native_codec.units(payload)
        rows[int(assignment["code"], 0) - 1] = payload
    packed = b"".join(row + b"\0" for row in rows)
    padding = len(original) - len(packed)
    dialogue.need(padding >= 0, f"82번 연출 원문 보존 사전 {-padding}바이트 초과")
    return packed + bytes(padding), padding


@lru_cache(maxsize=58)
def _later_narration_plan(scenario: int) -> dict:
    """Return the fixed Scenario 13~70 dictionary reservation plan."""

    dialogue.need(13 <= scenario <= 70,
                  f"후반 나레이션 시나리오 범위 오류: {scenario}")
    document = dialogue.load_json(
        dialogue.SCENARIO_DIALOGUE_PHRASE_EXTENSIONS
    )
    dialogue.need(
        document.get("schema")
        == "langrisser-fx-scenario-dialogue-phrase-extensions/v1"
        and document.get("status") == "prepared",
        "13~70화 나레이션 예약 자료 형식 오류",
    )
    row = next(
        (value for value in document["scenarios"]
         if int(value["scenario"]) == scenario),
        None,
    )
    dialogue.need(row is not None,
                  f"{scenario}화 나레이션 예약 자료 없음")
    return row


def _build_later_reserved_dictionary(
    resource: presentation_dict.LocalPresentationResource,
    scenario: int,
    edits: dict[str, str],
    records: tuple[NarrationRecord, ...],
) -> tuple[bytes, dict[str, int], dict]:
    """Fill only the codes pre-reserved by the Scenario 13~70 planner.

    The dialogue planner subtracts the complete narration payload budget
    before it assigns any phrase.  Reusing that exact plan keeps every live
    dialogue/common row fixed and avoids the destructive second dictionary
    repack that froze presentation playback.
    """

    plan = _later_narration_plan(scenario)
    planned = bytes.fromhex(str(plan["dictionary_payload_hex"]))
    # The planner owns the native zero-based sentinel immediately before the
    # section-4 row stream; locate_resource() starts at addressable code 01.
    dialogue.need(
        len(planned) == resource.dictionary_allocation + 1
        and planned[:1] == b"\0",
        f"{scenario}화 나레이션 예약 사전 경계 오류",
    )
    rows = list(presentation_dict._split_dictionary(planned[1:]))
    reserved_codes = sorted(
        (int(value, 0) for value in plan["narration_reserved_codes"]),
        reverse=True,
    )
    reservations = list(plan["narration_payload_reservations"])
    dialogue.need(
        len(reserved_codes) == len(reservations),
        f"{scenario}화 나레이션 예약 코드/레코드 수 불일치",
    )
    assignments = {
        str(reservation["id"]): code
        for reservation, code in zip(reservations, reserved_codes, strict=True)
    }
    known_ids = {record.id for record in records}
    dialogue.need(
        set(assignments) <= known_ids,
        f"{scenario}화 나레이션 예약 ID 불일치",
    )

    # User-added edits can use a genuinely empty planned row.  The fixed
    # dictionary byte budget below remains authoritative and rejects an edit
    # that would exceed it instead of clearing another consumer's row.
    extra_ids = sorted(set(edits) - set(assignments))
    extra_codes = [
        code for code in range(
            presentation_dict.MAX_PROVEN_DICTIONARY_CODE, 0, -1
        )
        if not rows[code - 1] and code not in reserved_codes
    ]
    dialogue.need(
        len(extra_ids) <= len(extra_codes),
        f"{scenario}화 사용자 나레이션 전용 코드 부족",
    )
    assignments.update(zip(extra_ids, extra_codes))

    by_id = {record.id: record for record in records}
    for record_id, code in assignments.items():
        if record_id not in edits:
            continue
        payload = validate_narration_text(by_id[record_id], edits[record_id])
        dialogue.need(
            not presentation_dict._references(payload),
            f"{record_id}: 후반 나레이션 예약 행의 중첩 참조 금지",
        )
        rows[code - 1] = payload
    packed = b"".join(row + b"\0" for row in rows)
    dialogue.need(
        len(packed) <= resource.dictionary_allocation,
        f"{scenario}화 나레이션 예약 사전 "
        f"{len(packed) - resource.dictionary_allocation}바이트 초과",
    )
    padding = resource.dictionary_allocation - len(packed)
    replacement = packed + bytes(padding)
    dialogue.need(
        len(replacement) == resource.dictionary_allocation,
        f"{scenario}화 나레이션 예약 사전 크기 변경",
    )
    return replacement, {
        record_id: code for record_id, code in assignments.items()
        if record_id in edits
    }, {
        "dictionary_storage_mode": "planned-reserved-rows",
        "dictionary_preserved_dialogue_rows": True,
        "dictionary_preserved_codes": list(
            plan["preserved_external_codes"]
        ),
        "dictionary_reserved_codes": [
            f"0x{code:02X}" for code in reserved_codes
        ],
        "dictionary_packed_bytes": len(packed),
        "dictionary_padding_bytes": padding,
    }


def _token_counter(text: str, kinds: tuple[str, ...]) -> Counter[str]:
    return Counter(
        match.group(0).lower() for match in TOKEN.finditer(text)
        if match.group(1) in kinds
    )


def validate_narration_text(record: NarrationRecord, text: str) -> bytes:
    dialogue.need("{page}" not in text and "\f" not in text,
                  f"{record.id}: 나레이션 한 장면에 페이지 토큰을 넣을 수 없습니다.")
    lines = text.split("\n")
    dialogue.need(1 <= len(lines) <= NARRATION_MAX_LINES,
                  f"{record.id}: 화면당 최대 4줄입니다.")
    widths = narration_line_widths(text)
    dialogue.need(
        all(width <= NARRATION_SAFE_WIDTH_PX for width in widths),
        f"{record.id}: 나레이션 줄 폭 {widths}/"
        f"{NARRATION_SAFE_WIDTH_PX}px 초과",
    )
    unknown = [token for token in ANY_BRACE.findall(text)
               if not TOKEN.fullmatch(token)]
    dialogue.need(not unknown,
                  f"{record.id}: 알 수 없는 토큰 {sorted(set(unknown))}")
    residuals = _script_residuals(text)
    dialogue.need(not residuals,
                  f"{record.id}: 일본어·한자 잔존 {', '.join(residuals)}")
    edited_tokens = _token_counter(text, ("name", "raw"))
    base_tokens = _token_counter(record.base_text, ("name", "raw"))
    source_tokens = _token_counter(record.source_text, ("name", "raw"))
    dialogue.need(edited_tokens in (base_tokens, source_tokens),
                  f"{record.id}: 동적 이름·주인공 토큰을 보존해야 합니다.")
    encoded, missing = _encode_for_record(record, text)
    dialogue.need(not missing,
                  f"{record.id}: 지원하지 않는 글자 {', '.join(missing)}")
    dialogue.need(b"\0" not in encoded and PAGE not in encoded,
                  f"{record.id}: 나레이션 제어 구조 침범")
    try:
        conditions.native_codec.units(encoded)
    except ValueError as exc:
        raise dialogue.DialogueError(f"{record.id}: 나레이션 문자 형식 오류: {exc}") from exc
    return encoded


def _compile_presentation(
    state: conditions.PresentationState,
    current: bytes,
    edits: dict[str, str],
    records: tuple[NarrationRecord, ...],
    dictionary_codes: dict[str, int] | None = None,
    title_dictionary_code: int | None = None,
    literalize_title: bool | None = None,
    output_allocation: int | None = None,
    force_literal_records: bool = False,
) -> tuple[bytes, dict]:
    dialogue.need(len(current) == state.allocation,
                  f"{state.label}: 나레이션 묶음 크기 오류")
    frames, suffix = conditions.split_frames(current)
    target_allocation = (
        state.allocation if output_allocation is None else output_allocation
    )
    dialogue.need(target_allocation > 0,
                  f"{state.label}: 나레이션 출력 묶음 크기 오류")
    dialogue.need(len(frames) == len(state.frames),
                  f"{state.label}: 현재 나레이션 프레임 수 변경")
    rebuilt = list(frames)
    missing_indexes = conditions.validate_frame_population(
        state.presentation_index, frames, allow_missing_restorations=True,
    )
    for index in missing_indexes:
        dialogue.need(any(r.frame_index == index and r.id in edits for r in records),
                      f"{state.label}: 누락 문단 복구 입력 없음")
        rebuilt.insert(index, PREFIX + PAGE)
    edited_indexes: set[int] = set()
    title_dictionary_dependency_removed = False
    scenario_title = SCENARIO.match(state.label)
    # Scenario 1's code 01 remains the original immutable SCENARIO- owner and
    # its aggregate has no room for the sixteen-byte literal expansion.  All
    # later scenarios remove the mutable dictionary dependency outright.
    replace_title = (
        state.presentation_index != 1
        if literalize_title is None
        else literalize_title
    )
    if scenario_title and replace_title:
        title = rebuilt[0]
        indirect = (
            PREFIX + b"\x08" + TITLE_DICTIONARY_TOKEN
            + TITLE_DYNAMIC_SUFFIX
        )
        direct = (
            PREFIX + b"\x08" + TITLE_LITERAL
            + TITLE_DYNAMIC_SUFFIX
        )
        external = (
            (SCENARIO02_CENTERED_PREFIX if state.presentation_index == 2
             and title_dictionary_code is not None else PREFIX + b"\x08")
            + (
                bytes((0x04, title_dictionary_code))
                if title_dictionary_code is not None
                else TITLE_LITERAL
            )
            + TITLE_DYNAMIC_SUFFIX
        )
        if title.startswith(indirect):
            rebuilt[0] = external + title[len(indirect):]
            edited_indexes.add(0)
            title_dictionary_dependency_removed = True
        elif title.startswith(direct):
            rebuilt[0] = external + title[len(direct):]
            if rebuilt[0] != title:
                edited_indexes.add(0)
        else:
            dialogue.need(
                title.startswith(external),
                f"{state.label}: SCENARIO 제목 프레임 구조 변경",
            )
    restoration_title_audit = None
    if missing_indexes:
        # The pinned S12 title also contains duplicated narration. Its adopted
        # title repair owns those bytes and must precede aggregate capacity
        # validation; applying it only after insertion falsely rejects the
        # full paragraph. Reuse the exact title owner, not a second repair rule.
        from scenario_title_core import center_frame
        title, restoration_title_audit = center_frame(rebuilt[0], state.presentation_index)
        if title != rebuilt[0]:
            rebuilt[0] = title
            edited_indexes.add(0)
    if state.presentation_index in missing_presentations.INDICES:
        rebuilt[0] = missing_presentation_title(state.presentation_index, rebuilt[0])
        edited_indexes.add(0)
    for record in records:
        if record.id not in edits:
            continue
        edited_indexes.add(record.frame_index)
        encoded = validate_narration_text(record, edits[record.id])
        if force_literal_records:
            encoded, missing = _encode(edits[record.id])
            dialogue.need(
                not missing and b"\0" not in encoded and PAGE not in encoded,
                f"{record.id}: 리터럴 나레이션 인코딩 실패 {missing}",
            )
        if dictionary_codes is not None and record.id in dictionary_codes:
            encoded = bytes((0x04, dictionary_codes[record.id]))
        rebuilt[record.frame_index] = PREFIX + encoded + PAGE
    final_index = len(rebuilt) - 1
    visible_final, old_padding = conditions._strip_last_padding(
        rebuilt[final_index], narration_mapping()
    )
    rebuilt[final_index] = visible_final
    unpadded = sum(map(len, rebuilt)) + len(suffix)
    padding = target_allocation - unpadded
    reclaimed_zero_suffix = 0
    if padding < 0 and suffix == bytes(len(suffix)):
        # Several bonus/development presentations reserve a large zero tail
        # inside the presentation's owned section.  It is storage padding,
        # not another consumer.  Let authored frames grow into that tail and
        # recreate a zero tail after the final PAGE marker; section offsets,
        # frame count, and the following section all remain unchanged.
        frame_bytes = sum(map(len, rebuilt))
        padding = target_allocation - frame_bytes
        dialogue.need(
            padding >= 0,
            f"{state.label}: 0 패딩 회수 후에도 나레이션 묶음 "
            f"{-padding}바이트 초과",
        )
        reclaimed_zero_suffix = len(suffix)
        replacement = b"".join(rebuilt) + bytes(padding)
    else:
        dialogue.need(padding >= 0,
                      f"{state.label}: 나레이션 묶음 {-padding}바이트 초과")
        final = bytearray(rebuilt[final_index][:-len(PAGE)])
        if len(old_padding) == padding:
            final.extend(old_padding)
        else:
            remaining = padding
            if remaining & 1:
                final.append(0x05)
                remaining -= 1
            final.extend(narration_mapping()["\u2009"] * (remaining // 2))
        rebuilt[final_index] = bytes(final) + PAGE
        replacement = b"".join(rebuilt) + suffix
    dialogue.need(len(replacement) == target_allocation,
                  f"{state.label}: 나레이션 묶음 크기 변경")
    for index, frame in enumerate(frames):
        target_index = index
        for inserted in missing_indexes:
            if inserted <= target_index:
                target_index += 1
        if target_index not in edited_indexes and target_index != final_index:
            dialogue.need(rebuilt[target_index] == frame,
                          f"{state.label}: 비소유 프레임 변경")
    conditions.validate_frame_population(state.presentation_index, rebuilt)
    return replacement, {
        "presentation_index": state.presentation_index,
        "label": state.label,
        "edited_records": sorted(edits),
        "padding_bytes": padding,
        "input_allocation_bytes": state.allocation,
        "output_allocation_bytes": target_allocation,
        "reclaimed_trailing_zero_padding_bytes": reclaimed_zero_suffix,
        "condition_frames_preserved": True,
        "restored_source_frame_indexes": list(missing_indexes),
        "restoration_prerequisite_title": restoration_title_audit,
        "glyph_aliases": 0,
        "space_owners_distinct": True,
        "lossless_local_dictionary": bool(dictionary_codes),
        "local_dictionary_records": len(dictionary_codes or {}),
        "direct_literal_records": sum(
            record.id in edits
            and (dictionary_codes is None or record.id not in dictionary_codes)
            for record in records
        ),
        "scenario_title_dictionary_dependency_removed": (
            title_dictionary_dependency_removed
        ),
        "scenario_title_literal": (
            "SCENARIO-0 + runtime scenario number"
            if scenario_title and replace_title else None
        ),
        "scenario02_title_dictionary_dependency_removed": (
            title_dictionary_dependency_removed
            if state.presentation_index == 2 else False
        ),
        "scenario02_title_literal": (
            (
                "local external SCENARIO- + runtime scenario number"
                if title_dictionary_code is not None
                else "SCENARIO-0 + runtime scenario number"
            )
            if state.presentation_index == 2 else None
        ),
    }


def _dictionary_closure(
    resource: presentation_dict.LocalPresentationResource,
    direct: set[int],
) -> set[int]:
    """Expand direct local-dictionary owners through their dependencies."""

    closure = set(direct)
    pending = list(direct)
    while pending:
        code = pending.pop()
        dialogue.need(
            1 <= code <= len(resource.dictionary_rows),
            f"로컬 사전 범위 밖 참조: 0x{code:02X}",
        )
        for dependency in presentation_dict._references(
            resource.dictionary_rows[code - 1]
        ):
            if dependency not in closure:
                closure.add(dependency)
                pending.append(dependency)
    return closure


def _build_scenario01_balanced_presentation(
    image: bytes | bytearray,
    state: conditions.PresentationState,
    edits: dict[str, str],
    records: tuple[NarrationRecord, ...],
) -> BalancedPresentationPatch:
    """Keep every Scenario-1 frame within its proved native byte span.

    The runtime-green 184-pixel PoC established a five-byte
    ``05 04 NN 06 07`` root and one literal dictionary body.  Only adopted
    pages longer than their source frame spans use that path here.  Codes are
    taken exclusively from the released pages, every other dictionary row is
    preserved, and section 4 grows by exactly the bytes reclaimed from
    section 7.  The outer resource end remains fixed.
    """

    dialogue.need(state.presentation_index == 1,
                  "1화 균형 재배치에 다른 연출이 들어왔습니다.")
    resource = presentation_dict.locate_resource(image, state.offset)
    current = bytes(image[
        resource.presentation_offset:
        resource.presentation_offset + resource.presentation_allocation
    ])
    live_frames, live_suffix = conditions.split_frames(current)
    dialogue.need(len(live_frames) == len(state.frames),
                  "1화 현재 프레젠테이션 프레임 수 변경")
    live_state = conditions.PresentationState(
        presentation_index=state.presentation_index,
        label=state.label,
        offset=resource.presentation_offset,
        allocation=resource.presentation_allocation,
        frames=tuple(live_frames),
        suffix=live_suffix,
        condition_frame_indexes=tuple(
            index for index, frame in enumerate(live_frames)
            if conditions.frame_kind(index, frame).endswith("condition")
        ),
    )

    direct_replacement, _direct_audit = _compile_presentation(
        live_state,
        current,
        edits,
        records,
        literalize_title=False,
    )
    direct_frames, _direct_suffix = conditions.split_frames(direct_replacement)
    external_records = tuple(
        record for record in records
        if record.id in edits
        and len(direct_frames[record.frame_index])
        > len(state.frames[record.frame_index])
    )
    dialogue.need(external_records,
                  "1화에는 원본 프레임 길이를 넘는 나레이션이 없습니다.")
    released_indexes = frozenset(
        record.frame_index for record in external_records
    )

    direct_kept: set[int] = set()
    # A presentation dictionary is shared by every nested section in this
    # resource, not just the visible narration aggregate.  The earlier
    # allocator skipped sections 0-2 and could consequently overwrite a row
    # still used by the map/title setup before the first narration page.  Scan
    # the complete non-dictionary prefix plus sections 5-6, then add every
    # narration frame that will remain in place.
    direct_kept.update(presentation_dict._references(bytes(image[
        resource.header_offset:resource.sections[4]
    ])))
    direct_kept.update(presentation_dict._references(bytes(image[
        resource.sections[5]:resource.sections[7]
    ])))
    for index, frame in enumerate(direct_frames):
        if index not in released_indexes:
            direct_kept.update(presentation_dict._references(frame))
    direct_kept.update(presentation_dict.RUNTIME_RESERVED_DICTIONARY_CODES)
    kept_codes = _dictionary_closure(resource, direct_kept)
    # Any row outside the reachable closure is genuinely dormant and can own
    # an external narration body.  Restricting candidates to phrases used by
    # the released frames was unsafe: those same phrases can also be consumed
    # by the omitted setup sections above.
    candidate_codes = sorted(
        set(range(1, len(resource.dictionary_rows) + 1)) - kept_codes,
        key=lambda code: (-len(resource.dictionary_rows[code - 1]), code),
    )
    dialogue.need(
        len(candidate_codes) >= len(external_records),
        "1화 해제 프레임만 소유한 로컬 사전 코드가 부족합니다.",
    )

    payload_rows: list[tuple[str, bytes]] = []
    for record in external_records:
        payload, missing = _encode(edits[record.id])
        dialogue.need(not missing,
                      f"{record.id}: 외부 본문 미지원 글자 {missing}")
        dialogue.need(
            payload and b"\0" not in payload
            and PAGE not in payload
            and not presentation_dict._references(payload),
            f"{record.id}: 외부 본문 제어 구조 오류",
        )
        payload_rows.append((record.id, payload))
    payload_rows.sort(key=lambda row: (-len(row[1]), row[0]))
    assignments = {
        record_id: code
        for (record_id, _payload), code in zip(
            payload_rows, candidate_codes, strict=False
        )
    }
    dialogue.need(len(assignments) == len(payload_rows),
                  "1화 외부 본문 코드 배정 수 불일치")

    dictionary_rows = list(resource.dictionary_rows)
    payload_by_id = dict(payload_rows)
    replaced_rows: list[dict[str, object]] = []
    for record_id, code in assignments.items():
        old = dictionary_rows[code - 1]
        payload = payload_by_id[record_id]
        dictionary_rows[code - 1] = payload
        replaced_rows.append({
            "record_id": record_id,
            "code": f"0x{code:02X}",
            "old_payload_bytes": len(old),
            "new_payload_bytes": len(payload),
        })
    dictionary_replacement = b"".join(
        row + b"\0" for row in dictionary_rows
    )
    dictionary_growth = (
        len(dictionary_replacement) - resource.dictionary_allocation
    )
    dialogue.need(dictionary_growth > 0,
                  "1화 균형 재배치가 실제 사전 확장을 만들지 않았습니다.")
    output_allocation = (
        resource.presentation_allocation - dictionary_growth
    )
    presentation_replacement, audit = _compile_presentation(
        live_state,
        current,
        edits,
        records,
        dictionary_codes=assignments,
        literalize_title=False,
        output_allocation=output_allocation,
    )
    final_frames, final_suffix = conditions.split_frames(
        presentation_replacement
    )
    external_ids = {record.id for record in external_records}
    for record in records:
        if record.id not in edits:
            continue
        if record.id in external_ids:
            dialogue.need(
                final_frames[record.frame_index]
                == PREFIX + bytes((0x04, assignments[record.id])) + PAGE,
                f"{record.id}: 외부 루트 왕복 실패",
            )
        else:
            dialogue.need(
                len(final_frames[record.frame_index])
                <= len(state.frames[record.frame_index]),
                f"{record.id}: 원본 프레임 길이 제한 초과",
            )
    dialogue.need(not any(final_suffix),
                  "1화 균형 재배치 뒤 프레젠테이션 꼬리 오염")

    old_offsets = list(resource.section_offsets)
    new_offsets = list(old_offsets)
    for index in (5, 6, 7):
        new_offsets[index] += dictionary_growth
    dialogue.need(new_offsets[8] == old_offsets[8],
                  "1화 바깥 자원 끝 주소 변경")
    section5 = bytes(image[resource.sections[5]:resource.sections[6]])
    section6 = bytes(image[resource.sections[6]:resource.sections[7]])
    old_middle = bytes(image[
        resource.sections[4]:resource.sections[8]
    ])
    new_middle = (
        dictionary_replacement
        + section5
        + section6
        + presentation_replacement
    )
    dialogue.need(len(new_middle) == len(old_middle),
                  "1화 균형 재배치 바깥 크기 변경")
    offsets_start = resource.header_offset + 8 + 5 * 4
    offsets_replacement = b"".join(
        int(value).to_bytes(4, "little") for value in new_offsets[5:8]
    )
    audit.update({
        "storage_mode": "balanced-native-frame-external-roots",
        "native_frame_limit_enforced": True,
        "external_records": [record.id for record in external_records],
        "external_assignments": {
            record_id: f"0x{code:02X}"
            for record_id, code in assignments.items()
        },
        "external_rows": replaced_rows,
        "released_frame_indexes": sorted(released_indexes),
        "candidate_codes": [f"0x{code:02X}" for code in candidate_codes],
        "preserved_dictionary_rows": (
            len(dictionary_rows) - len(assignments)
        ),
        "cleared_dictionary_rows": 0,
        "dictionary_old_allocation_bytes": resource.dictionary_allocation,
        "dictionary_new_allocation_bytes": len(dictionary_replacement),
        "dictionary_growth_bytes": dictionary_growth,
        "presentation_old_allocation_bytes": (
            resource.presentation_allocation
        ),
        "presentation_new_allocation_bytes": len(presentation_replacement),
        "outer_container_delta_bytes": 0,
        "old_section_offsets": [f"0x{value:X}" for value in old_offsets],
        "new_section_offsets": [f"0x{value:X}" for value in new_offsets],
        "dictionary_nested_references": 0,
        "semantic_abbreviation": False,
    })
    return BalancedPresentationPatch(
        patches=(
            (
                offsets_start,
                offsets_replacement,
                "narrations/scenario01-balanced-section-offsets",
            ),
            (
                resource.sections[4],
                new_middle,
                "narrations/scenario01-balanced-dictionary-through-presentation",
            ),
        ),
        audit=audit,
    )


def _compile_late_presentation(
    image: bytes | bytearray,
    state: conditions.PresentationState,
    edits: dict[str, str],
    records: tuple[NarrationRecord, ...],
) -> tuple[presentation_dict.LocalPresentationResource, bytes, bytes, dict]:
    """Compile Scenario 13+ narration without shortening authored text."""

    resource = presentation_dict.locate_resource(image, state.offset)
    current = bytes(image[
        resource.presentation_offset:
        resource.presentation_offset + resource.presentation_allocation
    ])
    if state.presentation_index == 82:
        plan = _presentation082_plan()
        dictionary_current = bytes(image[
            resource.dictionary_offset:
            resource.dictionary_offset + resource.dictionary_allocation
        ])
        dialogue.need(
            hashlib.sha256(dictionary_current).hexdigest().upper()
            == str(plan["dictionary"]["base_sha256"]),
            "82번 연출 나레이션 사전 기준 바이트 변경",
        )
        dictionary_replacement, native_padding = _presentation082_native_dictionary()
        dialogue.need(
            len(dictionary_replacement) == resource.dictionary_allocation,
            "82번 연출 나레이션 사전 payload 크기 오류",
        )
        live_frames, live_suffix = conditions.split_frames(current)
        live_state = conditions.PresentationState(
            presentation_index=state.presentation_index,
            label=state.label,
            offset=resource.presentation_offset,
            allocation=resource.presentation_allocation,
            frames=tuple(live_frames),
            suffix=live_suffix,
            condition_frame_indexes=tuple(
                index for index, frame in enumerate(live_frames)
                if conditions.frame_kind(index, frame).endswith("condition")
            ),
        )
        replacement, audit = _compile_presentation(
            live_state, current, edits, records
        )
        audit.update({
            "resource_header_offset": f"0x{resource.header_offset:08X}",
            "dictionary_offset": f"0x{resource.dictionary_offset:08X}",
            "dictionary_capacity_bytes": resource.dictionary_allocation,
            "dictionary_packed_bytes": (
                resource.dictionary_allocation
                - native_padding
            ),
            "dictionary_padding_bytes": native_padding,
            "dictionary_preserved_codes": list(
                plan["dictionary"]["preserved_codes"]
            ),
            "dictionary_phrase_owners": len(
                plan["dictionary"]["assignments"]
            ),
            "dictionary_roundtrip_records": len(records),
            "semantic_abbreviation": False,
        })
        return resource, dictionary_replacement, replacement, audit

    # The live resource header, not the historical catalogue, owns Scenario
    # 16's corrected +4-byte section-7 boundary.
    live_frames, live_suffix = conditions.split_frames(current)
    live_state = conditions.PresentationState(
        presentation_index=state.presentation_index,
        label=state.label,
        offset=resource.presentation_offset,
        allocation=resource.presentation_allocation,
        frames=tuple(live_frames),
        suffix=live_suffix,
        condition_frame_indexes=tuple(
            index for index, frame in enumerate(live_frames)
            if conditions.frame_kind(index, frame).endswith("condition")
        ),
    )
    scenario = records[0].scenario if records else None
    dialogue.need(
        all(record.scenario == scenario for record in records),
        f"{state.label}: 나레이션 시나리오 소유권 혼합",
    )

    if scenario is not None and 1 <= scenario <= 12:
        # The Scenario 1/2 and 3~12 dialogue planners already include the
        # complete narration compression vocabulary.  Re-encode the frames
        # against that installed table and leave every dictionary byte alone.
        # Scenario 2 and Scenario 4~12 inherited a non-title code 01, so only
        # those resources store SCENARIO- literally in the title frame.
        title_row = b"\x05\x05" + TITLE_LITERAL
        literalize_title = resource.dictionary_rows[0] != title_row
        title_dictionary_code = None
        if scenario == 2:
            scenario02_plan = dialogue.load_json(
                dialogue.S2_DIALOGUE_NARRATION_PHRASE_EXTENSION
            )
            title_dictionary_code = int(
                scenario02_plan["dictionary"]["presentation_title_code"], 0
            )
        replacement, audit = _compile_presentation(
            live_state,
            current,
            edits,
            records,
            title_dictionary_code=title_dictionary_code,
            literalize_title=literalize_title,
        )
        dictionary_current = bytes(image[
            resource.dictionary_offset:
            resource.dictionary_offset + resource.dictionary_allocation
        ])
        audit.update({
            "resource_header_offset": f"0x{resource.header_offset:08X}",
            "dictionary_offset": f"0x{resource.dictionary_offset:08X}",
            "dictionary_capacity_bytes": resource.dictionary_allocation,
            "dictionary_packed_bytes": resource.dictionary_allocation,
            "dictionary_padding_bytes": 0,
            "dictionary_storage_mode": "installed-shared-phrase-plan",
            "dictionary_preserved_byte_exact": True,
            "dictionary_unique_record_codes": (
                {LOCAL_TITLE_RECORD_ID: f"0x{title_dictionary_code:02X}"}
                if title_dictionary_code is not None else {}
            ),
            "dictionary_roundtrip_records": (
                len(edits) + (title_dictionary_code is not None)
            ),
            "dictionary_direct_literal_records": len(edits),
            "dictionary_nested_references": 0,
            "semantic_abbreviation": False,
        })
        return resource, dictionary_current, replacement, audit

    if scenario is not None and 13 <= scenario <= 70:
        dictionary_replacement, assignments, dictionary_audit = (
            _build_later_reserved_dictionary(
                resource, scenario, edits, records
            )
        )
        replacement, audit = _compile_presentation(
            live_state,
            current,
            edits,
            records,
            assignments,
            literalize_title=False,
        )
        audit.update({
            "resource_header_offset": f"0x{resource.header_offset:08X}",
            "dictionary_offset": f"0x{resource.dictionary_offset:08X}",
            "dictionary_capacity_bytes": resource.dictionary_allocation,
            "dictionary_unique_record_codes": {
                record_id: f"0x{code:02X}"
                for record_id, code in assignments.items()
            },
            "dictionary_roundtrip_records": len(assignments),
            "dictionary_direct_literal_records": 0,
            "dictionary_nested_references": 0,
            "semantic_abbreviation": False,
            **dictionary_audit,
        })
        return resource, dictionary_replacement, replacement, audit

    payload_rows: list[tuple[str, bytes]] = []
    for record in records:
        if record.id not in edits:
            continue
        # Scenario 1 has a runtime-green external-record proof.  Its ordinary
        # encoder emits phrase references; storing those references inside a
        # second dictionary row would create an unsafe nested expansion.
        if state.presentation_index in {1, 2}:
            encoded, missing = _encode(edits[record.id])
            dialogue.need(
                not missing,
                f"{record.id}: 지원하지 않는 글자 {', '.join(missing)}",
            )
            dialogue.need(
                b"\0" not in encoded and PAGE not in encoded,
                f"{record.id}: 외부 나레이션 제어 구조 침범",
            )
        else:
            encoded = validate_narration_text(record, edits[record.id])
        payload_rows.append((record.id, encoded))
    payloads = tuple(payload_rows)
    released_indexes = frozenset(
        record.frame_index for record in records if record.id in edits
    )
    # Prefer full per-record local ownership.  A few dense early-scenario
    # dictionaries cannot hold every literal body as a second copy.  In that
    # case choose the smallest high-yield subset that gives the presentation
    # enough room for its literal SCENARIO title; all remaining bodies stay
    # literal in the presentation itself and no nested dictionary is created.
    candidates: list[tuple[tuple[str, bytes], ...]] = [payloads]
    if len(payloads) > 1:
        for count in range(1, len(payloads)):
            groups = list(combinations(payloads, count))
            groups.sort(
                key=lambda group: sum(len(payload) for _id, payload in group),
                reverse=True,
            )
            candidates.extend(groups)
    # Some resources (notably Scenario 10) genuinely use every non-item
    # dictionary code.  The former allocator escaped that pressure only by
    # overwriting fixed-address item-name rows 205..239.  If the authored
    # presentation still fits directly, keep every narration body literal
    # and allocate no local record at all.
    candidates.append(tuple())
    if state.presentation_index == 2:
        title_payload = (LOCAL_TITLE_RECORD_ID, TITLE_LITERAL)
        candidates = [candidate + (title_payload,) for candidate in candidates]
        candidates.append((title_payload,))
    selected: tuple[tuple[str, bytes], ...] | None = None
    dictionary_plan: presentation_dict.DictionaryPlan | None = None
    replacement: bytes | None = None
    audit: dict | None = None
    failures: list[str] = []
    for candidate in candidates:
        try:
            plan = presentation_dict.build_dictionary_plan(
                image,
                resource,
                candidate,
                released_presentation_frame_indexes=released_indexes,
                preserve_all_source_rows=(state.presentation_index != 2),
            )
            assignments = dict(plan.assignments)
            title_code = assignments.pop(LOCAL_TITLE_RECORD_ID, None)
            trial, trial_audit = _compile_presentation(
                live_state,
                current,
                edits,
                records,
                assignments,
                title_code,
            )
        except dialogue.DialogueError as exc:
            failures.append(str(exc))
            continue
        selected = candidate
        dictionary_plan = plan
        replacement = trial
        audit = trial_audit
        break
    dialogue.need(
        selected is not None
        and dictionary_plan is not None
        and replacement is not None
        and audit is not None,
        f"{state.label}: 독립 나레이션 저장 조합 없음: "
        + " | ".join(dict.fromkeys(failures)),
    )
    codes = dict(dictionary_plan.assignments)
    audit.update({
        "resource_header_offset": f"0x{resource.header_offset:08X}",
        "dictionary_offset": f"0x{resource.dictionary_offset:08X}",
        "dictionary_capacity_bytes": resource.dictionary_allocation,
        "dictionary_packed_bytes": dictionary_plan.packed_bytes,
        "dictionary_padding_bytes": dictionary_plan.padding_bytes,
        "dictionary_preserved_codes": [
            f"0x{code:02X}" for code in dictionary_plan.preserved_codes
        ],
        "dictionary_minimal_cleared_codes": [
            f"0x{code:02X}" for code in dictionary_plan.cleared_codes
        ],
        "dictionary_unique_record_codes": {
            record_id: f"0x{code:02X}"
            for record_id, code in dictionary_plan.assignments
        },
        "dictionary_roundtrip_records": len(dictionary_plan.assignments),
        "dictionary_direct_literal_records": len(payloads) - len(selected),
        "dictionary_nested_references": 0,
        "semantic_abbreviation": False,
    })
    return resource, dictionary_plan.replacement, replacement, audit


def validate_narration_project(edits: dict[str, str]) -> None:
    records = load_narration_records()
    by_id = {row.id: row for row in records}
    dialogue.need(not (set(edits) - set(by_id)), "알 수 없는 나레이션 ID")
    effective = _effective_edits(records, edits)
    for record_id, text in effective.items():
        validate_narration_text(by_id[record_id], text)
    if not effective:
        return
    _condition_records, states = conditions.load_condition_data()
    state_by_index = {row.presentation_index: row for row in states}
    touched = sorted({
        by_id[record_id].presentation_index for record_id in effective
    })
    cooked = dialogue.BASE_DIR / dialogue.BASE_COOKED_NAME
    with cooked.open("rb") as stream:
        image = stream.read()
        for presentation_index in touched:
            state = state_by_index[presentation_index]
            local_records = tuple(
                row for row in records
                if row.presentation_index == presentation_index
            )
            local_edits = {
                record_id: effective[record_id] for record_id in effective
                if by_id[record_id].presentation_index == presentation_index
            }
            if presentation_index == 1:
                # Exact packing depends on the live post-dialogue dictionary.
                # The product build performs that fail-closed repack below;
                # all authored frame constraints were validated above.
                continue
            _compile_late_presentation(
                image, state, local_edits, local_records
            )


def build_narration_patches(
    image: bytes | bytearray,
    edits: dict[str, str],
    *,
    require_runtime_dictionary: bool = True,
) -> tuple[tuple[tuple[int, bytes, str], ...], dict]:
    validate_narration_project(edits)
    records = load_narration_records()
    by_id = {row.id: row for row in records}
    effective = _effective_edits(records, edits)
    _condition_records, states = conditions.load_condition_data()
    state_by_index = {row.presentation_index: row for row in states}
    touched = sorted({
        by_id[record_id].presentation_index for record_id in effective
    })
    patches: list[tuple[int, bytes, str]] = []
    audit_rows: list[dict] = []
    for presentation_index in touched:
        state = state_by_index[presentation_index]
        local_records = tuple(
            row for row in records if row.presentation_index == presentation_index
        )
        local_edits = {
            record_id: effective[record_id] for record_id in effective
            if by_id[record_id].presentation_index == presentation_index
        }
        scenario = local_records[0].scenario if local_records else None
        if scenario == 1:
            resource = presentation_dict.locate_resource(image, state.offset)
            scenario01_plan = dialogue.load_json(
                dialogue.SCENARIO01_DIALOGUE_PHRASE_EXTENSION
            )
            installed_dictionary = bytes(image[
                resource.dictionary_offset:
                resource.dictionary_offset + resource.dictionary_allocation
            ])
            expected_dictionary = bytes.fromhex(
                str(scenario01_plan["dictionary"]["payload_hex"])
            )
            # The dialogue writer applies the source-verified placeholder
            # glyph repairs to codes 02/03 before narration is compiled.
            # Narration shares this live dictionary, so compare against the
            # composed post-dialogue payload rather than the older extension
            # plan in isolation.
            def encode_repaired_phrase(text: str) -> bytes:
                encoded, missing = dialogue.encode_plain(
                    text, dialogue.all_dialogue_private_mapping()
                )
                dialogue.need(not missing,
                              "1화 복원 기호 공동 사전 인코딩 누락")
                return encoded

            expected_dictionary, _reference_repairs = (
                dialogue.reference_glyph_repairs.scenario01_payload(
                    expected_dictionary, encode_repaired_phrase
                )
            )
            if installed_dictionary == expected_dictionary:
                current = bytes(image[
                    resource.presentation_offset:
                    resource.presentation_offset
                    + resource.presentation_allocation
                ])
                live_frames, live_suffix = conditions.split_frames(current)
                dialogue.need(
                    len(live_frames) == len(state.frames),
                    "1화 현재 프레젠테이션 프레임 수 변경",
                )
                live_state = conditions.PresentationState(
                    presentation_index=state.presentation_index,
                    label=state.label,
                    offset=resource.presentation_offset,
                    allocation=resource.presentation_allocation,
                    frames=tuple(live_frames),
                    suffix=live_suffix,
                    condition_frame_indexes=tuple(
                        index for index, frame in enumerate(live_frames)
                        if conditions.frame_kind(index, frame).endswith(
                            "condition"
                        )
                    ),
                )
                direct_replacement, direct_audit = _compile_presentation(
                    live_state,
                    current,
                    local_edits,
                    local_records,
                    literalize_title=False,
                    force_literal_records=False,
                )
                direct_frames, _direct_suffix = conditions.split_frames(
                    direct_replacement
                )
                # Preserve a compact final frame and a zero tail for this
                # experiment. This matches the native padding position, but
                # successor215/217 still froze, so it is not a proven fix for
                # the title-to-narration transition.
                visible_final, _final_padding = conditions._strip_last_padding(
                    direct_frames[-1], narration_mapping()
                )
                direct_frames[-1] = visible_final
                visible_bytes = sum(map(len, direct_frames))
                trailing_zeros = (
                    resource.presentation_allocation - visible_bytes
                )
                dialogue.need(
                    trailing_zeros >= 1,
                    "1화 프레젠테이션 종료 0 패딩 부족",
                )
                direct_replacement = (
                    b"".join(direct_frames) + bytes(trailing_zeros)
                )
                direct_audit["trailing_zero_padding_bytes"] = trailing_zeros
                direct_audit["final_frame_internal_padding_bytes"] = 0
                # Frames are PAGE-delimited inside one aggregate; the
                # runtime-green PoC already proved that their boundaries may
                # move.  What must remain fixed is the aggregate allocation.
                # The current path uses dictionary-compressed records. Its
                # runtime compatibility is unresolved; no observation proves
                # that the dictionary expires after the title page.
                native_fit = all(
                    len(replacement_frame) <= len(source_frame)
                    for replacement_frame, source_frame
                    in zip(direct_frames, live_frames)
                )
                if native_fit:
                    direct_audit.update({
                        "storage_mode": "fixed-native-frame-shared-dictionary-zero-tail",
                        "native_frame_limit_enforced": True,
                        "aggregate_allocation_enforced": True,
                        "external_records": [],
                        "external_assignments": {},
                        "cleared_dictionary_rows": 0,
                        "dictionary_growth_bytes": 0,
                        "outer_container_delta_bytes": 0,
                        "semantic_abbreviation": False,
                    })
                    patches.append((
                        resource.presentation_offset,
                        direct_replacement,
                        "narrations/scenario01-fixed-native-frames",
                    ))
                    audit_rows.append(direct_audit)
                    continue
                balanced = _build_scenario01_balanced_presentation(
                    image, state, local_edits, local_records
                )
                audit_rows.append(balanced.audit)
                patches.extend(balanced.patches)
                continue
            dialogue.need(
                not require_runtime_dictionary,
                "1화 런타임 안전 나레이션 전에 공동 대사 사전이 "
                "설치되지 않았습니다.",
            )
        # Scenario 3 onward and the non-scenario bonus/development
        # presentations have their own local presentation dictionaries.  Use
        # those for complete Korean narration instead of forcing long prose
        # into the old fixed body.  Scenario 1 uses the same external-record
        # path proven by its 184 px runtime PoC.  Scenario 2 uses the same
        # local record mechanism while its separately addressed condition
        # container remains fixed and is restored by the final condition pass.
        late = True
        if late:
            resource, dictionary_replacement, replacement, audit = (
                _compile_late_presentation(
                    image, state, local_edits, local_records
                )
            )
            dictionary_current = bytes(image[
                resource.dictionary_offset:
                resource.dictionary_offset + resource.dictionary_allocation
            ])
            dictionary_changed = dictionary_replacement != dictionary_current
            audit["dictionary_write_required"] = dictionary_changed
            if dictionary_changed:
                patches.append((
                    resource.dictionary_offset,
                    dictionary_replacement,
                    f"narrations/dictionary-{presentation_index:03d}",
                ))
            patch_offset = resource.presentation_offset
            current = bytes(image[
                patch_offset:patch_offset + resource.presentation_allocation
            ])
        else:
            current = bytes(image[state.offset:state.offset + state.allocation])
            replacement, audit = _compile_presentation(
                state, current, local_edits, local_records
            )
            patch_offset = state.offset
        dialogue.need(replacement != current,
                      f"{state.label}: 나레이션 수정이 실제 변경을 만들지 않았습니다.")
        audit["changed_bytes"] = sum(
            old != new for old, new in zip(current, replacement)
        )
        audit_rows.append(audit)
        patches.append((
            patch_offset,
            replacement,
            f"narrations/presentation-{presentation_index:03d}",
        ))
    return tuple(patches), {
        "records": len(records),
        "presentations": len(states),
        "scenario_01_70_covered": 70,
        "adopted_records": sum(
            row.base_text != row.disc_text for row in records
        ),
        "user_edited_records": len(edits),
        "edited_records": len(effective),
        "changed_presentations": len(touched),
        "patches": audit_rows,
        "semantic_abbreviations": 0,
        "glyph_aliases": 0,
        "space_owners_distinct": True,
    }
