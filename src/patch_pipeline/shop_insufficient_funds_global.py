"""Exact global repair for the shop insufficient-funds dictionary phrase.

Every scenario owns a local 04xx dictionary. Thirty replicas already map
the warning's code 0x11 to ``부족합니다.``. In the other seventy-five,
code 0x11 is shared with unrelated dialogue (for example Hain's ``어.``), so
it must never be rewritten. Allocate the otherwise unused private code 0xF0
in those replicas and redirect only the fixed shop-warning token to it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_r76_shop_question_outer_root_component as ownership  # noqa: E402


CATALOG = ROOT / "analysis/common_dictionary_replicas_v340_audit.json"
CATALOG_SHA256 = "816B0D8A0FE6CAAFE54EF91A0F2AD8EF892A00B5D8E362D953509A007BA01B9A"
FIXED_RELATIVE = 0x032C
FIXED_RECORD = bytes.fromhex("F046F08AF082F1E80411")
SHARED_CODE = 0x11
PRIVATE_CODE = 0xF0
PRIVATE_LAST_CODE = 0xFC
PHRASE = bytes.fromhex("F1F6F24EF1E2F08CF08D2E05")
RECORD = PHRASE + b"\0"


def need(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def all_matches(image: bytes, needle: bytes, start: int, end: int) -> list[int]:
    matches: list[int] = []
    cursor = start
    while True:
        cursor = image.find(needle, cursor, end)
        if cursor < 0:
            return matches
        matches.append(cursor)
        cursor += 1


def replica_starts() -> tuple[int, ...]:
    need(sha(CATALOG.read_bytes()) == CATALOG_SHA256, "common catalog identity")
    document = json.loads(CATALOG.read_text(encoding="utf-8"))
    starts = tuple(int(value, 0) for value in document["replica_offsets"])
    need(len(starts) == 105 and len(set(starts)) == 105, "common population closure")
    return starts


def _geometry(image: bytes, replica: int, start: int):
    root = start - 0x6C
    header, offsets = ownership.parse_header(image, root)
    dictionary_start, dictionary_end, records = ownership.dictionary_records(
        image, replica, header, offsets
    )
    return header, offsets, dictionary_start, dictionary_end, records


def replica_plan(image: bytes, replica: int, start: int) -> tuple[list[tuple[int, bytes, bytes, str]], dict[str, object]]:
    header, offsets, dictionary_start, dictionary_end, records = _geometry(image, replica, start)
    need(b"".join(raw for _address, raw in records) == image[dictionary_start:dictionary_end],
         f"replica {replica:03d}: dictionary split geometry")
    warning = image[start + FIXED_RELATIVE:start + FIXED_RELATIVE + len(FIXED_RECORD)]
    need(warning == FIXED_RECORD, f"replica {replica:03d}: fixed warning root")

    shared_record = records[SHARED_CODE - 1][1]
    expanded, descendants = ownership.expand_code(records, SHARED_CODE)
    writes: list[tuple[int, bytes, bytes, str]] = []
    route = "existing-code11"
    warning_code = SHARED_CODE
    if expanded != PHRASE or descendants:
        need(len(RECORD) == PRIVATE_LAST_CODE - PRIVATE_CODE + 1,
             "private record extent")
        need(len(records) >= PRIVATE_LAST_CODE,
             f"replica {replica:03d}: private code population")
        donor_rows = records[PRIVATE_CODE - 1:PRIVATE_LAST_CODE]
        need(len(donor_rows) == len(RECORD),
             f"replica {replica:03d}: private row count")
        need(all(raw == b"\0" for _address, raw in donor_rows),
             f"replica {replica:03d}: private rows not empty")
        donor_address = donor_rows[0][0]
        need([address for address, _raw in donor_rows]
             == list(range(donor_address, donor_address + len(RECORD))),
             f"replica {replica:03d}: private rows not contiguous")
        donor_before = image[donor_address:donor_address + len(RECORD)]
        need(donor_before == bytes(len(RECORD)),
             f"replica {replica:03d}: private preimage")

        consumer_start = header + offsets[0]
        need(not all_matches(image, bytes((4, PRIVATE_CODE)), consumer_start, dictionary_end),
             f"replica {replica:03d}: private code already consumed")
        token_address = start + FIXED_RELATIVE + len(FIXED_RECORD) - 1
        need(image[token_address:token_address + 1] == bytes((SHARED_CODE,)),
             f"replica {replica:03d}: warning token preimage")
        writes.extend((
            (token_address, bytes((SHARED_CODE,)), bytes((PRIVATE_CODE,)),
             f"shop/insufficient-funds/private-token/replica/{replica:03d}"),
            (donor_address, donor_before, RECORD,
             f"shop/insufficient-funds/private-codeF0/replica/{replica:03d}"),
        ))
        route = "private-codeF0"
        warning_code = PRIVATE_CODE

    return writes, {
        "replica": replica,
        "dictionary_start": f"0x{dictionary_start:08X}",
        "dictionary_end": f"0x{dictionary_end:08X}",
        "route": route,
        "warning_dictionary_code": f"0x{warning_code:02X}",
        "shared_code11_record_hex": shared_record.hex().upper(),
        "private_record_hex": RECORD.hex().upper() if warning_code == PRIVATE_CODE else None,
    }


def plan(image: bytes) -> tuple[list[tuple[int, bytes, bytes, str]], list[dict[str, object]]]:
    writes: list[tuple[int, bytes, bytes, str]] = []
    rows: list[dict[str, object]] = []
    for replica, start in enumerate(replica_starts()):
        replica_writes, row = replica_plan(image, replica, start)
        rows.append(row)
        writes.extend(replica_writes)
    need(len(rows) == 105, "shop population denominator")
    need(sum(row["route"] == "existing-code11" for row in rows) == 30,
         "unexpected existing-code11 route count")
    need(sum(row["route"] == "private-codeF0" for row in rows) == 75,
         "unexpected private-codeF0 route count")
    need(len(writes) == 150, "shop write owner count")
    return writes, rows


def verify(image: bytes) -> dict[str, object]:
    starts = replica_starts()
    route_counts = {"existing-code11": 0, "private-codeF0": 0}
    for replica, start in enumerate(starts):
        header, offsets, _ds, dictionary_end, records = _geometry(image, replica, start)
        fixed = image[start + FIXED_RELATIVE:start + FIXED_RELATIVE + len(FIXED_RECORD)]
        need(fixed[:-1] == FIXED_RECORD[:-1],
             f"replica {replica:03d}: final fixed warning prefix")
        code = fixed[-1]
        need(code in (SHARED_CODE, PRIVATE_CODE),
             f"replica {replica:03d}: final warning code")
        expanded, descendants = ownership.expand_code(records, code)
        need(expanded == PHRASE and not descendants,
             f"replica {replica:03d}: final insufficient-funds suffix")
        if code == SHARED_CODE:
            need(records[SHARED_CODE - 1][1] == RECORD,
                 f"replica {replica:03d}: existing code11 record")
            route_counts["existing-code11"] += 1
        else:
            need(records[PRIVATE_CODE - 1][1] == RECORD,
                 f"replica {replica:03d}: private codeF0 record")
            consumer_start = header + offsets[0]
            token_address = start + FIXED_RELATIVE + len(FIXED_RECORD) - 1
            need(all_matches(image, bytes((4, PRIVATE_CODE)), consumer_start, dictionary_end)
                 == [token_address - 1],
                 f"replica {replica:03d}: private codeF0 ownership")
            route_counts["private-codeF0"] += 1
    need(route_counts == {"existing-code11": 30, "private-codeF0": 75},
         "final shop route population")
    return {
        "common_replicas": len(starts),
        "routes": route_counts,
        "private_dictionary_code": "0xF0",
        "encoded_suffix_hex": PHRASE.hex().upper(),
        "rendered_text": "자금이 부족합니다.",
        "all_replicas_exact": True,
        "shared_code11_rewritten": False,
    }
