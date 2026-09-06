#!/usr/bin/env python3
"""Repeatable static self-test for the dialogue editor."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import tempfile

import dialogue_core as core
import condition_core as condition_core
import dialogue_editor as editor_ui
import epilogue_core as epilogue_core
import narration_core as narration_core
import missing_presentations
import project_core as project_core
import subtitle_core as subtitle_core


def streamed_differences(left: Path, right: Path) -> list[int]:
    differences: list[int] = []
    position = 0
    with left.open("rb") as a, right.open("rb") as b:
        while True:
            left_chunk = a.read(4 << 20)
            right_chunk = b.read(4 << 20)
            if not left_chunk and not right_chunk:
                break
            assert len(left_chunk) == len(right_chunk), "image length differs"
            differences.extend(
                position + index
                for index, (old, new) in enumerate(zip(left_chunk, right_chunk))
                if old != new
            )
            position += len(left_chunk)
    return differences


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--smoke-output",
        type=Path,
        help="optional previously built smoke-test folder",
    )
    args = parser.parse_args()

    records = core.load_records()
    base_image = (core.BASE_DIR / core.BASE_COOKED_NAME).read_bytes()
    # Scenario 3 wall detail uses native tile 0x72C.  SYSTEM MENU previously
    # uploaded one private glyph to that same tile and left the lower-left HUD
    # thumbnail corrupted after returning to the field.  Every Slot-A replica
    # must keep the menu glyph on its independent 0xED6 owner.
    slot_offsets = (
        0x0192AE08, 0x019AEE08,
        0x2731FE08, 0x273ABE08,
        0x2742A608, 0x274BE608,
        0x27549E08, 0x275FDE08,
    )
    expected_slot_sha256 = (
        "84B9583F1AC2F862123C8CC6B2AC3CC6EB482CA77E6B7FAB4A79B137C3BE73E8"
    )
    for offset in slot_offsets:
        slot = base_image[offset:offset + 1024]
        assert hashlib.sha256(slot).hexdigest().upper() == expected_slot_sha256
        codes = struct.unpack_from("<66H", slot, 48)
        assert len(codes) == len(set(codes)) == 66
        assert codes[55] == 0xED6 and 0x72C not in codes
        assert struct.unpack_from("<H", slot, 0x26C)[0] == 0x4ED6
    # Fifteen source-extract tail rows physically belong to the dedicated
    # system-menu condition tables and are intentionally excluded here.
    assert len(records) == 9508
    assert {row.scenario for row in records} == set(range(1, 71))
    assert not any(core.script_residuals(row.base_text) for row in records)
    by_id = {row.id: row for row in records}
    core.validate_project(records, {}, core.BASE_DIR)
    latest_private = core.latest_private_mapping()
    early_private = core.early_private_mapping()
    scenario02_private, scenario02_phrases = core._s2_encoding_resources()
    assert latest_private["울"] == bytes.fromhex("F272")
    assert len(latest_private) == len(set(latest_private.values()))
    assert len(early_private) == len(set(early_private.values()))
    assert len(scenario02_private) == len(set(scenario02_private.values()))
    assert latest_private[" "] != latest_private["\u2009"]
    assert early_private[" "] != early_private["\u2009"]
    assert scenario02_private[" "] != scenario02_private["\u2009"]
    assert not (
        core.S2_CONDITION_EXCLUSIVE_CODES & set(scenario02_phrases.values())
    )
    # The literal event stays in the one native ordinal population.  Splitting
    # it into fixed-address slots inserted empty bodies on the actual SRAM.
    assert core.SUSPEND_RESUME_LITERAL_DIALOGUE_IDS == {
        f"scenario03/dialogue/{index:03d}" for index in range(46, 52)
    }
    for record_id in core.SUSPEND_RESUME_LITERAL_DIALOGUE_IDS:
        literal_row = by_id[record_id]
        expected_literal, missing = core.encode_plain(
            literal_row.base_text, early_private
        )
        assert not missing
        assert core.encode_for_record(
            literal_row, literal_row.base_text, base_image
        ) == expected_literal
    scenario3_pools = [
        pool for pool in core.contiguous_pools(records)
        if pool[0].scenario == 3
    ]
    assert len(scenario3_pools) == 1
    assert len(scenario3_pools[0]) == 229
    pooled, _, _ = core._plan_pooled_writes(records, {}, base_image)
    planned_image = bytearray(base_image)
    for start, payload, _ in pooled:
        planned_image[start:start + len(payload)] = payload
    assert core.verify_final_pooled_records(records, {}, base_image, bytes(planned_image))["records_verified"] > 229
    s3_start = scenario3_pools[0][0].cooked_offset
    s3_cursor = s3_start
    for _ in range(46):
        s3_cursor = planned_image.index(0, s3_cursor) + 1
    planned_image[s3_cursor] = 0
    try:
        core.verify_final_pooled_records(records, {}, base_image, bytes(planned_image))
    except core.DialogueError as exc:
        assert "scenario03/dialogue/046" in str(exc)
    else:
        raise AssertionError("Inserted native empty record was accepted")
    scenario1 = [row for row in records if row.scenario == 1]
    assert len(scenario1) == 190
    assert all(row.active_budget + 1 == row.allocation for row in scenario1)
    # Successor244 reflows every portrait row while preserving the extracted
    # source's native voice-page count.  Visual-only pages and punctuation or
    # word fragments stranded at the beginning of a continuation line are
    # forbidden.
    scenario1_reflow_ids = {
        "scenario01/dialogue/006",
        "scenario01/dialogue/047",
        "scenario01/dialogue/090",
        "scenario01/dialogue/091",
        "scenario01/dialogue/103",
        "scenario01/dialogue/153",
        "scenario01/dialogue/171",
    }
    pre_layout = {
        row.id: row for row in core.load_records(apply_layout_reflow=False)
    }
    portrait_rows = [row for row in records if core.is_portrait_dialogue(row)]
    assert len(portrait_rows) == 9505
    for row in portrait_rows:
        assert "{visual}" not in row.base_text
        assert (
            core.engine_text(row.base_text).count("\f")
            == core.engine_text(
                row.source_text.replace("\\n", "\n").replace("\\f", "\f")
            ).count("\f")
        )
        assert not core.portrait_layout_inspection(row.base_text)["failures"]
        continuation_lines = [
            line.lstrip()
            for page_index, page in enumerate(
                core.engine_text(row.base_text).split("\f")
            )
            for line_index, line in enumerate(page.splitlines())
            if line_index > 0 and line.lstrip()
        ]
        assert not any(
            line[0] in ",.!?，。！？、;:；：…‥"
            for line in continuation_lines
        )
        source_pages = core.engine_text(
            row.source_text.replace("\\n", "\n").replace("\\f", "\f")
        ).split("\f")
        for page_index, page in enumerate(
            core.engine_text(row.base_text).split("\f")
        ):
            first = page.lstrip()
            if page_index and first and first[0] in ",.!?，。！？、;:；：…‥":
                assert source_pages[page_index].lstrip()[0] in (
                    ",.!?，。！？、;:；：…‥"
                )
    for record_id in scenario1_reflow_ids:
        row = by_id[record_id]
        assert "{visual}" not in row.base_text
        assert row.base_text.count("{page}") == pre_layout[record_id].base_text.count("{page}")
        assert not core.portrait_layout_inspection(row.base_text)["failures"]
    assert by_id["scenario01/dialogue/006"].base_text == (
        "서두릅시다. 이대로 가면\n"
        "영주가 병사를 이끌고\n"
        "나타날지도 모릅니다."
    )
    # The current base's real NUL boundary is authoritative.  A replacement
    # larger than that current per-record allocation proves that it can still
    # borrow safely from the preserved Scenario-1 aggregate span.
    recovered = by_id["scenario01/dialogue/147"]
    assert recovered.allocation > 1
    # Preserve the original page boundary while proving that this record can
    # still borrow from the Scenario-1 aggregate span.  Page parity is part of
    # the voice-timing contract and an old newline-only fixture is invalid.
    recovered_text = "가" * 7 + "\n" + "가" * 7 + "{page}" + "가" * 7
    recovered_result = core.validate_record(
        recovered,
        recovered_text,
        (core.BASE_DIR / core.BASE_COOKED_NAME).read_bytes(),
    )
    assert recovered_result.ok
    assert recovered_result.encoded_bytes > recovered.active_budget

    # Scenario 1 now borrows safely inside the same contiguous catalogue run,
    # so an individual record may exceed its old Japanese slot while the run
    # start/end, record order and record count remain fixed.
    s1_pooled = by_id["scenario01/dialogue/000"]
    s1_borrowed = s1_pooled.base_text + "\n" + "가" * 8 + "\n" + "가" * 8
    s1_borrowed_result = core.validate_record(
        s1_pooled,
        s1_borrowed,
        (core.BASE_DIR / core.BASE_COOKED_NAME).read_bytes(),
    )
    assert s1_borrowed_result.ok
    assert s1_borrowed_result.capacity == -1
    assert s1_borrowed_result.encoded_bytes > s1_pooled.active_budget
    core.validate_project(records, {s1_pooled.id: s1_borrowed}, core.BASE_DIR)

    edits: dict[str, str] = {}
    for record_id in (
        "scenario01/dialogue/000",
        "scenario02/dialogue/003",
        "scenario03/dialogue/004",
        "scenario13/aftermath-a/asks-if-defeated",
    ):
        row = by_id[record_id]
        # Keep the edit width-neutral: the editor now rejects even a one-glyph
        # append when a line already occupies the 168px safe dialogue width.
        match = re.search(r"[가-힣]", row.base_text)
        assert match is not None
        replacement = "나" if match.group(0) != "나" else "가"
        edits[record_id] = (
            row.base_text[: match.start()]
            + replacement
            + row.base_text[match.end() :]
        )
    core.validate_project(records, edits, core.BASE_DIR)

    row = by_id["scenario03/dialogue/004"]
    assert not core.validate_record(row, row.base_text + "뷁").ok
    page_changed = row.base_text.replace("{page}", "\n", 1)
    page_result = core.validate_record(row, page_changed)
    assert not page_result.ok
    assert any("페이지 구분 수" in error for error in page_result.errors)
    five_lines = "가\n가\n가\n가\n가" + ("{page}" if "{page}" in row.base_text else "")
    five_line_result = core.validate_record(row, five_lines)
    assert not five_line_result.ok
    assert any("첫 화면 3줄·이후 4줄·168px" in error
               for error in five_line_result.errors)
    residual_result = core.validate_record(row, row.base_text + "漢")
    assert not residual_result.ok
    assert any("일본어·한자 잔존" in error for error in residual_result.errors)
    pooled = by_id["scenario13/aftermath-a/asks-if-defeated"]
    # Borrow beyond this record's native slot while keeping both rendered
    # lines inside the current 168px dialogue limit.
    borrowed = pooled.base_text + "\n" + "가" * 3
    borrowed_result = core.validate_record(pooled, borrowed)
    assert borrowed_result.ok
    assert borrowed_result.encoded_bytes > pooled.active_budget
    core.validate_project(records, {pooled.id: borrowed}, core.BASE_DIR)
    aggregate_overflow = pooled.base_text + "\n가" * 5000
    try:
        core._plan_pooled_writes(
            records,
            {pooled.id: aggregate_overflow},
            (core.BASE_DIR / core.BASE_COOKED_NAME).read_bytes(),
        )
    except core.DialogueError as exc:
        assert "묶음 전체 용량" in str(exc)
    else:
        raise AssertionError("aggregate pool overflow was not rejected")
    token_row = next(
        item
        for item in records
        if item.scenario >= 3 and re.search(r"\{name:[0-9A-Fa-f]{2}\}", item.base_text)
    )
    token_removed = re.sub(
        r"\{name:[0-9A-Fa-f]{2}\}", "", token_row.base_text, count=1
    )
    token_result = core.validate_record(token_row, token_removed)
    assert not token_result.ok
    assert any("토큰" in error for error in token_result.errors)

    page_voice_parity = by_id["scenario02/dialogue/000"]
    assert core.validate_record(page_voice_parity, page_voice_parity.base_text).ok
    page_voice_mismatch = core.validate_record(
        page_voice_parity,
        page_voice_parity.base_text.replace("{page}", "\n", 1),
    )
    assert not page_voice_mismatch.ok
    assert any("일본판 원문" in error for error in page_voice_mismatch.errors)

    legacy_control_mismatch = by_id["scenario01/dialogue/056"]
    legacy_control_result = core.validate_record(
        legacy_control_mismatch,
        legacy_control_mismatch.base_text + "{raw:05}",
    )
    assert not legacy_control_result.ok
    assert any("제어 토큰" in error for error in legacy_control_result.errors)

    with tempfile.TemporaryDirectory(prefix="langrisser-dialogue-editor-") as temporary:
        project = Path(temporary) / "edits.json"
        core.save_project(project, records, edits)
        assert core.load_project(project, records) == edits

    subtitle_rows = subtitle_core.load_subtitle_cues()
    assert len(subtitle_rows) == 150
    assert len({row.movie_id for row in subtitle_rows}) == 23
    first_subtitle = subtitle_rows[0]
    subtitle_edit = {
        first_subtitle.id: {
            "start": first_subtitle.start + 1 / 60,
            "end": first_subtitle.end,
            "ko": list(first_subtitle.ko),
        }
    }
    changed_subtitles = subtitle_core.apply_subtitle_edits(
        subtitle_rows, subtitle_edit
    )
    assert changed_subtitles[0].start != first_subtitle.start
    assert len({row.id for row in changed_subtitles}) == len(changed_subtitles)
    narration_rows = narration_core.load_narration_records()
    source_frame_kinds = condition_core.source_frame_kinds()
    source_presentation_count = len(source_frame_kinds)
    narration_filters = editor_ui.narration_filter_values(narration_rows)
    assert len(narration_filters) == source_presentation_count + 1
    assert narration_filters[0] == "전체"
    assert len(set(narration_filters[1:])) == source_presentation_count
    assert {"시나리오 1", "시나리오 70"} <= set(narration_filters)
    assert all(
        any(row.label == label for row in narration_rows)
        for label in narration_filters[1:]
    )
    source_narration_count = sum(
        kind == "narration" for kinds in condition_core.source_frame_kinds().values() for kind in kinds
    )
    assert len(narration_rows) == source_narration_count
    assert len({row.label for row in narration_rows}) == source_presentation_count
    assert {
        row.scenario for row in narration_rows if row.scenario is not None
    } == set(range(1, 71))
    narration_labels = {row.label for row in narration_rows}
    assert {
        f"시나리오 {scenario}" for scenario in range(1, 71)
    } <= narration_labels
    # The UI filter is label-based.  Keep representative scenarios selectable
    # instead of silently collapsing them into the aggregate presentations.
    assert sum(row.label == "시나리오 1" for row in narration_rows) == 7
    assert sum(row.label == "시나리오 2" for row in narration_rows) == 4
    assert sum(row.label == "시나리오 3" for row in narration_rows) == 4
    assert sum(row.label == "시나리오 12" for row in narration_rows) == 3
    assert sum(row.label == "시나리오 70" for row in narration_rows) == 4
    narration_map = narration_core.narration_mapping()
    assert len(narration_map) == len(set(narration_map.values()))
    assert narration_map[" "] != narration_map["\u2009"]
    assert narration_map["톨"] == bytes.fromhex("F75D")
    narration_translation_document = core.load_json(
        narration_core.TRANSLATIONS
    )
    adopted_narration_texts = {**narration_translation_document["records"],
                               **missing_presentations.draft()['narrations']}
    assert len(adopted_narration_texts) == source_narration_count
    assert set(adopted_narration_texts) == {
        row.id for row in narration_rows
    }
    assert {
        row.scenario for row in narration_rows
        if row.id in adopted_narration_texts and row.scenario is not None
    } == set(range(1, 71))
    narration_layout_document = core.load_json(
        narration_core.READABILITY_LAYOUT_OVERRIDES
    )
    narration_layout_overrides = narration_layout_document["records"]
    assert narration_layout_document["status"] == "reviewed-for-layout"
    assert set(narration_layout_overrides) <= {
        row.id for row in narration_rows
    }
    narration_capacity_document = core.load_json(
        narration_core.READABILITY_CAPACITY_EXCEPTIONS
    )
    narration_capacity_exceptions = narration_capacity_document["records"]
    assert narration_capacity_document["status"] == "reviewed-for-layout"
    assert set(narration_capacity_exceptions) <= {
        row.id for row in narration_rows
    }
    for row in narration_rows:
        if row.id not in adopted_narration_texts:
            continue
        working_text = narration_capacity_exceptions.get(
            row.id, adopted_narration_texts[row.id]
        )
        generated = narration_core.reflow_narration_text(
            working_text, record=row
        )
        assert row.base_text == narration_layout_overrides.get(row.id, generated)
        assert re.sub(r"\s+", "", row.base_text) == re.sub(
            r"\s+", "", working_text
        )
        assert len(row.base_text.splitlines()) <= narration_core.NARRATION_MAX_LINES
        assert max(narration_core.narration_line_widths(row.base_text)) <= (
            narration_core.NARRATION_SAFE_WIDTH_PX
        )
    adopted_narration_count = sum(
        row.base_text != row.disc_text for row in narration_rows
    )
    assert adopted_narration_count > 0
    assert "scenario12/narration/003" in {
        row.id for row in narration_rows
    }
    assert "scenario12/narration/003" in adopted_narration_texts
    assert not narration_translation_document.get("excluded_records")
    assert not any(
        core.script_residuals(row.base_text)
        for row in narration_rows
    )
    narration_test_row = next(
        row for row in narration_rows if row.scenario == 1
    )
    # Exercise the shared Scenario-1 narration/condition presentation with a
    # valid Korean edit.  The editable baseline is now translated for all 70
    # scenarios; the Japanese source remains separately available for review.
    narration_edit = {
        narration_test_row.id: "빛의 대신전으로 향했다！"
    }
    narration_core.validate_narration_project(narration_edit)
    base_image = (core.BASE_DIR / core.BASE_COOKED_NAME).read_bytes()
    adopted_only_patches, adopted_only_audit = (
        narration_core.build_narration_patches(
            base_image, {}, require_runtime_dictionary=False
        )
    )
    assert adopted_only_patches
    assert adopted_only_audit["adopted_records"] == adopted_narration_count
    # Scenario 3-12 are rebuilt even when semantically unchanged so their
    # narration bytes no longer depend on mutable field-dialogue dictionaries.
    assert adopted_only_audit["edited_records"] == source_narration_count
    assert adopted_only_audit["user_edited_records"] == 0
    assert adopted_only_audit["changed_presentations"] == source_presentation_count
    assert adopted_only_audit["semantic_abbreviations"] == 0
    assert all(
        row.get("semantic_abbreviation") in (None, False)
        for row in adopted_only_audit["patches"]
    )
    assert all(
        row["semantic_abbreviation"] is False
        and row["dictionary_roundtrip_records"] >= 1
        for row in adopted_only_audit["patches"]
        if row["lossless_local_dictionary"] is True
    )
    assert all(
        "0x1A" in row["dictionary_preserved_codes"]
        for row in adopted_only_audit["patches"]
        if 3 <= row["presentation_index"] <= 70
        and row["lossless_local_dictionary"] is True
    )
    narration_patches, narration_audit = narration_core.build_narration_patches(
        base_image, narration_edit, require_runtime_dictionary=False
    )
    assert narration_patches
    assert narration_audit["records"] == source_narration_count
    assert narration_audit["presentations"] == source_presentation_count
    assert narration_audit["adopted_records"] == adopted_narration_count
    assert narration_audit["user_edited_records"] == 1
    assert narration_audit["changed_presentations"] == source_presentation_count
    assert narration_audit["semantic_abbreviations"] == 0
    assert narration_audit["glyph_aliases"] == 0
    assert narration_audit["space_owners_distinct"] is True
    condition_rows = condition_core.load_condition_records()
    source_conditions = sum(kind.endswith('condition') for kinds in source_frame_kinds.values() for kind in kinds)
    assert len(condition_rows) == source_conditions + 194
    scenario12_condition = next(
        row for row in condition_rows
        if row.id == "presentation012/condition/victory"
    )
    assert scenario12_condition.frame_index == 3
    for condition_kind in ('victory-condition', 'defeat-condition'):
        assert sum(row.kind == condition_kind for row in condition_rows) == sum(
            kind == condition_kind for kinds in source_frame_kinds.values() for kind in kinds)
    assert sum(row.kind == "menu-condition" for row in condition_rows) == 194
    assert {
        row.scenario for row in condition_rows if row.scenario is not None
    } == set(range(1, 71))
    assert not any(
        condition_core._script_residuals(row.base_text)
        for row in condition_rows
    )
    assert condition_core.global_condition_mapping()["래"] == bytes.fromhex(
        "F163"
    )
    assert condition_core.global_condition_mapping()["토"] == bytes.fromhex(
        "F0DC"
    )
    assert "아래로" in next(
        row.base_text for row in condition_rows
        if row.id == "presentation001/condition/defeat"
    )
    condition_by_id = {row.id: row for row in condition_rows}
    assert condition_core.CONDITION_INTERIOR_TILES == 22
    assert condition_core.MAX_WIDTH_PX == 176
    assert condition_core.condition_line_widths("{raw:05}・적 전멸") == [56]
    condition_mapping = condition_core.condition_mapping(3)
    assert condition_core.encode_condition_glyph("･", condition_mapping) == bytes.fromhex("8145")
    assert condition_core.encode_condition_glyph("・", condition_mapping) == bytes.fromhex("8145")
    for character in "NPC19/":
        assert len(condition_core.encode_condition_glyph(character, condition_mapping)) == 2
    s3_defeat = condition_by_id["presentation003/condition/defeat"]
    s3_defeat_bytes = condition_core.validate_condition_text(s3_defeat, s3_defeat.base_text)
    assert condition_core.condition_layout_text(s3_defeat.base_text) == (
        " ・엘윈 사망\n ・사제, 신관 전멸\n ・리아나 사망")
    assert all(line.startswith(bytes.fromhex("F1E88145"))
               for line in s3_defeat_bytes.split(b"\x08"))
    assert b"\x05" not in s3_defeat_bytes
    assert condition_core.condition_layout_text(
        "{raw:05}・엘윈 사망\n{raw:05}　・리아나 사망\n{raw:05}　도착\n＊패배조건"
    ) == " ・엘윈 사망\n ・리아나 사망\n    도착\n＊패배조건"
    assert condition_core.condition_display_line_widths("・적 전멸") == [56]
    assert condition_core.condition_frame_prefix(s3_defeat) == bytes.fromhex("041D08")
    assert bytes.fromhex("8145F15BF0E9") in s3_defeat_bytes
    assert bytes.fromhex("8145F04FF06CF05D") in s3_defeat_bytes
    for broken in (bytes.fromhex("A5F15BF0E905"), b"NPC", b"19"):
        try:
            condition_core.native_codec.units(broken)
        except ValueError:
            pass
        else:
            raise AssertionError("Native condition scanner accepted single-byte glyphs")
    misleading_rows = (bytes.fromhex("8145F15BF0E9"), bytes.fromhex("F04FF06CF05D"))
    literal_names = bytes.fromhex("8145F15BF0E9088145F04FF06CF05D")
    compressed_names = condition_core.native_codec.compress(literal_names, misleading_rows)
    assert condition_core.native_codec.expand(compressed_names, misleading_rows) == literal_names
    scenario59_victory = condition_by_id[
        "presentation059/condition/victory"
    ]
    assert scenario59_victory.base_text == (
        "・리아나만 남기고 전원 격파\n{raw:05}・소니아를 리아나에 붙이기"
    )
    assert max(condition_core.condition_line_widths(
        scenario59_victory.base_text
    )) <= condition_core.MAX_WIDTH_PX
    scenario66_victory = condition_by_id[
        "presentation066/condition/victory"
    ]
    assert scenario66_victory.base_text == (
        "・２０턴 이내\n{name:0D}와 {name:0E}\n격파"
    )
    assert max(
        width
        for width in condition_core.condition_line_widths(
            scenario66_victory.base_text
        )
    ) <= condition_core.MAX_WIDTH_PX
    condition_edit = {
        "presentation066/condition/victory":
            "・２０턴 이내\n{name:0D}와 {name:0E} 격파"
    }
    condition_core.validate_condition_project(condition_edit)
    try:
        condition_core.validate_condition_text(
            condition_by_id["presentation002/condition/victory"],
            "{raw:05}・" + "가" * 14,
        )
    except core.DialogueError as exc:
        assert "176px" in str(exc)
    else:
        raise AssertionError("Condition 176 px limit was not enforced")
    condition_patches, condition_audit = (
        condition_core.build_condition_patches(condition_edit)
    )
    # The pinned editor base predates the complete 1~70 condition adoption.
    # Rebuild every adopted presentation plus the explicit Scenario-66 edit.
    assert condition_patches
    assert condition_audit["changed_records"] == source_conditions
    assert condition_audit["changed_presentation_records"] == source_conditions
    assert condition_audit["changed_menu_tables"] == 68
    assert condition_audit["repaired_menu_records"] == 194
    for state in condition_core.plan_menu_condition_states(condition_edit):
        assert state.extension_bytes >= 0 and state.extension_bytes % 4 == 0
        assert state.target_section7_relative == state.base_section7_relative + state.extension_bytes
        assert len(state.base_block) == len(state.target_block) == state.allocation
    assert condition_audit["menu_body_dictionary_tokens"] == 0
    expected_condition_mapping = {**condition_core.global_condition_mapping(),
                                  **{ch:core.all_dialogue_private_mapping()[ch] for ch in ('김','출')}}
    assert condition_core.condition_mapping(3) == expected_condition_mapping
    # These two established Resource-12 owners are intentional: F2C2/F2C3
    # belong to AV menu 증/점 and cannot also encode condition 출/김.
    assert {
        ch: code for ch, code in condition_core.condition_mapping(3).items()
        if 0xF4 <= code[0] <= 0xF7
    } == {ch: core.all_dialogue_private_mapping()[ch] for ch in ('김', '출')}
    assert condition_audit["scenario_01_70_covered"] == 70
    assert condition_audit["glyph_aliases"] == 0
    assert condition_audit[
        "scenario02_exclusive_codes_in_edited_body"
    ] == 0
    s2_condition = condition_by_id["presentation002/condition/victory"]
    try:
        condition_core.validate_condition_text(
            s2_condition, s2_condition.base_text + "{dict:01}"
        )
    except core.DialogueError as exc:
        assert "전용코드 재사용 금지" in str(exc)
    else:
        raise AssertionError("Scenario-2 condition code reuse was not rejected")
    s3_menu_enemy = condition_by_id["scenario03/menu-condition/003"]
    assert s3_menu_enemy.source_text == "{dict:0D}"
    assert s3_menu_enemy.base_text == " ・적 전멸"
    assert condition_core.encode_menu_condition_text(
        s3_menu_enemy, s3_menu_enemy.base_text
    ) == bytes.fromhex("F1E88145F0D6F1E8F0A4F1BF")
    try:
        condition_core.validate_condition_text(s3_menu_enemy, "{dict:0D}")
    except core.DialogueError as exc:
        assert "공용 문구 재사용 금지" in str(exc)
    else:
        raise AssertionError("System-menu dictionary reuse was not rejected")

    # Scenario 1 conditions and narration share one 658-byte presentation
    # aggregate.  Conditions are compiled first; rebuilding narration must
    # retain the condition frame byte-for-byte rather than restoring the base.
    scenario1_condition_edit = {
        "presentation001/condition/victory": "・발드\n격파"
    }
    scenario1_patches, _scenario1_audit = (
        condition_core.build_condition_patches(scenario1_condition_edit)
    )
    assert scenario1_patches
    scenario1_offset, after_condition, _patch_id = next(
        patch for patch in scenario1_patches
        if patch[2] == "conditions/presentation-001"
    )
    composed_image = bytearray(base_image)
    composed_image[
        scenario1_offset:scenario1_offset + len(after_condition)
    ] = after_condition
    composed_patches, composed_audit = narration_core.build_narration_patches(
        composed_image,
        narration_edit,
        require_runtime_dictionary=False,
    )
    assert composed_patches
    narration_offset, composed, _narration_patch_id = next(
        patch for patch in composed_patches
        if patch[2] == "narrations/presentation-001"
    )
    assert narration_offset == scenario1_offset
    after_condition_frames, _suffix = condition_core.split_frames(after_condition)
    composed_frames, _composed_suffix = condition_core.split_frames(composed)
    assert composed_frames[8] == after_condition_frames[8]
    assert next(
        row for row in composed_audit["patches"]
        if row["presentation_index"] == 1
    )["condition_frames_preserved"] is True

    epilogue_rows = epilogue_core.load_epilogue_records()
    assert len(epilogue_rows) == 134
    assert epilogue_rows[0].id == "ending-epilogue/000"
    assert epilogue_rows[-1].id == "ending-epilogue/133"
    assert all(row.id.startswith("ending-epilogue/") for row in epilogue_rows)
    assert not any("aftermath" in row.id for row in epilogue_rows)
    assert not any(
        "death" in row.id.lower() or "사망" in row.id
        for row in epilogue_rows
    )
    assert len(epilogue_core.TABLE_OFFSETS) == 5
    first_epilogue = epilogue_rows[0]
    epilogue_edit = {
        first_epilogue.id: "헤인은\n마법사로\n살았다."
    }
    epilogue_core.validate_epilogue_project(epilogue_edit)
    epilogue_patches, epilogue_audit = epilogue_core.build_epilogue_patches(
        base_image, epilogue_edit
    )
    assert len(epilogue_patches) == 5
    assert len({replacement for _offset, replacement, _id in epilogue_patches}) == 1
    assert epilogue_audit["glyph_aliases"] == 0
    assert epilogue_audit["physical_tables"] == 5
    assert epilogue_audit["dictionary_patches"] == 0
    assert epilogue_audit["table_patches"] == 5
    with tempfile.TemporaryDirectory(prefix="langrisser-translation-editor-") as temporary:
        temporary_path = Path(temporary)
        rejected_project = temporary_path / "too-wide.json"
        try:
            project_core.save_project(
                rejected_project,
                records,
                {"scenario03/dialogue/004": "가" * 18},
                {},
                {},
                {},
                {},
            )
        except core.DialogueError as exc:
            assert "168px 규칙 위반" in str(exc)
            assert "advance=216" in str(exc)
            assert not rejected_project.exists()
        else:
            raise AssertionError("save accepted a dialogue line over 168 px")
        project = temporary_path / "edits-v2.json"
        project_core.save_project(
            project,
            records,
            edits,
            subtitle_edit,
            narration_edit,
            condition_edit,
            epilogue_edit,
        )
        loaded = project_core.load_project(project, records)
        assert loaded.dialogue_edits == edits
        assert set(loaded.subtitle_edits) == {first_subtitle.id}
        assert loaded.subtitle_edits[first_subtitle.id]["start"] == round(
            first_subtitle.start + 1 / 60, 3
        )
        assert loaded.subtitle_edits[first_subtitle.id]["ko"] == list(
            first_subtitle.ko
        )
        assert loaded.narration_edits == narration_edit
        assert loaded.condition_edits == condition_edit
        assert loaded.epilogue_edits == epilogue_edit
        payload, _patches, subtitle_audit = subtitle_core.build_payload(
            subtitle_rows, temporary_path / "subtitle-preview.png"
        )
        accepted_payload = project_core.extract_subtitle_payload(
            project_core.DEFAULT_FXB
        )
        # successor207 intentionally changes the resident renderer: natural
        # playback must clear/fill BG1 with a dedicated transparent tile
        # instead of descriptor zero, which can expose stale field-map CG.
        assert payload != accepted_payload
        assert subtitle_audit["private_bg1_blank_tile"] == "0x15A"
        assert subtitle_audit["unique_characters"] == 309
        assert subtitle_audit["unique_private_glyphs"] == 309
        assert subtitle_audit["glyph_aliases"] == 0
        assert subtitle_audit["resident_font_reuse"] is False
        rebuilt_fxb, fxb_audit = project_core.replace_subtitle_payload(
            project_core.DEFAULT_FXB, payload
        )
        assert rebuilt_fxb != project_core.DEFAULT_FXB.read_bytes()
        rebuilt_path = temporary_path / "subtitle-private-blank.fxb"
        rebuilt_path.write_bytes(rebuilt_fxb)
        assert project_core.extract_subtitle_payload(rebuilt_path) == payload
        assert fxb_audit["changes_outside_owned_ranges"] == 0
        assert fxb_audit["aliases"] == 0

    if args.smoke_output:
        output_cooked = args.smoke_output / f"track02-{args.smoke_output.name}.iso"
        differences = streamed_differences(
            core.BASE_DIR / core.BASE_COOKED_NAME,
            output_cooked,
        )
        report = json.loads(
            (args.smoke_output / "dialogue-editor-build-report.json").read_text(
                encoding="utf-8"
            )
        )
        allowed: list[tuple[int, int]] = []
        pooled_ids = {
            record_id
            for pool in report.get("shared_dialogue_pools", [])
            for record_id in pool["changed_records"]
        }
        allowed.extend(
            (int(pool["start"], 0), int(pool["end_exclusive"], 0))
            for pool in report.get("shared_dialogue_pools", [])
        )
        for record_id in report["changed_record_ids"]:
            target = by_id[record_id]
            if record_id in pooled_ids:
                continue
            if target.scenario == 2:
                allowed.extend(
                    [
                        (core.S2_DICT_START, core.S2_DICT_END),
                        (core.S2_DIALOGUE_START, core.S2_DIALOGUE_END),
                    ]
                )
            else:
                length = (
                    target.active_budget
                    if target.family == "scenario01-prefix"
                    else target.allocation
                )
                allowed.append((target.cooked_offset, target.cooked_offset + length))
        assert differences
        assert all(
            any(start <= offset < end for start, end in allowed)
            for offset in differences
        )
        print(
            f"smoke_diff_bytes={len(differences)} "
            f"range=0x{min(differences):X}-0x{max(differences):X}"
        )

    print(f"PASS records={len(records)} scenarios=70 four_families=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
