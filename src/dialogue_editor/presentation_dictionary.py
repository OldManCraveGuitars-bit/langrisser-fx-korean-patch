#!/usr/bin/env python3
"""Lossless scenario-local dictionary storage for presentation text.

Scenario resources keep their narration aggregate in nested section 7 and a
241-record local dictionary in section 4.  Edited narration can be stored in
individually owned dictionary records and referenced with ``04 NN``.

This module deliberately does not share one authored phrase between records:
each edited narration owns one dictionary code.  Every source row is preserved
byte for byte unless the complete local-resource scan proves that exact row is
available and the allocator explicitly assigns it.  The game reads additional
rows while initializing a presentation, outside the visible text spans; zeroing
apparently unused rows therefore freezes Scenario 1 and Scenario 3+.  The
dictionary extent and every section offset remain unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct

import dialogue_core as dialogue
import missing_presentations


COMMON_SECTION_PREFIX = (0x24, 0x6C4, 0x9B0, 0x1500, 0x300C)
COMMON_SECTION_PREFIX_BYTES = struct.pack(
    f"<{len(COMMON_SECTION_PREFIX)}I", *COMMON_SECTION_PREFIX
)
SECTION_COUNT = 9
DICTIONARY_SECTION = 4
PRESENTATION_SECTION = 7
DICTIONARY_RECORDS = 241
MAX_PROVEN_DICTIONARY_CODE = 0xEF
# The system-menu save question invokes local dictionary code 0x1A through a
# fixed runtime path outside the presentation/common/dialogue spans scanned by
# referenced_codes().  It is the only hidden owner in this section.  Item
# records 205..346 live in the separate common-text section; their numbering
# is not a dictionary code and their physical writes do not intersect this
# section.
RUNTIME_RESERVED_DICTIONARY_CODES = frozenset({0x1A})
# The native runtime proof used a low dictionary row and later presentation
# setup was observed to consume low rows without a visible 04 NN owner.  Never
# reclaim this native range.  Capacity may be recovered only from scanned-free
# high rows, and only as much as the selected payloads require.
RUNTIME_SOURCE_PRESERVE_MAX = 0x9C
PRESENTATION_PREFIX = b"\x05\x08\x04\x01"


@dataclass(frozen=True)
class LocalPresentationResource:
    header_offset: int
    section_offsets: tuple[int, ...]
    sections: tuple[int, ...]
    dictionary_offset: int
    dictionary_allocation: int
    presentation_offset: int
    presentation_allocation: int
    dictionary_rows: tuple[bytes, ...]


@dataclass(frozen=True)
class DictionaryPlan:
    replacement: bytes
    assignments: tuple[tuple[str, int], ...]
    preserved_codes: tuple[int, ...]
    cleared_codes: tuple[int, ...]
    packed_bytes: int
    padding_bytes: int


def _split_dictionary(raw: bytes) -> tuple[bytes, ...]:
    rows: list[bytes] = []
    cursor = 0
    while cursor < len(raw) and len(rows) < DICTIONARY_RECORDS:
        end = raw.find(b"\0", cursor)
        dialogue.need(end >= 0, "프레젠테이션 로컬 사전 레코드 종단 없음")
        rows.append(raw[cursor:end])
        cursor = end + 1
    dialogue.need(
        len(rows) == DICTIONARY_RECORDS,
        f"프레젠테이션 로컬 사전 레코드 수 변경: {len(rows)}",
    )
    dialogue.need(
        raw[cursor:] == bytes(len(raw) - cursor),
        "프레젠테이션 로컬 사전 꼬리 오염",
    )
    return tuple(rows)


def locate_resource(
    image: bytes | bytearray,
    presentation_anchor: int,
    *,
    allow_authored_title: bool = False,
) -> LocalPresentationResource:
    """Locate the live nested resource owning one catalogue presentation.

    Historical catalogues describe the original aggregate.  Earlier condition
    work shifted Scenario 16's live section-7 start by four bytes, so the
    active header is authoritative and the catalogue offset is only an anchor.
    """

    start = max(0, presentation_anchor - 0x10000)
    end = min(len(image), presentation_anchor + 0x100)
    candidates: list[LocalPresentationResource] = []
    cursor = start
    while True:
        hit = image.find(COMMON_SECTION_PREFIX_BYTES, cursor, end)
        if hit < 0:
            break
        header = hit - 8
        cursor = hit + 1
        if header < 0:
            continue
        first = struct.unpack_from("<I", image, header + 8)[0]
        if first != 0x24:
            continue
        relative = struct.unpack_from(
            f"<{SECTION_COUNT}I", image, header + 8
        )
        if tuple(sorted(relative)) != relative:
            continue
        sections = tuple(header + 8 + value for value in relative)
        live_presentation = sections[PRESENTATION_SECTION]
        # Section 4/7 balanced repacks intentionally move section starts while
        # the outer resource and catalogue anchor remain fixed.  The first
        # five section offsets identify the same resource; accept the proved
        # local movement window and still require one unique candidate below.
        if abs(live_presentation - presentation_anchor) > 0x400:
            continue
        prefix = bytes(image[live_presentation:live_presentation + 24])
        # The number row can start with centered native 12/8/4px padding.
        # Accept only the known initial newline and label grammar, not an
        # arbitrary section that happens to contain a dictionary command.
        centered = prefix
        if centered.startswith(b"\x08"):
            centered = centered[1:]
            while centered.startswith((b"\x05", bytes.fromhex("F1E6"), bytes.fromhex("F1E8"))):
                centered = centered[1:] if centered[0] == 5 else centered[2:]
        else:
            centered = b""
        centered_label = (
            len(centered) >= 2 and centered[0] == 4
            and 1 <= centered[1] <= MAX_PROVEN_DICTIONARY_CODE
        ) or centered.startswith(bytes.fromhex("827282628264826D826082718268826E817C"))
        authored_title = allow_authored_title and (
            centered_label
            or
            (prefix.startswith(b"\x05\x08\x04") and 1 <= prefix[3] <= MAX_PROVEN_DICTIONARY_CODE)
            or prefix.startswith(bytes.fromhex("0508827282628264826D826082718268826E817C"))
            or (presentation_anchor == 0x13C378
                and prefix.startswith(bytes.fromhex("080505F1E804"))
                and 1 <= prefix[6] <= MAX_PROVEN_DICTIONARY_CODE)
        )
        dialogue.need(
            prefix.startswith(PRESENTATION_PREFIX) or authored_title
            or missing_presentations.original_prefix_matches(presentation_anchor, prefix),
            f"0x{presentation_anchor:08X}: 실사용 프레젠테이션 접두부 변경",
        )
        dictionary_offset = sections[DICTIONARY_SECTION]
        dictionary_end = sections[DICTIONARY_SECTION + 1]
        presentation_end = sections[PRESENTATION_SECTION + 1]
        raw_dictionary = bytes(image[dictionary_offset:dictionary_end])
        candidates.append(LocalPresentationResource(
            header_offset=header,
            section_offsets=tuple(relative),
            sections=sections,
            dictionary_offset=dictionary_offset,
            dictionary_allocation=dictionary_end - dictionary_offset,
            presentation_offset=live_presentation,
            presentation_allocation=presentation_end - live_presentation,
            dictionary_rows=_split_dictionary(raw_dictionary),
        ))
    dialogue.need(
        len(candidates) == 1,
        f"0x{presentation_anchor:08X}: 로컬 프레젠테이션 자원 "
        f"후보 수 {len(candidates)}",
    )
    return candidates[0]


def _references(raw: bytes) -> set[int]:
    """Return real ``04 NN`` dictionary tokens from one text byte stream.

    Speaker/name controls are encoded as ``09 NN``.  The old byte-by-byte
    scan revisited their argument byte, so ``09 04`` followed by a Korean
    glyph beginning with ``F6`` was falsely reported as dictionary code
    ``04 F6``.  Walk the same control and two-byte glyph boundaries used by
    the dialogue renderer so argument and trail bytes can never become
    synthetic dictionary references.
    """

    result: set[int] = set()
    cursor = 0
    while cursor + 1 < len(raw):
        value = raw[cursor]
        if value == 0x04:
            code = raw[cursor + 1]
            # 04 00 is a native empty/control form, not dictionary row zero.
            # Treating it as a reference made otherwise valid Scenario 7/10
            # resources fail the local-ownership audit.
            if code:
                result.add(code)
            cursor += 2
        elif value == 0x09:
            # Speaker/name control plus its one-byte argument.
            cursor += 2
        elif value == 0x06 and raw[cursor + 1] == 0x07:
            cursor += 2
        elif 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC:
            # Shift-JIS and the private Korean atlas both use two-byte glyphs.
            cursor += 2
        else:
            cursor += 1
    return result


def _presentation_frames(raw: bytes) -> tuple[bytes, ...]:
    frames: list[bytes] = []
    cursor = 0
    page = b"\x06\x07"
    while True:
        end = raw.find(page, cursor)
        if end < 0:
            return tuple(frames)
        frames.append(raw[cursor:end + len(page)])
        cursor = end + len(page)


def referenced_codes(
    image: bytes | bytearray,
    resource: LocalPresentationResource,
    *,
    released_presentation_frame_indexes: frozenset[int] = frozenset(),
) -> tuple[int, ...]:
    """Return dictionary codes used by all live text sections and dependencies."""

    sections = resource.sections
    direct = set()
    # Section 3 is common text, 5 is dialogue, and 6 is conditions.
    # Binary/font sections are intentionally excluded.  Presentation frames
    # being replaced may release their former dictionary dependencies, but
    # every untouched title/condition/narration frame remains authoritative.
    for section in (3, 5, 6):
        direct.update(_references(bytes(image[sections[section]:sections[section + 1]])))
    presentation = bytes(
        image[resource.presentation_offset:
              resource.presentation_offset + resource.presentation_allocation]
    )
    frames = _presentation_frames(presentation)
    dialogue.need(
        all(0 <= index < len(frames)
            for index in released_presentation_frame_indexes),
        "해제할 프레젠테이션 프레임 인덱스 범위 오류",
    )
    for index, frame in enumerate(frames):
        if index not in released_presentation_frame_indexes:
            direct.update(_references(frame))
    closure = set(direct)
    pending = list(direct)
    while pending:
        code = pending.pop()
        if not 1 <= code <= len(resource.dictionary_rows):
            continue
        for dependency in _references(resource.dictionary_rows[code - 1]):
            if dependency not in closure:
                closure.add(dependency)
                pending.append(dependency)
    dialogue.need(
        all(1 <= code <= DICTIONARY_RECORDS for code in closure),
        f"로컬 사전 범위 밖 참조: {sorted(closure)}",
    )
    return tuple(sorted(closure))


def build_dictionary_plan(
    image: bytes | bytearray,
    resource: LocalPresentationResource,
    payloads: tuple[tuple[str, bytes], ...],
    *,
    released_presentation_frame_indexes: frozenset[int] = frozenset(),
    preserve_all_source_rows: bool = True,
) -> DictionaryPlan:
    """Give every edited narration a unique, lossless local dictionary row."""

    preserved = set(referenced_codes(
        image,
        resource,
        released_presentation_frame_indexes=(
            released_presentation_frame_indexes
        ),
    ))
    preserved.update(RUNTIME_RESERVED_DICTIONARY_CODES)
    if preserve_all_source_rows:
        preserved.update(range(1, RUNTIME_SOURCE_PRESERVE_MAX + 1))
    available = [
        code for code in range(MAX_PROVEN_DICTIONARY_CODE, 0, -1)
        if code not in preserved
    ]
    dialogue.need(
        len(payloads) <= len(available),
        "프레젠테이션 전용 로컬 사전 코드 부족",
    )
    if preserve_all_source_rows:
        # Preserve every low/native source row plus every scanned dependency.
        # High rows may be reclaimed below, but only when the chosen payloads
        # cannot fit in the fixed dictionary allocation otherwise.
        rows = list(resource.dictionary_rows)

        # Minimize dictionary growth by pairing the largest payloads with the
        # largest available source rows.  This keeps all section boundaries
        # fixed and lets the caller fall back to fewer external records.
        payload_order = sorted(
            range(len(payloads)),
            key=lambda index: (-len(payloads[index][1]), payloads[index][0]),
        )
        code_order = sorted(
            available,
            key=lambda code: (-len(resource.dictionary_rows[code - 1]), code),
        )
        chosen_codes = [0] * len(payloads)
        for payload_index, code in zip(payload_order, code_order):
            chosen_codes[payload_index] = code
    else:
        # Scenario 2 is the measured exception: its presentation has no room
        # for a literal title and its shipped dictionary cannot retain every
        # unreferenced row plus that title.  The existing compact plan is
        # runtime-green there, so preserve its exact high-code allocation.
        rows = [b"" for _ in range(DICTIONARY_RECORDS)]
        for code in preserved:
            rows[code - 1] = resource.dictionary_rows[code - 1]
        chosen_codes = available[:len(payloads)]
    assignments: list[tuple[str, int]] = []
    for (record_id, payload), code in zip(payloads, chosen_codes):
        dialogue.need(payload and b"\0" not in payload,
                      f"{record_id}: 로컬 사전 본문 구조 오류")
        dialogue.need(
            not _references(payload),
            f"{record_id}: 로컬 나레이션 사전의 중첩 참조 금지",
        )
        rows[code - 1] = payload
        assignments.append((record_id, code))
    cleared_codes: list[int] = []
    if preserve_all_source_rows:
        assigned = set(chosen_codes)
        reclaimable = sorted(
            (code for code in available if code not in assigned),
            key=lambda code: (-len(resource.dictionary_rows[code - 1]), -code),
        )
        packed_size = sum(len(row) + 1 for row in rows)
        for code in reclaimable:
            if packed_size <= resource.dictionary_allocation:
                break
            old_size = len(rows[code - 1])
            if not old_size:
                continue
            rows[code - 1] = b""
            packed_size -= old_size
            cleared_codes.append(code)
    packed = b"".join(row + b"\0" for row in rows)
    dialogue.need(
        len(packed) <= resource.dictionary_allocation,
        "프레젠테이션 로컬 사전 용량 초과: "
        f"{len(packed)}/{resource.dictionary_allocation}",
    )
    padding = resource.dictionary_allocation - len(packed)
    replacement = packed + bytes(padding)
    dialogue.need(
        len(replacement) == resource.dictionary_allocation,
        "프레젠테이션 로컬 사전 최종 크기 오류",
    )
    # Every authored record owns a distinct code and expands to the exact
    # encoded payload.  No phrase or glyph is borrowed from another record.
    for record_id, code in assignments:
        source = dict(payloads)[record_id]
        dialogue.need(rows[code - 1] == source,
                      f"{record_id}: 로컬 사전 왕복 검증 실패")
    return DictionaryPlan(
        replacement=replacement,
        assignments=tuple(assignments),
        preserved_codes=tuple(sorted(preserved)),
        cleared_codes=tuple(sorted(cleared_codes)),
        packed_bytes=len(packed),
        padding_bytes=padding,
    )
