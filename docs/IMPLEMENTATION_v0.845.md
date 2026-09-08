# v0.845 implementation notes

This is an inspectable source snapshot, not a standalone public game-authoring
build. Source-derived catalogs, full editor snapshots and runtime state evidence
remain private. The public reproducible operation is original Japanese disc plus
the cumulative delta, producing the exact target in the verification document.

## Selected Scenario 8/9 dialogue

`src/dialogue_editor/scenario89_user_dialogue.py` implements the selected four
edits followed by six additional Scenario 9 edits. The final selection comprises
three Scenario 8 and seven Scenario 9 records. The ten Korean texts and their
stable record IDs are published in
`data/translations/scenario89_user_edits_v0.845.json`; full private snapshots and
original Japanese record dumps are not included.

The implementation checks immutable pool hashes and ordinal populations (116
and 174), encodability, layout, native page/dynamic-name topology and pool capacity.
It re-extracts the final records and requires every unselected record to remain
identical. No glyph or dictionary extension is needed. The public Korean-only
selection is documentation, not a replacement for private pinned authoring inputs.

## Native unit cache and menu ownership

`src/dialogue_editor/menu_unit_graphics_reservation.py` composes the previous
load-X fix with the new menu correction against the same immutable baseline.
The native cache has 46 slots of 9 tiles, spanning `0x8A0..0xA3D` inclusive.
Six menu scatter entries fell inside that range:

| Previous owner | New owner |
| --- | --- |
| `0x96D` | `0xEDA` |
| `0x9AB` | `0xEDB` |
| `0x99B` | `0xEDC` |
| `0x99C` | `0xEDD` |
| `0x9AC` | `0xEDE` |
| `0x9B3` | `0xEDF` |

The writer updates six upload entries and two menu BAT references per Slot A,
and twelve exact settings BAT references per Slot C. Ten copies of each resource
are checked. All 66 menu glyph payloads remain identical. The prior `0xED9` owner
continues to protect the native load-menu X glyph.

Two native loader copies are hash-checked to preserve the allocation rule. The
new destinations have no competing physical BAT consumers in the retained
7,801-state audit. The 24 linear boot/title states referencing those destinations
were checked not to contain Slot A. This is a bounded lifetime audit, not a
claim to have played 7,801 routes or every possible game state.

Compared with the immediately preceding dialogue build, the cooked image changes
exactly 400 bytes across 30 sectors. No executable, glyph bitmap, dialogue, name,
movie/subtitle, audio or gameplay data changes are introduced by this correction.
The native cache's complete 414-tile range is protected irrespective of which
enemy roster fills it; all 98 catalogued field containers remain unchanged.

## Build composition and boundaries

The updated `src/patch_pipeline/build_gel_gather_display.py` adopts both modules
into its expected-write plan. It starts from the immutable Japanese original and
the hash-pinned public v0.81 delta specification, reconstructing the baseline
within the invocation. It retires the earlier ten load-X writes and replaces
them with one composed owner per menu slot; it does not overwrite an already
modified slot with a second unrelated patch. Unknown preimages, undeclared
differences and conflicts fail verification. Changed raw sectors receive EDC/ECC
repair and the remaining raw bytes are checked unchanged.

Internal source identifiers for revisions 284/285/286 are retained for traceability;
the player-facing release and filenames are v0.845. Private audit hashes and
relative evidence references in the source are integrity gates, not bundled data.
See [build boundaries](BUILDING.md) and [verification](VERIFICATION_v0.845.md).
