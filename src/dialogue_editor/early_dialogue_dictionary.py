#!/usr/bin/env python3
"""Fixed-extent, record-private dictionary extension for Scenarios 3-12."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_scenario02_overlay_dialogue_candidate import (  # noqa: E402
    decode_candidate,
    encode_direct,
)
from extract_scenario_dictionary import split_records  # noqa: E402

import dialogue_core as dialogue  # noqa: E402


PLAN = ROOT / "dialogue_editor/early_dialogue_phrase_extension_successor193.json"
COMMON_RECORDS = 525
DICTIONARY_RECORDS = 242
TABLE_RECORDS = COMMON_RECORDS + DICTIONARY_RECORDS
NEVER_ASSIGN = frozenset((0, 240, 241))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def load_plan() -> dict:
    document = json.loads(PLAN.read_text(encoding="utf-8"))
    dialogue.need(
        document.get("schema")
        == "langrisser-fx-early-dialogue-phrase-extension/v1"
        and document.get("status") == "adopted",
        "3~12화 전용 사전 확장 자료 형식이 다릅니다.",
    )
    return document


def extension_phrases(scenario: int) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in load_plan()["scenarios"]:
        if int(row["scenario"]) != scenario:
            continue
        for assignment in row["assignments"]:
            phrase = str(assignment["phrase"])
            code = int(assignment["code"], 0) & 0xFF
            dialogue.need(phrase not in result, f"{scenario}화 전용 문구 중복")
            dialogue.need(code not in result.values(), f"{scenario}화 전용 코드 중복")
            result[phrase] = code
    return result


def plan_writes(source: bytes) -> tuple[list[tuple[int, bytes, str]], dict]:
    document = load_plan()
    private = dialogue.early_private_mapping()
    reverse_private = {value: key for key, value in private.items()}
    writes: list[tuple[int, bytes, str]] = []
    audits: list[dict[str, object]] = []
    owner_pairs: set[tuple[int, int]] = set()
    owner_records: set[str] = set()
    for row in document["scenarios"]:
        scenario = int(row["scenario"])
        start = int(row["table_start"], 0)
        end = int(row["table_end_exclusive"], 0)
        before = bytes(source[start:end])
        dialogue.need(
            len(before) == int(row["table_capacity_bytes"])
            and sha(before) == row["base_table_sha256"],
            f"{scenario}화 전용 사전 기준표가 달라졌습니다.",
        )
        records = split_records(before)
        dialogue.need(
            len(records) >= TABLE_RECORDS,
            f"{scenario}화 공용표 레코드 수가 부족합니다.",
        )
        common = records[:COMMON_RECORDS]
        dictionary_rows = list(records[COMMON_RECORDS:TABLE_RECORDS])
        dialogue.need(
            len(dictionary_rows) == DICTIONARY_RECORDS,
            f"{scenario}화 사전 레코드 수가 다릅니다.",
        )

        compression_plan = dialogue.load_json(
            ROOT / "analysis" / dialogue.EARLY[scenario][1]
        )
        assigned = {
            int(assignment["code"], 0) & 0xFF
            for assignment in compression_plan["dictionary"]["assignments"]
        }
        reserved = {
            int(code, 0) & 0xFF
            for code in compression_plan["dictionary"]["reserved_codes"]
        }
        safe = set(range(DICTIONARY_RECORDS)) - assigned - reserved - NEVER_ASSIGN
        dialogue.need(
            len(safe)
            == int(compression_plan["dictionary"]["unassigned_usable_entries"]),
            f"{scenario}화 회수 가능 사전 코드 수가 달라졌습니다.",
        )
        for code in safe:
            dictionary_rows[code] = b"\0"

        assignments = row["assignments"]
        dialogue.need(
            len({assignment["record_id"] for assignment in assignments})
            == len(assignments),
            f"{scenario}화 한 레코드가 여러 전용 문구를 공유합니다.",
        )
        assignment_audit: list[dict[str, object]] = []
        for assignment in assignments:
            record_id = str(assignment["record_id"])
            phrase = str(assignment["phrase"])
            code = int(assignment["code"], 0) & 0xFF
            dialogue.need(code in safe, f"{scenario}화 사전 코드가 안전 영역 밖입니다.")
            dialogue.need((scenario, code) not in owner_pairs,
                          f"{scenario}화 사전 코드 소유권 중복")
            dialogue.need(record_id not in owner_records,
                          f"전용 사전 레코드 소유권 중복: {record_id}")
            encoded = encode_direct(phrase, private)
            dialogue.need(
                encoded.hex().upper() == assignment["encoded_hex"]
                and b"\0" not in encoded,
                f"{record_id}: 전용 사전 문구 인코딩이 달라졌습니다.",
            )
            decoded = decode_candidate(encoded, reverse_private, {})
            dialogue.need(decoded == phrase,
                          f"{record_id}: 전용 사전 문구 왕복 실패")
            dictionary_rows[code] = encoded + b"\0"
            owner_pairs.add((scenario, code))
            owner_records.add(record_id)
            assignment_audit.append({
                "record_id": record_id,
                "code": f"0x04{code:02X}",
                "phrase": phrase,
                "bytes": len(encoded) + 1,
                "roundtrip": True,
                "unique_owner": True,
            })

        packed = b"".join(common + dictionary_rows)
        dialogue.need(
            len(packed) == int(row["table_packed_bytes"])
            and len(packed) <= len(before),
            f"{scenario}화 전용 사전 고정 범위 계산이 달라졌습니다.",
        )
        after = packed + bytes(len(before) - len(packed))
        dialogue.need(len(after) == len(before),
                      f"{scenario}화 사전 표 크기 변경")
        writes.append((start, after, f"scenario{scenario:02d}/private-dictionary"))
        audits.append({
            "scenario": scenario,
            "start": f"0x{start:X}",
            "end_exclusive": f"0x{end:X}",
            "capacity_bytes": len(before),
            "packed_bytes": len(packed),
            "free_bytes": len(before) - len(packed),
            "assignments": assignment_audit,
            "cleared_safe_rows": len(safe) - len(assignments),
            "resource_extent_changed": False,
        })
    dialogue.need(
        len(owner_pairs) == len(owner_records)
        == sum(len(row["assignments"]) for row in document["scenarios"]),
        "전용 사전 소유권 분모가 다릅니다.",
    )
    return writes, {
        "scenarios": audits,
        "assignments": len(owner_records),
        "phrase_aliases": 0,
        "code_aliases_within_resource": 0,
        "resource_extents_changed": 0,
        "roundtrip_records": len(owner_records),
    }
