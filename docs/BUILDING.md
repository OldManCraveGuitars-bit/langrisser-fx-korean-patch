# Building and verification

## Windows automatic patcher

The player-facing Windows GUI source is
`patch/langrisser_fx_auto_patcher.py`. It accepts the original CUE rather than
requiring the player to identify Track 2 manually. The installer parses the
CUE, verifies the exact supported hashes of Tracks 1–3, applies the Track 2
delta in a staging directory, copies the two unchanged audio tracks, writes a
fresh CUE and checksum list, and renames the completed staging directory only
after all checks pass. Existing output directories are rejected.

Build the single-file executable with:

```powershell
tools/build_windows_patcher.ps1
```

The script creates an ignored local build environment, installs pinned
PyInstaller 6.16.0, embeds the `.lfxpatch` payload, and writes
`release/windows-patcher/Langrisser-FX-KR-Auto-Patcher-v0.81.exe`. PyInstaller and the
generated executable are packaging artifacts; they are not required by the
Python command-line fallback.

## Player-facing patch application

The supported public operation is applying the delta patch. It requires only Python 3 and the exact original raw Track 2 listed in the root README.

```powershell
python patch/apply_patch.py ORIGINAL_TRACK_2.bin Track-2.KR.bin --patch patch/Langrisser-FX-KR-v0.81.lfxpatch
```

The applier:

1. rejects a missing or existing output path;
2. verifies the original size and SHA-256;
3. copies the original to a new output;
4. applies ordered, non-overlapping replacement ranges;
5. verifies the final size and SHA-256;
6. removes only the newly created incomplete output if verification fails.

Use the supplied CUE only after successful hash verification.

## Patch-container tests

The patch-format regression tests use small artificial data and do not need copyrighted game files:

```powershell
python -m unittest discover -s tests -v
```

They cover sparse changes, file growth, exact round-trip output, wrong-source
rejection, absence of a leftover output on failure, CUE parsing, full automatic
disc-set creation, original-file preservation, and existing-output rejection.

## Regenerating the Release delta

Maintainers with both the legally obtained supported original and the exact verified Korean target may regenerate the delta:

```powershell
python tools/create_lfx_patch.py ORIGINAL_TRACK_2.bin VERIFIED_TARGET_TRACK_2.bin patch/Langrisser-FX-KR-v0.81.lfxpatch
```

Requirements:

- Python 3.13 was used for the prepared candidate.
- NumPy is required only by the generator, not by the player-facing applier.
- The output path must not already exist.
- The generator records the source and target hashes in the patch header.

After generation, run the player-facing applier against the original into a temporary new file and compare that file's SHA-256 to the verified target. The prepared candidate passed this exact check.

## Full game product build

The inspected working tree has a large historical successor chain. The public
source snapshot retained from v0.8 includes this final-stage builder:

```text
src/patch_pipeline/build_successor261_shop_hud.py
```

The filename reflects an internal development-stage identifier. It requires an exact private cumulative directory containing cooked/raw media and supporting payloads. Those inputs are not public because they include a fully patched game product.

The v0.81 game target adds the combat/result fixes described in
[release notes](RELEASE_v0.81.md). The historical public pipeline snapshot is not
silently presented as its complete builder. Consequently, this repository does
not provide a working command that rebuilds the whole v0.81 game directly from
the untouched Japanese disc. The selected source is supplied for technical
review and future consolidation, not as a claim of clean full reproducibility.

Required future work for a true public primary build:

1. Identify one authoritative source profile and configuration manifest.
2. Replace successor-to-successor inputs with immutable original-disc injection.
3. Regenerate every Korean text/font/graphics asset from distributable translation data plus licensed font inputs.
4. Register every source-to-target write in one conflict-checked plan.
5. Rebuild cooked and raw representations with sector integrity checks.
6. Generate the delta from the same verified build graph.
7. Run the complete static suite and required runtime routes on that exact artifact.

Until this work is complete, do not describe the selected source snapshot as a one-command source release.

## Recorded verification status

The v0.81 target verification records:

- target Track 2 SHA-256 `033D1813DBD570FDABC4B8A0C53FAC7FA8DBEB5EB484F8ED0421B5B5A59EB594`;
- native Scenario 5 combat/clear/results and Scenario 6 through turn 4;
- targeted checks for the shop warning, Scenario 2 events/turn 7, Scenario 3 Hain dialogue, and 35 item-description records;
- 324 native matchup cells and 1,074 protected private glyph references;
- preservation of the prior movie/font bootstrap, not a fresh complete movie-playback sweep;
- no all-scenario or physical-console/iPhone completion claim.

The earlier cumulative tooling report recorded 131 checks with 8 known failures
and 1 known error. v0.81 does not claim those unrelated failures are resolved.
The public patch reproduces the exact target hash, but patch identity does not
expand the runtime scope above. See [release artifact verification](VERIFICATION_v0.81.md).
