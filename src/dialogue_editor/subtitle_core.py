#!/usr/bin/env python3
"""Canonical movie-subtitle model and cumulative successor190 payload compiler."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import copy
import json
import math
from pathlib import Path
import struct
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import build_r80_all_movie_subtitles_private_unifont_punctuation_successor145 as subtitle_build  # noqa: E402
import subtitle_bootstrap  # noqa: E402


SOURCES = (
    ROOT / "assets/subtitles/opening2-ko.json",
    ROOT / "assets/subtitles/silver-knight-ko.json",
    ROOT / "assets/subtitles/movies003-029-dialogue-ko.json",
)
MOVIE_COUNT = 30
FRAME_RATE = 60
MAX_LINES = 2
MAX_WIDTH_PX = 240
# The natural-playback namespace has one leading movie slot in addition to
# the 35 BGM slots.  Runtime evidence from successor181 showed that ID 36 is
# Opening 1 (Omake slot 0), not Opening 2.  Therefore natural 36..65 maps to
# the Omake editor's 0..29 directory.
NATURAL_MOVIE_ID_BASE = 36
NATURAL_MOVIE_ID_COUNT = MOVIE_COUNT
# Automatic Opening 1 and Opening 2 both expose natural movie ID 36.  The
# native route pointer is the stable discriminator captured across repeated
# playback: zero for Opening 1 and 0x00052580 for Opening 2.  Route only that
# exact combination to the editor's Opening-2/Omake slot 1.
NATURAL_SPECIAL_MOVIE_ID = 36
NATURAL_SPECIAL_MARKER_RAM = 0x001F1F24
NATURAL_SPECIAL_MARKER_VALUE = 0x00052580
NATURAL_SPECIAL_SELECTOR_ID = 1
NATURAL_SPECIAL_ROUTE_ENABLED = True
# The historical private renderer used 0x640 bytes and had only ten bytes
# free.  Dual Omake/natural ID normalization needs a little more code while
# leaving every cue and private glyph untouched.  The natural-route transparent
# BAT fill adds 0x18 bytes; 0x6A0 still fits the fixed 0x1F00-byte payload with
# twelve bytes of audited slack.
NATURAL_ALIAS_CODE_REGION_BYTES = 0x6A0


class SubtitleError(RuntimeError):
    pass


def need(ok: bool, message: str) -> None:
    if not ok:
        raise SubtitleError(message)


@dataclass(frozen=True)
class SubtitleCue:
    id: str
    movie_id: int
    movie_title: str
    source_index: int | None
    start: float
    end: float
    ja: str
    ko: tuple[str, ...]
    speaker: str = ""
    added: bool = False
    # Editor-only ordering. Playback and compilation still use start/end.
    list_order: int | None = None


def _source_documents() -> list[dict]:
    documents: list[dict] = []
    for path in SOURCES:
        need(path.is_file(), f"자막 원본이 없습니다: {path}")
        document = json.loads(path.read_text(encoding="utf-8"))
        need(int(document["frame_rate"]) == FRAME_RATE,
             f"자막 프레임레이트 오류: {path.name}")
        if "movies" in document:
            documents.extend(copy.deepcopy(document["movies"]))
        else:
            documents.append(copy.deepcopy(document))
    documents.sort(key=lambda row: int(row["movie_id"]))
    movie_ids = [int(row["movie_id"]) for row in documents]
    need(len(movie_ids) == len(set(movie_ids)), "영상 ID가 중복되었습니다.")
    return documents


@lru_cache(maxsize=1)
def load_subtitle_cues() -> tuple[SubtitleCue, ...]:
    records: list[SubtitleCue] = []
    for document in _source_documents():
        movie_id = int(document["movie_id"])
        title = str(document.get("movie_title") or f"영상 {movie_id:03d}")
        for index, cue in enumerate(document["cues"]):
            records.append(SubtitleCue(
                id=f"movie{movie_id:03d}/cue/{index:03d}",
                movie_id=movie_id,
                movie_title=title,
                source_index=index,
                start=float(cue["start"]),
                end=float(cue["end"]),
                ja=str(cue.get("ja") or ""),
                ko=tuple(str(line) for line in cue["ko"]),
                speaker=str(cue.get("speaker") or ""),
                added=False,
            ))
    validate_subtitle_cues(records)
    return tuple(records)


@lru_cache(maxsize=1024)
def glyph_advance(character: str) -> int:
    data_build = subtitle_build.data_build
    need(data_build.USE_RESIDENT_FONT is False,
         "자막 글꼴이 공용 글꼴을 참조합니다.")
    need(data_build.USE_UNIFONT_12 is True,
         "자막 글꼴이 12x12 Unifont 정책을 따르지 않습니다.")
    _cell, _packed, advance = data_build.cell_and_advance(character)
    return int(advance)


def line_width(line: str) -> int:
    return sum(glyph_advance(character) for character in line)


def subtitle_overlap_ids(cues: Iterable[SubtitleCue]) -> frozenset[str]:
    """Return every cue participating in a time overlap.

    This helper is deliberately non-throwing so the editor can keep its list
    usable while a timing conflict is being repaired.  Invalid single-cue
    ranges are left to ``validate_subtitle_cues``; only finite, positive
    intervals can participate in an overlap warning.
    """
    by_movie: dict[int, list[SubtitleCue]] = {}
    for row in cues:
        if not (math.isfinite(row.start) and math.isfinite(row.end)):
            continue
        if row.start >= row.end:
            continue
        by_movie.setdefault(row.movie_id, []).append(row)

    overlaps: set[str] = set()
    for movie_rows in by_movie.values():
        ordered = sorted(movie_rows, key=lambda row: (row.start, row.end, row.id))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1:]:
                # Touching boundaries are valid: one cue may start exactly
                # when the preceding cue ends.
                if right.start >= left.end:
                    break
                if left.start < right.end:
                    overlaps.update((left.id, right.id))
    return frozenset(overlaps)


def validate_subtitle_cues(cues: Iterable[SubtitleCue]) -> None:
    rows = list(cues)
    ids = [row.id for row in rows]
    need(len(ids) == len(set(ids)), "자막 ID가 중복되었습니다.")
    by_movie: dict[int, list[SubtitleCue]] = {}
    for row in rows:
        need(0 <= row.movie_id < MOVIE_COUNT,
             f"{row.id}: 영상 ID 범위 오류")
        need(0 <= row.start < row.end < 0xFFFF / FRAME_RATE,
             f"{row.id}: 시작/끝 시간이 잘못되었습니다.")
        need(1 <= len(row.ko) <= MAX_LINES,
             f"{row.id}: 자막은 1~2줄이어야 합니다.")
        for line in row.ko:
            need(bool(line), f"{row.id}: 빈 자막 줄")
            width = line_width(line)
            need(width <= MAX_WIDTH_PX,
                 f"{row.id}: 자막 폭 {width}/{MAX_WIDTH_PX}px")
        by_movie.setdefault(row.movie_id, []).append(row)
    for movie_id, movie_rows in by_movie.items():
        ordered = sorted(movie_rows, key=lambda row: (row.start, row.end, row.id))
        previous_end = 0.0
        for row in ordered:
            need(previous_end <= row.start,
                 f"영상 {movie_id:03d}: 자막 시간이 겹칩니다: {row.id}")
            previous_end = row.end


def apply_subtitle_edits(
    base: Iterable[SubtitleCue], edits: dict[str, dict], *, validate: bool = True
) -> tuple[SubtitleCue, ...]:
    base_by_id = {row.id: row for row in base}
    result = dict(base_by_id)
    for cue_id, value in edits.items():
        need(isinstance(value, dict), f"{cue_id}: 자막 편집 자료 오류")
        original = base_by_id.get(cue_id)
        need(type(value.get("deleted", False)) is bool, f"{cue_id}: 자막 삭제 표시 오류")
        if value.get("deleted"):
            need(original is not None, f"삭제할 원본 자막 ID가 없습니다: {cue_id}")
            result.pop(cue_id, None)
            continue
        if original is None:
            need(bool(value.get("added")), f"알 수 없는 자막 ID: {cue_id}")
            movie_id = int(value["movie_id"])
            original = SubtitleCue(
                id=cue_id,
                movie_id=movie_id,
                movie_title=str(value.get("movie_title") or f"영상 {movie_id:03d}"),
                source_index=None,
                start=float(value["start"]),
                end=float(value["end"]),
                ja=str(value.get("ja") or ""),
                ko=tuple(str(line) for line in value["ko"]),
                speaker=str(value.get("speaker") or ""),
                added=True,
            )
        result[cue_id] = replace(
            original,
            start=float(value.get("start", original.start)),
            end=float(value.get("end", original.end)),
            ja=str(value.get("ja", original.ja)),
            ko=tuple(str(line) for line in value.get("ko", original.ko)),
            speaker=str(value.get("speaker", original.speaker)),
            added=bool(value.get("added", original.added)),
            list_order=value.get("list_order", original.list_order),
        )
        order = result[cue_id].list_order
        need(order is None or (type(order) is int and order >= 0),
             f"{cue_id}: 자막 목록 순서 오류")
    ordered = tuple(sorted(
        result.values(), key=lambda row: (row.movie_id, row.start, row.end, row.id)
    ))
    if validate:
        validate_subtitle_cues(ordered)
    return ordered


def subtitle_edit_row(row: SubtitleCue) -> dict[str, object]:
    value: dict[str, object] = {
        "start": round(row.start, 3),
        "end": round(row.end, 3),
        "ko": list(row.ko),
    }
    if row.list_order is not None:
        value["list_order"] = row.list_order
    if row.added:
        value.update({
            "added": True,
            "movie_id": row.movie_id,
            "movie_title": row.movie_title,
            "ja": row.ja,
            "speaker": row.speaker,
        })
    return value


def subtitle_display_rows(cues: Iterable[SubtitleCue]) -> tuple[SubtitleCue, ...]:
    """Stable editor order, independent of the game's time-sorted cue table."""
    rows = sorted(cues, key=lambda row: (row.movie_id, row.start, row.end, row.id))
    ranks, counts = {}, {}
    for row in rows:
        ranks[row.id] = counts.get(row.movie_id, 0)
        counts[row.movie_id] = ranks[row.id] + 1
    return tuple(sorted(rows, key=lambda row: (
        row.movie_id, row.list_order if row.list_order is not None else ranks[row.id],
        ranks[row.id])))


def delete_subtitle_edit(base: Iterable[SubtitleCue], edits: dict[str, dict],
                         cue_id: str) -> dict[str, dict]:
    base = tuple(base)
    need(cue_id in {r.id for r in apply_subtitle_edits(base, edits, validate=False)},
         f"삭제할 자막이 없습니다: {cue_id}")
    result = copy.deepcopy(edits)
    if cue_id in {r.id for r in base}:
        result[cue_id] = {"deleted": True}
    else:
        result.pop(cue_id)
    return result


def move_subtitle_edit(base: Iterable[SubtitleCue], edits: dict[str, dict],
                       cue_id: str, direction: int) -> dict[str, dict]:
    need(direction in (-1, 1), "자막 이동 방향 오류")
    rows = subtitle_display_rows(apply_subtitle_edits(base, edits, validate=False))
    selected = next((row for row in rows if row.id == cue_id), None)
    need(selected is not None and selected.added, "추가한 자막만 목록에서 이동할 수 있습니다.")
    movie_rows = [row for row in rows if row.movie_id == selected.movie_id]
    index = next(i for i, row in enumerate(movie_rows) if row.id == cue_id)
    target = index + direction
    result = copy.deepcopy(edits)
    if not 0 <= target < len(movie_rows):
        return result
    movie_rows[index], movie_rows[target] = movie_rows[target], movie_rows[index]
    for order, row in enumerate(movie_rows):
        result[row.id] = subtitle_edit_row(replace(row, list_order=order))
    return result


def insert_subtitle_edit(base: Iterable[SubtitleCue], edits: dict[str, dict],
                         added: SubtitleCue, before_id: str | None) -> dict[str, dict]:
    """Insert a new editor row above the selection without retiming existing cues."""
    rows = subtitle_display_rows(apply_subtitle_edits(base, edits, validate=False))
    need(added.added and added.id not in {row.id for row in rows}, "추가 자막 ID 오류")
    movie_rows = [row for row in rows if row.movie_id == added.movie_id]
    index = next((i for i, row in enumerate(movie_rows) if row.id == before_id), len(movie_rows))
    movie_rows.insert(index, added)
    result = copy.deepcopy(edits)
    for order, row in enumerate(movie_rows):
        result[row.id] = subtitle_edit_row(replace(row, list_order=order))
    return result


def next_custom_id(cues: Iterable[SubtitleCue], movie_id: int) -> str:
    prefix = f"movie{movie_id:03d}/cue/custom-"
    used = {
        int(row.id.removeprefix(prefix))
        for row in cues
        if row.id.startswith(prefix) and row.id.removeprefix(prefix).isdigit()
    }
    ordinal = 1
    while ordinal in used:
        ordinal += 1
    return f"{prefix}{ordinal:03d}"


def build_documents(cues: Iterable[SubtitleCue]) -> tuple[list[dict], list[dict]]:
    rows = list(cues)
    validate_subtitle_cues(rows)
    source_titles = {
        int(document["movie_id"]): str(document.get("movie_title") or "")
        for document in _source_documents()
    }
    documents: list[dict] = []
    compiled: list[dict] = []
    # Deleting the last cue must not silently resurrect it or remove the
    # movie directory entry. An empty cue table means no captions for it.
    for movie_id in sorted(source_titles):
        movie_rows = sorted(
            (row for row in rows if row.movie_id == movie_id),
            key=lambda row: (row.start, row.end, row.id),
        )
        cues_out: list[dict] = []
        for row in movie_rows:
            cue = {
                "start": row.start,
                "end": row.end,
                "start_frame": round(row.start * FRAME_RATE),
                "end_frame": round(row.end * FRAME_RATE),
                "movie_id": movie_id,
                "ja": row.ja,
                "ko": list(row.ko),
            }
            if row.speaker:
                cue["speaker"] = row.speaker
            cues_out.append(cue)
            compiled.append(cue)
        documents.append({
            "movie_id": movie_id,
            "movie_title": source_titles.get(movie_id) or f"영상 {movie_id:03d}",
            "frame_rate": FRAME_RATE,
            "cues": cues_out,
        })
    expected = tuple(subtitle_build.data_build.SPOKEN_MOVIE_IDS)
    need(tuple(row["movie_id"] for row in documents) == expected,
         "대사 있는 영상의 자막 목록이 불완전합니다.")
    return documents, compiled


def build_payload(
    cues: Iterable[SubtitleCue], preview_path: Path
) -> tuple[bytes, list[tuple[int, bytes, str]], dict[str, object]]:
    """Compile captions and the matching dual-route resident bootstrap."""
    rows = tuple(cues)
    documents, compiled = build_documents(rows)
    prior = subtitle_build.prior
    data_build = subtitle_build.data_build
    base = prior.base

    old_preview = data_build.PREVIEW
    old_tile = base.TILE_FIRST
    old_refresh = base.REFRESH_ACTIVE_CUE_EVERY_FRAME
    old_hook_ram = base.HOOK_RAM
    old_hook_capacity = base.HOOK_CAPACITY
    old_scratch_ram = base.SCRATCH_RAM
    old_scratch_bitmap_ram = base.SCRATCH_BITMAP_RAM
    old_alias_base = base.DIRECT_RESIDENT_MOVIE_ID_ALIAS_BASE
    old_alias_count = base.DIRECT_RESIDENT_MOVIE_ID_ALIAS_COUNT
    old_special_id = base.DIRECT_RESIDENT_NATURAL_SPECIAL_ID
    old_special_marker_ram = base.DIRECT_RESIDENT_NATURAL_SPECIAL_MARKER_RAM
    old_special_marker_value = base.DIRECT_RESIDENT_NATURAL_SPECIAL_MARKER_VALUE
    old_special_selector_id = base.DIRECT_RESIDENT_NATURAL_SPECIAL_SELECTOR_ID
    old_private_blank_tile = base.DIRECT_RESIDENT_PRIVATE_BLANK_TILE
    old_code_region = prior.CODE_REGION_BYTES
    old_data_ram = prior.DATA_RAM
    data_build.PREVIEW = preview_path
    code_region_bytes = NATURAL_ALIAS_CODE_REGION_BYTES
    prior.CODE_REGION_BYTES = code_region_bytes
    prior.DATA_RAM = prior.TARGET_RAM + code_region_bytes
    base.TILE_FIRST = data_build.SUBTITLE_TILE_FIRST
    base.REFRESH_ACTIVE_CUE_EVERY_FRAME = False
    base.HOOK_RAM = prior.TARGET_RAM
    base.HOOK_CAPACITY = code_region_bytes
    base.SCRATCH_RAM = prior.SCRATCH_RAM
    base.SCRATCH_BITMAP_RAM = prior.SCRATCH_RAM + base.SCRATCH_STRIDE + 1
    base.DIRECT_RESIDENT_MOVIE_ID_ALIAS_BASE = NATURAL_MOVIE_ID_BASE
    base.DIRECT_RESIDENT_MOVIE_ID_ALIAS_COUNT = NATURAL_MOVIE_ID_COUNT
    base.DIRECT_RESIDENT_NATURAL_SPECIAL_ID = (
        NATURAL_SPECIAL_MOVIE_ID if NATURAL_SPECIAL_ROUTE_ENABLED else None
    )
    base.DIRECT_RESIDENT_NATURAL_SPECIAL_MARKER_RAM = (
        NATURAL_SPECIAL_MARKER_RAM if NATURAL_SPECIAL_ROUTE_ENABLED else None
    )
    base.DIRECT_RESIDENT_NATURAL_SPECIAL_MARKER_VALUE = (
        NATURAL_SPECIAL_MARKER_VALUE if NATURAL_SPECIAL_ROUTE_ENABLED else None
    )
    base.DIRECT_RESIDENT_NATURAL_SPECIAL_SELECTOR_ID = (
        NATURAL_SPECIAL_SELECTOR_ID if NATURAL_SPECIAL_ROUTE_ENABLED else None
    )
    # Caption tiles occupy TILE_FIRST..TILE_FIRST+89.  The immediately
    # following tile is inside the already-audited private 0x2C000..0x2D000
    # K-RAM window and is explicitly cleared before BAT activation.  Using it
    # prevents natural playback from exposing a stale field-map tile zero.
    private_blank_tile = (
        base.TILE_FIRST + base.CAPTION_TILE_COLUMNS * base.CAPTION_TILE_ROWS
    )
    base.DIRECT_RESIDENT_PRIVATE_BLANK_TILE = private_blank_tile
    try:
        data, addresses, data_audit = data_build.build_data(
            documents,
            compiled,
            {"R": (prior.DATA_RAM,
                   prior.TARGET_ZERO_CAPACITY - prior.CODE_REGION_BYTES)},
        )
        code, symbols = base.build_code(addresses)
    finally:
        data_build.PREVIEW = old_preview
        base.TILE_FIRST = old_tile
        base.REFRESH_ACTIVE_CUE_EVERY_FRAME = old_refresh
        base.HOOK_RAM = old_hook_ram
        base.HOOK_CAPACITY = old_hook_capacity
        base.SCRATCH_RAM = old_scratch_ram
        base.SCRATCH_BITMAP_RAM = old_scratch_bitmap_ram
        base.DIRECT_RESIDENT_MOVIE_ID_ALIAS_BASE = old_alias_base
        base.DIRECT_RESIDENT_MOVIE_ID_ALIAS_COUNT = old_alias_count
        base.DIRECT_RESIDENT_NATURAL_SPECIAL_ID = old_special_id
        base.DIRECT_RESIDENT_NATURAL_SPECIAL_MARKER_RAM = old_special_marker_ram
        base.DIRECT_RESIDENT_NATURAL_SPECIAL_MARKER_VALUE = old_special_marker_value
        base.DIRECT_RESIDENT_NATURAL_SPECIAL_SELECTOR_ID = old_special_selector_id
        base.DIRECT_RESIDENT_PRIVATE_BLANK_TILE = old_private_blank_tile
        prior.CODE_REGION_BYTES = old_code_region
        prior.DATA_RAM = old_data_ram

    need(len(code) <= code_region_bytes, "자막 실행 코드 영역 초과")
    payload = code.ljust(code_region_bytes, b"\0") + data
    need(len(payload) <= prior.BRAM_FREE_CLUSTER_BYTES,
         f"자막 payload 용량 초과: {len(payload)}/{prior.BRAM_FREE_CLUSTER_BYTES}")
    # RetroArch's 64 KiB .srm retains only the first 32 KiB of PC-FX Card.
    need(prior.BRAM_FILE_OFFSET + len(payload) <= 0x8000,
         "자막 payload가 RetroArch SRM 외부 카드 범위를 넘습니다.")
    signature = struct.unpack_from("<I", payload)[0]
    segment_a, segment_b, bootstrap_symbols = subtitle_bootstrap.build(
        len(payload), signature
    )
    vblank = base.encode_jal(base.VBLANK_CALL_RAM, prior.BOOT_A_RAM)
    patches = [
        (base.VBLANK_CALL_COOKED, vblank, "subtitle/vblank"),
        (prior.BOOT_A_COOKED,
         segment_a.ljust(prior.BOOT_A_CAPACITY, b"\0"),
         "subtitle/bootstrap-a"),
        (prior.BOOT_B_COOKED, segment_b, "subtitle/bootstrap-b"),
    ]

    characters = list(dict.fromkeys(
        character for row in rows for line in row.ko for character in line
    ))
    need(data_audit["resident_font_reuse"] is False,
         "자막이 공용 글꼴을 재사용합니다.")
    need(data_audit["custom_characters"] == len(characters),
         "자막 글리프 전용 소유 수가 문자 수와 다릅니다.")
    return payload, patches, {
        "cue_count": len(rows),
        "movie_count": len(documents),
        "unique_characters": len(characters),
        "unique_private_glyphs": data_audit["custom_characters"],
        "glyph_aliases": 0,
        "resident_font_reuse": False,
        "font_policy": data_audit["font_policy"],
        "payload_bytes": len(payload),
        "payload_signature": f"0x{signature:08X}",
        "movie_id_namespaces": {
            "omake_selector": [0, MOVIE_COUNT - 1],
            "natural_gameplay": [
                NATURAL_MOVIE_ID_BASE,
                NATURAL_MOVIE_ID_BASE + NATURAL_MOVIE_ID_COUNT - 1,
            ],
            "normalization": f"natural_id-{NATURAL_MOVIE_ID_BASE}",
            "ambiguous_natural_route": (
                {
                    "movie_id": NATURAL_SPECIAL_MOVIE_ID,
                    "marker_ram": f"0x{NATURAL_SPECIAL_MARKER_RAM:08X}",
                    "marker_value": f"0x{NATURAL_SPECIAL_MARKER_VALUE:08X}",
                    "normalized_omake_id": NATURAL_SPECIAL_SELECTOR_ID,
                }
                if NATURAL_SPECIAL_ROUTE_ENABLED else None
            ),
            "same_cue_tables": True,
        },
        "bootstrap_symbols": {
            key: f"0x{value:X}" for key, value in bootstrap_symbols.items()
        },
        "renderer_symbols": {
            key: f"0x{value:X}" for key, value in symbols.items()
        },
        "private_bg1_blank_tile": f"0x{private_blank_tile:X}",
        "data": data_audit,
    }


def build_disc_resident_payload(
    cues: Iterable[SubtitleCue],
    preview_path: Path,
    target_ram: int,
    source_ram: int | None = None,
) -> tuple[bytes, list[tuple[int, bytes, str]], dict[str, object]]:
    """Compile captions for direct boot-time disc residency.

    ``build_payload`` normally emits a tiny VBlank bootstrap which copies the
    renderer from an external backup-RAM card.  A physical-console build must
    not depend on an emulator-side save file, so this variant recompiles every
    embedded absolute address for ``target_ram`` and replaces that bootstrap
    with a direct VBlank call.  The caller is responsible for arranging for
    the PC-FX boot loader to place ``payload`` at ``target_ram``.
    """
    prior = subtitle_build.prior
    base = prior.base
    old_target_ram = prior.TARGET_RAM
    try:
        prior.TARGET_RAM = target_ram
        payload, _card_patches, audit = build_payload(cues, preview_path)
    finally:
        prior.TARGET_RAM = old_target_ram

    signature = struct.unpack_from("<I", payload)[0]
    if source_ram is None:
        segment_a, segment_b, bootstrap_symbols = (
            subtitle_bootstrap.build_disc_resident(target_ram, signature)
        )
        delivery_kind = "pcfx-boot-loaded-disc-resident"
    else:
        segment_a, segment_b, bootstrap_symbols = (
            subtitle_bootstrap.build_disc_staged(
                source_ram, target_ram, len(payload), signature
            )
        )
        delivery_kind = "pcfx-disc-staged-on-demand-restore"
    direct_vblank = base.encode_jal(base.VBLANK_CALL_RAM, prior.BOOT_A_RAM)
    patches = [
        (base.VBLANK_CALL_COOKED, direct_vblank, "subtitle/vblank-guarded"),
        (prior.BOOT_A_COOKED,
         segment_a.ljust(prior.BOOT_A_CAPACITY, b"\0"),
         "subtitle/disc-bootstrap-a"),
        (prior.BOOT_B_COOKED, segment_b, "subtitle/disc-bootstrap-b"),
    ]
    audit = dict(audit)
    audit["bootstrap_symbols"] = {
        key: f"0x{value:X}" for key, value in bootstrap_symbols.items()
    }
    audit["delivery"] = {
        "kind": delivery_kind,
        "target_ram": f"0x{target_ram:08X}",
        "source_ram": (
            f"0x{source_ram:08X}" if source_ram is not None else None
        ),
        "external_save_required": False,
        "vblank_call_ram": f"0x{base.VBLANK_CALL_RAM:08X}",
    }
    return payload, patches, audit
