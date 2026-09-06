<img width="1254" height="1254" alt="랑그_new" src="https://github.com/user-attachments/assets/f134092a-949d-47f3-b475-7084703d791f" />

# Langrisser FX Korean Translation Patch

This repository candidate documents and distributes a Korean translation patch for the Japanese PC-FX release of **Der Langrisser FX**. It contains a source-verified delta patch, a dependency-free patch applier, selected project-authored source code, and technical documentation. It does **not** contain the original game, a fully patched disc image, PC-FX BIOS files, emulator binaries, or extracted game media.

## Project status

The current public version is **v0.8**. It is a development/pre-release
snapshot, not a final-completion claim. The exact cumulative verification
record reports 131 checks with 8 known failures and 1 known error, and it does
not claim an all-scenario playthrough.

The translation editor's current catalogs enumerate these working domains:

- 9,508 dialogue records across Scenarios 1–70.
- 150 subtitle cues for 23 voiced movies; all 30 movie IDs are selectable for review.
- 462 narration records across 98 identified presentations.
- 336 victory/defeat-condition records, including presentation and system-menu forms.
- 134 ending character-epilogue records.

These counts describe the implemented/editor-visible population. They are not percentages and do not mean every route has received final human or hardware QA.

## Implemented technical work

The selected source and current project records show implementations for:

- Korean glyph generation and multiple consumer-specific font contexts, including a resident 12×12 Hangul set and a separate movie-subtitle glyph set.
- A private two-byte text encoding, dictionary-backed strings, token preservation, and width/page validation.
- Dialogue, narration, system-message, menu, shop, item-name, and item-tooltip changes.
- Victory/defeat-condition layout, dynamic character names, half-width indentation, and scenario-number/title centering.
- 8×8 bottom-HUD name/class rendering and class/category label repairs.
- Movie subtitles used by both OMAKE movie IDs and their natural-play aliases.
- PC-FX RAINBOW title-image replacement and title-menu resource work.
- Raw MODE1/2352 Track 2 regeneration with changed-sector EDC/ECC repair.
- Source/result hash checks and exact-diff verification for the newest final-stage builders.

See [Technical architecture](docs/ARCHITECTURE.md) for the boundaries and evidence behind these statements.

## Apply the patch

You must supply your own legally obtained Japanese game dump. The patch accepts only this exact raw Track 2 representation:

| Input | Size | SHA-256 |
| --- | ---: | --- |
| Original Japanese raw MODE1/2352 Track 2, including the 225-sector pregap | 755,535,312 bytes | `1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0` |

### Windows automatic patcher

Run `Langrisser-FX-KR-Auto-Patcher.exe`, select the original Japanese CUE, and
choose an output location. The program verifies all three original track files
and creates a complete `Langrisser FX Korean Patch` folder containing the new
Track 2, unchanged copies of Tracks 1 and 3, a ready-to-use CUE, and checksums.
It never overwrites the original disc files or an existing output folder.

The Python source is `patch/langrisser_fx_auto_patcher.py`; maintainers can
rebuild the Windows executable with `tools/build_windows_patcher.ps1`.

### Command-line fallback

Python 3 is required. The applier uses only the Python standard library.

```powershell
python patch/apply_patch.py "path/to/original Track 2.bin" "Track-2.KR.bin" --patch patch/Langrisser-FX-KR-v0.8.lfxpatch
```

Successful application produces:

- size: 762,048,000 bytes
- SHA-256: `E9F3E5D6C6AAD6C15FB554A440F2D8F9D22AE59756D3ABF11E5CF1941D3B04B3`

Copy your unchanged original Track 1 and Track 3 into the same directory as `Track-1.bin` and `Track-3.bin`, then use the supplied [CUE sheet](patch/Langrisser-FX-KR.cue). Do not overwrite your original tracks. Full bilingual instructions are in [INSTALL.txt](patch/INSTALL.txt).

## Build and patch generation

The public `src/patch_pipeline/` directory is a curated snapshot of the current final-stage implementation. It shows the adopted PC-FX media logic, V810 helpers, current class/category/HUD/shop fixes, and final write verification. The current working project, however, accumulated through a long chain of private intermediate builds. Its newest builder starts from a pinned private cumulative intermediate rather than rebuilding every historical change from the untouched Japanese disc in one command.

For that reason, this candidate does **not** claim a complete clean-room, one-command product build from the original disc. Source-derived catalogs and private intermediates are deliberately excluded. Maintainers who already possess the exact original and exact verified target can regenerate the distributable delta with:

```powershell
python tools/create_lfx_patch.py ORIGINAL_TRACK_2.bin VERIFIED_TARGET_TRACK_2.bin patch/Langrisser-FX-KR-v0.8.lfxpatch
```

The generator requires NumPy. See [Building and verification](docs/BUILDING.md) for current limitations and consolidation work still needed.

## Fonts and text output

Project records identify GNU Unifont 17.0.05 as the byte-pinned source for the current resident 12×12 Hangul raster. The movie subtitle path uses a separate 12×12 glyph set. Several UI consumers use different physical font resources and mappings, so their code spaces must not be merged. The 8×8 bottom-HUD work references Galmuri7. Font binaries are not bundled in this candidate; only the applicable GNU Unifont license notices are retained. See [Third-party material](docs/THIRD_PARTY.md).

## Known issues and limits

- The recorded cumulative test baseline is not fully green: 8 known failures and 1 known error remain in the exact v0.8 source-build report.
- An all-scenario playthrough and physical-console/iPhone verification are not recorded for the complete v0.8 scope.
- Some editor/build data catalogs contain substantial extracted Japanese text and are withheld pending a rights decision.
- The public source snapshot cannot reproduce the full patched disc without private/source-derived intermediate data.
- Emulator compatibility outside the recorded Mednafen/Beetle PC-FX routes is not guaranteed.

## Development and test environment

- Windows development host.
- Python 3.13 for the current packaging/audit pass.
- Mednafen 1.32.1 and Beetle PC-FX/libretro were used in recorded emulator QA paths.
- Pillow and NumPy are used by parts of the development and verification tooling.
- A user-supplied PC-FX BIOS is required for emulation and is never included here.

## Repository layout

```text
data/translations/   Korean-only editor delta selected for publication
docs/                architecture, build, audit, and licensing notes
patch/               delta patch, applier, CUE, and installation guide
src/dialogue_editor/ translation editor source snapshot
src/patch_pipeline/  current final-stage build/source snapshot
tests/               patch-container regression tests
third_party/         retained third-party license notices
tools/               maintainer-only delta generator
release/             local GitHub Release upload candidate (ignored by Git)
```

## Credits

- Project copyright-holder display: **기타 깎는 노인 (GiKakNo)**.
- Korean translation, reverse engineering, patch development, testing, and documentation: the project maintainer and contributors.
- GNU Unifont and Galmuri authors: see [third-party notices](docs/THIRD_PARTY.md).
- Mednafen and Beetle PC-FX/libretro were used as development and verification tools; they are not bundled.
- **Der Langrisser FX**, PC-FX, and all original game code, graphics, audio, video, names, and trademarks belong to their respective rights holders.

## License and disclaimer

Project-authored code, scripts, documentation, and Korean translation
contributions are available under the [MIT License](LICENSE), to the extent the
project contributors own those rights. The copyright-holder line is
`Copyright (c) 2026 기타 깎는 노인 (GiKakNo)`. The license does not apply to
the original game or grant rights to copyrighted game data, trademarks, or
third-party material. See [license scope](LICENSE_SCOPE.md) for the exact
boundary.

This is an unofficial, non-commercial fan translation. You must own and supply the supported original game dump. No warranty is provided. Do not distribute original or fully patched disc images.

---

# 한국어 안내

이 폴더는 일본 PC-FX판 **데어 랑그릿사 FX** 한국어 패치를 GitHub 공개 후보 형태로 정리한 것입니다. 원본 게임, 완성된 BIN/CUE 디스크, BIOS, 에뮬레이터, 원본 영상·음원·그래픽 추출물은 포함하지 않습니다.

현재 공개 버전은 **v0.8**이며 완성판이 아니라 개발/사전 공개
후보입니다. 누적 검증 기록에는 131개 검사 중 기존 실패 8개와 오류 1개가
남아 있으며, 모든 시나리오 완주 검증도 기록되어 있지 않습니다.

Windows에서는 자동 패처를 실행하여 원본 일본판 CUE와 출력 위치만 선택하면 됩니다. 자동 패처는 세 트랙을 모두 검사한 뒤 별도 폴더에 완성된 한국어판 BIN/CUE 세트를 만들며 원본과 기존 출력은 덮어쓰지 않습니다. 수동 방식에서는 위 표와 정확히 일치하는 원본 일본판 RAW MODE1/2352 Track 2가 필요합니다. `patch/apply_patch.py`는 원본 크기와 SHA-256을 먼저 검사하고, 새 출력 파일만 만든 뒤 결과 전체 SHA-256을 다시 검사합니다.

공개 소스는 현재 최종 단계와 편집기 코드를 보여 주지만, 개발 이력이 여러 successor 중간판을 이어 만든 구조라 원본부터 최신판까지 한 번에 재현하는 완전한 공개 빌드는 아직 아닙니다. 원본에서 추출된 일본어 전체 표와 비공개 중간판은 저작권상 포함하지 않았습니다. 자세한 제외·보류 내역은 [공개 감사 보고서](docs/PUBLICATION_AUDIT.md)를 확인하십시오.

프로젝트에서 직접 작성한 코드·스크립트·문서와 한국어 번역 기여분은
기여자가 보유한 권리 범위 안에서 MIT 라이선스로 공개합니다. 이 라이선스는
원작 게임 데이터·상표·제3자 자료에는 적용되지 않습니다. 자세한 범위는
[LICENSE_SCOPE.md](LICENSE_SCOPE.md)를 확인하십시오. 소유한 정품/합법 덤프에
개인적으로 패치를 적용하고, 원본 또는 완성된 게임 이미지를 재배포하지
마십시오.
