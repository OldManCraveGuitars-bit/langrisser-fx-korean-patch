"""Build successor263 from the pinned, accepted successor260 product.

The write plan owns only the 105 local insufficient-funds routes and the
eighteen previously blank class-map entries in all 15 active Resource-12
copies.  Every other successor260 byte is an exact protected complement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_successor257_event_rewards_menu_tiles as raw_tools  # noqa: E402
import hud_commander_class_restore as hud  # noqa: E402
import shop_insufficient_funds_global as shop  # noqa: E402


SOURCE_STEM = "r80-successor259-archer-category-global-successor260"
STEM = "r80-successor260-shop-hud-global-successor263"
SOURCE = ROOT / "work" / SOURCE_STEM
OUT = ROOT / "work" / STEM
SOURCE_FILES = {
    "cooked": f"track02-{SOURCE_STEM}.iso",
    "raw": f"Track-2.{SOURCE_STEM}.bin",
    "cue": f"Langrisser-FX-KR-{SOURCE_STEM}.cue",
    "track1": "Track-1.bin",
    "track3": "Track-3.bin",
    "subtitles": "subtitle-payload.bin",
    "readme": "README-KO.txt",
}
SOURCE_SHA256 = {
    "cooked": "399884524353466312CD9A3724337D46CB170C8B9CF5AB68A351B8133491A309",
    "raw": "7FAD166C7D5655BED40E1080CB5DF5D772BDD954EFAA9E93112DBF8AB43D1501",
    "cue": "34B85F17761F8C86EAA2873C5FA120BFE5686FDA8538781C141C95E41FB80E4C",
    "track1": "1E1840205CE98F5E0DF8067BEA8B3336DB62CA071C7B67538A0312C267D9CFA9",
    "track3": "9D1133A7DDAB061567F6C83F3342C90CBE32DC6A94561AE5309FA74335FDDD8D",
    "subtitles": "55DEC2772391FBBEE4A63F94813AA34BCE8F6534897BECFCD9B07096C5548D41",
    "readme": "B6725BCB030FA717CD797A6684A55DAE81FF757687793F9551767AEBE9245D27",
}


def need(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def file_sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def diff_bytes(left: bytes, right: bytes) -> set[int]:
    need(len(left) == len(right), "cooked image size changed")
    result: set[int] = set()
    block = 1 << 20
    for base in range(0, len(left), block):
        before = left[base:base + block]
        after = right[base:base + block]
        if before != after:
            result.update(base + index for index, (a, b) in enumerate(zip(before, after)) if a != b)
    return result


def compose(source: bytes):
    shop_writes, shop_rows = shop.plan(source)
    hud_writes, hud_rows = hud.plan(source)
    writes = sorted([*shop_writes, *hud_writes])
    for left, right in zip(writes, writes[1:]):
        need(left[0] + len(left[1]) <= right[0],
             f"overlapping writers: {left[3]} / {right[3]}")

    image = bytearray(source)
    expected: set[int] = set()
    for offset, before, after, owner in writes:
        need(len(before) == len(after), f"{owner}: fixed extent")
        need(source[offset:offset + len(before)] == before, f"{owner}: immutable preimage")
        image[offset:offset + len(before)] = after
        expected.update(offset + index for index, (a, b) in enumerate(zip(before, after)) if a != b)
    result = bytes(image)
    need(diff_bytes(source, result) == expected, "full cooked diff differs from write plan")
    shop_verify = shop.verify(result)
    hud_verify = hud.verify(result)
    return result, writes, expected, shop_rows, hud_rows, shop_verify, hud_verify


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    need(not args.out.exists(), "immutable successor263 output already exists")
    paths = {role: args.source / name for role, name in SOURCE_FILES.items()}
    for role, path in paths.items():
        need(path.is_file() and file_sha(path) == SOURCE_SHA256[role],
             f"successor260 {role} identity")

    source = paths["cooked"].read_bytes()
    image, writes, changed, shop_rows, hud_rows, shop_verify, hud_verify = compose(source)
    args.out.mkdir(parents=True)
    cooked = args.out / f"track02-{STEM}.iso"
    raw = args.out / f"Track-2.{STEM}.bin"
    cue = args.out / f"Langrisser-FX-KR-{STEM}.cue"
    cooked.write_bytes(image)
    sectors = sorted({offset // 2048 for offset in changed})
    raw_audit = raw_tools.dialogue._repair_raw(cooked, paths["raw"], raw, sectors)

    for role in ("track1", "track3", "subtitles", "readme"):
        target = args.out / paths[role].name
        shutil.copyfile(paths[role], target)
        need(file_sha(target) == SOURCE_SHA256[role], f"protected {role}")
    cue.write_text(
        paths["cue"].read_text(encoding="ascii").replace(paths["raw"].name, raw.name),
        encoding="ascii",
        newline="",
    )

    report = {
        "schema": "langrisser-fx-successor263-shop-hud-build/v1",
        "status": "STATIC_PASS_RUNTIME_REQUIRED",
        "stem": STEM,
        "source_stem": SOURCE_STEM,
        "source": SOURCE_SHA256,
        "source_changed_bytes": len(changed),
        "changed_cooked_sectors": sectors,
        "write_owners": len(writes),
        "shop": shop_verify | {"replicas": shop_rows},
        "bottom_hud": hud_verify | hud_rows,
        "protected": {
            "all_other_cooked_bytes_identical_to_successor260": True,
            "subtitle_payload_identical": True,
            "movie_tracks_identical": True,
            "item_names_and_tooltips_other_than_insufficient_funds_identical": True,
            "unit_classes_and_combat_parameters_identical": True,
            "sparse_mercenary_category_override_code_and_map_identical": True,
        },
        "raw_audit": raw_audit,
        "writes": [
            {"offset": f"0x{offset:08X}", "bytes": len(before), "owner": owner,
             "before_hex": before.hex().upper(), "after_hex": after.hex().upper()}
            for offset, before, after, owner in writes
        ],
        "outputs": {
            role: {"path": path.name, "sha256": file_sha(path)}
            for role, path in (("cue", cue), ("cooked", cooked), ("raw", raw))
        },
    }
    (args.out / "successor263-build-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": report["status"],
        "cue": str(cue),
        "changed_bytes": len(changed),
        "write_owners": len(writes),
    }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
