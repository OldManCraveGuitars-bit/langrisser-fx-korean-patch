# v0.84 publication decision

Decision ID: `v084-public-prerelease-with-pending-hidden-wording-review`.

The maintainer requested the current patch and change history on GitHub as v0.84.
The follow-up question explicitly stated that X2/X3 human wording review and all
branch playthroughs were unfinished, and asked whether to publish a pre-release
with these limitations, as with v0.825. The maintainer answered **네** (yes).

This authorizes the current prepared package as a public **pre-release**. It is
not evidence that every translated sentence was reviewed, that all branches were
played, or that physical PC-FX/iOS behavior was tested. Earlier hidden-dialogue
review limitations remain recorded. The source JSON and private technical build
reports deliberately retain their original needs-human-review/non-distribution
markers; this publication decision is a separate explicit maintainer decision.

- Exact target raw Track 2 SHA-256:
  `2907E3B635BBF95B0A6C0834EE71B61DF708E30B9606FC77914A4377884004EC`.
- Delta SHA-256:
  `C3DAB7C1FE127BF3119A3CD04E4628072BDA6D5ACF0616B39CA7AC2FAB75ABFE`.
- [Changes and unresolved scope](RELEASE_v0.84.md).
- [Artifact and runtime verification](VERIFICATION_v0.84.md).

The decision applies to this exact target and selected wording, not later builds.
Original images, BIOS, copyrighted media dumps, personal saves, runtime diagnostic
screenshots and credentials remain excluded. Older tags and release assets are
preserved. In particular, the RAM-only Imelda glyph diagnostic is not part of the
selected product dialogue or distribution patch.
