# v0.86 implementation notes

Internal product: successor296. The primary builder reconstructs the pinned
v0.81 specification from the immutable supported Japanese disc, then composes
all adopted writes. Prior patched game outputs are comparison evidence, not inputs.

## Scenario 17 review

The new S17 module owns the existing 3,320-byte ordinal dialogue pool at cooked
0x1A9B58–0x1AA850. It preserves the dictionary, 129 ordinals, every Japanese
page/wait/name control, unchanged compressed records and zero tail.
The final pool uses 2,978 bytes. Twenty-eight records change; no font is added.
The three originally empty slots remain separately identified and are not
counted as spoken Japanese pages. The Korean-only adopted selection is public;
extracted Japanese catalogs and full private review evidence are not.

## Equipment-message cause and scope

The native item-14 transfer selects its recipient from the actual combat context.
It prepared two dynamic arguments, but the selected common message consumed only
one name marker. The recipient was consequently displayed where the item should
have appeared. The item itself was transferred successfully.

The repair builds this one event's message from the actual recipient (+0x37)
and equipment (+0x38), using the native name and item resolver. Default-player
parameter zero retains the native player-name-buffer rule. A finite name mask
selects 이/가. Both name and item are copied into the existing transient text
buffer, trimming terminal F1E6/F1E8 blank cells while preserving internal spaces.
Byte accesses avoid unaligned halfword writes. Source strings remain unchanged.
The producer still installs item 14; this is not a general all-item grammar engine.

No new code cave, font slot or resident allocation is introduced. The repair
stays inside the native 768-byte function at RAM 0x2D0F8–0x2D3F8 and its existing
disc mirror. Nine sign-safe constant-load pairs are compacted. Three basic
blocks reuse an already-calculated RAM address; only dead volatile registers
differ at their joins. An immediately redundant AND mask is removed.
All relative control-flow destinations are re-encoded, with instruction and
branch/data boundaries checked by two V810 codecs.

The final machine-code end is 0x2D3E0, followed by a 14-byte suffix and 10-byte
particle mask, exactly within the original function extent. The native dispatch
entry remains unchanged. Finite instruction-effect checks compare game-data
writes, external call arguments and restored ABI across 3,360 old/new cases.
They are complementary to, not replacements for, the recorded emulator routes.

## Scenario 15 and public source

S15/116 and S15/131 are copied exactly from the separately pinned maintainer
selection. The writer composes them with the earlier S15/022 correction under
one pool owner. Original page/name controls and the other 142 compressed records
are retained. The public Korean-only selection excludes the personal editor file.

The curated source modules retain their private-development imports and input
identities for traceability. Source-derived catalogs and historical authoring
dependencies remain excluded; the public tree is inspectable, not a standalone
full-game authoring build. Original disc plus the cumulative delta is the supported
public route to the exact verified target.
