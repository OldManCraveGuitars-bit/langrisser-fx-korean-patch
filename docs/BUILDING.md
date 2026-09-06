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
`release/windows-patcher/Langrisser-FX-KR-Auto-Patcher.exe`. PyInstaller and the
generated executable are packaging artifacts; they are not required by the
Python command-line fallback.

## Player-facing patch application

The supported public operation is applying the delta patch. It requires only Python 3 and the exact original raw Track 2 listed in the root README.

```powershell
python patch/apply_patch.py ORIGINAL_TRACK_2.bin Track-2.KR.bin --patch patch/Langrisser-FX-KR-v0.8.lfxpatch
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
python tools/create_lfx_patch.py ORIGINAL_TRACK_2.bin VERIFIED_TARGET_TRACK_2.bin patch/Langrisser-FX-KR-v0.8.lfxpatch
```

Requirements:

- Python 3.13 was used for the prepared candidate.
- NumPy is required only by the generator, not by the player-facing applier.
- The output path must not already exist.
- The generator records the source and target hashes in the patch header.

After generation, run the player-facing applier against the original into a temporary new file and compare that file's SHA-256 to the verified target. The prepared candidate passed this exact check.

## Full game product build

The inspected working tree has a large historical successor chain. The newest selected builder is:

```text
src/patch_pipeline/build_successor261_shop_hud.py
```

The filename reflects an internal development-stage identifier. It requires an exact private cumulative directory containing cooked/raw media and supporting payloads. Those inputs are not public because they include a fully patched game product.

Consequently, the public candidate does not provide a working command that rebuilds v0.8 directly from the untouched Japanese disc. The selected source is supplied for technical review and future consolidation, not as a claim of clean full reproducibility.

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

The newest exact report records:

- target Track 2 SHA-256 `E9F3E5D6C6AAD6C15FB554A440F2D8F9D22AE59756D3ABF11E5CF1941D3B04B3`;
- targeted cold-emulator checks for the shop warning and Scenario 3 Hain dialogue;
- separate recorded subtitle checks for Scenario 1 clear/OMAKE and Opening 2;
- 131 tool checks with 8 known failures and 1 known error;
- no all-scenario or physical-console/iPhone completion claim.

The public patch reproduces the exact target hash, but patch identity does not expand the runtime scope above.
