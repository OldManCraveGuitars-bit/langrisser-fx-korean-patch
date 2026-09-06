"""Install the proven visual-only dialogue continuation in Resource-12.

The last 0x200 bytes of every expanded full Resource-12 subresource map to
RAM 0x1E9E00..0x1EA000.  They are outside the 1074-cell text atlas and are
zero in every physical replica.  Ordinary field dialogue already depends on
that same full Resource-12 atlas, so the helper and the F4-F9 glyphs have one
load/residency lifetime.  The short non-field subresource is deliberately not
modified.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
from pathlib import Path

import dialogue_core as dialogue
import early_dialogue_font as font
import dialogue_continuation_probe_code as compiler


OFFSET = compiler.BASE - font.atlas.TAIL_RAM  # 0x5E00 in the expanded tail.
SPAN = compiler.CAPACITY
HELPER_BYTES = 204
HELPER_SHA256 = "A2990C29D2AC4D5F69800F1C7100F023BB7EF0A4ADC27C2FDE2F50333F2A6A66"
DISPATCH = {
    0xF4AC: ("aa4d", "ab4d"),
    0xF864: ("43cd0800", "ca4c4084"),
    0xF88E: (
        "c0bd0600cea16ca9aecd00008d01a145aedd0000ecc10000e0d13c0a328a",
        "c0bd0600aecd6ca9edc10000a145aedd6ca9e0d13c0a388a1dac5aa5328a",
    ),
    0xF868: ("414d", "c14c"),
    0xF86C: ("424d", "c24c"),
    0xF870: ("434d", "c34c"),
    0xF874: ("444d", "c44c"),
    0xF878: ("454d", "c54c"),
    0xF87C: ("464d", "c64c"),
    0xF880: ("474d", "c74c"),
    0xF884: ("484d", "c84c"),
    0xF888: ("494d", "c94c"),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


@lru_cache(maxsize=1)
def payload() -> bytes:
    """Compile from the immutable base code and pin the exact helper."""
    source_path = dialogue.BASE_DIR / dialogue.BASE_COOKED_NAME
    dialogue.need(source_path.is_file(), "시각 전용 페이지 도우미 기준 이미지 없음")
    with source_path.open("rb") as stream:
        source = stream.read(0x30000)
    code, writes, _report = compiler.build(source)
    dialogue.need(
        len(code) == HELPER_BYTES and _sha(code) == HELPER_SHA256,
        "시각 전용 페이지 도우미 기계어가 변경되었습니다.",
    )
    found = {
        int(write["ram"]): (bytes(write["before"]), bytes(write["after"]))
        for write in writes
    }
    expected = {
        address: (bytes.fromhex(before), bytes.fromhex(after))
        for address, (before, after) in DISPATCH.items()
    }
    dialogue.need(found == expected, "시각 전용 페이지 디스패처 계약 변경")
    return code.ljust(SPAN, b"\0")


def _validate_nonoverlap(writes: list[dict]) -> None:
    spans = sorted(
        (int(write["offset"]), int(write["offset"]) + len(write["replacement"]),
         str(write["id"]))
        for write in writes
    )
    for left, right in zip(spans, spans[1:]):
        dialogue.need(left[1] <= right[0],
                      f"시각 전용 페이지 쓰기 중복: {left[2]} / {right[2]}")


def plan_writes(image: bytes) -> tuple[list[dict], dict]:
    expected_payload = payload()
    code, dispatch, machine = compiler.build(image)
    dialogue.need(code.ljust(SPAN, b"\0") == expected_payload,
                  "빌드 이미지의 시각 전용 페이지 도우미가 기준과 다릅니다.")

    # Bind the allocation against the final all-Unifont atlas denominator,
    # not against an assumption that a run of zero bytes is free.
    import build_r80_successor204_resource12_unifont_all_successor205 as unifont
    rows, bank = unifont.rows_and_bank()
    atlas_end = font.atlas.ATLAS_OFFSET + len(bank)
    dialogue.need(len(rows) == 1074 and atlas_end <= OFFSET,
                  "Resource-12 글꼴과 페이지 도우미 소유 범위가 겹칩니다.")
    dialogue.need(OFFSET + SPAN == font.EXPANDED_TAIL_BYTES,
                  "페이지 도우미가 Resource-12 전체 꼬리 끝에 고정되지 않았습니다.")

    writes: list[dict] = []
    for ordinal, tail in enumerate(font.resource12_tails(image)):
        start = tail + OFFSET
        before = image[start:start + SPAN]
        dialogue.need(before == bytes(SPAN),
                      f"페이지 도우미 소유 범위가 비어 있지 않습니다: 복제 {ordinal}")
        writes.append({
            "id": f"dialogue/visual-continuation/replica-{ordinal:02d}",
            "offset": start,
            "expected": before,
            "replacement": expected_payload,
        })
    for write in dispatch:
        address = int(write["ram"])
        before, after = DISPATCH[address]
        expected, replacement = bytes.fromhex(before), bytes.fromhex(after)
        cooked = address - compiler.DELTA
        dialogue.need(
            image[cooked:cooked + len(expected)] == expected
            and bytes(write["before"]) == expected
            and bytes(write["after"]) == replacement,
            f"페이지 제어 디스패처 기준 바이트 변경: 0x{address:X}",
        )
        writes.append({
            "id": f"dialogue/visual-continuation/dispatch-{address:05X}",
            "offset": cooked,
            "expected": expected,
            "replacement": replacement,
        })
    _validate_nonoverlap(writes)
    return writes, {
        "control": "0x0A",
        "helper_ram": f"0x{compiler.BASE:X}",
        "helper_bytes": HELPER_BYTES,
        "owned_span_bytes": SPAN,
        "helper_sha256": HELPER_SHA256,
        "physical_full_replicas": len(font.resource12_tails(image)),
        "short_subresources_modified": 0,
        "tail_offset": f"0x{OFFSET:X}",
        "tail_end_ram": f"0x{font.atlas.TAIL_RAM + font.EXPANDED_TAIL_BYTES:X}",
        "atlas_rows": len(rows),
        "atlas_end_offset": f"0x{atlas_end:X}",
        "free_guard_before_helper_bytes": OFFSET - atlas_end,
        "resource_extent_changed": False,
        "existing_voice_pages_changed": False,
        "machine": machine,
    }


def verify_final(image: bytes) -> dict:
    expected_payload = payload()
    tails = font.resource12_tails(image)
    for ordinal, tail in enumerate(tails):
        dialogue.need(
            image[tail + OFFSET:tail + OFFSET + SPAN] == expected_payload,
            f"최종 페이지 도우미 복제본 불일치: {ordinal}",
        )
    for address, (_before, after) in DISPATCH.items():
        cooked = address - compiler.DELTA
        replacement = bytes.fromhex(after)
        dialogue.need(image[cooked:cooked + len(replacement)] == replacement,
                      f"최종 페이지 디스패처 불일치: 0x{address:X}")
    return {
        "control": "0x0A",
        "helper_ram": f"0x{compiler.BASE:X}",
        "helper_sha256": HELPER_SHA256,
        "replicas_verified": len(tails),
        "dispatch_writes_verified": len(DISPATCH),
        "verified_after_last_writer": True,
    }
