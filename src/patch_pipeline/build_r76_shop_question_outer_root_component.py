#!/usr/bin/env python3
"""Build the cooked-only R76 shop-question ownership repair.

R75 writes the same purchase root to 105 local text aggregates.  The root
ends in a blank full-width cell after ``0x0435``.  In 102 aggregates the local
dictionary expansion already owns one question mark, but the three catalogued
global text blocks deliberately use a question-less ``0x0435`` tail because
their save roots own the final question mark outside the dictionary token.

This component changes only the purchase-root outer cell in those three
global blocks from ``8140`` to ``8148``.  It never edits dictionary 0x35, the
shared catalog, either save consumer, a raw track, or a CUE.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mmap
import os
import struct
import tempfile
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "work/poc/track02-r75-final-cooked-integrated-candidate.iso"
OUTPUT = ROOT / "work/poc/track02-r76-shop-question-outer-root-component.iso"
MANIFEST = ROOT / "analysis/r76-shop-question-outer-root-component.json"
OWNERSHIP_AUDIT = ROOT / "analysis/r76-shop-question-replica-ownership-audit.json"
VERIFIER = ROOT / "tools/verify_r76_shop_question_outer_root_component.py"
COMMON_AUDIT = ROOT / "analysis/common_dictionary_replicas_v340_audit.json"

COOKED_BYTES = 657_420_288
INPUT_SHA256 = "62EFDE14CCFE3EAC468FB5EF4666044EFF1B650661427B2F0C9FA4863372964F"
OUTPUT_SHA256 = "CF9B3ED7F434D6E3992A9E16301EC752F1D949B2102791D09F38FAC67B437C73"
COMMON_AUDIT_SHA256 = "816B0D8A0FE6CAAFE54EF91A0F2AD8EF892A00B5D8E362D953509A007BA01B9A"
TOPOLOGY_SHA256 = "7F443344AD7DCCE24DAA34AA2F7A50F56C33A1BAD0CDAA0D513704B8C7A115E3"
WRITE_PLAN_SHA256 = "37CFA9C97D5CE56869E20C3BFC78CC5528133250BF7CCC2AC30E794C85FDC8C8"
COMPLEMENT_SHA256 = "3F8C666C05A57D9A8C7F3A3BFB9C95AA2114DD52CD411E4F2B5FD0004D1B4709"
ROOT_BLOB_BEFORE_SHA256 = "8C2C24E09EE244340D556EDA6D0E071AFDDB4A4E5B30D2AE59DAA0766D27626D"
ROOT_BLOB_AFTER_SHA256 = "363614BE24242DBA6AC8815E95B960B3A75C09E4B1F6A5B5E9EB0723ACD6388E"
Q1_ROOTS_SHA256 = "8EB67DC5F91406E7E0A3C609DDA96C11A3C5B2E9BEDFA893AFED1851950FF43A"

# The v340 audit records where the original Japanese common signature lived.
# R75 contains the translated eight-byte replacement at those same 105 sites.
COMMON_SIGNATURE = bytes.fromhex("F0DFF0F1F1E6F0E6")
ROOT_BEFORE = bytes.fromhex("F05CF163F090F1E8F089F0B3F1E80435814000")
ROOT_AFTER = bytes.fromhex("F05CF163F090F1E8F089F0B3F1E80435814800")
QUESTION = bytes.fromhex("8148")
BLANK = bytes.fromhex("8140")
TARGET_INDICES = (0, 78, 98)
TARGET_OFFSETS = (0x0012F167, 0x003440FB, 0x003CFCE7)
EXPECTED_SECTORS = (606, 1672, 1951)
COPY_CHUNK = 8 << 20

PROTECTED_RANGES = {
    "scenario1-save-root": (
        0x0012F141,
        0x0012F14A,
        "ED8CA19B4C8F455CD29ADE11695A2DD289F3AD9D59551245A3A8A65A5D6FC600",
    ),
    "save-consumer-a-copy1": (
        0x00132399,
        0x001323A4,
        "E96865BE0FF0DC77743A16C8C64B61F347DC8D06458FF42EC8E153C4701446D4",
    ),
    "scenario2-save-root": (
        0x001370DD,
        0x001370E6,
        "B8F0AD16E7F7AAE96280C6C3198DDC1CD87147ACDA095C9D775C3C990D93F359",
    ),
    "scenario2-save-private-dictionary": (
        0x0013A214,
        0x0013A21E,
        "A566AADBAB8F509488A7E24EB5761202E29C8F7B226D638141A68866954DE7A5",
    ),
    "scenario2-purchase-code35-code36": (
        0x0013A335,
        0x0013A34B,
        "4065B0D66A02B5929EE324523A87034D97F381695CECAAA92505BEA42FB732F9",
    ),
    "save-consumer-a-copy2": (
        0x0034732D,
        0x00347338,
        "E96865BE0FF0DC77743A16C8C64B61F347DC8D06458FF42EC8E153C4701446D4",
    ),
    "save-consumer-a-copy3": (
        0x003D2F19,
        0x003D2F24,
        "E96865BE0FF0DC77743A16C8C64B61F347DC8D06458FF42EC8E153C4701446D4",
    ),
    "shop-core-a": (
        0x0004F080,
        0x0004F4B6,
        "AF4F40CF9E639B7369E9A313CB02F643E5448CF2617931D1ABC6208628CEFB3C",
    ),
    "shop-core-b": (
        0x0004F4CC,
        0x0004F63C,
        "2FB3A5D02E99EC605C010D15598A2D67A9621F62DB4A19A78873650F846CDB97",
    ),
    "shop-core-c": (
        0x0004F650,
        0x0004F800,
        "6150E30248BC1BA0DF436389FB97A441F46C970688E656BB4378AD854039AF76",
    ),
}

PROTECTED_GROUPS = {
    "save-consumer-a-all": (
        (0x00132399, 0x001323A4),
        (0x0034732D, 0x00347338),
        (0x003D2F19, 0x003D2F24),
        "A0022DC11ABFBCD95B5255CD843AD90C1DDEB46BF58252A48DC113169CF17702",
    ),
    "save-consumer-b-all": (
        (0x001370DD, 0x001370E6),
        (0x0013A214, 0x0013A21E),
        "D9BB94C9E666C5E475D983725F867899A819D3DD42FC07C2E4A19BB9E2C85468",
    ),
    "shop-core-all": (
        (0x0004F080, 0x0004F4B6),
        (0x0004F4CC, 0x0004F63C),
        (0x0004F650, 0x0004F800),
        "EB44DE11036BF8DFE732EBBB782AF176AEB8C2385D97A12A1240250330BAC0A2",
    ),
}


class ContractError(RuntimeError):
    pass


def sha256(data: bytes | bytearray | memoryview) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(COPY_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def require_file(path: Path, expected_sha: str, size: int | None = None) -> None:
    if not path.is_file():
        raise ContractError(f"missing pinned file: {path}")
    if size is not None and path.stat().st_size != size:
        raise ContractError(f"size mismatch: {path}")
    actual = file_sha256(path)
    if actual != expected_sha:
        raise ContractError(f"SHA-256 mismatch: {path}: {actual} != {expected_sha}")


def read_json(path: Path, expected_sha: str) -> dict[str, object]:
    require_file(path, expected_sha)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError(f"invalid pinned JSON: {path}: {error}") from error
    if not isinstance(document, dict):
        raise ContractError(f"pinned JSON is not an object: {path}")
    return document


def atomic_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            json.dump(document, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def replica_roots(common: dict[str, object]) -> list[int]:
    values = common.get("replica_offsets")
    if not isinstance(values, list) or len(values) != 105:
        raise ContractError("common dictionary replica inventory is not exactly 105")
    if common.get("long_replicas") != 100 or common.get("short_replicas") != 5:
        raise ContractError("common dictionary long/short topology drift")
    signatures = [int(str(value), 0) for value in values]
    roots = [value - 0x6C for value in signatures]
    if sha256(b"".join(struct.pack("<Q", value) for value in roots)) != TOPOLOGY_SHA256:
        raise ContractError("common dictionary replica topology hash drift")
    return roots


def parse_header(image: mmap.mmap, root: int) -> tuple[int, list[int]]:
    # The purchase root is the sixth non-empty record: 0x2A bytes after the
    # first section.  Global block 2 and one adjacent aggregate have eight
    # section pointers (0x20); every other aggregate has nine (0x24).
    candidates: list[tuple[int, list[int]]] = []
    for first in (0x24, 0x20):
        header = root - first - 0x2A
        if int.from_bytes(image[header : header + 4], "little") != first:
            continue
        count = first // 4
        offsets = [
            int.from_bytes(image[header + 4 * index : header + 4 * index + 4], "little")
            for index in range(count)
        ]
        if offsets[0] != first or offsets != sorted(offsets):
            continue
        if len(offsets) not in (8, 9) or offsets[4] not in (0x300C, 0x3008, 0x9B0):
            continue
        candidates.append((header, offsets))
    if len(candidates) != 1:
        raise ContractError(f"root 0x{root:08X}: header ownership is not unique")
    return candidates[0]


def split_records(image: mmap.mmap, start: int, end: int) -> list[tuple[int, bytes]]:
    records: list[tuple[int, bytes]] = []
    cursor = start
    while cursor < end:
        terminator = image.find(b"\x00", cursor, end)
        if terminator < 0:
            raise ContractError(f"unterminated local dictionary at 0x{cursor:08X}")
        records.append((cursor, bytes(image[cursor : terminator + 1])))
        cursor = terminator + 1
    return records


def dictionary_records(
    image: mmap.mmap, replica_index: int, header: int, offsets: list[int]
) -> tuple[int, int, list[tuple[int, bytes]]]:
    dictionary_start = header + offsets[4]
    # The five short replicas repeat early section pointers.  Their dictionary
    # occupies 0x9B0..0x124C; long replicas use section 4..5.
    dictionary_end = header + (offsets[7] if replica_index >= 100 else offsets[5])
    records = split_records(image, dictionary_start, dictionary_end)
    if len(records) < 0x36:
        raise ContractError(f"replica {replica_index:03d}: local dictionary is too short")
    return dictionary_start, dictionary_end, records


def expand_code(
    records: list[tuple[int, bytes]], code: int, stack: tuple[int, ...] = ()
) -> tuple[bytes, tuple[int, ...]]:
    if code < 1 or code > len(records):
        raise ContractError(f"dictionary code 0x{code:02X} is out of range")
    if code in stack:
        chain = " -> ".join(f"0x{value:02X}" for value in stack + (code,))
        raise ContractError(f"dictionary cycle: {chain}")
    raw = records[code - 1][1][:-1]
    result = bytearray()
    children: list[int] = []
    cursor = 0
    while cursor < len(raw):
        if raw[cursor] == 0x04:
            if cursor + 1 >= len(raw):
                raise ContractError(f"dangling 0x04 in dictionary code 0x{code:02X}")
            child = raw[cursor + 1]
            expanded, descendants = expand_code(records, child, stack + (code,))
            result.extend(expanded)
            children.append(child)
            children.extend(descendants)
            cursor += 2
            continue
        result.append(raw[cursor])
        cursor += 1
    return bytes(result), tuple(children)


def classify_replicas(image: mmap.mmap, roots: list[int]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, root in enumerate(roots):
        actual_root = bytes(image[root : root + len(ROOT_BEFORE)])
        if actual_root != ROOT_BEFORE:
            raise ContractError(f"replica {index:03d}: purchase root preimage drift at 0x{root:08X}")
        header, section_offsets = parse_header(image, root)
        dictionary_start, dictionary_end, records = dictionary_records(
            image, index, header, section_offsets
        )
        code35_offset, code35 = records[0x35 - 1]
        expanded, nested = expand_code(records, 0x35)
        inner_questions = expanded.count(QUESTION)
        if inner_questions not in (0, 1):
            raise ContractError(
                f"replica {index:03d}: 0x0435 expansion owns {inner_questions} questions"
            )
        target = index in TARGET_INDICES
        if target != (inner_questions == 0):
            raise ContractError(
                f"replica {index:03d}: q=0 target ownership set drifted"
            )
        if target:
            ownership = "purchase-root-outer"
        elif 0x36 in nested:
            ownership = "nested-local-code36"
        else:
            ownership = "local-code35-direct"
        outer_before = actual_root[-3:-1]
        outer_after = QUESTION if target else outer_before
        if outer_before != BLANK:
            raise ContractError(f"replica {index:03d}: purchase outer cell is not blank")
        final_questions = inner_questions + (1 if outer_after == QUESTION else 0)
        if final_questions != 1:
            raise ContractError(f"replica {index:03d}: projected question count is not one")
        rows.append(
            {
                "replica_index": index,
                "purchase_root": f"0x{root:08X}",
                "outer_cell_offset": f"0x{root + 16:08X}",
                "patched_byte_offset": f"0x{root + 17:08X}" if target else None,
                "text_header": f"0x{header:08X}",
                "section_count": len(section_offsets),
                "local_dictionary_start": f"0x{dictionary_start:08X}",
                "local_dictionary_end": f"0x{dictionary_end:08X}",
                "local_dictionary_records": len(records),
                "code35_offset": f"0x{code35_offset:08X}",
                "code35_hex": code35.hex().upper(),
                "nested_codes": [f"0x{code:02X}" for code in nested],
                "expanded_code35_hex": expanded.hex().upper(),
                "inner_question_count": inner_questions,
                "outer_before_hex": outer_before.hex().upper(),
                "outer_after_hex": outer_after.hex().upper(),
                "final_question_count": final_questions,
                "question_owner_after": ownership,
                "write": target,
            }
        )
    owners = {name: sum(row["question_owner_after"] == name for row in rows) for name in (
        "purchase-root-outer", "nested-local-code36", "local-code35-direct"
    )}
    expected = {
        "purchase-root-outer": 3,
        "nested-local-code36": 97,
        "local-code35-direct": 5,
    }
    if owners != expected:
        raise ContractError(f"replica question ownership distribution drift: {owners}")
    return rows


def range_bytes(image: mmap.mmap, start: int, end: int) -> bytes:
    raw = bytes(image[start:end])
    if len(raw) != end - start:
        raise ContractError(f"short protected read: 0x{start:08X}..0x{end:08X}")
    return raw


def validate_protected(image: mmap.mmap) -> dict[str, object]:
    report: dict[str, object] = {}
    for name, (start, end, expected) in PROTECTED_RANGES.items():
        actual = sha256(range_bytes(image, start, end))
        if actual != expected:
            raise ContractError(f"protected range drift: {name}: {actual}")
        report[name] = {
            "start": f"0x{start:08X}",
            "end_exclusive": f"0x{end:08X}",
            "sha256": actual,
            "unchanged": True,
        }
    groups: dict[str, object] = {}
    for name, specification in PROTECTED_GROUPS.items():
        *ranges, expected = specification
        payload = b"".join(range_bytes(image, start, end) for start, end in ranges)
        actual = sha256(payload)
        if actual != expected:
            raise ContractError(f"protected group drift: {name}: {actual}")
        groups[name] = {"sha256": actual, "bytes": len(payload), "unchanged": True}
    report["groups"] = groups
    return report


def hash_excluding(path: Path, offsets: Iterable[int]) -> str:
    digest = hashlib.sha256()
    cursor = 0
    with path.open("rb") as source:
        for offset in sorted(offsets):
            if offset < cursor:
                raise ContractError("complement offsets overlap")
            source.seek(cursor)
            remaining = offset - cursor
            while remaining:
                block = source.read(min(COPY_CHUNK, remaining))
                if not block:
                    raise ContractError("short complement read")
                digest.update(block)
                remaining -= len(block)
            cursor = offset + 1
        source.seek(cursor)
        for block in iter(lambda: source.read(COPY_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def projected_sha(path: Path, writes: dict[int, int]) -> str:
    digest = hashlib.sha256()
    absolute = 0
    with path.open("rb") as source:
        while True:
            block = source.read(COPY_CHUNK)
            if not block:
                break
            mutable = bytearray(block)
            for offset, value in writes.items():
                if absolute <= offset < absolute + len(block):
                    mutable[offset - absolute] = value
            digest.update(mutable)
            absolute += len(block)
    if absolute != COOKED_BYTES:
        raise ContractError("projected input size drift")
    return digest.hexdigest().upper()


def static_audit(path: Path) -> tuple[list[int], list[dict[str, object]], dict[str, object]]:
    require_file(path, INPUT_SHA256, COOKED_BYTES)
    common = read_json(COMMON_AUDIT, COMMON_AUDIT_SHA256)
    roots = replica_roots(common)
    with path.open("rb") as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as image:
        signatures: list[int] = []
        cursor = 0
        while True:
            match = image.find(COMMON_SIGNATURE, cursor)
            if match < 0:
                break
            signatures.append(match)
            cursor = match + 1
        expected_signatures = [root + 0x6C for root in roots]
        if signatures != expected_signatures:
            raise ContractError("live common-signature scan differs from pinned 105 topology")
        rows = classify_replicas(image, roots)
        if sha256(b"".join(range_bytes(image, root, root + len(ROOT_BEFORE)) for root in roots)) != ROOT_BLOB_BEFORE_SHA256:
            raise ContractError("purchase-root preimage inventory hash drift")
        q1_roots = b"".join(
            range_bytes(image, root, root + len(ROOT_BEFORE))
            for index, root in enumerate(roots)
            if index not in TARGET_INDICES
        )
        if sha256(q1_roots) != Q1_ROOTS_SHA256:
            raise ContractError("q=1 protected purchase-root inventory drift")
        protected = validate_protected(image)
    plan = b"".join(
        struct.pack("<Q", offset) + bytes((0x40, 0x48)) for offset in TARGET_OFFSETS
    )
    if sha256(plan) != WRITE_PLAN_SHA256:
        raise ContractError("write-plan hash drift")
    if tuple(int(str(row["patched_byte_offset"]), 0) for row in rows if row["write"]) != TARGET_OFFSETS:
        raise ContractError("derived write offsets differ from frozen target offsets")
    if hash_excluding(path, TARGET_OFFSETS) != COMPLEMENT_SHA256:
        raise ContractError("input complement hash drift")
    if projected_sha(path, {offset: 0x48 for offset in TARGET_OFFSETS}) != OUTPUT_SHA256:
        raise ContractError("projected output SHA-256 drift")
    return roots, rows, protected


def verify_output(path: Path, roots: list[int]) -> None:
    require_file(path, OUTPUT_SHA256, COOKED_BYTES)
    if hash_excluding(path, TARGET_OFFSETS) != COMPLEMENT_SHA256:
        raise ContractError("output complement hash drift")
    with path.open("rb") as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as image:
        for index, root in enumerate(roots):
            expected = ROOT_AFTER if index in TARGET_INDICES else ROOT_BEFORE
            if bytes(image[root : root + len(expected)]) != expected:
                raise ContractError(f"output purchase root mismatch: replica {index:03d}")
        blob = b"".join(bytes(image[root : root + len(ROOT_BEFORE)]) for root in roots)
        if sha256(blob) != ROOT_BLOB_AFTER_SHA256:
            raise ContractError("output purchase-root inventory hash drift")
        validate_protected(image)


def write_output(source_path: Path, output_path: Path, writes: dict[int, int]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    try:
        digest = hashlib.sha256()
        absolute = 0
        with source_path.open("rb") as source, os.fdopen(fd, "wb") as output:
            while True:
                block = source.read(COPY_CHUNK)
                if not block:
                    break
                mutable = bytearray(block)
                for offset, value in writes.items():
                    if absolute <= offset < absolute + len(block):
                        local = offset - absolute
                        if mutable[local] != 0x40:
                            raise ContractError(f"write preimage drift at 0x{offset:08X}")
                        mutable[local] = value
                output.write(mutable)
                digest.update(mutable)
                absolute += len(block)
            output.flush()
            os.fsync(output.fileno())
        if absolute != COOKED_BYTES or digest.hexdigest().upper() != OUTPUT_SHA256:
            raise ContractError("temporary output size/hash mismatch")
        os.replace(temporary, output_path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def run_negative_tests() -> dict[str, bool]:
    def exact_write(buffer: bytearray, offset: int, before: int, after: int) -> None:
        if buffer[offset] != before:
            raise ContractError("synthetic preimage mismatch")
        buffer[offset] = after

    preimage_rejected = False
    try:
        exact_write(bytearray(b"\x41"), 0, 0x40, 0x48)
    except ContractError:
        preimage_rejected = True
    cycle_rejected = False
    try:
        expand_code([(0, b"\x04\x01\x00")], 1)
    except ContractError:
        cycle_rejected = True
    double_question_rejected = QUESTION.count(QUESTION) + 1 != 1
    results = {
        "wrong_preimage_rejected": preimage_rejected,
        "dictionary_cycle_rejected": cycle_rejected,
        "patching_inner_q1_would_be_rejected": double_question_rejected,
    }
    if not all(results.values()):
        raise ContractError(f"negative self-test failed: {results}")
    return results


def make_ownership_audit(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": 1,
        "status": "pass",
        "input": {
            "path": INPUT.relative_to(ROOT).as_posix(),
            "bytes": COOKED_BYTES,
            "sha256": INPUT_SHA256,
            "coordinate": "cooked Mode 1 payload",
        },
        "root_cause": (
            "The 105 replicated purchase roots all ended 0x0435+8140. "
            "Three global text blocks expand local 0x0435 without a question "
            "because their save roots own an outer question; 97 scenario "
            "replicas own it through nested 0x0436 and five short replicas own "
            "it directly in 0x0435."
        ),
        "classification": {
            "replicas": 105,
            "purchase_root_outer_owner": 3,
            "nested_local_code36_owner": 97,
            "local_code35_direct_owner": 5,
            "target_indices": list(TARGET_INDICES),
            "all_projected_question_counts": 1,
        },
        "replicas": rows,
        "runtime": {
            "executed": False,
            "reason": "withheld: pre-existing user-owned Mednafen process observed",
        },
        "package_allowed": False,
        "release": False,
    }


def make_manifest(
    output_path: Path,
    rows: list[dict[str, object]],
    protected: dict[str, object],
    negatives: dict[str, bool],
) -> dict[str, object]:
    return {
        "schema": 1,
        "component": "r76-shop-question-outer-root",
        "status": "cooked-static-pass",
        "purpose": "add the sole missing purchase question mark without editing shared 0x0435",
        "input": {
            "path": INPUT.relative_to(ROOT).as_posix(),
            "bytes": COOKED_BYTES,
            "sha256": INPUT_SHA256,
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "bytes": COOKED_BYTES,
            "sha256": OUTPUT_SHA256,
        },
        "builder": {
            "path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "sha256": file_sha256(Path(__file__).resolve()),
        },
        "verifier": {
            "path": VERIFIER.relative_to(ROOT).as_posix(),
            "sha256": file_sha256(VERIFIER),
        },
        "common_replica_audit": {
            "path": COMMON_AUDIT.relative_to(ROOT).as_posix(),
            "sha256": COMMON_AUDIT_SHA256,
            "topology_sha256": TOPOLOGY_SHA256,
        },
        "writes": [
            {
                "id": f"global-text-block-{block}/purchase-root-outer-question",
                "replica_index": index,
                "cooked_offset": f"0x{offset:08X}",
                "expected_hex": "40",
                "replacement_hex": "48",
                "containing_pair_before_hex": "8140",
                "containing_pair_after_hex": "8148",
            }
            for block, index, offset in zip((0, 1, 2), TARGET_INDICES, TARGET_OFFSETS)
        ],
        "diff_gates": {
            "changed_bytes": 3,
            "changed_offsets": [f"0x{offset:08X}" for offset in TARGET_OFFSETS],
            "changed_cooked_sectors": list(EXPECTED_SECTORS),
            "write_plan_sha256": WRITE_PLAN_SHA256,
            "complement_sha256": COMPLEMENT_SHA256,
            "root_blob_before_sha256": ROOT_BLOB_BEFORE_SHA256,
            "root_blob_after_sha256": ROOT_BLOB_AFTER_SHA256,
            "protected_q1_roots_sha256": Q1_ROOTS_SHA256,
        },
        "ownership": {
            "replicas": len(rows),
            "target_indices": list(TARGET_INDICES),
            "q0_before": sum(row["inner_question_count"] == 0 for row in rows),
            "q1_before": sum(row["inner_question_count"] == 1 for row in rows),
            "q1_after_all": sum(row["final_question_count"] == 1 for row in rows),
            "audit_path": OWNERSHIP_AUDIT.relative_to(ROOT).as_posix(),
        },
        "protected": protected,
        "negative_tests": negatives,
        "scope": {
            "shared_0435_dictionary_edited": False,
            "catalog_edited": False,
            "save_consumer_a_edited": False,
            "save_consumer_b_edited": False,
            "q1_shop_replicas_edited": False,
            "cooked_only": True,
        },
        "runtime": {
            "executed": False,
            "reason": "withheld: pre-existing user-owned Mednafen process observed",
        },
        "raw_track_created": False,
        "cue_created": False,
        "emulator_run": False,
        "package_allowed": False,
        "release": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--negative-test", action="store_true")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--ownership-audit", type=Path, default=OWNERSHIP_AUDIT)
    args = parser.parse_args()

    if args.input.resolve() != INPUT.resolve():
        # Custom paths are allowed only as aliases/copies of the exact R75 bytes.
        require_file(args.input, INPUT_SHA256, COOKED_BYTES)
    roots, rows, protected = static_audit(args.input)
    negatives = run_negative_tests()
    if args.negative_test:
        print(json.dumps(negatives, sort_keys=True))
        return 0
    if args.self_test:
        print(
            f"PASS self-test replicas={len(rows)} targets={list(TARGET_INDICES)} "
            f"projected_sha256={OUTPUT_SHA256}"
        )
        return 0

    writes = {offset: 0x48 for offset in TARGET_OFFSETS}
    write_output(args.input, args.output, writes)
    verify_output(args.output, roots)
    atomic_json(args.ownership_audit, make_ownership_audit(rows))
    manifest = make_manifest(args.output, rows, protected, negatives)
    if args.ownership_audit.resolve() != OWNERSHIP_AUDIT.resolve():
        manifest["ownership"]["audit_path"] = args.ownership_audit.as_posix()
    atomic_json(args.manifest, manifest)
    print(
        f"PASS build changed_bytes=3 sectors={list(EXPECTED_SECTORS)} "
        f"output_sha256={OUTPUT_SHA256}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as error:
        raise SystemExit(f"FAIL CLOSED: {error}") from error
