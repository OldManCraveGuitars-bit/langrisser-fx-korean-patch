# v0.86 verification and limits

Internal successor296. This report separates final-disc checks, finite machine
tests, real installer readback and targeted controller/emulator evidence.

## Artifact identities

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Original Japanese raw Track 2 | 755,535,312 | 1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0 |
| Result raw Track 2 | 762,048,000 | 15741244E1291043884EA2E944EA2D1BE21521719DB42529CD0F984B7B906372 |
| Cumulative v0.86 delta | 5,002,360 | B2403E8E18AB73920963B4A6E43D89E844CD00719D72B63BB043B832E32BAD05 |
| Windows v0.86 automatic patcher | 16,659,470 | EB2942B57AB66A81AA11E365A26ECEC3878FA30C5CAEDA1FB83640697A126F96 |

The cooked image hash is
61C0BA87882C7EB77C391AB06A0D5A900F86FAC99540FAE77E92B6B949D17E4F.
The delta contains 696 chunks. The ZIP has an adjacent checksum file and
per-member checksums; it is not the same artifact as the patched Track 2.

## Final data checks

- S17: all 129 native records checked against Japanese controls, adopted Korean
  text, glyph coverage, layout, compression/expansion and ordinal boundaries.
  Twenty-eight records change. The 3,320-byte pool uses 2,978 bytes.
- All Japanese page/wait/name sequences are preserved. The page-model sum of
  144 includes three originally empty slots; those are not claimed as spoken pages.
- S15: the exact saved 116/131 edits retain 4/2 Japanese pages and name controls;
  the other 142 compressed records remain unchanged from v0.855.
- Compared with private successor294, exactly **4,162 cooked bytes** differ,
  confined to S17 dialogue and the same 768-byte native function in two mirrors.
  Every other cooked byte was compared, including all shared dictionaries/fonts,
  menu/condition data, other dialogue, battle data and movie/subtitle resources.
- Compared with public v0.855, exactly **5,546 cooked bytes** differ: the same
  S17/function scope plus the selected S15 pool. Every byte outside those
  ranges is identical to that public release.
- Both V810 codecs check whole instructions. Relative branches are relocated;
  the native dispatcher is unchanged. Checks reject control-flow references into
  relocated interiors and confirm the original function allocation.
- All 78 installed name endings and 105 physical name replicas were checked
  for the same particle decision. A finite machine runner tests 2,765
  name/item inputs, correct forwarding, internal-space preservation, terminal
  blank trimming and absence of source-string writes. It is not an all-item
  gameplay claim: the native producer installs item 14.
- A separate old/new machine-effect comparison covers 3,360 inventory/recipient
  configurations, checking game-data writes, relevant native call arguments,
  and restored callee-saved registers. External native calls are modeled;
  actual event playback is checked separately below.
- The primary build applies immutable-preimage, nonoverlap, protected-range,
  final-byte and raw MODE1 EDC/ECC checks. There is no new font or code-cave owner.

## Actual emulator evidence

Elwin and Sherry each killed Rouga from the supplied Scenario 17 save. Both
routes showed the separate Necklace acquisition, the subsequent death dialogue,
and the corrected equipment notice with their actual recipient and particle.
The equipment field changed to item14 (Holy Rod), and control returned to the
field after dismissing the notice (and Sherry's normal level-up message).
Elwin's preceding “Rouga…” line remains; Rouga's following line shows only
ellipses. Screenshots and saved RAM were bound to the final function bytes.

The final disc was cold-booted with the supplied in-game SRAM save. Retries use
only states created by this same final build. No memory edits, position/HP cheats
or cross-build emulator states are used. The blocking mercenary is moved away
with normal controller input before the attack.

The before images are from successor294. A separate Japanese-disc comparison
confirmed Rouga's ellipsis-only line. That Japanese comparison used the supplied
Korean-produced SRAM; it does not establish how a fresh Japanese campaign behaves.
All screenshots are unedited actual outputs, not generated mockups.

## Installer and distribution

The Python CUE installer and the actual packaged Windows executable were each
applied to the supported original in separate new output folders. Both reported
success and retained source/existing-output protection. All three resulting
track files were then compared byte-for-byte with the expected final Track 2
and unchanged original Tracks 1/3. Both complete CUE sets passed readback.

Eleven public patch-container/CUE/boundary tests pass. The ZIP uses an explicit
file allowlist, member SHA-256, CRC and byte-for-byte readback checks. Its archive,
screenshots and canonical source manifest are checked before publication.

## Limits retained

Only Elwin and Sherry are requested for gameplay verification, not every
possible recipient. Arbitrarily player-renamed names are not certified for
automatic particles. This formatter is the native Holy Rod transfer event,
not a generic replacement for all acquisition/equipment messages.

S17/112 remains unchanged pending actual speaker confirmation. The three
originally empty slots 126–128 retain their existing contents pending consumer
context. Not every S17 branch or the newly selected S15 events was replayed.
Hidden-dungeon full wording review, all-scenario playthroughs and physical-console/
iPhone verification remain incomplete. The earlier cumulative tool baseline's
8 failures and 1 error are not declared resolved by this release.

This is a maintainer-authorized development prerelease for continued testing.
