# Changelog

Dates are omitted where the project records do not establish a single release date. This file summarizes only work visible in the inspected source and verification records.

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
