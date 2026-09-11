# v0.865 verification and limits

Internal successor297. Static full-population checks, actual controller routes
and installer readback are distinct evidence; none implies an all-branch campaign.

## Artifact identities

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Original Japanese raw Track 2 | 755,535,312 | 1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0 |
| Result raw Track 2 | 762,048,000 | C198548FB9E4288B7DB4D380DECEBD5F1DC77D5CEC1DD37645987A66BEA2C147 |
| Cumulative v0.865 delta | 5,002,388 | EB6D3449219EC764EDBE36962C8E35304F221F35C4B8A4663B0AB99578CCB3F5 |
| Windows v0.865 automatic patcher | 16,658,343 | 0214870EF4219B25834F5BAF52BF608D6CF456B940425D73463E78ACF336F910 |

Cooked target SHA-256:
`556BA8576474D22EEE1C78B6DDEFE0B64039DF08A2661E4D243492652AF2457E`.
The delta has 696 chunks. The ZIP has a separate checksum sidecar and internal
member checksums; its hash is not the resulting Track 2 hash.

## Complete Scenario 18 data audit

- 98 native positions: 96 content entries and two original empty tail entries.
  The final complete pool uses 3,452 of 3,716 bytes. Ordinals 73–96 are no longer
  selected as padding. The original first 72 encoded records are byte-identical.
- Every adopted record matches the Japanese protected controls and page-local
  dynamic arguments. Page geometry, glyph encoding, dictionary roundtrip,
  terminators and final-disc extraction pass. There are no untranslated Japanese
  body characters in the extracted selected population. Latin monster cries are
  deliberate original content, not omissions.
- Exactly five records have content corrections relative to their formerly
  stored bodies: 076, 077, 081, 089 and 091 (zero-based). These restore punctuation,
  correct the interjection and match the original semantic page splits.
- All seven introductory presentation frames (title, five narration frames,
  combined conditions) were compared. Title is `복수`; victory is `소니아 격파`,
  defeat is `엘윈 사망`. The presentation and both condition consumers are
  unchanged from v0.86.
- Six synthetic population/terminator/capacity tests pass. They reject missing
  records, phantom empty content, altered empty tail, embedded NUL and overflow.
- The new 12×12 `흥` cell is identical in 15 full font replicas; all 11,279 prior
  valid glyph routes retain their old target and output behavior. The bounded
  router/dispatcher runner checks 1,693 values. Independent instruction checks
  and final-writer cell checks also pass. Runtime RAM matches the new cell.
- Full cooked-image comparison against v0.86 finds exactly **1,362 changed bytes**,
  all inside the declared S18 dialogue/font scope. Every other byte is identical,
  including other scenarios, S18 code/dictionary, menus, conditions, battles,
  equipment handling and subtitles. The primary build also checks composed write
  ownership, protected ranges and RAW MODE1 EDC/ECC after the final writer.

## Actual controller/emulator checks

The supplied SRAM was cold-loaded separately into v0.86/296, original Japanese
and final297 discs using the same PC-FX core/BIOS. End Turn reproduces the defect.
The Japanese comparison uses this Korean-produced SRAM, not a fresh Japanese
campaign. Retries load only states from the same disc session; no position/HP
cheats, RAM writes or cross-build state transfers were used.

1. **Enemy death:** Living Armor's HP changes from 3 to 0 in the turn route. At
   the death callback, 296 has an empty message buffer and blank box; Japanese
   and 297 display `MU……`. Normal input closes the line and play continues.
   This is an actual missing-death-body comparison, not a forced text preview.
2. **Turn event:** Sonia's restored request, all five Vampire Lord pages,
   Succubus, Sonia's response, Est, Ost and the final Vampire Lord line display.
   The Vampire Lord's five-page sequence is compared with Japanese; the newly
   appended glyph is visible in page four. Play continues into the next turn.
3. **Additional unchanged death regression:** Elwin attacks Est through normal
   movement/attack input. Est reaches HP 0, says `크윽, 강하다‥‥.`, and Sonia's
   following name call appears. This record was already before the bad padding;
   it is a regression check, not one of the newly restored 24 entries.
4. **Menu return:** The S18 victory/defeat menu displays both conditions and
   closes back through the system menu to the field with normal Cancel input.

The user SRAM and personal editor file retain their prior hashes. Screenshots
are unedited 256×240 core captures; provenance and before/after identities are
listed in [the screenshot record](../screenshots/v0.865/README.md).

Recorded core SHA-256:
`97CFF6E559237A6528D823D850C3718AE92EE58713895A3719668F8BC53AD43A`.
BIOS SHA-256:
`4B44CCF5D84CC83DAA2E6A2BEE00FDAFA14EB58BDF5859E96D8861A891675417`.
Neither core nor BIOS is distributed.

## Installer and release checks

Both the Python CUE installer and the actual packaged Windows executable were
applied to the exact supported original in separate new output folders. All
three resulting tracks were compared byte-for-byte: final Track 2 equals297,
Tracks 1/3 equal the originals. Both output CUE files have SHA-256
`7D9FE47C59C73BA66A86B5077D5CB49877B0263CBC94CE95F35CAE1F7FA95799`.

Eleven public patch-container/CUE/native-directory boundary tests pass. The
release archive uses an explicit file allowlist, CRC, internal SHA-256 and
member readback. Source-copy equality, canonical Git-blob manifest, screenshot
identity and document/privacy checks are required before publication.

## Limits retained

All S18 records are statically covered, but not every death actor, conversation
branch, ending choice or introductory scene was individually replayed. Targeted
runtime verification does not certify every battle or platform. Physical-console
and iPhone checks are not recorded for this update.

Earlier hidden-dungeon full wording review, all-scenario playthroughs and
known cumulative tool failures (8 failures, 1 error) remain outside this repair.
S17's ambiguous records, arbitrary custom-name grammar and historical limitations
remain as documented for their original versions. Public source is a curated
snapshot, not a complete standalone game authoring build.
