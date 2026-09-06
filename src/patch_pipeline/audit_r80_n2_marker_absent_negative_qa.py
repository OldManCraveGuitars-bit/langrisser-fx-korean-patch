#!/usr/bin/env python3
"""Independently audit corrected R80 marker-absent n2 runtime evidence.

This consumes, but does not create, the isolated runner's four synchronized n2
routes.  Both settled and after-action post-states must retain the exact n2
overlay, absent authentication marker, and source private KRAM envelope.  The
script also rejects black/unchanged route images.  Korean wording/clean return
remain explicit visual-review fields rather than an OCR claim.
"""

from __future__ import annotations

import argparse
import binascii
import gzip
import hashlib
import json
import os
import struct
import tempfile
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE = ROOT / "work/qa/r80-n2-marker-absent-negative"
DEFAULT_OUTPUT = ROOT / "analysis/r80-n2-marker-absent-negative-audit.json"
MANIFEST_SCHEMA = "langrisser-fx-r80-n2-marker-absent-negative-runtime-v1"
MANIFEST_STATUS = "CAPTURES_AND_POST_STATES_COMPLETE_INDEPENDENT_AUDIT_REQUIRED"
SYNC_STATUS = "PASS_FOUR_SYNCED_STATES_STATICALLY_VERIFIED_RUNTIME_NOT_STARTED"
RAW_STATUS = "PASS_ALL_321006_USER_SECTORS_AND_MODE1_PROTECTION_NO_EMULATOR"
BOUNDARY_STATUS = "PASS_CORRECTED_R2_COOKED_BOUNDARY_NO_RAW_NO_EMULATOR"
N2_SHA256 = "270E3C96BDD8310D7F4B3DAB6A0C89F6979B0C5665F5CBB8146651B353061603"
N2_RAM = (0x1D7000, 0x1E2000)
MARKER_RAM = 0x1D9748
PRIVATE_KRAM = (0x60000, 0x63000)
ROUTES = (
    "n2-victory-conditions", "n2-preparation", "n2-equipment", "n2-dialogue"
)
PHASES = ("settled", "after-action")


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def sha(data: bytes | memoryview) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def parse_state(path: Path) -> tuple[dict[tuple[str, str], bytes], bytes]:
    packed = path.read_bytes()
    raw = gzip.decompress(packed) if packed[:2] == b"\x1f\x8b" else packed
    require(raw[:8] == b"MDFNSVST", f"bad state magic: {path.name}")
    total = struct.unpack_from("<I", raw, 20)[0] & 0x7FFFFFFF
    width, height = struct.unpack_from("<II", raw, 24)
    preview_end = 32 + width * height * 3
    require(preview_end <= total <= len(raw), f"state extent drift: {path.name}")
    variables: dict[tuple[str, str], bytes] = {}
    cursor = preview_end
    while cursor < total:
        section = raw[cursor:cursor + 32].split(b"\0", 1)[0].decode("ascii")
        size = struct.unpack_from("<I", raw, cursor + 32)[0]
        position, end = cursor + 36, cursor + 36 + size
        require(end <= total, f"section overrun: {path.name}:{section}")
        while position < end:
            name_size = raw[position]
            position += 1
            name = raw[position:position + name_size].decode("ascii")
            position += name_size
            value_size = struct.unpack_from("<I", raw, position)[0]
            position += 4
            value_end = position + value_size
            require(value_end <= end, f"variable overrun: {path.name}:{section}/{name}")
            key = (section, name)
            require(key not in variables, f"duplicate variable: {path.name}:{key}")
            variables[key] = raw[position:value_end]
            position = value_end
        require(position == end, f"section boundary drift: {path.name}:{section}")
        cursor = end
    require(cursor == total, f"state did not close: {path.name}")
    return variables, raw[32:preview_end]


def decode_png(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    require(data[:8] == b"\x89PNG\r\n\x1a\n", f"not PNG: {path.name}")
    cursor = 8
    width = height = channels = 0
    compressed = bytearray()
    saw_end = False
    while cursor < len(data):
        require(cursor + 12 <= len(data), f"truncated PNG chunk: {path.name}")
        length = struct.unpack_from(">I", data, cursor)[0]
        kind = data[cursor + 4:cursor + 8]
        start, end = cursor + 8, cursor + 8 + length
        require(end + 4 <= len(data), f"PNG chunk overrun: {path.name}")
        payload = data[start:end]
        expected_crc = struct.unpack_from(">I", data, end)[0]
        require(binascii.crc32(kind + payload) & 0xFFFFFFFF == expected_crc,
                f"PNG CRC drift: {path.name}:{kind!r}")
        if kind == b"IHDR":
            require(length == 13, f"IHDR length drift: {path.name}")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            require(depth == 8 and color in (2, 6) and compression == filtering == interlace == 0,
                    f"unsupported PNG format: {path.name}")
            channels = 3 if color == 2 else 4
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            saw_end = True
            break
        cursor = end + 4
    require(saw_end and width > 0 and height > 0 and channels in (3, 4), f"incomplete PNG: {path.name}")
    filtered = zlib.decompress(bytes(compressed))
    row_bytes = width * channels
    require(len(filtered) == height * (row_bytes + 1), f"PNG scanline extent drift: {path.name}")
    output = bytearray(height * row_bytes)
    source = 0
    previous = bytearray(row_bytes)
    for y in range(height):
        mode = filtered[source]
        source += 1
        row = bytearray(filtered[source:source + row_bytes])
        source += row_bytes
        require(mode <= 4, f"unknown PNG filter: {path.name}:{mode}")
        for x in range(row_bytes):
            left = row[x - channels] if x >= channels else 0
            above = previous[x]
            upper_left = previous[x - channels] if x >= channels else 0
            if mode == 1:
                row[x] = (row[x] + left) & 0xFF
            elif mode == 2:
                row[x] = (row[x] + above) & 0xFF
            elif mode == 3:
                row[x] = (row[x] + ((left + above) >> 1)) & 0xFF
            elif mode == 4:
                predictor = left + above - upper_left
                pa, pb, pc = abs(predictor - left), abs(predictor - above), abs(predictor - upper_left)
                chosen = left if pa <= pb and pa <= pc else (above if pb <= pc else upper_left)
                row[x] = (row[x] + chosen) & 0xFF
        output[y * row_bytes:(y + 1) * row_bytes] = row
        previous = row
    if channels == 4:
        rgb = bytes(value for index, value in enumerate(output) if index % 4 != 3)
    else:
        rgb = bytes(output)
    return width, height, rgb


def preview_metrics(path: Path) -> tuple[dict[str, Any], bytes]:
    width, height, rgb = decode_png(path)
    channels = [rgb[index::3] for index in range(3)]
    extrema = [(min(channel), max(channel)) for channel in channels]
    means = [sum(channel) / len(channel) for channel in channels]
    variances = [sum((value - mean) ** 2 for value in channel) / len(channel)
                 for channel, mean in zip(channels, means)]
    require(max(high for _low, high in extrema) >= 32, f"black/near-black capture: {path.name}")
    require(sum(variances) >= 20, f"flat capture: {path.name}")
    return {
        "width": width,
        "height": height,
        "rgb_sha256": sha(rgb),
        "mean": [round(value, 3) for value in means],
        "variance_sum": round(sum(variances), 3),
        "extrema": [list(value) for value in extrema],
    }, rgb


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("self-test", "audit"))
    parser.add_argument("--capture", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.mode == "self-test":
        require(len(ROUTES) == len(set(ROUTES)) == 4, "route denominator drift")
        require(PHASES == ("settled", "after-action"), "phase contract drift")
        print(json.dumps({
            "status": "PASS_SELF_TEST_NO_RUNTIME_EVIDENCE_READ_OR_EMULATOR_STARTED",
            "routes": len(ROUTES), "post_states": len(ROUTES) * len(PHASES),
            "marker_absent_required": True, "private_kram_exact_required": True,
            "emulator_started": False, "runtime_pass": False, "package_allowed": False,
        }, indent=2))
        return 0

    capture = args.capture.resolve()
    manifest_path = capture / "runtime-review-required.json"
    require(manifest_path.is_file(), "missing runtime manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("schema") == MANIFEST_SCHEMA and manifest.get("status") == MANIFEST_STATUS,
            "runtime manifest schema/status drift")
    require(manifest.get("runtime_pass") is False and manifest.get("package_allowed") is False,
            "runtime manifest prematurely claims pass/package")
    require(manifest["protected_processes"]["unchanged"] is True,
            "protected PID was not preserved")
    require(manifest["execution"]["stops_only_spawned_pid"] is True
            and manifest["execution"]["spawned_process_exited"] is True,
            "process isolation contract failed")

    pinned_docs = (
        (Path(manifest["candidate"]["raw_audit"]), manifest["candidate"]["raw_audit_sha256"], RAW_STATUS),
        (Path(manifest["candidate"]["cooked_boundary_audit"]), manifest["candidate"]["cooked_boundary_audit_sha256"], BOUNDARY_STATUS),
        (Path(manifest["inputs"]["state_sync_manifest"]), manifest["inputs"]["state_sync_manifest_sha256"], SYNC_STATUS),
    )
    documents = []
    for path, expected, status in pinned_docs:
        require(path.is_file() and sha_file(path) == expected, f"pinned document drift: {path.name}")
        document = json.loads(path.read_text(encoding="utf-8"))
        require(document.get("status") == status, f"pinned document not GREEN: {path.name}")
        documents.append((path, document))
    sync = documents[2][1]
    sync_rows = {row["route"]: row for row in sync["routes"]}
    require(set(sync_rows) == set(ROUTES), "sync route set drift")

    state_rows = []
    capture_rows = []
    for route in ROUTES:
        source_kram_sha = sync_rows[route]["private_kram_source_sha256"]
        route_images: list[tuple[tuple[int, int], bytes]] = []
        for phase in PHASES:
            stem = f"{route}-{phase}"
            state_path = capture / f"{stem}.mc0"
            image_path = capture / f"{stem}.png"
            require(state_path.is_file() and image_path.is_file(), f"missing evidence: {stem}")
            variables, preview = parse_state(state_path)
            main = variables.get(("MAIN", "RAM"))
            kram = variables.get(("KING", "KRAM0"))
            require(main is not None and len(main) == 0x200000, f"MAIN/RAM missing: {stem}")
            require(kram is not None and len(kram) >= PRIVATE_KRAM[1], f"KING/KRAM0 missing: {stem}")
            require(sha(main[N2_RAM[0]:N2_RAM[1]]) == N2_SHA256, f"n2 overlay drift: {stem}")
            require(main[MARKER_RAM:MARKER_RAM + 8] == bytes(8), f"marker appeared: {stem}")
            private_sha = sha(kram[PRIVATE_KRAM[0]:PRIVATE_KRAM[1]])
            require(private_sha == source_kram_sha, f"private KRAM mutation: {stem}")
            state_rows.append({
                "route": route, "phase": phase, "path": str(state_path),
                "file_sha256": sha_file(state_path), "preview_rgb_sha256": sha(preview),
                "n2_overlay_exact": True, "marker_absent": True,
                "private_kram_sha256": private_sha, "private_kram_exact_source": True,
            })
            metrics, rgb = preview_metrics(image_path)
            route_images.append(((metrics["width"], metrics["height"]), rgb))
            capture_rows.append({"route": route, "phase": phase, "path": str(image_path),
                                 "file_sha256": sha_file(image_path), **metrics})
        require(route_images[0][0] == route_images[1][0], f"capture size drift: {route}")
        require(route_images[0][1] != route_images[1][1],
                f"route action produced identical capture: {route}")

    require(len(state_rows) == len(capture_rows) == 8, "evidence denominator drift")
    report = {
        "schema": "langrisser-fx-r80-n2-marker-absent-negative-audit-v1",
        "status": "MECHANICAL_PASS_INDEPENDENT_VISUAL_REVIEW_REQUIRED",
        "runtime_manifest": {"path": str(manifest_path), "sha256": sha_file(manifest_path)},
        "mechanical_gates": {
            "four_routes_two_post_states_each": "PASS",
            "all_n2_overlays_exact": "PASS",
            "all_markers_absent": "PASS",
            "all_private_kram_envelopes_exact_source": "PASS",
            "no_black_or_flat_capture": "PASS",
            "all_actions_produced_distinct_capture": "PASS",
            "protected_pid_unchanged": "PASS",
        },
        "states": state_rows,
        "captures": capture_rows,
        "visual_review": {
            "status": "REQUIRED",
            "victory_conditions_native_and_clean_return": None,
            "preparation_no_private_contamination": None,
            "equipment_no_private_contamination": None,
            "dialogue_no_private_contamination": None,
            "no_crash_black_screen_or_tail_residue": None,
        },
        "runtime_pass": False,
        "package_allowed": False,
        "next_gate": "independent visual review of all eight captures",
    }
    output = args.output.resolve()
    atomic_json(output, report)
    print(json.dumps({
        "status": report["status"], "states": len(state_rows), "captures": len(capture_rows),
        "report": str(output), "report_sha256": sha_file(output),
        "runtime_pass": False, "package_allowed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as error:
        raise SystemExit(f"AUDIT_FAIL: {error}") from error
