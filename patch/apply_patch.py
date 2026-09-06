#!/usr/bin/env python3
"""Apply a Langrisser FX sparse delta without overwriting the source image.

The patch format is intentionally small and dependency-free.  It verifies the
exact source size and SHA-256 before writing, applies ordered zlib-compressed
replacement ranges, and verifies the complete target SHA-256 afterwards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import zlib


MAGIC = b"LFXPAT01"
HEADER_LENGTH = struct.Struct("<I")
CHUNK_HEADER = struct.Struct("<QII")
COPY_BLOCK = 4 * 1024 * 1024


class PatchError(RuntimeError):
    """Raised when the source, patch container, or final result is invalid."""


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def read_header(stream) -> dict[str, object]:
    if stream.read(len(MAGIC)) != MAGIC:
        raise PatchError("not a Langrisser FX LFXPAT01 patch")
    raw_length = stream.read(HEADER_LENGTH.size)
    if len(raw_length) != HEADER_LENGTH.size:
        raise PatchError("truncated patch header length")
    (length,) = HEADER_LENGTH.unpack(raw_length)
    if length <= 0 or length > 1024 * 1024:
        raise PatchError("invalid patch header length")
    raw_header = stream.read(length)
    if len(raw_header) != length:
        raise PatchError("truncated patch header")
    try:
        header = json.loads(raw_header.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PatchError("invalid patch header JSON") from exc
    required = {
        "schema",
        "source_size",
        "source_sha256",
        "target_size",
        "target_sha256",
        "chunk_count",
    }
    if header.get("schema") != "langrisser-fx-sparse-patch/v1":
        raise PatchError("unsupported patch schema")
    if not required.issubset(header):
        raise PatchError("patch header is missing required fields")
    return header


def apply_patch(source: Path, patch: Path, output: Path) -> dict[str, object]:
    source = source.resolve()
    patch = patch.resolve()
    output = output.resolve()
    if not source.is_file() or not patch.is_file():
        raise PatchError("source Track 2 or patch file does not exist")
    if output.exists():
        raise PatchError("output already exists; choose a new file")
    if output == source or output == patch:
        raise PatchError("output must be a separate new file")

    created = False
    try:
        with patch.open("rb") as patch_stream:
            header = read_header(patch_stream)
            source_size = int(header["source_size"])
            target_size = int(header["target_size"])
            chunk_count = int(header["chunk_count"])
            if source.stat().st_size != source_size:
                raise PatchError("source Track 2 size does not match the supported dump")
            actual_source_hash = sha256_file(source)
            if actual_source_hash != str(header["source_sha256"]).upper():
                raise PatchError("source Track 2 SHA-256 does not match the supported dump")
            if target_size <= 0 or chunk_count < 0:
                raise PatchError("invalid target size or chunk count")

            output.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as source_stream, output.open("xb+") as target_stream:
                created = True
                shutil.copyfileobj(source_stream, target_stream, COPY_BLOCK)
                target_stream.truncate(target_size)
                previous_end = 0
                for index in range(chunk_count):
                    raw_chunk_header = patch_stream.read(CHUNK_HEADER.size)
                    if len(raw_chunk_header) != CHUNK_HEADER.size:
                        raise PatchError(f"truncated chunk header at index {index}")
                    offset, raw_size, compressed_size = CHUNK_HEADER.unpack(raw_chunk_header)
                    if raw_size <= 0 or compressed_size <= 0:
                        raise PatchError(f"invalid chunk size at index {index}")
                    if offset < previous_end or offset + raw_size > target_size:
                        raise PatchError(f"overlapping or out-of-range chunk at index {index}")
                    compressed = patch_stream.read(compressed_size)
                    if len(compressed) != compressed_size:
                        raise PatchError(f"truncated chunk payload at index {index}")
                    try:
                        replacement = zlib.decompress(compressed)
                    except zlib.error as exc:
                        raise PatchError(f"invalid compressed chunk at index {index}") from exc
                    if len(replacement) != raw_size:
                        raise PatchError(f"decompressed chunk length mismatch at index {index}")
                    target_stream.seek(offset)
                    target_stream.write(replacement)
                    previous_end = offset + raw_size
                if patch_stream.read(1):
                    raise PatchError("unexpected trailing data in patch")
                target_stream.flush()

        actual_target_hash = sha256_file(output)
        expected_target_hash = str(header["target_sha256"]).upper()
        if actual_target_hash != expected_target_hash:
            raise PatchError("patched Track 2 SHA-256 verification failed")
        return {
            "status": "PASS",
            "output": str(output),
            "bytes": output.stat().st_size,
            "sha256": actual_target_hash,
            "chunks": int(header["chunk_count"]),
        }
    except Exception:
        if created and output.exists():
            output.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply the Langrisser FX Korean Track 2 delta patch."
    )
    parser.add_argument("source", type=Path, help="original Japanese raw MODE1/2352 Track 2")
    parser.add_argument("output", type=Path, help="new patched Track 2 path")
    parser.add_argument(
        "--patch",
        type=Path,
        default=Path(__file__).with_name("Langrisser-FX-KR-successor264.lfxpatch"),
    )
    args = parser.parse_args()
    try:
        result = apply_patch(args.source, args.patch, args.output)
    except (OSError, PatchError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

