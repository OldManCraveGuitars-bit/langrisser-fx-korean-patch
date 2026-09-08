#!/usr/bin/env python3
"""Package only the explicitly selected v0.845 player-facing release material."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "v0.845"
sys.path.insert(0, str(ROOT / "patch"))
import apply_patch
import langrisser_fx_auto_patcher as auto

FILES = {
    "Langrisser-FX-KR-Auto-Patcher-v0.845.exe": "release/windows-patcher/Langrisser-FX-KR-Auto-Patcher-v0.845.exe",
    "Langrisser-FX-KR-v0.845.lfxpatch": "patch/Langrisser-FX-KR-v0.845.lfxpatch",
    "apply_patch.py": "patch/apply_patch.py",
    "langrisser_fx_auto_patcher.py": "patch/langrisser_fx_auto_patcher.py",
    "Langrisser-FX-KR.cue": "patch/Langrisser-FX-KR.cue",
    "INSTALL.txt": "patch/INSTALL.txt",
    "CHANGELOG.md": "CHANGELOG.md",
    "LICENSE": "LICENSE",
    "LICENSE_SCOPE.md": "LICENSE_SCOPE.md",
    "docs/RELEASE_v0.845.md": "docs/RELEASE_v0.845.md",
    "docs/VERIFICATION_v0.845.md": "docs/VERIFICATION_v0.845.md",
    "docs/IMPLEMENTATION_v0.845.md": "docs/IMPLEMENTATION_v0.845.md",
    "docs/PUBLICATION_v0.845.md": "docs/PUBLICATION_v0.845.md",
    "docs/BUILDING.md": "docs/BUILDING.md",
    "docs/THIRD_PARTY.md": "docs/THIRD_PARTY.md",
    "third_party/unifont/LICENSE.txt": "third_party/unifont/LICENSE.txt",
    "third_party/unifont/OFL-1.1.txt": "third_party/unifont/OFL-1.1.txt",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> None:
    output = ROOT / "release" / f"Langrisser_FX_Korean_Patch_{VERSION}.zip"
    if output.exists():
        raise RuntimeError("Preserve existing release archive; output already exists")
    with (ROOT / "patch" / auto.PATCH_FILENAME).open("rb") as stream:
        header = apply_patch.read_header(stream)
    if (header["target_sha256"] != auto.OUTPUT_TRACK2_SHA256
            or header["source_sha256"] != auto.EXPECTED_TRACKS[2]["sha256"]
            or VERSION not in header["description"]):
        raise RuntimeError("Installer and patch release identities disagree")
    payloads = {name: (ROOT / source).read_bytes() for name, source in FILES.items()}
    if digest(payloads[auto.PATCH_FILENAME]) != "B1C6E25E5CA0DE9C524F20CA0AEEC3226217340FE30922194067596FA056EC87":
        raise RuntimeError("Delta differs from the verified release")
    if digest(payloads["Langrisser-FX-KR-Auto-Patcher-v0.845.exe"]) != "66A5D2A1026018267B8146E0FFA883335483559499A54A8E7847B8BD95034725":
        raise RuntimeError("EXE differs from the application-verified release")
    payloads["README.txt"] = (
        "Langrisser FX Korean Patch v0.845 (development/pre-release)\n\n"
        "Read INSTALL.txt and docs/RELEASE_v0.845.md before applying.\n"
        "Run Langrisser-FX-KR-Auto-Patcher-v0.845.exe with the original Japanese CUE.\n"
        "Do not apply to an already Korean-patched BIN. Back up SRAM saves.\n"
        "No original or fully patched game images are included.\n\n"
        "New hidden-dungeon wording review and all-branch playthroughs remain incomplete.\n"
        "설치 방법: INSTALL.txt / 수정 내역: docs/RELEASE_v0.845.md\n"
        "원본 일본판 CUE에 새로 적용하세요. 이전 한글판에 덧씌우지 마세요.\n"
    ).encode("utf-8")
    payloads["SHA256SUMS.txt"] = ("\n".join(
        f"{digest(data)} *{name}" for name, data in sorted(payloads.items())
    ) + "\n").encode("utf-8")
    for name in payloads:
        if Path(name).suffix.lower() in {".bin", ".iso", ".rom", ".srm", ".state", ".mp4", ".wav"}:
            raise RuntimeError(f"Forbidden release asset: {name}")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payloads.items()):
            info = zipfile.ZipInfo(name)  # stable ZIP metadata, not a claimed release date
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    with zipfile.ZipFile(output) as archive:
        if set(archive.namelist()) != set(payloads) or archive.testzip() is not None:
            raise RuntimeError("Release member/CRC verification failed")
        for name, data in payloads.items():
            if archive.read(name) != data:
                raise RuntimeError(f"Release payload mismatch: {name}")
    print(f"PASS: {output.name}; {len(payloads)} allowlisted members; {output.stat().st_size} bytes")
    print(f"SHA256: {apply_patch.sha256_file(output)}")


if __name__ == "__main__":
    main()
