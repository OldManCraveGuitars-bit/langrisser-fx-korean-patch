#!/usr/bin/env python3
"""Build the R80 collision-free global bottom-HUD 8x8 test disc.

The native field loader already reads resource 12 subentries by the offsets in
its 0x800-byte header.  This builder leaves every existing resource and track
byte at its current address, appends replacement copies of the sixteen field
subentries, and adds one private 0x800-byte tail to each full field subentry.
The tail is therefore loaded at MAIN 0x1E2000 without a new resident loader.

Only the resource-12 offset words and the three frozen R67 HUD hooks are
changed in the existing cooked image.  The short non-field subentry (index 11)
is copied unchanged.  All appended Mode-1 sectors receive fresh MSF, EDC and
ECC data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_bottom_hud_name_class_r67 as asset_builder  # noqa: E402
import build_bottom_hud_name_class_postcompose_r67 as hud  # noqa: E402
import cd_mode1  # noqa: E402


SOURCE_DIR = ROOT / "work/r80-enemy-y-6e8-postscenario-prompt-raw-sync-fix-v2"
SOURCE_COOKED = SOURCE_DIR / "track02-r80-enemy-y-6e8-postscenario-prompt-raw-sync-fix-v2.iso"
SOURCE_RAW = SOURCE_DIR / "Track-2.r80-enemy-y-6e8-postscenario-prompt-raw-sync-fix-v2.bin"
SOURCE_CUE = SOURCE_DIR / "Langrisser-FX-KR-r80-enemy-y-6e8-postscenario-prompt-raw-sync-fix-v2.cue"
SOURCE_TRACK1 = SOURCE_DIR / "Track-1.bin"
SOURCE_TRACK3 = SOURCE_DIR / "Track-3.bin"

SOURCE_COOKED_SHA = "2526EAA95C9062171AEEDA142B23AF1AC79617B1D85571166D85FFD04B6BE1B7"
SOURCE_RAW_SHA = "1DC7238775FF51CD643B61940B36146A7E4EB5187A3D23184C0E01C626847F19"
SOURCE_CUE_SHA = "ACBF8A3A194F52B2D22FDB5E50ED1E42F962CE1F098E43C1AEAF459313231FD3"

NAME = "r80-bottom-hud-8x8-highbank-global-successor"
OUTPUT_DIR = ROOT / "work" / NAME
OUTPUT_COOKED = OUTPUT_DIR / f"track02-{NAME}.iso"
OUTPUT_RAW = OUTPUT_DIR / f"Track-2.{NAME}.bin"
OUTPUT_CUE = OUTPUT_DIR / f"Langrisser-FX-KR-{NAME}.cue"
OUTPUT_REPORT = ROOT / "analysis/r80-bottom-hud-8x8-highbank-global-postbuild.json"

SECTOR = 0x800
RAW_SECTOR = 2352
RAW_LEADIN = 225
RESOURCE12 = 0x1903800
RESOURCE12_OFFSETS = (
    0x000800, 0x011000, 0x021800, 0x032000, 0x042800, 0x053000,
    0x063800, 0x074000, 0x084800, 0x095000, 0x0A5800, 0x0B6000,
    0x0B8000, 0x0C8800, 0x0D9000, 0x0E9800, 0x0FA000,
)
FULL_SUBENTRY = 0x10800
SHORT_INDEX = 11
SHORT_SUBENTRY = 0x2000
TAIL_BYTES = 0x800
HIGH_BASE = 0x1E2000
HIGH_LIMIT = HIGH_BASE + TAIL_BYTES

CLASS_CALL_RAM = hud.CLASS_CALL_RAM
CLASS_CALL_COOKED = hud.CLASS_CALL_COOKED
NAME_CALL_RAM = hud.NAME_CALL_RAM
NAME_CALL_COOKED = hud.NAME_CALL_COOKED
POST_CALL_RAM = hud.POSTDRAW_CALL_RAM
POST_CALL_COOKED = hud.POSTDRAW_CALL_COOKED


class BuildError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_exact(path: Path, offset: int, length: int) -> bytes:
    with path.open("rb") as stream:
        stream.seek(offset)
        data = stream.read(length)
    require(len(data) == length, f"short read: {path.name} @ 0x{offset:X}")
    return data


def align4(value: int) -> int:
    return (value + 3) & ~3


def descriptor(count: int, address: int) -> bytes:
    require(1 <= count <= 255 and 0 <= address < 0x1000000,
            "compact descriptor is out of range")
    return struct.pack("<I", count | (address << 8))


def build_payload(assets: dict[str, object]) -> tuple[bytes, dict[str, object]]:
    glyph_rows = bytes(assets["glyph_rows"])
    glyph0 = glyph_rows[:hud.GLYPH_SPLIT * 7]
    glyph1 = glyph_rows[hud.GLYPH_SPLIT * 7:]
    full_name_map = bool(assets.get("full_name_map", False))
    private_names = (
        bytes(assets["name_map"])
        if full_name_map else
        bytes(
            assets["name_map"][name_id]
            for name_id in sorted(asset_builder.PRIVATE_NAME_IDS)
        )
    )
    class_map = bytes(assets["class_map"])
    records = bytes(assets["records"])
    record_rows = list(assets["record_rows"])

    full_class_map = bool(assets.get("full_class_map", False))
    ff_records = assets.get("record_format") == "ff-terminated-u8"
    require_r28_two = not bool(assets.get("postdraw_unconditional", False))
    clear_native_upper_rows = bool(assets.get("clear_native_upper_rows", False))

    if full_class_map:
        require(len(class_map) == 255, "full class-map denominator drift")
        require(
            len(private_names) == (167 if full_name_map else 73),
            "name-map geometry drift",
        )
        require(ff_records, "full class map requires FF-terminated records")
        require(len(glyph_rows) // 7 <= 255, "unsigned glyph-ID space overflow")
    else:
        require((len(glyph0), len(glyph1)) == (497, 315), "glyph split drift")
        require((len(class_map), len(private_names), len(records), len(record_rows)) ==
                (55, 73, 234, 79), "map/record geometry drift")
    mapped_record_ids = [
        value for value in class_map + private_names
        if not (ff_records and value == 0xFF)
    ]
    require(mapped_record_ids and max(mapped_record_ids) < len(record_rows),
            "record ID overflow")
    if not full_class_map:
        require(sha(glyph_rows) ==
                "FDD41B21C7C33E8B0EDB87E86BD36F0F45DA4D790CFB49C5614F5C0CBE74C5D6",
                "frozen glyph asset drift")
        require(sha(records) ==
                "2535375ABBBF2C6944B2B2E290A9E4E925927E9EE8C53DD6FC8757785F95CCA7",
                "frozen record asset drift")

    layout: dict[str, tuple[int, int]] = {}
    cursor = HIGH_BASE

    upload_ram = cursor
    upload_builder = (
        hud.build_upload_helper_u8_ff if ff_records
        else hud.build_upload_helper_compact
    )
    upload = upload_builder(upload_ram, hud.GLYPH_SPLIT)
    layout["glyph_uploader"] = (upload_ram, len(upload))
    cursor += len(upload)

    cursor = align4(cursor)
    lut_ram = cursor
    lut = bytes(assets["lut"])
    layout["private_4bpp_lut"] = (lut_ram, len(lut))
    cursor += len(lut)

    cursor = align4(cursor)
    scratch_ram = cursor
    layout["captured_ids"] = (scratch_ram, 8)
    cursor += 8

    # The frozen assembler resolves SCRATCH_RAM when the two routines are built.
    hud.SCRATCH_RAM = scratch_ram
    cursor = align4(cursor)
    capture_ram = cursor
    capture, capture_symbols = hud.build_capture_handler(capture_ram)
    layout["id_capture_handler"] = (capture_ram, len(capture))
    cursor += len(capture)

    cursor = align4(cursor)
    post_ram = cursor
    placeholder, _ = hud.build_post_handler(
        post_ram, HIGH_BASE, HIGH_BASE, HIGH_BASE, upload_ram,
        HIGH_BASE, HIGH_BASE, lut_ram,
        full_class_map=full_class_map, full_name_map=full_name_map,
        ff_records=ff_records,
        require_r28_two=require_r28_two,
        clear_native_upper_rows=clear_native_upper_rows,
    )
    layout["post_compose_handler"] = (post_ram, len(placeholder))
    cursor += len(placeholder)

    cursor = align4(cursor)
    class_desc_ram = cursor
    cursor += 4
    name_desc_ram = cursor
    cursor += 4
    record_desc_ram = cursor
    cursor += 4
    layout["compact_descriptors"] = (class_desc_ram, 12)

    class_map_ram = cursor
    layout["class_map"] = (class_map_ram, len(class_map))
    cursor += len(class_map)
    name_map_ram = cursor
    layout["name_map"] = (name_map_ram, len(private_names))
    cursor += len(private_names)
    record_ram = cursor
    layout["label_records"] = (record_ram, len(records))
    cursor += len(records)

    cursor = align4(cursor)
    glyph0_ram = cursor
    layout["glyph_bank_0"] = (glyph0_ram, len(glyph0))
    cursor += len(glyph0)
    glyph1_ram = cursor
    layout["glyph_bank_1"] = (glyph1_ram, len(glyph1))
    cursor += len(glyph1)

    require(cursor <= HIGH_LIMIT, f"payload overflow: 0x{cursor:X} > 0x{HIGH_LIMIT:X}")
    post, post_symbols = hud.build_post_handler(
        post_ram, class_desc_ram, name_desc_ram, record_desc_ram, upload_ram,
        glyph0_ram, glyph1_ram, lut_ram,
        full_class_map=full_class_map, full_name_map=full_name_map,
        ff_records=ff_records,
        require_r28_two=require_r28_two,
        clear_native_upper_rows=clear_native_upper_rows,
    )
    require(len(post) == len(placeholder) and len(post) <= 0x1D0,
            f"post handler size drift: placeholder={len(placeholder)} post={len(post)}")
    require(len(capture) == 86, "capture helper size drift")
    if not ff_records:
        require(len(upload) == 120, "legacy upload helper size drift")

    payload = bytearray(TAIL_BYTES)

    def put(address: int, data: bytes) -> None:
        first = address - HIGH_BASE
        last = first + len(data)
        require(0 <= first <= last <= len(payload), "payload placement overflow")
        require(not any(payload[first:last]), f"payload overlap at 0x{address:X}")
        payload[first:last] = data

    put(upload_ram, upload)
    put(lut_ram, lut)
    put(scratch_ram, b"\xFF" * 8)
    put(capture_ram, capture)
    put(post_ram, post)
    put(class_desc_ram, descriptor(len(class_map), class_map_ram))
    put(name_desc_ram, descriptor(len(private_names), name_map_ram))
    put(record_desc_ram, descriptor(len(record_rows), record_ram))
    put(class_map_ram, class_map)
    put(name_map_ram, private_names)
    put(record_ram, records)
    put(glyph0_ram, glyph0)
    put(glyph1_ram, glyph1)

    validations = {
        "upload": hud.validate_instruction_stream(upload, upload_ram),
        "capture": hud.validate_instruction_stream(capture, capture_ram),
        "post": hud.validate_instruction_stream(post, post_ram),
    }
    report_layout = {
        key: {"ram": f"0x{address:X}", "bytes": length}
        for key, (address, length) in layout.items()
    }
    return bytes(payload), {
        "layout": report_layout,
        "used_bytes": cursor - HIGH_BASE,
        "slack_bytes": HIGH_LIMIT - cursor,
        "sha256": sha(bytes(payload)),
        "symbols": {
            "class_entry": f"0x{capture_symbols['class_entry']:X}",
            "name_entry": f"0x{capture_symbols['name_entry']:X}",
            "post_entry": f"0x{post_symbols['post_entry']:X}",
        },
        "symbol_values": {
            "class_entry": capture_symbols["class_entry"],
            "name_entry": capture_symbols["name_entry"],
            "post_entry": post_symbols["post_entry"],
        },
        "code_validation": validations,
    }


def bcd(value: int) -> int:
    require(0 <= value <= 99, "BCD component overflow")
    return ((value // 10) << 4) | (value % 10)


def bcd_value(value: int) -> int:
    return (value >> 4) * 10 + (value & 0x0F)


def msf_bytes(frame: int) -> bytes:
    minute, remainder = divmod(frame, 60 * 75)
    second, sector = divmod(remainder, 75)
    return bytes((bcd(minute), bcd(second), bcd(sector)))


def write_cue(path: Path) -> None:
    text = (
        "CATALOG 0000000000000\r\n"
        "FILE \"Track-1.bin\" BINARY\r\n"
        "  TRACK 01 AUDIO\r\n"
        "    INDEX 01 00:00:00\r\n"
        f"FILE \"{OUTPUT_RAW.name}\" BINARY\r\n"
        "  TRACK 02 MODE1/2352\r\n"
        "    INDEX 00 00:00:00\r\n"
        "    INDEX 01 00:03:00\r\n"
        "FILE \"Track-3.bin\" BINARY\r\n"
        "  TRACK 03 AUDIO\r\n"
        "    INDEX 00 00:00:00\r\n"
        "    INDEX 01 00:02:00\r\n"
    )
    path.write_text(text, encoding="ascii", newline="")


def source_contract() -> None:
    for path in (SOURCE_COOKED, SOURCE_RAW, SOURCE_CUE, SOURCE_TRACK1, SOURCE_TRACK3):
        require(path.is_file(), f"missing source: {path}")
    require(sha_file(SOURCE_COOKED) == SOURCE_COOKED_SHA, "source cooked SHA drift")
    require(sha_file(SOURCE_RAW) == SOURCE_RAW_SHA, "source raw SHA drift")
    require(sha_file(SOURCE_CUE) == SOURCE_CUE_SHA, "source CUE SHA drift")
    require(SOURCE_COOKED.stat().st_size % SECTOR == 0, "cooked alignment drift")
    require(SOURCE_RAW.stat().st_size % RAW_SECTOR == 0, "raw alignment drift")
    require(SOURCE_RAW.stat().st_size // RAW_SECTOR ==
            SOURCE_COOKED.stat().st_size // SECTOR + RAW_LEADIN,
            "raw/cooked geometry drift")
    header = read_exact(SOURCE_COOKED, RESOURCE12, 0x80)
    actual = struct.unpack_from("<17I", header)
    require(actual == RESOURCE12_OFFSETS, "resource-12 offset table drift")
    lengths = tuple(b - a for a, b in zip(actual, actual[1:]))
    require(lengths.count(FULL_SUBENTRY) == 15, "full field-subentry count drift")
    require(lengths[SHORT_INDEX] == SHORT_SUBENTRY, "short subentry drift")


def create_cooked(payload: bytes, symbols: dict[str, int]) -> dict[str, object]:
    shutil.copyfile(SOURCE_COOKED, OUTPUT_COOKED)
    source_size = SOURCE_COOKED.stat().st_size
    new_offsets: list[int] = []
    copied_lengths: list[int] = []
    with SOURCE_COOKED.open("rb") as source, OUTPUT_COOKED.open("r+b") as output:
        output.seek(0, os.SEEK_END)
        cursor = source_size - RESOURCE12
        for index, (first, last) in enumerate(zip(RESOURCE12_OFFSETS, RESOURCE12_OFFSETS[1:])):
            length = last - first
            new_offsets.append(cursor)
            source.seek(RESOURCE12 + first)
            remaining = length
            while remaining:
                block = source.read(min(1 << 20, remaining))
                require(block, f"short resource-12 subentry {index}")
                output.write(block)
                remaining -= len(block)
            cursor += length
            copied_lengths.append(length)
            if length == FULL_SUBENTRY:
                output.write(payload)
                cursor += len(payload)
            else:
                require(index == SHORT_INDEX and length == SHORT_SUBENTRY,
                        f"unexpected short subentry {index}")
        new_offsets.append(cursor)
        expected_collection = sum(copied_lengths) + 15 * len(payload)
        require(cursor - (source_size - RESOURCE12) == expected_collection,
                "appended resource collection size drift")

        output.seek(RESOURCE12)
        output.write(struct.pack("<17I", *new_offsets))

        expected_class = hud.encode_jal(CLASS_CALL_RAM, hud.NATIVE_DECODER_RAM)
        expected_name = hud.encode_jal(NAME_CALL_RAM, hud.NATIVE_DECODER_RAM)
        hooks = (
            (CLASS_CALL_COOKED, expected_class,
             hud.encode_jal(CLASS_CALL_RAM, symbols["class_entry"]), "class_capture"),
            (NAME_CALL_COOKED, expected_name,
             hud.encode_jal(NAME_CALL_RAM, symbols["name_entry"]), "name_capture"),
            (POST_CALL_COOKED, hud.POSTDRAW_EXPECTED,
             hud.encode_jal(POST_CALL_RAM, symbols["post_entry"]), "post_compose"),
        )
        hook_rows = []
        for offset, expected, replacement, name in hooks:
            require(read_exact(SOURCE_COOKED, offset, 4) == expected,
                    f"{name} native preimage drift")
            output.seek(offset)
            output.write(replacement)
            hook_rows.append({
                "name": name, "cooked": f"0x{offset:X}",
                "expected": expected.hex().upper(),
                "replacement": replacement.hex().upper(),
            })
        output.flush()
        os.fsync(output.fileno())

    expected_size = source_size + sum(copied_lengths) + 15 * len(payload)
    require(OUTPUT_COOKED.stat().st_size == expected_size, "output cooked size drift")
    require(struct.unpack("<17I", read_exact(OUTPUT_COOKED, RESOURCE12, 68)) ==
            tuple(new_offsets), "patched resource-12 offsets drift")
    return {
        "source_bytes": source_size,
        "output_bytes": expected_size,
        "appended_bytes": expected_size - source_size,
        "old_offsets": [f"0x{x:X}" for x in RESOURCE12_OFFSETS],
        "new_offsets": [f"0x{x:X}" for x in new_offsets],
        "subentry_lengths": [f"0x{x:X}" for x in copied_lengths],
        "hooks": hook_rows,
    }


def repair_existing_raw_sector(raw, cooked_sector: int) -> None:
    raw_sector = RAW_LEADIN + cooked_sector
    raw.seek(raw_sector * RAW_SECTOR)
    sector = bytearray(raw.read(RAW_SECTOR))
    require(len(sector) == RAW_SECTOR and sector[15] == 1,
            f"invalid source raw sector {raw_sector}")
    sector[16:16 + SECTOR] = read_exact(OUTPUT_COOKED, cooked_sector * SECTOR, SECTOR)
    cd_mode1.repair_mode1_sector(sector)
    require(cd_mode1.verify_mode1_sector(bytes(sector)),
            f"repaired raw sector invalid: {raw_sector}")
    raw.seek(raw_sector * RAW_SECTOR)
    raw.write(sector)


def create_raw() -> dict[str, object]:
    shutil.copyfile(SOURCE_RAW, OUTPUT_RAW)
    changed_existing = sorted({
        RESOURCE12 // SECTOR,
        CLASS_CALL_COOKED // SECTOR,
        NAME_CALL_COOKED // SECTOR,
        POST_CALL_COOKED // SECTOR,
    })
    source_raw_sectors = SOURCE_RAW.stat().st_size // RAW_SECTOR
    source_cooked_sectors = SOURCE_COOKED.stat().st_size // SECTOR
    output_cooked_sectors = OUTPUT_COOKED.stat().st_size // SECTOR
    appended_sectors = output_cooked_sectors - source_cooked_sectors

    with OUTPUT_RAW.open("r+b") as raw:
        for cooked_sector in changed_existing:
            repair_existing_raw_sector(raw, cooked_sector)

        raw.seek((source_raw_sectors - 1) * RAW_SECTOR)
        template = bytearray(raw.read(RAW_SECTOR))
        require(len(template) == RAW_SECTOR and cd_mode1.verify_mode1_sector(bytes(template)),
                "last source Mode-1 sector drift")
        minute, second, frame = (bcd_value(value) for value in template[12:15])
        absolute_frame = (minute * 60 + second) * 75 + frame

        raw.seek(0, os.SEEK_END)
        with OUTPUT_COOKED.open("rb") as cooked:
            cooked.seek(source_cooked_sectors * SECTOR)
            for index in range(appended_sectors):
                user = cooked.read(SECTOR)
                require(len(user) == SECTOR, f"short appended cooked sector {index}")
                sector = bytearray(template)
                sector[12:15] = msf_bytes(absolute_frame + index + 1)
                sector[15] = 1
                sector[16:16 + SECTOR] = user
                cd_mode1.repair_mode1_sector(sector)
                require(cd_mode1.verify_mode1_sector(bytes(sector)),
                        f"appended Mode-1 sector invalid: {index}")
                raw.write(sector)
        raw.flush()
        os.fsync(raw.fileno())

    require(OUTPUT_RAW.stat().st_size // RAW_SECTOR ==
            output_cooked_sectors + RAW_LEADIN, "output raw geometry drift")
    # Verify every rebuilt or appended sector against the cooked user bytes.
    verify_sectors = changed_existing + list(range(source_cooked_sectors, output_cooked_sectors))
    with OUTPUT_RAW.open("rb") as raw, OUTPUT_COOKED.open("rb") as cooked:
        for cooked_sector in verify_sectors:
            raw.seek((RAW_LEADIN + cooked_sector) * RAW_SECTOR)
            sector = raw.read(RAW_SECTOR)
            cooked.seek(cooked_sector * SECTOR)
            user = cooked.read(SECTOR)
            require(cd_mode1.verify_mode1_sector(sector),
                    f"postbuild Mode-1 verification failed: {cooked_sector}")
            require(sector[16:16 + SECTOR] == user,
                    f"postbuild raw/cooked mismatch: {cooked_sector}")
    return {
        "raw_leadin_sectors": RAW_LEADIN,
        "changed_existing_cooked_sectors": changed_existing,
        "appended_cooked_sectors": appended_sectors,
        "verified_mode1_sectors": len(verify_sectors),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--materialize", action="store_true")
    args = parser.parse_args()

    source_contract()
    # build_assets decodes only the frozen native name table but currently
    # accepts a byte image.  Release the large image immediately afterwards.
    source_image = SOURCE_COOKED.read_bytes()
    assets = asset_builder.build_assets(source_image)
    del source_image
    payload, payload_report = build_payload(assets)

    dry = {
        "status": "GREEN_STATIC_READY_TO_MATERIALIZE",
        "source_cooked_sha256": SOURCE_COOKED_SHA,
        "source_raw_sha256": SOURCE_RAW_SHA,
        "payload": payload_report,
        "resource12": {
            "header_cooked": f"0x{RESOURCE12:X}",
            "full_subentries": 15,
            "short_subentry_index": SHORT_INDEX,
            "tail_load_ram": [f"0x{HIGH_BASE:X}", f"0x{HIGH_LIMIT:X}"],
            "existing_resources_shifted": False,
        },
    }
    if not args.materialize:
        print(json.dumps(dry, ensure_ascii=False, indent=2))
        return 0

    require(not OUTPUT_DIR.exists(), f"output already exists: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True)
    try:
        cooked_report = create_cooked(payload, payload_report["symbol_values"])
        raw_report = create_raw()
        shutil.copyfile(SOURCE_TRACK1, OUTPUT_DIR / "Track-1.bin")
        shutil.copyfile(SOURCE_TRACK3, OUTPUT_DIR / "Track-3.bin")
        write_cue(OUTPUT_CUE)
        report = {
            **dry,
            "status": "GREEN_POSTBUILD_STATIC_MODE1_RUNTIME_VISUAL_PENDING",
            "output": {
                "directory": str(OUTPUT_DIR.relative_to(ROOT)).replace("\\", "/"),
                "cooked": OUTPUT_COOKED.name,
                "raw": OUTPUT_RAW.name,
                "cue": OUTPUT_CUE.name,
                "cooked_sha256": sha_file(OUTPUT_COOKED),
                "raw_sha256": sha_file(OUTPUT_RAW),
                "cue_sha256": sha_file(OUTPUT_CUE),
                "track1_sha256": sha_file(OUTPUT_DIR / "Track-1.bin"),
                "track3_sha256": sha_file(OUTPUT_DIR / "Track-3.bin"),
            },
            "cooked_projection": cooked_report,
            "raw_projection": raw_report,
            "regression_contract": {
                "existing_resource_addresses_shifted": False,
                "existing_cooked_bytes_changed_only_in": [
                    "resource-12 17-word subentry offset table",
                    "bottom-HUD native class/name capture hooks",
                    "bottom-HUD native post-compose hook",
                ],
                "english_and_number_glyph_assets_changed": False,
                "normal_menu_resources_changed": False,
                "runtime_visual_verification_pending": True,
            },
        }
        OUTPUT_REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (OUTPUT_DIR / "BUILD-README.txt").write_text(
            "하단 UI 이름/클래스 8x8 전용 테스트 빌드\n"
            "기준: r80 enemy-y + postscenario prompt raw-sync-fix-v2\n"
            "기존 메뉴/영문/숫자/전투 리소스는 이동하지 않음\n"
            "테스트: 필드에서 아군/적 지휘관과 용병을 차례로 선택해 하단 이름과 클래스 확인\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        # A failed materialization is not a candidate.  Keep cleanup scoped to
        # the newly created, exact output directory only.
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
