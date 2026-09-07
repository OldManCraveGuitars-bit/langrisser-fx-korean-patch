#!/usr/bin/env python3
"""Create the source-gated LFXPAT01 sparse patch used by this project.

Patch creation is a maintainer operation and uses NumPy to compare large raw
tracks efficiently.  Applying the resulting patch requires only Python's
standard library; see ``patch/apply_patch.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

import numpy as np


MAGIC = b"LFXPAT01"
HEADER_LENGTH = struct.Struct("<I")
CHUNK_HEADER = struct.Struct("<QII")
COMPARE_BLOCK = 8 * 1024 * 1024
MAX_CHUNK = 1024 * 1024
MERGE_GAP = 64


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def split_extent(start: int, end: int):
    while start < end:
        next_end = min(start + MAX_CHUNK, end)
        yield start, next_end
        start = next_end


def changed_extents(source: Path, target: Path):
    source_size = source.stat().st_size
    target_size = target.stat().st_size
    common = min(source_size, target_size)
    source_map = np.memmap(source, dtype=np.uint8, mode="r")
    target_map = np.memmap(target, dtype=np.uint8, mode="r")
    try:
        for base in range(0, common, COMPARE_BLOCK):
            end = min(base + COMPARE_BLOCK, common)
            indices = np.flatnonzero(source_map[base:end] != target_map[base:end])
            if not len(indices):
                continue
            breaks = np.flatnonzero(np.diff(indices) > MERGE_GAP)
            group_starts = np.concatenate(([0], breaks + 1))
            group_ends = np.concatenate((breaks, [len(indices) - 1]))
            for first, last in zip(group_starts, group_ends):
                start = base + int(indices[int(first)])
                stop = base + int(indices[int(last)]) + 1
                yield from split_extent(start, stop)
        if target_size > common:
            yield from split_extent(common, target_size)
    finally:
        del source_map
        del target_map


def create_patch(source: Path, target: Path, output: Path) -> dict[str, object]:
    source = source.resolve()
    target = target.resolve()
    output = output.resolve()
    if not source.is_file() or not target.is_file():
        raise RuntimeError("source or target is missing")
    if output.exists():
        raise RuntimeError("output already exists")
    if output in {source, target}:
        raise RuntimeError("patch output must be a separate file")

    target_map = np.memmap(target, dtype=np.uint8, mode="r")
    chunks: list[tuple[int, int, bytes]] = []
    try:
        previous_end = 0
        for start, stop in changed_extents(source, target):
            if start < previous_end:
                raise RuntimeError("internal overlap in generated extents")
            replacement = bytes(target_map[start:stop])
            chunks.append((start, len(replacement), zlib.compress(replacement, level=9)))
            previous_end = stop
    finally:
        del target_map

    header = {
        "schema": "langrisser-fx-sparse-patch/v1",
        "description": "Der Langrisser FX (PC-FX) Korean Track 2 v0.825 delta",
        "source_representation": "raw MODE1/2352 Track 2 with 225-sector pregap",
        "source_size": source.stat().st_size,
        "source_sha256": sha256_file(source),
        "target_size": target.stat().st_size,
        "target_sha256": sha256_file(target),
        "chunk_count": len(chunks),
        "compression": "zlib",
        "merge_gap": MERGE_GAP,
        "max_chunk": MAX_CHUNK,
    }
    encoded_header = json.dumps(
        header, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as stream:
            stream.write(MAGIC)
            stream.write(HEADER_LENGTH.pack(len(encoded_header)))
            stream.write(encoded_header)
            for offset, raw_size, compressed in chunks:
                stream.write(CHUNK_HEADER.pack(offset, raw_size, len(compressed)))
                stream.write(compressed)
    except Exception:
        if output.exists():
            output.unlink()
        raise
    return header | {
        "patch_path": str(output),
        "patch_size": output.stat().st_size,
        "patch_sha256": sha256_file(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(create_patch(args.source, args.target, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
