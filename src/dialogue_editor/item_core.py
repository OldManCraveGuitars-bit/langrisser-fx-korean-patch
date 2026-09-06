#!/usr/bin/env python3
"""Source-faithful item pools, flush cells, and coupled Resource-12 routing.

The successor208 fixed-slot fallback reintroduced shortened text and missing
final glyphs, confirmed on the user's SRAM with successor219.  Restore the
reviewed full wording and native ordinal pools; update every routing layer
when installing the item atlas extension.  Runtime verification is mandatory.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_r80_source_faithful_items_successor201 as faithful
import resource12_router


def verify_sources() -> None:
    """Pin the reviewed text, geometry catalogue, and native charset."""

    for path, expected in faithful.INPUT_HASHES.items():
        faithful.need(path.is_file(), f"missing item authority: {path}")
        faithful.need(
            faithful.sha_file(path) == expected,
            f"item authority SHA drift: {path}",
        )


def load_inputs() -> tuple[list[dict], list[str], list[str]]:
    return faithful.load_inputs()


def mapping_and_ownership(
    tooltip_lines: list[str], names: list[str]
) -> tuple[dict[str, bytes], dict[str, Any]]:
    return faithful.mapping_and_ownership(tooltip_lines, names)


def geometry() -> dict[int, tuple[int, int]]:
    return faithful.geometry()


def resource12_font_writes(
    source: bytes,
) -> tuple[list[dict], dict[str, Any]]:
    writes, audit = faithful.resource12_font_writes(source)
    font = faithful.resource_font
    old_upper = faithful.CURRENT_RESOURCE12_LAST + 1
    new_upper = 0xF9C7
    router_rows = []
    for replica, tail in enumerate(font.resource12_tails(source)):
        offset = tail + font.ROUTER_OFFSET
        before = source[offset:offset + resource12_router.BYTES]
        resource12_router.verify(before, old_upper)
        after = resource12_router.build(new_upper)
        resource12_router.verify(after, new_upper)
        writes.append({"id": f"resource12/item-router/replica-{replica:02d}",
                       "offset": offset, "expected": before, "replacement": after})
        router_rows.append({"offset": f"0x{offset:X}", "upper_exclusive": f"0x{new_upper:X}"})
    audit.pop("protected_router_sha256", None)
    return writes, {**audit, "coupled_routers": router_rows}


def plan_writes(
    source: bytes,
    names: list[str],
    tooltip_lines: list[str],
    mapping: dict[str, bytes],
    rows: dict[int, tuple[int, int]],
) -> tuple[list[dict], dict[str, Any]]:
    return faithful.plan_writes(source, names, tooltip_lines, mapping, rows)


def validate_writes(source: bytes, writes: list[dict]) -> None:
    faithful.validate_writes(source, writes)
