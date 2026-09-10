#!/usr/bin/env python3
"""Safe data/model and disc builder for the Langrisser FX dialogue editor.

The editor is tied to the cumulative successor190 image.  It
never edits that image in place; every build is written to a new directory
and receives a static-QA report.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import cd_mode1  # noqa: E402
from audit_patched_scenario_presentations import line_widths  # noqa: E402
from build_scenario02_overlay_dialogue_candidate import (  # noqa: E402
    decode_candidate,
    encode_compressed,
    encode_direct,
)
import inventory_r76_scenario01_dialogue_polish as s1inv  # noqa: E402
from build_r76_scenario01_dialogue_polish_component import (  # noqa: E402
    dictionary_texts as s1_dictionary_texts,
)
import build_r80_global_text_atlas_items_successor45 as global_atlas  # noqa: E402
import reference_glyph_repairs  # noqa: E402
from native_glyphs import native_phrase_resources, with_native_ascii  # noqa: E402


BASE_STEM = "r80-successor189-s12-condition-repair-successor190"
BASE_DIR = ROOT / "work" / BASE_STEM
BASE_COOKED_NAME = f"track02-{BASE_STEM}.iso"
BASE_RAW_NAME = f"Track-2.{BASE_STEM}.bin"
BASE_CUE_NAME = f"Langrisser-FX-KR-{BASE_STEM}.cue"
BASE_HASHES = {
    BASE_COOKED_NAME: "3F61AA060AB8F2FF2F866F7F0FC6EA7ACBE9DDD5957F4CEC4D54D81EADD1318E",
    BASE_RAW_NAME: "C0B81ADD92EDC1407B86B5A4716A37FD69139E316F373BF4240259D577E40185",
    BASE_CUE_NAME: "38D4F96FD2DD71408E8D08604F0D3B15397AD238DB8B4A8B31CB908BBF50DA6A",
}
DIALOGUE_RESIDENT_CHARSET = (
    ROOT / "analysis/hangul_charset_v342-r77-faction-unit-description-nul-safe.json"
)
LEGACY_CHARSET = ROOT / "analysis/hangul_charset_v342-r40-scenario03.json"
GLOBAL_PRESENTATION_REPORT = (
    ROOT / "analysis/r80-global-presentations03-12-successor47-build-20260829.json"
)
GLOBAL_ATLAS_REPORT = (
    ROOT / "analysis/r80-global-text-atlas-items-successor45-build-20260829.json"
)
GLOBAL_DIALOGUE_REPORT = (
    ROOT / "analysis/r80-global-dialogue03-12-successor46-build-20260829.json"
)
S1_INVENTORY = ROOT / "analysis/r76-scenario01-dialogue-inventory.json"
S2_LAYOUT = ROOT / "analysis/scenario02_overlay_dialogue_candidate_r37_r36safe.json"
S2_SOURCE = ROOT / "analysis/scenario02_dialogue_source_original.json"
S2_CURRENT_REPORT = (
    ROOT /
    "analysis/r80-scenario02-noalias-dialogue-conditions-successor158-"
    "build-20260901.json"
)
S2_PAGE_VOICE_FIXES = (
    ROOT / "dialogue_editor/scenario02_page_voice_parity_successor178.json"
)
S2_CHARSET = (
    ROOT / "analysis/hangul_charset_v342-scenario02-successor158-noalias.json"
)
S2_DIALOGUE_NARRATION_PHRASE_EXTENSION = (
    ROOT
    / "dialogue_editor/scenario02_dialogue_narration_phrase_extension_name_particles_20260904.json"
)
EARLY_FAITHFUL_ADOPTIONS = (
    ROOT
    / "dialogue_editor/dialogue_faithful_adoptions_scenarios03_12_successor193.json"
)
EARLY_DIALOGUE_GLYPH_EXTENSION = (
    ROOT / "dialogue_editor/early_dialogue_glyph_extension_successor193.json"
)
EARLY_DIALOGUE_PHRASE_EXTENSION = (
    ROOT / "dialogue_editor/early_dialogue_phrase_extension_successor193.json"
)
ALL_FAITHFUL_ADOPTIONS = (
    ROOT / "dialogue_editor/dialogue_faithful_adoptions_all_successor199.json"
)
DIALOGUE_LAYOUT_REFLOW = (
    ROOT / "dialogue_editor/dialogue_layout_reflow_successor240.json"
)
DIALOGUE_LAYOUT_MANUAL_CORRECTIONS = (
    ROOT
    / "dialogue_editor/dialogue_layout_manual_corrections_successor243.json"
)
DIALOGUE_LAYOUT_READABLE_PAGE_PARITY = (
    ROOT
    / "dialogue_editor/dialogue_layout_readable_page_parity_successor244.json"
)
GLOBAL_DIALOGUE_GLYPH_EXTENSION = (
    ROOT / "dialogue_editor/global_text_glyph_extension_successor200.json"
)
SCENARIO_DIALOGUE_PHRASE_EXTENSIONS = (
    ROOT / "dialogue_editor/scenario_dialogue_phrase_extensions_successor207.json"
)
SCENARIO01_DIALOGUE_PHRASE_EXTENSION = (
    ROOT / "dialogue_editor/scenario01_dialogue_phrase_extension_successor200.json"
)
EARLY_SCENARIO_DIALOGUE_PHRASE_EXTENSIONS = (
    ROOT / "dialogue_editor/early_scenario_dialogue_phrase_extensions_successor207.json"
)
MENU_CONDITION_CATALOG = (
    ROOT / "analysis/r80-battle-menu-condition-catalog-successor168.json"
)

COOKED_SECTOR = 2048
RAW_SECTOR = 2352
RAW_USER = 16
RAW_LEADIN = 225
SPACE_VISIBLE = bytes.fromhex("F1E8")
PAGE = b"\x06\x07"
MAX_DIALOGUE_WIDTH_PX = 204
# Runtime edge probes show that 172px already clips the final glyph while
# 168px is stable.  The first portrait screen also has only three body rows
# because its first row is owned by the speaker name; visual continuations
# and native voice pages have four body rows.
MAX_DIALOGUE_SAFE_VISIBLE_WIDTH_PX = 168
FIRST_DIALOGUE_BODY_LINES = 3
MAX_DIALOGUE_LINES_PER_PAGE = 4
# Scenario 1 stores the three true in-battle victory/defeat rows immediately
# before its presentation aggregate.  The historical dialogue inventory
# exposed those NUL records as ordinary dialogue, but raw 05 and their native
# route identify the 22-tile condition window as their consumer.  They must
# never receive portrait pages or the portrait 192 px policy.
SCENARIO01_MENU_CONDITION_IDS = frozenset({
    "scenario01/dialogue/187",
    "scenario01/dialogue/188",
    "scenario01/dialogue/189",
})
SCENARIO01_MENU_CONDITION_TEXT = {
    "scenario01/dialogue/187": "{raw:05}・{raw:02} 사망",
    "scenario01/dialogue/188": "{raw:05}・{name:18} 격파",
    "scenario01/dialogue/189": "{raw:05}・{name:18} 아래로 도망",
}
MENU_CONDITION_MAX_WIDTH_PX = 22 * 8
UL_CODE = bytes.fromhex("F272")
UL_GLYPH_COOKED = 0x0004F1FA
UL_GLYPH_ASSET = ROOT / "assets/glyphs/private-f272-shop-complete-unifont-uc6b8-12x12.bin"
POOL_FAMILIES = frozenset(
    ("scenario01-prefix", "scenario03-12-fixed", "scenario13-70-fixed")
)
# Keep the existing literal encoding for this event, but NOT fixed slots.
# The exact user SRAM on successor219 exposed empty bodies beginning at
# ordinal 046: padding between independently pinned slots inserted native
# NUL records.  All 229 Scenario-3 dialogue records share one ordinal pool.
# Literal encoding alone does not establish dictionary-residency behavior.
SUSPEND_RESUME_LITERAL_DIALOGUE_IDS = frozenset(
    f"scenario03/dialogue/{index:03d}" for index in range(46, 52)
)
TOKEN = re.compile(
    r"\{(name|raw|dict):([0-9A-Fa-f]{2})\}|\{page\}|\{visual\}"
)
ANY_BRACE = re.compile(r"\{[^{}]*\}")
VERSION = re.compile(r"_v(\d+)")
NAME_PARTICLE_REPLACEMENTS = (
    ("{name:04}가", "{name:04}이"),
    ("{name:01}을", "{name:01}를"),
    ("{name:13}을", "{name:13}를"),
    ("{name:0C}와", "{name:0C}과"),
    ("{name:07}가", "{name:07}이"),
)

S2_DICT_START, S2_DICT_END, S2_DICT_RECORDS = 0x13A0B0, 0x13A94C, 239
S2_DIALOGUE_START, S2_DIALOGUE_END, S2_DIALOGUE_RECORDS = (
    0x13A94C,
    # 0x13C33A begins Scenario 2's separately addressed condition container
    # (20 00 04 1C).  Historical dialogue metadata overclaimed those four
    # bytes through 0x13C33E; dialogue must stop at the actual owner boundary.
    0x13C33A,
    174,
)
S2_CONDITION_EXCLUSIVE_CODES = frozenset(
    (0x01, 0x02, 0x0B, 0x1C, 0x1D, 0x36)
)
S2_RELOCATED_DIALOGUE_PHRASE = "한 저로서"
S2_RELOCATED_DIALOGUE_CODE = 0x07


class DialogueError(RuntimeError):
    pass


@dataclass(frozen=True)
class DialogueRecord:
    id: str
    scenario: int
    source_text: str
    base_text: str
    cooked_offset: int | None
    allocation: int
    active_budget: int
    family: str
    # Text physically present on BASE_STEM. ``base_text`` is the reviewed
    # editor default and may be a newly adopted faithful translation.
    disc_text: str | None = None


@dataclass(frozen=True)
class Validation:
    ok: bool
    encoded_bytes: int
    capacity: int
    max_line_width_px: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def need(condition: bool, message: str) -> None:
    if not condition:
        raise DialogueError(message)


def need_unique_mapping(mapping: dict[str, bytes], label: str) -> None:
    """Require one character owner per emitted glyph code, with no aliases."""
    owners: dict[bytes, list[str]] = {}
    for character, code in mapping.items():
        owners.setdefault(code, []).append(character)
    duplicates = {
        code.hex().upper(): characters
        for code, characters in owners.items()
        if len(characters) != 1
    }
    need(not duplicates, f"{label} 글리프 코드 중복 소유: {duplicates}")


def installed_text(record: DialogueRecord) -> str:
    return record.disc_text if record.disc_text is not None else record.base_text


def apply_name_particle_policy(records: Iterable[DialogueRecord]) -> list[DialogueRecord]:
    """Apply the user's fixed-name particle choices to every active record."""
    result = []
    for row in records:
        text = row.base_text
        for before, after in NAME_PARTICLE_REPLACEMENTS:
            text = text.replace(before, after)
        result.append(row if text == row.base_text else replace(row, base_text=text))
    return result


def apply_scenario01_condition_policy(
    records: Iterable[DialogueRecord],
) -> list[DialogueRecord]:
    """Keep Scenario 1's fixed-address battle rows complete and aligned."""
    return [
        replace(row, base_text=SCENARIO01_MENU_CONDITION_TEXT[row.id])
        if row.id in SCENARIO01_MENU_CONDITION_TEXT else row
        for row in records
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(16 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def version_key(path: Path) -> tuple[int, str]:
    match = VERSION.search(path.stem)
    return (int(match.group(1)) if match else -1, path.name)


@lru_cache(maxsize=1)
def menu_condition_owned_ranges() -> dict[int, tuple[int, int]]:
    """Return the immutable system-menu condition extents by scenario.

    A handful of the historical dialogue extracts let their final record run
    two to fifteen bytes into the following condition table.  Scenario 60
    additionally exposed six condition-table rows as if they were dialogue.
    Those bytes have one owner: the condition compiler.  Keeping the ranges in
    the dialogue model prevents pool zero-fill or ordinary edits from erasing
    the victory heading and other menu-condition rows.
    """

    document = load_json(MENU_CONDITION_CATALOG)
    need(
        document.get("schema")
        == "langrisser-fx-r80-battle-menu-condition-catalog-successor168/v1",
        "시스템 메뉴 승패조건 소유 범위 자료 형식이 다릅니다.",
    )
    result = {
        int(row["scenario"]): (
            int(row["offset"], 0),
            int(row["offset"], 0) + int(row["allocation"]),
        )
        for row in document["scenarios"]
    }
    need(set(result) == set(range(3, 71)),
         "시스템 메뉴 승패조건 소유 범위가 불완전합니다.")
    return result


def overlaps_menu_condition(record: DialogueRecord) -> bool:
    if record.cooked_offset is None:
        return False
    owned = menu_condition_owned_ranges().get(record.scenario)
    if owned is None:
        return False
    start, end = owned
    record_end = record.cooked_offset + record.allocation
    return record.cooked_offset < end and start < record_end


def starts_in_menu_condition(record: DialogueRecord) -> bool:
    if record.cooked_offset is None:
        return False
    owned = menu_condition_owned_ranges().get(record.scenario)
    return bool(
        owned is not None
        and owned[0] <= record.cooked_offset < owned[1]
    )


def ui_text(text: str) -> str:
    return (
        text.replace("\u2009", " ")
        .replace("\f", "{page}")
        .replace("{raw:0A}", "{visual}")
        .replace("{raw:0a}", "{visual}")
        .replace("{name:00}", "{raw:02}")
    )


def engine_text(text: str) -> str:
    # U+00B7 is used by two legacy Korean dialogue rows as a visual middle
    # dot.  CP932 owns the same native glyph at U+30FB (81 45); normalise only
    # for encoding so the editor-facing translation remains unchanged and no
    # private Hangul cell is aliased or consumed for punctuation.
    return (
        text.replace("{page}", "\f")
        .replace("{visual}", "{raw:0A}")
        .replace("\u00b7", "\u30fb")
    )


def token_multiset(text: str) -> Counter[str]:
    return Counter(
        match.group(0).lower()
        for match in TOKEN.finditer(text)
        if match.group(0).lower() not in ("{page}", "{visual}")
    )


def token_kind_multiset(text: str, kind: str) -> Counter[str]:
    """Return only one kind of structured token from a decoded dialogue."""
    prefix = "{" + kind.lower() + ":"
    return Counter({
        token: count
        for token, count in token_multiset(text).items()
        if token.startswith(prefix)
    })


def page_line_counts(text: str) -> tuple[int, ...]:
    """Return the number of visible rows on every dialogue page."""
    pages = re.split(r"\{page\}|\{visual\}", ui_text(text))
    return tuple(page.count("\n") + 1 for page in pages)


@lru_cache(maxsize=None)
def portrait_name_metrics(number: int):
    """Return exact installed cursor/right extent for one native 09 name."""
    import dialogue_layout_model as layout
    from native_name_widths import installed_names, name_width_px

    name_width_px(number)  # Fail closed on unknown IDs.
    raw = installed_names()[number][1][:-1]
    size = layout.Metrics(0, 0)
    for cursor in range(0, len(raw), 2):
        code = raw[cursor:cursor + 2]
        item = (
            layout.Metrics(4, 0) if code == SPACE_VISIBLE
            else layout.Metrics(8, 0) if code == b"\xF1\xE6"
            else layout.Metrics(12, 12)
        )
        size = size.then(item)
    need(size.advance == name_width_px(number),
         f"이름 {number:02X} 실제 폭 자료가 다릅니다.")
    return size


def portrait_layout_inspection(text: str) -> dict:
    """Inspect the exact runtime-proven ordinary portrait geometry."""
    import dialogue_layout_model as layout

    return layout.inspect(
        ui_text(text),
        portrait_name_metrics,
        {"{raw:02}": layout.Metrics(28, 28)},
        layout.Profile(
            width=MAX_DIALOGUE_SAFE_VISIBLE_WIDTH_PX,
            first_lines=FIRST_DIALOGUE_BODY_LINES,
            later_lines=MAX_DIALOGUE_LINES_PER_PAGE,
        ),
    )


def is_portrait_dialogue(record: DialogueRecord) -> bool:
    """Return whether the record is consumed by the ordinary portrait box."""
    return record.id not in SCENARIO01_MENU_CONDITION_IDS


def scenario01_menu_condition_line_widths(text: str) -> list[int]:
    """Measure the three Scenario-1 condition rows in their true consumer.

    Native raw 05 becomes the resident 4 px indent.  Raw 02 is the current
    supplied, unrenamed Elwin path with the same conservative 36 px reserve
    used by the complete condition editor.  Dynamic 09 names use their
    installed native widths; no unknown control is assigned a guessed width.
    """
    from native_name_widths import name_width_px

    widths: list[int] = []
    for line in engine_text(text).replace("\f", "").split("\n"):
        width = 0
        cursor = 0
        while cursor < len(line):
            match = TOKEN.match(line, cursor)
            if match:
                token = match.group(0).lower()
                if token == "{page}":
                    raise DialogueError("1화 전투 조건 문구에 페이지 토큰을 넣을 수 없습니다.")
                kind, raw_value = match.group(1), match.group(2)
                value = int(raw_value, 16)
                if kind == "name":
                    try:
                        width += name_width_px(value)
                    except ValueError as exc:
                        raise DialogueError(str(exc)) from exc
                elif kind == "raw" and value in (0x02, 0x05, 0x20):
                    width += {0x02: 36, 0x05: 4, 0x20: 8}[value]
                else:
                    raise DialogueError(
                        f"1화 전투 조건 폭을 계산할 수 없는 토큰 {match.group(0)}"
                    )
                cursor = match.end()
                continue
            character = line[cursor]
            width += 4 if character in (" ", "\u2009", "\u3000") else 12
            cursor += 1
        widths.append(width)
    return widths


def _record_source_text(row: dict) -> str:
    value = row.get("expanded_text") or row.get("source_text") or ""
    return ui_text(value.replace("{end}", "").replace("{br}", "\n"))


def _merge_translation_files(paths: Iterable[Path], prefix: str) -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in sorted(paths, key=version_key):
        document = load_json(path)
        if isinstance(document, dict) and isinstance(document.get("records"), dict):
            document = document["records"]
        if not isinstance(document, dict):
            continue
        for record_id, text in document.items():
            if isinstance(text, str) and record_id.startswith(prefix):
                merged[record_id] = ui_text(text)
    return merged


EARLY = {
    3: ("r40", "scenario03_dictionary_compression_plan_r40.json"),
    4: ("r41", "scenario04_dictionary_compression_plan_r51.json"),
    5: ("r42", "scenario05_dictionary_partial_r53.json"),
    6: ("r43", "scenario06_dictionary_partial_r52b.json"),
    7: ("r48", "scenario07_dictionary_partial_r53.json"),
    8: ("r44", "scenario08_dictionary_partial_r52b.json"),
    9: ("r49", "scenario09_dictionary_partial_r52b.json"),
    10: ("r45", "scenario10_dictionary_partial_r52b.json"),
    11: ("r46", "scenario11_dictionary_partial_r53.json"),
    12: ("r47", "scenario12_dictionary_partial_r52b.json"),
}


def load_records(
    *,
    apply_all_faithful: bool = True,
    apply_layout_reflow: bool = True,
) -> list[DialogueRecord]:
    records: list[DialogueRecord] = []

    # Scenario 1 has one external NUL immediately after each original record
    # allocation.  R76 merely changed some trailing full-width blank padding
    # *inside* those allocations to zero bytes; it did not place another asset
    # there.  The editor may therefore restore and use the complete Japanese
    # record allocation instead of inheriting the shortened R76 prefix.
    inventory = load_json(S1_INVENTORY)
    for ordinal, row in enumerate(inventory["dialogue"]):
        if row["record_id"] == "block0/01303":
            # This is the title/narration aggregate, not ordinary dialogue.
            continue
        records.append(
            DialogueRecord(
                id=f"scenario01/dialogue/{ordinal:03d}",
                scenario=1,
                source_text=ui_text(row.get("jp_original") or ""),
                base_text=ui_text(row["current_korean"]),
                cooked_offset=int(row["cooked_offset"], 0),
                # The catalogue allocation excludes the external NUL.  Keep
                # that byte in the storage span so Scenario 1 can use the
                # same proven contiguous-record pooling model as the later
                # scenarios without moving the aggregate presentation block.
                allocation=int(row["allocation_bytes"]) + 1,
                active_budget=int(row["allocation_bytes"]),
                family="scenario01-prefix",
            )
        )

    # Scenario 2 is an addressable packed stream with a local dictionary.
    s2_layout = load_json(S2_LAYOUT)
    s2_source = load_json(S2_SOURCE)
    s2_current = load_json(S2_CURRENT_REPORT)
    s2_sources = {row["id"]: _record_source_text(row) for row in s2_source["dialogue"]}
    s2_current_texts = {
        row["id"]: ui_text(row["text"])
        for row in s2_current["dialogue"]["rows"]
    }
    page_voice = load_json(S2_PAGE_VOICE_FIXES)
    need(
        page_voice.get("schema")
        == "langrisser-fx-scenario02-page-voice-parity-fixes/v1",
        "2화 페이지/음성 교정 자료 형식이 다릅니다.",
    )
    page_voice_edits = {
        str(record_id): ui_text(str(text))
        for record_id, text in page_voice["edits"].items()
    }
    need(
        len(page_voice_edits) == 11
        and set(page_voice_edits) <= set(s2_current_texts),
        "2화 페이지/음성 교정 자료가 불완전합니다.",
    )
    s2_current_texts.update(page_voice_edits)
    s2_edits = sorted(
        (
            int(edit["id"].rsplit("/", 1)[1]),
            edit,
        )
        for edit in s2_layout["edits"]
        if edit.get("edit_class") == "scenario02-fixed-korean-dialogue"
    )
    need(len(s2_edits) == S2_DIALOGUE_RECORDS, "2화 레코드 수가 예상과 다릅니다.")
    need(
        set(s2_current_texts) == {
            f"scenario02/dialogue/{ordinal:03d}"
            for ordinal in range(S2_DIALOGUE_RECORDS)
        },
        "2화 현행 기준 대사 보고서가 불완전합니다.",
    )
    for ordinal, edit in s2_edits:
        record_id = f"scenario02/dialogue/{ordinal:03d}"
        records.append(
            DialogueRecord(
                id=record_id,
                scenario=2,
                source_text=s2_sources.get(record_id, ""),
                base_text=s2_current_texts[record_id],
                cooked_offset=None,
                allocation=0,
                active_budget=S2_DIALOGUE_END - S2_DIALOGUE_START,
                family="scenario02-packed",
            )
        )

    # Scenarios 3-12 use fixed records and their already-installed dictionaries.
    # The old compact catalogues are the physical successor190 preimage only.
    # Reviewed full drafts that already satisfy the page, glyph and aggregate
    # pool contracts are the editor defaults and must be installed by the next
    # build without requiring the user to touch each row manually.
    faithful_document = load_json(EARLY_FAITHFUL_ADOPTIONS)
    need(
        faithful_document.get("schema")
        == "langrisser-fx-dialogue-faithful-adoptions/v2",
        "3~12화 무축약 채택 자료 형식이 다릅니다.",
    )
    faithful = {
        str(record_id): ui_text(str(text))
        for record_id, text in faithful_document.get("records", {}).items()
    }
    need(len(faithful) == 409, "3~12화 무축약 해결 수가 예상과 다릅니다.")
    for scenario, (revision, _plan_name) in EARLY.items():
        source = load_json(
            ROOT / f"analysis/scenario{scenario:02d}_dialogue_source_original.json"
        )
        translations = load_json(
            ROOT
            / "analysis/early_scenario_compact_r53"
            / f"translations_scenario{scenario:02d}_{revision}_compact.json"
        )["records"]
        by_id = {row["id"]: row for row in source["dialogue"]}
        for record_id, text in sorted(translations.items()):
            row = by_id[record_id]
            compact_text = ui_text(text)
            records.append(
                DialogueRecord(
                    id=record_id,
                    scenario=scenario,
                    source_text=_record_source_text(row),
                    base_text=faithful.get(record_id, compact_text),
                    cooked_offset=int(row["cooked_offset"], 0),
                    allocation=int(row["length"]),
                    active_budget=int(row["length"]) - 1,
                    family="scenario03-12-fixed",
                    disc_text=compact_text,
                )
            )
    need(
        set(faithful) <= {row.id for row in records},
        "3~12화 무축약 채택 ID가 현행 대사 목록과 맞지 않습니다.",
    )

    # Scenario 13 was extracted in verified fragments.
    s13_rows: dict[str, dict] = {}
    for path in sorted((ROOT / "analysis").glob("scenario13_*_source_v*.json")):
        document = load_json(path)
        rows = document.get("dialogue") or document.get("records") or document.get("entries") or []
        for row in rows:
            if row.get("id", "").startswith("scenario13/"):
                s13_rows[row["id"]] = row
    s13_translations = _merge_translation_files(
        (ROOT / "analysis").glob("translations_scenario13_*_draft_v*.json"),
        "scenario13/",
    )
    boundary = ROOT / "analysis/translations_scenario13_record_boundary_v78.json"
    if boundary.is_file():
        s13_translations.update(
            {key: ui_text(value) for key, value in load_json(boundary).items()}
        )
    for record_id, row in sorted(s13_rows.items()):
        need(record_id in s13_translations, f"13화 번역 누락: {record_id}")
        records.append(
            DialogueRecord(
                id=record_id,
                scenario=13,
                source_text=_record_source_text(row),
                base_text=s13_translations[record_id],
                cooked_offset=int(row["cooked_offset"], 0),
                allocation=int(row.get("length") or len(bytes.fromhex(row["raw_hex"]))),
                active_budget=int(row.get("length") or len(bytes.fromhex(row["raw_hex"]))) - 1,
                family="scenario13-70-fixed",
            )
        )

    # Scenarios 14-70 each have a verified fixed-record source extract.
    for scenario in range(14, 71):
        candidates = sorted(
            (ROOT / "analysis").glob(f"scenario{scenario:02d}_dialogue_source_v*.json"),
            key=version_key,
        )
        if scenario == 14:
            candidates = [ROOT / "analysis/scenario14_source_v79.json"]
        need(bool(candidates), f"{scenario}화 소스 추출 파일이 없습니다.")
        source = load_json(candidates[-1])
        translations = _merge_translation_files(
            (ROOT / "analysis").glob(f"translations_scenario{scenario:02d}_*.json"),
            f"scenario{scenario:02d}/dialogue/",
        )
        rows = source.get("dialogue", [])
        for row in rows:
            record_id = row["id"]
            # Some extracts include a small preserved presentation tail after
            # the true dialogue.  Only IDs present in the verified dialogue
            # translation set belong in this editor.
            if record_id not in translations:
                continue
            allocation = int(row.get("length") or len(bytes.fromhex(row["raw_hex"])))
            records.append(
                DialogueRecord(
                    id=record_id,
                    scenario=scenario,
                    source_text=_record_source_text(row),
                    base_text=translations[record_id],
                    cooked_offset=int(row["cooked_offset"], 0),
                    allocation=allocation,
                    active_budget=allocation - 1,
                    family="scenario13-70-fixed",
                )
            )

    # Source extracts predate the dedicated system-menu condition catalogue.
    # Do not expose rows that physically belong to that table as dialogue, and
    # never let pooled dialogue capacity extend into the table that follows it.
    condition_owned_dialogue_ids = {
        row.id for row in records if starts_in_menu_condition(row)
    }
    records = [
        row for row in records if row.id not in condition_owned_dialogue_ids
    ]
    ids = [row.id for row in records]
    need(len(ids) == len(set(ids)), "대사 ID가 중복되었습니다.")
    loaded_scenarios = {row.scenario for row in records}
    missing_scenarios = sorted(set(range(1, 71)) - loaded_scenarios)
    need(not missing_scenarios, f"대사 자료가 없는 시나리오: {missing_scenarios}")
    ordered = sorted(records, key=lambda row: (row.scenario, row.id))
    ordered = _rebase_pooled_boundaries(ordered)
    if not apply_all_faithful:
        return ordered

    # Successor199 adopts the complete PC-FX-source-reviewed corpus.  Scenario
    # 2 changes are limited to individually reviewed rows whose native page
    # count and control-token order were preserved by the resolver.
    all_faithful = load_json(ALL_FAITHFUL_ADOPTIONS)
    need(
        all_faithful.get("schema")
        == "langrisser-fx-dialogue-faithful-adoptions-all/v1",
        "전체 무축약 대사 채택 자료 형식이 다릅니다.",
    )
    adopted = {
        str(record_id): ui_text(str(text))
        for record_id, text in all_faithful["records"].items()
    }
    known = {row.id for row in ordered}
    unknown_adoptions = set(adopted) - known
    need(
        unknown_adoptions <= condition_owned_dialogue_ids,
        "전체 무축약 대사 ID가 현행 목록과 다릅니다.",
    )
    result: list[DialogueRecord] = []
    for row in ordered:
        if row.id not in adopted:
            result.append(row)
            continue
        physical = installed_text(row)
        result.append(replace(
            row,
            base_text=adopted[row.id],
            disc_text=physical,
        ))
    # Source-bound missing-glyph repairs precede the layout compiler.  The
    # successor240 reflow is generated from this repaired text, so applying a
    # second legacy post-layout variant would both duplicate ownership and
    # tie the repair to obsolete 192px line breaks.
    repaired = apply_name_particle_policy(reference_glyph_repairs.apply_to_adopted_records(
        result, layout=False
    ))
    if not apply_layout_reflow:
        return apply_scenario01_condition_policy(repaired)

    # successor240 and its successor243 exceptions remain immutable evidence
    # for the preceding test build.  Successor244 starts again from the
    # reviewed wording layer, restores exact native page parity, and performs
    # one full-corpus readable reflow without visual-only continuation pages.
    layout = load_json(DIALOGUE_LAYOUT_READABLE_PAGE_PARITY)
    need(
        layout.get("schema")
        == "langrisser-fx-dialogue-readable-page-parity-layout/v1"
        and layout.get("status") == "prepared"
        and int(layout.get("safe_visible_width_px", -1))
        == MAX_DIALOGUE_SAFE_VISIBLE_WIDTH_PX
        and int(layout.get("first_page_body_lines", -1))
        == FIRST_DIALOGUE_BODY_LINES
        and int(layout.get("later_page_body_lines", -1))
        == MAX_DIALOGUE_LINES_PER_PAGE,
        "전체 대사 원문 페이지/가독성 재배치 자료 형식이 다릅니다.",
    )
    reflowed = {
        str(record_id): ui_text(str(text))
        for record_id, text in layout["records"].items()
    }
    need(set(reflowed) <= known, "전체 대사 원문 페이지 재배치 ID가 현행 목록과 다릅니다.")
    final: list[DialogueRecord] = []
    for row in repaired:
        if row.id not in reflowed:
            final.append(row)
            continue
        final.append(replace(
            row,
            base_text=reflowed[row.id],
            disc_text=installed_text(row),
        ))
    final = apply_scenario01_condition_policy(apply_name_particle_policy(final))
    corrections = load_json(ROOT / "dialogue_editor/dialogue_user_corrections.json")
    need(corrections.get("schema") == "langrisser-fx-user-dialogue-corrections/v1",
         "사용자 대사 교정 자료 형식이 다릅니다.")
    by_id = corrections["corrections"]
    need(set(by_id) <= {row.id for row in final}, "교정할 대사가 누락되었습니다.")
    corrected = []
    for row in final:
        change = by_id.get(row.id)
        if change is not None:
            need(row.base_text in (change["before"], change["after"]),
                 f"{row.id}: 사용자 교정 전 문장이 변경되었습니다.")
            row = replace(row, base_text=change["after"], disc_text=installed_text(row))
        corrected.append(row)
    # Separate source-bound reviews own S13/S14 wording and explicit page-local
    # layout. Do not feed it back through the historical cross-page reflow.
    import scenario_dialogue_review
    import scenario14_dialogue_review
    import scenario15_user_dialogue
    import scenario15_additional_dialogue
    import scenario17_dialogue_review
    return scenario17_dialogue_review.apply_to_editor(scenario15_additional_dialogue.apply_to_editor(scenario15_user_dialogue.apply_to_editor(
        scenario14_dialogue_review.apply_to_editor(
            scenario_dialogue_review.apply_to_editor(corrected)))))


@lru_cache(maxsize=1)
def latest_private_mapping() -> dict[str, bytes]:
    # The ordinary dialogue renderer uses the resident R77 ownership table.
    # Never merge the later v375 secret-shop table here: that table describes
    # a different physical font context and deliberately assigns several of
    # the same two-byte codes to different characters.  Treating it as a
    # global update made edits emit shop owners such as F049=룬 even though
    # the resident dialogue cell is F049=읽.
    document = load_json(DIALOGUE_RESIDENT_CHARSET)
    result = {
        row["character"]: int(row["code"], 0).to_bytes(2, "big")
        for row in document["mappings"]
    }
    # U+0020/F1E6 and U+2009/F1E8 retain separate owners.  Encoders normalize
    # user-entered ordinary spaces to U+2009 at emission time instead of
    # registering an alias in this ownership table.
    need(result.get("울") == UL_CODE,
         "현행 resident 문자표의 F272 ‘울’ 소유권이 다릅니다.")
    need_unique_mapping(result, "현행 공용 문자표")
    return result


@lru_cache(maxsize=1)
def early_private_mapping() -> dict[str, bytes]:
    # The rejected successor45 F4 atlas must never be emitted on the recovered
    # successor161 lineage.  Early-scenario user edits use only the resident
    # mapping actually present in the current image.
    result = dict(latest_private_mapping())
    # Successor73 restores the 3-12 dialogue/item atlas through a safe
    # Resource-12-local route.  Reconstruct its pinned assignments so edits
    # use the exact codes already installed in the game image.
    # Never rebuild this atlas from the mutable translation JSON files.  The
    # on-disc Resource-12 atlas was assigned from the exact successor45/46
    # build inputs.  Adding even one Hangul syllable to a later draft changes
    # the sorted-code order and makes every following character point at the
    # wrong glyph.  The two pinned build reports preserve the actual texts
    # used to create the resident atlas, so reconstruct its immutable mapping
    # from those reports instead.
    atlas_report = load_json(GLOBAL_ATLAS_REPORT)
    dialogue_report = load_json(GLOBAL_DIALOGUE_REPORT)
    atlas_texts = [
        row["display_text"]
        for row in atlas_report["item_names"]["writes"]
    ] + [
        row["display_text"]
        for row in dialogue_report["edits"]
    ]
    atlas_characters = sorted({
        character
        for text in atlas_texts
        for character in text
        if 0xAC00 <= ord(character) <= 0xD7A3
    })
    need(
        len(atlas_characters)
        == int(atlas_report["global_private_atlas"]["characters"]),
        "고정 F4-F7 글리프 표의 문자 수가 빌드 보고서와 다릅니다.",
    )
    for character, code in global_atlas.code_rows(atlas_characters):
        result[character] = code.to_bytes(2, "big")
    extension = load_json(GLOBAL_PRESENTATION_REPORT)["atlas_extension"]
    for character, code in zip(
        extension["appended_characters"], extension["appended_codes"]
    ):
        result[character] = int(code, 0).to_bytes(2, "big")
    legacy = load_json(LEGACY_CHARSET)
    for row in legacy["mappings"]:
        character = row["character"]
        if len(character) != 1 or character in (" ", "\u2009"):
            continue
        if 0xAC00 <= ord(character) <= 0xD7A3:
            continue
        code = int(row["code"], 0).to_bytes(2, "big")
        # R40's local punctuation owners are not global resident owners.  A
        # notable collision is local F049=· versus resident F049=읽.  Use the
        # normal Shift-JIS punctuation path whenever the local code is already
        # owned in this physical context instead of creating an alias.
        if code in result.values():
            continue
        result.setdefault(character, code)
    extension = load_json(EARLY_DIALOGUE_GLYPH_EXTENSION)
    need(
        extension.get("schema")
        == "langrisser-fx-early-dialogue-glyph-extension/v1"
        and extension.get("status") == "adopted",
        "3~12화 무축약 글리프 확장 자료 형식이 다릅니다.",
    )
    for row in extension["font"]["assignments"]:
        character = str(row["character"])
        code = int(row["code"], 0).to_bytes(2, "big")
        need(character not in result,
             f"3~12화 확장 문자가 이미 소유됨: {character}")
        need(code not in result.values(),
             f"3~12화 확장 코드가 이미 소유됨: {code.hex().upper()}")
        result[character] = code
    result["!"] = bytes.fromhex("8149")
    result["?"] = bytes.fromhex("8148")
    need_unique_mapping(result, "3화 이후 문자표")
    return result


@lru_cache(maxsize=1)
def all_dialogue_private_mapping() -> dict[str, bytes]:
    """Return the immutable early atlas plus successor200 unique cells."""
    result = dict(early_private_mapping())
    document = load_json(GLOBAL_DIALOGUE_GLYPH_EXTENSION)
    need(
        document.get("schema")
        == "langrisser-fx-global-dialogue-glyph-extension/v1"
        and document.get("status") == "prepared",
        "전체 대사 글리프 확장 자료 형식이 다릅니다.",
    )
    for row in document["font"]["assignments"]:
        character = str(row["character"])
        code = int(row["code"], 0).to_bytes(2, "big")
        need(character not in result, f"전체 대사 확장 문자가 이미 소유됨: {character}")
        need(code not in result.values(), f"전체 대사 확장 코드가 이미 소유됨: {code.hex()}")
        result[character] = code
    need_unique_mapping(result, "전체 대사 확장 문자표")
    return result


def is_pooled_record(record: DialogueRecord) -> bool:
    # Scenario 1's three in-battle condition rows are separately addressed by
    # the native victory/defeat consumer.  They happen to sit beside ordinary
    # NUL-delimited dialogue, but moving them to shorter pooled boundaries
    # makes the second defeat row disappear at runtime.  Keep their historical
    # starts and allocations fixed; only ordinary dialogue may share capacity.
    return (
        record.family in POOL_FAMILIES
        and record.id not in SCENARIO01_MENU_CONDITION_IDS
    )


def contiguous_pools(
    records: Iterable[DialogueRecord],
) -> list[list[DialogueRecord]]:
    """Return fixed-record runs whose total extent may be shared safely.

    Runs never cross scenario/family boundaries or an unowned byte gap.  The
    first offset, record order, record count, and exclusive end stay fixed.
    """
    candidates = sorted(
        (row for row in records
         if is_pooled_record(row) and row.cooked_offset is not None),
        key=lambda row: (row.scenario, row.family, row.cooked_offset or 0),
    )
    pools: list[list[DialogueRecord]] = []
    current: list[DialogueRecord] = []
    for row in candidates:
        adjacent = bool(
            current
            and current[-1].scenario == row.scenario
            and current[-1].family == row.family
            and current[-1].cooked_offset is not None
            and current[-1].cooked_offset + current[-1].allocation
            == row.cooked_offset
        )
        if current and not adjacent:
            pools.append(current)
            current = []
        current.append(row)
    if current:
        pools.append(current)
    return pools


def _rebase_pooled_boundaries(
    records: list[DialogueRecord],
) -> list[DialogueRecord]:
    """Use the pinned base image's real NUL boundaries inside each run.

    One historical Scenario-13 boundary repair moved two bytes between two
    adjacent records while preserving their combined span.  Source-extract
    offsets predate that repair, so the editor must follow the current image
    rather than reopen the old split.
    """
    cooked = BASE_DIR / BASE_COOKED_NAME
    if not cooked.is_file():
        return records
    image = cooked.read_bytes()
    replacements: dict[str, DialogueRecord] = {}
    for pool in contiguous_pools(records):
        start = pool[0].cooked_offset
        final_offset = pool[-1].cooked_offset
        need(start is not None and final_offset is not None,
             f"{pool[0].id}: 묶음 오프셋 없음")
        end = final_offset + pool[-1].allocation
        condition_extent = menu_condition_owned_ranges().get(
            pool[0].scenario
        )
        if (
            condition_extent is not None
            and start < condition_extent[0] < end
        ):
            # Historical extract lengths occasionally swallowed the first
            # bytes of the following menu-condition table.  The last dialogue
            # record ends at that table boundary, never after it.
            end = condition_extent[0]
        need(final_offset < end,
             f"{pool[0].id}: 승패조건 소유 범위와 대사 범위가 겹칩니다.")
        cursor = start
        for index, row in enumerate(pool):
            terminator = image.find(b"\0", cursor, end)
            need(terminator >= 0, f"{row.id}: 기준판 NUL 종단 없음")
            next_cursor = terminator + 1
            allocation = (
                end - cursor if index == len(pool) - 1
                else next_cursor - cursor
            )
            replacements[row.id] = replace(
                row,
                cooked_offset=cursor,
                allocation=allocation,
                active_budget=allocation - 1,
            )
            cursor = next_cursor
        need(cursor <= end, f"{pool[0].id}: 기준판 묶음 경계 초과")
    return [replacements.get(row.id, row) for row in records]


def encode_plain(text: str, private: dict[str, bytes]) -> tuple[bytes, list[str]]:
    text = engine_text(text)
    output = bytearray()
    missing: list[str] = []
    cursor = 0
    while cursor < len(text):
        if text[cursor] == "\n":
            output.append(0x08)
            cursor += 1
            continue
        if text[cursor] == "\f":
            output.extend(PAGE)
            cursor += 1
            continue
        match = TOKEN.match(text, cursor)
        if match and match.group(0).lower() != "{page}":
            kind, value = match.group(1), int(match.group(2), 16)
            output.extend((0x09, value) if kind == "name" else (value,))
            cursor = match.end()
            continue
        character = text[cursor]
        lookup = "\u2009" if character == " " else character
        if lookup in private:
            output.extend(private[lookup])
        else:
            try:
                output.extend(character.encode("shift_jis"))
            except UnicodeEncodeError:
                missing.append(character)
        cursor += 1
    return bytes(output), sorted(set(missing))


def fixed_record(encoded: bytes, allocation: int) -> bytes:
    need(b"\0" not in encoded, "대사에 NUL 바이트가 들어갔습니다.")
    padding = allocation - len(encoded) - 1
    need(padding >= 0, f"레코드 용량을 {-padding}바이트 초과했습니다.")
    result = bytearray(encoded)
    if padding & 1:
        result.append(0x05)
        padding -= 1
    result.extend(SPACE_VISIBLE * (padding // 2))
    result.append(0)
    need(len(result) == allocation, "고정 레코드 크기 계산 오류")
    return bytes(result)


@lru_cache(maxsize=10)
def _early_plan(scenario: int) -> tuple[dict, dict[str, int]]:
    plan = load_json(ROOT / "analysis" / EARLY[scenario][1])
    phrase_codes = {
        row["phrase"]: int(row["code"], 0) & 0xFF
        for row in plan["dictionary"]["assignments"]
    }
    extension = load_json(EARLY_DIALOGUE_PHRASE_EXTENSION)
    need(
        extension.get("schema")
        == "langrisser-fx-early-dialogue-phrase-extension/v1"
        and extension.get("status") == "adopted",
        "3~12화 전용 사전 확장 자료 형식이 다릅니다.",
    )
    for scenario_row in extension["scenarios"]:
        if int(scenario_row["scenario"]) != scenario:
            continue
        for assignment in scenario_row["assignments"]:
            phrase = str(assignment["phrase"])
            code = int(assignment["code"], 0) & 0xFF
            need(phrase not in phrase_codes,
                 f"{scenario}화 전용 사전 문구가 기존 문구와 중복됩니다.")
            need(code not in phrase_codes.values(),
                 f"{scenario}화 전용 사전 코드가 기존 코드와 중복됩니다.")
            phrase_codes[phrase] = code
    return plan, phrase_codes


@lru_cache(maxsize=58)
def _later_phrase_codes(scenario: int) -> dict[str, int]:
    need(13 <= scenario <= 70, f"후반 시나리오 범위 오류: {scenario}")
    document = load_json(SCENARIO_DIALOGUE_PHRASE_EXTENSIONS)
    need(
        document.get("schema")
        == "langrisser-fx-scenario-dialogue-phrase-extensions/v1"
        and document.get("status") == "prepared",
        "13~70화 전용 사전 확장 자료 형식이 다릅니다.",
    )
    row = next(
        (value for value in document["scenarios"]
         if int(value["scenario"]) == scenario),
        None,
    )
    need(row is not None, f"{scenario}화 전용 사전 계획이 없습니다.")
    result = {
        str(assignment["phrase"]): int(assignment["code"], 0) & 0xFF
        for assignment in row["assignments"]
    }
    need(
        len(result) == len(row["assignments"])
        and len(set(result.values())) == len(result)
        and all(1 <= code <= 0xF1 for code in result.values()),
        f"{scenario}화 전용 사전 소유권 오류",
    )
    return result


@lru_cache(maxsize=1)
def _s2_encoding_resources() -> tuple[dict[str, bytes], dict[str, int]]:
    charset = load_json(S2_CHARSET)
    private = {
        row["character"]: int(row["code"], 0).to_bytes(2, "big")
        for row in charset["mappings"]
    }
    private["!"] = bytes.fromhex("8149")
    private["?"] = bytes.fromhex("8148")
    need_unique_mapping(private, "2화 문자표")
    plan = load_json(S2_DIALOGUE_NARRATION_PHRASE_EXTENSION)
    need(
        plan.get("schema")
        == "langrisser-fx-scenario02-dialogue-narration-phrase-extension/v1"
        and plan.get("status") == "prepared",
        "2화 대사·나레이션 공동 사전 계획 형식이 다릅니다.",
    )
    phrase_codes = {
        str(row["phrase"]): int(row["code"], 0) & 0xFF
        for row in plan["dictionary"]["assignments"]
    }
    need(
        S2_RELOCATED_DIALOGUE_CODE not in phrase_codes.values(),
        "2화 0407 재배치 코드가 다른 대사에 사용 중입니다.",
    )
    phrase_codes[S2_RELOCATED_DIALOGUE_PHRASE] = S2_RELOCATED_DIALOGUE_CODE
    need(
        not (set(phrase_codes.values()) & S2_CONDITION_EXCLUSIVE_CODES),
        "2화 대사 압축표가 승패조건 전용 코드를 참조합니다.",
    )
    return private, phrase_codes


_S1_DICTIONARY_CACHE: dict[int, dict[int, str]] = {}


@lru_cache(maxsize=1)
def _s1_phrase_codes() -> dict[str, int]:
    document = load_json(SCENARIO01_DIALOGUE_PHRASE_EXTENSION)
    need(
        document.get("schema")
        == "langrisser-fx-scenario01-dialogue-phrase-extension/v1"
        and document.get("status") == "prepared",
        "1화 전용 대사 사전 계획 형식이 다릅니다.",
    )
    rows = list(document["dictionary"]["assignments"])
    rows.extend(document["dictionary"]["preserved_entries"])
    phrases: dict[str, int] = {}
    codes: set[int] = set()
    for row in rows:
        phrase = str(row.get("phrase", row.get("text", "")))
        code = int(row["code"], 0)
        phrase = reference_glyph_repairs.scenario01_phrase(code, phrase)
        if not phrase:
            continue
        need(phrase not in phrases, f"1화 사전 문구 소유권 중복: {phrase}")
        need(code not in codes, f"1화 사전 코드 소유권 중복: {code:02X}")
        phrases[phrase] = code
        codes.add(code)
    need(
        len(codes) == len(rows)
        and len(codes) <= 239
        and all(1 <= code <= 239 for code in codes),
        "1화 사전 코드 소유 범위가 다릅니다.",
    )
    return phrases


@lru_cache(maxsize=10)
def _early_full_phrase_codes(scenario: int) -> dict[str, int]:
    document = load_json(EARLY_SCENARIO_DIALOGUE_PHRASE_EXTENSIONS)
    need(
        document.get("schema")
        == "langrisser-fx-early-scenario-dialogue-phrase-extensions/v1"
        and document.get("status") == "prepared",
        "3~12화 전체 대사 사전 계획 형식이 다릅니다.",
    )
    selected = [
        row for row in document["scenarios"]
        if int(row["scenario"]) == scenario
    ]
    need(len(selected) == 1, f"{scenario}화 전체 대사 사전 계획 없음")
    phrases: dict[str, int] = {}
    codes: set[int] = set()
    for row in selected[0]["assignments"]:
        phrase = str(row["phrase"])
        code = int(row["code"], 0)
        need(phrase not in phrases, f"{scenario}화 전체 사전 문구 중복")
        need(code not in codes, f"{scenario}화 전체 사전 코드 중복")
        phrases[phrase] = code
        codes.add(code)
    return phrases


def encode_for_record(record: DialogueRecord, text: str, image: bytes | None = None) -> bytes:
    if record.id in SUSPEND_RESUME_LITERAL_DIALOGUE_IDS:
        encoded, missing = encode_plain(text, with_native_ascii(early_private_mapping()))
        need(not missing, f"지원하지 않는 글자: {', '.join(missing)}")
        return encoded
    if record.family == "scenario02-packed":
        private, phrases = native_phrase_resources(*_s2_encoding_resources())
        encoded, _used = encode_compressed(
            engine_text(text), private, phrases, S2_DIALOGUE_END - S2_DIALOGUE_START
        )
        return encoded
    if record.family == "scenario03-12-fixed":
        private, phrases = native_phrase_resources(
            early_private_mapping(), _early_full_phrase_codes(record.scenario))
        # Successor79 stores these records in a shared NUL-delimited pool.
        # Individual historical slot sizes are no longer a write limit; the
        # aggregate pool capacity is enforced by _plan_pooled_writes().
        encoded, _used = encode_compressed(
            engine_text(text), private, phrases,
            1 << 20,
        )
        return encoded
    if record.family == "scenario01-prefix":
        private, phrases = native_phrase_resources(all_dialogue_private_mapping(), _s1_phrase_codes())
        encoded, _used = encode_compressed(
            engine_text(text), private, phrases, 1 << 20
        )
        return encoded
    if record.family == "scenario13-70-fixed":
        private, phrases = native_phrase_resources(
            all_dialogue_private_mapping(), _later_phrase_codes(record.scenario))
        encoded, _used = encode_compressed(
            engine_text(text), private, phrases,
            1 << 20,
        )
        return encoded
    private = with_native_ascii(all_dialogue_private_mapping())
    encoded, missing = encode_plain(text, private)
    need(not missing, f"지원하지 않는 글자: {', '.join(missing)}")
    return encoded


def _unknown_tokens(text: str) -> list[str]:
    return [token for token in ANY_BRACE.findall(text) if not TOKEN.fullmatch(token)]


def script_residuals(text: str) -> list[str]:
    """Return Japanese kana or CJK ideographs left in a Korean dialogue."""
    residuals = {
        character
        for character in text
        if ((0x3040 <= ord(character) <= 0x30FF and character != "・")
            or 0x3400 <= ord(character) <= 0x9FFF)
    }
    return sorted(residuals)


def validate_record(
    record: DialogueRecord,
    text: str,
    image: bytes | None = None,
) -> Validation:
    errors: list[str] = []
    warnings: list[str] = []
    if reference_glyph_repairs.MARKER.search(text):
        errors.append("참고 글꼴 복원 실패 표기 [번호:번호]가 남아 있습니다. 원문 대조가 필요합니다.")
    condition_row = not is_portrait_dialogue(record)
    try:
        if condition_row:
            widths = scenario01_menu_condition_line_widths(text)
        else:
            inspected = portrait_layout_inspection(text)
            widths = [
                max(int(line["advance"]), int(line["right"]))
                for line in inspected["lines"]
            ]
            if inspected["failures"]:
                errors.append(
                    "대사창 배치 규칙 위반(첫 화면 3줄·이후 4줄·168px): "
                    + "; ".join(inspected["failures"])
                )
    except (DialogueError, ValueError) as exc:
        widths = []
        errors.append(str(exc))
    maximum = max(widths, default=0)
    changed = text != installed_text(record)
    maximum_width = (
        MENU_CONDITION_MAX_WIDTH_PX
        if condition_row else MAX_DIALOGUE_SAFE_VISIBLE_WIDTH_PX
    )
    if maximum > maximum_width:
        errors.append(
            "한 줄 폭 "
            f"{maximum}px: 안전 표시 폭 {maximum_width}px를 "
            "넘었습니다. 마지막 글자가 잘릴 수 있습니다."
        )
    residuals = script_residuals(text)
    if residuals:
        errors.append(
            "일본어·한자 잔존: " + ", ".join(residuals)
        )
    line_counts = page_line_counts(text)
    if condition_row:
        if line_counts != (1,):
            errors.append("1화 전투 승리·패배조건의 각 항목은 한 줄이어야 합니다.")
        if max(line_counts, default=0) > 1:
            errors.append("1화 전투 조건 문구는 시각·음성 페이지를 사용할 수 없습니다.")
    # Extracted PC-FX source keeps voice-page controls as the literal escape
    # sequence ``\\f``.  Normalise that source notation before comparing it
    # with editor ``{page}`` tokens; otherwise every multi-page source is
    # incorrectly treated as a one-page line.
    source_contract = (
        record.source_text.replace("\\n", "\n").replace("\\f", "\f")
    )
    source_pages = engine_text(source_contract).count("\f")
    base_pages = engine_text(record.base_text).count("\f")
    edited_pages = engine_text(text).count("\f")
    if record.family == "scenario02-packed" and edited_pages != source_pages:
        errors.append(
            "2화 음성 타이밍을 위해 페이지 구분 수는 일본판 원문과 "
            f"같아야 합니다. 원문 {source_pages}개 / 현재 {edited_pages}개"
        )
    if not changed:
        return Validation(
            not errors, -1, record.active_budget, maximum,
            tuple(errors), tuple(warnings),
        )
    unknown = _unknown_tokens(text)
    if unknown:
        errors.append("알 수 없는 토큰: " + ", ".join(sorted(set(unknown))))
    edited_names = token_kind_multiset(text, "name")
    base_names = token_kind_multiset(record.base_text, "name")
    source_names = token_kind_multiset(record.source_text, "name")
    if edited_names not in (base_names, source_names):
        errors.append(
            "이름 토큰은 기준판 또는 일본판 원문과 같은 종류·개수여야 합니다."
        )
    edited_dict = token_kind_multiset(text, "dict")
    base_dict = token_kind_multiset(record.base_text, "dict")
    source_dict = token_kind_multiset(record.source_text, "dict")
    if edited_dict not in (base_dict, source_dict):
        errors.append(
            "사전 토큰은 기준판 또는 일본판 원문과 같은 종류·개수여야 합니다."
        )
    source_raw = token_kind_multiset(record.source_text, "raw")
    base_raw = token_kind_multiset(record.base_text, "raw")
    edited_raw = token_kind_multiset(text, "raw")
    if edited_raw not in (base_raw, source_raw):
        errors.append(
            "제어 토큰은 기준판 또는 일본판 원문과 같아야 합니다. "
            f"기준 {dict(base_raw)} / 원문 {dict(source_raw)} / 현재 {dict(edited_raw)}"
        )
    if (
        record.family != "scenario02-packed"
        and edited_pages not in (base_pages, source_pages)
    ):
        errors.append(
            "음성 타이밍을 위해 페이지 구분 수는 기준 번역 또는 일본판 "
            "원문과 같아야 합니다. "
            f"기준 {base_pages}개 / 원문 {source_pages}개 / 현재 {edited_pages}개"
        )
    if "\f" in text:
        errors.append("페이지 구분은 실제 FF 문자가 아니라 {page}로 입력하세요.")
    encoded = b""
    if not errors or not unknown:
        try:
            encoded = encode_for_record(record, text, image)
        except (DialogueError, ValueError, KeyError) as exc:
            errors.append(str(exc))
    if encoded and b"\0" in encoded:
        errors.append("대사 본문에 NUL 종단값이 생겼습니다.")
    capacity = record.active_budget
    if record.family == "scenario02-packed":
        capacity = S2_DIALOGUE_END - S2_DIALOGUE_START
        # Per-line validation is useful here; exact packed capacity is checked
        # globally by validate_project/build.
    elif is_pooled_record(record):
        # Individual fixed slots may borrow from their contiguous dialogue
        # run.  Exact aggregate capacity is checked by validate_project/build.
        capacity = -1
    elif len(encoded) > capacity:
        errors.append(f"{len(encoded) - capacity}바이트 초과 ({len(encoded)}/{capacity})")
    if changed and not errors:
        warnings.append("수정됨")
    return Validation(not errors, len(encoded), capacity, maximum, tuple(errors), tuple(warnings))


def load_project(path: Path, records: list[DialogueRecord]) -> dict[str, str]:
    if not path.is_file():
        return {}
    document = load_json(path)
    need(document.get("schema") == "langrisser-fx-dialogue-editor/v1", "편집 파일 형식이 다릅니다.")
    known = {row.id for row in records}
    edits = document.get("edits", {})
    need(isinstance(edits, dict), "편집 파일 edits가 잘못되었습니다.")
    unknown = set(edits) - known
    need(not unknown, "알 수 없는 대사 ID: " + ", ".join(sorted(unknown)[:5]))
    return {key: str(value) for key, value in edits.items()}


def save_project(path: Path, records: list[DialogueRecord], texts: dict[str, str]) -> None:
    base = {row.id: row.base_text for row in records}
    edits = {key: value for key, value in sorted(texts.items()) if value != base[key]}
    document = {
        "schema": "langrisser-fx-dialogue-editor/v1",
        "base": BASE_STEM,
        "base_cooked_sha256": BASE_HASHES[BASE_COOKED_NAME],
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "edits": edits,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def verify_base_folder(folder: Path) -> tuple[Path, Path, Path]:
    cooked = folder / BASE_COOKED_NAME
    raw = folder / BASE_RAW_NAME
    cue = folder / BASE_CUE_NAME
    for path in (cooked, raw, cue):
        need(path.is_file(), f"기준 파일 없음: {path}")
        expected = BASE_HASHES[path.name]
        actual = sha256_file(path)
        need(actual == expected, f"기준 파일 해시 불일치: {path.name}\n{actual}")
    glyph = UL_GLYPH_ASSET.read_bytes()
    need(len(glyph) == 18 and any(glyph), "울 글리프 자산이 잘못되었습니다.")
    with cooked.open("rb") as stream:
        stream.seek(UL_GLYPH_COOKED)
        installed = stream.read(len(glyph))
    need(installed == glyph,
         "기준 이미지의 12x12 ‘울’ 글리프(F272)가 예상과 다릅니다.")
    # Successor159 inherits all 190 editable Scenario-1 messages packed in their original
    # aggregate span.  Individual Japanese boundaries intentionally no longer
    # apply, so validate the packed denominator/order and the zero free tail.
    inventory = load_json(S1_INVENTORY)
    scenario1_rows = [
        row for row in inventory["dialogue"]
        if row["record_id"] != "block0/01303"
    ]
    need(len(scenario1_rows) == 190, "1화 편집 레코드 수가 다릅니다.")
    scenario1_rows.sort(key=lambda row: int(row["cooked_offset"], 0))
    scenario1_pools: list[list[dict]] = []
    for row in scenario1_rows:
        start = int(row["cooked_offset"], 0)
        adjacent = bool(
            scenario1_pools
            and int(scenario1_pools[-1][-1]["cooked_offset"], 0)
            + int(scenario1_pools[-1][-1]["allocation_bytes"]) + 1
            == start
        )
        if not adjacent:
            scenario1_pools.append([])
        scenario1_pools[-1].append(row)
    scenario1_image = cooked.read_bytes()
    parsed_records = 0
    for pool_index, pool in enumerate(scenario1_pools):
        start = int(pool[0]["cooked_offset"], 0)
        end = (
            int(pool[-1]["cooked_offset"], 0)
            + int(pool[-1]["allocation_bytes"]) + 1
        )
        blob = scenario1_image[start:end]
        cursor = 0
        for row in pool:
            terminator = blob.find(b"\0", cursor)
            need(
                terminator >= 0,
                f"1화 패킹 NUL 종단 누락: {row['record_id']}",
            )
            cursor = terminator + 1
            parsed_records += 1
        need(
            not any(blob[cursor:]),
            f"1화 패킹 묶음 {pool_index:02d} 꼬리가 0이 아닙니다.",
        )
    need(parsed_records == 190, "1화 패킹 레코드 수가 다릅니다.")
    return cooked, raw, cue


def _first_records(blob: bytes, count: int) -> tuple[list[bytes], int]:
    rows: list[bytes] = []
    cursor = 0
    for index in range(count):
        end = blob.find(b"\0", cursor)
        need(end >= 0, f"NUL 레코드 누락: {index}")
        rows.append(blob[cursor : end + 1])
        cursor = end + 1
    return rows, cursor


def _build_s2(image: bytearray, texts: dict[str, str]) -> tuple[list[tuple[int, bytes]], dict]:
    private, phrase_codes = native_phrase_resources(*_s2_encoding_resources())
    reverse_private = {value: key for key, value in private.items()}
    reverse_private[SPACE_VISIBLE] = " "
    reverse_private[bytes.fromhex("8149")] = "!"
    reverse_private[bytes.fromhex("8148")] = "?"

    dictionary_text = {code: phrase for phrase, code in phrase_codes.items()}
    dialogue_rows: list[bytes] = []
    used_phrases: set[str] = set()
    for ordinal in range(S2_DIALOGUE_RECORDS):
        record_id = f"scenario02/dialogue/{ordinal:03d}"
        encoded, used = encode_compressed(
            engine_text(texts[record_id]), private, phrase_codes, 1 << 20
        )
        decoded = decode_candidate(encoded, reverse_private, dictionary_text)
        need(encode_direct(decoded, private) == encode_direct(engine_text(texts[record_id]), private),
             f"{record_id}: 압축 왕복 검증 실패")
        referenced_exclusive = {
            code
            for code in S2_CONDITION_EXCLUSIVE_CODES
            if bytes((0x04, code)) in encoded
        }
        need(
            not referenced_exclusive,
            f"{record_id}: 승패조건 전용 사전 코드 참조 {referenced_exclusive}",
        )
        used_phrases.update(used)
        dialogue_rows.append(encoded + b"\0")

    plan = load_json(S2_DIALOGUE_NARRATION_PHRASE_EXTENSION)
    before_dictionary = bytes(image[S2_DICT_START:S2_DICT_END])
    need(
        hashlib.sha256(before_dictionary).hexdigest().upper()
        == str(plan["dictionary"]["base_sha256"]),
        "2화 공동 사전 기준 바이트가 다릅니다.",
    )
    dictionary_after = bytes.fromhex(plan["dictionary"]["payload_hex"])
    need(
        len(dictionary_after) == S2_DICT_END - S2_DICT_START,
        "2화 공동 사전 payload 크기 오류",
    )

    packed_dialogue = b"".join(dialogue_rows)
    need(len(packed_dialogue) <= S2_DIALOGUE_END - S2_DIALOGUE_START,
         f"2화 대사 전체 용량을 {len(packed_dialogue) - (S2_DIALOGUE_END - S2_DIALOGUE_START)}바이트 초과했습니다.")
    dialogue_after = packed_dialogue + bytes(S2_DIALOGUE_END - S2_DIALOGUE_START - len(packed_dialogue))
    return [
        (S2_DICT_START, dictionary_after),
        (S2_DIALOGUE_START, dialogue_after),
    ], {
        "dictionary_phrase_owners": len(plan["dictionary"]["assignments"]) + 1,
        "dictionary_padding": int(plan["dictionary"]["trailing_padding"]),
        "dialogue_narration_shared_dictionary": True,
        "dialogue_bytes": len(packed_dialogue),
        "dialogue_capacity": S2_DIALOGUE_END - S2_DIALOGUE_START,
        "condition_exclusive_codes": [
            f"0x04{code:02X}" for code in sorted(S2_CONDITION_EXCLUSIVE_CODES)
        ],
        "condition_exclusive_dialogue_hits": 0,
        "character_aliases": 0,
    }


def _minimal_existing_record(image: bytes | bytearray,
                             record: DialogueRecord) -> bytes:
    need(record.cooked_offset is not None, f"{record.id}: 오프셋 없음")
    raw = bytes(image[
        record.cooked_offset:record.cooked_offset + record.allocation
    ])
    need(len(raw) == record.allocation, f"{record.id}: 이미지 범위 초과")
    end = raw.find(b"\0")
    need(end >= 0, f"{record.id}: 기존 NUL 종단 없음")
    content = raw[:end]
    # Fixed-record builds pad the semantic stream with drawable blank cells
    # (and occasionally one native no-op alignment byte).  Removing only a
    # trailing run recovers shared capacity without decoding or rewriting the
    # unchanged record's dictionary/control tokens.
    while content.endswith(SPACE_VISIBLE) or content.endswith(b"\x81\x40"):
        content = content[:-2]
    if content.endswith(b"\x05"):
        content = content[:-1]
    need(b"\0" not in content, f"{record.id}: 기존 레코드 내부 NUL")
    return content + b"\0"


def _plan_pooled_writes(
    records: list[DialogueRecord],
    texts: dict[str, str],
    image: bytes | bytearray,
) -> tuple[list[tuple[int, bytes, str]], list[dict], set[str]]:
    """Repack every changed fixed-record run without per-record filler.

    Runtime verification proved that the historical odd-byte filler 0x05 is
    not inert in field dialogue.  It can replay the preceding text/voice and
    show unrelated Japanese/Hanzi glyphs.  Therefore even an edit that fits
    its old individual allocation must use the NUL-delimited pool writer; the
    unused capacity is zero-filled only after the final record in the run.
    """
    writes: list[tuple[int, bytes, str]] = []
    audits: list[dict] = []
    packed_changed_ids: set[str] = set()
    for pool_index, pool in enumerate(contiguous_pools(records)):
        changed = [
            row for row in pool
            if texts.get(row.id, row.base_text) != installed_text(row)
        ]
        if not changed:
            continue
        encoded_changed: dict[str, bytes] = {}
        encoded_scope = (
            pool
            if pool[0].family in (
                "scenario01-prefix", "scenario03-12-fixed",
                "scenario13-70-fixed",
            )
            else changed
        )
        for row in encoded_scope:
            try:
                encoded = encode_for_record(
                    row, texts.get(row.id, row.base_text), bytes(image)
                )
            except (RecursionError, ValueError) as exc:
                raise DialogueError(
                    f"{row.id} 묶음 전체 용량 검사 전에 대사가 인코더 "
                    f"안전 길이를 초과했거나 인코딩할 수 없습니다: {exc}"
                ) from exc
            need(b"\0" not in encoded, f"{row.id}: 대사 내부 NUL")
            encoded_changed[row.id] = encoded
        rows: list[bytes] = []
        for row in pool:
            if row.id in encoded_changed:
                rows.append(encoded_changed[row.id] + b"\0")
            else:
                rows.append(_minimal_existing_record(image, row))
        used = sum(map(len, rows))
        capacity = sum(row.allocation for row in pool)
        need(used <= capacity,
             f"{pool[0].id} 묶음 전체 용량을 {used - capacity}바이트 초과했습니다. "
             f"({used}/{capacity})")
        replacement = b"".join(rows) + bytes(capacity - used)
        start = pool[0].cooked_offset
        need(start is not None, f"{pool[0].id}: 묶음 시작 오프셋 없음")
        pool_id = f"scenario{pool[0].scenario:02d}/pool/{pool_index:03d}"
        writes.append((start, replacement, pool_id))
        packed_changed_ids.update(row.id for row in changed)
        audits.append({
            "id": pool_id,
            "scenario": pool[0].scenario,
            "start": f"0x{start:X}",
            "end_exclusive": f"0x{start + capacity:X}",
            "records": len(pool),
            "changed_records": [row.id for row in changed],
            "used_bytes": used,
            "capacity_bytes": capacity,
            "free_bytes": capacity - used,
            "record_order_preserved": True,
            "record_count_preserved": True,
        })
    return writes, audits, packed_changed_ids


def verify_final_pooled_records(
    records: list[DialogueRecord],
    texts: dict[str, str],
    source: bytes,
    final_image: bytes,
) -> dict:
    """Re-extract native ordinal populations after all product writers.

    A byte check at an inherited start misses inserted empty records.  Walk
    from the true aggregate start and require one NUL per intended record,
    with unused zero capacity only after the complete native population.
    """
    expected_writes, _audits, _ids = _plan_pooled_writes(records, texts, source)
    expected_by_start = {start: replacement for start, replacement, _ in expected_writes}
    checked = []
    for pool in contiguous_pools(records):
        start = pool[0].cooked_offset
        if start not in expected_by_start:
            continue
        expected = expected_by_start[start]
        actual = final_image[start:start + len(expected)]
        cursor = 0
        for row in pool:
            expected_end = expected.find(b"\0", cursor)
            actual_end = actual.find(b"\0", cursor)
            need(expected_end >= cursor, f"{row.id}: 생성 대사 종단 없음")
            need(actual_end == expected_end
                 and actual[cursor:actual_end] == expected[cursor:expected_end],
                 f"{row.id}: 최종 대사 순번/종단 불일치; 빈 레코드 삽입 또는 후속 덮어쓰기")
            cursor = expected_end + 1
        need(actual[cursor:] == expected[cursor:] == bytes(len(expected) - cursor),
             f"{pool[0].id}: 대사 묶음 뒤의 여유 공간 변경")
        checked.append({"first_id": pool[0].id, "last_id": pool[-1].id,
                        "records": len(pool), "start": f"0x{start:X}",
                        "used_bytes": cursor, "capacity_bytes": len(expected)})
    return {"pools": checked, "records_verified": sum(r["records"] for r in checked),
            "verified_after_last_writer": True}


def validate_project(
    records: list[DialogueRecord],
    texts: dict[str, str],
    base_folder: Path,
    progress: Callable[[str], None] | None = None,
) -> list[tuple[DialogueRecord, Validation]]:
    cooked, _raw, _cue = verify_base_folder(base_folder)
    image = cooked.read_bytes()
    results: list[tuple[DialogueRecord, Validation]] = []
    for index, record in enumerate(records):
        if progress and index % 100 == 0:
            progress(f"대사 검사 중… {index}/{len(records)}")
        text = texts.get(record.id, record.base_text)
        results.append((record, validate_record(record, text, image)))
    failures = [(row, result) for row, result in results if not result.ok]
    need(not failures, "\n".join(
        f"{row.id}: {'; '.join(result.errors)}" for row, result in failures[:20]
    ))
    # Scenario 2 exact aggregate capacity is checked with its real dictionary.
    if any(
        texts.get(row.id, row.base_text) != installed_text(row)
        for row in records if row.scenario == 2
    ):
        all_text = {row.id: texts.get(row.id, row.base_text) for row in records}
        _build_s2(bytearray(image), all_text)
    _plan_pooled_writes(records, texts, image)
    return results


def _repair_raw(
    cooked: Path,
    source_raw: Path,
    output_raw: Path,
    sectors: list[int],
) -> dict[str, int]:
    shutil.copyfile(source_raw, output_raw)
    source_raw_sectors = source_raw.stat().st_size // RAW_SECTOR
    source_cooked_sectors = source_raw_sectors - RAW_LEADIN
    output_cooked_sectors = cooked.stat().st_size // COOKED_SECTOR
    with output_raw.open("r+b") as target, cooked.open("rb") as source:
        existing = [value for value in sectors if value < source_cooked_sectors]
        for sector_index in existing:
            raw_index = RAW_LEADIN + sector_index
            target.seek(raw_index * RAW_SECTOR)
            sector = bytearray(target.read(RAW_SECTOR))
            need(len(sector) == RAW_SECTOR and cd_mode1.verify_mode1_sector(bytes(sector)),
                 f"원본 MODE1 섹터 오류: {raw_index}")
            source.seek(sector_index * COOKED_SECTOR)
            payload = source.read(COOKED_SECTOR)
            need(len(payload) == COOKED_SECTOR, "cooked 섹터 읽기 실패")
            sector[RAW_USER : RAW_USER + COOKED_SECTOR] = payload
            cd_mode1.repair_mode1_sector(sector)
            need(cd_mode1.verify_mode1_sector(bytes(sector)), f"MODE1 복구 실패: {raw_index}")
            target.seek(raw_index * RAW_SECTOR)
            target.write(sector)
        if output_cooked_sectors > source_cooked_sectors:
            target.seek((source_raw_sectors - 1) * RAW_SECTOR)
            template = bytearray(target.read(RAW_SECTOR))
            need(
                len(template) == RAW_SECTOR
                and cd_mode1.verify_mode1_sector(bytes(template)),
                "MODE1 추가 섹터 템플릿 오류",
            )
            target.seek(0, os.SEEK_END)
            for cooked_sector in range(source_cooked_sectors, output_cooked_sectors):
                sector = bytearray(template)
                minute, remainder = divmod(RAW_LEADIN + cooked_sector, 75 * 60)
                second, frame = divmod(remainder, 75)
                sector[12] = ((minute // 10) << 4) | (minute % 10)
                sector[13] = ((second // 10) << 4) | (second % 10)
                sector[14] = ((frame // 10) << 4) | (frame % 10)
                source.seek(cooked_sector * COOKED_SECTOR)
                payload = source.read(COOKED_SECTOR)
                need(len(payload) == COOKED_SECTOR, "추가 cooked 섹터 읽기 실패")
                sector[RAW_USER:RAW_USER + COOKED_SECTOR] = payload
                cd_mode1.repair_mode1_sector(sector)
                need(cd_mode1.verify_mode1_sector(bytes(sector)),
                     f"추가 MODE1 섹터 복구 실패: {cooked_sector}")
                target.write(sector)
        target.flush()
        os.fsync(target.fileno())
    need(
        output_raw.stat().st_size // RAW_SECTOR
        == output_cooked_sectors + RAW_LEADIN,
        "확장 raw/cooked 섹터 수가 맞지 않습니다.",
    )
    return {
        "existing_sectors_repaired": len(existing),
        "appended_sectors": output_cooked_sectors - source_cooked_sectors,
    }


def build_disc(
    records: list[DialogueRecord],
    texts: dict[str, str],
    base_folder: Path,
    output_folder: Path,
    progress: Callable[[str], None] | None = None,
) -> Path:
    cooked_source, raw_source, cue_source = verify_base_folder(base_folder)
    need(not output_folder.exists(), "출력 폴더가 이미 있습니다. 새 폴더를 지정하세요.")
    changed = [
        row for row in records
        if texts.get(row.id, row.base_text) != installed_text(row)
    ]
    need(bool(changed), "수정된 대사가 없습니다.")
    if progress:
        progress("전체 대사와 용량 검사 중…")
    validate_project(records, texts, base_folder, progress)

    source_image = cooked_source.read_bytes()
    image = bytearray(source_image)
    all_text = {row.id: texts.get(row.id, row.base_text) for row in records}
    writes: list[tuple[int, bytes, str]] = []
    s2_audit: dict | None = None
    early_dictionary_audit: dict | None = None
    early_font_audit: dict | None = None
    later_dictionary_audit: dict | None = None
    scenario01_dictionary_audit: dict | None = None
    resource12_expansion_audit: dict | None = None
    expansion_ranges: list[tuple[int, int]] = []

    if any(row.scenario != 2 for row in changed):
        import global_dialogue_storage

        image, resource12_expansion_audit, expansion_ranges = (
            global_dialogue_storage.expand_resource12(source_image)
        )
    if any(13 <= row.scenario <= 70 for row in changed):
        import global_dialogue_storage

        dictionary_writes, later_dictionary_audit = (
            global_dialogue_storage.plan_dictionary_writes(source_image)
        )
        writes.extend(dictionary_writes)
    if any(row.scenario == 1 for row in changed):
        import global_dialogue_storage

        dictionary_writes, scenario01_dictionary_audit = (
            global_dialogue_storage.plan_scenario01_dictionary_write(source_image)
        )
        writes.extend(dictionary_writes)

    if any(row.scenario == 2 for row in changed):
        s2_writes, s2_audit = _build_s2(image, all_text)
        writes.extend((offset, replacement, "scenario02/packed") for offset, replacement in s2_writes)

    pooled_writes, pooled_audit, pooled_changed_ids = _plan_pooled_writes(
        records, all_text, source_image
    )
    writes.extend(pooled_writes)

    if any(3 <= row.scenario <= 12 for row in changed):
        import global_dialogue_storage

        dictionary_writes, early_dictionary_audit = (
            global_dialogue_storage.plan_early_dictionary_writes(source_image)
        )
        writes.extend(dictionary_writes)

    if any(row.scenario != 2 for row in changed):
        import early_dialogue_font

        need(resource12_expansion_audit is not None,
             "전체 대사 글리프 설치 전 Resource-12 확장이 필요합니다.")
        font_writes, early_font_audit = early_dialogue_font.plan_writes(bytes(image))
        writes.extend(font_writes)

    latest_private = all_dialogue_private_mapping()
    s1_charset = load_json(s1inv.CHARSET)
    s1_dicts = s1_dictionary_texts(source_image, s1_charset)
    for record in changed:
        if record.scenario == 2:
            continue
        if record.id in pooled_changed_ids:
            continue
        text = all_text[record.id]
        if record.family == "scenario01-prefix":
            encoded, missing = s1inv.compressed_encode(
                engine_text(text), latest_private, s1_dicts, record.active_budget % 2
            )
            need(not missing, f"{record.id}: 지원하지 않는 글자 {missing}")
            need(len(encoded) <= record.active_budget, f"{record.id}: 용량 초과")
            padding = record.active_budget - len(encoded)
            replacement = bytearray(encoded)
            if padding & 1:
                # 0x05 is the native one-byte no-op already accepted by this
                # text engine and avoids rejecting an otherwise valid edit
                # solely because its compressed length has opposite parity.
                replacement.append(0x05)
                padding -= 1
            replacement.extend(b"\x81\x40" * (padding // 2))
            replacement = bytes(replacement)
        else:
            encoded = encode_for_record(record, text, source_image)
            replacement = fixed_record(encoded, record.allocation)
        need(record.cooked_offset is not None, f"{record.id}: 오프셋 없음")
        writes.append((record.cooked_offset, replacement, record.id))

    writes.sort(key=lambda row: row[0])
    for left, right in zip(writes, writes[1:]):
        need(left[0] + len(left[1]) <= right[0], f"쓰기 범위 중복: {left[2]} / {right[2]}")
    changed_offsets: set[int] = set()
    if expansion_ranges:
        header_start, header_size = expansion_ranges[0]
        changed_offsets.update(
            header_start + index
            for index, (old, new) in enumerate(zip(
                source_image[header_start:header_start + header_size],
                image[header_start:header_start + header_size],
            ))
            if old != new
        )
    for offset, replacement, record_id in writes:
        before = bytes(image[offset : offset + len(replacement)])
        need(len(before) == len(replacement), f"{record_id}: 이미지 범위 초과")
        image[offset : offset + len(replacement)] = replacement
        changed_offsets.update(
            offset + index
            for index, (old, new) in enumerate(zip(before, replacement))
            if old != new
        )
    need(bool(changed_offsets), "선택한 수정이 실제 바이트 변경을 만들지 않았습니다.")

    output_folder.mkdir(parents=True)
    output_stem = output_folder.name
    cooked_out = output_folder / f"track02-{output_stem}.iso"
    raw_out = output_folder / f"Track-2.{output_stem}.bin"
    cue_out = output_folder / f"Langrisser-FX-KR-{output_stem}.cue"
    if progress:
        progress("cooked 이미지 기록 중…")
    cooked_out.write_bytes(image)
    sector_set = {offset // COOKED_SECTOR for offset in changed_offsets}
    for start, size in expansion_ranges:
        sector_set.update(range(
            start // COOKED_SECTOR,
            (start + size - 1) // COOKED_SECTOR + 1,
        ))
    sectors = sorted(sector_set)
    if progress:
        progress(f"MODE1 섹터 복구 중… {len(sectors)}개")
    raw_audit = _repair_raw(cooked_out, raw_source, raw_out, sectors)
    for name in ("Track-1.bin", "Track-3.bin"):
        shutil.copyfile(base_folder / name, output_folder / name)
    cue_text = cue_source.read_text(encoding="ascii")
    cue_text = cue_text.replace(raw_source.name, raw_out.name)
    cue_out.write_text(cue_text, encoding="ascii", newline="")

    for sector_index in sectors:
        with raw_out.open("rb") as stream:
            stream.seek((RAW_LEADIN + sector_index) * RAW_SECTOR)
            sector = stream.read(RAW_SECTOR)
        need(cd_mode1.verify_mode1_sector(sector), f"출력 MODE1 검증 실패: {sector_index}")
    report = {
        "schema": "langrisser-fx-dialogue-editor-build/v1",
        "status": "BUILT_STATIC_QA_PASS_RUNTIME_REQUIRED",
        "release_allowed": False,
        "runtime_verified": False,
        "base": {"stem": BASE_STEM, "sha256": BASE_HASHES[BASE_COOKED_NAME]},
        "changed_records": len(changed),
        "changed_record_ids": [row.id for row in changed],
        "changed_cooked_bytes": len(changed_offsets),
        "changed_cooked_sectors": len(sectors),
        "scenario02": s2_audit,
        "scenario03_12_private_dictionaries": early_dictionary_audit,
        "scenario03_12_unique_glyph_extension": early_font_audit,
        "scenario01_private_dictionary": scenario01_dictionary_audit,
        "scenario13_70_private_dictionaries": later_dictionary_audit,
        "resource12_expansion": resource12_expansion_audit,
        "raw_geometry": raw_audit,
        "semantic_abbreviations": 0,
        "shared_dialogue_pools": pooled_audit,
        "outputs": {
            "cue": {"path": cue_out.name, "sha256": sha256_file(cue_out)},
            "cooked": {"path": cooked_out.name, "sha256": sha256_file(cooked_out)},
            "raw": {"path": raw_out.name, "sha256": sha256_file(raw_out)},
        },
        "note": "개인 대사 수정용 개발 빌드. 에뮬레이터 실기 확인 전 배포 금지.",
    }
    (output_folder / "dialogue-editor-build-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if progress:
        progress("빌드 완료")
    return cue_out


def suggested_output_folder() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return ROOT / "work" / f"dialogue-custom-{stamp}"
