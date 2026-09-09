# v0.855 implementation snapshot

The private primary builder still starts with the immutable supported Japanese
Track 2 plus the hash-pinned public v0.81 cumulative delta specification. It does
not use a previously patched game image as its next build input. Expected writes
are planned, source-checked, composed without overlap and verified after the last
writer. Raw changed-sector EDC/ECC fields are derived and verified afterward.

New selected sources:

- `scenario_dialogue_review.py` and `scenario13_review.json`: the existing S13
  ordinal pool, all 174 selected records, original page/wait/name signature,
  glyph and geometry checks, compression/expansion and final pool verification.
  This single pool owner includes the prior one-row duplicate-word correction.
- `scenario14_dialogue_review.py` and `scenario14_review.json`: the same scoped
  checks for the separate S14 pool of 104 records / 125 pages.
- `scenario15_user_dialogue.py`: validates the pinned maintainer selection and
  original S15 source population, then changes only the directly encoded particle
  in record 022. It proves the entire expanded result equals the selected text;
  no repacking, pointer or record-boundary changes are needed.
- `dialogue_wording_corrections.py`: retained predecessor helper/source identity.
- `build_gel_gather_display.py`: composes the new owners after the existing profile.
  The final flags are `--review-scenario13 --review-scenario14 --scenario15-user-edit`.

The public Korean-only S15 selection is in
`data/translations/scenario15_user_edit_v0.855.json`. Private editor snapshots and
Japanese source catalogs are not included. The source modules retain their
private project-relative import/input relationships for inspection; this curated
snapshot is not a complete standalone authoring build. Source-derived catalogs,
some historical modules and separately obtained font inputs remain required.

The source input review markers are historical/development states. The separate
maintainer publication decision designates the verified 293 output as a prerelease
review candidate; it does not pretend that all localization has received final
human review. See [publication scope](PUBLICATION_v0.855.md).

Supported public reproducibility remains **original disc + cumulative delta →
exact target**, checked independently with Python and the packaged Windows EXE.
