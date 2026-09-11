# Changelog

Dates are omitted where the project records do not establish a single release date. This file summarizes only work visible in the inspected source and verification records.

## v0.865

- 18화 적 사망·턴 이벤트에서 본문이 비던 24개 대사 항목의 참조 순서를 복구.
  내용 96개와 원본의 빈 끝 항목 2개, 영문 괴성·이름·말줄임표를 모두 보존.
- 말줄임표 오염과 감탄사 “홍/흥”을 수정하고 두 항목의 의미상 페이지 구분을
  일본판에 맞춤. 원본 페이지 수·대기·이름 제어는 유지.
- “흥” 12×12 한 칸을 예약된 끝 공간에 추가. 기존 글자나 다른 시나리오 데이터를
  덮어쓰지 않으며 전체 이미지 차이는 선언된 1,362바이트로 한정.
- Original/full-target checks, both installers, whole S18 record coverage and
  targeted cold-load runtime screenshots are documented separately from unplayed branches.
- Cumulative update; v0.86 and all earlier fixes remain included.

[수정 내용과 스크린샷 / Report](docs/RELEASE_v0.865.md) ·
[검증 범위 / Verification](docs/VERIFICATION_v0.865.md).
Development prerelease; remaining wording/branch/platform limitations are retained.

## v0.86

- 17화 전체 129개 레코드를 일본판과 대조하여 28곳의 문구·줄 배치를 수정.
  일본판 페이지·대기·이름 제어를 유지하고, 로우가가 자기 이름을 말하던 오류 수정.
- 로우가 처치 후 잘못된 장비 안내를 실제 수령자 + 이/가 + 홀리 로드 표시로 수정.
  끝 여백은 안내문에서만 제거하며 공용 이름표·글꼴과 장비 이전 규칙은 보존.
- 사용자가 저장한 15화 116번·131번 추가 수정 적용. 이전 22번 수정도 유지.
- Updated the cumulative delta, matching Windows installer, selected sources,
  Korean/English reports and actual before/after screenshots. Earlier releases are preserved.
- Checked 2,765 formatter cases, 3,360 native effect cases and final whole-image
  byte ownership. These finite checks are not an all-character gameplay claim.

[수정 내용과 스크린샷 / Report](docs/RELEASE_v0.86.md) ·
[검증 범위 / Verification](docs/VERIFICATION_v0.86.md).
Development prerelease; remaining wording/branch/platform limitations are retained.

## v0.855

- Applied the maintainer's Scenario 15 dialogue 022 correction: the particle
  after the protagonist token changes from `가` to `이` (default name 엘윈).
  Only two cooked bytes change from the reviewed successor292; all record
  boundaries, the other 143 Scenario 15 records, fonts and dictionaries remain intact.
- Included the Scenario 13 review of 174 dialogue records and Scenario 14 review
  of 104 records. Both preserve the Japanese page/wait/name topology: 243 and
  125 pages respectively. Page-local meaning and Korean phrase breaks were reviewed.
- Included the previously local correction removing duplicate `네가` in the
  Bernhardt confrontation reported during Scenario 12 (stable catalog ID in S13).
- 10,129 cooked bytes change from v0.851, only in S13/S14 dialogue and the selected
  S15 particle. Gameplay, fonts, UI, conditions, subtitle data and audio are unchanged.
- Refreshed the cumulative delta, Windows automatic patcher, selected source and
  bilingual change/verification reports. Previous releases are preserved.

[Correction report](docs/RELEASE_v0.855.md) · [Verification and limits](docs/VERIFICATION_v0.855.md).
This is a maintainer-authorized prerelease review candidate, not a claim of
complete human review, all-branch testing or final localization quality.

## v0.851

- Removed stale native tiles before Liana's 8×8 bottom-HUD commander name.
  The shared helper now checks the rendered Korean name context before treating
  a residual tile as a SCENARIO digit. Applied to all 15 field copies.
- Retained numeric behavior outside name rows. Fonts, name/class records, tile
  positions, dialogue, gameplay and subtitle bytes are unchanged; only 735
  cooked bytes differ from v0.85.
- Checked all 65,536 prefix descriptors in each context, 167 native name IDs,
  333 native/alias executions and all 201 glyphs in every bank.
- Verified cold Scenario 12 name/menu/ground transitions and Scenario 10
  name/SCENARIO transitions. Five failing frames change only 38 prefix pixels;
  every other pixel matches the baseline. This is not an all-scenario playtest.
- Added unedited before/after screenshots, a bilingual correction report,
  refreshed cumulative delta and Windows automatic patcher. Previous fixes
  and previous releases are preserved.

한국어 수정 리포트 및 전후 스샷: [v0.851 release notes](docs/RELEASE_v0.851.md).
Development/pre-release status and existing review limitations remain unchanged.

## v0.85

- Fixed the Scenario 12 Angel-versus-Phoenix freeze: restored a native resource
  directory's terminal word, previously overwritten by an obsolete subtitle
  allocation. The original six-sector read is restored; battle balance is unchanged.
- Found and restored one more directory terminal word with the same confirmed
  data defect. Audited all 629 resource intervals across both directories;
  no separate gameplay freeze is claimed for that second finding.
- Restored the shared bottom-HUD `로` glyph to canonical Galmuri7 in all 15 banks.
  Checked all 201 glyphs per bank. Label spelling, spacing and other glyphs are unchanged.
- Verified cold Scenario 12 combat and map return, the Royal Lancer HUD, and
  Scenario 10 combat/results. All 88 sampled result images match v0.845.
- Rechecked automatic Opening 2 and OMAKE playback: eight matching checkpoints,
  including Korean subtitles. Only 92 cooked bytes change from v0.845.
- Refreshed the cumulative delta, automatic Windows patcher, selected sources
  and a bilingual correction report. Original discs and earlier releases are preserved.

한국어 수정 리포트 및 검증 한계: [v0.85 release notes](docs/RELEASE_v0.85.md).
This remains a pre-release; full wording review and all-scenario playthroughs
are not complete.

## v0.845

- Applied ten selected maintainer-authored dialogue edits in Scenarios 8 and 9,
  including Cherie's informal speech. Preserved unselected records, native page
  waits, dynamic-name controls, existing fonts and section boundaries.
- Fixed corrupted enemy graphics on the Scenario 10 results screen. Moved six
  Korean menu scatter entries and their exact menu/settings references outside
  the complete native unit-cache range, across ten copies of each resource.
- Audited all 46 cache slots / 414 tiles rather than only the reported roster.
  The menu correction changes 400 cooked bytes from the preceding dialogue build;
  executable code, glyph pixels, names, subtitle/audio and gameplay data are unchanged.
- Verified a cold Scenario 10 SRAM route through native combat, clear events
  and results. All 88 sampled result frames matched the original Japanese unit
  graphics for the same roster; lower UI/names matched the preceding build.
- Retained the earlier X1/X2/X3 load-glyph fix and checked settings, victory/defeat
  conditions and one-cancel menu return. Other stages received shared-data checks,
  not a new full-campaign playthrough.
- Refreshed the cumulative patch, Windows automatic patcher and selected sources.

한국어 수정 내역과 검증 한계: [v0.845 release notes](docs/RELEASE_v0.845.md).
Full hidden-dialogue wording review, all branches and physical-device QA remain
unfinished; this continues the project's pre-release status.

## v0.84

- Added missing X2 quiz-dungeon dialogue (97 records) and X3 parody-dungeon
  dialogue (146 nonempty records plus two preserved empty slots).
- Localized their battle-menu conditions: X2 `우키 격파`, X3 `마녀 격파`,
  and the original dynamic protagonist's death condition. Preserved eight-row
  boundaries, quiz option order, original page waits and dynamic-name controls.
- Fixed the Muscle Temple condition text: `적 전멸` / protagonist `사망`.
  Removed the unrelated question fragment and untranslated defeat-condition suffix.
- Applied the maintainer's four saved Scenario 7 dialogue edits unchanged.
- Fixed the corrupted X in the in-game `X1` load label by separating its tile
  owner from the Korean system menu. Kept the title-screen `22` display because
  it matches the original Japanese game; save data and numbering rules are unchanged.
- Added ten append-only 12×12 Hangul glyphs and reused the existing `닝` glyph.
  Preserved the prior font cells, F8 safety clone, combat data and continuation code.
- Verified X2/X3 entry and condition-menu open/cancel cycles. Combat (12), shop
  (2) and load-menu (24) regression screenshots match the preceding verified build.
- Refreshed the cumulative delta, automatic Windows patcher and selected sources.

Full wording review and every hidden branch are not complete. The maintainer
approved publication with these limits as a pre-release, not a final localization.
See [v0.84 release notes](docs/RELEASE_v0.84.md) and
[verification scope](docs/VERIFICATION_v0.84.md).

## v0.825

- Fixed the common movie-entry/exit subtitle state so automatic openings and
  ordinary-play movie callers no longer depend on entering OMAKE first.
- Standardized Gel Gather labels: detailed character name `겔 게더`, class
  `겔게더`, and compact lower-HUD/battle name `겔게더`.
- Repaired victory-condition menu record boundaries responsible for delayed
  opening, corrupt arrows and repeated Cancel presses. Checked all 98 registered
  field containers without rewriting live condition text or the native menu code.
- Added the missing Muscle Temple dialogue (the reported Scenario 22 route,
  native hidden resource 71): 86 nonempty records and one retained empty slot.
  Technical checks passed; complete human wording review remains pending.
- Included the maintainer's two saved dialogue edits in Scenarios 2 and 6.
- Normalized legacy 12×12 Hangul name glyphs, including 삼손, 아돈 and 바란,
  and Hangul portions of split faction-label cells. Kept 8×8 HUD, 16×16 UI,
  intentional compact shop text and non-Hangul columns unchanged.
- Refreshed the cumulative patch, Windows automatic patcher and selected
  implementation-source snapshot. Original Japanese media remain required;
  this is not an incremental patch for an older Korean BIN.

This remains a development/pre-release, not a full-campaign or hardware QA
claim. See [v0.825 release notes](docs/RELEASE_v0.825.md) and
[verification scope](docs/VERIFICATION_v0.825.md).

## v0.81

- Fixed corrupted shared combat matchup data, including the Scenario 6 case
  where monks could not properly damage Gel units. Restored the native Japanese
  matchup values without changing the damage formula or arbitrarily rebalancing units.
- Separated the matchup table from existing Korean font/subtitle startup storage;
  covered both common constructor copies and all 15 complete resident-resource copies.
- Fixed stray graphics on enemy units in the Scenario 5 result screen and the
  unwanted mark beside Rohga's Korean name.
- Corrected `버퀴를 눌러주세요` to `버튼을 눌러주세요` across the registered common message copies.
- Rechecked Scenario 2/3 text and shop warnings, Scenario 5 native combat/clear/results,
  Scenario 6 through turn 4, and all 35 item-description records (two through a
  diagnostic-only catalog substitution). No new Korean text defect was observed
  within those routes; this is not an all-scenario or physical-hardware QA claim.
- Updated the cumulative source-verified patch and Windows automatic patcher to v0.81.

한국어 수정 내역과 검증 한계: [v0.81 release notes](docs/RELEASE_v0.81.md).

## Unreleased — GitHub public-repository preparation

- Added a Windows GUI automatic patcher that accepts the original CUE, verifies
  all three source tracks, and creates a separate ready-to-run Korean CUE set.
- Added overwrite protection, staging cleanup, free-space checks, final Track 2
  verification, and generated checksums to the automatic patch workflow.
- Added a source-hash-gated, sparse zlib Track 2 delta format and dependency-free Python applier.
- Verified that applying the public delta to the exact supported original Track 2 reproduces the newest target Track 2 byte-for-byte.
- Curated the current final-stage patch source, translation editor source, and Korean-only user edit delta into a separate public candidate.
- Excluded original/patched disc images, saves, emulator/BIOS files, extracted media, runtime dumps, and full Japanese text catalogs.
- Added English/Korean documentation, Git ignore rules, rights-risk audit, and third-party notices.
- Applied the MIT License to project-owned contributions under the explicit scope boundary in `LICENSE_SCOPE.md`.

## v0.8

- Packaged the current verified game data with short CUE/track names for device-side testing.
- Added the source-verified automatic Windows patcher and public patch package.

## Current cumulative source build

- Applied the insufficient-funds message fix across the registered shop dictionary copies.
- Restored missing 8×8 bottom-HUD commander class mappings, including the Scenario 3 Morgan/Sorcerer case.
- Retained the cumulative private baseline media/subtitle data outside the owned write ranges.
- Recorded cold-emulator checks for the Scenario 2 shop warning and Scenario 3 Hain dialogue.

## Earlier cumulative work visible in the project

- Added Hangul font resources, private Korean encodings, and consumer-specific glyph mappings.
- Added dialogue, narration, condition, item, shop, menu, title, class, and bottom-HUD text work.
- Added movie subtitle authoring and runtime paths for OMAKE and natural movie IDs.
- Added RAINBOW title-image/resource processing.
- Added raw-sector reconstruction and MODE1 EDC/ECC checks.
- Added translation-editor validation, subtitle timing/reordering/undo support, name-token help, and build reports.

The items above describe implemented work. They do not assert a complete campaign-wide QA pass.
