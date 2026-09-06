# Technical architecture

This document separates facts established in the inspected project from remaining publication/build limitations.

## Disc boundary

The supported source is a three-track PC-FX CUE/BIN dump:

- Track 1: audio, unchanged by the inspected latest product.
- Track 2: raw MODE1/2352 data track with `INDEX 00 00:00:00` and `INDEX 01 00:03:00` (225-sector pregap).
- Track 3: audio, unchanged by the inspected latest product.

All current Korean code, text, fonts, title resources, and subtitle runtime data are carried by the patched Track 2. The public delta therefore targets only raw Track 2. The original and target representations are identified by size and SHA-256 before/after application.

The development tooling also uses a cooked 2048-byte-per-sector view. Changed cooked sectors are written back to the raw image and their MODE1 EDC/ECC fields are regenerated. Cooked offsets must never be applied directly to a 2352-byte raw image.

## Text and glyph consumers

The project does not have one universal text renderer. The records and source identify separate consumers with separate physical resources and constraints:

- General dialogue uses a resident private two-byte Korean encoding and dictionary/token processing.
- Narration and victory/defeat presentations use related but independently validated resource layouts.
- Scenario 2 condition codes have reserved ownership that cannot be reused by dialogue compression.
- Item/shop text uses resource-local dictionaries and glyph routing; registered copies are handled as a population rather than by one visible sample.
- Movie subtitles use their own 12×12 glyph set and payload. OMAKE IDs `0–29` and natural-play aliases `36–65` are mapped to the same 30 logical movies.
- The bottom battle HUD is byte-oriented and uses a separate 8×8 renderer for names and classes.
- Title-screen menus and the RAINBOW title image are graphics-resource paths, not ordinary dialogue text.

The current editor validators preserve control tokens such as `{page}`, `{name:XX}`, `{raw:XX}`, and `{dict:XX}`. They separately enforce the widths and page counts recorded for dialogue, subtitles, narration, and condition windows.

## Fonts

The latest project records pin the resident 12×12 Korean raster to GNU Unifont 17.0.05. A separate 309-glyph 12×12 set is recorded for movie subtitles. The 8×8 bottom-HUD builder references Galmuri7. Resource-local glyph maps are deliberately kept distinct because equal byte values do not imply equal glyph ownership across consumers.

Font binaries and generated game-ready glyph banks are not copied into the public candidate. The former need license/attribution review; the latter may contain source-derived layout or binary data. License notices for the current Unifont dependency are retained.

## Current final-stage write path

The selected `src/patch_pipeline/` snapshot contains the dependency closure for the newest final-stage work:

1. A pinned successor260 cooked/raw product is validated by exact hashes.
2. Shop insufficient-funds dictionary writes and bottom-HUD class-map writes are planned.
3. Writes are checked against the immutable successor260 preimage.
4. Overlap is rejected and the complete cooked diff is compared with the registered write set.
5. Only the affected raw MODE1 sectors are rebuilt with EDC/ECC repair.
6. Track 1, Track 3, subtitle payload, and other protected files are required to remain byte-identical at this stage.
7. Static and targeted cold-emulator evidence is checked before the private full-image package is made.

This is a reproducible *final stage*, but it is not yet a public primary build from the untouched Japanese source. Earlier adopted changes are embodied in the private successor260 input. Consolidating the full successor chain into one source-to-product graph is still required.

## Editor boundary

`src/dialogue_editor/` is the current translation-editor code snapshot. `data/translations/사용자_대사수정.json` is a v4 edit delta containing Korean changes rather than a full Japanese extraction. The base catalogs and generated resources required for a complete editor/build session are not published because several reproduce substantial source text or binary game data.

## Distribution boundary

The public `LFXPAT01` patch is an ordered collection of zlib-compressed replacement ranges with a JSON header containing:

- source and target sizes;
- source and target SHA-256 hashes;
- raw-disc representation;
- chunk count and compression parameters.

Application never edits the source. The applier refuses an existing output, validates non-overlap/bounds, and hashes the complete result. The patch was regenerated from the exact original Track 2 and successor264 target and independently applied back to the target hash.

