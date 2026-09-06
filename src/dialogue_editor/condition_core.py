#!/usr/bin/env python3
"""Editable victory/defeat-condition records with fixed aggregate ownership."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from functools import lru_cache
import json
from pathlib import Path
import re
import struct
import unicodedata

import dialogue_core as dialogue
import condition_native_codec as native_codec
import presentation_dictionary as presentation_dict
import missing_presentations


CATALOG = dialogue.ROOT / "analysis/all_scenario_presentations_v84.json"
MENU_CATALOG = (
    dialogue.ROOT
    / "analysis/r80-battle-menu-condition-catalog-successor168.json"
)
PRESENTATION_CHARSET = (
    dialogue.ROOT / "analysis/hangul_charset_ui_condition_successor203.json"
)
PAGE = b"\x06\x07"
VICTORY_PREFIX = b"\x04\x1C\x08\x05"
DEFEAT_PREFIX = b"\x04\x1D\x08\x05"
# Legacy prefixes above describe the immutable input. New frames put their
# indentation in the body, so the first row cannot acquire a second indent.
CONDITION_SPACE = bytes.fromhex("F1E8")
CONDITION_SPACE_PX = 4
CONDITION_BULLET_PX = 12
MAX_LINES = 4
CONDITION_INTERIOR_TILES = 22
MAX_WIDTH_PX = CONDITION_INTERIOR_TILES * 8
TOKEN = re.compile(r"\{(name|raw|dict):([0-9A-Fa-f]{2})\}")
ANY_BRACE = re.compile(r"\{[^{}]*\}")
SCENARIO = re.compile(r"^scenario-(\d{2})$")
# Source frame identities absent from the immutable successor190 input.
# Japanese S12 frame 3 is narration; its combined condition is frame 4.
# Evidence: analysis/successor229-narration-population-reassessment-20260903.json.
RESTORED_NARRATION_FRAMES = {12: (3,)}
DICTIONARY_DISPLAY = {
    0x02: "・턴 초과",
    0x0D: "적 전멸",
    0x1C: "＊승리조건",
    0x1D: "＊패배조건",
}
S2_EXCLUSIVE_DICTIONARY_CODES = frozenset((0x01, 0x02, 0x0B, 0x1C, 0x1D))
ADOPTED_BASE_TEXT = {
    # Faithful PC-FX condition wording repairs.  These replace inherited
    # drafts that added objectives, collapsed named targets, or changed
    # escape/arrival semantics.  Wrapped continuation rows use the native
    # 4 px advance and never borrow another glyph or dictionary entry.
    "presentation007/condition/defeat": (
        "・엘윈 사망\n{raw:05}・주민 전멸"
    ),
    "presentation008/condition/defeat": (
        "・엘윈 사망\n{raw:05}・턴 초과"
    ),
    "presentation011/condition/defeat": (
        "・엘윈 사망\n{raw:05}・레온이 랑그릿사에 도착"
    ),
    "presentation014/condition/defeat": (
        "・엘윈 사망\n{raw:05}・턴 초과"
    ),
    "presentation015/condition/defeat": "・엘윈 사망",
    "presentation017/condition/defeat": (
        "・엘윈 사망\n{raw:05}・홀리로드를 가진 적이\n"
        "{raw:05}\u2009화면 아래로 탈출"
    ),
    "presentation025/condition/victory": (
        "・에스트, 오스트,\n{raw:05}\u2009뱀파이어 로드 격파"
    ),
    "presentation027/condition/defeat": (
        "・엘윈 사망\n{raw:05}・턴 초과"
    ),
    "presentation028/condition/defeat": (
        "・엘윈 사망\n{raw:05}・주민 전멸"
    ),
    "presentation030/condition/victory": "・적 전멸",
    "presentation031/condition/defeat": (
        "・엘윈 사망\n{raw:05}・홀리로드를 가진 적이\n"
        "{raw:05}\u2009화면 아래로 탈출"
    ),
    "presentation033/condition/defeat": (
        "・엘윈 사망\n{raw:05}・홀리로드를 가진 적이\n"
        "{raw:05}\u2009화면 아래로 탈출"
    ),
    # PC-FX source: ・１９ターン以内に / レスターを撃破.
    # The inherited Korean frame incorrectly changed the limit to 18 turns.
    "presentation037/condition/victory": "・１９턴 안에 레스터 격파",
    "presentation037/condition/defeat": (
        "・엘윈 사망\n{raw:05}・턴 초과"
    ),
    "presentation040/condition/defeat": (
        "・엘윈 사망\n{raw:05}・랑그릿사를 빼앗김"
    ),
    "presentation042/condition/defeat": (
        "・엘윈 사망\n{raw:05}・적이 화면 위로 탈출"
    ),
    "presentation044/condition/victory": (
        "・리아나 외 전원 격파\n{raw:05}・에그베르트를\n"
        "{raw:05}\u2009리아나 옆에 붙이기"
    ),
    "presentation044/condition/defeat": (
        "・엘윈 사망\n{raw:05}・리아나 사망 또는 탈출"
    ),
    "presentation054/condition/victory": (
        "・적 전멸\n＊패배조건\n{raw:05}・엘윈 사망"
    ),
    "presentation055/condition/victory": (
        "・보젤 격파\n＊패배조건\n{raw:05}・엘윈 사망"
    ),
    "presentation058/condition/defeat": (
        "・엘윈 사망\n{raw:05}・스코트와 로렌이\n"
        "{raw:05}\u2009화면 위로 탈출"
    ),
    "presentation059/condition/defeat": (
        "・엘윈 사망\n{raw:05}・리아나 사망 또는 탈출"
    ),
    "presentation061/condition/defeat": (
        "・엘윈 사망\n{raw:05}・턴 초과"
    ),
    "presentation062/condition/defeat": (
        "・엘윈 사망\n{raw:05}・턴 초과"
    ),
    "presentation066/condition/defeat": (
        "・엘윈 사망\n{raw:05}・턴 초과"
    ),
    "presentation069/condition/victory": (
        "・적 전멸\n{raw:05}・유적 재기동"
    ),
    "presentation069/condition/defeat": "・엘윈 사망",
    "presentation080/condition/defeat": (
        "・엘윈 사망\n{raw:05}・NPC 전멸"
    ),
    "presentation081/condition/defeat": (
        "・엘윈 사망\n{raw:05}・주민 전멸"
    ),
    "presentation085/condition/victory": (
        "・적 전멸\n{raw:05}・유적 재기동"
    ),
    "presentation085/condition/defeat": "・엘윈 사망",
    # Original: ・リアナ以外の全滅 / ・ソニアをリアナに隣接させる
    # The former Korean draft was semantically wrong (enemy commander) and
    # 200 px wide.  These rows retain the source conditions inside the proven
    # 22-tile condition-window interior.
    "presentation059/condition/victory": (
        "・리아나만 남기고 전원 격파\n{raw:05}・소니아를 리아나에 붙이기"
    ),
}


@dataclass(frozen=True)
class ConditionRecord:
    id: str
    presentation_index: int
    label: str
    scenario: int | None
    frame_index: int
    kind: str
    source_text: str
    base_text: str
    storage: str = "presentation"


@dataclass(frozen=True)
class PresentationState:
    presentation_index: int
    label: str
    offset: int
    allocation: int
    frames: tuple[bytes, ...]
    suffix: bytes
    condition_frame_indexes: tuple[int, ...]


@dataclass(frozen=True)
class MenuConditionState:
    scenario: int
    label: str
    offset: int
    allocation: int
    source_record_count: int
    base_block: bytes
    target_block: bytes
    record_indexes: tuple[int, ...]
    section_offset_field: int
    base_section6_relative: int
    target_section6_relative: int
    section7_offset_field: int
    base_section7_relative: int
    target_section7_relative: int
    relocation_direction: str
    extension_bytes: int
    section5_terminal_offset: int | None
    section5_terminal_base: int | None
    presentation_shift_bytes: int


@lru_cache(maxsize=1)
def global_condition_mapping() -> dict[str, bytes]:
    document = json.loads(PRESENTATION_CHARSET.read_text(encoding="utf-8"))
    mapping = {
        str(row["character"]): int(row["code"], 0).to_bytes(2, "big")
        for row in document["mappings"]
    }
    dialogue.need_unique_mapping(mapping, "전역 조건 화면 문자표")
    dialogue.need(mapping[" "] != mapping["\u2009"],
                  "전역 조건 화면 공백 글리프 중복")
    return mapping


@lru_cache(maxsize=2)
def condition_mapping(scenario: int | None = None) -> dict[str, bytes]:
    # Preserve established UI owners, but do not reuse the AV prefilter's
    # F2C2=증 / F2C3=점 as 출 / 김 (the inherited 203 plan did exactly that).
    # Since 234 the repaired Resource-12 router supplies the full private
    # atlas on native presentation entry. Use those existing same-character
    # owners, not another alias or a change to the AV menu glyphs.
    mapping = dict(global_condition_mapping())
    private = dialogue.all_dialogue_private_mapping()
    for character in ('출', '김'):
        mapping[character] = private[character]
    validate_condition_code_owners(mapping)
    dialogue.need_unique_mapping(mapping, "승리·패배조건 문자표")
    dialogue.need(mapping[" "] != mapping["\u2009"],
                  "승리·패배조건 공백 글리프 중복")
    return mapping


def validate_condition_code_owners(mapping: dict[str, bytes]) -> None:
    import av_font_core
    reserved = {code.to_bytes(2,'big'):character
                for character,code,_use in av_font_core.AV_GLYPH_ROWS}
    for character,code in mapping.items():
        dialogue.need(code not in reserved or reserved[code] == character,
                      f"승패조건 '{character}': '{reserved.get(code)}' 전용 글자 번호 중복")


def condition_reverse(scenario: int | None) -> dict[bytes, str]:
    return {
        code: character for character, code in condition_mapping(scenario).items()
    }


@lru_cache(maxsize=2)
def legacy_condition_mapping(scenario: int | None = None) -> dict[str, bytes]:
    """Decode the normalized successor181 condition-screen preimage.

    Successor181 inherits the later global condition-atlas normalization, so
    Scenario 3-12 no longer use their historical dialogue-only F4-F7 owners.
    Keeping that old compatibility overlay here removed valid global owners
    such as F15B=엘 from the reverse table.
    """
    mapping = dict(global_condition_mapping())
    dialogue.need_unique_mapping(mapping, "기준판 승리·패배조건 문자표")
    return mapping


def legacy_condition_reverse(scenario: int | None) -> dict[bytes, str]:
    reverse = {
        code: character for character, code
        in legacy_condition_mapping(scenario).items()
    }
    return reverse


def split_frames(raw: bytes) -> tuple[list[bytes], bytes]:
    frames: list[bytes] = []
    cursor = 0
    while True:
        end = raw.find(PAGE, cursor)
        if end < 0:
            return frames, raw[cursor:]
        frames.append(raw[cursor:end + len(PAGE)])
        cursor = end + len(PAGE)


def frame_kind(index: int, raw: bytes) -> str:
    if index == 0:
        return "title"
    if raw.startswith(VICTORY_PREFIX[:2]):
        return "victory-condition"
    if raw.startswith(DEFEAT_PREFIX[:2]):
        return "defeat-condition"
    return "narration"


@lru_cache(maxsize=1)
def source_frame_kinds() -> dict[int, tuple[str, ...]]:
    catalog = missing_presentations.load_catalog(CATALOG)
    result = {}
    for row in catalog["presentations"]:
        frames = row["frames"]
        dialogue.need([int(f["index"]) for f in frames] == list(range(len(frames))),
                      "원문 연출 프레임 순서 변경")
        result[int(row["presentation_index"])] = tuple(f["kind"] for f in frames)
    return result


def validate_frame_population(presentation_index: int, frames: list[bytes] | tuple[bytes, ...],
                              *, allow_missing_restorations: bool = False) -> tuple[int, ...]:
    """Return declared missing source indexes, never infer exclusions from output."""
    expected = source_frame_kinds()[presentation_index]
    actual = tuple(frame_kind(i, frame) for i, frame in enumerate(frames))
    if actual == expected:
        return ()
    missing = RESTORED_NARRATION_FRAMES.get(presentation_index, ())
    dialogue.need(all(expected[i] == "narration" for i in missing),
                  f"{presentation_index}: 복구 대상 원문 종류 변경")
    legacy = tuple(kind for i, kind in enumerate(expected) if i not in missing)
    dialogue.need(allow_missing_restorations and bool(missing) and actual == legacy,
                  f"{presentation_index}: 원문 연출 프레임 수/종류 불일치: {actual} / {expected}")
    return missing


def resolve_condition_records(presentation_index: int, frames: list[bytes] | tuple[bytes, ...],
                              records: tuple[ConditionRecord, ...] | list[ConditionRecord],
                              *, allow_missing_restorations: bool = True) -> dict[int, ConditionRecord]:
    """Bind logical condition identities to live indexes after narration insertion."""
    validate_frame_population(presentation_index, frames,
                              allow_missing_restorations=allow_missing_restorations)
    by_kind = {r.kind: r for r in records}
    dialogue.need(len(by_kind) == len(records)
                  and all(r.presentation_index == presentation_index and r.storage == "presentation"
                          for r in records), "승패조건 소유권 중복/혼합")
    result = {}
    for index, frame in enumerate(frames):
        kind = frame_kind(index, frame)
        if kind.endswith("condition"):
            dialogue.need(kind in by_kind, f"{presentation_index}: 알 수 없는 조건 종류 {kind}")
            result[index] = replace(by_kind.pop(kind), frame_index=index)
    dialogue.need(not by_kind, f"{presentation_index}: 승패조건 레코드 누락")
    return result


def _decode(raw: bytes, reverse: dict[bytes, str]) -> str:
    output: list[str] = []
    cursor = 0
    while cursor < len(raw):
        pair = raw[cursor:cursor + 2]
        if pair in reverse:
            character = reverse[pair]
            output.append(" " if character == "\u2009" else character)
            cursor += 2
            continue
        value = raw[cursor]
        if value == 0x08:
            output.append("\n")
            cursor += 1
        elif value == 0x04 and cursor + 1 < len(raw):
            code = raw[cursor + 1]
            output.append(DICTIONARY_DISPLAY.get(code, f"{{dict:{code:02X}}}"))
            cursor += 2
        elif value == 0x09 and cursor + 1 < len(raw):
            output.append(f"{{name:{raw[cursor + 1]:02X}}}")
            cursor += 2
        elif value < 0x20:
            output.append(f"{{raw:{value:02X}}}")
            cursor += 1
        elif value < 0x80 or 0xA1 <= value <= 0xDF:
            output.append(bytes((value,)).decode("shift_jis"))
            cursor += 1
        else:
            dialogue.need(cursor + 1 < len(raw), "조건 프레임 문자 절단")
            try:
                output.append(pair.decode("shift_jis"))
            except UnicodeDecodeError as exc:
                raise dialogue.DialogueError(
                    f"조건 프레임 미등록 코드: {pair.hex().upper()}"
                ) from exc
            cursor += 2
    return "".join(output)


def _strip_last_padding(
    frame: bytes, mapping: dict[str, bytes]
) -> tuple[bytes, bytes]:
    dialogue.need(frame.endswith(PAGE), "조건 프레임 PAGE 종단 없음")
    body = frame[:-len(PAGE)]
    end = len(body)
    spaces = (mapping["\u2009"], mapping[" "])
    while end:
        if end >= 2 and body[end - 2:end] in spaces:
            end -= 2
            continue
        if body[end - 1] == 0x05:
            end -= 1
            continue
        break
    return body[:end] + PAGE, body[end:]


def _clean_source(text: str, kind: str) -> str:
    value = dialogue.ui_text(
        str(text).replace("{br}", "\n").replace("{end}", "")
    ).removesuffix("{page}")
    headers = {
        "victory-condition": ("＊勝利条件\n", "＊승리조건\n"),
        "defeat-condition": ("＊敗北条件\n", "＊패배조건\n"),
    }
    for header in headers[kind]:
        if value.startswith(header):
            return value[len(header):]
    return value


@lru_cache(maxsize=1)
def load_condition_data() -> tuple[
    tuple[ConditionRecord, ...], tuple[PresentationState, ...]
]:
    catalog = missing_presentations.load_catalog(CATALOG)
    menu_catalog = json.loads(MENU_CATALOG.read_text(encoding="utf-8"))
    live_menu_ends = {
        int(row["scenario"]): int(row["offset"], 0) + int(row["allocation"])
        for row in menu_catalog["scenarios"]
    }
    cooked = dialogue.BASE_DIR / dialogue.BASE_COOKED_NAME
    dialogue.need(cooked.is_file(), "successor190 기준 이미지가 없습니다.")
    records: list[ConditionRecord] = []
    states: list[PresentationState] = []
    with cooked.open("rb") as stream:
        for source in catalog["presentations"]:
            index = int(source["presentation_index"])
            label = str(source["inferred_label"])
            scenario_match = SCENARIO.match(label)
            scenario = (int(scenario_match.group(1))
                        if scenario_match else None)
            # Successor181's pinned base and all new writes use the same
            # normalized global condition-screen ownership table.
            mapping = legacy_condition_mapping(scenario)
            reverse = legacy_condition_reverse(scenario)
            offset = int(source["cooked_offset"], 0)
            allocation = int(source["length"])
            if scenario in live_menu_ends:
                movement = live_menu_ends[scenario] - offset
                dialogue.need(movement in (0, 4),
                              f"{label}: 기준 메뉴/연출 경계 변경")
                # S16/21/63/65's historical anchor includes the final four
                # menu bytes. The native section-7 start is authoritative.
                offset += movement
                allocation -= movement
            stream.seek(offset)
            aggregate = stream.read(allocation)
            dialogue.need(len(aggregate) == allocation,
                          f"{label}: 조건 묶음 범위 초과")
            if index in missing_presentations.INDICES:
                missing_presentations.verify_source_region(index, aggregate)
            frames, suffix = split_frames(aggregate)
            kinds = [frame_kind(i, frame) for i, frame in enumerate(frames)]
            condition_indexes = tuple(
                i for i, kind in enumerate(kinds) if kind.endswith("condition")
            )
            if condition_indexes:
                dialogue.need(
                    list(condition_indexes)
                    == list(range(condition_indexes[0], len(frames))),
                    f"{label}: 조건 프레임이 묶음 끝에 있지 않습니다.",
                )
            states.append(PresentationState(
                presentation_index=index,
                label=label,
                offset=offset,
                allocation=allocation,
                frames=tuple(frames),
                suffix=suffix,
                condition_frame_indexes=condition_indexes,
            ))
            original_by_kind: dict[str, list[dict]] = {}
            for frame in source["frames"]:
                original_by_kind.setdefault(str(frame["kind"]), []).append(frame)
            kind_ordinals: Counter[str] = Counter()
            for frame_index in condition_indexes:
                kind = kinds[frame_index]
                raw = frames[frame_index]
                dialogue.need(index in missing_presentations.INDICES or raw.startswith(
                    VICTORY_PREFIX if kind == "victory-condition"
                    else DEFEAT_PREFIX
                ), f"{label}: 조건 접두부 변경")
                visible = raw
                if frame_index == len(frames) - 1:
                    visible, _padding = _strip_last_padding(raw, mapping)
                body = visible[4:-len(PAGE)]
                base_text = _decode(body, reverse)
                ordinal = kind_ordinals[kind]
                kind_ordinals[kind] += 1
                original_rows = original_by_kind.get(kind, [])
                source_text = ""
                if ordinal < len(original_rows):
                    row = original_rows[ordinal]
                    source_text = _clean_source(
                        row.get("expanded_text") or row.get("source_text") or "",
                        kind,
                    )
                short_kind = "victory" if kind == "victory-condition" else "defeat"
                record_id = f"presentation{index:03d}/condition/{short_kind}"
                if index in missing_presentations.INDICES:
                    # These original Japanese bodies were never Korean-normalized;
                    # the protected extraction, not the legacy decoder, is authoritative.
                    base_text = missing_presentations.draft()['conditions'][record_id]
                records.append(ConditionRecord(
                    id=record_id,
                    presentation_index=index,
                    label=(missing_presentations.display_label(index)
                           if index in missing_presentations.INDICES else label),
                    scenario=scenario,
                    frame_index=frame_index,
                    kind=kind,
                    source_text=source_text,
                    base_text=ADOPTED_BASE_TEXT.get(record_id, base_text),
                ))
    expected_count = sum(f['kind'].endswith('condition')
                         for row in catalog['presentations'] for f in row['frames'])
    dialogue.need(len(records) == expected_count, "원문/편집기 조건 레코드 수가 다릅니다.")
    dialogue.need(len({row.id for row in records}) == len(records),
                  "조건 레코드 ID 중복")
    dialogue.need(
        {row.scenario for row in records if row.scenario is not None}
        == set(range(1, 71)),
        "시나리오 1~70 조건 레코드가 불완전합니다.",
    )
    return tuple(records), tuple(states)


@lru_cache(maxsize=1)
def load_menu_condition_data() -> tuple[
    tuple[ConditionRecord, ...], tuple[MenuConditionState, ...]
]:
    dialogue.need(MENU_CATALOG.is_file(), "시스템 메뉴 승패조건 자료가 없습니다.")
    document = json.loads(MENU_CATALOG.read_text(encoding="utf-8"))
    dialogue.need(
        document.get("schema")
        == "langrisser-fx-r80-battle-menu-condition-catalog-successor168/v1",
        "시스템 메뉴 승패조건 자료 형식이 다릅니다.",
    )
    cooked = dialogue.BASE_DIR / dialogue.BASE_COOKED_NAME
    dialogue.need(cooked.is_file(), "successor190 기준 이미지가 없습니다.")
    image = cooked.read_bytes()
    records: list[ConditionRecord] = []
    states: list[MenuConditionState] = []
    for source in document["scenarios"]:
        scenario = int(source["scenario"])
        offset = int(source["offset"], 0)
        allocation = int(source["allocation"])
        historical_block = bytes.fromhex(source["base_block_hex"])
        target_block = bytes.fromhex(source["target_block_hex"])
        dialogue.need(
            len(historical_block) == len(target_block) == allocation,
            f"{scenario}화 시스템 메뉴 조건 범위 오류",
        )
        dialogue.need(
            image[offset:offset + allocation] == target_block,
            f"{scenario}화 시스템 메뉴 조건 기준 바이트 변경",
        )
        section_offset_field = int(source["section6_offset_field"], 0)
        historical_section6_relative = int(source["base_section6_relative"], 0)
        target_section6_relative = int(source["target_section6_relative"], 0)
        dialogue.need(
            image[section_offset_field:section_offset_field + 4]
            == struct.pack("<I", target_section6_relative),
            f"{scenario}화 시스템 메뉴 섹션 경계 기준값 변경",
        )
        section7_offset_field = int(source["section7_offset_field"], 0)
        historical_section7_relative = int(source["base_section7_relative"], 0)
        target_section7_relative = int(source["target_section7_relative"], 0)
        dialogue.need(
            image[section7_offset_field:section7_offset_field + 4]
            == struct.pack("<I", target_section7_relative),
            f"{scenario}화 연출 섹션 경계 기준값 변경",
        )
        terminal_text = source.get("section5_terminal_offset")
        section5_terminal_offset = (
            int(terminal_text, 0) if terminal_text is not None else None
        )
        terminal_target_text = source.get("section5_terminal_target_hex")
        section5_terminal_current = (
            int(terminal_target_text, 16)
            if terminal_target_text is not None else None
        )
        if section5_terminal_offset is not None:
            dialogue.need(
                image[section5_terminal_offset] == section5_terminal_current,
                f"{scenario}화 대사 섹션 끝 패딩 기준값 변경",
            )
        indexes: list[int] = []
        for row in source["editable_records"]:
            record_index = int(row["record_index"])
            indexes.append(record_index)
            records.append(ConditionRecord(
                id=str(row["id"]),
                presentation_index=1000 + scenario,
                label=f"{scenario}화 시스템 메뉴",
                scenario=scenario,
                frame_index=record_index,
                kind="menu-condition",
                source_text=dialogue.ui_text(str(row["source_text"])),
                base_text=dialogue.ui_text(str(row["base_text"])),
                storage="menu",
            ))
        dialogue.need(
            len(indexes) == len(set(indexes)),
            f"{scenario}화 시스템 메뉴 조건 인덱스 중복",
        )
        states.append(MenuConditionState(
            scenario=scenario,
            label=str(source["label"]),
            offset=offset,
            allocation=allocation,
            source_record_count=int(source["source_record_count"]),
            base_block=target_block,
            target_block=target_block,
            record_indexes=tuple(indexes),
            section_offset_field=section_offset_field,
            base_section6_relative=target_section6_relative,
            target_section6_relative=target_section6_relative,
            section7_offset_field=section7_offset_field,
            base_section7_relative=target_section7_relative,
            target_section7_relative=target_section7_relative,
            relocation_direction="already-applied-in-successor181",
            extension_bytes=0,
            section5_terminal_offset=section5_terminal_offset,
            section5_terminal_base=section5_terminal_current,
            presentation_shift_bytes=0,
        ))
    dialogue.need(
        {row.scenario for row in records} == set(range(3, 71)),
        "3~70화 시스템 메뉴 조건 레코드가 불완전합니다.",
    )
    dialogue.need(len(records) == 194, "시스템 메뉴 조건 레코드 수 변경")
    return tuple(records), tuple(states)


def load_condition_records() -> tuple[ConditionRecord, ...]:
    presentation, _states = load_condition_data()
    menu, _menu_states = load_menu_condition_data()
    result = presentation + menu
    dialogue.need(
        len({row.id for row in result}) == len(result),
        "승패조건 ID 중복",
    )
    return result


def _script_residuals(text: str) -> list[str]:
    residuals: list[str] = []
    for character in text:
        code = ord(character)
        if (0x3040 <= code <= 0x30FF and character != "・") or (
            0x3400 <= code <= 0x9FFF
        ):
            residuals.append(character)
    return sorted(set(residuals))


def condition_layout_text(text: str, storage: str = "presentation") -> str:
    """Align bullets and hanging continuations without changing wording.

    User-approved 2026-09-03: both victory and defeat use the same indentation
    and narrow word spaces. In the presentation renderer, native 05 advances
    a full 12px cell; F1E8 is its existing resident 4px spacing-hook glyph.
    The CN mapper uses physical tile extent (cn_text_extent), so it can use
    the same resident narrow-space glyph without mapping stale extra tiles.
    """
    def expand_display(match: re.Match) -> str:
        kind, value = match.groups()
        if kind != "dict":
            return match.group(0)
        return DICTIONARY_DISPLAY.get(int(value, 16), match.group(0))

    expanded = TOKEN.sub(expand_display, text)
    rows = []
    for line in expanded.split("\n"):
        body = re.sub(r"^(?:[ \u2009\u3000]|\{raw:05\})+", "", line,
                      flags=re.IGNORECASE)
        if not body or body.startswith(("＊승리조건", "＊패배조건")):
            rows.append(body)
        elif body.startswith(("・", "･")):
            rows.append(" " + body)
        else:
            # Presentation: 4px indent + 12px bullet = 16px text column.
            rows.append(" " * 4 + body)
    return "\n".join(rows)


def condition_display_line_widths(text: str, storage: str = "presentation") -> list[int]:
    return condition_line_widths(condition_layout_text(text, storage))


def condition_frame_prefix(record: ConditionRecord) -> bytes:
    legacy = VICTORY_PREFIX if record.kind == "victory-condition" else DEFEAT_PREFIX
    return legacy[:-1]


def condition_line_widths(text: str) -> list[int]:
    """Measure the condition renderer, including native raw advances."""
    from native_name_widths import name_width_px
    widths: list[int] = []
    for line in text.replace("\f", "").split("\n"):
        width = 0
        cursor = 0
        while cursor < len(line):
            match = TOKEN.match(line, cursor)
            if match:
                kind, raw_value = match.groups()
                value = int(raw_value, 16)
                if kind == "name":
                    try:
                        width += name_width_px(value)
                    except ValueError as exc:
                        raise dialogue.DialogueError(str(exc)) from exc
                elif kind == "raw":
                    # Both consumers convert authored 05 to resident F1E8.
                    # The supplied unrenamed Elwin is 28px; reserve 36px,
                    # consistently with narration, rather than zero pixels.
                    width += {0x02: 36, 0x05: 4, 0x20: 8}.get(value, 0)
                else:
                    phrase = DICTIONARY_DISPLAY.get(value)
                    dialogue.need(
                        phrase is not None,
                        f"조건 폭을 계산할 수 없는 사전 토큰 {{dict:{value:02X}}}",
                    )
                    phrase_widths = condition_line_widths(phrase)
                    dialogue.need(len(phrase_widths) == 1,
                                  "조건 사전 토큰에 줄바꿈이 있습니다.")
                    width += phrase_widths[0]
                cursor = match.end()
                continue
            character = line[cursor]
            if character in ("\u2009", "\u3000"):
                width += 4
            elif character == " ":
                # F1E8's existing spacing hook removes 8px from a 12px cell.
                width += 4
            elif character in ("・", "･"):
                # F486 reads all printable glyphs as two bytes (except the
                # dedicated 20/21 space controls). A5 consumes the next byte.
                width += 12
            else:
                width += 12
            cursor += 1
        widths.append(width)
    return widths


def encode_condition_glyph(character: str, mapping: dict[str, bytes]) -> bytes:
    """Use the game's two-byte glyph grammar, not CP932 byte lengths.

    Native F4F2..F516 always reads a second glyph byte.  A CP932 halfwidth
    bullet or ASCII letter would therefore consume the following name or
    control. Spaces are handled separately by the consumer-specific encoder.
    """
    if character == "･":
        character = "・"
    if character in mapping:
        encoded = mapping[character]
    else:
        if "!" <= character <= "~":
            character = chr(ord(character) + 0xFEE0)
        encoded = character.encode("shift_jis")
    dialogue.need(len(encoded) == 2,
                  f"조건 글자는 게임의 2바이트 형식이어야 합니다: {character!r}")
    return encoded


def encode_menu_condition_text(record: ConditionRecord, text: str) -> bytes:
    """Encode one real System-menu row without shared phrase aliases."""
    mapping = condition_mapping(record.scenario)
    output = bytearray()
    missing: list[str] = []
    cursor = 0
    while cursor < len(text):
        match = TOKEN.match(text, cursor)
        if match:
            kind, raw_value = match.groups()
            value = int(raw_value, 16)
            dialogue.need(
                kind != "dict",
                f"{record.id}: 시스템 메뉴 본문 공용 문구 재사용 금지",
            )
            if kind == "name":
                output.extend((0x09, value))
            elif value == 0x05:
                output.extend(CONDITION_SPACE)
            else:
                output.append(value)
            cursor = match.end()
            continue
        character = text[cursor]
        if character in (" ", "\u2009", "\u3000"):
            output.extend(CONDITION_SPACE)
        else:
            try:
                output.extend(encode_condition_glyph(character, mapping))
            except UnicodeEncodeError:
                missing.append(character)
        cursor += 1
    dialogue.need(
        not missing,
        f"{record.id}: 지원하지 않는 글자 {', '.join(sorted(set(missing)))}",
    )
    result = bytes(output)
    dialogue.need(
        b"\0" not in result and PAGE not in result and b"\x04" not in result,
        f"{record.id}: 시스템 메뉴 조건 제어 구조 침범",
    )
    return result


def encode_condition_text(record: ConditionRecord, text: str) -> bytes:
    if record.storage == "menu":
        return encode_menu_condition_text(record, text)
    mapping = condition_mapping(record.scenario)
    if record.presentation_index in missing_presentations.INDICES:
        # Same native text consumer and installed private bank as the preceding
        # narration; only this newly restored proper name needs the extra glyph.
        import narration_core
        mapping = {**mapping, '뚱': narration_core.narration_mapping()['뚱']}
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
            kind, raw_value = match.groups()
            value = int(raw_value, 16)
            if kind == "name":
                output.extend((0x09, value))
            elif kind == "dict":
                phrase = DICTIONARY_DISPLAY.get(value)
                dialogue.need(phrase is not None,
                              f"{record.id}: 의미를 확인할 수 없는 조건 문구 {value:02X}")
                output.extend(encode_condition_text(record, phrase))
            else:
                output.extend(CONDITION_SPACE if value == 0x05 else bytes((value,)))
            cursor = match.end()
            continue
        character = text[cursor]
        if character in (" ", "\u2009", "\u3000"):
            output.extend(CONDITION_SPACE)
        else:
            try:
                output.extend(encode_condition_glyph(character, mapping))
            except UnicodeEncodeError:
                missing.append(character)
        cursor += 1
    dialogue.need(not missing,
                  f"{record.id}: 지원하지 않는 글자 {', '.join(sorted(set(missing)))}")
    result = bytes(output)
    dialogue.need(b"\0" not in result and PAGE not in result,
                  f"{record.id}: 조건 제어 구조 침범")
    # This also rejects raw-token attempts to reinstate either obsolete owner.
    # Dictionary references are checked after expansion in the final verifier.
    dialogue.need(not any(unit in (b'\xf2\xc2',b'\xf2\xc3')
                          for unit in native_codec.units(result)),
                  f"{record.id}: 증/점 전용 번호를 조건의 출/김으로 사용할 수 없습니다.")
    if record.presentation_index == 2:
        hits = sorted(
            code for code in S2_EXCLUSIVE_DICTIONARY_CODES
            if bytes((0x04, code)) in result
        )
        dialogue.need(not hits,
                      f"{record.id}: 2화 조건 본문 전용코드 재사용 금지 {hits}")
    return result


def compile_condition_body(record: ConditionRecord, text: str, image: bytes) -> bytes:
    """Compress only byte-exact phrases in this particular native resource."""
    literal = validate_condition_text(record, text)
    if record.storage == "menu":
        return literal
    _records, states = load_condition_data()
    state = next(row for row in states if row.presentation_index == record.presentation_index)
    resource = presentation_dict.locate_resource(image, state.offset, allow_authored_title=True)
    encoded = native_codec.compress(literal, resource.dictionary_rows)
    dialogue.need(native_codec.expand(encoded, resource.dictionary_rows) == literal,
                  f"{record.id}: 최종 조건 문구 왕복 불일치")
    return encoded


def fit_condition_frames(image: bytes, state: PresentationState,
                         frames: list[bytes], texts: dict[str, str],
                         allocation: int, suffix_bytes: int) -> tuple[list[bytes], tuple | None]:
    """Use existing per-record native dictionary storage only if needed.

    No section moves or shortened text. Untouched narration, all low/native
    dictionary rows and every referenced row stay preserved by the shared
    ownership planner. The allocated body contains no nested dictionary.
    """
    if sum(map(len, frames)) + suffix_bytes <= allocation:
        return frames, None
    live_records = resolve_condition_records(
        state.presentation_index, frames,
        [r for r in load_condition_data()[0] if r.presentation_index == state.presentation_index],
    )
    records = [r for r in live_records.values() if r.id in texts]
    resource = presentation_dict.locate_resource(image, state.offset, allow_authored_title=True)
    rows = sorted(records, key=lambda r: len(frames[r.frame_index]), reverse=True)
    errors = []
    for count in range(1, len(rows) + 1):
        selected = rows[:count]
        payloads = tuple((r.id, validate_condition_text(r, texts[r.id])) for r in selected)
        try:
            plan = presentation_dict.build_dictionary_plan(
                image, resource, payloads,
                released_presentation_frame_indexes=frozenset(r.frame_index for r in selected),
                preserve_all_source_rows=True,
            )
        except dialogue.DialogueError as exc:
            errors.append(str(exc))
            continue
        candidate = list(frames)
        assignments = dict(plan.assignments)
        for record in selected:
            prefix = condition_frame_prefix(record)
            candidate[record.frame_index] = prefix + bytes((4, assignments[record.id])) + PAGE
        if sum(map(len, candidate)) + suffix_bytes <= allocation:
            return candidate, (resource.dictionary_offset, plan.replacement,
                               f"conditions/dictionary-{state.presentation_index:03d}")
    raise dialogue.DialogueError(f"{state.label}: 원문을 보존하는 조건 저장 공간 부족: {' | '.join(errors)}")


def verify_final_condition_records(image: bytes, edits: dict[str, str]) -> dict:
    """Expand final native tokens and compare every authored condition byte."""
    records, states = load_condition_data()
    resources = {}
    frames = {}
    live_records = []
    for state in states:
        resource = presentation_dict.locate_resource(image, state.offset, allow_authored_title=True)
        resources[state.presentation_index] = resource
        frames[state.presentation_index] = split_frames(image[
            resource.presentation_offset:
            resource.presentation_offset + resource.presentation_allocation
        ])[0]
        live_records.extend(resolve_condition_records(
            state.presentation_index, frames[state.presentation_index],
            [r for r in records if r.presentation_index == state.presentation_index],
            allow_missing_restorations=False,
        ).values())
    for record in live_records:
        actual = frames[record.presentation_index][record.frame_index]
        resource = resources[record.presentation_index]
        title = "＊승리조건" if record.kind == "victory-condition" else "＊패배조건"
        expected = (encode_condition_text(record, title) + b"\x08"
                    + validate_condition_text(record, edits.get(record.id, record.base_text)) + PAGE)
        dialogue.need(native_codec.expand(actual, resource.dictionary_rows) == expected,
                      f"{record.id}: 최종 네이티브 승패조건 표시 데이터 불일치")
    menu_records, _menu_states = load_menu_condition_data()
    menu_states = plan_menu_condition_states(edits)
    by_scenario = {state.scenario: state for state in menu_states}
    for record in menu_records:
        state = by_scenario[record.scenario]
        dialogue.need(struct.unpack_from("<I", image, state.section7_offset_field)[0]
                      == state.target_section7_relative,
                      f"{record.id}: 최종 메뉴/연출 경계 불일치")
        rows = image[state.offset:state.offset + state.allocation].split(b"\0")
        dialogue.need(rows[:2] == [b"\x04\x1C", b"\x04\x1D"],
                      f"{record.id}: 최종 시스템 메뉴 조건 머리말 불일치")
        actual = rows[record.frame_index]
        expected = validate_condition_text(record, edits.get(record.id, record.base_text))
        native_codec.units(actual)
        dialogue.need(actual == expected, f"{record.id}: 최종 시스템 메뉴 조건 문구 불일치")
    return {"presentation_records": len(records), "menu_records": len(menu_records),
            "native_expansion_byte_exact": True, "unsupported_single_byte_glyphs": 0,
            "runtime_verified": False}


def validate_condition_text(record: ConditionRecord, text: str) -> bytes:
    dialogue.need("{page}" not in text and "\f" not in text,
                  f"{record.id}: 조건 한 프레임에 페이지 토큰을 넣을 수 없습니다.")
    lines = text.split("\n")
    maximum_lines = 1 if record.storage == "menu" else MAX_LINES
    dialogue.need(1 <= len(lines) <= maximum_lines,
                  f"{record.id}: 조건 화면은 최대 {maximum_lines}줄입니다.")
    if record.presentation_index == 2:
        exclusive_hits = sorted(
            int(match.group(2), 16)
            for match in TOKEN.finditer(text)
            if match.group(1) == "dict"
            and int(match.group(2), 16) in S2_EXCLUSIVE_DICTIONARY_CODES
        )
        dialogue.need(
            not exclusive_hits,
            f"{record.id}: 2화 조건 본문 전용코드 재사용 금지 "
            f"{exclusive_hits}",
        )
    widths = condition_display_line_widths(text, record.storage)
    dialogue.need(all(width <= MAX_WIDTH_PX for width in widths),
                  f"{record.id}: 조건 줄 폭 {widths}/{MAX_WIDTH_PX}px")
    unknown = [token for token in ANY_BRACE.findall(text)
               if not TOKEN.fullmatch(token)]
    dialogue.need(not unknown,
                  f"{record.id}: 알 수 없는 토큰 {sorted(set(unknown))}")
    residuals = _script_residuals(text)
    dialogue.need(not residuals,
                  f"{record.id}: 일본어·한자 잔존 {', '.join(residuals)}")
    if record.storage == "menu":
        dialogue.need(
            not any(
                match.group(1) == "dict" for match in TOKEN.finditer(text)
            ),
            f"{record.id}: 시스템 메뉴 본문 공용 문구 재사용 금지",
        )
    for token_kind in ("name",):
        base = Counter(
            match.group(0).lower() for match in TOKEN.finditer(record.base_text)
            if match.group(1) == token_kind
        )
        source = Counter(
            match.group(0).lower() for match in TOKEN.finditer(record.source_text)
            if match.group(1) == token_kind
        )
        edited = Counter(
            match.group(0).lower() for match in TOKEN.finditer(text)
            if match.group(1) == token_kind
        )
        dialogue.need(edited in (base, source),
                      f"{record.id}: 동적 이름 토큰을 보존해야 합니다.")
    base_raw02 = record.base_text.lower().count("{raw:02}")
    source_raw02 = record.source_text.lower().count("{raw:02}")
    edited_raw02 = text.lower().count("{raw:02}")
    dialogue.need(edited_raw02 in (base_raw02, source_raw02),
                  f"{record.id}: 주인공 토큰 {{raw:02}}를 보존해야 합니다.")
    if record.storage == "menu":
        base_raw = Counter(
            match.group(0).lower() for match in TOKEN.finditer(record.base_text)
            if match.group(1) == "raw"
        )
        source_raw = Counter(
            match.group(0).lower() for match in TOKEN.finditer(record.source_text)
            if match.group(1) == "raw"
        )
        edited_raw = Counter(
            match.group(0).lower() for match in TOKEN.finditer(text)
            if match.group(1) == "raw"
        )
        dialogue.need(
            edited_raw in (base_raw, source_raw),
            f"{record.id}: 시스템 메뉴 제어 토큰을 보존해야 합니다.",
        )
    if "＊패배조건" in record.base_text:
        dialogue.need("＊패배조건" in text,
                      f"{record.id}: 통합 패배조건 머리말을 보존해야 합니다.")
    return encode_condition_text(record, condition_layout_text(text, record.storage))


def validate_condition_project(edits: dict[str, str]) -> None:
    records = load_condition_records()
    known = {row.id: row for row in records}
    dialogue.need(not (set(edits) - set(known)), "알 수 없는 승패조건 ID")
    for record_id, text in edits.items():
        validate_condition_text(known[record_id], text)
    build_condition_patches(edits)


def plan_menu_condition_states(edits: dict[str, str]) -> tuple[MenuConditionState, ...]:
    """Grow CN only into the jointly rebuilt presentation's owned extent.

    The following presentation is repacked byte-exactly by the condition
    layer. Section 8 and all later addresses remain fixed; any insufficient
    text budget fails rather than shortening wording or dropping records.
    """
    records, states = load_menu_condition_data()
    planned = []
    for state in states:
        rows = state.target_block.split(b"\0")
        for record in records:
            if record.scenario == state.scenario:
                rows[record.frame_index] = validate_condition_text(
                    record, edits.get(record.id, record.base_text))
        packed = b"\0".join(rows).rstrip(b"\0") + b"\0"
        growth = (max(0, len(packed) - state.allocation) + 3) & ~3
        allocation = state.allocation + growth
        planned.append(replace(
            state, allocation=allocation,
            base_block=state.base_block.ljust(allocation, b"\0"),
            target_block=packed.ljust(allocation, b"\0"),
            target_section7_relative=state.target_section7_relative+growth,
            extension_bytes=growth, presentation_shift_bytes=growth,
            relocation_direction="forward-with-byte-exact-presentation-repack" if growth
            else state.relocation_direction,
        ))
    return tuple(planned)


def build_condition_patches(edits: dict[str, str]) -> tuple[
    tuple[tuple[int, bytes, str], ...], dict
]:
    presentation_records, states = load_condition_data()
    source_image = (dialogue.BASE_DIR / dialogue.BASE_COOKED_NAME).read_bytes()
    menu_records, _menu_states = load_menu_condition_data()
    menu_states = plan_menu_condition_states(edits)
    records = presentation_records + menu_records
    by_id = {row.id: row for row in records}
    dialogue.need(not (set(edits) - set(by_id)), "알 수 없는 승패조건 ID")
    chosen = {
        record.id: edits.get(record.id, record.base_text)
        for record in records
    }
    # A semantic no-op can still be a required repair: Scenario 3-12 base
    # records decode to the intended Korean text but carry Resource-12-only
    # F4-F7 byte owners.  Compare each visible frame with the canonical global
    # encoding so an ordinary editor build normalizes every affected record.
    state_lookup = {row.presentation_index: row for row in states}
    presentation_changed: dict[str, str] = {}
    for record in presentation_records:
        state = state_lookup[record.presentation_index]
        raw = state.frames[record.frame_index]
        if record.frame_index == len(state.frames) - 1:
            raw, _padding = _strip_last_padding(
                raw, legacy_condition_mapping(record.scenario)
            )
        prefix = condition_frame_prefix(record)
        canonical = (
            prefix
            + compile_condition_body(record, chosen[record.id], source_image)
            + PAGE
        )
        normalize_legacy_owner = raw != canonical
        canonical_adopted_repair = (
            record.id in ADOPTED_BASE_TEXT and raw != canonical
        )
        if (
            chosen[record.id] != record.base_text
            or normalize_legacy_owner
            or canonical_adopted_repair
        ):
            presentation_changed[record.id] = chosen[record.id]
    menu_changed = {
        record.id: chosen[record.id]
        for record in menu_records
        if chosen[record.id] != record.base_text
    }
    changed = presentation_changed | menu_changed
    for record_id, text in changed.items():
        validate_condition_text(by_id[record_id], text)
    records_by_presentation: dict[int, dict[int, ConditionRecord]] = {}
    for row in presentation_records:
        records_by_presentation.setdefault(row.presentation_index, {})[
            row.frame_index
        ] = row
    state_by_index = {row.presentation_index: row for row in states}
    forward_shift_by_scenario = {
        state.scenario: state.presentation_shift_bytes
        for state in menu_states if state.presentation_shift_bytes
    }
    forward_presentation_indexes = {
        record.presentation_index
        for record in presentation_records
        if record.scenario in forward_shift_by_scenario
    }
    touched = sorted({
        by_id[record_id].presentation_index
        for record_id in presentation_changed
    } | forward_presentation_indexes)
    patches: list[tuple[int, bytes, str]] = []
    audit_rows: list[dict] = []
    for presentation_index in touched:
        state = state_by_index[presentation_index]
        frame_records = records_by_presentation[presentation_index]
        presentation_record = next(iter(frame_records.values()))
        shift = forward_shift_by_scenario.get(
            presentation_record.scenario, 0
        )
        target_offset = state.offset + shift
        target_allocation = state.allocation - shift
        rebuilt = list(state.frames)
        final_index = len(rebuilt) - 1
        dialogue.need(final_index in frame_records,
                      f"{state.label}: 마지막 프레임이 조건 소유가 아닙니다.")
        old_final_without_padding, old_padding = _strip_last_padding(
            state.frames[final_index],
            legacy_condition_mapping(presentation_record.scenario),
        )
        for frame_index, record in frame_records.items():
            raw = state.frames[frame_index]
            if frame_index == final_index:
                raw = old_final_without_padding
            if record.id in presentation_changed:
                prefix = condition_frame_prefix(record)
                dialogue.need(record.presentation_index in missing_presentations.INDICES or raw.startswith(prefix),
                              f"{record.id}: 조건 접두부 변경")
                raw = prefix + compile_condition_body(
                    record, presentation_changed[record.id], source_image
                ) + PAGE
            rebuilt[frame_index] = raw
        rebuilt, dictionary_patch = fit_condition_frames(
            source_image, state, rebuilt, presentation_changed,
            target_allocation, len(state.suffix),
        )
        if dictionary_patch is not None:
            patches.append(dictionary_patch)
        unpadded_bytes = sum(map(len, rebuilt)) + len(state.suffix)
        padding = target_allocation - unpadded_bytes
        dialogue.need(padding >= 0,
                      f"{state.label}: 조건 묶음 {-padding}바이트 초과")
        # Never render fixed-allocation filler.  Earlier builds inserted blank
        # glyphs before the final PAGE marker; the cursor still advanced over
        # those blanks and could overwrite the right frame/UI.  Preserve the
        # one-byte presentation terminator, then place inert zero padding after
        # it where the text renderer cannot consume it.
        replacement = b"".join(rebuilt) + state.suffix + bytes(padding)
        dialogue.need(len(replacement) == target_allocation,
                      f"{state.label}: 조건 묶음 크기 변경")
        original = b"".join(state.frames) + state.suffix
        dialogue.need(len(original) == state.allocation,
                      f"{state.label}: 기준 조건 묶음 크기 오류")
        preimage = original[shift:]
        dialogue.need(len(preimage) == target_allocation,
                      f"{state.label}: 이동 후 기준 범위 오류")
        changed_offsets = [
            target_offset + i for i, (old, new)
            in enumerate(zip(preimage, replacement)) if old != new
        ]
        dialogue.need(bool(changed_offsets),
                      f"{state.label}: 조건 수정이 실제 변경을 만들지 않았습니다.")
        patches.append((
            target_offset,
            replacement,
            f"conditions/presentation-{presentation_index:03d}",
        ))
        audit_rows.append({
            "presentation_index": presentation_index,
            "label": state.label,
            "offset": f"0x{target_offset:08X}",
            "owned_bytes": target_allocation,
            "changed_bytes": len(changed_offsets),
            "changed_records": sorted(
                record_id for record_id in presentation_changed
                if by_id[record_id].presentation_index == presentation_index
            ),
            "padding_bytes": padding,
            "padding_location": "after-page-and-presentation-terminator",
            "rendered_padding_bytes": 0,
            "native_dictionary_body_fallback": dictionary_patch is not None,
            "relocated_forward_bytes": shift,
            "section8_start_preserved": True,
            "changes_outside_owned_range": 0,
        })

    menu_by_scenario: dict[int, list[ConditionRecord]] = {}
    for row in menu_records:
        dialogue.need(row.scenario is not None, f"{row.id}: 메뉴 화 번호 없음")
        menu_by_scenario.setdefault(row.scenario, []).append(row)
    menu_audit_rows: list[dict] = []
    repaired_menu_records = 0
    for state in menu_states:
        rows = [b"\0" for _ in range(state.source_record_count)]
        dialogue.need(state.source_record_count >= 2,
                      f"{state.label}: 시스템 메뉴 레코드 수 오류")
        rows[0] = b"\x04\x1C\0"
        rows[1] = b"\x04\x1D\0"
        scenario_records = sorted(
            menu_by_scenario[state.scenario], key=lambda row: row.frame_index
        )
        for record in scenario_records:
            dialogue.need(
                2 <= record.frame_index < state.source_record_count,
                f"{record.id}: 시스템 메뉴 레코드 인덱스 범위 초과",
            )
            text = chosen[record.id]
            rows[record.frame_index] = validate_condition_text(
                record, text
            ) + b"\0"
        packed = b"".join(rows).rstrip(b"\0") + b"\0"
        dialogue.need(
            len(packed) <= state.allocation,
            f"{state.scenario}화 시스템 메뉴 조건 "
            f"{len(packed) - state.allocation}바이트 초과",
        )
        replacement = packed + bytes(state.allocation - len(packed))
        # The immutable catalogue remains the checked preimage, not a codec
        # oracle: its ASCII NPC/19/slash bytes also violate the native grammar.
        if replacement == state.base_block:
            continue
        if state.target_section6_relative != state.base_section6_relative:
            patches.append((
                state.section_offset_field,
                struct.pack("<I", state.target_section6_relative),
                f"conditions/menu-section6-pointer-scenario-{state.scenario:02d}",
            ))
        if state.target_section7_relative != state.base_section7_relative:
            patches.append((
                state.section7_offset_field,
                struct.pack("<I", state.target_section7_relative),
                f"conditions/menu-section7-pointer-scenario-{state.scenario:02d}",
            ))
        if (
            state.section5_terminal_offset is not None
            and state.section5_terminal_base != 0
        ):
            patches.append((
                state.section5_terminal_offset,
                b"\0",
                f"conditions/menu-section5-terminal-scenario-{state.scenario:02d}",
            ))
        changed_offsets = [
            state.offset + index
            for index, (old, new) in enumerate(
                zip(state.base_block, replacement)
            )
            if old != new
        ]
        dialogue.need(changed_offsets, f"{state.label}: 빈 시스템 메뉴 수정")
        patches.append((
            state.offset,
            replacement,
            f"conditions/menu-scenario-{state.scenario:02d}",
        ))
        repaired_menu_records += len(scenario_records)
        menu_audit_rows.append({
            "scenario": state.scenario,
            "label": state.label,
            "offset": f"0x{state.offset:08X}",
            "owned_bytes": state.allocation,
            "changed_bytes": len(changed_offsets),
            "records": len(scenario_records),
            "edited_records": sorted(
                row.id for row in scenario_records if row.id in menu_changed
            ),
            "body_dictionary_tokens": 0,
            "glyph_allocations": 0,
            "glyph_aliases": 0,
            "changes_outside_owned_range": 0,
            "relocation_direction": state.relocation_direction,
            "extension_bytes": state.extension_bytes,
            "presentation_shift_bytes": state.presentation_shift_bytes,
            "section8_and_later_addresses_preserved": True,
        })
    return tuple(patches), {
        "records": len(records),
        "scenario_01_70_covered": 70,
        "victory_records": sum(row.kind == "victory-condition" for row in records),
        "defeat_records": sum(row.kind == "defeat-condition" for row in records),
        "presentation_records": len(presentation_records),
        "menu_records": len(menu_records),
        "changed_records": len(changed),
        "changed_presentation_records": len(presentation_changed),
        "edited_menu_records": len(menu_changed),
        "repaired_menu_records": repaired_menu_records,
        "changed_presentations": len(touched),
        "changed_menu_tables": len(menu_audit_rows),
        "presentations": audit_rows,
        "menu_tables": menu_audit_rows,
        "glyph_contexts": {
            "global": {
                "characters": len(condition_mapping()),
                "codes": len(set(condition_mapping().values())),
                "aliases": 0,
            },
            "scenario03_12": {
                "characters": len(condition_mapping(3)),
                "codes": len(set(condition_mapping(3).values())),
                "aliases": 0,
            },
        },
        "glyph_aliases": 0,
        "space_owners_distinct": True,
        "scenario02_exclusive_codes_in_edited_body": 0,
        "menu_body_dictionary_tokens": 0,
    }
