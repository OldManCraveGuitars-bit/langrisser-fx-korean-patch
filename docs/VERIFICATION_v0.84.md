# v0.84 verification scope

## Artifact identity and application

| Object | Bytes | SHA-256 |
| --- | ---: | --- |
| Supported original raw Track 2 | 755,535,312 | `1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0` |
| Final raw Track 2 | 762,048,000 | `2907E3B635BBF95B0A6C0834EE71B61DF708E30B9606FC77914A4377884004EC` |
| LFXPAT01 delta | 5,001,535 | `C3DAB7C1FE127BF3119A3CD04E4628072BDA6D5ACF0616B39CA7AC2FAB75ABFE` |
| Automatic Windows EXE | 16,659,045 | `CF0AEFC85DB9351FF283552756D7F5787B7A613B3A9A5DABC0815CB16008254F` |

The delta has 694 ordered compressed replacement ranges, including file growth.
Its input is the supported original Japanese raw track, not an earlier Korean BIN.
Its output is byte-identical to the private runtime-verified development build 283.
The cooked projection hash is
`1A7E41BD30E22DE3705E9198BB28ADAA7151CD1458C497F61D0DB586B51F8205`.

- Python automatic CUE application: PASS; creates a separate complete disc set.
- Packaged EXE `--apply-cue`, using its embedded delta: PASS, exit 0.
- Both produce the exact final raw Track 2 hash above.
- Unchanged audio Track 1: `1E1840205CE98F5E0DF8067BEA8B3336DB62CA071C7B67538A0312C267D9CFA9`.
- Unchanged audio Track 3: `9D1133A7DDAB061567F6C83F3342C90CBE32DC6A94561AE5309FA74335FDDD8D`.
- Five public synthetic installer/container tests pass: sparse/growth round trip,
  wrong-source rejection, CUE parsing, verified separate output and overwrite refusal.
- EXE CLI verification uses the same installation logic as its GUI; it is not a
  new manual GUI-button walkthrough. No command file is needed on the game device.

Tooling: Python 3.13.15, PyInstaller 6.16.0, contributed hooks 2026.7, Windows x64.

## Final game-data checks

The private builder reconstructs the pinned v0.81 specification from the original
Japanese media, composes every expected write before applying it, rejects overlaps
and unknown preimages, and checks the complete final cooked/raw difference.

The X2/X3 step changes 15,084 cooked bytes relative to the preceding build 282.
Everything else is identical at the disc-byte level; all other 96 field-resource
text/script regions remain byte-identical. All 324,000 raw sectors are compared
with unchanged bytes or declared EDC/ECC regeneration for the 39 changed sectors.
These are structural denominators, not counts of playthroughs.

- X2: 97/97 native dialogue records decode exactly to the selected Korean text.
- X3: 148/148 records decode exactly, including two original empty slots.
- All 245 records pass the current glyph, layout, original page/control/name and
  ordinal checks. Compression is lossless; quiz option order is preserved.
- Both new condition tables contain the native eight rows, including empty rows.
- Ten new Hangul cells are appended in reserved gaps in all 15 full font replicas.
  Existing atlas cells, F8 safety clone, matchup table and continuation instructions
  are unchanged. All 11,270 previous valid two-byte glyph inputs retain their
  previous renderer destination and glyph address; this is not a whole-CPU test.

Earlier steps included in this cumulative version:

- Muscle Temple conditions use only the bounded native condition/presentation
  region, preserving other fields and shared dictionaries.
- Scenario 7 changes exactly the four selected dialogue records (187, 189, 193,
  200); the other 238 records and data outside that pool remain unchanged by that step.
- The load-X repair changes only 40 bytes in ten menu replicas, preserving the
  native X bitmap, executable code and save data. The Japanese title menu shows
  `22`, while the in-game load menu uses `X1`; that distinction is retained.

## Recorded runtime routes

The final target uses the pinned Beetle/Mednafen PC-FX libretro core, SHA-256
`97CFF6E559237A6528D823D850C3718AE92EE58713895A3719668F8BC53AD43A`.

- X2: supplied SRAM, ordinary load and sortie, translated introduction and field.
- X3: native title LOAD cheat selector 73, forced deployment and ordinary sortie,
  translated introduction and field. Selector 72 was separately confirmed as X2.
- Both routes have no RAM edits or state loads. Actual resident dictionary,
  dialogue and condition bytes match the final disc.
- Conditions opened three times per dungeon; one Cancel returned to the system
  menu. The victory and dynamic-protagonist defeat text were visually checked.
- Regression routes from the same cold SRAM/controller inputs match 282 exactly:
  12 combat, 2 shop and 24 load-menu screenshots, with identical logged frame,
  command and battle-memory outcomes. These 38 captures are bounded regression
  evidence, not an all-scenario or all-font lifetime guarantee.

### Separate diagnostic, not normal gameplay

One isolated same-build state was used to replace one unconsumed dialogue record
in test RAM with eleven glyphs. All eleven rendered 12×12 masks match the declared
font exactly, including the new segmented-storage paths and the existing `닝`.
The first capture attempt lacked a produced video frame and is not counted as a pass.

The diagnostic Imelda gibberish screenshot is **not included** in game text, patch
data or this release package. The actual X3 Imelda line remains:
`이런 곳에 대체 / 뭐가 있다는 건지‥‥.` The source and final disc hashes were checked
again after the diagnostic. This experiment proves this renderer path, not normal
gameplay of every later event using those characters.

## Scope limits and evidence ownership

Private evidence index: `successor283-final-verification.json`. Earlier boundary
and selected-edit reports remain separate. Eight focused private codec/font tests
pass; they are not a claim that all historical project tests pass.

Full human wording review, every quiz choice, combat dialogue, hidden item and
ending/failure branch remain incomplete. Other internal fields 74–98 retain
previously recorded condition-text issues outside this change. The older tool
suite failures are not retroactively declared fixed. No new physical PC-FX,
iPhone, automatic-opening or every-natural-movie-trigger run was made for v0.84.
Earlier movie evidence remains attributed to its original version.

Publication with these limitations is explicitly approved in
[PUBLICATION_v0.84.md](PUBLICATION_v0.84.md). It does not change translation units
to fully reviewed. No original media, BIOS, emulator, save, memory dump or private
screenshot is included. Packaging uses an explicit allowlist, member checksums
and CRC checks; application must reproduce the exact runtime-verified target.
