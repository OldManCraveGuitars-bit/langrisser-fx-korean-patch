# Selected v0.825 implementation sources

These are project-authored source snapshots from the private cumulative build,
not a claim that every imported authoring dependency is included. Internal
development IDs are preserved in code and evidence; public packages use v0.825.
See [Building](BUILDING.md) for the original-disc injection and dependency boundary.

| Public source | Responsibility |
| --- | --- |
| `src/dialogue_editor/gel_gather_labels.py` and `.json` | Approved full/compact character names and class label; common replicas and HUD references |
| `src/dialogue_editor/subtitle_movie_lifecycle.py` | Common native movie-entry/exit subtitle latch handling |
| `src/dialogue_editor/condition_menu_boundaries.py` | Native NUL-record menu boundaries and protected presentation extent |
| `src/dialogue_editor/condition_core.py` | Keep native-indexed empty condition rows during future editor reinsertion |
| `src/dialogue_editor/muscle_temple_dialogue.py` | Hidden dialogue ordinal codec, capacity checks, dictionary and font routing |
| `src/dialogue_editor/muscle_temple_dialogue_successor278.json` | Korean-only hidden dialogue draft; review marker deliberately retained |
| `src/dialogue_editor/selected_user_dialogue.py` and `user_dialogue_edits_successor278.json` | The two exact saved Scenario 2/6 edits and input identity |
| `src/dialogue_editor/font_policy_12x12.py` | Semantic ownership for legacy PUA/name slots and protected split-word columns |
| `src/patch_pipeline/build_gel_gather_display.py` | Cumulative original-disc + pinned delta build, write composition and raw-sector verification |

The Korean draft and selected edits are authoring data, not complete extracted
Japanese scripts. Referenced extraction baselines, runtime screenshots, SRAMs,
memory dumps, original fonts/media and private editor backups are intentionally
not copied. The old `data/translations/사용자_대사수정.json` remains a historical
public editor snapshot; the two later edits are explicitly selected by the new
manifest rather than silently rewriting that historical file.

## Important consumer boundaries

- Detailed character name `겔 게더` and class `겔게더` are separate decisions;
  compact lower-HUD/battle name `겔게더` is deliberate.
- Subtitles follow common physical movie entry/exit, not a per-save unlock or
  a prerequisite OMAKE visit. Representative automatic openings were exercised;
  every possible natural trigger was not individually replayed.
- The condition-menu repair restores the caller's empty-row boundary contract.
  It does not replace the native menu code or shorten the live condition text.
- Hidden Muscle Temple is native resource 71, reached by the reported Scenario
  22 route. It lies outside the historical editor's ordinary 1–70 catalog.
- Twelve logical name glyph slots and Hangul columns in fifteen split cells
  are regenerated in both MAIN copies. The final font step changes only 700
  cooked bytes; other font sizes, sprites, text codes and combat data are protected.

## Review and evidence ownership

The private original build report remains a non-distribution technical-review
record. It is not rewritten to imply human approval. Public release status and
accepted review limitations are recorded separately for v0.825. A later wording
change must revalidate its code, glyph, page and consumer constraints.

No source game image, BIOS, audio/video, private save or credential is required
in Git history. The retained v0.81 delta is a pinned cumulative specification,
not an invitation to distribute a fully patched image.
