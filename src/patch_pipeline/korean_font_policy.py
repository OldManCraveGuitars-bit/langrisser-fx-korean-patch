#!/usr/bin/env python3
"""Deterministic Korean raster policy for the v342 patch.

Hangul is taken from the declared physical font for each rendering profile.
Do not infer semantics from Unicode alone: some legacy PUA cells now contain
whole Hangul names or split Hangul words. The cumulative 12x12 build audits
those owners through dialogue_editor/font_policy_12x12.py. Genuine spacing,
control, and numeral pixels remain protected byte assets.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from materialize_charset_glyphs import pack_cell


ROOT = Path(__file__).resolve().parents[1]
NEODGM = ROOT / "assets/fonts/neodgm-v1.601/neodgm.ttf"
NEODGM_SHA256 = "77305267996073AAE07BAD9313DAD2E306A4128E55BFAFBED4C41558FEE57B4D"
UNIFONT = ROOT / "assets/fonts/unifont-v17.0.05/unifont-17.0.05.otf"
UNIFONT_SHA256 = "85701AB9B1E251EE16F4DF00B13F22EAC311D72B7DAB427A7D975FE7F5064702"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest().upper()


def verify_sources() -> None:
    expected = ((NEODGM, NEODGM_SHA256), (UNIFONT, UNIFONT_SHA256))
    for path, wanted in expected:
        if not path.is_file():
            raise SystemExit(f"missing required font: {path}")
        actual = sha256_file(path)
        if actual != wanted:
            raise SystemExit(f"font SHA-256 mismatch: {path} {actual}")


def ks_x_1001_hangul() -> tuple[str, ...]:
    """Return the 2,350 precomposed Hangul syllables in KS X 1001 order."""
    return tuple(
        bytes((lead, trail)).decode("euc_kr")
        for lead in range(0xB0, 0xC9)
        for trail in range(0xA1, 0xFF)
    )


@lru_cache(maxsize=4)
def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


def validate_coverage(path: Path, size: int) -> list[str]:
    """Detect characters rendered as the font's missing-glyph box."""
    font = load_font(str(path), size)
    missing_mask = font.getmask(chr(0x10FFFF))
    missing_key = (missing_mask.size, bytes(missing_mask))
    missing = []
    for character in ks_x_1001_hangul():
        mask = font.getmask(character)
        if (mask.size, bytes(mask)) == missing_key:
            missing.append(character)
    return missing


def render_cell(
    character: str,
    *,
    path: Path,
    point_size: int,
    width: int,
    height: int,
    x_shift: int = 0,
    y_shift: int = 0,
) -> Image.Image:
    if len(character) != 1:
        raise ValueError("font cell requires exactly one Unicode character")
    font = load_font(str(path), point_size)
    bbox = font.getbbox(character, anchor="lt")
    glyph_width = bbox[2] - bbox[0]
    glyph_height = bbox[3] - bbox[1]
    x = (width - glyph_width) // 2 - bbox[0] + x_shift
    y = (height - glyph_height) // 2 - bbox[1] + y_shift
    # Draw directly into a 1bpp canvas.  At 12px, thresholding an antialiased
    # outline drops single-pixel Unifont strokes; FreeType's monochrome raster
    # keeps the intended pixel-font skeleton intact.
    canvas = Image.new("1", (width, height), 0)
    ImageDraw.Draw(canvas).text(
        (x, y), character, font=font, fill=1, anchor="lt"
    )
    return canvas


def unifont_cell_12(
    character: str,
    *,
    x_shift: int = 0,
    y_shift: int = 0,
) -> Image.Image:
    return render_cell(
        character,
        path=UNIFONT,
        point_size=12,
        width=12,
        height=12,
        x_shift=x_shift,
        y_shift=y_shift,
    )


def unifont_dense_12(
    character: str,
    *,
    x_shift: int = 0,
    y_shift: int = 0,
) -> tuple[bytes, Image.Image]:
    cell = unifont_cell_12(character, x_shift=x_shift, y_shift=y_shift)
    return pack_cell(cell), cell


def neodgm_cell_16(
    character: str,
    *,
    x_shift: int = 0,
    y_shift: int = 0,
) -> Image.Image:
    return render_cell(
        character,
        path=NEODGM,
        point_size=16,
        width=16,
        height=16,
        x_shift=x_shift,
        y_shift=y_shift,
    )
