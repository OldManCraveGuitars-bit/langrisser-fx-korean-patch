#!/usr/bin/env python3
"""Windows GUI/CLI installer for the Langrisser FX Korean patch.

The installer accepts the original Japanese CUE sheet, verifies all three
track files, and creates a new playable Korean-patched CUE set in a separate
directory.  It never writes to or renames the user's original files.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable
import uuid

from apply_patch import PatchError, apply_patch, sha256_file


APP_TITLE = "랑그릿사 FX 한국어 자동 패처 v0.845"
PATCH_FILENAME = "Langrisser-FX-KR-v0.845.lfxpatch"
OUTPUT_DIRECTORY_NAME = "Langrisser FX Korean Patch"
OUTPUT_CUE_NAME = "Langrisser-FX-KR.cue"
MIN_FREE_MARGIN = 256 * 1024 * 1024

EXPECTED_TRACKS = {
    1: {
        "size": 4_106_592,
        "sha256": "1E1840205CE98F5E0DF8067BEA8B3336DB62CA071C7B67538A0312C267D9CFA9",
        "output": "Track-1.bin",
    },
    2: {
        "size": 755_535_312,
        "sha256": "1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0",
        "output": "Track-2.KR.bin",
    },
    3: {
        "size": 17_120_208,
        "sha256": "9D1133A7DDAB061567F6C83F3342C90CBE32DC6A94561AE5309FA74335FDDD8D",
        "output": "Track-3.bin",
    },
}

OUTPUT_TRACK2_SIZE = 762_048_000
OUTPUT_TRACK2_SHA256 = "18652F60B9156BFA40DF8A3A638749D05D0A68898D938A86A2C7A2A38D8A927D"

CUE_TEXT = """CATALOG 0000000000000
FILE "Track-1.bin" BINARY
  TRACK 01 AUDIO
    INDEX 01 00:00:00
FILE "Track-2.KR.bin" BINARY
  TRACK 02 MODE1/2352
    INDEX 00 00:00:00
    INDEX 01 00:03:00
FILE "Track-3.bin" BINARY
  TRACK 03 AUDIO
    INDEX 00 00:00:00
    INDEX 01 00:02:00
"""

FILE_RE = re.compile(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+(\S+)\s*$', re.IGNORECASE)
TRACK_RE = re.compile(r"^\s*TRACK\s+(\d+)\s+(\S+)\s*$", re.IGNORECASE)

StatusCallback = Callable[[str], None]


class InstallerError(RuntimeError):
    """Raised when a disc set cannot be safely verified or built."""


@dataclass(frozen=True)
class DiscSet:
    cue: Path
    tracks: dict[int, Path]
    hashes: dict[int, str]


def resource_path(filename: str) -> Path:
    """Resolve a file beside the script or inside a PyInstaller bundle."""

    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_root / filename


def parse_cue(cue_path: Path) -> dict[int, Path]:
    """Return the file used by each track in a three-file CUE sheet."""

    cue_path = cue_path.resolve()
    if not cue_path.is_file():
        raise InstallerError("선택한 CUE 파일을 찾을 수 없습니다.")

    try:
        text = cue_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = cue_path.read_text(encoding="cp932")
        except UnicodeDecodeError as exc:
            raise InstallerError("CUE 파일의 문자 인코딩을 읽을 수 없습니다.") from exc

    current_file: str | None = None
    tracks: dict[int, Path] = {}
    for line in text.splitlines():
        file_match = FILE_RE.match(line)
        if file_match:
            current_file = file_match.group(1) or file_match.group(2)
            continue
        track_match = TRACK_RE.match(line)
        if not track_match:
            continue
        if current_file is None:
            raise InstallerError("CUE의 TRACK보다 앞에 FILE 항목이 없습니다.")
        number = int(track_match.group(1))
        if number in tracks:
            raise InstallerError(f"CUE에 Track {number} 항목이 중복되어 있습니다.")
        tracks[number] = (cue_path.parent / current_file).resolve()

    if set(tracks) != {1, 2, 3}:
        found = ", ".join(str(number) for number in sorted(tracks)) or "없음"
        raise InstallerError(f"지원하는 3트랙 CUE가 아닙니다. 발견된 트랙: {found}")
    if len(set(tracks.values())) != 3:
        raise InstallerError("세 트랙이 각각 별도 BIN 파일인 원본 덤프만 지원합니다.")
    return tracks


def validate_disc(cue_path: Path, status: StatusCallback | None = None) -> DiscSet:
    """Verify that a CUE references the exact supported Japanese disc dump."""

    tracks = parse_cue(cue_path)
    hashes: dict[int, str] = {}
    for number in (1, 2, 3):
        path = tracks[number]
        expected = EXPECTED_TRACKS[number]
        if status:
            status(f"원본 Track {number} 확인 중: {path.name}")
        if not path.is_file():
            raise InstallerError(f"원본 Track {number} 파일을 찾을 수 없습니다:\n{path}")
        size = path.stat().st_size
        if size != int(expected["size"]):
            raise InstallerError(
                f"원본 Track {number} 크기가 지원판과 다릅니다.\n"
                f"예상: {int(expected['size']):,} 바이트\n실제: {size:,} 바이트"
            )
        digest = sha256_file(path)
        if digest != str(expected["sha256"]):
            raise InstallerError(
                f"원본 Track {number} SHA-256이 지원판과 다릅니다.\n"
                "다른 버전이거나 손상된 덤프일 수 있습니다."
            )
        hashes[number] = digest
    return DiscSet(cue=Path(cue_path).resolve(), tracks=tracks, hashes=hashes)


def write_checksums(directory: Path, track_hashes: dict[int, str]) -> None:
    cue_hash = hashlib.sha256((directory / OUTPUT_CUE_NAME).read_bytes()).hexdigest().upper()
    lines = [
        f"{track_hashes[1]}  {EXPECTED_TRACKS[1]['output']}",
        f"{OUTPUT_TRACK2_SHA256}  {EXPECTED_TRACKS[2]['output']}",
        f"{track_hashes[3]}  {EXPECTED_TRACKS[3]['output']}",
        f"{cue_hash}  {OUTPUT_CUE_NAME}",
        "",
    ]
    (directory / "SHA256SUMS.txt").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def build_disc_set(
    cue_path: Path,
    output_parent: Path,
    patch_path: Path | None = None,
    status: StatusCallback | None = None,
) -> Path:
    """Build a complete patched CUE set without touching the original files."""

    disc = validate_disc(cue_path, status=status)
    patch_path = (patch_path or resource_path(PATCH_FILENAME)).resolve()
    if not patch_path.is_file():
        raise InstallerError(f"패치 데이터 파일을 찾을 수 없습니다:\n{patch_path}")

    output_parent = Path(output_parent).resolve()
    output_parent.mkdir(parents=True, exist_ok=True)
    output_directory = output_parent / OUTPUT_DIRECTORY_NAME
    if output_directory.exists():
        raise InstallerError(
            f"출력 폴더가 이미 있습니다:\n{output_directory}\n"
            "기존 결과를 보존하기 위해 덮어쓰지 않습니다. 폴더를 옮기거나 이름을 바꿔주세요."
        )

    required = OUTPUT_TRACK2_SIZE + int(EXPECTED_TRACKS[1]["size"]) + int(EXPECTED_TRACKS[3]["size"])
    free = shutil.disk_usage(output_parent).free
    if free < required + MIN_FREE_MARGIN:
        raise InstallerError(
            "출력 드라이브의 여유 공간이 부족합니다.\n"
            f"필요 여유 공간: 약 {(required + MIN_FREE_MARGIN) / (1024 ** 3):.2f} GiB\n"
            f"현재 여유 공간: {free / (1024 ** 3):.2f} GiB"
        )

    staging = output_parent / f".langrisser-fx-kr-{uuid.uuid4().hex}.tmp"
    try:
        staging.mkdir()
        if status:
            status("원본 Track 1 복사 중…")
        shutil.copy2(disc.tracks[1], staging / str(EXPECTED_TRACKS[1]["output"]))

        if status:
            status("한국어 Track 2 생성 및 전체 해시 검증 중… 잠시 기다려 주세요.")
        result = apply_patch(
            disc.tracks[2],
            patch_path,
            staging / str(EXPECTED_TRACKS[2]["output"]),
        )
        if int(result["bytes"]) != OUTPUT_TRACK2_SIZE or str(result["sha256"]) != OUTPUT_TRACK2_SHA256:
            raise InstallerError("생성된 Track 2의 최종 검증값이 예상과 다릅니다.")

        if status:
            status("원본 Track 3 복사 중…")
        shutil.copy2(disc.tracks[3], staging / str(EXPECTED_TRACKS[3]["output"]))

        (staging / OUTPUT_CUE_NAME).write_text(CUE_TEXT, encoding="ascii", newline="\n")
        write_checksums(staging, disc.hashes)
        staging.rename(output_directory)
    except (OSError, PatchError) as exc:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if isinstance(exc, InstallerError):
            raise
        raise InstallerError(str(exc)) from exc
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise

    if status:
        status("완료: 한국어판 CUE 세트가 생성되었습니다.")
    return output_directory


class PatcherWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.resizable(False, False)
        self.cue_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(value="원본 일본판 CUE 파일을 선택하세요.")
        self.last_output: Path | None = None

        frame = ttk.Frame(root, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Langrisser FX 한국어 패치 v0.845", font=("맑은 고딕", 15, "bold")).grid(
            row=0, column=0, columnspan=3, pady=(0, 4)
        )
        ttk.Label(
            frame,
            text="원본 파일은 변경하지 않고 새 폴더에 한국어판을 만듭니다.",
        ).grid(row=1, column=0, columnspan=3, pady=(0, 16))

        ttk.Label(frame, text="원본 CUE").grid(row=2, column=0, sticky="w", padx=(0, 8))
        self.cue_entry = ttk.Entry(frame, textvariable=self.cue_var, width=62)
        self.cue_entry.grid(row=2, column=1, sticky="ew")
        self.cue_button = ttk.Button(frame, text="찾아보기…", command=self.choose_cue)
        self.cue_button.grid(row=2, column=2, padx=(8, 0))

        ttk.Label(frame, text="출력 위치").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(10, 0))
        self.output_entry = ttk.Entry(frame, textvariable=self.output_var, width=62)
        self.output_entry.grid(row=3, column=1, sticky="ew", pady=(10, 0))
        self.output_button = ttk.Button(frame, text="찾아보기…", command=self.choose_output)
        self.output_button.grid(row=3, column=2, padx=(8, 0), pady=(10, 0))

        ttk.Label(
            frame,
            text=f"선택한 위치 아래에 ‘{OUTPUT_DIRECTORY_NAME}’ 폴더가 생성됩니다.",
            foreground="#555555",
        ).grid(row=4, column=1, columnspan=2, sticky="w", pady=(4, 14))

        self.progress = ttk.Progressbar(frame, mode="indeterminate", length=560)
        self.progress.grid(row=5, column=0, columnspan=3, sticky="ew")
        ttk.Label(frame, textvariable=self.status_var, wraplength=610).grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(8, 14)
        )

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=7, column=0, columnspan=3, sticky="e")
        self.open_button = ttk.Button(button_frame, text="완성 폴더 열기", command=self.open_output, state="disabled")
        self.open_button.grid(row=0, column=0, padx=(0, 8))
        self.start_button = ttk.Button(button_frame, text="한국어판 만들기", command=self.start)
        self.start_button.grid(row=0, column=1)

    def choose_cue(self) -> None:
        chosen = filedialog.askopenfilename(
            title="원본 일본판 CUE 선택",
            filetypes=[("CUE 시트", "*.cue"), ("모든 파일", "*.*")],
        )
        if chosen:
            path = Path(chosen)
            self.cue_var.set(str(path))
            if not self.output_var.get().strip():
                self.output_var.set(str(path.parent))

    def choose_output(self) -> None:
        chosen = filedialog.askdirectory(title="한국어판을 만들 상위 폴더 선택")
        if chosen:
            self.output_var.set(chosen)

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for widget in (self.cue_entry, self.output_entry, self.cue_button, self.output_button, self.start_button):
            widget.configure(state=state)
        if busy:
            self.open_button.configure(state="disabled")
            self.progress.start(12)
        else:
            self.progress.stop()

    def post_status(self, text: str) -> None:
        self.root.after(0, self.status_var.set, text)

    def start(self) -> None:
        cue_text = self.cue_var.get().strip()
        output_text = self.output_var.get().strip()
        if not cue_text or not output_text:
            messagebox.showwarning(APP_TITLE, "원본 CUE와 출력 위치를 모두 선택하세요.")
            return
        self.last_output = None
        self.set_busy(True)
        threading.Thread(
            target=self.worker,
            args=(Path(cue_text), Path(output_text)),
            daemon=True,
        ).start()

    def worker(self, cue: Path, output_parent: Path) -> None:
        try:
            output = build_disc_set(cue, output_parent, status=self.post_status)
        except (OSError, InstallerError, PatchError) as exc:
            self.root.after(0, self.finish_error, str(exc))
        except Exception as exc:  # defensive GUI boundary
            self.root.after(0, self.finish_error, f"예상하지 못한 오류가 발생했습니다:\n{exc}")
        else:
            self.root.after(0, self.finish_success, output)

    def finish_error(self, detail: str) -> None:
        self.set_busy(False)
        self.status_var.set("실패: 원본과 출력 폴더를 확인하세요.")
        messagebox.showerror(APP_TITLE, detail)

    def finish_success(self, output: Path) -> None:
        self.set_busy(False)
        self.last_output = output
        self.open_button.configure(state="normal")
        self.status_var.set(f"완료: {output}")
        messagebox.showinfo(
            APP_TITLE,
            f"한국어판 생성이 완료되었습니다.\n\n{output / OUTPUT_CUE_NAME}",
        )

    def open_output(self) -> None:
        if self.last_output and self.last_output.is_dir():
            os.startfile(self.last_output)  # type: ignore[attr-defined]


def run_gui() -> int:
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    PatcherWindow(root)
    root.mainloop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Langrisser FX Korean automatic patcher")
    parser.add_argument("--verify-cue", type=Path, help="verify an original CUE and its three tracks")
    parser.add_argument("--apply-cue", type=Path, help="build a patched disc set from an original CUE")
    parser.add_argument("--output-parent", type=Path, help="parent directory for --apply-cue")
    args = parser.parse_args()

    try:
        if args.verify_cue:
            disc = validate_disc(args.verify_cue, status=print)
            print(f"PASS: {disc.cue}")
            return 0
        if args.apply_cue:
            if not args.output_parent:
                parser.error("--apply-cue requires --output-parent")
            output = build_disc_set(args.apply_cue, args.output_parent, status=print)
            print(f"PASS: {output}")
            return 0
    except (OSError, InstallerError, PatchError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
