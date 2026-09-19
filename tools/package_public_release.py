#!/usr/bin/env python3
"""Package only the explicitly verified V0.972 player-facing release."""
from __future__ import annotations
import hashlib,json,sys,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION="V0.972"
sys.path.insert(0,str(ROOT/"patch"))
import apply_patch
import langrisser_fx_auto_patcher as auto
REPORT=ROOT/"docs/verification_V0.972.json"
EXE=f"Langrisser-FX-KR-Auto-Patcher-{VERSION}.exe"
FILES={
    EXE:f"release/windows-patcher/{EXE}",
    auto.PATCH_FILENAME:f"patch/{auto.PATCH_FILENAME}",
    "apply_patch.py":"patch/apply_patch.py",
    "langrisser_fx_auto_patcher.py":"patch/langrisser_fx_auto_patcher.py",
    "Langrisser-FX-KR.cue":"patch/Langrisser-FX-KR.cue",
    "INSTALL.txt":"patch/INSTALL.txt",
    "patch/INSTALL.txt":"patch/INSTALL.txt",
    "CHANGELOG.md":"CHANGELOG.md",
    "LICENSE":"LICENSE",
    "LICENSE_SCOPE.md":"LICENSE_SCOPE.md",
}
for name in (f"RELEASE_{VERSION}.md",f"VERIFICATION_{VERSION}.md",
             f"IMPLEMENTATION_{VERSION}.md",f"PUBLICATION_{VERSION}.md",
             f"verification_{VERSION}.json","BUILDING.md","THIRD_PARTY.md"):
    FILES[f"docs/{name}"]=f"docs/{name}"
for name in ("third_party/unifont/LICENSE.txt","third_party/unifont/OFL-1.1.txt",
             "third_party/galmuri/OFL-1.1.md",f"screenshots/{VERSION}/README.md",
             f"screenshots/{VERSION}/provenance.json"):
    FILES[name]=name
provenance=json.loads((ROOT/f"screenshots/{VERSION}/provenance.json").read_bytes())
for row in provenance["screenshots"]:
    name=f"screenshots/{VERSION}/{row['file']}"
    if Path(row["file"]).name!=row["file"] or Path(row["file"]).suffix.lower() not in {".png",".jpg"}:
        raise RuntimeError("Unsafe screenshot path")
    FILES[name]=name

def digest(data):return hashlib.sha256(data).hexdigest().upper()
def main():
    output=ROOT/"release"/f"Langrisser_FX_Korean_Patch_{VERSION}.zip"
    if output.exists():raise RuntimeError("Preserve existing release archive")
    report=json.loads(REPORT.read_bytes())
    if report["status"]!="PASS_APPROVED_TARGET_AND_BOTH_INSTALLERS" or report["version"]!=VERSION:
        raise RuntimeError("Missing current application verification")
    with (ROOT/"patch"/auto.PATCH_FILENAME).open("rb") as f:header=apply_patch.read_header(f)
    if header["target_sha256"]!=auto.OUTPUT_TRACK2_SHA256 or VERSION not in header["description"]:
        raise RuntimeError("Patcher and delta disagree")
    payloads={name:(ROOT/source).read_bytes() for name,source in FILES.items()}
    if digest(payloads[auto.PATCH_FILENAME])!=report["patch"]["sha256"]:
        raise RuntimeError("Delta changed after full application verification")
    if digest(payloads[EXE])!=report["windows_exe"]["sha256"]:
        raise RuntimeError("EXE changed after full application verification")
    for row in provenance["screenshots"]:
        if digest(payloads[f"screenshots/{VERSION}/{row['file']}"])!=row["sha256"]:
            raise RuntimeError("Screenshot provenance mismatch")
    payloads["README.txt"]=(
        "데어 랑그릿사 FX 한국어 패치 V0.972 — 사전 공개 버전\n\n"
        "INSTALL.txt와 docs/RELEASE_V0.972.md를 먼저 읽어 주세요.\n"
        "Langrisser-FX-KR-Auto-Patcher-V0.972.exe에 원본 일본판 CUE를 선택하세요.\n"
        "이전 한글판에 덧씌우지 마세요. SRAM을 백업하고 게임 내 저장을 불러오세요.\n"
        "원본 게임·BIOS·세이브·완성된 게임 이미지는 포함하지 않습니다.\n"
        "간헐적인 엔딩 검은 화면은 미해결입니다. 모든 분기/실기 검증은 아닙니다.\n\n"
        "Development prerelease. Apply to the supported original Japanese disc.\n"
        "See the release and verification reports for tested routes and limitations.\n"
    ).encode("utf8")
    payloads["SHA256SUMS.txt"]=("\n".join(
        f"{digest(data)} *{name}" for name,data in sorted(payloads.items()))+"\n").encode("utf8")
    for name in payloads:
        if Path(name).suffix.lower() in {".bin",".iso",".rom",".srm",".state",".mp4",".wav",".dmp"}:
            raise RuntimeError("Forbidden release member")
    with zipfile.ZipFile(output,"x") as z:
        for name,data in sorted(payloads.items()):
            info=zipfile.ZipInfo(name);info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data,compresslevel=9)
    with zipfile.ZipFile(output) as z:
        if set(z.namelist())!=set(payloads) or z.testzip() is not None:raise RuntimeError("ZIP integrity")
        for name,data in payloads.items():
            if z.read(name)!=data:raise RuntimeError("ZIP payload mismatch")
    checksum=output.with_suffix(output.suffix+".sha256")
    if checksum.exists():raise RuntimeError("Preserve existing checksum")
    checksum.write_text(f"{apply_patch.sha256_file(output)} *{output.name}\n",encoding="ascii",newline="\n")
    print(json.dumps(dict(status="PASS_ALLOWLISTED_PACKAGE",file=output.name,
        members=len(payloads),screenshots=len(provenance["screenshots"]),
        bytes=output.stat().st_size,sha256=apply_patch.sha256_file(output))))
if __name__=="__main__":main()
