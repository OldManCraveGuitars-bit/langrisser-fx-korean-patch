#!/usr/bin/env python3
"""True ending-character epilogues replicated by the five ending resources."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import re

import dialogue_core as dialogue
import epilogue_codec as codec


DICTIONARY_BYTES = codec.DICTIONARY_BYTES
DICTIONARY_OFFSETS = (
    0x003DE24C,
    0x003E53D4,
    0x003EDADC,
    0x003F62A4,
    0x003FD2A4,
)
DICTIONARY_SHA256 = (
    "12C2CDFF6F92BB7131E13527A79BA594EC1146289BE9AFFD3E5A622AC5839824"
)
TABLE_OFFSETS = (0x003DEAE8, 0x003E5F54, 0x003EE378, 0x003F6BB0, 0x003FDB40)
TABLE_BYTES = 18360
TABLE_RECORDS = 134
TABLE_SHA256 = "400286339082930934FC6336F1342F4D8DDD7048C87270CE1036610AC0AD7CE4"
SOURCE_CATALOG = dialogue.ROOT / "dialogue_editor/ending_epilogue_source.json"
TOKEN = re.compile(r"\{(name|raw|dict):([0-9A-Fa-f]{2})\}")
ANY_BRACE = re.compile(r"\{[^{}]*\}")


@dataclass(frozen=True)
class EpilogueRecord:
    id: str
    ordinal: int
    source_text: str
    base_text: str
    relative_offset: int
    allocation: int
    base_encoded: bytes


def epilogue_mapping() -> dict[str, bytes]:
    # Successor189 extends the immutable F4-F7 atlas with 63 ending-only
    # cells.  The adopted build plan is the authority for those assignments;
    # no edit may allocate another code or alias an existing glyph.
    plan = codec.load_plan()
    mapping = codec.encoding_mapping(codec.plan_assignments(plan))
    dialogue.need_unique_mapping(mapping, "엔딩 후일담 문자표")
    dialogue.need(mapping[" "] != mapping["\u2009"],
                  "엔딩 후일담 공백 글리프 중복")
    return mapping


def _split_table(blob: bytes) -> list[tuple[int, bytes]]:
    dialogue.need(len(blob) == TABLE_BYTES, "엔딩 후일담 표 크기 오류")
    rows: list[tuple[int, bytes]] = []
    cursor = 0
    for _ordinal in range(TABLE_RECORDS):
        end = blob.find(b"\0", cursor)
        dialogue.need(end >= 0, "엔딩 후일담 NUL 종단 없음")
        rows.append((cursor, blob[cursor:end + 1]))
        cursor = end + 1
    dialogue.need(not any(blob[cursor:]), "엔딩 후일담 후미 패딩 변경")
    dialogue.need(len(rows) == TABLE_RECORDS, "엔딩 후일담 레코드 수 변경")
    return rows


def _render_raw(raw: bytes) -> str:
    output: list[str] = []
    run = bytearray()

    def flush() -> None:
        if run:
            output.append(bytes(run).decode("shift_jis"))
            run.clear()

    index = 0
    while index < len(raw):
        value = raw[index]
        if value == 0x08:
            flush()
            output.append("\n")
            index += 1
        elif raw[index:index + 2] == dialogue.PAGE:
            flush()
            output.append("{page}")
            index += 2
        elif value == 0x04 and index + 1 < len(raw):
            flush()
            output.append(f"{{dict:{raw[index + 1]:02X}}}")
            index += 2
        elif value == 0x09 and index + 1 < len(raw):
            flush()
            output.append(f"{{name:{raw[index + 1]:02X}}}")
            index += 2
        elif value < 0x20:
            flush()
            output.append(f"{{raw:{value:02X}}}")
            index += 1
        else:
            run.append(value)
            index += 1
    flush()
    return "".join(output)


@lru_cache(maxsize=1)
def load_epilogue_records() -> tuple[EpilogueRecord, ...]:
    image = (dialogue.BASE_DIR / dialogue.BASE_COOKED_NAME).read_bytes()
    dictionaries = [
        image[offset:offset + DICTIONARY_BYTES]
        for offset in DICTIONARY_OFFSETS
    ]
    dialogue.need(all(len(blob) == DICTIONARY_BYTES for blob in dictionaries),
                  "엔딩 후일담 사전 복제 범위 초과")
    dialogue.need(len(set(dictionaries)) == 1,
                  "다섯 엔딩 후일담 사전이 서로 다릅니다.")
    dialogue.need(
        hashlib.sha256(dictionaries[0]).hexdigest().upper()
        == DICTIONARY_SHA256,
        "엔딩 후일담 기준 사전 해시 변경",
    )
    copies = [image[offset:offset + TABLE_BYTES] for offset in TABLE_OFFSETS]
    dialogue.need(all(len(blob) == TABLE_BYTES for blob in copies),
                  "엔딩 후일담 복제 표 범위 초과")
    dialogue.need(len(set(copies)) == 1,
                  "다섯 엔딩 후일담 복제 표가 서로 다릅니다.")
    dialogue.need(hashlib.sha256(copies[0]).hexdigest().upper() == TABLE_SHA256,
                  "엔딩 후일담 기준 해시 변경")
    rows = _split_table(copies[0])
    translated_texts, translated_audit = codec.load_validated_texts()
    dialogue.need(translated_audit["records"] == TABLE_RECORDS,
                  "엔딩 후일담 한글 문안 수 변경")
    source_document = dialogue.load_json(SOURCE_CATALOG)
    dialogue.need(
        source_document.get("schema")
        == "langrisser-fx-ending-epilogue-source/v1",
        "엔딩 후일담 원문 자료 형식 오류",
    )
    source_rows = source_document.get("records", [])
    dialogue.need(len(source_rows) == TABLE_RECORDS,
                  "엔딩 후일담 원문 레코드 수 변경")
    records: list[EpilogueRecord] = []
    for ordinal, (relative_offset, raw) in enumerate(rows):
        source_row = source_rows[ordinal]
        dialogue.need(source_row.get("id") == f"ending-epilogue/{ordinal:03d}",
                      "엔딩 후일담 원문 ID 순서 변경")
        source = str(source_row["source_text"])
        records.append(EpilogueRecord(
            id=f"ending-epilogue/{ordinal:03d}",
            ordinal=ordinal,
            source_text=source,
            base_text=translated_texts[ordinal],
            relative_offset=relative_offset,
            allocation=len(raw),
            base_encoded=raw[:-1],
        ))
    dialogue.need(len({row.id for row in records}) == TABLE_RECORDS,
                  "엔딩 후일담 ID 중복")
    return tuple(records)


def _script_residuals(text: str) -> list[str]:
    return sorted(set(
        character for character in text
        if 0x3040 <= ord(character) <= 0x30FF
        or 0x3400 <= ord(character) <= 0x9FFF
    ))


def _encode(text: str) -> bytes:
    try:
        return b"".join(
            encoded for _kind, encoded in codec.literal_units(
                text, epilogue_mapping()
            )
        )
    except codec.EpilogueCodecError as exc:
        raise dialogue.DialogueError(str(exc)) from exc


def _tokens(text: str, kinds: tuple[str, ...]) -> Counter[str]:
    return Counter(
        match.group(0).lower() for match in TOKEN.finditer(text)
        if match.group(1) in kinds
    )


def validate_epilogue_text(record: EpilogueRecord, text: str) -> bytes:
    unknown = [token for token in ANY_BRACE.findall(text)
               if token != "{page}" and not codec.TOKEN.fullmatch(token)]
    dialogue.need(not unknown,
                  f"{record.id}: 알 수 없는 토큰 {sorted(set(unknown))}")
    dialogue.need("{dict:" not in text.lower(),
                  f"{record.id}: 사전 코드를 직접 재사용할 수 없습니다.")
    pages = text.split("{page}")
    dialogue.need(len(pages) == len(record.source_text.split("{page}")),
                  f"{record.id}: 원문 페이지 수를 보존해야 합니다.")
    excessive = [index + 1 for index, page in enumerate(pages)
                 if page.count("\n") + 1 > dialogue.MAX_DIALOGUE_LINES_PER_PAGE]
    dialogue.need(not excessive,
                  f"{record.id}: 화면당 최대 4줄입니다. 페이지 {excessive}")
    widths = [width for page in pages for line in page.split("\n")
              for width in dialogue.line_widths(line)]
    dialogue.need(all(width <= dialogue.MAX_DIALOGUE_WIDTH_PX for width in widths),
                  f"{record.id}: 줄 폭 204px 초과 {widths}")
    residuals = _script_residuals(text)
    dialogue.need(not residuals,
                  f"{record.id}: 일본어·한자 잔존 {', '.join(residuals)}")
    dialogue.need(
        _tokens(text, ("name", "raw"))
        == _tokens(record.source_text, ("name", "raw")),
        f"{record.id}: 동적 이름·주인공 토큰을 보존해야 합니다.",
    )
    encoded = _encode(text)
    dialogue.need(b"\0" not in encoded, f"{record.id}: NUL 구조 침범")
    return encoded


def validate_epilogue_project(edits: dict[str, str]) -> None:
    records = load_epilogue_records()
    by_id = {row.id: row for row in records}
    dialogue.need(not (set(edits) - set(by_id)), "알 수 없는 엔딩 후일담 ID")
    for record_id, text in edits.items():
        validate_epilogue_text(by_id[record_id], text)
    texts = tuple(edits.get(row.id, row.base_text) for row in records)
    image = (dialogue.BASE_DIR / dialogue.BASE_COOKED_NAME).read_bytes()
    source_dictionary = image[
        DICTIONARY_OFFSETS[0]:DICTIONARY_OFFSETS[0] + DICTIONARY_BYTES
    ]
    plan = codec.load_plan()
    try:
        codec.compile_epilogues(
            texts,
            codec.plan_assignments(plan),
            codec.plan_phrases(plan),
            source_dictionary,
        )
    except codec.EpilogueCodecError as exc:
        raise dialogue.DialogueError(str(exc)) from exc


def build_epilogue_patches(
    image: bytes | bytearray,
    edits: dict[str, str],
) -> tuple[tuple[tuple[int, bytes, str], ...], dict]:
    validate_epilogue_project(edits)
    records = load_epilogue_records()
    texts = tuple(edits.get(row.id, row.base_text) for row in records)
    source_dictionary = bytes(image[
        DICTIONARY_OFFSETS[0]:DICTIONARY_OFFSETS[0] + DICTIONARY_BYTES
    ])
    plan = codec.load_plan()
    try:
        compiled = codec.compile_epilogues(
            texts,
            codec.plan_assignments(plan),
            codec.plan_phrases(plan),
            source_dictionary,
        )
    except codec.EpilogueCodecError as exc:
        raise dialogue.DialogueError(str(exc)) from exc
    patches: list[tuple[int, bytes, str]] = []
    dictionary_patches = 0
    table_patches = 0
    for copy_index, dictionary_offset in enumerate(
        DICTIONARY_OFFSETS, start=1
    ):
        before = bytes(image[
            dictionary_offset:dictionary_offset + DICTIONARY_BYTES
        ])
        dialogue.need(len(before) == DICTIONARY_BYTES,
                      "엔딩 후일담 사전 이미지 범위 초과")
        if before != compiled.dictionary_blob:
            patches.append((
                dictionary_offset,
                compiled.dictionary_blob,
                f"ending-epilogues/dictionary-{copy_index}",
            ))
            dictionary_patches += 1
    for copy_index, table_offset in enumerate(TABLE_OFFSETS, start=1):
        before = bytes(image[table_offset:table_offset + TABLE_BYTES])
        dialogue.need(len(before) == TABLE_BYTES,
                      "엔딩 후일담 표 이미지 범위 초과")
        if before != compiled.table_blob:
            patches.append((
                table_offset,
                compiled.table_blob,
                f"ending-epilogues/table-{copy_index}",
            ))
            table_patches += 1
    return tuple(patches), {
        **compiled.audit,
        "logical_records": TABLE_RECORDS,
        "edited_records": len(edits),
        "physical_dictionaries": len(DICTIONARY_OFFSETS),
        "physical_tables": len(TABLE_OFFSETS),
        "physical_patches": len(patches),
        "dictionary_patches": dictionary_patches,
        "table_patches": table_patches,
        "dictionary_sha256": DICTIONARY_SHA256,
        "table_sha256": TABLE_SHA256,
        "glyph_aliases": 0,
        "space_owners_distinct": True,
    }
