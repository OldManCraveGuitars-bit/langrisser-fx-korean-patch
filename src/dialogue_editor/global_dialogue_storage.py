#!/usr/bin/env python3
"""Storage expansion and per-scenario dictionary writes for successor194."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_r80_global_text_atlas_items_successor45 as atlas  # noqa: E402

import dialogue_core as dialogue  # noqa: E402


PLAN = ROOT / "dialogue_editor/scenario_dialogue_phrase_extensions_successor207.json"
SCENARIO01_PLAN = (
    ROOT / "dialogue_editor/scenario01_dialogue_phrase_extension_successor200.json"
)
EARLY_PLAN = (
    ROOT / "dialogue_editor/early_scenario_dialogue_phrase_extensions_successor207.json"
)
CURRENT_FULL_BYTES = atlas.FULL_NEW  # 0x16800
EXPANDED_FULL_BYTES = 0x18800
GROWTH_BYTES = EXPANDED_FULL_BYTES - CURRENT_FULL_BYTES
SHORT_BYTES = atlas.SHORT
DICTIONARY_BYTES = 0x89D


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def expand_resource12(source: bytes) -> tuple[bytearray, dict, list[tuple[int, int]]]:
    """Append a larger Resource-12 collection and retarget its offset table."""
    offsets = struct.unpack_from("<17I", source, atlas.RESOURCE12)
    lengths = [right - left for left, right in zip(offsets, offsets[1:])]
    dialogue.need(
        lengths.count(CURRENT_FULL_BYTES) == 15
        and lengths.count(SHORT_BYTES) == 1,
        "Resource-12 현행 하위 리소스 구성이 다릅니다.",
    )
    dialogue.need(len(source) % dialogue.COOKED_SECTOR == 0,
                  "기준 cooked 크기가 섹터 경계가 아닙니다.")
    image = bytearray(source)
    cursor = len(source) - atlas.RESOURCE12
    new_offsets: list[int] = []
    appended_start = len(image)
    for index, (left, right) in enumerate(zip(offsets, offsets[1:])):
        length = right - left
        new_offsets.append(cursor)
        payload = source[atlas.RESOURCE12 + left:atlas.RESOURCE12 + right]
        dialogue.need(len(payload) == length,
                      f"Resource-12 하위 리소스 {index} 읽기 실패")
        image.extend(payload)
        cursor += length
        if length == CURRENT_FULL_BYTES:
            image.extend(bytes(GROWTH_BYTES))
            cursor += GROWTH_BYTES
        else:
            dialogue.need(length == SHORT_BYTES,
                          f"Resource-12 알 수 없는 크기 0x{length:X}")
    new_offsets.append(cursor)
    dialogue.need(
        all(right - left in (EXPANDED_FULL_BYTES, SHORT_BYTES)
            for left, right in zip(new_offsets, new_offsets[1:])),
        "Resource-12 확장 후 하위 리소스 구성이 다릅니다.",
    )
    header = struct.pack("<17I", *new_offsets)
    image[atlas.RESOURCE12:atlas.RESOURCE12 + len(header)] = header
    expected_size = len(source) + sum(lengths) + 15 * GROWTH_BYTES
    dialogue.need(len(image) == expected_size, "Resource-12 확장 이미지 크기 오류")
    dialogue.need(len(image) % dialogue.COOKED_SECTOR == 0,
                  "Resource-12 확장 크기가 섹터 경계를 벗어났습니다.")
    return image, {
        "full_replicas": 15,
        "short_replicas": 1,
        "old_full_bytes": CURRENT_FULL_BYTES,
        "new_full_bytes": EXPANDED_FULL_BYTES,
        "growth_per_full_replica": GROWTH_BYTES,
        "old_offsets": [f"0x{value:X}" for value in offsets],
        "new_offsets": [f"0x{value:X}" for value in new_offsets],
        "source_bytes": len(source),
        "output_bytes": len(image),
        "appended_bytes": len(image) - len(source),
        "appended_start": f"0x{appended_start:X}",
    }, [
        (atlas.RESOURCE12, len(header)),
        (appended_start, len(image) - appended_start),
    ]


def load_plan() -> dict:
    document = json.loads(PLAN.read_text(encoding="utf-8"))
    dialogue.need(
        document.get("schema")
        == "langrisser-fx-scenario-dialogue-phrase-extensions/v1"
        and document.get("status") == "prepared",
        "13~70화 전용 사전 계획 형식이 다릅니다.",
    )
    return document


def plan_dictionary_writes(source: bytes) -> tuple[list[tuple[int, bytes, str]], dict]:
    document = load_plan()
    writes: list[tuple[int, bytes, str]] = []
    audits = []
    owners: set[tuple[int, int]] = set()
    for row in document["scenarios"]:
        scenario = int(row["scenario"])
        start = int(row["dictionary_start"], 0)
        before = bytes(source[start:start + DICTIONARY_BYTES])
        dialogue.need(
            len(before) == DICTIONARY_BYTES
            and sha(before) == row["base_dictionary_sha256"],
            f"{scenario}화 전용 사전 기준 바이트가 다릅니다.",
        )
        after = bytes.fromhex(str(row["dictionary_payload_hex"]))
        dialogue.need(
            len(after) == DICTIONARY_BYTES
            and sha(after) == row["dictionary_payload_sha256"],
            f"{scenario}화 전용 사전 payload가 계획과 다릅니다.",
        )
        cursor = 0
        for _index in range(242):
            cursor = after.find(b"\0", cursor) + 1
            dialogue.need(cursor > 0,
                          f"{scenario}화 전용 사전 레코드 종단 오류")
        dialogue.need(after[cursor:] == bytes(len(after) - cursor),
                      f"{scenario}화 전용 사전 꼬리 오염")
        parsed: list[bytes] = []
        parse_cursor = 0
        for _index in range(242):
            end = after.find(b"\0", parse_cursor)
            dialogue.need(end >= 0, f"{scenario}화 전용 사전 파싱 오류")
            parsed.append(after[parse_cursor:end])
            parse_cursor = end + 1
        for preserved in row["preserved_entries"]:
            code = int(preserved["code"], 0)
            dialogue.need(
                parsed[code] == bytes.fromhex(str(preserved["raw_hex"])),
                f"{scenario}화 비대사 소유 사전 코드 {code:02X} 변경",
            )
        for assignment in row["assignments"]:
            owner = (scenario, int(assignment["code"], 0))
            dialogue.need(owner not in owners, "시나리오·사전 코드 소유권 중복")
            owners.add(owner)
        writes.append((start, after, f"scenario{scenario:02d}/full-dialogue-dictionary"))
        audits.append({
            "scenario": scenario,
            "start": f"0x{start:X}",
            "bytes": len(after),
            "assignments": len(row["assignments"]),
            "preserved_external_codes": len(row["preserved_external_codes"]),
            "narration_reserved_codes": len(row["narration_reserved_codes"]),
            "records": int(row["record_count"]),
            "roundtrips": int(row["roundtrips"]),
            "free_dialogue_bytes": int(row["free"]),
            "overflow": int(row["overflow"]),
            "before_sha256": sha(before),
            "after_sha256": sha(after),
        })
    dialogue.need(len(audits) == 58, "13~70화 전용 사전 복사본 수 오류")
    dialogue.need(all(row["overflow"] == 0 for row in audits),
                  "13~70화 전용 사전 계획에 용량 초과가 남았습니다.")
    return writes, {
        "scenarios": audits,
        "scenario_code_owners": len(owners),
        "duplicate_scenario_code_owners": 0,
        "roundtrip_records": sum(row["roundtrips"] for row in audits),
        "glyph_aliases": 0,
    }


def plan_scenario01_dictionary_write(
    source: bytes,
) -> tuple[list[tuple[int, bytes, str]], dict]:
    document = json.loads(SCENARIO01_PLAN.read_text(encoding="utf-8"))
    dialogue.need(
        document.get("schema")
        == "langrisser-fx-scenario01-dialogue-phrase-extension/v1"
        and document.get("status") == "prepared",
        "1화 전용 사전 계획 형식이 다릅니다.",
    )
    row = document["dictionary"]
    start = int(row["start"], 0)
    end = int(row["end_exclusive"], 0)
    before = bytes(source[start:end])
    dialogue.need(
        len(before) == int(row["bytes"])
        and sha(before) == row["base_sha256"],
        "1화 전용 사전 기준 바이트가 다릅니다.",
    )
    after = bytes.fromhex(str(row["payload_hex"]))
    dialogue.need(
        len(after) == len(before)
        and sha(after) == row["payload_sha256"],
        "1화 전용 사전 payload가 계획과 다릅니다.",
    )
    record_count = int(row["records"])
    dialogue.need(record_count == 241,
                  "1화 전용 사전 레코드 분모 오류")
    records: list[bytes] = []
    cursor = 0
    for _index in range(record_count):
        end_of_record = after.find(b"\0", cursor)
        dialogue.need(end_of_record >= 0, "1화 전용 사전 레코드 파싱 오류")
        records.append(after[cursor:end_of_record])
        cursor = end_of_record + 1
    dialogue.need(cursor == len(after), "1화 전용 사전 241행 뒤 꼬리 오염")
    filler_code = int(str(row["filler_code"]), 0)
    dialogue.need(
        filler_code == 0xF1
        and records[filler_code - 1]
        == bytes((0x05,)) * int(row["filler_bytes"]),
        "1화 전용 사전 채움 행 오류",
    )
    for preserved in row["preserved_entries"]:
        code = int(preserved["code"], 0)
        dialogue.need(
            records[code - 1] == bytes.fromhex(str(preserved["raw_hex"])),
            f"1화 비대사 소유 사전 코드 {code:02X}가 바뀌었습니다.",
        )
    assignments = row["assignments"]
    codes = [int(assignment["code"], 0) for assignment in assignments]
    dialogue.need(len(codes) == len(set(codes)), "1화 전용 사전 코드 중복")
    dialogue.need(
        not (set(codes) & {int(value, 0) for value in row["preserved_codes"]}),
        "1화 전용 사전이 비대사 소유 코드와 충돌했습니다.",
    )
    def encode_phrase(text):
        encoded, missing = dialogue.encode_plain(text, dialogue.all_dialogue_private_mapping())
        dialogue.need(not missing, "1화 복원 기호 사전 인코딩 누락")
        return encoded

    after, reference_repairs = dialogue.reference_glyph_repairs.scenario01_payload(after, encode_phrase)
    return [(start, after, "scenario01/full-dialogue-dictionary")], {
        "start": f"0x{start:X}",
        "bytes": len(after),
        "assignments": len(assignments),
        "preserved_external_codes": len(row["preserved_codes"]),
        "records": int(document["metrics"]["records"]),
        "roundtrip_records": int(document["metrics"]["records"]),
        "free_dialogue_bytes": sum(
            int(pool["free"]) for pool in document["pools"]
        ),
        "overflow": int(document["metrics"]["overflow_bytes"]),
        "before_sha256": sha(before),
        "after_sha256": sha(after),
        "reference_glyph_repairs": reference_repairs,
        "duplicate_codes": 0,
        "glyph_aliases": 0,
    }


def plan_early_dictionary_writes(
    source: bytes,
) -> tuple[list[tuple[int, bytes, str]], dict]:
    document = json.loads(EARLY_PLAN.read_text(encoding="utf-8"))
    dialogue.need(
        document.get("schema")
        == "langrisser-fx-early-scenario-dialogue-phrase-extensions/v1"
        and document.get("status") == "prepared",
        "3~12화 전체 대사 사전 계획 형식이 다릅니다.",
    )
    writes: list[tuple[int, bytes, str]] = []
    audits = []
    owners: set[tuple[int, int]] = set()
    for row in document["scenarios"]:
        scenario = int(row["scenario"])
        start = int(row["dictionary_start"], 0)
        before = bytes(source[start:start + DICTIONARY_BYTES])
        dialogue.need(
            len(before) == DICTIONARY_BYTES
            and sha(before) == row["base_dictionary_sha256"],
            f"{scenario}화 전체 대사 사전 기준 바이트가 다릅니다.",
        )
        after = bytes.fromhex(str(row["dictionary_payload_hex"]))
        dialogue.need(
            len(after) == DICTIONARY_BYTES
            and sha(after) == row["dictionary_payload_sha256"],
            f"{scenario}화 전체 대사 사전 payload가 다릅니다.",
        )
        parsed: list[bytes] = []
        cursor = 0
        for _index in range(242):
            end = after.find(b"\0", cursor)
            dialogue.need(end >= 0, f"{scenario}화 전체 사전 파싱 오류")
            parsed.append(after[cursor:end])
            cursor = end + 1
        dialogue.need(after[cursor:] == bytes(len(after) - cursor),
                      f"{scenario}화 전체 사전 꼬리 오염")
        for preserved in row["preserved_entries"]:
            code = int(preserved["code"], 0)
            dialogue.need(
                parsed[code] == bytes.fromhex(str(preserved["raw_hex"])),
                f"{scenario}화 비대사 사전 코드 {code:02X} 변경",
            )
        for assignment in row["assignments"]:
            owner = (scenario, int(assignment["code"], 0))
            dialogue.need(owner not in owners, "3~12화 시나리오·사전 코드 중복")
            owners.add(owner)
        writes.append((start, after, f"scenario{scenario:02d}/full-dialogue-dictionary"))
        audits.append({
            "scenario": scenario,
            "start": f"0x{start:X}",
            "bytes": len(after),
            "assignments": len(row["assignments"]),
            "preserved_external_codes": len(row["preserved_external_codes"]),
            "records": int(row["record_count"]),
            "roundtrips": int(row["roundtrips"]),
            "free_dialogue_bytes": int(row["free"]),
            "overflow": int(row["overflow"]),
            "before_sha256": sha(before),
            "after_sha256": sha(after),
        })
    dialogue.need(len(audits) == 10, "3~12화 전체 대사 사전 복사본 수 오류")
    dialogue.need(all(not row["overflow"] for row in audits),
                  "3~12화 전체 대사 사전 계획에 용량 초과")
    return writes, {
        "scenarios": audits,
        "assignments": len(owners),
        "scenario_code_owners": len(owners),
        "duplicate_scenario_code_owners": 0,
        "roundtrip_records": sum(row["roundtrips"] for row in audits),
        "phrase_aliases": 0,
        "glyph_aliases": 0,
    }
