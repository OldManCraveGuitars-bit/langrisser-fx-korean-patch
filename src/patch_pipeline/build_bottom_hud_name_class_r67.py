#!/usr/bin/env python3
"""Build R67: dedicated Galmuri7 8x8 bottom-HUD class and name labels.

The native bottom-HUD consumer is byte-oriented.  It cannot consume the
private two-byte Korean strings used by the character-status class field.
R67 therefore selects the visible class/name by its native table ID, renders
from private Galmuri7 rows, uploads to two non-overlapping 4bpp tile ranges,
and rewrites only the two bottom-HUD fields.  No Japanese or resident Hangul
glyph resource is repurposed.
"""

from __future__ import annotations

import hashlib
import json
import struct
import unicodedata
from pathlib import Path

from PIL import Image

from bdf_bitmap_glyphs import load_bdf_cell
from build_deployment_menu_hook import Assembler, encode_jal
from find_v810_kram_writers import OPNAMES, decode


# The private development tree used an absolute local path here.  Keep the
# public snapshot portable and resolve the repository root from this file.
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "work/poc/track02-r66-commander-status-labels.iso"
SOURCE_SHA256 = "C66094A1B43EB583BFA229D5DC97D22B6667F271B00B6E88FE39A560F4248569"
OUTPUT = ROOT / "work/poc/track02-r67-bottom-hud-name-class.iso"
MANIFEST = ROOT / "analysis/r67-bottom-hud-name-class.json"
PREVIEW = ROOT / "evidence/fonts/r67-bottom-hud-name-class-galmuri7.png"

GALMURI_DIR = ROOT / "assets/fonts/galmuri-v2.40.4"
GALMURI7 = GALMURI_DIR / "Galmuri7.bdf"
GALMURI7_SHA256 = "2A6FD090AC6D24F7392D6CC49DB02CE54B9D1C01048BF8C97CBCDBC5A885CB15"
GALMURI_LICENSE = GALMURI_DIR / "OFL-1.1.md"
GALMURI_LICENSE_SHA256 = "9A9E5A342C430C3FCF01A408B680F4405D5BF4AC659C931BE35F8A1B27EA69C9"

RAM_DELTA = 0x7000
CLASS_CALL_RAM = 0x34634
CLASS_CALL_COOKED = CLASS_CALL_RAM - RAM_DELTA
NAME_CALL_RAM = 0x34650
NAME_CALL_COOKED = NAME_CALL_RAM - RAM_DELTA
NATIVE_DECODER_RAM = 0x33EC4
SET_KRAM_WRITE_RAM = 0x4D3C8

CLASS_TILE_FIRST = 0xD40
NAME_TILE_FIRST = 0xD50
CLASS_CG_WORD = 0x2D400
NAME_CG_WORD = 0x2D500
# Fixed first cell directly above the HUD's L-level origin.  Class labels grow
# rightward from here; they are not right-aligned against the value column.
CLASS_BAT_WORD = 0x21E8C
NAME_BAT_WORD = 0x21E96
BAT_SECOND_ROW_DELTA = 0x20
BLANK_BAT = 0x5300

# Dedicated padding proved byte-zero on R66 disc and in two independent live
# field states.  The FF run is independently proved unchanged in the same
# states.  R67 allocates it exclusively; no prior hook/resource is shared.
CAVES = (
    (0x000768, 0x000800, 0x00),
    (0x00080C, 0x000820, 0x00),
    (0x000850, 0x000870, 0x00),
    (0x000880, 0x000ABC, 0x00),
    (0x000B9D, 0x000D08, 0x00),
    (0x000D0B, 0x000F01, 0x00),
    (0x000F0E, 0x000F20, 0x00),
    (0x000F5F, 0x000FC4, 0x00),
    (0x001008, 0x001080, 0xFF),
)

DATA_CAVES = (
    (0x053693, 0x0536A6, 0x00), (0x0538CD, 0x0538E1, 0x00),
    (0x0539ED, 0x0539FD, 0x00), (0x053C28, 0x053C38, 0x00),
    (0x053D43, 0x053D58, 0x00), (0x0544FC, 0x05450F, 0x00),
    (0x054619, 0x05462A, 0x00), (0x054855, 0x054867, 0x00),
    (0x054971, 0x054984, 0x00), (0x054A8F, 0x054AA2, 0x00),
    (0x055B52, 0x055B63, 0x00), (0x055D8E, 0x055D9E, 0x00),
    (0x055EAD, 0x055EBD, 0x00), (0x055FCB, 0x055FDB, 0x00),
    (0x07F493, 0x07F4A4, 0x00), (0x07F4B1, 0x07F4C8, 0x00),
)

CLASS_LABELS = (
    "워록", "기사단장", "엠퍼러", "자베라", "어쌔신", "암흑공주", "위저드",
    "해룡기사", "용기사", "용군주", "노블", "용기사", "로열가드", "대마법사",
    "하이로드", "검성", "나이트", "해룡군주", "기사단장", "어쌔신", "레인저",
    "대사범", "대마법사", "위저드", "대신관", "카오스", "비숍", "루시리스",
    "소서러", "은기사", "사령술사", "세인트", "메이지", "소드맨", "하이랜더",
    "세인트", "서모너", "소드맨", "해룡기사", "프리스트", "매기사", "용군주",
    "세이지", "세이지", "대마법사", "제너럴", "검성", "해룡군주", "검성",
    "대신관", "세이지", "제너럴", "기사단장", "해적", "나이트",
)

NAME_TRANSLATIONS = {
    "エルウィン": "엘윈", "リアナ": "리아나", "ラーナ": "라나",
    "シェリー": "쉐리", "ヘイン": "헤인", "スコット": "스코트",
    "キース": "키스", "アーロン": "아론", "レスター": "레스터",
    "ロウガ": "로우가", "ソニア": "소니아", "レオン": "레온",
    "バルガス": "발가스", "イメルダ": "이멜다", "エグベルト": "에그베르트",
    "エスト": "에스트", "オスト": "오스트", "レアード": "레아드",
    "ジェシカ": "제시카", "ダークプリンセス": "암흑공주",
    "ベルンハルト": "베른하르트", "ボーゼル": "보젤",
    "ナゾノキシ": "의문의기사", "バルドー": "발드", "ゾルム": "졸름",
    "モーガン": "모건", "ギナム": "기남", "クレイマー": "크레이머",
    "セイガル": "세이갈", "フォルガー": "포르가",
    "イッパンヘイ": "일반병", "シキカン": "지휘관", "シサイ": "사제",
    "ムラビト": "주민", "カイゾク": "해적", "ジケイダン": "자경단",
    "ローレン": "로렌", "アドン": "아돈", "サムソン": "삼손",
    "バラン": "바란", "テイコクシキカン": "제국지휘관",
    "ウェアウルフ": "웨어울프", "ゲルギャザー": "게르갸저",
    "スキュラ": "스큐라", "ストーンゴーレム": "스톤골렘", "リッチ": "리치",
    "リビングアーマー": "리빙아머", "バンパイアロード": "뱀파이어로드",
    "ゴースト": "고스트", "ケルベロス": "켈베로스",
    "マスターディーノ": "마스터디노", "ワイバーン": "와이번",
    "グレートドラゴン": "그레이트드래곤", "ミノタウロス": "미노타우로스",
    "クラーケン": "크라켄", "サキュバス": "서큐버스",
    "デーモンロード": "데몬로드", "アニキ": "형님", "マジョ": "마녀",
    "シンカン": "신관", "テイコクヘイ": "제국병", "ファイアス": "파이어스",
    "ロック": "록", "ネクロマンサー": "네크로맨서", "リデル": "리델",
    "エヴァンゼ": "에반제", "フェニックス": "피닉스", "カオス": "카오스",
    "ルシリス": "루시리스", "レディン": "레딘", "ジークハルト": "지크하르트",
    "イェルムンガルド": "요르문간드", "カミラ": "카밀라", "カニヲ": "카니오",
    "ウッキー": "우키", "アキターン": "아키탄", "エリザ": "엘리자",
}

# R67 covers every named character and every human/common command label.  The
# monster-only rows remain on the native path; adding those is a separate font
# page because their syllables would exceed this resident hook's private
# one-byte glyph index.  This is deliberate fallback, not tile reuse.
PRIVATE_NAME_IDS = frozenset(
    [*range(1, 57), *range(127, 140), *range(147, 151)]
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def encode_jr(pc: int, target: int) -> bytes:
    displacement = target - pc
    if displacement & 1 or not -(1 << 25) <= displacement < (1 << 25):
        raise ValueError("JR displacement out of range")
    value = displacement & ((1 << 26) - 1)
    return bytes(((value >> 16) & 0xFF, 0xA8 | ((value >> 24) & 3),
                  value & 0xFF, (value >> 8) & 0xFF))


def emit_jr(a: Assembler, target: int) -> None:
    a.code.extend(encode_jr(a.pc, target))


def set_kram_inline(a: Assembler) -> None:
    """Select an auto-incrementing KING K-RAM word stream at r6."""
    a.mov(6, 30)
    a.mov_i(1, 1)
    a.imm5(0x14, 18, 1)
    a.reg(0x0C, 1, 30)
    a.mov_i(13, 1)
    a.out(0x3D, 0x0600, 0, 1)
    a.out(0x3F, 0x0604, 0, 30)
    a.mov_i(14, 1)
    a.out(0x3D, 0x0600, 0, 1)


def build_upload_helper(
    base: int,
    glyph_split: int,
) -> bytes:
    """Upload one selected label and return its length in r19.

    Input: r6 K-RAM CG word, r21 record pointer, r24 private LUT, r16/r17
    private glyph banks.  The helper has no nested JAL, so r26 safely carries
    its private return link.
    """
    a = Assembler(base)
    a.mov(31, 26)
    set_kram_inline(a)
    a.mov_i(0, 19)
    a.label("glyph_loop")
    a.load(0x30, 0, 21, 10)
    a.fmt_v(0x2D, 0x00FF, 10, 10)
    a.add_i(1, 21)
    a.mov(10, 23)
    a.fmt_v(0x2D, 0x0080, 23, 23)
    a.fmt_v(0x2D, 0x007F, 10, 10)

    a.movea(glyph_split, 0, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x46, "bank0")
    a.addi(-glyph_split, 10, 10)
    a.mov(17, 20)
    a.branch(0x45, "have_bank")
    a.label("bank0")
    a.mov(16, 20)
    a.label("have_bank")

    # Compact glyph index * 7.
    a.mov(10, 11)
    a.imm5(0x14, 3, 11)
    a.reg(0x02, 10, 11)
    a.reg(0x01, 11, 20)
    a.mov_i(7, 18)
    a.label("row_loop")
    a.load(0x30, 0, 20, 10)
    a.fmt_v(0x2D, 0x00FF, 10, 10)
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
    a.branch(0x42, "glyph_loop")
    a.reg(0x06, 26, 0)
    return a.finish()


def build_bat_helper(base: int) -> bytes:
    """Write one fixed-start class/name field into one HUD BAT buffer.

    Input: r20 BAT word, r19 label length, r23 post-blanks, r24 first private
    tile.  Both R67 fields have a fixed left edge, so no pre-blank path exists.
    """
    a = Assembler(base)
    a.mov(31, 26)
    a.mov(20, 6)
    a.mov_i(0, 7)
    a.mov_i(1, 8)
    a.jal(SET_KRAM_WRITE_RAM)
    a.mov_i(14, 1)
    a.out(0x3D, 0x0600, 0, 1)
    a.mov(19, 11)
    a.mov(24, 12)
    a.movea(0x5000, 0, 13)
    a.label("tile_loop")
    a.mov(13, 10)
    a.reg(0x0C, 12, 10)
    a.out(0x3D, 0x0604, 0, 10)
    a.add_i(1, 12)
    a.add_i(-1, 11)
    a.branch(0x4A, "tile_loop")

    a.movea(BLANK_BAT, 0, 10)
    a.mov(23, 11)
    a.label("post_loop")
    a.out(0x3D, 0x0604, 0, 10)
    a.add_i(-1, 11)
    a.branch(0x4A, "post_loop")
    a.reg(0x06, 26, 0)
    return a.finish()


def build_main_handler(
    base: int,
    class_descriptor_ram: int,
    name_descriptor_ram: int,
    record_descriptor_ram: int,
    upload_ram: int,
    bat_ram: int,
    glyph_bank0_ram: int,
    glyph_bank1_ram: int,
    lut_ram: int,
) -> tuple[bytes, dict[str, int]]:
    """Build the two entry stubs and shared ID/record dispatcher."""
    a = Assembler(base)
    a.label("class_entry")
    a.mov_i(0, 1)
    a.branch(0x45, "common")
    a.label("name_entry")
    a.mov_i(1, 1)
    a.label("common")

    saved = tuple(range(20, 26))
    frame_size = 4 + len(saved) * 4
    a.addi(-frame_size, 3, 3)
    a.store(0x37, 0, 3, 31)
    for index, register in enumerate(saved, 1):
        a.store(0x37, index * 4, 3, register)
    a.mov(1, 25)
    a.reg(0x03, 0, 25)
    a.branch(0x4A, "name_select")

    # Class ID 14 is map entry 0; IDs 201..254 are entries 1..54.
    a.mov(7, 10)
    a.mov_i(14, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x42, "class_zero")
    a.movea(201, 0, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x46, "native_near")
    a.movea(255, 0, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x4E, "native_near")
    a.addi(-200, 10, 10)
    a.branch(0x45, "class_lookup")
    a.label("class_zero")
    a.mov_i(0, 10)
    a.label("class_lookup")
    a.load_address(class_descriptor_ram, 20)
    a.jal("select_bank")
    a.reg(0x01, 10, 20)
    a.load(0x30, 0, 20, 10)
    a.fmt_v(0x2D, 0x00FF, 10, 10)
    a.branch(0x45, "record_select")

    a.label("name_select")
    a.movea(167, 0, 11)
    a.reg(0x03, 11, 7)
    a.branch(0x4E, "native_near")
    a.mov(7, 10)
    a.load_address(name_descriptor_ram, 20)
    a.jal("select_bank")
    a.reg(0x01, 10, 20)
    a.load(0x30, 0, 20, 10)
    a.fmt_v(0x2D, 0x00FF, 10, 10)
    a.movea(0x00FF, 0, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x42, "native_near")
    a.branch(0x45, "record_select")

    a.label("native_near")
    a.mov_i(1, 1)
    emit_jr(a, 0)  # patched to restore after finish
    native_restore_jr = len(a.code) - 4

    a.label("record_select")
    a.load_address(record_descriptor_ram, 20)
    a.jal("select_bank")
    a.label("record_walk")
    a.reg(0x03, 0, 10)
    a.branch(0x42, "record_found")
    a.label("skip_character")
    a.load(0x30, 0, 20, 11)
    a.fmt_v(0x2D, 0x00FF, 11, 11)
    a.add_i(1, 20)
    a.fmt_v(0x2D, 0x0080, 11, 11)
    a.reg(0x03, 0, 11)
    a.branch(0x42, "skip_character")
    a.add_i(-1, 10)
    a.branch(0x4A, "record_walk")
    a.label("record_found")
    a.mov(20, 21)

    a.reg(0x03, 0, 25)
    a.branch(0x4A, "name_upload")
    a.load_address(CLASS_CG_WORD, 6)
    a.branch(0x45, "do_upload")
    a.label("name_upload")
    a.load_address(NAME_CG_WORD, 6)
    a.label("do_upload")
    a.load_address(glyph_bank0_ram, 16)
    a.load_address(glyph_bank1_ram, 17)
    a.load_address(lut_ram, 24)
    a.jal(upload_ram)

    a.reg(0x03, 0, 25)
    a.branch(0x4A, "name_bat")
    a.load_address(CLASS_BAT_WORD, 20)
    a.mov_i(0, 22)
    a.mov_i(8, 23)
    a.reg(0x02, 19, 23)
    a.movea(CLASS_TILE_FIRST, 0, 24)
    a.branch(0x45, "do_bat")
    a.label("name_bat")
    a.load_address(NAME_BAT_WORD, 20)
    a.mov_i(0, 22)
    a.mov_i(9, 23)
    a.reg(0x02, 19, 23)
    a.movea(NAME_TILE_FIRST, 0, 24)
    a.label("do_bat")
    a.jal(bat_ram)
    a.addi(BAT_SECOND_ROW_DELTA, 20, 20)
    a.jal(bat_ram)
    a.mov_i(0, 1)
    a.branch(0x45, "restore")

    a.label("restore")
    for index, register in reversed(list(enumerate(saved, 1))):
        a.load(0x33, index * 4, 3, register)
    a.load(0x33, 0, 3, 31)
    a.addi(frame_size, 3, 3)
    a.reg(0x03, 0, 1)
    a.branch(0x4A, "tail_native")
    a.reg(0x06, 31, 0)
    a.label("tail_native")
    emit_jr(a, NATIVE_DECODER_RAM)

    # Generic descriptor lookup.  Each aligned descriptor is
    # (entry_count:u8, pad[3], data_address:u32).  Input r10 is an index and
    # r20 points at the first descriptor; output is the selected bank pointer
    # in r20 and the bank-relative index in r10.
    a.label("select_bank")
    a.mov(31, 26)
    a.label("bank_loop")
    a.load(0x30, 0, 20, 11)
    a.fmt_v(0x2D, 0x00FF, 11, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x46, "bank_found")
    a.reg(0x02, 11, 10)
    a.add_i(8, 20)
    a.branch(0x45, "bank_loop")
    a.label("bank_found")
    a.load(0x33, 4, 20, 20)
    a.reg(0x06, 26, 0)

    output = bytearray(a.finish())
    output[native_restore_jr:native_restore_jr + 4] = encode_jr(
        base + native_restore_jr, a.labels["restore"]
    )
    return bytes(output), dict(a.labels)


def decode_name_table(cooked: bytes) -> list[str]:
    result = []
    table = 0x53AE4 - RAM_DELTA
    for name_id in range(167):
        pointer = struct.unpack_from("<I", cooked, table + name_id * 4)[0]
        offset = pointer - RAM_DELTA
        end = cooked.index(0, offset)
        result.append(unicodedata.normalize("NFKC", cooked[offset:end].decode("cp932")))
    return result


def build_assets(cooked: bytes) -> dict[str, object]:
    native_names = decode_name_table(cooked)
    unknown = sorted(set(native_names) - set(NAME_TRANSLATIONS) - {""})
    if unknown:
        raise SystemExit(f"untranslated native bottom-HUD names: {unknown}")

    name_labels = [
        NAME_TRANSLATIONS.get(name) if name_id in PRIVATE_NAME_IDS else None
        for name_id, name in enumerate(native_names)
    ]
    all_labels = list(dict.fromkeys([*CLASS_LABELS, *(x for x in name_labels if x)]))
    characters = list(dict.fromkeys("".join(all_labels)))
    if len(characters) > 127:
        raise SystemExit(f"too many private glyphs for high-bit records: {len(characters)}")
    glyph_id = {character: index for index, character in enumerate(characters)}
    label_id = {label: index for index, label in enumerate(all_labels)}
    if len(all_labels) > 255:
        raise SystemExit("too many shared label records")

    record_rows: list[bytes] = []
    for label in all_labels:
        encoded = [glyph_id[character] for character in label]
        if not encoded:
            raise SystemExit("empty private label")
        encoded[-1] |= 0x80
        record_rows.append(bytes(encoded))
    records = b"".join(record_rows)

    class_map = bytes(label_id[label] for label in CLASS_LABELS)
    name_map = bytes(0xFF if label is None else label_id[label] for label in name_labels)

    glyph_rows = bytearray()
    glyph_images: dict[str, Image.Image] = {}
    glyph_rows_hex: dict[str, str] = {}
    for character in characters:
        rows, image = load_bdf_cell(
            GALMURI7, ord(character), cell_width=8, cell_height=8,
            ascent=7, center_x=True,
        )
        if len(rows) != 8 or rows[-1] != 0:
            raise SystemExit(f"{character}: Galmuri7 eighth row is not blank")
        glyph_rows.extend(rows[:7])
        glyph_images[character] = image
        glyph_rows_hex[character] = rows.hex().upper()

    lut = bytearray()
    for nibble in range(16):
        word = 0
        for bit in range(4):
            if nibble & (1 << (3 - bit)):
                word |= 1 << (12 - bit * 4)
        lut.extend(struct.pack("<H", word))

    return {
        "native_names": native_names,
        "name_labels": name_labels,
        "labels": all_labels,
        "characters": characters,
        "records": records,
        "record_rows": record_rows,
        "class_map": class_map,
        "name_map": name_map,
        "glyph_rows": bytes(glyph_rows),
        "glyph_images": glyph_images,
        "glyph_rows_hex": glyph_rows_hex,
        "lut": bytes(lut),
    }


def verify_status_class_correlation(cooked: bytes) -> list[dict[str, object]]:
    """Prove the exact Korean status strings that trigger the HUD mismatch."""
    charset_path = ROOT / "analysis/hangul_charset_v342-r57-safe-table-font-repair.json"
    charset = json.loads(charset_path.read_text(encoding="utf-8"))
    code_to_character = {
        int(row["code"], 0): str(row["character"])
        for row in charset["mappings"]
    }
    table = 0x536E8 - RAM_DELTA
    class_ids = (14, *range(201, 255))
    rows = []
    decoded = []
    for class_id in class_ids:
        pointer = struct.unpack_from("<I", cooked, table + class_id * 4)[0]
        offset = pointer - RAM_DELTA
        cursor = offset
        text = []
        raw = bytearray()
        while cooked[cursor] != 0:
            code = (cooked[cursor] << 8) | cooked[cursor + 1]
            if code not in code_to_character:
                raise SystemExit(f"class {class_id}: unknown private code 0x{code:04X}")
            text.append(code_to_character[code])
            raw.extend(cooked[cursor:cursor + 2])
            cursor += 2
        label = "".join(text)
        decoded.append(label)
        rows.append({
            "class_id": class_id,
            "pointer_ram": f"0x{pointer:X}",
            "private_bytes": raw.hex().upper(),
            "status_text": label,
        })
    if tuple(decoded) != CLASS_LABELS:
        for class_id, actual, expected in zip(class_ids, decoded, CLASS_LABELS):
            if actual != expected:
                raise SystemExit(
                    f"class correlation changed at ID {class_id}: {actual} != {expected}"
                )
        raise SystemExit("class correlation length changed")
    return rows


def subtract_interval(
    spans: list[tuple[int, int, int]], start: int, end: int
) -> list[tuple[int, int, int]]:
    output = []
    for left, right, fill in spans:
        if end <= left or start >= right:
            output.append((left, right, fill))
            continue
        if start > left:
            output.append((left, start, fill))
        if end < right:
            output.append((end, right, fill))
    return output


class SpanAllocator:
    def __init__(self, spans: list[tuple[int, int, int]]) -> None:
        self.spans = list(spans)

    def _largest(self) -> tuple[int, int, int]:
        if not self.spans:
            raise SystemExit("R67 private padding exhausted")
        return max(self.spans, key=lambda row: row[1] - row[0])

    def take(self, length: int, purpose: str) -> dict[str, object]:
        candidates = [row for row in self.spans if row[1] - row[0] >= length]
        if not candidates:
            raise SystemExit(f"no private span can hold {purpose} ({length} bytes)")
        left, right, fill = min(candidates, key=lambda row: row[1] - row[0])
        self.spans.remove((left, right, fill))
        if left + length < right:
            self.spans.append((left + length, right, fill))
        return {"cooked": left, "fill": fill, "purpose": purpose}

    def split_bytes(self, data: bytes, purpose: str) -> list[dict[str, object]]:
        cursor = 0
        banks = []
        while cursor < len(data):
            left, right, fill = self._largest()
            self.spans.remove((left, right, fill))
            count = min(right - left, len(data) - cursor, 255)
            chunk = data[cursor:cursor + count]
            banks.append({
                "cooked": left, "fill": fill, "purpose": purpose,
                "count": count, "data": chunk,
            })
            cursor += count
            if left + count < right:
                self.spans.append((left + count, right, fill))
        return banks

    def split_records(
        self, rows: list[bytes], purpose: str
    ) -> list[dict[str, object]]:
        cursor = 0
        banks = []
        while cursor < len(rows):
            ranked = sorted(self.spans, key=lambda row: row[1] - row[0], reverse=True)
            selected = None
            for left, right, fill in ranked:
                if len(rows[cursor]) <= right - left:
                    selected = (left, right, fill)
                    break
            if selected is None:
                raise SystemExit("no private span can hold the next label record")
            left, right, fill = selected
            self.spans.remove(selected)
            payload = bytearray()
            first = cursor
            while cursor < len(rows) and len(payload) + len(rows[cursor]) <= right - left:
                payload.extend(rows[cursor])
                cursor += 1
            banks.append({
                "cooked": left, "fill": fill, "purpose": purpose,
                "count": cursor - first, "data": bytes(payload),
            })
            if left + len(payload) < right:
                self.spans.append((left + len(payload), right, fill))
        return banks


def descriptor_bytes(banks: list[dict[str, object]]) -> bytes:
    output = bytearray()
    for bank in banks:
        count = int(bank["count"])
        if not 1 <= count <= 255:
            raise SystemExit("descriptor count is outside one byte")
        output.extend(struct.pack("<B3xI", count, int(bank["cooked"]) + RAM_DELTA))
    return bytes(output)


def validate_instruction_stream(code: bytes, base: int) -> dict[str, object]:
    image = bytes(base) + code
    pc = base
    end = base + len(code)
    opcodes = set()
    count = 0
    while pc < end:
        instruction = decode(image, pc)
        opcode = int(instruction["opcode"])
        if opcode not in OPNAMES and opcode not in {0x14, 0x15}:
            raise SystemExit(f"unknown V810 opcode 0x{opcode:X} at 0x{pc:X}")
        size = int(instruction["size"])
        if pc + size > end:
            raise SystemExit("V810 instruction crosses fragment boundary")
        opcodes.add(str(instruction["name"]))
        count += 1
        pc += size
    if pc != end:
        raise SystemExit("V810 validation ended at the wrong boundary")
    return {"bytes": len(code), "instructions": count, "opcodes": sorted(opcodes)}


def render_preview(assets: dict[str, object]) -> None:
    labels = ("워록", "기사단장", "엘윈", "스코트", "로렌", "리델", "에반제")
    images = assets["glyph_images"]
    width = max(len(label) for label in labels) * 8
    canvas = Image.new("L", (width, len(labels) * 10), 0)
    for row, label in enumerate(labels):
        for column, character in enumerate(label):
            canvas.paste(images[character], (column * 8, row * 10))
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    canvas.resize((width * 8, len(labels) * 80), Image.Resampling.NEAREST).save(PREVIEW)


def main() -> int:
    cooked = SOURCE.read_bytes()
    if sha256(cooked) != SOURCE_SHA256:
        raise SystemExit("R66 cooked baseline SHA-256 mismatch")
    if sha256(GALMURI7.read_bytes()) != GALMURI7_SHA256:
        raise SystemExit("Galmuri7 SHA-256 mismatch")
    if sha256(GALMURI_LICENSE.read_bytes()) != GALMURI_LICENSE_SHA256:
        raise SystemExit("Galmuri license SHA-256 mismatch")
    assets = build_assets(cooked)
    correlation = verify_status_class_correlation(cooked)

    if max(map(len, CLASS_LABELS)) > 8:
        raise SystemExit("class label exceeds its private eight-cell field")
    visible_names = [label for label in assets["name_labels"] if label]
    if max(map(len, visible_names)) > 9:
        raise SystemExit("name label exceeds its private nine-cell field")

    main_cooked = 0x0880
    upload_cooked = 0x0768
    bat_cooked = 0x0F60
    glyph0_cooked = 0x0D0B
    glyph1_cooked = 0x0B9D
    lut_cooked = 0x0850
    glyph_split = 71

    glyph_rows = assets["glyph_rows"]
    glyph0 = glyph_rows[:glyph_split * 7]
    glyph1 = glyph_rows[glyph_split * 7:]
    if len(glyph0) != 497 or len(glyph1) != 315:
        raise SystemExit("unexpected R67 glyph-bank split")

    upload = build_upload_helper(upload_cooked + RAM_DELTA, glyph_split)
    bat = build_bat_helper(bat_cooked + RAM_DELTA)
    placeholder, _ = build_main_handler(
        main_cooked + RAM_DELTA, 0x7A20, 0x7A40, 0x7A60,
        upload_cooked + RAM_DELTA, bat_cooked + RAM_DELTA,
        glyph0_cooked + RAM_DELTA, glyph1_cooked + RAM_DELTA,
        lut_cooked + RAM_DELTA,
    )

    spans = list(CAVES + DATA_CAVES)
    fixed_intervals = (
        (main_cooked, 0x0ABC),
        (upload_cooked, upload_cooked + len(upload)),
        (bat_cooked, bat_cooked + len(bat)),
        (glyph0_cooked, glyph0_cooked + len(glyph0)),
        (glyph1_cooked, glyph1_cooked + len(glyph1)),
        (lut_cooked, lut_cooked + len(assets["lut"])),
    )
    for start, end in fixed_intervals:
        spans = subtract_interval(spans, start, end)
    allocator = SpanAllocator(spans)

    # Map chunks may end anywhere.  Label records remain whole inside each
    # chunk so the runtime never crosses an unrelated padding gap.
    name_banks = allocator.split_bytes(assets["name_map"], "name-map")
    class_banks = allocator.split_bytes(assets["class_map"], "class-map")
    record_banks = allocator.split_records(assets["record_rows"], "label-records")

    main_end = main_cooked + len(placeholder)
    descriptor_cooked = (main_end + 3) & ~3
    class_descriptor = descriptor_bytes(class_banks)
    class_descriptor_cooked = descriptor_cooked
    name_descriptor_cooked = class_descriptor_cooked + len(class_descriptor)
    name_descriptor = descriptor_bytes(name_banks)
    record_descriptor_cooked = name_descriptor_cooked + len(name_descriptor)
    record_descriptor = descriptor_bytes(record_banks)
    descriptors = class_descriptor + name_descriptor + record_descriptor
    if descriptor_cooked + len(descriptors) > 0x0ABC:
        raise SystemExit(
            f"descriptor table ends at 0x{descriptor_cooked + len(descriptors):X}, "
            "past the private main cave"
        )

    main_code, symbols = build_main_handler(
        main_cooked + RAM_DELTA,
        class_descriptor_cooked + RAM_DELTA,
        name_descriptor_cooked + RAM_DELTA,
        record_descriptor_cooked + RAM_DELTA,
        upload_cooked + RAM_DELTA,
        bat_cooked + RAM_DELTA,
        glyph0_cooked + RAM_DELTA,
        glyph1_cooked + RAM_DELTA,
        lut_cooked + RAM_DELTA,
    )
    if len(main_code) != len(placeholder):
        raise SystemExit("main handler size changed after descriptor placement")

    validations = {
        "main": validate_instruction_stream(main_code, main_cooked + RAM_DELTA),
        "upload": validate_instruction_stream(upload, upload_cooked + RAM_DELTA),
        "bat": validate_instruction_stream(bat, bat_cooked + RAM_DELTA),
    }

    writes: list[dict[str, object]] = []

    def add_write(
        purpose: str, offset: int, data: bytes, fill: int | None = 0,
        expected: bytes | None = None,
    ) -> None:
        wanted = expected if expected is not None else bytes((int(fill),)) * len(data)
        actual = cooked[offset:offset + len(data)]
        if actual != wanted:
            mismatch = next(
                (index for index, pair in enumerate(zip(actual, wanted)) if pair[0] != pair[1]),
                min(len(actual), len(wanted)),
            )
            raise SystemExit(f"{purpose}: expected bytes changed at 0x{offset + mismatch:X}")
        writes.append({
            "purpose": purpose, "cooked": offset, "data": data,
            "expected": wanted,
        })

    add_write("main-handler", main_cooked, main_code)
    if descriptor_cooked > main_end:
        if cooked[main_end:descriptor_cooked] != bytes(descriptor_cooked - main_end):
            raise SystemExit("main descriptor alignment gap is no longer zero")
    add_write("bank-descriptors", descriptor_cooked, descriptors)
    add_write("glyph-uploader", upload_cooked, upload)
    add_write("bat-row-writer", bat_cooked, bat)
    add_write("glyph-bank-0", glyph0_cooked, glyph0)
    add_write("glyph-bank-1", glyph1_cooked, glyph1)
    add_write("private-4bpp-lut", lut_cooked, assets["lut"])

    for bank in (*name_banks, *class_banks, *record_banks):
        add_write(
            str(bank["purpose"]), int(bank["cooked"]), bank["data"],
            fill=int(bank["fill"]),
        )

    expected_class_call = encode_jal(CLASS_CALL_RAM, NATIVE_DECODER_RAM)
    expected_name_call = encode_jal(NAME_CALL_RAM, NATIVE_DECODER_RAM)
    add_write(
        "class-consumer-hook", CLASS_CALL_COOKED,
        encode_jal(CLASS_CALL_RAM, symbols["class_entry"]),
        expected=expected_class_call,
    )
    add_write(
        "name-consumer-hook", NAME_CALL_COOKED,
        encode_jal(NAME_CALL_RAM, symbols["name_entry"]),
        expected=expected_name_call,
    )

    writes.sort(key=lambda row: int(row["cooked"]))
    for previous, current in zip(writes, writes[1:]):
        previous_end = int(previous["cooked"]) + len(previous["data"])
        if int(current["cooked"]) < previous_end:
            raise SystemExit(
                f"R67 write overlap: {previous['purpose']} / {current['purpose']}"
            )

    output = bytearray(cooked)
    for row in writes:
        start = int(row["cooked"])
        output[start:start + len(row["data"])] = row["data"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(output)

    asset_root = ROOT / "assets/hooks"
    asset_root.mkdir(parents=True, exist_ok=True)
    glyph_asset = asset_root / "r67-bottom-hud-galmuri7-8x8-rows.bin"
    record_asset = asset_root / "r67-bottom-hud-label-records.bin"
    glyph_asset.write_bytes(glyph_rows)
    record_asset.write_bytes(assets["records"])
    render_preview(assets)

    manifest = {
        "version": "r67",
        "purpose": "dedicated Galmuri7 8x8 bottom-HUD Korean class and name renderer",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": SOURCE_SHA256,
        "output": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "output_sha256": sha256(bytes(output)),
        "font": {
            "name": "Galmuri7", "version": "2.40.4", "cell": "8x8",
            "source_sha256": GALMURI7_SHA256,
            "license_sha256": GALMURI_LICENSE_SHA256,
            "glyph_count": len(assets["characters"]),
            "glyph_rows_sha256": sha256(glyph_rows),
            "glyph_asset": str(glyph_asset.relative_to(ROOT)).replace("\\", "/"),
            "preview": str(PREVIEW.relative_to(ROOT)).replace("\\", "/"),
        },
        "correlation": {
            "native_bottom_hud_decoder": f"0x{NATIVE_DECODER_RAM:X}",
            "status_class_encoding": "private two-byte F0/F1/F2 Korean codes",
            "bottom_hud_encoding": "native one-byte consumer",
            "verified_korean_class_rows": correlation,
            "conclusion": (
                "the status class strings are valid; corruption occurs only when the "
                "byte-oriented bottom-HUD consumer reads those two-byte strings"
            ),
        },
        "layout": {
            "class": {
                "tile_range": ["0xD40", "0xD47"],
                "bat_first_word": f"0x{CLASS_BAT_WORD:X}",
                "cells": 8,
                "alignment": "fixed start at the column directly above the L-level origin",
            },
            "name": {
                "tile_range": ["0xD50", "0xD58"],
                "bat_first_word": f"0x{NAME_BAT_WORD:X}",
                "cells": 9, "alignment": "existing fixed name origin preserved",
            },
            "buffers_written": ["0x21E80 row", "0x21EA0 row"],
            "blank_bat": f"0x{BLANK_BAT:04X}",
        },
        "scope": {
            "class_ids": [14, *range(201, 255)],
            "name_ids": sorted(PRIVATE_NAME_IDS),
            "native_fallback_name_ids": [
                name_id for name_id in range(167) if name_id not in PRIVATE_NAME_IDS
            ],
            "name_labels": {
                str(name_id): label for name_id, label in enumerate(assets["name_labels"])
                if label is not None
            },
            "monster_only_names": "native fallback; no Japanese tile is overwritten",
        },
        "private_allocations": [
            {
                "purpose": str(row["purpose"]),
                "cooked": f"0x{int(row['cooked']):X}",
                "ram": f"0x{int(row['cooked']) + RAM_DELTA:X}",
                "bytes": len(row["data"]),
                "expected_sha256": sha256(row["expected"]),
                "replacement_sha256": sha256(row["data"]),
            }
            for row in writes
        ],
        "descriptor_banks": {
            "class": [{"count": int(x["count"]), "ram": f"0x{int(x['cooked']) + RAM_DELTA:X}"} for x in class_banks],
            "name": [{"count": int(x["count"]), "ram": f"0x{int(x['cooked']) + RAM_DELTA:X}"} for x in name_banks],
            "records": [{"count": int(x["count"]), "ram": f"0x{int(x['cooked']) + RAM_DELTA:X}"} for x in record_banks],
        },
        "code_validation": validations,
        "invariants": {
            "existing_r66_payload_modified": False,
            "resident_hangul_glyph_modified": False,
            "native_japanese_glyph_modified": False,
            "class_and_name_tiles_overlap": False,
            "stale_cells_cleared_on_every_draw": True,
            "four_pixel_space_rule": "no space glyph is emitted by these compact HUD labels",
        },
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"labels={len(assets['labels'])} glyphs={len(assets['characters'])} "
        f"records={len(assets['records'])} main={len(main_code)} "
        f"upload={len(upload)} bat={len(bat)} descriptors={len(descriptors)}"
    )
    print(f"name_banks={len(name_banks)} class_banks={len(class_banks)} record_banks={len(record_banks)}")
    print(f"output={OUTPUT}")
    print(f"sha256={manifest['output_sha256']}")
    print(f"manifest={MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
