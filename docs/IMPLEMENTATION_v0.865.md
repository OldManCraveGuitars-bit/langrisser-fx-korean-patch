# v0.865 implementation — complete Scenario 18 ordinal stream

The selected source snapshot adds `scenario18_dialogue_repair.py`,
`scenario18_repair.json` and `scenario18_font.py`, updates `dialogue_core.py`,
and composes the new writers in `build_gel_gather_display.py` through
`--fix-scenario18-dialogue`. These retain their actual private implementation
imports; the curated repository is not a standalone authoring environment.

## Cause and bounded repair

The original S18 section at cooked `0x1AFEA8..0x1B0D2C` is a single sequence of
98 NUL-terminated records: 96 nonempty entries followed by two intentional empty
entries. The native E14C selector uses one-based NUL ordinals. It does not use
the historical per-record file offsets.

The old editor excluded ten non-prose entries (eight Latin cries, one name-only
entry and one punctuation-only entry). Separate repacking runs then introduced
NUL padding after the first 72 records. The v0.86 stream consequently had 360
terminators; native ordinals 73–96 selected padding even though later nonempty
translations were still physically present.

The new writer builds the complete population as one pool. Its 3,452 used bytes
fit the original 3,716-byte allocation. It preserves both original empty tail
records and pads only after them. No runtime pointer/selector rewrite is needed.
The initial 72 encoded records remain byte-identical. The content outside the
five explicitly corrected records is preserved while the ordinal structure is
restored. Every record's protected controls and page-local dynamic tokens are
checked against the immutable Japanese source, then the packed pool is read back.

The source and dictionary are hash-pinned. Recovery of later physical records
is limited to this exact known preimage, not a generic deletion of empty strings.
Population, unexpected embedded NUL, empty content entries and overflow fail
closed. Six synthetic tests exercise these acceptance/rejection boundaries.
The editor also retains all 98 positions, preventing the original omission from
being silently reintroduced through its normal complete-pool path.

## Single-glyph extension

The newly needed `흥` uses code `F9DC`, with exclusive upper bound `F9DD`.
Its 18-byte 12×12 cell occupies the reserved final font segment at
`Resource12 + 0x5FEA..0x5FFC` (runtime `0x1E9FEA`). GNU Unifont 17.0.05 and the
existing adopted 12×12 raster policy are used.

All 15 full field-font replicas receive the same cell. The short non-field
resource is excluded. The existing helper's immediate bound and matching
router/dispatcher bounds increase by one; instruction/branch positions and
earlier glyph cells do not move. The previous extension writer is composed once,
not overlaid by independent competing writers.

The final-image audit covers 11,279 previously valid glyph routes and 1,693
router/dispatcher boundary values, plus independently decoded instruction fields,
all replicas and the actual runtime bytes for the new glyph.

## Build and change boundary

The primary product is built from immutable original Japanese Track 2 and the
pinned v0.81 cumulative implementation specification, not from a previous Korean
game image. The new expected-write plan is merged with all prior writers and
verified after the last writer and RAW sector regeneration.

Compared with v0.86/296, exactly **1,362 cooked bytes** differ, all inside the
declared S18 text pool or its font-cell/bound changes. Every other byte is equal,
including other scenarios, shared dictionaries, S18 event code, menu conditions,
unit data, battle rules, prior equipment handling and subtitles.

This exact-diff result bounds unintended data changes. It does not establish
that every possible gameplay branch or platform was exercised.
