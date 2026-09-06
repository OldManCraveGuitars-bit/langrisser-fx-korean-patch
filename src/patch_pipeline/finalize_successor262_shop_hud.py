"""Verify successor263 cold-boot evidence and create its CUE/BIN package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

from PIL import Image

import build_successor261_shop_hud as build
import audit_successor258_unit_baseline as historical
from audit_r80_n2_marker_absent_negative_qa import parse_state
import hud_commander_class_restore as hud
import shop_insufficient_funds_global as shop


ROOT = build.ROOT
PRODUCT = ROOT / "work" / build.STEM
STATIC_REPORT = PRODUCT / "successor263-build-report.json"
SHOP_RUN = ROOT / "analysis/successor263-shop-insufficient-cold-product-v2"
HAIN_RUN = ROOT / "analysis/successor263-scenario3-hain-cold-product"
REPORT = ROOT / "analysis/successor263-final-verification.json"
PACKAGE = ROOT / "dist/Langrisser-FX-KR-successor263.zip"
README = ROOT / "release-notes/successor263-README-KO.txt"
PHRASE = bytes.fromhex("F1F6F24EF1E2F08CF08D2E05")


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def ram(path: Path) -> bytes:
    return parse_state(path)[0]["MAIN", "RAM"]


def verify_cold_replay(directory: Path, cue_hash: str, required_capture: str) -> dict[str, object]:
    replay = load(directory / "replay.json")
    assert replay["cue_sha256"] == cue_hash
    assert sha(Path(replay["srm"])) == replay["srm_sha256"]
    assert replay["actions"] and not any("load" in row for row in replay["actions"])
    assert not any(row.get("ram_diagnostics") for row in replay["actions"])
    assert required_capture in {row.get("cap") for row in replay["actions"]}
    picture = directory / f"{required_capture}.png"
    state = directory / f"{required_capture}.state"
    assert Image.open(picture).size == (256, 240) and state.is_file()
    return replay


def main() -> int:
    assert not REPORT.exists() and not PACKAGE.exists(), "Published successor263 outputs are immutable"
    static = load(STATIC_REPORT)
    assert static["status"] == "STATIC_PASS_RUNTIME_REQUIRED"
    assert static["source_changed_bytes"] == 1245 and static["write_owners"] == 165
    for row in static["outputs"].values():
        assert sha(PRODUCT / row["path"]) == row["sha256"]
    cooked = PRODUCT / static["outputs"]["cooked"]["path"]
    image = cooked.read_bytes()
    shop_static = shop.verify(image)
    hud_static = hud.verify(image)
    assert shop_static["common_replicas"] == 105 and shop_static["all_replicas_exact"]
    assert hud_static["active_resource12_copies"] == 15
    assert hud_static["class_ids_checked"] == 255 and hud_static["morgan_rendered_class"] == "소서러"

    source = (ROOT / "work" / build.SOURCE_STEM / build.SOURCE_FILES["cooked"]).read_bytes()
    starts = shop.replica_starts()
    assert all(
        shop._geometry(source, index, start)[4][shop.SHARED_CODE - 1][1]
        == shop._geometry(image, index, start)[4][shop.SHARED_CODE - 1][1]
        for index, start in enumerate(starts)
    )

    cue_hash = static["outputs"]["cue"]["sha256"]
    shop_replay = verify_cold_replay(SHOP_RUN, cue_hash, "08-insufficient-warning")
    hain_replay = verify_cold_replay(HAIN_RUN, cue_hash, "05-dialogue")
    shop_ram = ram(SHOP_RUN / "08-insufficient-warning.state")
    assert shop_ram.count(PHRASE) == 1

    process = subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "tools/audit_successor258_unit_baseline.py"),
         "--variant", "current"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    tests = json.loads(process.stdout)
    assert tests["tests"] == 131 and tests["skipped"] == 0
    assert {row["test"] for row in tests["failures"]} == historical.EXPECTED_FAILURES
    assert {row["test"] for row in tests["errors"]} == historical.EXPECTED_ERRORS

    cue = PRODUCT / static["outputs"]["cue"]["path"]
    tracks = re.findall(r'^FILE "([^"\r\n]+)" BINARY$', cue.read_text(encoding="ascii"), re.M)
    assert tracks == ["Track-1.bin", static["outputs"]["raw"]["path"], "Track-3.bin"]
    package_sources = [(cue, cue.name), *((PRODUCT / name, name) for name in tracks),
                       (README, "README-KO.txt")]
    hashes = {archive_name: sha(path) for path, archive_name in package_sources}
    manifest = "".join(f"{hashes[name]} *{name}\n" for _path, name in package_sources).encode("utf-8")
    folder = "Langrisser-FX-KR-successor263"
    with zipfile.ZipFile(PACKAGE, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for path, archive_name in package_sources:
            print("Packing " + archive_name, flush=True)
            archive.write(path, f"{folder}/{archive_name}")
        archive.writestr(f"{folder}/SHA256SUMS.txt", manifest)
    with zipfile.ZipFile(PACKAGE) as archive:
        for path, archive_name in package_sources:
            with archive.open(f"{folder}/{archive_name}") as stream:
                assert hashlib.file_digest(stream, "sha256").hexdigest().upper() == hashes[archive_name]
        assert archive.read(f"{folder}/SHA256SUMS.txt") == manifest

    report = {
        "schema": "langrisser-fx-successor263-hain-shop-runtime/v1",
        "stem": build.STEM,
        "status": "PASS_REPORTED_HAIN_AND_SHOP_REGRESSION",
        "release_allowed": True,
        "static": {
            "shop": shop_static,
            "bottom_hud": hud_static,
            "changed_bytes_relative_to_accepted_successor260": static["source_changed_bytes"],
            "all_other_cooked_bytes_identical": True,
            "shared_code11_identical_in_all_105_replicas": True,
        },
        "runtime": {
            "shop": {
                "route": "cold boot -> Scenario 2 save -> preparation item shop -> buy to 40P -> rejected purchase",
                "rendered": "자금이 부족합니다.",
                "exact_encoded_phrase_in_live_ram": shop_ram.count(PHRASE) == 1,
                "capture": "analysis/successor263-shop-insufficient-cold-product-v2/08-insufficient-warning.png",
                "controller_only": True,
            },
            "hain": {
                "route": "cold boot -> Scenario 3 continue -> deploy -> opening dialogue",
                "rendered": "응. 푹 잘 잤어.",
                "capture": "analysis/successor263-scenario3-hain-cold-product/05-dialogue.png",
                "controller_only": True,
            },
            "all_scenarios_played": False,
            "global_basis": "105 local shop dictionaries and all 15 active Resource-12 copies",
        },
        "source_sram": {
            "shop_sha256": shop_replay["srm_sha256"],
            "hain_sha256": hain_replay["srm_sha256"],
            "unchanged": True,
        },
        "tests": {
            "status": "NO_NEW_FAILURES",
            "all_tests_pass": False,
            "known_failures": len(tests["failures"]),
            "known_errors": len(tests["errors"]),
            "result": tests,
        },
        "evidence": {
            "shop_replay_sha256": sha(SHOP_RUN / "replay.json"),
            "shop_capture_sha256": sha(SHOP_RUN / "08-insufficient-warning.png"),
            "hain_replay_sha256": sha(HAIN_RUN / "replay.json"),
            "hain_capture_sha256": sha(HAIN_RUN / "05-dialogue.png"),
        },
        "package": {
            "path": str(PACKAGE.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha(PACKAGE),
            "bytes": PACKAGE.stat().st_size,
            "contains_SRM_or_BIOS": False,
            "files": hashes,
        },
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "package": str(PACKAGE),
                      "sha256": report["package"]["sha256"]}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
