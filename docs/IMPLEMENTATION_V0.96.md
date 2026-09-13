# V0.96 implementation notes

V0.96 packages the accepted successor302-review5 media without additional game edits.
The private primary path reconstructs 297 and 298 from the supported original RAW
disc plus the pinned v0.81 delta specification, then composes the adopted epilogue,
credits, inventory, super-dialogue and menu changes. Old playable output is not a
product-build input. Expected source bytes, single-writer composition, protected
complements, container/sector integrity and the exact final output are checked.

Key cumulative changes:

- Preserve native whole-pool ordinal streams, original empty entries and protected
  page/wait/name tokens for late dialogue instead of reinserting split prose batches.
- Use the original caller's actual side argument for long battle class names.
- Encode Scott's digit and the super introduction's Latin O as valid native two-byte
  characters; retain record lengths, NUL and page controls.
- Fit credits to the actual 192px consumer using its 12px space behavior; never
  shorten a staff name to make the previous mistaken width model pass.
- Deduplicate only proven identical glyph bitmaps while preserving every existing
  code's pixel result; new super glyphs and the narrowly owned helper use the released bank.
- Protect dictionary dependencies of common section0 consumers as well as dialogue,
  presentation and condition consumers. Fixed buy/capacity phrases do not depend on
  locally reused dictionary entries.
- Translate actual section6 battle condition rows independently of narration. Keep
  the eight native ordinals, empty slots, variable operands and victory event code.
- At B8CC, after the original artwork VRAM upload, native N1/3/4/5 loads restage the
  N2 UI working prefix through the original 8CC0 reader. Artwork on disc and its
  VRAM upload are not replaced. The helper reserves 16 outgoing-argument bytes and
  preserves caller registers/PSW and the displaced return instruction. The rejected
  review3 ABI experiment is not included; final review5 uses the corrected helper.

The final 302-to-301 difference is 19,100 bytes, not the size of the cumulative patch.
The final complete RAW checksum is in [verification](VERIFICATION_V0.96.md).

The curated public source tree is not a full standalone authoring environment;
the newer private planners still depend on withheld source-derived catalogs.
No Japanese extraction catalog or memory dump is added to this release. The
supported public reproducible operation remains original disc + cumulative delta
→ the exact verified three-track result. The public installer, delta creator,
packager and application tests are updated for V0.96.
