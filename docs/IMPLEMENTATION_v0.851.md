# v0.851 implementation

## First incorrect state and repair

The final Korean name starts at MAIN `0x6CC74` with BAT descriptors
`5F28 5F29 5F2A` for Liana. The observed preceding cells at
`0x6CC70/0x6CC72` contain `5380/531A`.
The previous helper at `0x1E3E90` masked the latter to `0x31A`,
classified it in the native digit range `0x312..0x31B`, and kept both
stale cells. The Korean name glyphs themselves were correct.

The replacement checks the actual first private-name BAT (`5F28`) before
the numeric guard. In a name row it clears both prefix cells to `5300`.
Outside that context it preserves the prior numeric policy. The private
name marker is shared by the renderer: no name ID or Liana-specific branch
is added. The fixed field origin, tile allocation and ABI remain unchanged.

The helper grows from 58 to 62 bytes inside the existing reservation ending
at `0x1E3F01`. All 15 copies are source-gated and checked from the output.
Exactly 735 cooked bytes differ from v0.85, entirely inside those helpers;
the complete complement is byte-identical. Raw changed-sector EDC/ECC is
regenerated. Audio tracks remain unchanged.

## Adopted source

- [hud_name_prefix.py](../src/dialogue_editor/hud_name_prefix.py):
  source preimage checks, helper emission, independent instruction roundtrip
  and branch-boundary verification, per-copy planning and final readback.
- [primary builder](../src/patch_pipeline/build_gel_gather_display.py):
  adds `--fix-hud-name-prefix` after the existing native-archive correction
  and checks the cumulative result.

The adopted source is copied from the implementation used for successor289,
not a different display-only patch. The private primary build starts with
original Japanese Track 2 and the pinned v0.81 delta specification, reconstructs
its baseline inside the build, and composes all subsequent writers.
It does not use an old fully patched image as its source.

Use the preceding cumulative options, followed by `--fix-hud-name-prefix`.
The new option requires `--fix-native-archive-boundaries`. Authoring catalogs,
historical helpers and separate font inputs are not all distributable here;
these selected modules are inspectable snapshots, not a self-contained game
build. The supported public reproducible path is the cumulative delta applied
to the exact original. See [building](BUILDING.md).

## Protected consumers

The name-row check has precedence only where a private name is rendered.
SCENARIO/TURN, classes, stats and other fields keep their prior locations.
All 167 native name IDs and 333 name/alias post-compose instruction cases
were checked. All 201 glyphs in each of 15 banks were independently compared
to the adopted Galmuri7 BDF; no glyph bytes or name maps changed.

This fix does not alter dialogue, battle arithmetic, movie/subtitle data,
the earlier archive-boundary repair, or the menu/unit-cache separation.
