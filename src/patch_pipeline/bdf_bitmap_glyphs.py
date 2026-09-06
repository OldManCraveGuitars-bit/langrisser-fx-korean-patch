#!/usr/bin/env python3
"""Extract fixed-cell 1bpp glyphs from an ISO-10646 BDF font."""

from pathlib import Path

from PIL import Image

from materialize_charset_glyphs import pack_cell


def load_bdf_cell(
    path: Path,
    codepoint: int,
    cell_width: int = 12,
    cell_height: int = 12,
    ascent: int = 12,
    center_x: bool = False,
    x_shift: int = 0,
    y_shift: int = 0,
) -> tuple[bytes, Image.Image]:
    # BDF syntax itself is ASCII, but some maintained fonts include UTF-8
    # copyright/comment fields.  UTF-8 remains byte-compatible with ordinary
    # ASCII-only BDF sources and lets us consume those files without rewriting
    # the upstream asset.
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    wanted = f"ENCODING {codepoint}"
    try:
        encoding_index = lines.index(wanted)
    except ValueError as exc:
        raise KeyError(f"U+{codepoint:04X} is missing from {path}") from exc

    bbx_line = next(
        line for line in lines[encoding_index:] if line.startswith("BBX ")
    )
    width, height, x_offset, y_offset = map(int, bbx_line.split()[1:])
    bitmap_index = lines.index("BITMAP", encoding_index)
    rows = lines[bitmap_index + 1 : bitmap_index + 1 + height]
    if len(rows) != height:
        raise ValueError(f"U+{codepoint:04X}: truncated BDF bitmap")

    cell = Image.new("L", (cell_width, cell_height), 0)
    left = (cell_width - width) // 2 if center_x else x_offset
    left += x_shift
    top = ascent - y_offset - height + y_shift
    for source_y, row_hex in enumerate(rows):
        row_bits = len(row_hex) * 4
        value = int(row_hex, 16)
        for source_x in range(width):
            if value & (1 << (row_bits - 1 - source_x)):
                x = left + source_x
                y = top + source_y
                if 0 <= x < cell_width and 0 <= y < cell_height:
                    cell.putpixel((x, y), 255)
    if cell_width == 12 and cell_height == 12:
        packed = pack_cell(cell)
    else:
        if cell_width % 8:
            raise ValueError("non-12px BDF cells must have an 8px-aligned width")
        packed_bytes = bytearray()
        for y in range(cell_height):
            for byte_x in range(cell_width // 8):
                value = 0
                for bit in range(8):
                    if cell.getpixel((byte_x * 8 + bit, y)):
                        value |= 1 << (7 - bit)
                packed_bytes.append(value)
        packed = bytes(packed_bytes)
    return packed, cell
