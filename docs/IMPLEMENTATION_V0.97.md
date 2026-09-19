# V0.97 implementation notes

The public target is the unchanged approved successor309 media. Internal names
remain V0.96-era development names; the user-facing release is V0.97.

- 303 restores Scenario 5 page-local meaning; 304 applies Scenario 6 review;
  305/306 apply Scenario Select 38/39 review without replacing protagonist variables.
- 307 repairs five shared discard strings in 105 physical copies, using drawing
  spaces and bounded terminators. It preserves two dynamic item-name tokens and
  the 89-byte allocation. Dialogue review also restores source-identical branch copies.
- 308 changes Charm labels from the obsolete glyph code to the installed 참 route.
  108 records/216 cooked bytes change, without changing the original 증 glyph or magic logic.
- 309 changes selected field dialogue pools, and compresses 18 ending speeches into
  their original ordinal pools. External dictionary reference closures, original
  blank rows, page/wait/name controls and the five epilogue tables are protected.
- The epilogue compiler preserves each physical dictionary's route-specific high
  rows. Its invariant is identical epilogue tables and expanded meaning, not identical
  unrelated ending-speech dictionary entries.
- MP notices use native paired M/P codes within the same 11-byte common record.

Selected authored modules and Korean-only review deltas are under
`src/review_v097/` and `data/translations/V0.97/`. These snapshots require private
historical modules, source-derived catalogs and original media; copying them alone
does not create a standalone editor or full game build. No extracted Japanese
catalog, complete game, BIOS, SRAM or RAM dump is included.

The private cumulative entry point is `build_scenario50_ending_successor309.py`.
It reconstructs earlier versions from the original Track 2 and pinned public v0.81
delta, asserts exact predecessor identities, then applies the bounded review layers.
Publication repeats this build independently and compares all five output files.
The public sparse-patch generator/applier and the packaged Windows installer are
tested separately. See [verification](VERIFICATION_V0.97.md).
