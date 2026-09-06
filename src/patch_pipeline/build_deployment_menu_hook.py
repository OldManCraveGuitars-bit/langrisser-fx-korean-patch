#!/usr/bin/env python3
"""Build the scenario-deployment Korean menu V810 runtime hook.

The deployment screen reloads its Japanese KING tile asset every time it is
entered, so a static K-RAM/save-state edit is not persistent.  This hook wraps
the final setup call, uploads compact 1bpp Korean labels as 4bpp KING tiles,
and rewrites only the eight BAT rows occupied by the four menu labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HOOK_COOKED = 0x7F200
MAIN_IMAGE_RAM_DELTA = 0x7000
HOOK_RAM = HOOK_COOKED + MAIN_IMAGE_RAM_DELTA
HOOK_CAPACITY = 0x600
CALL_RAM = 0x1C3E2
CALL_COOKED = 0x153E2
ORIGINAL_TARGET = 0xFA94
CG_WORD_ADDRESS = 0x2B000
BAT_FIRST_WORD = 0x21800 + 7 * 64 + 4
TILE_FIRST = 0xB00
BAT_COLUMNS = 12

LINES = (
    ("병사 배속", 8),
    ("아이템 장비", 9),
    ("지휘관 배치", 9),
    ("출격", 3),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def encode_jal(pc: int, target: int) -> bytes:
    displacement = target - pc
    if displacement & 1 or not -(1 << 25) <= displacement < (1 << 25):
        raise ValueError(f"JAL displacement out of range: {displacement}")
    value = displacement & ((1 << 26) - 1)
    return bytes((
        (value >> 16) & 0xFF,
        0xAC | ((value >> 24) & 0x03),
        value & 0xFF,
        (value >> 8) & 0xFF,
    ))


@dataclass
class Assembler:
    base: int
    code: bytearray = field(default_factory=bytearray)
    labels: dict[str, int] = field(default_factory=dict)
    fixups: list[tuple[str, int, str | int, int]] = field(default_factory=list)

    @property
    def pc(self) -> int:
        return self.base + len(self.code)

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"duplicate label: {name}")
        self.labels[name] = self.pc

    def halfword(self, value: int) -> None:
        self.code.extend(struct.pack("<H", value & 0xFFFF))

    def reg(self, opcode: int, source: int, destination: int) -> None:
        self.halfword((opcode << 10) | (destination << 5) | source)

    def imm5(self, opcode: int, immediate: int, destination: int) -> None:
        if not -16 <= immediate <= 31:
            raise ValueError(f"5-bit immediate out of range: {immediate}")
        self.halfword((opcode << 10) | (destination << 5) | (immediate & 0x1F))

    def fmt_v(self, opcode: int, immediate: int, base: int, destination: int) -> None:
        self.halfword((opcode << 10) | (destination << 5) | base)
        self.halfword(immediate)

    def mov(self, source: int, destination: int) -> None:
        self.reg(0x00, source, destination)

    def mov_i(self, immediate: int, destination: int) -> None:
        self.imm5(0x10, immediate, destination)

    def add_i(self, immediate: int, destination: int) -> None:
        self.imm5(0x11, immediate, destination)

    def addi(self, immediate: int, base: int, destination: int) -> None:
        self.fmt_v(0x29, immediate, base, destination)

    def movea(self, immediate: int, base: int, destination: int) -> None:
        self.fmt_v(0x28, immediate, base, destination)

    def movhi(self, immediate: int, base: int, destination: int) -> None:
        self.fmt_v(0x2F, immediate, base, destination)

    def load_address(self, address: int, destination: int) -> None:
        upper = (address + 0x8000) >> 16
        lower = address - (upper << 16)
        self.movhi(upper, 0, destination)
        self.movea(lower, destination, destination)

    def load(self, opcode: int, displacement: int, base: int, destination: int) -> None:
        self.fmt_v(opcode, displacement, base, destination)

    def store(self, opcode: int, displacement: int, base: int, value: int) -> None:
        self.fmt_v(opcode, displacement, base, value)

    def out(self, opcode: int, displacement: int, base: int, value: int) -> None:
        self.fmt_v(opcode, displacement, base, value)

    def jal(self, target: str | int) -> None:
        offset = len(self.code)
        self.code.extend(b"\0" * 4)
        self.fixups.append(("jal", offset, target, 0))

    def branch(self, condition: int, target: str) -> None:
        offset = len(self.code)
        self.halfword(condition << 9)
        self.fixups.append(("branch", offset, target, condition))

    def finish(self) -> bytes:
        output = bytearray(self.code)
        for kind, offset, target, condition in self.fixups:
            address = self.labels[target] if isinstance(target, str) else target
            pc = self.base + offset
            if kind == "jal":
                output[offset:offset + 4] = encode_jal(pc, address)
            else:
                displacement = address - pc
                if displacement & 1 or not -256 <= displacement <= 254:
                    raise ValueError(f"branch displacement out of range: {displacement}")
                struct.pack_into("<H", output, offset, (condition << 9) | (displacement & 0x1FE))
        return bytes(output)


def render_line(text: str, width: int, font: ImageFont.FreeTypeFont,
                char_advance: int, word_gap: int) -> Image.Image:
    mask = Image.new("1", (width, 16), 0)
    draw = ImageDraw.Draw(mask)
    cursor = 0
    for character in text:
        if character == " ":
            cursor += word_gap
            continue
        bbox = draw.textbbox((0, 0), character, font=font)
        glyph_height = bbox[3] - bbox[1]
        y = (16 - glyph_height) // 2 - bbox[1]
        draw.text((cursor - bbox[0], y), character, font=font, fill=1)
        cursor += char_advance
    return mask


def pack_line_1bpp(image: Image.Image) -> bytes:
    if image.width % 8 or image.height != 16:
        raise ValueError("line bitmap must be an 8-pixel multiple by 16 pixels")
    output = bytearray()
    for tile_y in range(2):
        for tile_x in range(image.width // 8):
            for y in range(8):
                value = 0
                for x in range(8):
                    value |= int(bool(image.getpixel((tile_x * 8 + x, tile_y * 8 + y)))) << (7 - x)
                output.append(value)
    return bytes(output)


def build_code() -> tuple[bytes, dict[str, int]]:
    a = Assembler(HOOK_RAM)
    saved = list(range(6, 21)) + [30]
    frame_size = 4 + len(saved) * 4

    a.label("hook")
    a.addi(-frame_size, 3, 3)
    a.store(0x37, 0, 3, 31)
    a.jal(ORIGINAL_TARGET)
    for index, register in enumerate(saved, 1):
        a.store(0x37, index * 4, 3, register)

    # Upload 59 compact 1bpp tiles, expanded to 4bpp through a 16-entry LUT.
    a.load_address(CG_WORD_ADDRESS, 6)
    a.load_address(0, 7)  # fixed up once data labels are known
    glyph_pointer_movhi = len(a.code) - 8
    a.movea(472, 0, 8)
    a.load_address(0, 20)
    lut_pointer_movhi = len(a.code) - 8
    a.jal("upload_1bpp")

    # Eight consecutive BAT rows, described by (tile_first, visible_columns).
    a.load_address(BAT_FIRST_WORD, 6)
    a.load_address(0, 17)
    descriptors_pointer_movhi = len(a.code) - 8
    a.mov_i(8, 18)
    a.label("bat_rows")
    a.load(0x31, 0, 17, 7)
    a.load(0x31, 2, 17, 8)
    a.jal("upload_bat_row")
    a.add_i(4, 17)
    a.addi(64, 6, 6)
    a.add_i(-1, 18)
    a.branch(0x4A, "bat_rows")

    for index, register in reversed(list(enumerate(saved, 1))):
        a.load(0x33, index * 4, 3, register)
    a.load(0x33, 0, 3, 31)
    a.addi(frame_size, 3, 3)
    a.reg(0x06, 31, 0)  # jmp [lp]

    a.label("set_kram_write_address")
    a.mov(6, 30)
    a.mov_i(1, 1)
    a.imm5(0x14, 18, 1)
    a.reg(0x0C, 1, 30)
    a.mov_i(13, 1)
    a.out(0x3D, 0x0600, 0, 1)
    a.out(0x3F, 0x0604, 0, 30)
    a.mov_i(14, 1)
    a.out(0x3D, 0x0600, 0, 1)
    a.reg(0x06, 31, 0)

    a.label("upload_1bpp")
    a.mov(31, 13)
    a.jal("set_kram_write_address")
    a.mov(13, 31)
    a.label("glyph_loop")
    a.load(0x30, 0, 7, 10)
    a.fmt_v(0x2D, 0x00FF, 10, 10)
    a.mov(10, 11)
    a.imm5(0x15, 4, 10)
    a.fmt_v(0x2D, 0x000F, 11, 11)
    a.imm5(0x14, 1, 10)
    a.imm5(0x14, 1, 11)
    a.reg(0x01, 20, 10)
    a.reg(0x01, 20, 11)
    a.load(0x31, 0, 10, 10)
    a.load(0x31, 0, 11, 11)
    a.out(0x3D, 0x0604, 0, 10)
    a.out(0x3D, 0x0604, 0, 11)
    a.add_i(1, 7)
    a.add_i(-1, 8)
    a.branch(0x4A, "glyph_loop")
    a.reg(0x06, 31, 0)

    a.label("upload_bat_row")
    a.mov(31, 13)
    a.jal("set_kram_write_address")
    a.mov(13, 31)
    a.mov(7, 11)
    a.mov(8, 12)
    a.label("bat_real_loop")
    a.mov(11, 10)
    a.fmt_v(0x2C, 0x4000, 10, 10)
    a.out(0x3D, 0x0604, 0, 10)
    a.add_i(1, 11)
    a.add_i(-1, 12)
    a.branch(0x4A, "bat_real_loop")
    a.mov_i(BAT_COLUMNS, 12)
    a.reg(0x02, 8, 12)
    a.load_address(0x4000 | 0xB3A, 9)
    a.label("bat_blank_loop")
    a.out(0x3D, 0x0604, 0, 9)
    a.add_i(-1, 12)
    a.branch(0x4A, "bat_blank_loop")
    a.reg(0x06, 31, 0)

    code = bytearray(a.finish())
    labels = dict(a.labels)
    return bytes(code), {
        "glyph_pointer_movhi": glyph_pointer_movhi,
        "lut_pointer_movhi": lut_pointer_movhi,
        "descriptors_pointer_movhi": descriptors_pointer_movhi,
        **labels,
    }


def patch_load_address(code: bytearray, offset: int, address: int) -> None:
    upper = (address + 0x8000) >> 16
    lower = address - (upper << 16)
    struct.pack_into("<H", code, offset + 2, upper & 0xFFFF)
    struct.pack_into("<H", code, offset + 6, lower & 0xFFFF)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cooked", type=Path)
    ap.add_argument("manifest", type=Path)
    ap.add_argument("payload", type=Path)
    ap.add_argument("--font", type=Path, required=True,
                    help="path to a locally supplied font file")
    ap.add_argument("--font-size", type=int, default=11)
    ap.add_argument("--char-advance", type=int, default=12)
    ap.add_argument("--word-gap", type=int, default=8)
    ap.add_argument("--preview", type=Path)
    args = ap.parse_args()

    cooked = args.cooked.read_bytes()
    if cooked[HOOK_COOKED:HOOK_COOKED + HOOK_CAPACITY] != b"\0" * HOOK_CAPACITY:
        raise SystemExit("deployment hook storage is not the expected zero-filled region")
    original_call = cooked[CALL_COOKED:CALL_COOKED + 4]
    if original_call != encode_jal(CALL_RAM, ORIGINAL_TARGET):
        raise SystemExit(f"unexpected deployment final-call bytes: {original_call.hex()}")

    font = ImageFont.truetype(str(args.font), args.font_size)
    bitmaps = [render_line(text, columns * 8, font, args.char_advance, args.word_gap)
               for text, columns in LINES]
    glyph_data = b"".join(pack_line_1bpp(bitmap) for bitmap in bitmaps) + b"\0" * 8
    if len(glyph_data) != 472:
        raise AssertionError(f"unexpected compact glyph size: {len(glyph_data)}")

    tile_cursor = TILE_FIRST
    descriptors: list[tuple[int, int]] = []
    for (_, columns) in LINES:
        descriptors.append((tile_cursor, columns))
        descriptors.append((tile_cursor + columns, columns))
        tile_cursor += columns * 2
    if tile_cursor != 0xB3A:
        raise AssertionError(f"unexpected blank tile: 0x{tile_cursor:X}")
    descriptor_data = b"".join(struct.pack("<HH", *item) for item in descriptors)

    # Each set bit expands to palette index 3 in one 4-pixel KING word.
    lut = bytearray()
    for nibble in range(16):
        value = 0
        for bit in range(4):
            if nibble & (1 << (3 - bit)):
                value |= 3 << (12 - bit * 4)
        lut.extend(struct.pack("<H", value))

    code, symbols = build_code()
    code_buffer = bytearray(code)
    data_start = (HOOK_RAM + len(code_buffer) + 3) & ~3
    glyph_address = data_start
    lut_address = glyph_address + len(glyph_data)
    descriptors_address = lut_address + len(lut)
    patch_load_address(code_buffer, symbols["glyph_pointer_movhi"], glyph_address)
    patch_load_address(code_buffer, symbols["lut_pointer_movhi"], lut_address)
    patch_load_address(code_buffer, symbols["descriptors_pointer_movhi"], descriptors_address)
    payload = bytes(code_buffer).ljust(data_start - HOOK_RAM, b"\0") + glyph_data + bytes(lut) + descriptor_data
    if len(payload) > HOOK_CAPACITY:
        raise SystemExit(f"hook payload 0x{len(payload):X} exceeds 0x{HOOK_CAPACITY:X} capacity")

    args.payload.parent.mkdir(parents=True, exist_ok=True)
    args.payload.write_bytes(payload)
    call_replacement = encode_jal(CALL_RAM, HOOK_RAM)
    manifest = {
        "purpose": "persistent Korean deployment-menu KING tile/BAT runtime hook",
        "hook": {
            "ram_address": f"0x{HOOK_RAM:X}",
            "capacity": HOOK_CAPACITY,
            "payload_size": len(payload),
            "payload_sha256": sha256(payload),
            "original_target": f"0x{ORIGINAL_TARGET:X}",
            "call_ram": f"0x{CALL_RAM:X}",
            "cg_word_address": f"0x{CG_WORD_ADDRESS:X}",
            "bat_first_word": f"0x{BAT_FIRST_WORD:X}",
            "tile_range": [f"0x{TILE_FIRST:X}", "0xB3A"],
            "symbols": {key: f"0x{value:X}" for key, value in symbols.items()
                        if not key.endswith("_movhi")},
        },
        "labels": [text for text, _ in LINES],
        "font": str(args.font),
        "font_size": args.font_size,
        "char_advance": args.char_advance,
        "word_gap": args.word_gap,
        "edits": [
            {
                "id": "deployment-menu/runtime-hook-payload",
                "cooked_offset": f"0x{HOOK_COOKED:08X}",
                "expected_fill_hex": "00",
                "length": len(payload),
                "replacement_file": str(Path("..") / args.payload.relative_to(args.manifest.parent.parent)),
            },
            {
                "id": "deployment-menu/wrap-final-setup-call",
                "cooked_offset": f"0x{CALL_COOKED:08X}",
                "expected_hex": original_call.hex().upper(),
                "replacement_hex": call_replacement.hex().upper(),
            },
        ],
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.preview:
        preview = Image.new("RGB", (96, 64), (24, 24, 24))
        for line_index, bitmap in enumerate(bitmaps):
            for y in range(16):
                for x in range(bitmap.width):
                    if bitmap.getpixel((x, y)):
                        preview.putpixel((x, line_index * 16 + y), (255, 255, 255))
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        preview.resize((384, 256), Image.Resampling.NEAREST).save(args.preview)

    print(f"code=0x{len(code_buffer):X} glyph=0x{len(glyph_data):X} payload=0x{len(payload):X}")
    print(f"payload_sha256={sha256(payload)} call={call_replacement.hex().upper()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
