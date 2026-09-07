# v0.825 verification scope

## Artifact identity

| Object | Bytes | SHA-256 |
| --- | ---: | --- |
| Original raw Track 2 | 755,535,312 | `1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0` |
| Final raw Track 2 | 762,048,000 | `657F36173A2A1518D0440B4E95C67883C70378D7848C58AD4E620FF44777DA44` |
| LFXPAT01 delta | 4,994,880 | `729C38A8B5FD5CBDD89B566AF39DE0606D6A50E039405BE7089777C6ECCE7AA2` |
| Windows automatic EXE | 16,653,169 | `2788FE45B03B5061AE6B99F3A0C9B7B9647FA4AAA09AEC84A2CDB4EFE58E9124` |

The delta has 698 ordered compressed replacement ranges and includes file growth.
It is generated from the original Japanese raw track, not an older Korean image.
The target is byte-identical to the private runtime-verified development build 279.
Its cooked projection hash is
`3175CF248760955CCA4DB8944DDE16ED9C4145ADACFA611096CBABBE2F1E241D`.

## Application verification

- Python automatic CUE workflow: PASS, creating a separate complete disc set.
- Packaged EXE `--apply-cue` workflow using the embedded payload: PASS, exit 0.
- Both paths reproduce the final raw Track 2 identity above.
- Tracks 1 and 3 remain the supported originals with hashes
  `1E1840205CE98F5E0DF8067BEA8B3336DB62CA071C7B67538A0312C267D9CFA9`
  and `9D1133A7DDAB061567F6C83F3342C90CBE32DC6A94561AE5309FA74335FDDD8D`.
- Five public synthetic container/installer tests pass: sparse/growth round trip,
  wrong-source rejection, CUE parsing, separate verified output, overwrite protection.
- EXE command-line application exercises the same installer logic as the GUI;
  this is not a new manual GUI-button walkthrough.

Python 3.13.15, PyInstaller 6.16.0, contributed hooks 2026.7, Windows x64.

## Product evidence retained privately

The cumulative private build reconstructs the pinned v0.81 baseline from original
Japanese media, applies a preflighted composed write plan, and verifies all
324,000 raw sectors against unchanged bytes or declared sector regeneration.
The v0.825 cooked target differs from v0.81 at 14,065 bytes.

The final font-only change relative to development build 278 changes 700 cooked
bytes in 54 cells across both MAIN copies, and four raw sectors with independently
checked MODE1 EDC/ECC. Its protected complement is byte-identical.

Final semantic font-profile audit has zero mismatches across 888 resident
full-syllable cells, 38 split-word cells, 34 compact shop segments, 16,110 global
atlas cells, 15 F8 clones, 165 new hidden-dialogue cells, 120 condition cells and
117 Scenario 2 cells. The name inventory contains 78 records in 105 replicas.
These are structural populations, not counts of distinct playthroughs.

Runtime on the final target, from cold SRAM and ordinary controller input:

- Muscle Temple introduction through field: 27 checkpoints; modified glyphs
  resident at each. Eight changed captures differ only in expected name columns.
- Victory-condition menu: three open/cancel cycles, 16 captures unchanged from
  the preceding verified boundary repair.
- Shop: two captures, including the robe tooltip, unchanged from the preceding build.
- Native combat: 12 captures unchanged from the preceding build.
- Unattended openings 1/2: 18 captures unchanged, including opening-2 Korean
  subtitles. No SRAM or subtitle injection was used for this route.

Runtime core: Beetle/Mednafen PC-FX libretro, SHA-256
`97CFF6E559237A6528D823D850C3718AE92EE58713895A3719668F8BC53AD43A`.
No emulator, BIOS, SRAM, memory dump or copyrighted screenshot is added here.
Private evidence index: `successor279-final-verification.json`; selected source
modules are listed in [v0.825 implementation notes](IMPLEMENTATION_v0.825.md).

## Limits and review status

Technical verification is not human wording approval. The 86 new nonempty hidden
dialogue records retain a needs-human-review status. Full hidden branches,
all-scenario playthrough, every natural movie trigger, iPhone and physical PC-FX
execution remain outside the recorded final-target runtime coverage.

The older cumulative tooling report's known failures are not retroactively
declared fixed. A supplementary historical test discovery in this packaging
session ran 287 tests, skipped 19, and reported one setup error for a missing
old Scenario-header ISO fixture. This is not a v0.825 runtime failure, nor a
claim that the complete historical test suite passes. Public installer tests
are independent of that private historical suite.

Original media, user saves, old release assets and private working files are
preserved. ZIP packaging uses an explicit allowlist and verifies members,
hashes and CRCs. Full game images and private diagnostics are excluded.
