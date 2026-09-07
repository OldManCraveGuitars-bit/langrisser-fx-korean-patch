# Building and verification

## Player-facing patch application

Use the Windows automatic patcher with the **original Japanese CUE**. It
validates all three original tracks, creates a staging directory, applies the
cumulative Track 2 delta, copies unchanged audio tracks, writes a fresh CUE and
checksums, and exposes the finished directory only after verification. Original
files and existing outputs are never overwritten.

Python fallback (standard library only):

```powershell
python patch/apply_patch.py ORIGINAL_TRACK_2.bin Track-2.KR.bin --patch patch/Langrisser-FX-KR-v0.825.lfxpatch
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
6.16.0. It embeds the v0.825 delta and outputs
`release/windows-patcher/Langrisser-FX-KR-Auto-Patcher-v0.825.exe`.
The tooling build packages the installer; it does not rebuild the game.
Python 3.13.15 and contributed hooks 2026.7 were used for this EXE.

## Patch-container and installer tests

```powershell
python -m unittest discover -s tests -v
```

Five synthetic tests need no copyrighted game files. They cover sparse/growing
round trips, wrong-source rejection, CUE parsing, complete separate output,
and preservation of an existing output marker.

## Regenerate the cumulative delta

Maintainers must supply the supported original and the exact verified target:

```powershell
python tools/create_lfx_patch.py ORIGINAL_TRACK_2.bin VERIFIED_TARGET_TRACK_2.bin patch/Langrisser-FX-KR-v0.825.lfxpatch
```

The generator requires NumPy; the applier does not. The output must be new.
The format records source/target representations, sizes and SHA-256 identities.
Apply the delta back to the original and compare the whole result with the
verified target; command success alone is not sufficient.

The v0.825 target hash is
`657F36173A2A1518D0440B4E95C67883C70378D7848C58AD4E620FF44777DA44`.
Both Python and packaged EXE application were verified against it.

## Package the release

After verifying the delta and EXE identities recorded in the packaging script:

```powershell
python tools/package_public_release.py
```

This creates `release/Langrisser_FX_Korean_Patch_v0.825.zip` using an explicit
allowlist, stable ZIP metadata, member checksums and CRC verification. It
refuses an existing ZIP. Existing releases remain unchanged. No game image,
save, BIOS, emulator, extracted media or private evidence is allowlisted.

## Full game product build: current boundary

The selected source snapshots are inspectable implementation code, not a
complete publicly runnable game authoring pipeline. See
[implementation notes](IMPLEMENTATION_v0.825.md) for the new modules.

The private primary builder `build_gel_gather_display.py` starts with original
Japanese Track 2 and the fixed public v0.81 delta (SHA-256
`AD05ACECDFEA7EC2B3E49D8FD82B74D189E789C7EB645955FA0608C5C2B07511`)
as its cumulative implementation specification. It reconstructs the baseline
within that invocation; an old fully patched game output is not a build input.
It then derives the composed expected writes for labels, movie lifecycle,
condition boundaries, hidden dialogue, the two user edits and font normalization
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

See [v0.825 verification](VERIFICATION_v0.825.md) for artifact identities,
application checks, actual consumer routes and limitations. The new hidden
dialogue retains a needs-human-review state; successful encoding, font and
runtime checks do not certify every sentence.

Historical reports and v0.81 source/patch material are kept as history. The
v0.81 verification and release documents still describe v0.81, not this target.
