<img width="1254" height="1254" alt="랑그_new" src="https://github.com/user-attachments/assets/f134092a-949d-47f3-b475-7084703d791f" />

# Langrisser FX Korean Translation Patch

This repository candidate documents and distributes a Korean translation patch for the Japanese PC-FX release of **Der Langrisser FX**. It contains a source-verified delta patch, a dependency-free patch applier, selected project-authored source code, and technical documentation. It does **not** contain the original game, a fully patched disc image, PC-FX BIOS files, emulator binaries, or extracted game media.

## Project status

The current public version is **v0.85**. It is a development/pre-release
snapshot, not a final-completion claim. Since v0.845, this update fixes the
Scenario 12 Angel-versus-Phoenix battle freeze, repairs a second resource-directory
boundary damaged by the same historical allocator, and restores the shared
bottom-HUD syllable `로` to the adopted Galmuri7 shape. Only 92 cooked bytes change
from v0.845; gameplay balance, dialogue and current subtitle data are unchanged.
Earlier fixes remain included. Hidden dialogue still requires full human wording review. See the [v0.85 release notes](docs/RELEASE_v0.85.md)
for the fixes and exact verification scope. The earlier cumulative tool baseline
reported 131 checks with 8 known failures and 1 known error; this update does not
claim to resolve those unrelated tooling failures or complete an all-scenario playthrough.

Download the automatic patcher from [GitHub Releases](https://github.com/OldManCraveGuitars-bit/langrisser-fx-korean-patch/releases/tag/v0.85).

The translation editor's current catalogs enumerate these working domains:

- 9,508 dialogue records across Scenarios 1–70.
- 150 subtitle cues for 23 voiced movies; all 30 movie IDs are selectable for review.
- 462 narration records across 98 identified presentations.
- 336 victory/defeat-condition records, including presentation and system-menu forms.
- 134 ending character-epilogue records.

Outside that historical Scenarios 1–70 editor catalog, Muscle Temple has 86
nonempty dialogue records and one empty slot. X2 adds 97 nonempty records; X3
adds 146 nonempty records and retains two empty slots. These counts describe
implemented populations, not percentages or complete human/hardware QA.

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

Run `Langrisser-FX-KR-Auto-Patcher-v0.85.exe`, select the original Japanese CUE, and
choose an output location. The program verifies all three original track files
and creates a complete `Langrisser FX Korean Patch` folder containing the new
Track 2, unchanged copies of Tracks 1 and 3, a ready-to-use CUE, and checksums.
It never overwrites the original disc files or an existing output folder.

The Python source is `patch/langrisser_fx_auto_patcher.py`; maintainers can
rebuild the Windows executable with `tools/build_windows_patcher.ps1`.

### Command-line fallback

Python 3 is required. The applier uses only the Python standard library.

```powershell
python patch/apply_patch.py "path/to/original Track 2.bin" "Track-2.KR.bin" --patch patch/Langrisser-FX-KR-v0.85.lfxpatch
```

Successful application produces:

- size: 762,048,000 bytes
- SHA-256: `3FF464E484B55064BED49C7451E8DDFAEA24896D3819DA3A3EEFBBD443824B0A`

Copy your unchanged original Track 1 and Track 3 into the same directory as `Track-1.bin` and `Track-3.bin`, then use the supplied [CUE sheet](patch/Langrisser-FX-KR.cue). Do not overwrite your original tracks. Full bilingual instructions are in [INSTALL.txt](patch/INSTALL.txt).

Apply this cumulative patch to the **original Japanese dump**, not to an older
patched image. Back up SRAM saves and load an in-game save after changing builds;
old emulator save states can restore old patched code.

## Build and patch generation

The public source is a curated implementation snapshot, now including the
v0.85 native archive-boundary and HUD font modules, alongside earlier selected
dialogue, complete menu/unit-cache separation, hidden-dialogue and subtitle work.
Its private primary build starts with the immutable Japanese Track 2 and the
hash-pinned v0.81 cumulative delta specification, reconstructs that baseline
within the build, then applies a conflict-checked composed write plan. Existing
patched game outputs are comparison evidence, not its input. Some source-derived
catalogs and historical authoring dependencies remain private, so these source
snapshots are for inspection, not a complete standalone source build.

For that reason, this candidate does **not** claim a complete clean-room, one-command product build from the original disc. Source-derived catalogs and private intermediates are deliberately excluded. Maintainers who already possess the exact original and exact verified target can regenerate the distributable delta with:

```powershell
python tools/create_lfx_patch.py ORIGINAL_TRACK_2.bin VERIFIED_TARGET_TRACK_2.bin patch/Langrisser-FX-KR-v0.85.lfxpatch
```

The generator requires NumPy. See [Building and verification](docs/BUILDING.md) for current limitations and consolidation work still needed.

## Fonts and text output

Project records identify GNU Unifont 17.0.05 as the byte-pinned source for the current resident 12×12 Hangul raster. The movie subtitle path uses a separate 12×12 glyph set. Several UI consumers use different physical font resources and mappings, so their code spaces must not be merged. The 8×8 bottom-HUD work references Galmuri7. Font source files are not bundled; the applicable GNU Unifont and Galmuri license notices are retained. See [Third-party material](docs/THIRD_PARTY.md).

## Known issues and limits

- The earlier cumulative tool baseline was not fully green: 8 known failures and 1 known error were recorded. Their resolution is not claimed by v0.85.
- The new Muscle Temple and X2/X3 dialogue passes the recorded technical checks, but full human wording review and all hidden branches remain unfinished.
- An all-scenario playthrough and physical-console/iPhone verification are not recorded for the complete v0.85 scope.
- The v0.85 target was checked through cold SRAM loads for Scenario 12 Angel-versus-Phoenix combat, the Royal Lancer HUD and Scenario 10 combat/results, plus automatic Opening 2 and OMAKE playback. All 629 intervals in the two repaired directories were checked. This is targeted runtime verification and shared-data coverage, not every battle or stage. See [verification](docs/VERIFICATION_v0.85.md).
- Earlier X2/X3 and menu/shop/load runtime evidence remains attributed to its original version. Every natural movie trigger was not replayed for v0.85; current movie/subtitle bytes are unchanged.
- Previously recorded condition-text issues in other internal fields 74–98 were not repaired by this update. Internal field/container counts are not counts of additional playable scenarios.
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

현재 공개 버전은 **v0.85**이며 완성판이 아니라 개발/사전 공개
버전입니다. 시나리오 12 엔젤→피닉스 전투 프리징을 고치고, 같은 원인으로
손상된 공용 자료 경계 1곳도 복원했습니다. 하단 로열랜서 등에 쓰는
‘로’ 글꼴을 기존 Galmuri7 규칙에 맞췄습니다. v0.845 대비 실제 게임 데이터
변경은 92바이트이며 전투 수치·대사·현재 영상 자막 데이터는 유지했습니다.
이전 수정도 누적 포함합니다. 숨은 던전 번역은 기술 검증을
통과했지만 전체 문장 검수와 모든 분기 플레이는 아직 완료되지 않았습니다.
[수정 내역과 검증 범위](docs/RELEASE_v0.85.md)를 확인하세요.
이전 누적 도구 검사에서 기록된 실패 8개와 오류 1개의 해결이나 모든 시나리오
완주 검증을 주장하는 업데이트는 아닙니다.

v0.85는 **원본 일본판에 새로 적용하는 누적 패치**입니다. 이전 한글판에
덧씌우지 마세요. SRAM은 백업한 뒤 게임 내 저장을 불러오고, 이전 버전의
강제 세이브/상태 저장은 사용하지 마세요.

Windows에서는 자동 패처를 실행하여 원본 일본판 CUE와 출력 위치만 선택하면 됩니다. 자동 패처는 세 트랙을 모두 검사한 뒤 별도 폴더에 완성된 한국어판 BIN/CUE 세트를 만들며 원본과 기존 출력은 덮어쓰지 않습니다. 수동 방식에서는 위 표와 정확히 일치하는 원본 일본판 RAW MODE1/2352 Track 2가 필요합니다. `patch/apply_patch.py`는 원본 크기와 SHA-256을 먼저 검사하고, 새 출력 파일만 만든 뒤 결과 전체 SHA-256을 다시 검사합니다.

공개 소스는 편집기 및 이번 수정의 구현을 보여 주는 선별본입니다. 비공개 빌드는 원본 일본판과 고정된 v0.81 누적 패치 명세에서 시작하지만, 원본 추출 표 등 일부 의존 자료가 공개본에 없으므로 완전한 단일 명령 소스 빌드는 아직 아닙니다. 원본 게임 데이터와 세이브는 공개하지 않습니다. [빌드 문서](docs/BUILDING.md)와 [공개 감사 보고서](docs/PUBLICATION_AUDIT.md)를 확인하십시오.

프로젝트에서 직접 작성한 코드·스크립트·문서와 한국어 번역 기여분은
기여자가 보유한 권리 범위 안에서 MIT 라이선스로 공개합니다. 이 라이선스는
원작 게임 데이터·상표·제3자 자료에는 적용되지 않습니다. 자세한 범위는
[LICENSE_SCOPE.md](LICENSE_SCOPE.md)를 확인하십시오. 소유한 정품/합법 덤프에
개인적으로 패치를 적용하고, 원본 또는 완성된 게임 이미지를 재배포하지
마십시오.
