"""Restore the complete lower-HUD commander class map.

The old broad mercenary fallback blanked class IDs 102..119.  A later sparse
unit-ID override now handles the mercenary exceptions before normal class
selection, so the complete commander map can and must be restored.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_bottom_hud_name_class_r67 as names  # noqa: E402
import build_r80_bottom_hud_8x8_full_classes_units as full  # noqa: E402


RESOURCE12 = 0x1903800
FULL_LENGTH = 0x18800
PRIVATE = 0x10800
CLASS_MAP = 0x2A4
CLASS_COUNT = 255
GAP_FIRST = 102
GAP_LAST = 120
BEFORE = bytes([0xFF]) * (GAP_LAST - GAP_FIRST)
AFTER = bytes.fromhex("3E3E3E3E3F40414242434343434415454546")
CHARSET = ROOT / "analysis/hangul_charset_v342-r57-safe-table-font-repair.json"


def need(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def resource_starts(image: bytes) -> tuple[int, ...]:
    offsets = struct.unpack_from("<17I", image, RESOURCE12)
    lengths = tuple(right - left for left, right in zip(offsets, offsets[1:]))
    need(lengths.count(FULL_LENGTH) == 15 and lengths.count(0x2000) == 1,
         "Resource-12 field population")
    return tuple(RESOURCE12 + offset for offset, length in zip(offsets, lengths)
                 if length == FULL_LENGTH)


def expected_class_map(image: bytes) -> tuple[bytes, list[str | None]]:
    charset = json.loads(CHARSET.read_text(encoding="utf-8"))
    code_to_character = {
        int(row["code"], 0): str(row["character"])
        for row in charset["mappings"]
    }
    labels: list[str | None] = []
    for class_id in range(CLASS_COUNT):
        source = full.decode_class_text(image, class_id, code_to_character).strip()
        labels.append(source.replace(" ", "") if source else None)
    native_names = names.decode_name_table(image)
    unknown = sorted(set(native_names) - set(names.NAME_TRANSLATIONS) - {""})
    need(not unknown, f"untranslated native names: {unknown}")
    name_labels = [names.NAME_TRANSLATIONS.get(value) if value else None
                   for value in native_names]
    records = list(dict.fromkeys(label for label in [*labels, *name_labels] if label))
    need(len(records) == 197, "existing HUD record denominator")
    record_id = {label: index for index, label in enumerate(records)}
    result = bytes(0xFF if label is None else record_id[label] for label in labels)
    need(result[GAP_FIRST:GAP_LAST] == AFTER, "derived commander gap bytes")
    return result, labels


def plan(image: bytes) -> tuple[list[tuple[int, bytes, bytes, str]], dict[str, object]]:
    expected, labels = expected_class_map(image)
    writes = []
    for replica, start in enumerate(resource_starts(image)):
        map_offset = start + PRIVATE + CLASS_MAP
        current = image[map_offset:map_offset + CLASS_COUNT]
        mismatches = [index for index, (left, right) in enumerate(zip(current, expected))
                      if left != right]
        need(mismatches == list(range(GAP_FIRST, GAP_LAST)),
             f"Resource-12 replica {replica}: unexpected class-map differences {mismatches}")
        offset = map_offset + GAP_FIRST
        need(image[offset:offset + len(BEFORE)] == BEFORE,
             f"Resource-12 replica {replica}: class gap preimage")
        writes.append((offset, BEFORE, AFTER,
                       f"bottom-hud/class-map-completion/replica/{replica:02d}"))
    need(len(writes) == 15, "Resource-12 full-copy denominator")
    return writes, {
        "restored_ids": [
            {"class_id": class_id, "label": labels[class_id], "record_id": expected[class_id]}
            for class_id in range(GAP_FIRST, GAP_LAST)
        ],
        "morgan": {"unit_class_id": 116, "label": labels[116], "record_id": expected[116]},
    }


def verify(image: bytes) -> dict[str, object]:
    expected, labels = expected_class_map(image)
    for replica, start in enumerate(resource_starts(image)):
        actual = image[start + PRIVATE + CLASS_MAP:start + PRIVATE + CLASS_MAP + CLASS_COUNT]
        need(actual == expected, f"Resource-12 replica {replica}: incomplete class map")
    need(labels[116] == "소서러" and expected[116] == 21, "Morgan class mapping")
    return {
        "active_resource12_copies": 15,
        "class_ids_checked": CLASS_COUNT,
        "class_ids_mapped": sum(value != 0xFF for value in expected),
        "morgan_class_id": 116,
        "morgan_rendered_class": "소서러",
        "sparse_mercenary_override_precedence_preserved": True,
    }

