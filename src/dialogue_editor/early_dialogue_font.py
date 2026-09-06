#!/usr/bin/env python3
"""Append the lossless Scenario 3-12 glyphs to every Resource-12 atlas."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_r80_global_text_atlas_items_successor45 as atlas  # noqa: E402

import dialogue_core as dialogue  # noqa: E402
import epilogue_codec as epilogue  # noqa: E402
import resource12_router  # noqa: E402


PLAN = ROOT / "dialogue_editor/early_dialogue_glyph_extension_successor193.json"
GLOBAL_PLAN = ROOT / "dialogue_editor/global_text_glyph_extension_successor200.json"
HELPER_SPAN = 0x100
ROUTER_OFFSET = 0x100
ROUTER_BYTES = resource12_router.BYTES
HANDLER_BASE_VALUE = 0xF33D
HANDLER_COOKED = 0x0004F00C
HANDLER_UPPER_MOVEA_OFFSET = 0x28
EXPANDED_FULL_BYTES = 0x18800
EXPANDED_TAIL_BYTES = EXPANDED_FULL_BYTES - atlas.FULL_OLD
EXTENDED_LEADS = (0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def load_plan() -> dict:
    document = json.loads(PLAN.read_text(encoding="utf-8"))
    dialogue.need(
        document.get("schema")
        == "langrisser-fx-early-dialogue-glyph-extension/v1"
        and document.get("status") == "adopted",
        "3~12화 무축약 글리프 확장 자료 형식이 다릅니다.",
    )
    return document


def load_global_plan() -> dict:
    document = json.loads(GLOBAL_PLAN.read_text(encoding="utf-8"))
    dialogue.need(
        document.get("schema")
        == "langrisser-fx-global-dialogue-glyph-extension/v1"
        and document.get("status") == "prepared",
        "전체 대사 글리프 확장 자료 형식이 다릅니다.",
    )
    return document


def resource12_tails(source: bytes) -> tuple[int, ...]:
    offsets = struct.unpack(
        "<17I", source[atlas.RESOURCE12:atlas.RESOURCE12 + 17 * 4]
    )
    starts: list[int] = []
    for left, right in zip(offsets, offsets[1:]):
        length = right - left
        if length == EXPANDED_FULL_BYTES:
            starts.append(atlas.RESOURCE12 + left + atlas.FULL_OLD)
        else:
            dialogue.need(length == atlas.SHORT,
                          "Resource-12 하위 리소스 크기가 달라졌습니다.")
    dialogue.need(len(starts) == 15, "Resource-12 전체 복제 수가 다릅니다.")
    payloads = [source[start:start + EXPANDED_TAIL_BYTES] for start in starts]
    dialogue.need(all(len(payload) == EXPANDED_TAIL_BYTES for payload in payloads),
                  "Resource-12 꼬리 범위 초과")
    dialogue.need(len({sha(payload) for payload in payloads}) == 1,
                  "Resource-12 꼬리 복제본이 서로 다릅니다.")
    return tuple(starts)


def verify_final_router_contract(image: bytes) -> dict:
    """Verify the dispatcher and all physical routers after the last writer."""
    handler = HANDLER_COOKED + HANDLER_UPPER_MOVEA_OFFSET
    dialogue.need(image[handler:handler + 2] == bytes.fromhex("6BA1"),
                  "최종 공용 글꼴 분기 명령이 변경되었습니다.")
    upper = HANDLER_BASE_VALUE + int.from_bytes(
        image[handler + 2:handler + 4], "little", signed=True)
    tails = resource12_tails(image)
    contract = None
    for tail in tails:
        start = tail + ROUTER_OFFSET
        contract = resource12_router.verify(image[start:start + ROUTER_BYTES], upper)
    return {"replicas_verified": len(tails), "contract": contract,
            "verified_after_last_writer": True}


def build_helper(rows: list[tuple[str, int]], leads: tuple[int, ...]) -> tuple[bytes, dict]:
    """Build the direct 18-byte atlas helper, including the new F8 page."""
    upper = rows[-1][1] + 1
    a = atlas.Assembler(atlas.TAIL_RAM + atlas.HELPER_OFFSET)
    a.load_address(upper, 10)
    a.reg(0x03, 10, 6)
    a.branch(0x4E, "original")
    a.mov(6, 10)
    a.imm5(0x15, 8, 10)
    for lead in leads:
        a.movea(lead, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x42, f"lead_{lead:02X}")
    a.branch(0x45, "original")
    for page, lead in enumerate(leads):
        a.label(f"lead_{lead:02X}")
        a.load_address(
            atlas.TAIL_RAM + atlas.ATLAS_OFFSET
            + page * atlas.VALID_TRAILS_PER_LEAD * atlas.GLYPH_BYTES,
            10,
        )
        a.branch(0x45, "trail")
    a.label("trail")
    a.fmt_v(0x2D, 0x00FF, 6, 6)
    a.addi(-0x40, 6, 6)
    a.movea(0x40, 0, 11)
    a.reg(0x03, 11, 6)
    a.branch(0x46, "index_ready")
    a.add_i(-1, 6)
    a.label("index_ready")
    a.mov(6, 11)
    a.imm5(0x14, 4, 6)
    a.imm5(0x14, 1, 11)
    a.reg(0x01, 11, 6)
    a.reg(0x01, 10, 6)
    a.code.extend(atlas.encode_jr(a.pc, atlas.GLYPH_RENDERER_RAM))
    a.label("original")
    a.load_address(0x00010000, 10)
    a.movea(0xF040, 10, 10)
    a.code.extend(atlas.encode_jr(a.pc, atlas.ORIGINAL_THIRD_RAM))
    code = a.finish()
    dialogue.need(len(code) <= HELPER_SPAN,
                  f"F8 확장 글리프 도우미가 {len(code)}/256바이트입니다.")
    return code, dict(a.labels)


def installed_rows(plan: dict) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    extension_codes = {
        int(row["code"], 0) for row in plan["font"]["assignments"]
    }
    early = sorted(
        (
            (character, int.from_bytes(code, "big"))
            for character, code in dialogue.early_private_mapping().items()
            if (len(code) == 2 and 0xF4 <= code[0] <= 0xF7
                and int.from_bytes(code, "big") not in extension_codes)
        ),
        key=lambda row: row[1],
    )
    dialogue.need(
        len(early) == 670 and early[0][1] == 0xF440
        and early[-1][1] == 0xF7AA,
        "기존 3~12화 F4-F7 글리프 소유표가 달라졌습니다.",
    )
    ending = list(epilogue.plan_assignments(epilogue.load_plan()))
    ending = [(character, code) for character, code in ending]
    dialogue.need(
        len(ending) == 63 and ending[0][1] == 0xF7AB
        and ending[-1][1] == 0xF7E9,
        "기존 엔딩 후일담 글리프 소유표가 달라졌습니다.",
    )
    base = early + ending
    expected = tuple(itertools.islice(atlas.valid_codes(0xF440), len(base)))
    dialogue.need(tuple(code for _character, code in base) == expected,
                  "기존 Resource-12 글리프 코드가 연속적이지 않습니다.")
    return base, ending


def plan_writes(source: bytes) -> tuple[list[tuple[int, bytes, str]], dict]:
    plan = load_plan()
    global_plan = load_global_plan()
    base, _ending = installed_rows(plan)
    early_additions = [
        (str(row["character"]), int(row["code"], 0), str(row["glyph"]), row["sha256"])
        for row in plan["font"]["assignments"]
    ]
    global_additions = [
        (str(row["character"]), int(row["code"], 0), str(row["glyph"]), row["sha256"])
        for row in global_plan["font"]["assignments"]
    ]
    additions = early_additions + global_additions
    dialogue.need(
        len(early_additions) == 121 and early_additions[0][1] == 0xF7EA
        and early_additions[-1][1] == 0xF8A6
        and len(global_additions) == 211
        and global_additions[0][1] == 0xF8A7
        and global_additions[-1][1] == 0xF9BD,
        "전체 무축약 글리프 추가 범위가 달라졌습니다.",
    )
    expected_codes = tuple(
        itertools.islice(atlas.valid_codes(0xF440), len(base) + len(additions))
    )
    dialogue.need(
        tuple(code for _character, code in base)
        + tuple(code for _character, code, _path, _sha in additions)
        == expected_codes,
        "전체 무축약 글리프 코드가 기존 표 뒤에 연속되지 않습니다.",
    )
    glyph_parts: list[bytes] = []
    for character, code, relative, expected_sha in additions:
        glyph = (ROOT / relative).read_bytes()
        dialogue.need(
            len(glyph) == atlas.GLYPH_BYTES and any(glyph)
            and sha(glyph) == expected_sha,
            f"무축약 글리프 자산 오류: {character}/0x{code:04X}",
        )
        glyph_parts.append(glyph)
    glyphs = b"".join(glyph_parts)
    dialogue.need(
        sha(glyphs[:len(early_additions) * atlas.GLYPH_BYTES])
        == plan["font"]["payload_sha256"]
        and sha(glyphs[len(early_additions) * atlas.GLYPH_BYTES:])
        == global_plan["font"]["payload_sha256"]
        and len(glyphs) == len(additions) * atlas.GLYPH_BYTES,
        "전체 무축약 글리프 묶음이 계획과 다릅니다.",
    )

    old_helper, _old_symbols = atlas.build_helper(base)
    new_rows = base + [(character, code) for character, code, _path, _sha in additions]
    new_helper, symbols = build_helper(new_rows, EXTENDED_LEADS)
    new_upper = new_rows[-1][1] + 1
    new_router = resource12_router.build(new_upper)
    router_contract = resource12_router.verify(new_router, new_upper)
    old_span = old_helper.ljust(HELPER_SPAN, b"\0")
    new_span = new_helper.ljust(HELPER_SPAN, b"\0")
    glyph_offset = atlas.ATLAS_OFFSET + len(base) * atlas.GLYPH_BYTES
    dialogue.need(
        glyph_offset + len(glyphs) <= EXPANDED_TAIL_BYTES,
        "Resource-12 확장 꼬리 글리프 공간 초과",
    )
    writes: list[tuple[int, bytes, str]] = []
    starts = resource12_tails(source)
    router_hashes: set[str] = set()
    for replica, start in enumerate(starts):
        dialogue.need(
            source[start:start + HELPER_SPAN] == old_span,
            f"Resource-12 도우미 복제 {replica} 기준 바이트가 다릅니다.",
        )
        router = source[
            start + ROUTER_OFFSET:start + ROUTER_OFFSET + ROUTER_BYTES
        ]
        router_hashes.add(sha(router))
        dialogue.need(router == resource12_router.INHERITED,
                      f"Resource-12 라우터 복제 {replica} 기준 바이트가 다릅니다.")
        target = start + glyph_offset
        dialogue.need(
            source[target:target + len(glyphs)] == bytes(len(glyphs)),
            f"Resource-12 새 글리프 복제 {replica} 영역이 비어 있지 않습니다.",
        )
        writes.extend((
            (start, new_span, f"resource12/faithful-helper/{replica:02d}"),
            (start + ROUTER_OFFSET, new_router,
             f"resource12/faithful-router/{replica:02d}"),
            (target, glyphs, f"resource12/faithful-glyphs/{replica:02d}"),
        ))
    dialogue.need(len(router_hashes) == 1,
                  "Resource-12 보호 라우터 복제본이 다릅니다.")

    handler_offset = HANDLER_COOKED + HANDLER_UPPER_MOVEA_OFFSET
    old_upper = base[-1][1] + 1
    new_upper = additions[-1][1] + 1
    handler_before = bytes.fromhex("6BA1") + (
        old_upper - HANDLER_BASE_VALUE
    ).to_bytes(2, "little")
    handler_after = bytes.fromhex("6BA1") + (
        new_upper - HANDLER_BASE_VALUE
    ).to_bytes(2, "little")
    dialogue.need(
        source[handler_offset:handler_offset + 4] == handler_before,
        "F4-F8 렌더러 상한 기준 바이트가 다릅니다.",
    )
    writes.append((handler_offset, handler_after, "renderer/faithful-f8-upper-bound"))
    return writes, {
        "replicas": len(starts),
        # The 121 early-dialogue cells are already established owners in the
        # current text atlas.  This build recreates them in the newly appended
        # Resource-12 tails, but only the successor200 global cells are new
        # ownership.  Keep the audit denominator aligned with the glyph plan.
        "existing_cells": len(base) + len(early_additions),
        "new_cells": len(global_additions),
        "installed_cells_written": len(additions),
        "remaining_cells": (
            (EXPANDED_TAIL_BYTES - atlas.ATLAS_OFFSET) // atlas.GLYPH_BYTES
            - len(base) - len(additions)
        ),
        "code_first": f"0x{global_additions[0][1]:04X}",
        "code_last": f"0x{global_additions[-1][1]:04X}",
        "glyph_offset_in_tail": f"0x{glyph_offset:X}",
        "glyph_payload_sha256": sha(glyphs),
        "helper_before_bytes": len(old_helper),
        "helper_after_bytes": len(new_helper),
        "helper_owned_span": HELPER_SPAN,
        "handler_before_hex": handler_before.hex().upper(),
        "handler_after_hex": handler_after.hex().upper(),
        "router_before_sha256": next(iter(router_hashes)),
        "router_after_sha256": sha(new_router),
        "router_contract": router_contract,
        "symbols": {key: f"0x{value:X}" for key, value in symbols.items()},
        "glyph_aliases": 0,
        "existing_cells_overwritten": 0,
        "resource_extent_changed": True,
    }
