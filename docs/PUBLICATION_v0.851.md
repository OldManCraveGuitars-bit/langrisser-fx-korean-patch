# v0.851 publication scope

The maintainer explicitly requested publication as **v0.851**, with a correction
report and before/after screenshots. This continues the existing
development/pre-release policy and does not mark pending translation review
or all-scenario testing complete.

## Included

- New cumulative source-gated delta and version-matched automatic patcher.
- Python appliers, installation guide, changelog, correction/implementation/
  verification reports and retained license notices.
- The adopted HUD prefix helper and updated primary-builder source snapshot.
- Exactly two unedited native 256×240 game captures, selected as diagnostic
  evidence for the same Scenario 12 save/input path before and after the fix.

## Excluded and preserved privately

Original/patched BIN/ISO media, BIOS, emulator executables, user SRAM and state
files, RAM/VRAM dumps, extracted graphics/audio/video, private absolute-path
reports, backups and authoring catalogs are not included. Previous versioned
patches, release archives and tags are preserved. The public CUE is only the
reviewed generic patch-output template, not an original game CUE.

The screenshot exception is limited to the two requested evidence images.
They contain original game art, which is not relicensed under MIT. The
maintainer's MIT license applies only to project-owned contributions;
see [license scope](../LICENSE_SCOPE.md).

Publication checks include an explicit ZIP allowlist, checksum/readback checks,
canonical Git-blob manifest, source-file equality, privacy scans, separate
Python and packaged-EXE application to the original dump, and verification
that previous local release archives retain their hashes. Private paths and
save identities are not included in these public reports. Detailed tooling
checks and limitations are in [verification](VERIFICATION_v0.851.md).
