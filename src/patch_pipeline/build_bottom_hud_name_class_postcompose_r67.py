#!/usr/bin/env python3
"""Build the corrected R67 bottom-HUD 8x8 Korean class/name renderer.

Both native text calls remain in the original control flow.  Tiny capture
stubs remember their class/name IDs; the post-compose hook then uploads
dedicated Galmuri7 4bpp tiles and replaces only the class/name cells in the
native RAM BAT row immediately before its two K-RAM copies.
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from PIL import Image

from build_deployment_menu_hook import Assembler, encode_jal
from build_bottom_hud_name_class_r67 import (
    CAVES,
    DATA_CAVES,
    GALMURI7,
    GALMURI7_SHA256,
    GALMURI_LICENSE,
    GALMURI_LICENSE_SHA256,
    NATIVE_DECODER_RAM,
    PRIVATE_NAME_IDS,
    RAM_DELTA,
    ROOT,
    SET_KRAM_WRITE_RAM,
    SOURCE,
    SOURCE_SHA256,
    SpanAllocator,
    build_assets,
    emit_jr,
    sha256,
    subtract_interval,
    validate_instruction_stream,
    verify_status_class_correlation,
)


OUTPUT = ROOT / "work/poc/track02-r67-bottom-hud-name-class.iso"
MANIFEST = ROOT / "analysis/r67-bottom-hud-name-class-postcompose.json"
PREVIEW = ROOT / "evidence/fonts/r67-bottom-hud-name-class-postcompose.png"
GLYPH_ASSET = ROOT / "assets/hooks/r67-bottom-hud-name-class-galmuri7-rows.bin"
RECORD_ASSET = ROOT / "assets/hooks/r67-bottom-hud-name-class-records.bin"

CLASS_CALL_RAM = 0x34634
CLASS_CALL_COOKED = CLASS_CALL_RAM - RAM_DELTA
NAME_CALL_RAM = 0x34650
NAME_CALL_COOKED = NAME_CALL_RAM - RAM_DELTA
POSTDRAW_CALL_RAM = 0x34900
POSTDRAW_CALL_COOKED = POSTDRAW_CALL_RAM - RAM_DELTA
POSTDRAW_EXPECTED = bytes.fromhex("E000DC00")

UPLOAD_COOKED = 0x1008
LUT_COOKED = 0x0850
POST_COOKED = 0x0880
POST_LIMIT_COOKED = 0x0ABC
GLYPH0_COOKED = 0x0D0B
GLYPH1_COOKED = 0x0B9D
GLYPH_SPLIT = 71
SCRATCH_COOKED = 0x0F50
SCRATCH_RAM = SCRATCH_COOKED + RAM_DELTA
CAPTURE_COOKED = 0x0F60
CAPTURE_LIMIT_COOKED = 0x0FC4

# This 17-tile allocation is inside the audited F20..F3E run.  None of its
# tile IDs is referenced by any BAT in 707 independent saved states.  It is
# also disjoint from the R66 battle-menu (C00..) and status (C40..) banks.
CLASS_TILE_FIRST = 0x0F20
NAME_TILE_FIRST = 0x0F28
CLASS_CG_WORD = 0x2F200
NAME_CG_WORD = 0x2F280
CLASS_ROW_RAM = 0x6CC60  # native row 2, column 12: directly above L
NAME_ROW_RAM = 0x6CC74   # native row 2, existing name origin at column 22
CLASS_CELLS = 8
NAME_CELLS = 9
BLANK_BAT = 0x5300


def build_upload_helper_compact(base: int, glyph_split: int) -> bytes:
    """Cold-boot-safe compact uploader that fits the 0x1008 FF cave."""
    a = Assembler(base)
    a.mov(31, 26)
    a.jal(SET_KRAM_WRITE_RAM)
    a.mov_i(14, 1)
    a.out(0x3D, 0x0600, 0, 1)
    a.mov_i(0, 19)
    a.label("glyph_loop")
    # Keep the signed record byte in r23.  Its high bit terminates the record;
    # only the 7-bit glyph index needs masking.
    a.load(0x30, 0, 21, 10)
    a.mov(10, 23)
    a.fmt_v(0x2D, 0x007F, 10, 10)
    a.add_i(1, 21)

    a.movea(glyph_split, 0, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x46, "bank0")
    a.addi(-glyph_split, 10, 10)
    a.mov(17, 20)
    a.branch(0x45, "have_bank")
    a.label("bank0")
    a.mov(16, 20)
    a.label("have_bank")

    a.mov(10, 11)
    a.imm5(0x14, 3, 11)
    a.reg(0x02, 10, 11)
    a.reg(0x01, 11, 20)
    a.mov_i(7, 18)
    a.label("row_loop")
    a.load(0x30, 0, 20, 10)
    a.add_i(1, 20)
    a.mov(10, 11)
    a.imm5(0x15, 4, 10)
    a.fmt_v(0x2D, 0x000F, 10, 10)
    a.fmt_v(0x2D, 0x000F, 11, 11)
    a.imm5(0x14, 1, 10)
    a.imm5(0x14, 1, 11)
    a.mov(24, 12)
    a.reg(0x01, 10, 12)
    a.load(0x31, 0, 12, 10)
    a.out(0x3D, 0x0604, 0, 10)
    a.mov(24, 12)
    a.reg(0x01, 11, 12)
    a.load(0x31, 0, 12, 10)
    a.out(0x3D, 0x0604, 0, 10)
    a.add_i(-1, 18)
    a.branch(0x4A, "row_loop")
    a.out(0x3D, 0x0604, 0, 0)
    a.out(0x3D, 0x0604, 0, 0)
    a.add_i(1, 19)
    a.reg(0x03, 0, 23)
    a.branch(0x4E, "glyph_loop")
    a.reg(0x06, 26, 0)
    return a.finish()


def build_upload_helper_u8_ff(base: int, glyph_split: int) -> bytes:
    """Upload an FF-terminated record with full unsigned 8-bit glyph IDs.

    The original compact format spends bit 7 as the end marker and therefore
    caps the combined class/name alphabet at 127 glyphs.  Full commander and
    mercenary coverage exceeds that alphabet.  This sibling keeps the same
    renderer/K-RAM contract but reserves byte FF as a standalone terminator,
    allowing glyph IDs 0..254.
    """
    a = Assembler(base)
    a.mov(31, 26)
    a.jal(SET_KRAM_WRITE_RAM)
    a.mov_i(14, 1)
    a.out(0x3D, 0x0600, 0, 1)
    a.mov_i(0, 19)
    a.label("glyph_loop")
    a.load(0x30, 0, 21, 10)
    a.fmt_v(0x2D, 0x00FF, 10, 10)
    a.add_i(1, 21)
    a.movea(0x00FF, 0, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x42, "done")

    a.movea(glyph_split, 0, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x46, "bank0")
    a.addi(-glyph_split, 10, 10)
    a.mov(17, 20)
    a.branch(0x45, "have_bank")
    a.label("bank0")
    a.mov(16, 20)
    a.label("have_bank")

    a.mov(10, 11)
    a.imm5(0x14, 3, 11)
    a.reg(0x02, 10, 11)
    a.reg(0x01, 11, 20)
    a.mov_i(7, 18)
    a.label("row_loop")
    a.load(0x30, 0, 20, 10)
    a.add_i(1, 20)
    a.mov(10, 11)
    a.imm5(0x15, 4, 10)
    a.fmt_v(0x2D, 0x000F, 10, 10)
    a.fmt_v(0x2D, 0x000F, 11, 11)
    a.imm5(0x14, 1, 10)
    a.imm5(0x14, 1, 11)
    a.mov(24, 12)
    a.reg(0x01, 10, 12)
    a.load(0x31, 0, 12, 10)
    a.out(0x3D, 0x0604, 0, 10)
    a.mov(24, 12)
    a.reg(0x01, 11, 12)
    a.load(0x31, 0, 12, 10)
    a.out(0x3D, 0x0604, 0, 10)
    a.add_i(-1, 18)
    a.branch(0x4A, "row_loop")
    a.out(0x3D, 0x0604, 0, 0)
    a.out(0x3D, 0x0604, 0, 0)
    a.add_i(1, 19)
    a.branch(0x45, "glyph_loop")
    a.label("done")
    a.reg(0x06, 26, 0)
    return a.finish()


def compact_descriptors(banks: list[dict[str, object]]) -> bytes:
    """Pack count:u8 + 24-bit MAIN address into one little-endian word."""
    output = bytearray()
    for bank in banks:
        count = int(bank["count"])
        address = int(bank["cooked"]) + RAM_DELTA
        if not 1 <= count <= 255 or not 0 <= address < 0x1000000:
            raise SystemExit("compact descriptor is out of range")
        output.extend(struct.pack("<I", count | (address << 8)))
    return bytes(output)


def build_capture_handler(base: int) -> tuple[bytes, dict[str, int]]:
    a = Assembler(base)
    for name, offset in (("class_entry", 0), ("name_entry", 4)):
        a.label(name)
        a.addi(-16, 3, 3)
        a.store(0x37, 0, 3, 31)
        a.store(0x37, 4, 3, 10)
        a.store(0x37, 8, 3, 11)
        a.store(0x37, 12, 3, 12)
        a.mov_i(offset, 12)
        a.branch(0x45, "common")
    a.label("common")
    a.load_address(SCRATCH_RAM, 10)
    a.reg(0x01, 12, 10)
    a.store(0x37, 0, 10, 7)
    a.load(0x33, 12, 3, 12)
    a.load(0x33, 8, 3, 11)
    a.load(0x33, 4, 3, 10)
    a.load(0x33, 0, 3, 31)
    a.addi(16, 3, 3)
    emit_jr(a, NATIVE_DECODER_RAM)
    return a.finish(), dict(a.labels)


def build_post_handler(
    base: int,
    class_desc_ram: int,
    name_desc_ram: int,
    record_desc_ram: int,
    upload_ram: int,
    glyph0_ram: int,
    glyph1_ram: int,
    lut_ram: int,
    *,
    full_class_map: bool = False,
    full_name_map: bool = False,
    ff_records: bool = False,
    require_r28_two: bool = True,
    clear_native_upper_rows: bool = False,
    class_override_desc_ram: int | None = None,
    last_unit_id_ram: int | None = None,
) -> tuple[bytes, dict[str, int]]:
    a = Assembler(base)
    a.label("post_entry")
    # At this point only r1, r3, r5 and r28 remain live in the native six-row
    # uploader.  The renderer does not touch r5/r28; preserve r1 and the link.
    a.addi(-8, 3, 3)
    a.store(0x37, 0, 3, 31)
    a.store(0x37, 4, 3, 1)
    if require_r28_two:
        a.mov_i(2, 10)
        a.reg(0x03, 10, 28)
        a.branch(0x4A, "restore")

    if class_override_desc_ram is not None:
        # Some mercenary unit IDs share a native job/class ID with a
        # commander class even though their HUD category is different.  A
        # sparse map keyed by the captured unit/name ID lets callers correct
        # only those mercenaries without relabelling the commander class.
        a.load_address(SCRATCH_RAM, 20)
        a.load(0x33, 4, 20, 10)
        a.fmt_v(0x2D, 0x00FF, 10, 10)
        a.movea(0x00FF, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x42, "normal_class_select")
        if last_unit_id_ram is not None:
            # Preserve the currently displayed unit ID for consumers that run
            # after this one-draw scratch handoff has been cleared.  The field
            # information button resolves its faction/category sentence later
            # than the lower HUD, so it cannot safely reuse SCRATCH_RAM.
            a.load_address(last_unit_id_ram, 20)
            a.store(0x37, 0, 20, 10)
        a.load_address(class_override_desc_ram, 20)
        a.jal("select_bank")
        a.reg(0x01, 10, 20)
        a.load(0x30, 0, 20, 10)
        a.fmt_v(0x2D, 0x00FF, 10, 10)
        a.movea(0x00FF, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x42, "normal_class_select")
        a.mov_i(0, 15)
        a.jal("render_label")
        a.branch(0x45, "name_select")
        a.label("normal_class_select")

    a.load_address(SCRATCH_RAM, 20)
    a.load(0x33, 0, 20, 10)
    if full_class_map:
        # FF is both the consumed/no-capture sentinel and the sparse-map
        # sentinel.  Valid class IDs are the complete 0..254 denominator.
        a.fmt_v(0x2D, 0x00FF, 10, 10)
        a.movea(0x00FF, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x42, "name_select")
    else:
        # Legacy R67 subset: ID 14 -> map 0; IDs 201..254 -> map 1..54.
        a.mov_i(14, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x42, "class_zero")
        a.movea(201, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x46, "name_select")
        a.movea(255, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x4E, "name_select")
        a.addi(-200, 10, 10)
        a.branch(0x45, "class_map")
        a.label("class_zero")
        a.mov_i(0, 10)
    a.label("class_map")
    a.load_address(class_desc_ram, 20)
    a.jal("select_bank")
    a.reg(0x01, 10, 20)
    a.load(0x30, 0, 20, 10)
    a.fmt_v(0x2D, 0x00FF, 10, 10)
    if full_class_map:
        a.movea(0x00FF, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x42, "name_select")
    a.mov_i(0, 15)
    a.jal("render_label")

    # Name: every named/human/common ID has a private record.  Monster-only
    # IDs keep the native name path without changing its cells.
    a.label("name_select")
    a.load_address(SCRATCH_RAM, 20)
    a.load(0x33, 4, 20, 10)
    # The native name decoder folds unit IDs 201..255 back to name-table
    # indices 1..55.  Mirror that normalization before selecting the private
    # Korean record (for example, live Leon is unit ID 213 -> name ID 13).
    a.movea(201, 0, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x46, "name_range")
    a.addi(-200, 10, 10)
    a.label("name_range")
    if full_name_map:
        # Complete native name denominator 0..166.  This includes commander,
        # human mercenary and monster/unit labels; sparse entry 0 stays FF.
        a.fmt_v(0x2D, 0x00FF, 10, 10)
        a.movea(167, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x4E, "restore")
    else:
        # Compact only the three explicitly private name ranges instead of
        # carrying a 167-byte sparse table: 1..56, 127..139 and 147..150.
        a.mov_i(1, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x46, "restore")
        a.movea(57, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x46, "name_low")
        a.movea(127, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x46, "restore")
        a.movea(140, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x46, "name_mid")
        a.movea(147, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x46, "restore")
        a.movea(151, 0, 11)
        a.reg(0x03, 11, 10)
        a.branch(0x4E, "restore")
        a.addi(-78, 10, 10)
        a.branch(0x45, "name_map")
        a.label("name_mid")
        a.addi(-71, 10, 10)
        a.branch(0x45, "name_map")
        a.label("name_low")
        a.add_i(-1, 10)
    a.label("name_map")
    a.load_address(name_desc_ram, 20)
    a.jal("select_bank")
    a.reg(0x01, 10, 20)
    a.load(0x30, 0, 20, 10)
    a.fmt_v(0x2D, 0x00FF, 10, 10)
    a.movea(0x00FF, 0, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x42, "restore")
    a.mov_i(1, 15)
    a.jal("render_label")

    a.label("restore")
    # Captured IDs are a one-draw handoff, not persistent HUD state.  Without
    # consuming them here, a later native SCENARIO/TURN draw that does not call
    # either decoder is overwritten again with the previously selected unit.
    a.load_address(SCRATCH_RAM, 20)
    a.mov_i(-1, 10)
    a.store(0x37, 0, 20, 10)
    a.store(0x37, 4, 20, 10)
    a.load(0x33, 4, 3, 1)
    a.load(0x33, 0, 3, 31)
    a.addi(8, 3, 3)
    # Reproduce the two instructions replaced at native 0x34900.
    a.mov_i(0, 7)
    a.mov(28, 6)
    a.reg(0x06, 31, 0)

    # Resolve one label ID to its record, upload its Galmuri7 glyphs, then
    # replace only its fixed RAM BAT field.
    a.label("render_label")
    a.mov(31, 25)
    a.load_address(record_desc_ram, 20)
    a.jal("select_bank")
    a.label("record_walk")
    a.reg(0x03, 0, 10)
    a.branch(0x42, "record_found")
    a.label("skip_character")
    a.load(0x30, 0, 20, 11)
    a.fmt_v(0x2D, 0x00FF, 11, 11)
    a.add_i(1, 20)
    if ff_records:
        a.movea(0x00FF, 0, 12)
        a.reg(0x03, 12, 11)
        a.branch(0x42, "record_end")
        a.branch(0x45, "skip_character")
        a.label("record_end")
    else:
        a.fmt_v(0x2D, 0x0080, 11, 11)
        a.reg(0x03, 0, 11)
        a.branch(0x42, "skip_character")
    a.add_i(-1, 10)
    a.branch(0x4A, "record_walk")
    a.label("record_found")
    a.mov(20, 21)
    a.reg(0x03, 0, 15)
    a.branch(0x4A, "name_upload")
    a.load_address(CLASS_CG_WORD, 6)
    a.branch(0x45, "do_upload")
    a.label("name_upload")
    a.load_address(NAME_CG_WORD, 6)
    a.label("do_upload")
    a.load_address(glyph0_ram, 16)
    a.load_address(glyph1_ram, 17)
    a.load_address(lut_ram, 24)
    a.mov_i(0, 7)
    a.mov_i(1, 8)
    a.jal(upload_ram)
    a.reg(0x03, 0, 15)
    a.branch(0x4A, "name_field")
    a.load_address(CLASS_ROW_RAM, 20)
    a.mov_i(CLASS_CELLS, 22)
    a.movea(CLASS_TILE_FIRST, 0, 24)
    a.branch(0x45, "do_field")
    a.label("name_field")
    a.load_address(NAME_ROW_RAM, 20)
    a.mov_i(NAME_CELLS, 22)
    a.movea(NAME_TILE_FIRST, 0, 24)
    a.label("do_field")
    a.jal("patch_field")
    a.reg(0x06, 25, 0)

    # Compact descriptor selector.  Each word is count:u8 | address:u24<<8.
    a.label("select_bank")
    a.mov(31, 26)
    a.label("bank_loop")
    a.load(0x33, 0, 20, 11)
    a.fmt_v(0x2D, 0x00FF, 11, 12)
    a.reg(0x03, 12, 10)
    a.branch(0x46, "bank_found")
    a.reg(0x02, 12, 10)
    a.add_i(4, 20)
    a.branch(0x45, "bank_loop")
    a.label("bank_found")
    a.imm5(0x15, 8, 11)
    a.mov(11, 20)
    a.reg(0x06, 26, 0)

    # r20=row pointer, r19=length, r22=field cells, r24=first private tile.
    a.label("patch_field")
    a.mov(31, 26)
    if clear_native_upper_rows:
        # Native small-font kana can leave marks in the BAT row immediately
        # above the main glyph row.  Korean 8x8 replacement tiles only cover
        # the lower row, so パイク otherwise leaves its handakuten above
        # 파이크.  The live field BAT buffer is 32 cells wide (0x40 bytes per
        # row), so clear exactly that accent row and no UI background row.
        a.mov(20, 18)
        a.addi(-0x40, 18, 18)
        a.mov(22, 11)
        a.movea(BLANK_BAT, 0, 10)
        a.label("upper_blank_loop")
        a.store(0x35, 0, 18, 10)
        a.add_i(2, 18)
        a.add_i(-1, 11)
        a.branch(0x4A, "upper_blank_loop")
    a.mov(19, 11)
    a.mov(24, 12)
    a.movea(0x5000, 0, 13)
    a.label("tile_loop")
    a.mov(13, 10)
    a.reg(0x0C, 12, 10)
    a.store(0x35, 0, 20, 10)
    a.add_i(2, 20)
    a.add_i(1, 12)
    a.add_i(-1, 11)
    a.branch(0x4A, "tile_loop")
    a.reg(0x02, 19, 22)
    a.movea(BLANK_BAT, 0, 10)
    a.label("blank_loop")
    a.store(0x35, 0, 20, 10)
    a.add_i(2, 20)
    a.add_i(-1, 22)
    a.branch(0x4A, "blank_loop")
    a.reg(0x06, 26, 0)
    return a.finish(), dict(a.labels)


def render_preview(assets: dict[str, object]) -> None:
    labels = [assets["labels"][index] for index in (0, 1, 12)]
    labels.extend(label for label in assets["name_labels"] if label) 
    labels = labels[:3] + list(dict.fromkeys(labels[3:]))[:5]
    images = assets["glyph_images"]
    canvas = Image.new("L", (max(map(len, labels)) * 8, len(labels) * 10), 0)
    for y, label in enumerate(labels):
        for x, character in enumerate(label):
            canvas.paste(images[character], (x * 8, y * 10))
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    canvas.resize((canvas.width * 8, canvas.height * 8), Image.Resampling.NEAREST).save(PREVIEW)


def main() -> int:
    source = SOURCE.read_bytes()
    if sha256(source) != SOURCE_SHA256:
        raise SystemExit("R66 baseline SHA-256 mismatch")
    if sha256(GALMURI7.read_bytes()) != GALMURI7_SHA256:
        raise SystemExit("Galmuri7 SHA-256 mismatch")
    if sha256(GALMURI_LICENSE.read_bytes()) != GALMURI_LICENSE_SHA256:
        raise SystemExit("Galmuri license SHA-256 mismatch")
    assets = build_assets(source)
    correlation = verify_status_class_correlation(source)

    glyph_rows = assets["glyph_rows"]
    glyph0 = glyph_rows[:GLYPH_SPLIT * 7]
    glyph1 = glyph_rows[GLYPH_SPLIT * 7:]
    if len(glyph0) != 497 or len(glyph1) != 315:
        raise SystemExit("unexpected combined glyph-bank split")
    upload = build_upload_helper_compact(UPLOAD_COOKED + RAM_DELTA, GLYPH_SPLIT)
    capture, capture_symbols = build_capture_handler(CAPTURE_COOKED + RAM_DELTA)
    if CAPTURE_COOKED + len(capture) > CAPTURE_LIMIT_COOKED:
        raise SystemExit("capture handler exceeds its private cave")

    spans = list(CAVES + DATA_CAVES)
    fixed = (
        # The first data sector is boot-sensitive even where it is padded.
        # Keep its 0x768..0x7FF run entirely untouched.
        (0x000768, 0x000800),
        (UPLOAD_COOKED, UPLOAD_COOKED + len(upload)),
        (LUT_COOKED, LUT_COOKED + len(assets["lut"])),
        (POST_COOKED, POST_LIMIT_COOKED),
        (GLYPH0_COOKED, GLYPH0_COOKED + len(glyph0)),
        (GLYPH1_COOKED, GLYPH1_COOKED + len(glyph1)),
        (SCRATCH_COOKED, SCRATCH_COOKED + 8),
        (CAPTURE_COOKED, CAPTURE_COOKED + len(capture)),
    )
    for start, end in fixed:
        spans = subtract_interval(spans, start, end)
    allocator = SpanAllocator(spans)
    private_name_map = bytes(
        assets["name_map"][name_id] for name_id in sorted(PRIVATE_NAME_IDS)
    )
    name_banks = allocator.split_bytes(private_name_map, "name-map")
    class_banks = allocator.split_bytes(assets["class_map"], "class-map")
    record_banks = allocator.split_records(assets["record_rows"], "label-records")

    class_desc = compact_descriptors(class_banks)
    name_desc = compact_descriptors(name_banks)
    record_desc = compact_descriptors(record_banks)
    placeholder, _ = build_post_handler(
        POST_COOKED + RAM_DELTA, 0x7A00, 0x7A20, 0x7A40,
        UPLOAD_COOKED + RAM_DELTA, GLYPH0_COOKED + RAM_DELTA,
        GLYPH1_COOKED + RAM_DELTA, LUT_COOKED + RAM_DELTA,
    )
    desc_cooked = (POST_COOKED + len(placeholder) + 3) & ~3
    class_desc_cooked = desc_cooked
    name_desc_cooked = class_desc_cooked + len(class_desc)
    record_desc_cooked = name_desc_cooked + len(name_desc)
    descriptors = class_desc + name_desc + record_desc
    if record_desc_cooked + len(record_desc) > POST_LIMIT_COOKED:
        raise SystemExit(
            f"post handler/descriptors end at 0x{record_desc_cooked + len(record_desc):X}"
        )
    post, post_symbols = build_post_handler(
        POST_COOKED + RAM_DELTA,
        class_desc_cooked + RAM_DELTA,
        name_desc_cooked + RAM_DELTA,
        record_desc_cooked + RAM_DELTA,
        UPLOAD_COOKED + RAM_DELTA,
        GLYPH0_COOKED + RAM_DELTA,
        GLYPH1_COOKED + RAM_DELTA,
        LUT_COOKED + RAM_DELTA,
    )
    if len(post) != len(placeholder):
        raise SystemExit("post handler size changed after descriptor placement")

    output = bytearray(source)
    allocations: list[dict[str, object]] = []

    def add_write(purpose: str, cooked: int, payload: bytes, fill: int = 0) -> None:
        expected = bytes(source[cooked:cooked + len(payload)])
        if expected != bytes([fill]) * len(payload):
            raise SystemExit(f"{purpose} target 0x{cooked:X} changed")
        output[cooked:cooked + len(payload)] = payload
        allocations.append({
            "purpose": purpose, "cooked": f"0x{cooked:X}",
            "ram": f"0x{cooked + RAM_DELTA:X}", "bytes": len(payload),
            "fill": f"0x{fill:02X}",
            "expected_sha256": hashlib.sha256(expected).hexdigest().upper(),
            "replacement_sha256": hashlib.sha256(payload).hexdigest().upper(),
        })

    add_write("glyph-uploader", UPLOAD_COOKED, upload, 0xFF)
    add_write("private-4bpp-lut", LUT_COOKED, assets["lut"])
    add_write("post-compose-handler", POST_COOKED, post)
    add_write("compact-descriptors", desc_cooked, descriptors)
    add_write("captured-ids", SCRATCH_COOKED, bytes.fromhex("FFFFFFFFFFFFFFFF"))
    add_write("id-capture-handler", CAPTURE_COOKED, capture)
    add_write("glyph-bank-0", GLYPH0_COOKED, glyph0)
    add_write("glyph-bank-1", GLYPH1_COOKED, glyph1)
    for bank in (*name_banks, *class_banks, *record_banks):
        add_write(str(bank["purpose"]), int(bank["cooked"]), bytes(bank["data"]), int(bank["fill"]))

    expected_class = encode_jal(CLASS_CALL_RAM, NATIVE_DECODER_RAM)
    expected_name = encode_jal(NAME_CALL_RAM, NATIVE_DECODER_RAM)
    if source[CLASS_CALL_COOKED:CLASS_CALL_COOKED + 4] != expected_class:
        raise SystemExit("native class call changed")
    if source[NAME_CALL_COOKED:NAME_CALL_COOKED + 4] != expected_name:
        raise SystemExit("native name call changed")
    if source[POSTDRAW_CALL_COOKED:POSTDRAW_CALL_COOKED + 4] != POSTDRAW_EXPECTED:
        raise SystemExit("native post-compose instructions changed")
    hook_rows = (
        ("class-capture-hook", CLASS_CALL_COOKED, expected_class,
         encode_jal(CLASS_CALL_RAM, capture_symbols["class_entry"])),
        ("name-capture-hook", NAME_CALL_COOKED, expected_name,
         encode_jal(NAME_CALL_RAM, capture_symbols["name_entry"])),
        ("post-compose-hook", POSTDRAW_CALL_COOKED, POSTDRAW_EXPECTED,
         encode_jal(POSTDRAW_CALL_RAM, post_symbols["post_entry"])),
    )
    for purpose, cooked, expected, replacement in hook_rows:
        output[cooked:cooked + 4] = replacement
        allocations.append({
            "purpose": purpose, "cooked": f"0x{cooked:X}",
            "ram": f"0x{cooked + RAM_DELTA:X}", "bytes": 4,
            "fill": None,
            "expected_sha256": hashlib.sha256(expected).hexdigest().upper(),
            "replacement_sha256": hashlib.sha256(replacement).hexdigest().upper(),
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(output)
    GLYPH_ASSET.parent.mkdir(parents=True, exist_ok=True)
    GLYPH_ASSET.write_bytes(glyph_rows)
    RECORD_ASSET.write_bytes(assets["records"])
    render_preview(assets)

    manifest = {
        "version": "r67",
        "purpose": "post-compose Galmuri7 8x8 bottom-HUD Korean class and name renderer",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": SOURCE_SHA256,
        "output": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "output_sha256": hashlib.sha256(output).hexdigest().upper(),
        "font": {
            "name": "Galmuri7", "cell": "8x8", "glyph_count": len(assets["characters"]),
            "glyph_asset": str(GLYPH_ASSET.relative_to(ROOT)).replace("\\", "/"),
            "records_asset": str(RECORD_ASSET.relative_to(ROOT)).replace("\\", "/"),
            "preview": str(PREVIEW.relative_to(ROOT)).replace("\\", "/"),
        },
        "layout": {
            "class": {"row_ram": f"0x{CLASS_ROW_RAM:X}", "column": 12, "cells": 8,
                      "tile_range": ["0xF20", "0xF27"], "alignment": "fixed above L origin"},
            "name": {"row_ram": f"0x{NAME_ROW_RAM:X}", "column": 22, "cells": 9,
                     "tile_range": ["0xF28", "0xF30"], "alignment": "native origin unchanged"},
        },
        "scope": {
            "class_ids": [14, *range(201, 255)],
            "private_name_ids": sorted(PRIVATE_NAME_IDS),
            "native_fallback_name_ids": [i for i in range(167) if i not in PRIVATE_NAME_IDS],
        },
        "correlation": {
            "failure": "native bottom-HUD decoder is byte-oriented while status classes use F0/F1/F2 pairs",
            "verified_class_rows": correlation,
        },
        "private_allocations": allocations,
        "descriptor_banks": {
            "class": [{"count": int(b["count"]), "ram": f"0x{int(b['cooked']) + RAM_DELTA:X}"} for b in class_banks],
            "name": [{"count": int(b["count"]), "ram": f"0x{int(b['cooked']) + RAM_DELTA:X}"} for b in name_banks],
            "records": [{"count": int(b["count"]), "ram": f"0x{int(b['cooked']) + RAM_DELTA:X}"} for b in record_banks],
        },
        "code_validation": {
            "capture": validate_instruction_stream(capture, CAPTURE_COOKED + RAM_DELTA),
            "post": validate_instruction_stream(post, POST_COOKED + RAM_DELTA),
            "upload": validate_instruction_stream(upload, UPLOAD_COOKED + RAM_DELTA),
        },
        "invariants": {
            "native_class_decoder_still_called": True,
            "native_name_decoder_still_called": True,
            "name_origin_changed": False,
            "resource_reuse": False,
            "class_name_tiles_overlap": False,
            "stale_cells_cleared": True,
            "r66_existing_payload_modified": False,
        },
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"output={OUTPUT}")
    print(f"sha256={manifest['output_sha256']}")
    print(f"capture={len(capture)} post={len(post)} descriptors={len(descriptors)} upload={len(upload)}")
    print(f"glyphs={len(assets['characters'])} name_banks={len(name_banks)} class_banks={len(class_banks)} record_banks={len(record_banks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
