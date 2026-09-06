#!/usr/bin/env python3
"""Unified translation project persistence and safe build wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Callable

import dialogue_core as dialogue
import av_font_core as av_fonts
import condition_core as conditions
import condition_resident
import dialogue_continuation_resident
import missing_presentations
import epilogue_core as epilogues
import narration_core as narrations
import scenario_title_core as scenario_titles
import scenario_header_core as scenario_headers
import subtitle_core as subtitles
import item_core as item_layer
import early_dialogue_font
import title_screen_core as title_screen
import native_dialogue_verification
from native_name_widths import verify_installed_name_widths
import build_r80_full_conditions_successor203 as condition_layer
import build_r80_successor204_resource12_unifont_all_successor205 as resource12_layer


ROOT = Path(__file__).resolve().parents[1]
PROJECT_SCHEMA = "langrisser-fx-translation-editor/v4"
DEFAULT_SAVE_DIR = (
    ROOT
    / "work/modified-save/"
      "r80-successor189-s12-condition-repair-successor190"
)
DEFAULT_SAVE_STEM = (
    "Langrisser-FX-KR-r80-successor189-s12-condition-repair-successor190-user-progress"
)
DEFAULT_SAV = DEFAULT_SAVE_DIR / f"{DEFAULT_SAVE_STEM}.sav"
DEFAULT_FXB = DEFAULT_SAVE_DIR / f"{DEFAULT_SAVE_STEM}.fxb"
FXB_BYTES = 0x20000
LIBRETRO_CARD_BYTES = 0x8000
SRM_BYTES = 0x10000
FAT_OFFSET = 0x80
ROOT_OFFSET = 0x680
ROOT_ENTRIES = 0xFC
ENTRY_SIZE = 0x20
DATA_OFFSET = 0x2600
CLUSTER_SIZE = 0x80
MAX_CLUSTER = 949
SUBTITLE_FILE_NAME = b"SUBTITLEBIN"


@dataclass(frozen=True)
class ProjectData:
    dialogue_edits: dict[str, str]
    subtitle_edits: dict[str, dict]
    narration_edits: dict[str, str]
    condition_edits: dict[str, str]
    epilogue_edits: dict[str, str]


def _validate_dialogue_layout_edits(
    records: list[dialogue.DialogueRecord],
    edits: dict[str, str],
) -> None:
    """Reject text that would leave the dialogue window before persistence.

    Full encoding and aggregate-capacity checks still run during validation and
    build because Scenario 1 needs the pinned base image.  Pixel width and page
    line count do not need that image, so enforce both when a project is saved
    or loaded as well.
    """
    by_id = {row.id: row for row in records}
    unknown = set(edits) - set(by_id)
    dialogue.need(
        not unknown,
        "알 수 없는 대사 ID: " + ", ".join(sorted(unknown)[:5]),
    )
    for record_id, text in edits.items():
        row = by_id[record_id]
        if dialogue.is_portrait_dialogue(row):
            try:
                inspected = dialogue.portrait_layout_inspection(text)
            except ValueError as exc:
                raise dialogue.DialogueError(f"{record_id}: {exc}") from exc
            dialogue.need(
                not inspected["failures"],
                f"{record_id}: 첫 화면 3줄·이후 4줄·168px 규칙 위반: "
                + "; ".join(inspected["failures"]),
            )
        else:
            widths = dialogue.scenario01_menu_condition_line_widths(text)
            dialogue.need(
                len(widths) == 1
                and max(widths, default=0) <= dialogue.MENU_CONDITION_MAX_WIDTH_PX,
                f"{record_id}: 1화 전투 조건 한 줄/176px 규칙 위반",
            )


def sha(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def load_project(
    path: Path,
    records: list[dialogue.DialogueRecord],
) -> ProjectData:
    if not path.is_file():
        return ProjectData({}, {}, {}, {}, {})
    document = dialogue.load_json(path)
    schema = document.get("schema")
    if schema == "langrisser-fx-dialogue-editor/v1":
        return ProjectData(dialogue.load_project(path, records), {}, {}, {}, {})
    dialogue.need(
        schema in ("langrisser-fx-translation-editor/v2", "langrisser-fx-translation-editor/v3", PROJECT_SCHEMA),
        "편집 파일 형식이 다릅니다.",
    )
    known = {row.id for row in records}
    dialogue_edits = document.get("dialogue_edits", {})
    subtitle_edits = document.get("subtitle_edits", {})
    narration_edits = document.get("narration_edits", {})
    condition_edits = document.get("condition_edits", {})
    epilogue_edits = document.get("epilogue_edits", {})
    dialogue.need(isinstance(dialogue_edits, dict),
                  "dialogue_edits 형식이 잘못되었습니다.")
    dialogue.need(isinstance(subtitle_edits, dict),
                  "subtitle_edits 형식이 잘못되었습니다.")
    dialogue.need(isinstance(narration_edits, dict),
                  "narration_edits 형식이 잘못되었습니다.")
    dialogue.need(isinstance(condition_edits, dict),
                  "condition_edits 형식이 잘못되었습니다.")
    dialogue.need(isinstance(epilogue_edits, dict),
                  "epilogue_edits 형식이 잘못되었습니다.")
    unknown = set(dialogue_edits) - known
    dialogue.need(not unknown,
                  "알 수 없는 대사 ID: " + ", ".join(sorted(unknown)[:5]))
    normalized_dialogue = {
        key: str(value) for key, value in dialogue_edits.items()
    }
    normalized_subtitles = {
        str(key): dict(value) for key, value in subtitle_edits.items()
    }
    normalized_narrations = {
        str(key): str(value) for key, value in narration_edits.items()
    }
    normalized_conditions = {
        str(key): str(value) for key, value in condition_edits.items()
    }
    normalized_epilogues = {
        str(key): str(value) for key, value in epilogue_edits.items()
    }
    _validate_dialogue_layout_edits(records, normalized_dialogue)
    subtitles.apply_subtitle_edits(
        subtitles.load_subtitle_cues(), normalized_subtitles
    )
    narrations.validate_narration_project(normalized_narrations)
    conditions.validate_condition_project(normalized_conditions)
    epilogues.validate_epilogue_project(normalized_epilogues)
    return ProjectData(
        normalized_dialogue,
        normalized_subtitles,
        normalized_narrations,
        normalized_conditions,
        normalized_epilogues,
    )


def _trim_subtitle_edits(edits: dict[str, dict]) -> dict[str, dict]:
    base = {row.id: row for row in subtitles.load_subtitle_cues()}
    current = {
        row.id: row
        for row in subtitles.apply_subtitle_edits(base.values(), edits)
    }
    result: dict[str, dict] = {}
    for cue_id in sorted(set(base) - set(current)):
        result[cue_id] = {"deleted": True}
    for cue_id, row in sorted(current.items()):
        original = base.get(cue_id)
        if original is not None and (
            row.start == original.start
            and row.end == original.end
            and row.ja == original.ja
            and row.ko == original.ko
            and row.speaker == original.speaker
            and row.list_order == original.list_order
        ):
            continue
        result[cue_id] = subtitles.subtitle_edit_row(row)
    return result


def save_project(
    path: Path,
    records: list[dialogue.DialogueRecord],
    dialogue_texts: dict[str, str],
    subtitle_edits: dict[str, dict],
    narration_edits: dict[str, str],
    condition_edits: dict[str, str],
    epilogue_edits: dict[str, str],
) -> None:
    base = {row.id: row.base_text for row in records}
    unknown = set(dialogue_texts) - set(base)
    dialogue.need(not unknown,
                  "알 수 없는 대사 ID: " + ", ".join(sorted(unknown)[:5]))
    saved_dialogue = {
        key: value for key, value in sorted(dialogue_texts.items())
        if value != base[key]
    }
    _validate_dialogue_layout_edits(records, saved_dialogue)
    saved_subtitles = _trim_subtitle_edits(subtitle_edits)
    narration_base = {
        row.id: row.base_text for row in narrations.load_narration_records()
    }
    dialogue.need(not (set(narration_edits) - set(narration_base)),
                  "알 수 없는 나레이션 ID")
    saved_narrations = {
        key: value for key, value in sorted(narration_edits.items())
        if value != narration_base[key]
    }
    narrations.validate_narration_project(saved_narrations)
    condition_base = {
        row.id: row.base_text for row in conditions.load_condition_records()
    }
    dialogue.need(not (set(condition_edits) - set(condition_base)),
                  "알 수 없는 승패조건 ID")
    saved_conditions = {
        key: value for key, value in sorted(condition_edits.items())
        if value != condition_base[key]
    }
    conditions.validate_condition_project(saved_conditions)
    epilogue_base = {
        row.id: row.base_text for row in epilogues.load_epilogue_records()
    }
    dialogue.need(not (set(epilogue_edits) - set(epilogue_base)),
                  "알 수 없는 엔딩 후일담 ID")
    saved_epilogues = {
        key: value for key, value in sorted(epilogue_edits.items())
        if value != epilogue_base[key]
    }
    epilogues.validate_epilogue_project(saved_epilogues)
    document = {
        "schema": PROJECT_SCHEMA,
        "base": dialogue.BASE_STEM,
        "base_cooked_sha256": dialogue.BASE_HASHES[dialogue.BASE_COOKED_NAME],
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dialogue_edits": saved_dialogue,
        "subtitle_edits": saved_subtitles,
        "narration_edits": saved_narrations,
        "condition_edits": saved_conditions,
        "epilogue_edits": saved_epilogues,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def validate_project(
    records: list[dialogue.DialogueRecord],
    dialogue_texts: dict[str, str],
    subtitle_edits: dict[str, dict],
    narration_edits: dict[str, str],
    condition_edits: dict[str, str],
    epilogue_edits: dict[str, str],
    base_folder: Path,
    progress: Callable[[str], None] | None = None,
) -> None:
    dialogue.validate_project(records, dialogue_texts, base_folder, progress)
    if progress:
        progress("영상 자막·전용 글리프 검사 중…")
    subtitles.apply_subtitle_edits(
        subtitles.load_subtitle_cues(), subtitle_edits
    )
    if progress:
        progress("나레이션·전용 글리프 검사 중…")
    narrations.validate_narration_project(narration_edits)
    if progress:
        progress("승리·패배조건·전용 글리프 검사 중…")
    conditions.validate_condition_project(condition_edits)
    if progress:
        progress("실제 엔딩 후일담·다섯 복제 표 검사 중…")
    epilogues.validate_epilogue_project(epilogue_edits)


def _fat_get(data: bytes | bytearray, cluster: int) -> int:
    offset = FAT_OFFSET + cluster * 3 // 2
    if cluster & 1:
        return (data[offset] >> 4) | (data[offset + 1] << 4)
    return data[offset] | ((data[offset + 1] & 0x0F) << 8)


def _fat_set(data: bytearray, cluster: int, value: int) -> None:
    dialogue.need(0 <= value <= 0xFFF, "FAT12 값 오류")
    offset = FAT_OFFSET + cluster * 3 // 2
    if cluster & 1:
        data[offset] = (data[offset] & 0x0F) | ((value & 0x0F) << 4)
        data[offset + 1] = (value >> 4) & 0xFF
    else:
        data[offset] = value & 0xFF
        data[offset + 1] = (data[offset + 1] & 0xF0) | ((value >> 8) & 0x0F)


def _cluster_offset(cluster: int) -> int:
    dialogue.need(2 <= cluster <= MAX_CLUSTER, f"외부 카드 클러스터 오류: {cluster}")
    return DATA_OFFSET + (cluster - 2) * CLUSTER_SIZE


def extract_subtitle_payload(source_fxb: Path) -> bytes:
    """Read the single SUBTITLE.BIN payload from a pinned PC-FX card image."""
    source = source_fxb.read_bytes()
    dialogue.need(len(source) == FXB_BYTES and source[3:11] == b"PCFXCard",
                  "기준 .fxb가 PC-FX Card 형식이 아닙니다.")
    entries = [ROOT_OFFSET + index * ENTRY_SIZE for index in range(ROOT_ENTRIES)]
    matches = [offset for offset in entries
               if source[offset:offset + 11] == SUBTITLE_FILE_NAME]
    dialogue.need(len(matches) == 1,
                  "SUBTITLE.BIN 소유 항목이 정확히 하나가 아닙니다.")
    entry = matches[0]
    first = struct.unpack_from("<H", source, entry + 0x1A)[0]
    size = struct.unpack_from("<I", source, entry + 0x1C)[0]
    dialogue.need(first == 2 and _cluster_offset(first) == DATA_OFFSET,
                  "SUBTITLE.BIN이 전용 0x2600 영역을 소유하지 않습니다.")
    payload = bytearray()
    chain: list[int] = []
    current = first
    while current < 0xFF8:
        dialogue.need(current not in chain, "SUBTITLE.BIN FAT 순환")
        chain.append(current)
        start = _cluster_offset(current)
        payload.extend(source[start:start + CLUSTER_SIZE])
        current = _fat_get(source, current)
    required = (size + CLUSTER_SIZE - 1) // CLUSTER_SIZE
    dialogue.need(len(chain) == required,
                  "SUBTITLE.BIN 크기와 FAT 체인이 다릅니다.")
    dialogue.need(len(payload) >= size, "SUBTITLE.BIN payload가 잘렸습니다.")
    return bytes(payload[:size])


def replace_subtitle_payload(source_fxb: Path, payload: bytes) -> tuple[bytes, dict]:
    source = source_fxb.read_bytes()
    dialogue.need(len(source) == FXB_BYTES and source[3:11] == b"PCFXCard",
                  "기준 .fxb가 PC-FX Card 형식이 아닙니다.")
    entries = [ROOT_OFFSET + index * ENTRY_SIZE for index in range(ROOT_ENTRIES)]
    matches = [offset for offset in entries
               if source[offset:offset + 11] == SUBTITLE_FILE_NAME]
    dialogue.need(len(matches) == 1, "SUBTITLE.BIN 소유 항목이 정확히 하나가 아닙니다.")
    entry = matches[0]
    first = struct.unpack_from("<H", source, entry + 0x1A)[0]
    old_size = struct.unpack_from("<I", source, entry + 0x1C)[0]
    dialogue.need(first == 2 and _cluster_offset(first) == DATA_OFFSET,
                  "SUBTITLE.BIN이 전용 0x2600 영역을 소유하지 않습니다.")

    chain: list[int] = []
    current = first
    while current < 0xFF8:
        dialogue.need(current not in chain, "SUBTITLE.BIN FAT 순환")
        chain.append(current)
        current = _fat_get(source, current)
    dialogue.need(bool(chain), "SUBTITLE.BIN FAT 체인이 비었습니다.")
    old_required = (old_size + CLUSTER_SIZE - 1) // CLUSTER_SIZE
    dialogue.need(len(chain) == old_required,
                  "SUBTITLE.BIN 크기와 FAT 체인이 다릅니다.")

    required = (len(payload) + CLUSTER_SIZE - 1) // CLUSTER_SIZE
    dialogue.need(required > 0 and 2 + required - 1 <= MAX_CLUSTER,
                  "새 자막 payload 외부 카드 용량 초과")
    data = bytearray(source)
    for cluster in chain:
        _fat_set(data, cluster, 0)
        start = _cluster_offset(cluster)
        data[start:start + CLUSTER_SIZE] = bytes(CLUSTER_SIZE)
    run = list(range(2, 2 + required))
    occupied = [cluster for cluster in run if _fat_get(data, cluster) != 0]
    dialogue.need(not occupied,
                  f"자막 전용 연속 클러스터를 다른 파일이 사용 중입니다: {occupied[:4]}")
    for index, cluster in enumerate(run):
        _fat_set(data, cluster,
                 run[index + 1] if index + 1 < len(run) else 0xFFF)
        start = _cluster_offset(cluster)
        block = payload[index * CLUSTER_SIZE:(index + 1) * CLUSTER_SIZE]
        data[start:start + CLUSTER_SIZE] = block.ljust(CLUSTER_SIZE, b"\0")
    struct.pack_into("<H", data, entry + 0x1A, run[0])
    struct.pack_into("<I", data, entry + 0x1C, len(payload))
    dialogue.need(bytes(data[DATA_OFFSET:DATA_OFFSET + len(payload)]) == payload,
                  "SUBTITLE.BIN payload 사후 검증 실패")
    owned_clusters = set(chain) | set(run)
    fat_bytes = {
        byte_offset
        for cluster in owned_clusters
        for byte_offset in (
            FAT_OFFSET + cluster * 3 // 2,
            FAT_OFFSET + cluster * 3 // 2 + 1,
        )
    }
    owned_data_start = min(_cluster_offset(cluster)
                           for cluster in owned_clusters)
    owned_data_end = max(_cluster_offset(cluster) + CLUSTER_SIZE
                         for cluster in owned_clusters)
    changed = [index for index, (old, new) in enumerate(zip(source, data))
               if old != new]
    outside = [
        index for index in changed
        if not (
            index in fat_bytes
            or entry <= index < entry + ENTRY_SIZE
            or owned_data_start <= index < owned_data_end
        )
    ]
    dialogue.need(not outside,
                  f"SUBTITLE.BIN 소유 범위 밖 외부 카드 변경: {outside[:8]}")
    other_entries = [offset for offset in entries if offset != entry]
    dialogue.need(all(
        source[offset:offset + ENTRY_SIZE] == data[offset:offset + ENTRY_SIZE]
        for offset in other_entries
    ), "다른 외부 카드 디렉터리 항목이 변경되었습니다.")
    return bytes(data), {
        "source_sha256": sha(source),
        "output_sha256": sha(data),
        "directory_entry_offset": f"0x{entry:X}",
        "first_cluster": run[0],
        "last_cluster": run[-1],
        "cluster_count": len(run),
        "old_payload_bytes": old_size,
        "new_payload_bytes": len(payload),
        "payload_sha256": sha(payload),
        "changed_bytes": len(changed),
        "changes_outside_owned_ranges": 0,
        "preserved_other_directory_entries": ROOT_ENTRIES - 1,
        "aliases": 0,
    }


def _copy_base_disc(base_folder: Path, output_folder: Path) -> Path:
    cooked, raw, cue = dialogue.verify_base_folder(base_folder)
    output_folder.mkdir(parents=True)
    stem = output_folder.name
    cooked_out = output_folder / f"track02-{stem}.iso"
    raw_out = output_folder / f"Track-2.{stem}.bin"
    cue_out = output_folder / f"Langrisser-FX-KR-{stem}.cue"
    shutil.copyfile(cooked, cooked_out)
    shutil.copyfile(raw, raw_out)
    for name in ("Track-1.bin", "Track-3.bin"):
        shutil.copyfile(base_folder / name, output_folder / name)
    cue_out.write_text(
        cue.read_text(encoding="ascii").replace(raw.name, raw_out.name),
        encoding="ascii",
        newline="",
    )
    return cue_out


def _repair_existing_raw(cooked: Path, raw: Path, sectors: list[int]) -> None:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{raw.stem}-", suffix=".tmp", dir=raw.parent
    )
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.unlink()
        dialogue._repair_raw(cooked, raw, temporary, sectors)
        os.replace(temporary, raw)
    finally:
        temporary.unlink(missing_ok=True)


def _write_mednafen_subtitle_launcher(
    output_folder: Path,
    cue: Path,
    sav: Path,
    fxb: Path,
) -> tuple[Path, Path]:
    """Emit a one-click Mednafen route that installs the paired PC-FX card."""
    ps1 = output_folder / "PLAYTEST-WITH-SUBTITLES.ps1"
    cmd = output_folder / "PLAYTEST-WITH-SUBTITLES.cmd"
    script = r'''[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$codex = Split-Path -Parent $repo
$emulatorDirectory = Join-Path $codex 'tools\mednafen-1.32.1-win64'
$emulator = Join-Path $emulatorDirectory 'mednafen.exe'
$config = Join-Path $emulatorDirectory 'mednafen.cfg'
$biosSource = Join-Path $codex 'bios\pcfx.rom'
$cue = Join-Path $PSScriptRoot '__CUE__'
$savSource = Join-Path $PSScriptRoot '__SAV__'
$fxbSource = Join-Path $PSScriptRoot '__FXB__'
$runtime = Join-Path $PSScriptRoot '_playtest-runtime'
$saveDirectory = Join-Path $runtime 'sav'
$firmwareDirectory = Join-Path $runtime 'firmware'
foreach ($path in @($emulator,$config,$biosSource,$cue,$savSource,$fxbSource)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing: $path" }
}
foreach ($path in @($runtime,$saveDirectory,$firmwareDirectory)) {
    [IO.Directory]::CreateDirectory($path) | Out-Null
}
Copy-Item -LiteralPath $config -Destination (Join-Path $runtime 'mednafen.cfg') -Force
$bios = Join-Path $firmwareDirectory 'pcfx.rom'
Copy-Item -LiteralPath $biosSource -Destination $bios -Force
$cueStem = [IO.Path]::GetFileNameWithoutExtension($cue)
$card = @(Get-ChildItem -LiteralPath $saveDirectory -Filter "$cueStem.*.fxb" -File)
if ($card.Count -eq 0) {
    $prior = $env:MEDNAFEN_HOME
    $probe = $null
    try {
        $env:MEDNAFEN_HOME = $runtime
        $probe = Start-Process -FilePath $emulator -ArgumentList @(
            '-video.driver','softfb','-pcfx.bios',$bios,
            '-pcfx.rainbow.chromaip','0','-pcfx.videoip','0',
            '-pcfx.shader','none','-pcfx.special','none',$cue
        ) -WorkingDirectory $emulatorDirectory -PassThru -WindowStyle Hidden
    } finally {
        if ($null -eq $prior) { Remove-Item Env:MEDNAFEN_HOME -ErrorAction SilentlyContinue }
        else { $env:MEDNAFEN_HOME = $prior }
    }
    Start-Sleep -Seconds 7
    $probe.Refresh()
    if (-not $probe.HasExited) { Stop-Process -Id $probe.Id -Force; $probe.WaitForExit() }
    $card = @(Get-ChildItem -LiteralPath $saveDirectory -Filter "$cueStem.*.fxb" -File)
}
if ($card.Count -ne 1) { throw "Could not resolve Mednafen PC-FX save identity: $($card.Count)" }
$suffix = $card[0].BaseName.Substring($cueStem.Length)
$internal = Join-Path $saveDirectory "$cueStem$suffix.sav"
$marker = Join-Path $runtime 'subtitle-card-installed.txt'
if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
    Copy-Item -LiteralPath $fxbSource -Destination $card[0].FullName -Force
    Copy-Item -LiteralPath $savSource -Destination $internal -Force
    @(
        (Get-FileHash -Algorithm SHA256 -LiteralPath $fxbSource).Hash,
        (Get-FileHash -Algorithm SHA256 -LiteralPath $savSource).Hash
    ) | Set-Content -LiteralPath $marker -Encoding ASCII
}
$prior = $env:MEDNAFEN_HOME
try {
    $env:MEDNAFEN_HOME = $runtime
    Start-Process -FilePath $emulator -ArgumentList @(
        '-video.driver','softfb','-pcfx.bios',$bios,
        '-pcfx.rainbow.chromaip','0','-pcfx.videoip','0',
        '-pcfx.shader','none','-pcfx.special','none',$cue
    ) -WorkingDirectory $emulatorDirectory -WindowStyle Normal
} finally {
    if ($null -eq $prior) { Remove-Item Env:MEDNAFEN_HOME -ErrorAction SilentlyContinue }
    else { $env:MEDNAFEN_HOME = $prior }
}
'''
    script = (script.replace("__CUE__", cue.name)
                    .replace("__SAV__", sav.name)
                    .replace("__FXB__", fxb.name))
    ps1.write_text(script, encoding="utf-8-sig", newline="\r\n")
    cmd.write_text(
        '@echo off\r\n'
        'powershell.exe -NoProfile -ExecutionPolicy Bypass '
        '-File "%~dp0PLAYTEST-WITH-SUBTITLES.ps1"\r\n'
        'if errorlevel 1 pause\r\n',
        encoding="ascii",
        newline="",
    )
    return ps1, cmd


def build_disc(
    records: list[dialogue.DialogueRecord],
    dialogue_texts: dict[str, str],
    subtitle_edits: dict[str, dict],
    narration_edits: dict[str, str],
    condition_edits: dict[str, str],
    epilogue_edits: dict[str, str],
    base_folder: Path,
    output_folder: Path,
    progress: Callable[[str], None] | None = None,
) -> Path:
    dialogue_base = {row.id: row.base_text for row in records}
    dialogue.need(
        not (set(dialogue_texts) - set(dialogue_base)),
        "알 수 없는 대사 ID가 빌드 입력에 있습니다.",
    )
    adopted_dialogue = {
        row.id: row.base_text for row in records
        if row.base_text != dialogue.installed_text(row)
    }
    user_edited_dialogue = {
        record_id: text for record_id, text in dialogue_texts.items()
        if text != dialogue_base[record_id]
    }
    changed_dialogue = [
        row for row in records
        if dialogue_texts.get(row.id, row.base_text)
        != dialogue.installed_text(row)
    ]
    trimmed_subtitles = _trim_subtitle_edits(subtitle_edits)
    adopted_subtitles = tuple(subtitles.load_subtitle_cues())
    narration_records = narrations.load_narration_records()
    narration_base = {
        row.id: row.base_text for row in narration_records
    }
    adopted_narrations = {
        row.id: row.base_text for row in narration_records
        if row.base_text != row.disc_text
    }
    trimmed_narrations = {
        key: value for key, value in sorted(narration_edits.items())
        if value != narration_base.get(key)
    }
    narrations.validate_narration_project(trimmed_narrations)
    condition_base = {
        row.id: row.base_text for row in conditions.load_condition_records()
    }
    trimmed_conditions = {
        key: value for key, value in sorted(condition_edits.items())
        if value != condition_base.get(key)
    }
    conditions.validate_condition_project(trimmed_conditions)
    epilogue_base = {
        row.id: row.base_text for row in epilogues.load_epilogue_records()
    }
    trimmed_epilogues = {
        key: value for key, value in sorted(epilogue_edits.items())
        if value != epilogue_base.get(key)
    }
    epilogues.validate_epilogue_project(trimmed_epilogues)
    dialogue.need(bool(changed_dialogue or adopted_subtitles
                       or adopted_narrations or trimmed_narrations
                       or trimmed_conditions
                       or trimmed_epilogues),
                  "수정된 대사·영상 자막·나레이션·승패조건·후일담이 없습니다.")
    dialogue.need(not output_folder.exists(),
                  "출력 폴더가 이미 있습니다. 새 폴더를 지정하세요.")

    # Compile the adopted whole-image replacement before creating any output.
    # Its single expected write is verified against the immutable input, not
    # inferred from an already patched title or an emulator checkpoint.
    title_stream, title_preview, title_screen_audit = title_screen.compile_asset()
    with (base_folder / dialogue.BASE_COOKED_NAME).open('rb') as source_file:
        title_base_image = source_file.read()
    title_screen_writes = title_screen.plan_writes(title_base_image, title_stream)
    del title_base_image

    if changed_dialogue:
        cue_out = dialogue.build_disc(
            records, dialogue_texts, base_folder, output_folder, progress
        )
    else:
        if progress:
            progress("successor190 기준 디스크 복사 중…")
        cue_out = _copy_base_disc(base_folder, output_folder)

    stem = output_folder.name
    cooked_out = output_folder / f"track02-{stem}.iso"
    raw_out = output_folder / f"Track-2.{stem}.bin"
    item_audit: dict[str, object] | None = None
    subtitle_audit: dict[str, object] | None = None
    narration_audit: dict[str, object] | None = None
    condition_audit: dict[str, object] | None = None
    epilogue_audit: dict[str, object] | None = None
    resource12_unifont_audit: dict[str, object] | None = None
    av_unifont_audit: dict[str, object] | None = None

    # Item names/tooltips and their Resource-12 ownership are reviewed product
    # inputs, not optional user edits.  Rebuild them on every editor output so
    # a no-touch project cannot silently fall back to successor190 data.
    if progress:
        progress("전체 아이템 이름·설명·전용 글리프 생성 중…")
    item_layer.verify_sources()
    items, item_names, item_lines = item_layer.load_inputs()
    item_mapping, ownership_audit = item_layer.mapping_and_ownership(
        item_lines, item_names
    )
    item_rows = item_layer.geometry()
    if adopted_narrations or trimmed_narrations:
        if progress:
            progress("전체 시나리오·연출 나레이션 영역 생성 중…")
        image = bytearray(cooked_out.read_bytes())
        patches, compile_audit = narrations.build_narration_patches(
            image, trimmed_narrations
        )
        changed_offsets: set[int] = set()
        patch_rows: list[dict[str, object]] = []
        for offset, replacement, patch_id in patches:
            before = bytes(image[offset:offset + len(replacement)])
            dialogue.need(len(before) == len(replacement),
                          f"{patch_id}: 이미지 범위 초과")
            image[offset:offset + len(replacement)] = replacement
            changed = [
                offset + index for index, (old, new)
                in enumerate(zip(before, replacement)) if old != new
            ]
            changed_offsets.update(changed)
            patch_rows.append({
                "id": patch_id,
                "offset": f"0x{offset:08X}",
                "owned_bytes": len(replacement),
                "changed_bytes": len(changed),
                "changes_outside_owned_range": 0,
            })
        dialogue.need(bool(changed_offsets),
                      "나레이션 수정이 실제 바이트 변경을 만들지 않았습니다.")
        cooked_out.write_bytes(image)
        sectors = sorted({offset // dialogue.COOKED_SECTOR
                          for offset in changed_offsets})
        if sectors:
            _repair_existing_raw(cooked_out, raw_out, sectors)
        narration_audit = {
            "compile": compile_audit,
            "patches": patch_rows,
            "changed_cooked_bytes": len(changed_offsets),
            "changed_cooked_sectors": sectors,
            "changes_outside_owned_ranges": 0,
            "glyph_aliases": 0,
        }

    # Match the proven product lineage: dialogue+narration first, then the
    # complete source-faithful item layer.  Applying items earlier lets the
    # narration aggregate compiler restore older neighboring bytes.
    if progress:
        progress("나레이션 이후 아이템 복제 영역 최종 고정 중…")
    image = bytearray(cooked_out.read_bytes())
    item_reapply_source = bytes(image)
    item_reapply_font, item_reapply_font_audit = (
        item_layer.resource12_font_writes(item_reapply_source)
    )
    item_reapply_pools, item_reapply_pool_audit = item_layer.plan_writes(
        item_reapply_source, item_names, item_lines, item_mapping, item_rows
    )
    item_reapply_writes = [*item_reapply_font, *item_reapply_pools]
    item_layer.validate_writes(item_reapply_source, item_reapply_writes)
    item_reapply_offsets: set[int] = set()
    item_reapply_rows: list[dict[str, object]] = []
    for write in sorted(item_reapply_writes,
                        key=lambda row: int(row["offset"])):
        offset = int(write["offset"])
        before = bytes(image[offset:offset + len(write["replacement"])])
        replacement = bytes(write["replacement"])
        dialogue.need(before == bytes(write["expected"]),
                      f"{write['id']}: 아이템 재적용 기준 바이트 변경")
        image[offset:offset + len(replacement)] = replacement
        changed = [
            offset + index for index, (old, new)
            in enumerate(zip(before, replacement)) if old != new
        ]
        item_reapply_offsets.update(changed)
        if changed:
            item_reapply_rows.append({
                "id": str(write["id"]),
                "offset": f"0x{offset:08X}",
                "owned_bytes": len(replacement),
                "changed_bytes": len(changed),
                "changes_outside_owned_range": 0,
            })
    if item_reapply_offsets:
        cooked_out.write_bytes(image)
        item_reapply_sectors = sorted({
            offset // dialogue.COOKED_SECTOR for offset in item_reapply_offsets
        })
        _repair_existing_raw(cooked_out, raw_out, item_reapply_sectors)
    else:
        item_reapply_sectors = []
    dialogue.need(item_reapply_offsets,
                  "아이템 기본 번역이 실제 바이트 변경을 만들지 않았습니다.")
    item_audit = {
        "items": len(items),
        "names": len(item_names),
        "tooltip_rows": len(item_lines),
        "ownership": ownership_audit,
        "font": item_reapply_font_audit,
        "pools": item_reapply_pool_audit,
        "patches": item_reapply_rows,
        "changed_cooked_bytes": len(item_reapply_offsets),
        "changed_cooked_sectors": item_reapply_sectors,
        "changes_outside_owned_ranges": 0,
    }

    # Conditions follow items in successor203.  Install the dedicated renderer,
    # seven unique glyphs, adopted repairs, and any user edits in one pass that
    # preserves the current non-condition presentation frames.
    if condition_base:
        if progress:
            progress("승리·패배조건 전용 렌더러·글리프·프레임 생성 중…")
        image = bytearray(cooked_out.read_bytes())
        condition_source = bytes(image)
        condition_tail_writes, layer_audit = (
            condition_layer.plan_writes(condition_source, trimmed_conditions)
        )
        condition_layer.validate_writes(
            condition_source, condition_tail_writes
        )
        tail_changed_offsets: set[int] = set()
        tail_patch_rows: list[dict[str, object]] = []
        for write in sorted(condition_tail_writes,
                            key=lambda row: int(row["offset"])):
            offset = int(write["offset"])
            before = bytes(image[offset:offset + len(write["replacement"])])
            replacement = bytes(write["replacement"])
            dialogue.need(before == bytes(write["expected"]),
                          f"{write['id']}: 조건 꼬리 기준 바이트 변경")
            image[offset:offset + len(replacement)] = replacement
            changed = [
                offset + index for index, (old, new)
                in enumerate(zip(before, replacement)) if old != new
            ]
            tail_changed_offsets.update(changed)
            tail_patch_rows.append({
                "id": str(write["id"]),
                "offset": f"0x{offset:08X}",
                "owned_bytes": len(replacement),
                "changed_bytes": len(changed),
                "changes_outside_owned_range": 0,
            })
        if tail_changed_offsets:
            cooked_out.write_bytes(image)
            tail_sectors = sorted({
                offset // dialogue.COOKED_SECTOR
                for offset in tail_changed_offsets
            })
            _repair_existing_raw(cooked_out, raw_out, tail_sectors)
        else:
            tail_sectors = []
        dialogue.need(tail_changed_offsets,
                      "승패조건 기본 렌더러가 실제 변경을 만들지 않았습니다.")
        condition_audit = {
            "compile": layer_audit["conditions"],
            "patches": tail_patch_rows,
            "changed_cooked_bytes": len(tail_changed_offsets),
            "changed_cooked_sectors": tail_sectors,
            "non_condition_frames_preserved": True,
            "changes_outside_owned_ranges": 0,
            "glyph_aliases": 0,
            "scenario02_condition_body_exclusive_code_reuse": 0,
            "renderer": {
                key: value for key, value in layer_audit.items()
                if key != "conditions"
            },
        }
    # Recompute the native title row's complete visible advance, including
    # the old leading 05. Preserve every other frame and the numbered header.
    title_source = bytes(image)
    title_writes, title_rows = scenario_titles.plan_writes(title_source)
    condition_layer.validate_writes(title_source, title_writes)
    title_changed_offsets: set[int] = set()
    for write in title_writes:
        offset = int(write["offset"])
        before, after = bytes(write["expected"]), bytes(write["replacement"])
        dialogue.need(bytes(image[offset:offset + len(before)]) == before,
                      f"{write['id']}: 제목 쓰기 기준 바이트 변경")
        image[offset:offset + len(after)] = after
        title_changed_offsets.update(offset + index for index, (a, b)
                                     in enumerate(zip(before, after)) if a != b)
    title_sectors = sorted({offset // dialogue.COOKED_SECTOR for offset in title_changed_offsets})
    if title_changed_offsets:
        cooked_out.write_bytes(image)
        _repair_existing_raw(cooked_out, raw_out, title_sectors)
    title_audit = {"rows": title_rows, "changed_bytes": len(title_changed_offsets),
                   "changed_sectors": title_sectors, "numbered_header_preserved": True,
                   "non_title_frames_preserved": True}

    # Independent owner for the SCENARIO-number row; captions stay untouched.
    header_source = bytes(image)
    header_writes, header_rows = scenario_headers.plan_writes(header_source)
    condition_layer.validate_writes(header_source, header_writes)
    header_changed_offsets = set()
    for write in header_writes:
        offset = int(write["offset"])
        before, after = bytes(write["expected"]), bytes(write["replacement"])
        dialogue.need(bytes(image[offset:offset + len(before)]) == before,
                      f"{write['id']}: 번호 정렬 쓰기 기준 변경")
        image[offset:offset + len(after)] = after
        header_changed_offsets.update(offset + i for i, (a, b)
                                      in enumerate(zip(before, after)) if a != b)
    header_sectors = sorted({offset // dialogue.COOKED_SECTOR for offset in header_changed_offsets})
    if header_changed_offsets:
        cooked_out.write_bytes(image)
        _repair_existing_raw(cooked_out, raw_out, header_sectors)
    header_audit = {"rows": header_rows, "changed_bytes": len(header_changed_offsets),
                    "changed_sectors": header_sectors, "captions_preserved": True,
                    "non_title_frames_preserved": True}

    # The 134 reviewed ending-character epilogues are also adopted defaults.
    # Compile all five physical copies even when the user made no edit.
    if epilogue_base:
        if progress:
            progress("실제 엔딩 후일담 다섯 복제 표 생성 중…")
        image = bytearray(cooked_out.read_bytes())
        patches, compile_audit = epilogues.build_epilogue_patches(
            image, trimmed_epilogues
        )
        changed_offsets: set[int] = set()
        patch_rows: list[dict[str, object]] = []
        for offset, replacement, patch_id in patches:
            before = bytes(image[offset:offset + len(replacement)])
            dialogue.need(len(before) == len(replacement),
                          f"{patch_id}: 이미지 범위 초과")
            image[offset:offset + len(replacement)] = replacement
            changed = [
                offset + index for index, (old, new)
                in enumerate(zip(before, replacement)) if old != new
            ]
            dialogue.need(changed, f"{patch_id}: 빈 후일담 수정")
            changed_offsets.update(changed)
            patch_rows.append({
                "id": patch_id,
                "offset": f"0x{offset:08X}",
                "owned_bytes": len(replacement),
                "changed_bytes": len(changed),
                "changes_outside_owned_range": 0,
            })
        dialogue.need(
            len({
                bytes(image[offset:offset + epilogues.TABLE_BYTES])
                for offset in epilogues.TABLE_OFFSETS
            }) == 1,
            "엔딩 후일담 다섯 복제 표 불일치",
        )
        dialogue.need(
            len({
                bytes(image[
                    offset:offset + epilogues.DICTIONARY_BYTES
                ])
                for offset in epilogues.DICTIONARY_OFFSETS
            }) == 1,
            "엔딩 후일담 다섯 복제 사전 불일치",
        )
        cooked_out.write_bytes(image)
        sectors = sorted({offset // dialogue.COOKED_SECTOR
                          for offset in changed_offsets})
        if sectors:
            _repair_existing_raw(cooked_out, raw_out, sectors)
        epilogue_audit = {
            "compile": compile_audit,
            "patches": patch_rows,
            "changed_cooked_bytes": len(changed_offsets),
            "changed_cooked_sectors": sectors,
            "five_physical_copies_identical": True,
            "changes_outside_owned_ranges": 0,
            "glyph_aliases": 0,
        }
    # The reviewed subtitle JSON files are adopted product inputs, just like
    # the reviewed narration defaults.  They must be compiled even when the
    # user has not changed a cue in the editor.  Earlier builds gated this
    # block on ``trimmed_subtitles`` and could therefore emit a new BIN/CUE
    # without the matching SUBTITLE.BIN/SRM, leaving natural playback on an
    # older route table while Omake happened to work.
    if adopted_subtitles:
        if progress:
            progress("전용 12x12 영상 자막 payload 생성 중…")
        current_cues = subtitles.apply_subtitle_edits(
            adopted_subtitles, trimmed_subtitles
        )
        preview = output_folder / "movie-subtitle-preview.png"
        payload, patches, compile_audit = subtitles.build_payload(
            current_cues, preview
        )
        image = bytearray(cooked_out.read_bytes())
        changed_offsets: set[int] = set()
        patch_audit: list[dict[str, object]] = []
        for offset, replacement, patch_id in patches:
            before = bytes(image[offset:offset + len(replacement)])
            dialogue.need(len(before) == len(replacement),
                          f"{patch_id}: 이미지 범위 초과")
            image[offset:offset + len(replacement)] = replacement
            changed = [offset + index for index, (old, new)
                       in enumerate(zip(before, replacement)) if old != new]
            changed_offsets.update(changed)
            patch_audit.append({
                "id": patch_id,
                "offset": f"0x{offset:08X}",
                "bytes": len(replacement),
                "changed_bytes": len(changed),
                "before_sha256": sha(before),
                "after_sha256": sha(replacement),
            })
        cooked_out.write_bytes(image)
        sectors = sorted({offset // dialogue.COOKED_SECTOR
                          for offset in changed_offsets})
        if sectors:
            if progress:
                progress(f"영상 자막 MODE1 섹터 복구 중… {len(sectors)}개")
            _repair_existing_raw(cooked_out, raw_out, sectors)
        payload_path = output_folder / "subtitle-payload.bin"
        payload_path.write_bytes(payload)

        dialogue.need(DEFAULT_SAV.is_file() and DEFAULT_FXB.is_file(),
                      "기본 SRM/FXB 자료가 없습니다.")
        sav_out = output_folder / f"{stem}.sav"
        fxb_out = output_folder / f"{stem}.fxb"
        srm_out = output_folder / f"{stem}.srm"
        shutil.copyfile(DEFAULT_SAV, sav_out)
        fxb, fxb_audit = replace_subtitle_payload(DEFAULT_FXB, payload)
        fxb_out.write_bytes(fxb)
        sav = sav_out.read_bytes()
        dialogue.need(len(sav) == 0x8000 and sav[3:11] == b"PCFXSram",
                      "기준 내부 세이브 형식 오류")
        dialogue.need(not any(fxb[LIBRETRO_CARD_BYTES:]),
                      "외부 카드 32 KiB 이후 자료는 SRM으로 보존할 수 없습니다.")
        srm = sav + fxb[:LIBRETRO_CARD_BYTES]
        dialogue.need(len(srm) == SRM_BYTES,
                      "RetroArch SRM 크기 오류")
        srm_out.write_bytes(srm)
        # Frontends such as RetroArch discover SRAM from the launched CUE's
        # basename.  The historical editor emitted only ``<folder>.srm``
        # while the CUE is named ``Langrisser-FX-KR-<folder>.cue``; launching
        # the CUE therefore silently omitted the external subtitle card.
        # Keep the short legacy files used by QA tools and add exact CUE-name
        # companions as explicit frontend compatibility views.
        cue_sav_out = output_folder / f"{cue_out.stem}.sav"
        cue_fxb_out = output_folder / f"{cue_out.stem}.fxb"
        cue_srm_out = output_folder / f"{cue_out.stem}.srm"
        cue_sav_out.write_bytes(sav)
        cue_fxb_out.write_bytes(fxb)
        cue_srm_out.write_bytes(srm)
        launcher_ps1, launcher_cmd = _write_mednafen_subtitle_launcher(
            output_folder, cue_out, sav_out, fxb_out
        )
        subtitle_audit = {
            "compile": compile_audit,
            "patches": patch_audit,
            "changed_cooked_bytes": len(changed_offsets),
            "changed_cooked_sectors": sectors,
            "payload": {"path": payload_path.name,
                        "sha256": sha(payload)},
            "paired_save": {
                "sav": {"path": sav_out.name, "sha256": sha(sav)},
                "fxb": {"path": fxb_out.name, "sha256": sha(fxb),
                        "filesystem": fxb_audit},
                "srm": {"path": srm_out.name, "sha256": sha(srm)},
            },
            "cue_basename_save": {
                "sav": {"path": cue_sav_out.name, "sha256": sha(sav)},
                "fxb": {"path": cue_fxb_out.name, "sha256": sha(fxb)},
                "srm": {"path": cue_srm_out.name, "sha256": sha(srm)},
                "purpose": "automatic frontend pairing with launched CUE",
            },
            "mednafen_launcher": {
                "cmd": {"path": launcher_cmd.name,
                        "sha256": dialogue.sha256_file(launcher_cmd)},
                "ps1": {"path": launcher_ps1.name,
                        "sha256": dialogue.sha256_file(launcher_ps1)},
                "purpose": "discover Mednafen layout id and install paired SAV/FXB",
            },
        }

    # Finish with a renderer-wide normalization of every Resource-12 Hangul
    # cell, including battle explanations and command/menu text not present in
    # the item corpus.  Only the proven atlas spans are writable here.
    if progress:
        progress("공용 12x12 글꼴 전체 규칙 통일 중…")
    image = bytearray(cooked_out.read_bytes())
    resource12_source = bytes(image)
    resource12_rows, resource12_bank = resource12_layer.rows_and_bank()
    resource12_writes, resource12_plan_audit = (
        resource12_layer.planned_writes(resource12_source, resource12_bank)
    )
    resource12_changed_offsets: set[int] = set()
    resource12_patch_rows: list[dict[str, object]] = []
    for write in sorted(resource12_writes,
                        key=lambda row: int(row["offset"])):
        offset = int(write["offset"])
        expected = bytes(write["expected"])
        replacement = bytes(write["replacement"])
        before = bytes(image[offset:offset + len(replacement)])
        dialogue.need(before == expected,
                      f"{write['id']}: 공용 글꼴 기준 바이트 변경")
        image[offset:offset + len(replacement)] = replacement
        changed = [
            offset + index for index, (old, new)
            in enumerate(zip(before, replacement)) if old != new
        ]
        resource12_changed_offsets.update(changed)
        resource12_patch_rows.append({
            "id": str(write["id"]),
            "offset": f"0x{offset:08X}",
            "owned_bytes": len(replacement),
            "changed_bytes": len(changed),
            "changes_outside_owned_range": 0,
        })
    dialogue.need(resource12_changed_offsets,
                  "공용 12x12 글꼴 정규화가 실제 변경을 만들지 않았습니다.")
    cooked_out.write_bytes(image)
    resource12_sectors = sorted({
        offset // dialogue.COOKED_SECTOR
        for offset in resource12_changed_offsets
    })
    _repair_existing_raw(cooked_out, raw_out, resource12_sectors)
    resource12_unifont_audit = {
        **resource12_plan_audit,
        "physical_cells_verified": (
            len(resource12_rows) * len(resource12_writes)
        ),
        "all_target_rasters_gnu_unifont_exact": True,
        "patches": resource12_patch_rows,
        "changed_cooked_bytes": len(resource12_changed_offsets),
        "changed_cooked_sectors": resource12_sectors,
        "changes_outside_owned_ranges": 0,
    }

    # The four append-only AV/menu cells were originally drawn from a PC-98
    # BDF and therefore did not match the project's 12x12 rule.  They live
    # outside Resource-12, so normalize this dedicated bank separately on
    # every editor build.
    if progress:
        progress("배경음·오프닝·증원·상점 글꼴 규칙 통일 중…")
    image = bytearray(cooked_out.read_bytes())
    av_writes, av_plan_audit = av_fonts.planned_writes(bytes(image))
    av_changed_offsets: set[int] = set()
    av_patch_rows: list[dict[str, object]] = []
    for write in av_writes:
        offset = int(write["offset"])
        expected = bytes(write["expected"])
        replacement = bytes(write["replacement"])
        before = bytes(image[offset:offset + len(replacement)])
        dialogue.need(before == expected,
                      f"{write['id']}: AV 전용 글꼴 기준 바이트 변경")
        image[offset:offset + len(replacement)] = replacement
        changed = [
            offset + index for index, (old, new)
            in enumerate(zip(before, replacement)) if old != new
        ]
        av_changed_offsets.update(changed)
        av_patch_rows.append({
            "id": str(write["id"]),
            "offset": f"0x{offset:08X}",
            "owned_bytes": len(replacement),
            "changed_bytes": len(changed),
            "changes_outside_owned_range": 0,
        })
    if av_changed_offsets:
        cooked_out.write_bytes(image)
        av_sectors = sorted({
            offset // dialogue.COOKED_SECTOR
            for offset in av_changed_offsets
        })
        _repair_existing_raw(cooked_out, raw_out, av_sectors)
    else:
        av_sectors = []
    av_unifont_audit = {
        **av_plan_audit,
        "patches": av_patch_rows,
        "changed_cooked_bytes": len(av_changed_offsets),
        "changed_cooked_sectors": av_sectors,
        "changes_outside_owned_ranges": 0,
    }

    # Keep the condition extension in the same loaded Resource-12 header as
    # the native router; successor236's low-bank runtime route was absent.
    if progress:
        progress("조건 글자 처리의 실제 로드 경로 검사 중…")
    resident_source = bytes(image)
    resident_writes, resident_plan = condition_resident.plan_writes(resident_source)
    condition_layer.validate_writes(resident_source, resident_writes)
    resident_offsets = set()
    for write in resident_writes:
        start = int(write['offset'])
        replacement = bytes(write['replacement'])
        before = bytes(image[start:start+len(replacement)])
        dialogue.need(before == bytes(write['expected']),
                      f"{write['id']}: 조건 상주 영역 기준 변경")
        image[start:start+len(replacement)] = replacement
        resident_offsets.update(start+i for i,(a,b) in enumerate(zip(before,replacement)) if a!=b)
    cooked_out.write_bytes(image)
    _repair_existing_raw(cooked_out,raw_out,sorted({i//dialogue.COOKED_SECTOR for i in resident_offsets}))

    # Install the ordinary-dialogue 0A visual continuation only after every
    # Resource-12 atlas/header writer. It occupies the registered final 0x200
    # bytes of every full replica and preserves native 06 voice pages.
    if progress:
        progress("긴 대사 시각 전용 페이지 처리 설치 중…")
    continuation_source = bytes(image)
    continuation_writes, continuation_plan = (
        dialogue_continuation_resident.plan_writes(continuation_source)
    )
    condition_layer.validate_writes(continuation_source, continuation_writes)
    continuation_offsets = set()
    for write in continuation_writes:
        start = int(write["offset"])
        before = bytes(image[start:start + len(write["replacement"])])
        replacement = bytes(write["replacement"])
        dialogue.need(before == bytes(write["expected"]),
                      f"{write['id']}: 시각 전용 페이지 기준 변경")
        image[start:start + len(replacement)] = replacement
        continuation_offsets.update(
            start + index for index, (old, new)
            in enumerate(zip(before, replacement)) if old != new
        )
    dialogue.need(continuation_offsets,
                  "시각 전용 페이지 설치가 실제 변경을 만들지 않았습니다.")
    cooked_out.write_bytes(image)
    _repair_existing_raw(
        cooked_out, raw_out,
        sorted({offset // dialogue.COOKED_SECTOR for offset in continuation_offsets}),
    )

    if progress:
        progress("사용자가 선택한 256×240 타이틀 그림 적용 중…")
    condition_layer.validate_writes(bytes(image), title_screen_writes)
    title_screen_offsets = set()
    for write in title_screen_writes:
        start = int(write['offset'])
        before = bytes(image[start:start+len(write['replacement'])])
        dialogue.need(before == write['expected'], '타이틀 영역에 다른 쓰기가 겹쳤습니다.')
        image[start:start+len(write['replacement'])] = write['replacement']
        title_screen_offsets.update(start+i for i,(a,b) in enumerate(zip(before,write['replacement'])) if a!=b)
    cooked_out.write_bytes(image)
    title_screen_sectors = sorted({i//dialogue.COOKED_SECTOR for i in title_screen_offsets})
    _repair_existing_raw(cooked_out, raw_out, title_screen_sectors)
    title_preview.save(output_folder / 'title-screen-format-preview.png')
    title_screen_audit.update(changed_bytes=len(title_screen_offsets),
                              changed_sectors=title_screen_sectors)

    # Re-read after every layer: tests of generated bytes alone cannot catch
    # a later font or presentation writer undoing a resident hook.
    final_image = cooked_out.read_bytes()
    try:
        final_name_width_verification = verify_installed_name_widths(final_image)
    except ValueError as exc:
        raise dialogue.DialogueError(str(exc)) from exc
    final_hook_audit = {
        "resource12_router": early_dialogue_font.verify_final_router_contract(final_image),
        "condition_resident": {**condition_resident.verify_final(final_image),
                               "plan": resident_plan},
        "dialogue_visual_continuation": {
            **dialogue_continuation_resident.verify_final(final_image),
            "plan": continuation_plan,
        },
        "installed_name_widths": final_name_width_verification,
        "title_screen": title_screen.verify_final(final_image, title_stream),
        "subtitle_patches": [],
    }
    final_hook_audit["dialogue_ordinals"] = dialogue.verify_final_pooled_records(
        records, dialogue_texts,
        (base_folder / dialogue.BASE_COOKED_NAME).read_bytes(), final_image,
    )
    final_hook_audit['dialogue_native_text'] = native_dialogue_verification.verify_final(
        final_image, records, dialogue_texts,
    )
    final_hook_audit['missing_presentation_inputs'] = missing_presentations.verify_final_titles(final_image)
    final_hook_audit["condition_native_records"] = conditions.verify_final_condition_records(
        final_image, trimmed_conditions
    )
    condition_layer.cn_text_extent.verify(final_image)
    final_hook_audit["cn_text_physical_extent"] = {"verified_after_last_writer": True}
    final_hook_audit["narration_source_population"] = narrations.verify_final_narration_population(
        final_image, trimmed_narrations
    )
    final_hook_audit["scenario_title_centering"] = {
        "rows": scenario_titles.verify(final_image),
        "verified_after_last_writer": True,
    }
    final_hook_audit["scenario_number_centering"] = {
        "rows": scenario_headers.verify(final_image),
        "verified_after_last_writer": True,
    }
    item_final_writes, _item_final_audit = item_layer.plan_writes(
        final_image, item_names, item_lines, item_mapping, item_rows
    )
    dialogue.need(all(w["expected"] == w["replacement"] for w in item_final_writes),
                  "최종 아이템 순번·문구·마지막 글자 여유 공간이 변경되었습니다.")
    final_hook_audit["item_pools"] = {
        "physical_pools_verified": len(item_final_writes),
        "verified_after_last_writer": True,
        "native_geometry_verified": all(
            _item_final_audit[pool]["native_geometry_verified"]
            for pool in ("name_pool", "tooltip_pool")
        ),
    }
    if subtitle_audit is not None:
        for offset, replacement, patch_id in patches:
            dialogue.need(final_image[offset:offset + len(replacement)] == replacement,
                          f"{patch_id}: 최종 이미지에서 자막 훅이 변경되었습니다.")
            final_hook_audit["subtitle_patches"].append({
                "id": patch_id, "bytes": len(replacement),
                "sha256": sha(replacement), "verified_after_last_writer": True,
            })
        with (base_folder / dialogue.BASE_COOKED_NAME).open("rb") as stream:
            stream.seek(0x4B536)
            protected_gap = stream.read(2)
        dialogue.need(final_image[0x4B536:0x4B538] == protected_gap,
                      "자막 훅 사이의 원본 경계 바이트가 변경되었습니다.")
        final_hook_audit["subtitle_protected_gap_preserved"] = True

    report = {
        "schema": "langrisser-fx-translation-editor-build/v2",
        "status": "BUILT_STATIC_QA_PASS_RUNTIME_REQUIRED",
        "release_allowed": False,
        "runtime_verified": False,
        "base": {"stem": dialogue.BASE_STEM,
                 "cooked_sha256": dialogue.BASE_HASHES[dialogue.BASE_COOKED_NAME]},
        "dialogue_changed_records": len(changed_dialogue),
        "dialogue_adopted_records": len(adopted_dialogue),
        "dialogue_user_edited_records": len(user_edited_dialogue),
        "item_adopted_records": 35,
        "subtitle_changed_records": len(trimmed_subtitles),
        "subtitle_adopted_records": len(adopted_subtitles),
        # Keep the historical user-edit count, but report adopted defaults
        # separately.  Otherwise a build that installs new reviewed
        # translations can misleadingly say that zero narrations changed.
        "narration_changed_records": len(trimmed_narrations),
        "narration_adopted_records": len(adopted_narrations),
        "narration_total_changed_records": (
            narration_audit["compile"]["edited_records"]
            if narration_audit is not None else 0
        ),
        "semantic_abbreviations": (
            narration_audit["compile"].get("semantic_abbreviations", 0)
            if narration_audit is not None else 0
        ),
        "condition_changed_records": len(trimmed_conditions),
        "condition_adopted_records": len(condition_base),
        "epilogue_changed_records": len(trimmed_epilogues),
        "epilogue_adopted_records": len(epilogue_base),
        "items": item_audit,
        "title_screen": title_screen_audit,
        "subtitles": subtitle_audit,
        "narrations": narration_audit,
        "conditions": condition_audit,
        "scenario_titles": title_audit,
        "scenario_numbers": header_audit,
        "epilogues": epilogue_audit,
        "resource12_all_unifont": resource12_unifont_audit,
        "av_menu_all_unifont": av_unifont_audit,
        "final_hook_verification": final_hook_audit,
        "outputs": {
            "cue": {"path": cue_out.name,
                    "sha256": dialogue.sha256_file(cue_out)},
            "cooked": {"path": cooked_out.name,
                       "sha256": dialogue.sha256_file(cooked_out)},
            "raw": {"path": raw_out.name,
                    "sha256": dialogue.sha256_file(raw_out)},
        },
    }
    (output_folder / "translation-editor-build-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if progress:
        progress("통합 빌드 완료")
    return cue_out
