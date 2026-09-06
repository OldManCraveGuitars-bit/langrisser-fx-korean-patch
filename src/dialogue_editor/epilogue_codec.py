#!/usr/bin/env python3
"""Validated Korean ending-epilogue encoding and dictionary packing.

The game stores 134 NUL-terminated epilogues behind a 241-entry phrase
dictionary.  This module owns the target-side representation only: authored
text never contains dictionary tokens, every new Hangul syllable receives one
private code, and compression is verified by expanding the built rows back to
their literal encoded bytes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import itertools
import json
from pathlib import Path
import re

import dialogue_core as dialogue


DICTIONARY_BYTES = 0x89C
DICTIONARY_RECORDS = 241
TABLE_BYTES = 18360
TABLE_RECORDS = 134
PRIVATE_CODE_COUNT = 4 * 188
TRANSLATIONS = (
    dialogue.ROOT
    / "dialogue_editor/ending_epilogue_translations_successor189.json"
)
SOURCE_CATALOG = dialogue.ROOT / "dialogue_editor/ending_epilogue_source.json"
BUILD_PLAN = dialogue.ROOT / "dialogue_editor/ending_epilogue_build_plan_successor189.json"
TOKEN = re.compile(r"\{(name|raw):([0-9A-Fa-f]{2})\}|\{page\}")
ANY_BRACE = re.compile(r"\{[^{}]*\}")


class EpilogueCodecError(RuntimeError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise EpilogueCodecError(message)


def sha(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_tokens(text: str) -> tuple[str, ...]:
    return tuple(
        match.group(0).lower()
        for match in TOKEN.finditer(text)
        if match.group(1) in ("name", "raw")
    )


def _script_residuals(text: str) -> tuple[str, ...]:
    return tuple(sorted(set(
        character for character in text
        if 0x3040 <= ord(character) <= 0x30FF
        or 0x3400 <= ord(character) <= 0x9FFF
    )))


def load_validated_texts() -> tuple[tuple[str, ...], dict]:
    source = load_json(SOURCE_CATALOG)
    translation = load_json(TRANSLATIONS)
    need(
        source.get("schema") == "langrisser-fx-ending-epilogue-source/v1",
        "ending epilogue source schema",
    )
    need(
        translation.get("schema")
        == "langrisser-fx-ending-epilogue-translations/v1",
        "ending epilogue translation schema",
    )
    source_rows = source.get("records")
    translated = translation.get("records")
    need(isinstance(source_rows, list) and len(source_rows) == TABLE_RECORDS,
         "ending epilogue source denominator")
    need(isinstance(translated, dict) and len(translated) == TABLE_RECORDS,
         "ending epilogue translation denominator")
    texts: list[str] = []
    width_max = 0
    page_total = 0
    for ordinal, source_row in enumerate(source_rows):
        record_id = f"ending-epilogue/{ordinal:03d}"
        need(source_row.get("id") == record_id,
             f"ending epilogue source order {record_id}")
        need(record_id in translated,
             f"missing ending epilogue translation {record_id}")
        source_text = str(source_row["source_text"])
        text = translated[record_id]
        need(isinstance(text, str) and text,
             f"empty ending epilogue translation {record_id}")
        unknown = [
            token for token in ANY_BRACE.findall(text)
            if token != "{page}" and not TOKEN.fullmatch(token)
        ]
        need(not unknown, f"{record_id}: unknown tokens {sorted(set(unknown))}")
        need("{dict:" not in text.lower(),
             f"{record_id}: authored dictionary token is forbidden")
        source_pages = source_text.split("{page}")
        pages = text.split("{page}")
        need(len(pages) == len(source_pages),
             f"{record_id}: page count changed")
        page_total += len(pages)
        need(_source_tokens(text) == _source_tokens(source_text),
             f"{record_id}: dynamic token order changed")
        residuals = _script_residuals(text)
        need(not residuals,
             f"{record_id}: Japanese/CJK residual {', '.join(residuals)}")
        for page_number, page in enumerate(pages, start=1):
            need(page.count("\n") + 1 <= dialogue.MAX_DIALOGUE_LINES_PER_PAGE,
                 f"{record_id}: page {page_number} exceeds four lines")
            for line_number, line in enumerate(page.split("\n"), start=1):
                widths = dialogue.line_widths(line)
                need(widths, f"{record_id}: empty width result")
                width_max = max(width_max, *widths)
                need(all(width <= dialogue.MAX_DIALOGUE_WIDTH_PX for width in widths),
                     f"{record_id}: page {page_number} line {line_number} "
                     f"exceeds {dialogue.MAX_DIALOGUE_WIDTH_PX}px: {widths}")
        texts.append(text)
    need(set(translated) == {
        f"ending-epilogue/{ordinal:03d}" for ordinal in range(TABLE_RECORDS)
    }, "unknown ending epilogue translation IDs")
    return tuple(texts), {
        "records": len(texts),
        "pages": page_total,
        "maximum_line_width_px": width_max,
        "maximum_lines_per_page": dialogue.MAX_DIALOGUE_LINES_PER_PAGE,
        "japanese_or_cjk_residual_records": 0,
        "token_order_preserved": True,
    }


def _private_code_supply() -> tuple[int, ...]:
    return tuple(itertools.islice(
        dialogue.global_atlas.valid_codes(dialogue.global_atlas.PRIVATE_FIRST),
        PRIVATE_CODE_COUNT,
    ))


def _base_mapping_without_early_dialogue_extension() -> dict[str, bytes]:
    """Return the atlas owners that predate the Scenario 3-12 extension.

    The ending epilogue has its own 63 pinned cells.  Successor193 appends a
    separate set of dialogue-only cells after them, and a few characters are
    deliberately present in both contexts.  Do not let the later dialogue
    extension make the older ending assignments look like aliases, or make
    ending text silently start referring to dialogue-owned cells.
    """

    mapping = dict(dialogue.early_private_mapping())
    extension = dialogue.load_json(dialogue.EARLY_DIALOGUE_GLYPH_EXTENSION)
    extension_codes = {
        int(row["code"], 0).to_bytes(2, "big")
        for row in extension["font"]["assignments"]
    }
    result = {
        character: code for character, code in mapping.items()
        if code not in extension_codes
    }
    need(len(mapping) - len(result) == len(extension_codes),
         "early dialogue extension mapping denominator")
    dialogue.need_unique_mapping(result, "엔딩 후일담 기준 문자표")
    return result


def propose_glyph_assignments(texts: tuple[str, ...]) -> tuple[tuple[str, int], ...]:
    mapping = _base_mapping_without_early_dialogue_extension()
    missing: set[str] = set()
    for text in texts:
        cursor = 0
        while cursor < len(text):
            if text[cursor] == "\n":
                cursor += 1
                continue
            match = TOKEN.match(text, cursor)
            if match:
                cursor = match.end()
                continue
            character = text[cursor]
            lookup = "\u2009" if character == " " else character
            if lookup not in mapping:
                try:
                    character.encode("shift_jis")
                except UnicodeEncodeError:
                    missing.add(character)
            cursor += 1
    occupied = {
        int.from_bytes(code, "big") for code in mapping.values()
        if len(code) == 2 and 0xF4 <= code[0] <= 0xF7
    }
    free = [code for code in _private_code_supply() if code not in occupied]
    ordered = sorted(missing)
    need(len(ordered) <= len(free),
         f"ending epilogue private glyph overflow {len(ordered)}/{len(free)}")
    assignments = tuple(zip(ordered, free, strict=False))
    need(len({character for character, _code in assignments}) == len(assignments),
         "ending epilogue glyph character alias")
    need(len({code for _character, code in assignments}) == len(assignments),
         "ending epilogue glyph code alias")
    return assignments


def load_plan() -> dict:
    document = load_json(BUILD_PLAN)
    need(
        document.get("schema")
        == "langrisser-fx-ending-epilogue-build-plan-successor189/v1",
        "ending epilogue build plan schema",
    )
    need(document.get("status") == "adopted",
         "ending epilogue build plan is not adopted")
    need(document["translation"]["sha256"] == sha_file(TRANSLATIONS),
         "ending epilogue translation changed after build-plan adoption")
    return document


def plan_assignments(plan: dict) -> tuple[tuple[str, int], ...]:
    rows = plan["font"]["assignments"]
    assignments = tuple(
        (str(row["character"]), int(row["code"], 0)) for row in rows
    )
    need(len(assignments) == int(plan["font"]["new_characters"]),
         "ending epilogue build-plan glyph denominator")
    need(len({character for character, _code in assignments}) == len(assignments),
         "ending epilogue build-plan character alias")
    need(len({code for _character, code in assignments}) == len(assignments),
         "ending epilogue build-plan code alias")
    return assignments


def encoding_mapping(assignments: tuple[tuple[str, int], ...]) -> dict[str, bytes]:
    mapping = _base_mapping_without_early_dialogue_extension()
    for character, code in assignments:
        need(character not in mapping,
             f"ending epilogue glyph already owned {character!r}")
        value = code.to_bytes(2, "big")
        need(value not in mapping.values(),
             f"ending epilogue glyph code already owned 0x{code:04X}")
        mapping[character] = value
    dialogue.need_unique_mapping(mapping, "엔딩 후일담 확장 문자표")
    need(mapping[" "] != mapping["\u2009"],
         "ending epilogue ordinary/thin space alias")
    return mapping


Unit = tuple[str, bytes]


def literal_units(text: str, mapping: dict[str, bytes]) -> tuple[Unit, ...]:
    units: list[Unit] = []
    cursor = 0
    while cursor < len(text):
        if text[cursor] == "\n":
            units.append(("control", b"\x08"))
            cursor += 1
            continue
        match = TOKEN.match(text, cursor)
        if match:
            kind, raw = match.groups()
            if match.group(0) == "{page}":
                units.append(("control", dialogue.PAGE))
            elif kind == "name":
                units.append(("control", bytes((0x09, int(raw, 16)))))
            else:
                units.append(("control", bytes((int(raw, 16),))))
            cursor = match.end()
            continue
        character = text[cursor]
        lookup = "\u2009" if character == " " else character
        if lookup in mapping:
            encoded = mapping[lookup]
        else:
            try:
                encoded = character.encode("shift_jis")
            except UnicodeEncodeError as exc:
                raise EpilogueCodecError(
                    f"ending epilogue unmapped character {character!r}"
                ) from exc
        need(b"\0" not in encoded, "ending epilogue encoded NUL")
        units.append(("text", encoded))
        cursor += 1
    return tuple(units)


def plan_phrases(plan: dict) -> tuple[tuple[int, str], ...]:
    result = tuple(
        (int(row["code"], 0), str(row["text"]))
        for row in plan["dictionary"]["phrases"]
    )
    need(result and len(result) <= DICTIONARY_RECORDS,
         "ending epilogue phrase denominator")
    need(tuple(code for code, _text in result) == tuple(range(1, len(result) + 1)),
         "ending epilogue phrase codes must be consecutive from one")
    need(len({text for _code, text in result}) == len(result),
         "ending epilogue duplicate phrase")
    return result


@dataclass(frozen=True)
class CompiledEpilogues:
    dictionary_blob: bytes
    table_blob: bytes
    literal_rows: tuple[bytes, ...]
    compressed_rows: tuple[bytes, ...]
    dictionary_rows: tuple[bytes, ...]
    audit: dict


def _replace_phrase(
    rows: list[list[Unit]], phrase: tuple[bytes, ...], code: int
) -> int:
    uses = 0
    length = len(phrase)
    for row_index, row in enumerate(rows):
        rebuilt: list[Unit] = []
        cursor = 0
        while cursor < len(row):
            if (
                cursor + length <= len(row)
                and all(
                    row[cursor + offset][0] == "text"
                    and row[cursor + offset][1] == phrase[offset]
                    for offset in range(length)
                )
            ):
                rebuilt.append(("dictionary", bytes((0x04, code))))
                cursor += length
                uses += 1
            else:
                rebuilt.append(row[cursor])
                cursor += 1
        rows[row_index] = rebuilt
    return uses


def _first_rows(blob: bytes, count: int) -> tuple[tuple[bytes, ...], bytes]:
    rows: list[bytes] = []
    cursor = 0
    for _index in range(count):
        end = blob.find(b"\0", cursor)
        need(end >= 0, "NUL-delimited region ended early")
        rows.append(blob[cursor:end])
        cursor = end + 1
    return tuple(rows), blob[cursor:]


def compile_epilogues(
    texts: tuple[str, ...],
    assignments: tuple[tuple[str, int], ...],
    phrases: tuple[tuple[int, str], ...],
    source_dictionary: bytes,
) -> CompiledEpilogues:
    need(len(texts) == TABLE_RECORDS, "ending epilogue compile denominator")
    need(len(source_dictionary) == DICTIONARY_BYTES,
         "ending epilogue source dictionary extent")
    mapping = encoding_mapping(assignments)
    literal_unit_rows = [list(literal_units(text, mapping)) for text in texts]
    literal_rows = tuple(
        b"".join(encoded for _kind, encoded in row)
        for row in literal_unit_rows
    )
    working = [list(row) for row in literal_unit_rows]
    dictionary_phrases: list[bytes] = []
    phrase_audit: list[dict] = []
    for code, phrase_text in phrases:
        phrase_units = literal_units(phrase_text, mapping)
        need(phrase_units and all(kind == "text" for kind, _data in phrase_units),
             f"dictionary phrase crosses a control boundary: {phrase_text!r}")
        phrase = tuple(data for _kind, data in phrase_units)
        encoded = b"".join(phrase)
        need(b"\0" not in encoded and b"\x04" not in encoded,
             f"dictionary phrase contains reserved byte: {phrase_text!r}")
        uses = _replace_phrase(working, phrase, code)
        need(uses >= 2, f"dictionary phrase is not repeated: {phrase_text!r}")
        dictionary_phrases.append(encoded)
        phrase_audit.append({
            "code": f"0x{code:02X}",
            "text": phrase_text,
            "encoded_hex": encoded.hex().upper(),
            "encoded_bytes": len(encoded),
            "uses": uses,
            "table_bytes_saved": uses * (len(encoded) - 2),
        })
    compressed_rows = tuple(
        b"".join(encoded for _kind, encoded in row) for row in working
    )
    for ordinal, (literal, compressed) in enumerate(
        zip(literal_rows, compressed_rows, strict=True)
    ):
        expanded = bytearray()
        cursor = 0
        while cursor < len(compressed):
            if compressed[cursor] == 0x04:
                need(cursor + 1 < len(compressed),
                     f"ending epilogue {ordinal}: truncated dictionary token")
                code = compressed[cursor + 1]
                need(1 <= code <= len(dictionary_phrases),
                     f"ending epilogue {ordinal}: unknown dictionary code {code}")
                expanded.extend(dictionary_phrases[code - 1])
                cursor += 2
            else:
                expanded.append(compressed[cursor])
                cursor += 1
        need(bytes(expanded) == literal,
             f"ending epilogue {ordinal}: dictionary round trip")
    source_rows, source_tail = _first_rows(
        source_dictionary, DICTIONARY_RECORDS
    )
    need(not any(source_tail),
         "source ending dictionary has nonzero trailing bytes")
    dictionary_rows = tuple(dictionary_phrases) + source_rows[len(dictionary_phrases):]
    need(len(dictionary_rows) == DICTIONARY_RECORDS,
         "target ending dictionary row count")
    packed_dictionary = b"".join(row + b"\0" for row in dictionary_rows)
    need(len(packed_dictionary) <= DICTIONARY_BYTES,
         f"target ending dictionary overflow {len(packed_dictionary)}/{DICTIONARY_BYTES}")
    dictionary_padding = DICTIONARY_BYTES - len(packed_dictionary)
    dictionary_blob = packed_dictionary + bytes(dictionary_padding)
    packed_table = b"".join(row + b"\0" for row in compressed_rows)
    need(len(packed_table) <= TABLE_BYTES,
         f"target ending table overflow {len(packed_table)}/{TABLE_BYTES}")
    table_padding = TABLE_BYTES - len(packed_table)
    table_blob = packed_table + bytes(table_padding)
    parsed_rows, trailing = _first_rows(table_blob, TABLE_RECORDS)
    need(parsed_rows == compressed_rows, "target ending table row parse")
    need(not any(trailing), "target ending table trailing padding is not zero")
    need(len(dictionary_blob) == DICTIONARY_BYTES,
         "target ending dictionary final extent")
    need(len(table_blob) == TABLE_BYTES, "target ending table final extent")
    literal_bytes = sum(len(row) + 1 for row in literal_rows)
    compressed_bytes = sum(len(row) + 1 for row in compressed_rows)
    return CompiledEpilogues(
        dictionary_blob=dictionary_blob,
        table_blob=table_blob,
        literal_rows=literal_rows,
        compressed_rows=compressed_rows,
        dictionary_rows=dictionary_rows,
        audit={
            "records": len(compressed_rows),
            "literal_table_bytes": literal_bytes,
            "compressed_table_bytes": compressed_bytes,
            "table_capacity_bytes": TABLE_BYTES,
            "table_padding_bytes": table_padding,
            "table_bytes_saved": literal_bytes - compressed_bytes,
            "dictionary_rows": len(dictionary_rows),
            "dictionary_packed_bytes": len(packed_dictionary),
            "dictionary_capacity_bytes": DICTIONARY_BYTES,
            "dictionary_padding_bytes": dictionary_padding,
            "dictionary_roundtrip_records": TABLE_RECORDS,
            "phrases": phrase_audit,
            "glyph_aliases": 0,
        },
    )
