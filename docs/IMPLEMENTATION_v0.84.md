# Selected v0.84 implementation sources

This supplements [the v0.825 snapshot](IMPLEMENTATION_v0.825.md). It is selected
project-authored implementation code, not a complete standalone authoring build.
Internal development IDs remain in code for traceability; player-facing files
use v0.84. See [Building](BUILDING.md) for missing private dependencies.

| Source | Responsibility |
| --- | --- |
| `src/dialogue_editor/muscle_temple_conditions.py` | Literal native field-71 conditions, dynamic protagonist and bounded presentation slack |
| `src/dialogue_editor/scenario7_user_dialogue.py` and `user_dialogue_edits_successor281.json` | Four selected maintainer edits and preserved source-snapshot identity |
| `src/dialogue_editor/load_x_menu_tile.py` | Separate native X and Korean menu tile owners in all ten registered menu replicas |
| `src/dialogue_editor/hidden_x_dialogue.py` | Complete native X2/X3 ordinal pools, dictionary dependencies, lossless compression and conditions |
| `src/dialogue_editor/hidden_x2_dialogue_successor283.json` and `hidden_x3_dialogue_successor283.json` | Korean authored text; human-review and non-distribution historical markers retained |
| `src/dialogue_editor/hidden_x_font.py` | Append-only segmented storage, glyph routing, prior-input contract and final owner checks |
| `src/patch_pipeline/korean_font_policy.py` | Byte-pinned 12×12 Unifont raster policy; font binary not bundled |
| `src/dialogue_editor/muscle_temple_dialogue.py` | Earlier hidden font verification accepts the explicitly composed later font profile |
| `src/patch_pipeline/build_gel_gather_display.py` | Cumulative primary build composes all adopted writes against one immutable source |

Native fields 72 and 73 are X2 and X3 respectively; they are separate from the
historical ordinary 1–70 editor population. The actual title LOAD cheat was used
to establish this numbering. Their dictionary/dialogue/CN regions were observed
resident from the exact final disc, not inferred from matching metadata alone.

No old atlas cells, F8 clone, combat matchup bytes or continuation instructions
were replaced by the new glyph storage. Ten new cells occupy three bounded gaps;
the existing hidden extension remains where it was. The final image checks all
15 full replicas and both dispatcher copies. Earlier 11,270 valid two-byte inputs
retain their old destination and glyph address. Native runtime rendering was also
checked; the isolated all-glyph diagnostic is not a gameplay-path claim.

Source extraction catalogs, emulator states, screenshots, BIOS and disc images
remain private. The Scenario 7 manifest references a private editor snapshot;
its Korean-only selected values are published separately for inspection in
`data/translations/scenario7_user_edits_v0.84.json`, without claiming that this
curated tree supplies every dependency needed by the primary builder.
