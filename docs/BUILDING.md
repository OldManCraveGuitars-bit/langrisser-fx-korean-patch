# Building and verification

## Player-facing patch application

Use the Windows automatic patcher with the **original Japanese CUE**. It
validates all three original tracks, creates a staging directory, applies the
cumulative Track 2 delta, copies unchanged audio tracks, writes a fresh CUE and
checksums, and exposes the finished directory only after verification. Original
files and existing outputs are never overwritten.

Python fallback (standard library only):

```powershell
python patch/apply_patch.py ORIGINAL_TRACK_2.bin Track-2.KR.bin --patch patch/Langrisser-FX-KR-v0.86.lfxpatch
```

The applier rejects an unknown source, validates ordered non-overlapping ranges
and the final size/hash, and removes only its newly created incomplete output
on failure. Keep original Tracks 1/3 and use the reviewed CUE template after
successful application. Full CUE-based Python operation is also available:

```powershell
python patch/langrisser_fx_auto_patcher.py --apply-cue ORIGINAL.cue --output-parent NEW_OUTPUT_PARENT
```

## Build the Windows executable

```powershell
tools/build_windows_patcher.ps1
```

The script uses an ignored local build environment and pinned PyInstaller
6.16.0. It embeds the v0.86 delta and outputs
`release/windows-patcher/Langrisser-FX-KR-Auto-Patcher-v0.86.exe`.
The tooling build packages the installer; it does not rebuild the game.
Python 3.13.15 and contributed hooks 2026.7 were used for this EXE.

## Patch-container and installer tests

```powershell
python -m unittest discover -s tests -v
```

Eleven synthetic tests need no copyrighted game files. They cover sparse/growing
round trips, wrong-source rejection, CUE parsing, complete separate output,
preservation of an existing output marker, and six native-directory boundary
acceptance/rejection cases.

## Regenerate the cumulative delta

Maintainers must supply the supported original and the exact verified target:

```powershell
python tools/create_lfx_patch.py ORIGINAL_TRACK_2.bin VERIFIED_TARGET_TRACK_2.bin patch/Langrisser-FX-KR-v0.86.lfxpatch
```

The generator requires NumPy; the applier does not. The output must be new.
The format records source/target representations, sizes and SHA-256 identities.
Apply the delta back to the original and compare the whole result with the
verified target; command success alone is not sufficient.

The v0.86 target hash is
`15741244E1291043884EA2E944EA2D1BE21521719DB42529CD0F984B7B906372`.
Both Python and packaged EXE application were verified against it.

## Package the release

After verifying the delta and EXE identities recorded in the packaging script:

```powershell
python tools/package_public_release.py
```

This creates `release/Langrisser_FX_Korean_Patch_v0.86.zip` using an explicit
allowlist, stable ZIP metadata, member checksums and CRC verification. It
refuses an existing ZIP. Existing releases remain unchanged. No game image,
save, BIOS, emulator, extracted media or private dumps are allowlisted.
Selected actual before/after game screenshots and their attribution are included.
They document the reported defects and are not covered by the project's MIT license.

## Full game product build: current boundary

The selected source snapshots are inspectable implementation code, not a
complete publicly runnable game authoring pipeline. See
[implementation notes](IMPLEMENTATION_v0.86.md) for the new modules.

The private primary builder `build_gel_gather_display.py` starts with original
Japanese Track 2 and the fixed public v0.81 delta (SHA-256
`AD05ACECDFEA7EC2B3E49D8FD82B74D189E789C7EB645955FA0608C5C2B07511`)
as its cumulative implementation specification. It reconstructs the baseline
within that invocation; an old fully patched game output is not a build input.
It then derives the composed expected writes for labels, movie lifecycle,
condition boundaries, Muscle Temple and X2/X3 dialogue, selected Scenario 2/6/7
user edits, selected Scenario 8/9 edits, complete menu/unit-cache separation,
load-menu tile ownership, HUD Galmuri normalization, both native archive
terminal-word repairs, context-aware HUD name-prefix cleanup, font normalization/extension,
the Scenario 13/14/17 dialogue reviews, selected Scenario 15 corrections, and
the recipient-aware Holy Rod equipment formatter
from that immutable baseline. Unknown source bytes, overlap and unexplained
final differences fail the build.

That builder still requires private source-derived catalogs, supporting
historical authoring modules and separately obtained font inputs. They are not
silently bundled here. The new source modules retain their internal development
identities and imports so readers can trace them to the actual implementation;
copying them into this curated tree does not satisfy those missing dependencies.

A fully standalone source build would still need distributable replacements or
source-extraction procedures for those dependencies, a public manifest, and
the same artifact/runtime gates. Until then, the supported public reproducible
operation is **original disc + cumulative delta -> exact verified target**.

## Verification and review

See [v0.86 verification](VERIFICATION_v0.86.md) for artifact identities,
application checks, actual consumer routes and limitations. The new hidden
dialogue retains a needs-human-review state; successful encoding, font and
runtime checks do not certify every sentence.

Historical reports and v0.8/v0.81/v0.825/v0.84/v0.845/v0.85/v0.851/v0.855 patch material are kept as history.
Their versioned verification and release documents describe their original targets,
not v0.86. The separate maintainer publication decision does not rewrite the private
development inputs' needs-human-review or non-distribution historical markers.
