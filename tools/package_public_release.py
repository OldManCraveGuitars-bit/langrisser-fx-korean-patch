#!/usr/bin/env python3
"""Package only the explicitly selected v0.851 player-facing release material."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "v0.851"
sys.path.insert(0, str(ROOT / "patch"))
import apply_patch
import langrisser_fx_auto_patcher as auto

FILES = {
    "Langrisser-FX-KR-Auto-Patcher-v0.851.exe": "release/windows-patcher/Langrisser-FX-KR-Auto-Patcher-v0.851.exe",
    "Langrisser-FX-KR-v0.851.lfxpatch": "patch/Langrisser-FX-KR-v0.851.lfxpatch",
    "apply_patch.py": "patch/apply_patch.py",
    "langrisser_fx_auto_patcher.py": "patch/langrisser_fx_auto_patcher.py",
    "Langrisser-FX-KR.cue": "patch/Langrisser-FX-KR.cue",
    "INSTALL.txt": "patch/INSTALL.txt",
    "CHANGELOG.md": "CHANGELOG.md",
    "LICENSE": "LICENSE",
    "LICENSE_SCOPE.md": "LICENSE_SCOPE.md",
    "docs/RELEASE_v0.851.md": "docs/RELEASE_v0.851.md",
    "docs/VERIFICATION_v0.851.md": "docs/VERIFICATION_v0.851.md",
    "docs/IMPLEMENTATION_v0.851.md": "docs/IMPLEMENTATION_v0.851.md",
    "docs/PUBLICATION_v0.851.md": "docs/PUBLICATION_v0.851.md",
    "docs/BUILDING.md": "docs/BUILDING.md",
    "screenshots/v0.851/liana-before-v0.85.png": "screenshots/v0.851/liana-before-v0.85.png",
    "screenshots/v0.851/liana-after-v0.851.png": "screenshots/v0.851/liana-after-v0.851.png",
    "docs/THIRD_PARTY.md": "docs/THIRD_PARTY.md",
    "third_party/unifont/LICENSE.txt": "third_party/unifont/LICENSE.txt",
    "third_party/unifont/OFL-1.1.txt": "third_party/unifont/OFL-1.1.txt",
    "third_party/galmuri/OFL-1.1.md": "third_party/galmuri/OFL-1.1.md",
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
    if digest(payloads[auto.PATCH_FILENAME]) != "402A4506CB9374B30E82C84BC92B56A4A59E15B86D5A490F1AF8DCC066103919":
        raise RuntimeError("Delta differs from the verified release")
    if digest(payloads["Langrisser-FX-KR-Auto-Patcher-v0.851.exe"]) != "632112448FB8101AD66B737EBF52A9B35B65F538A63F0DD266EE1635E00B973C":
        raise RuntimeError("EXE differs from the application-verified release")
    payloads["README.txt"] = (
        "Langrisser FX Korean Patch v0.851 (development/pre-release)\n\n"
        "Read INSTALL.txt and docs/RELEASE_v0.851.md before applying.\n"
        "Run Langrisser-FX-KR-Auto-Patcher-v0.851.exe with the original Japanese CUE.\n"
        "Do not apply to an already Korean-patched BIN. Back up SRAM saves.\n"
        "No original or fully patched game images are included.\n\n"
        "New hidden-dungeon wording review and all-branch playthroughs remain incomplete.\n"
        "설치 방법: INSTALL.txt / 수정 내역: docs/RELEASE_v0.851.md\n"
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
