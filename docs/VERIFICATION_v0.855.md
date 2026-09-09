# v0.855 verification and limits

This report concerns internal successor293. It separates final-product data
checks, real installer readback and targeted emulator evidence from untested
branches. This is a development/prerelease review candidate.

## Artifact identity

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Supported original raw Track 2 | 755,535,312 | `1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0` |
| Result raw Track 2 | 762,048,000 | `6E6DE32054CE408BF3F91843E0C0D4645955C2E24E7E34A4810523B623204F5D` |
| Cumulative v0.855 delta | 5,001,308 | `647709FAC73C9DDB66E51AAB2D023A7429CF867DB066CBD0C5F756ABB98FBD13` |
| Windows v0.855 automatic patcher | 16,659,058 | `1F007B210168D6941726A08BC6361E401010C2BC55B2DBE69597E552E90958EA` |

The delta has 694 source-verified chunks. The final cooked image hash is
`C64F6D16EC6BAC1E3102D4387AF1B30B5FF70F3615D26B1E45E5E9D75ACD41B3`.
The release ZIP has its own adjacent `.sha256` file and per-member checksums.

## Final data and page-contract checks

- Compared with the last private reviewed build 292, exactly **two cooked
  bytes** change: the direct `가` → `이` glyph in S15/022. Its expanded result
  equals the saved maintainer text. No new glyph or pointer relocation is used.
- All other 143 S15 records, its dictionary, boundaries and the rest of the
  complete cooked image are identical to 292. The selected line retains one
  page and three lines; measured widths are 112, 104 and 140 pixels against
  a 168-pixel limit. Original dynamic-name/control order is preserved.
- S13's 174 records / 243 pages and S14's 104 records / 125 pages were checked
  again in the final 293 artifact: selected text, original page/wait and
  page-local dynamic tokens, glyph coverage, layout, compression/expansion,
  pool boundaries and zero tail. Their pools equal their accepted predecessor
  review artifacts byte-for-byte.
- Compared with public v0.851, exactly **10,129 cooked bytes** differ, all
  inside the S13/S14 dialogue pools or the selected S15 glyph. Every byte
  outside these scopes was compared. Shared dictionaries/fonts, conditions,
  UI, code, battle data and subtitles are unchanged.
- Final raw-disc checks covered all **324,000 sectors**, including exact
  planned payloads and derived EDC/ECC. The cumulative composed-build audit
  reports 399 repaired existing sectors; this is not 399 new S15 changes.
- The editor's saved personal input was hash-checked before and after the work
  and was not overwritten. The selected edit was pinned separately.

## Actual emulator routes

The final 293 product was cold-booted with the native stage-select cheat into
S14. Controller input reproduced the already verified Japanese/292 route:
deployment, natural movie transition, dialogue records **000–010 / 13 pages**,
and first-turn input. Captured dialogue buffers matched the exact final disc
records; all 13 captured pages and the two final input captures were
pixel-identical to 292. No RAM modification or imported emulator state was
used in this acceptance run. The stage-select cheat bypasses earlier campaign
progression; this is not an uninterrupted campaign playthrough.

Earlier S13 evidence covers 14 introductory records / 20 pages on its reviewed
291 artifact against the Japanese original. The corresponding final 293 pool
and shared consumer are unchanged; this is retained evidence plus final byte
identity, not a claim that all 243 pages were replayed this time.

For **S15/022**, final data/control/glyph checks passed and 293 cold entry into
S15 preparation was exercised, but the edited confession event itself was
**not reached in this pass**. Its in-game event/branch is not claimed as
runtime-verified. The public review candidate keeps that limitation explicit.

Emulator evidence used the existing Beetle PC-FX/libretro route on Windows.
Core SHA-256:
`97CFF6E559237A6528D823D850C3718AE92EE58713895A3719668F8BC53AD43A`.
The user-supplied BIOS, save files, states and private captures are not bundled.

## Installer and regression checks

- The Python automatic applier and the freshly packaged Windows EXE were each
  run against the supported original Japanese CUE into separate new folders.
  Independent readback verified the entire resulting Track 2 hash/size,
  unchanged Track 1/3 hashes/sizes, generated CUE and each output checksum.
- **11 public synthetic tests passed**: patch round trips/rejection, CUE/output
  preservation and native archive boundary checks.
- **9 focused private dialogue tests passed**: original page/name contracts,
  overflow and malformed control rejection, and the S15 exact-token write.
  These do not replace or claim to fix the historical cumulative suite.
- Packaging uses an explicit allowlist, CRC/readback and member hashes. The
  selected source copies, canonical Git-blob manifest, old archive identities
  and privacy scan are checked separately before publication.

## Not claimed

No all-branch/all-scenario playthrough, completed hidden-dialogue human review,
physical-console/iPhone validation, or resolution of the previously recorded
8 cumulative test failures and 1 error is claimed. Previous versioned runtime
reports remain attributed to their original artifacts. Fixed default-name
particles do not add a new automatic particle-selection system for renamed
characters.

한국어 요약: 13·14화 일본판 페이지 규칙과 최종 데이터, 자동 패처 두 방식의
실제 적용을 검사했습니다. 새 293 빌드에서 14화 도입 13페이지와 첫 턴을 다시
확인했습니다. 15화 수정 대사 자체의 이벤트 재생은 이번에 확인하지 못했으며,
저장 문구와 최종 데이터의 일치·글꼴·제어문 보존을 검증한 상태로 공개합니다.
