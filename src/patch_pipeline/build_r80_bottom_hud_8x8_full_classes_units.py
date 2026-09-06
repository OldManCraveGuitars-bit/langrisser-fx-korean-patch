#!/usr/bin/env python3
"""Build an R80 HUD covering every class and unit/name table ID.

This successor replaces the old hand-picked class denominator (14 and
201..254) with the actual 0..254 class pointer table and the complete 0..166
name table.  Records use an FF terminator so the combined Korean alphabet can
exceed the legacy 127-glyph high-bit format without touching native English
or numeric glyph storage.
"""

from __future__ import annotations

import json
import ast
import struct
import sys
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_bottom_hud_name_class_r67 as asset_builder  # noqa: E402
import build_bottom_hud_name_class_postcompose_r67 as hud  # noqa: E402
import build_r80_bottom_hud_8x8_highbank_global as base  # noqa: E402


NAME = "r80-bottom-hud-8x8-full-classes-units"
base.NAME = NAME
base.OUTPUT_DIR = ROOT / "work" / NAME
base.OUTPUT_COOKED = base.OUTPUT_DIR / f"track02-{NAME}.iso"
base.OUTPUT_RAW = base.OUTPUT_DIR / f"Track-2.{NAME}.bin"
base.OUTPUT_CUE = base.OUTPUT_DIR / f"Langrisser-FX-KR-{NAME}.cue"
base.OUTPUT_REPORT = ROOT / "analysis/r80-bottom-hud-8x8-full-classes-units-postbuild.json"

# A complete class/name alphabet and record set needs two additional sectors.
# Every full field subentry receives the same private tail, so the existing
# global resource-12 replication contract remains intact.
base.TAIL_BYTES = 0x1000
base.HIGH_LIMIT = base.HIGH_BASE + base.TAIL_BYTES
hud.GLYPH_SPLIT = 128

RAM_DELTA = 0x7000
CLASS_TABLE = 0x536E8 - RAM_DELTA
CLASS_COUNT = 255
PRIVATE_CHARSET = ROOT / "analysis/hangul_charset_v342-r57-safe-table-font-repair.json"
CLASS_TRANSLATION_SOURCE = ROOT / "tools/build_feedback_class_names_v362.py"


def load_class_translations() -> dict[str, str]:
    """Read the frozen BASE_NAMES literal without executing the old builder."""
    module = ast.parse(CLASS_TRANSLATION_SOURCE.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == "BASE_NAMES"
                for target in node.targets
            ):
                value = ast.literal_eval(node.value)
                return {str(key): str(label) for key, label in value.items()}
    raise SystemExit("BASE_NAMES literal not found in class translation source")


def decode_class_text(
    image: bytes, class_id: int, code_to_character: dict[int, str]
) -> str:
    pointer = struct.unpack_from("<I", image, CLASS_TABLE + class_id * 4)[0]
    offset = pointer - RAM_DELTA
    end = image.index(0, offset)
    raw = image[offset:end]
    if not raw:
        return ""
    if len(raw) % 2 == 0:
        private = []
        for cursor in range(0, len(raw), 2):
            code = (raw[cursor] << 8) | raw[cursor + 1]
            if code not in code_to_character:
                private = []
                break
            private.append(code_to_character[code])
        if private:
            return "".join(private)
    return unicodedata.normalize("NFKC", raw.decode("cp932"))


def build_full_assets(image: bytes) -> dict[str, object]:
    charset = json.loads(PRIVATE_CHARSET.read_text(encoding="utf-8"))
    code_to_character = {
        int(row["code"], 0): str(row["character"])
        for row in charset["mappings"]
    }

    class_translations = load_class_translations()
    class_labels: list[str | None] = []
    unresolved = []
    for class_id in range(CLASS_COUNT):
        source = decode_class_text(image, class_id, code_to_character).strip()
        if not source:
            class_labels.append(None)
        elif all("가" <= character <= "힣" for character in source):
            class_labels.append(source.replace(" ", ""))
        elif source in class_translations:
            class_labels.append(
                class_translations[source].replace(" ", "")
            )
        elif source in asset_builder.NAME_TRANSLATIONS:
            class_labels.append(
                asset_builder.NAME_TRANSLATIONS[source].replace(" ", "")
            )
        else:
            unresolved.append({"class_id": class_id, "source": source})
            class_labels.append(None)
    if unresolved:
        raise SystemExit(f"untranslated active class IDs: {unresolved}")

    native_names = asset_builder.decode_name_table(image)
    unknown_names = sorted(
        set(native_names) - set(asset_builder.NAME_TRANSLATIONS) - {""}
    )
    if unknown_names:
        raise SystemExit(f"untranslated native HUD names: {unknown_names}")
    name_labels = [
        asset_builder.NAME_TRANSLATIONS.get(name) if name else None
        for name in native_names
    ]

    if max(len(label) for label in class_labels if label) > hud.CLASS_CELLS:
        raise SystemExit("full class label exceeds the eight-cell HUD field")
    if max(len(label) for label in name_labels if label) > hud.NAME_CELLS:
        raise SystemExit("full unit/name label exceeds the nine-cell HUD field")

    labels = list(dict.fromkeys(
        label for label in [*class_labels, *name_labels] if label
    ))
    if len(labels) > 255:
        raise SystemExit(f"label-record ID overflow: {len(labels)}")
    characters = list(dict.fromkeys("".join(labels)))
    if len(characters) > 255:
        raise SystemExit(f"unsigned glyph-ID overflow: {len(characters)}")

    glyph_id = {character: index for index, character in enumerate(characters)}
    label_id = {label: index for index, label in enumerate(labels)}
    record_rows = [
        bytes([*(glyph_id[character] for character in label), 0xFF])
        for label in labels
    ]
    class_map = bytes(
        0xFF if label is None else label_id[label] for label in class_labels
    )
    name_map = bytes(
        0xFF if label is None else label_id[label] for label in name_labels
    )

    glyph_rows = bytearray()
    glyph_images = {}
    glyph_rows_hex = {}
    for character in characters:
        rows, glyph = asset_builder.load_bdf_cell(
            asset_builder.GALMURI7,
            ord(character),
            cell_width=8,
            cell_height=8,
            ascent=7,
            center_x=True,
        )
        if len(rows) != 8 or rows[-1] != 0:
            raise SystemExit(f"{character}: Galmuri7 eighth row is not blank")
        glyph_rows.extend(rows[:7])
        glyph_images[character] = glyph
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
        "class_labels": class_labels,
        "labels": labels,
        "characters": characters,
        "records": b"".join(record_rows),
        "record_rows": record_rows,
        "class_map": class_map,
        "name_map": name_map,
        "glyph_rows": bytes(glyph_rows),
        "glyph_images": glyph_images,
        "glyph_rows_hex": glyph_rows_hex,
        "lut": bytes(lut),
        "full_class_map": True,
        "full_name_map": True,
        "record_format": "ff-terminated-u8",
        "postdraw_unconditional": True,
    }


asset_builder.build_assets = build_full_assets


if __name__ == "__main__":
    raise SystemExit(base.main())
