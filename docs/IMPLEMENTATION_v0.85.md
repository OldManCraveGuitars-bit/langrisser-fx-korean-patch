# v0.85 implementation notes

The selected target is internal successor288. Internal filenames retain their
development identities; the player-facing version is v0.85. These are selected
implementation sources, not a complete standalone public game-authoring build.
See [build boundaries](BUILDING.md).

## Native archive boundary restoration

`src/dialogue_editor/native_archive_boundaries.py` owns the repair. A historical
Opening 2 allocator treated the first zero byte of a terminal little-endian u32
as free space. It was still part of the native directory, not padding after it.

| Native resource | Cooked directory | Intervals | Corrupted terminal | Original terminal | Repaired byte |
| --- | --- | ---: | --- | --- | --- |
| 13 | `0x019FD800` | 555 | `0xBF6FE000` | `0x006FE000` | `0x019FE0AF` |
| 14 | `0x020FB800` | 74 | `0xFF09B000` | `0x0009B000` | `0x020FB92B` |

Resource 14's final entry is selected by the reproduced Phoenix route. Native
code at `0xA570..0xA58E` reads the terminal word at RAM `0x1EF128`, shifts by 11
and subtracts the previous offset. The corrupted value requests `0x1FE006`
sectors instead of 6, leaving the game waiting in the CD read loop. Original
Japanese and pre-fix Korean traces distinguish the first incorrect request.
Restoring only its high byte in a diagnostic RAM experiment allowed the same
fight to finish. That experiment is causal evidence, not a product input.

The product repair restores the two high bytes to zero using exact preimages
and independently hash-pinned Japanese directories. It checks complete u32
records, sector alignment, monotonicity, allocation bounds and the terminal
sentinel. All 629 start/end pairs and every directory word must match the native
source. Whole-image inspection found one copy of each directory and no remaining
corrupted copy. Resource 13 is a confirmed sibling data defect; a separate
gameplay freeze was not independently reproduced there.

Current subtitles use a separate KRAM-staged payload and MAIN `0x1A8118`, not
these obsolete payload starts. Current cues, glyphs and decoder are unchanged.
Native code, resource bodies, damage calculations and matchup data are unchanged.

## Shared HUD font normalization

`src/dialogue_editor/hud_font_galmuri.py` restores only glyph ID 30, `로`, in the
15 active split font banks. The adopted source is Galmuri7 v2.40.4, SHA-256
`2A6FD090AC6D24F7392D6CC49DB02CE54B9D1C01048BF8C97CBCDBC5A885CB15`.
The existing 8×8 cell, ascent 7, seven stored rows and 8-pixel advance are retained.

- Previous rows: `7C047C407C107C`.
- Canonical rows: `7C1C607C10FE00`.
- Six changed rows in each of 15 banks: 90 changed bytes.

Every bank's 201 glyphs is checked against the same canonical profile; the
builder refuses unrelated glyph drift rather than silently normalizing it.
All 197 encoded label records, class/name mappings, palette, renderer and
spacing remain unchanged. This does not rename the existing `로열랜서` label.
Sixteen labels sharing `로` receive the same glyph, including `로열가드`,
`로우가` and `로렌`.

## Build ownership and protected complement

The primary builder adds `--normalize-hud-ro` and
`--fix-native-archive-boundaries` to the complete preceding profile. It starts
from the original Japanese Track 2 and the hash-pinned public v0.81 delta
specification, reconstructing that baseline inside the invocation. A previous
fully patched image is comparison evidence, not a product input.

Both fixes register their complete expected writes against the immutable
baseline before application. Unknown preimages, overlapping owners or an
unexplained final difference fail the build. Final read-back rechecks both
directories and the complete font banks. The new target differs from public
v0.845 by exactly 92 cooked bytes; corresponding changed RAW sector integrity
fields are regenerated. No extra repair is applied after packaging.

The six native-directory contract tests are included in `tests/` and can run
without game assets. Four controlled HUD-glyph contract tests also passed in
the private development tree. Full font/catalog-dependent artifact checks still
require the declared private dependencies; copying the source snapshot alone
does not supply them.
