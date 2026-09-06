#!/usr/bin/env python3
"""Normalize the dedicated AV/menu glyph bank to the 12x12 font policy."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from korean_font_policy import unifont_dense_12, verify_sources  # noqa: E402


AV_GLYPH_COOKED = 0x0004B452
GLYPH_BYTES = 18
AV_GLYPH_ROWS = (
    ("음", 0xF2C0, "배경음"),
    ("닝", 0xF2C1, "오프닝"),
    ("증", 0xF2C2, "증원"),
    ("점", 0xF2C3, "상점"),
)


class AvFontError(RuntimeError):
    pass


def need(ok: bool, message: str) -> None:
    if not ok:
        raise AvFontError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def planned_writes(source: bytes) -> tuple[list[dict], dict]:
    """Return one fixed-range write for the four dedicated AV glyphs."""

    verify_sources()
    replacement = b"".join(
        unifont_dense_12(character)[0]
        for character, _code, _use in AV_GLYPH_ROWS
    )
    need(len(replacement) == len(AV_GLYPH_ROWS) * GLYPH_BYTES,
         "AV 전용 글꼴 범위 오류")
    before = source[
        AV_GLYPH_COOKED:AV_GLYPH_COOKED + len(replacement)
    ]
    need(len(before) == len(replacement), "AV 전용 글꼴 기준 범위 초과")
    rows = []
    for index, (character, code, use) in enumerate(AV_GLYPH_ROWS):
        old = before[index * GLYPH_BYTES:(index + 1) * GLYPH_BYTES]
        new = replacement[index * GLYPH_BYTES:(index + 1) * GLYPH_BYTES]
        rows.append({
            "character": character,
            "code": f"0x{code:04X}",
            "use": use,
            "before_sha256": sha(old),
            "after_sha256": sha(new),
            "changed": old != new,
            "font": "GNU Unifont 17.0.05 / 12x12",
        })
    return ([{
        "id": "av-menu/all-dedicated-glyphs-unifont-12x12",
        "offset": AV_GLYPH_COOKED,
        "expected": before,
        "replacement": replacement,
    }], {
        "rows": rows,
        "cells": len(rows),
        "changed_cells": sum(row["changed"] for row in rows),
        "aliases": 0,
        "all_target_rasters_gnu_unifont_exact": True,
    })

