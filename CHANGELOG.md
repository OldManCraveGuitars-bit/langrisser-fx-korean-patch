# Changelog

Dates are omitted where the project records do not establish a single release date. This file summarizes only work visible in the inspected source and verification records.

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
