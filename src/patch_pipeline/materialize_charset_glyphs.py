#!/usr/bin/env python3
"""Rasterize missing glyph assets and enrich a planned charset manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def pack_cell(cell: Image.Image) -> bytes:
    bits = [1 if cell.getpixel((x, y)) else 0 for y in range(12) for x in range(12)]
    data = bytearray()
    for start in range(0, 144, 8):
        value = 0
        for bit in bits[start:start + 8]:
            value = (value << 1) | bit
        data.append(value)
    return bytes(data)


def pack_pixels(pixels: list[list[int]]) -> tuple[bytes, Image.Image]:
    cell = Image.new("L", (12, 12), 0)
    for coordinate in pixels:
        if len(coordinate) != 2:
            raise ValueError(f"pixel coordinate must contain x and y: {coordinate}")
        x, y = map(int, coordinate)
        if not (0 <= x < 12 and 0 <= y < 12):
            raise ValueError(f"pixel coordinate outside 12x12 cell: {(x, y)}")
        cell.putpixel((x, y), 255)
    return pack_cell(cell), cell


def pack_pattern(pattern: list[str]) -> tuple[bytes, Image.Image]:
    if len(pattern) != 12 or any(len(row) != 12 for row in pattern):
        raise ValueError("glyph pattern must be exactly 12 rows of 12 columns")
    invalid = {character for row in pattern for character in row} - {".", "#"}
    if invalid:
        raise ValueError(f"glyph pattern contains unsupported pixels: {sorted(invalid)}")
    return pack_pixels(
        [[x, y] for y, row in enumerate(pattern) for x, pixel in enumerate(row) if pixel == "#"]
    )


def normalize_jongseong_ieung(cell: Image.Image) -> tuple[bytes, Image.Image]:
    normalized = cell.copy()
    for y in range(7, 12):
        for x in range(12):
            normalized.putpixel((x, y), 0)
    for x, y in (
        *((x, 7) for x in range(3, 9)),
        (2, 8),
        (9, 8),
        (2, 9),
        (9, 9),
        *((x, 10) for x in range(3, 9)),
    ):
        normalized.putpixel((x, y), 255)
    return pack_cell(normalized), normalized


def pack(character: str, font: ImageFont.FreeTypeFont, threshold: int,
         visual_width: int = 12, x_shift: int = 0,
         y_shift: int = 0) -> tuple[bytes, Image.Image]:
    canvas = Image.new("L", (24, 24), 0)
    draw = ImageDraw.Draw(canvas)
    bbox = draw.textbbox((0, 0), character, font=font)
    x = (12 - (bbox[2] - bbox[0])) // 2 - bbox[0] + x_shift
    y = (12 - (bbox[3] - bbox[1])) // 2 - bbox[1] + y_shift
    draw.text((x, y), character, font=font, fill=255)
    cell = canvas.crop((0, 0, 12, 12)).point(lambda value: 255 if value >= threshold else 0)
    if visual_width != 12:
        cell = cell.resize((visual_width, 12), Image.Resampling.NEAREST)
        narrowed = Image.new("L", (12, 12), 0)
        narrowed.paste(cell, (0, 0))
        cell = narrowed
    return pack_cell(cell), cell


def pack_text_tile(text: str, tile_index: int, leading_px: int,
                   font: ImageFont.FreeTypeFont, threshold: int) -> tuple[bytes, Image.Image]:
    width = (len(text) + 1) * 12
    canvas = Image.new("L", (width, 24), 0)
    draw = ImageDraw.Draw(canvas)
    for index, character in enumerate(text):
        bbox = draw.textbbox((0, 0), character, font=font)
        x = leading_px + index * 12 + (12 - (bbox[2] - bbox[0])) // 2 - bbox[0]
        y = (12 - (bbox[3] - bbox[1])) // 2 - bbox[1]
        draw.text((x, y), character, font=font, fill=255)
    left = tile_index * 12
    cell = canvas.crop((left, 0, left + 12, 12)).point(
        lambda value: 255 if value >= threshold else 0
    )
    return pack_cell(cell), cell


def pack_positioned_text_tile(text: str, positions: list[int], tile_index: int,
                              font: ImageFont.FreeTypeFont, threshold: int) -> tuple[bytes, Image.Image]:
    width = (tile_index + 1) * 12
    width = max(width, max(positions) + 12)
    canvas = Image.new("L", (width, 24), 0)
    draw = ImageDraw.Draw(canvas)
    for character, position in zip(text, positions, strict=True):
        bbox = draw.textbbox((0, 0), character, font=font)
        x = position + (12 - (bbox[2] - bbox[0])) // 2 - bbox[0]
        y = (12 - (bbox[3] - bbox[1])) // 2 - bbox[1]
        draw.text((x, y), character, font=font, fill=255)
    left = tile_index * 12
    cell = canvas.crop((left, 0, left + 12, 12)).point(
        lambda value: 255 if value >= threshold else 0
    )
    return pack_cell(cell), cell


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--font", type=Path, required=True,
                    help="path to a locally supplied font file")
    ap.add_argument("--size", type=int, default=12)
    ap.add_argument("--threshold", type=int, default=96)
    ap.add_argument("--preview-dir", type=Path)
    ap.add_argument("--aliases", type=Path,
                    help="JSON mapping a private character to source/visual_width")
    args = ap.parse_args()
    root = args.output.parent.parent
    document = json.loads(args.input.read_text(encoding="utf-8"))
    font = ImageFont.truetype(str(args.font), args.size)
    font_cache = {args.size: font}
    aliases = json.loads(args.aliases.read_text(encoding="utf-8")) if args.aliases else {}
    created = 0
    for item in document["mappings"]:
        if "glyph" in item:
            continue
        code = int(item["code"], 0)
        relative = Path("assets") / "glyphs" / f"private-{code:04x}-12x12.bin"
        alias = aliases.get(item["character"], {})
        glyph_size = int(alias.get("size", args.size))
        if glyph_size not in font_cache:
            font_cache[glyph_size] = ImageFont.truetype(str(args.font), glyph_size)
        glyph_font = font_cache[glyph_size]
        glyph_threshold = int(alias.get("threshold", args.threshold))
        if "pattern" in alias:
            data, cell = pack_pattern(alias["pattern"])
        elif "pixels" in alias:
            data, cell = pack_pixels(alias["pixels"])
        elif "positions" in alias:
            data, cell = pack_positioned_text_tile(
                alias["source_text"], [int(value) for value in alias["positions"]],
                int(alias["tile_index"]), glyph_font, glyph_threshold
            )
        elif "source_text" in alias:
            data, cell = pack_text_tile(
                alias["source_text"], int(alias["tile_index"]),
                int(alias.get("leading_px", 6)), glyph_font, glyph_threshold
            )
        else:
            source = alias.get("source", item["character"])
            visual_width = int(alias.get("visual_width", 12))
            x_shift = int(alias.get("x_shift", 0))
            y_shift = int(alias.get("y_shift", 0))
            data, cell = pack(
                source, glyph_font, glyph_threshold, visual_width, x_shift, y_shift
            )
        if alias.get("normalize_jongseong_ieung"):
            data, cell = normalize_jongseong_ieung(cell)
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        item["glyph"] = relative.as_posix()
        if args.preview_dir:
            args.preview_dir.mkdir(parents=True, exist_ok=True)
            cell.resize((192, 192), Image.Resampling.NEAREST).save(args.preview_dir / f"private-{code:04x}.png")
        created += 1
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"mappings={len(document['mappings'])} glyphs_created={created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
