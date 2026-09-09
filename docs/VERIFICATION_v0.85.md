# v0.85 verification

## Exact artifact identity

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Original Japanese RAW Track 2 | 755535312 | `1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0` |
| v0.85 RAW Track 2 | 762048000 | `3FF464E484B55064BED49C7451E8DDFAEA24896D3819DA3A3EEFBBD443824B0A` |
| v0.85 cooked Track 2 | 663091200 | `7AED47B12F3AB84AF40661170290EAD57AA6CE4B70F0E0C23A126D51BF1D94BA` |
| v0.85 cumulative delta | 5001495 | `ED4E1B06BC466BAF220DC930D41334626AC1D34BA57EA8E06E242CF775C8C939` |
| v0.85 Windows automatic patcher | 16658866 | `64BC89B6682B0189D6B3B5543E5CE152D3F04EB68185753AF367915DED73ACC1` |

Internal target: successor288. The prior public v0.845 comparison target's RAW
SHA-256 is `18652F60B9156BFA40DF8A3A638749D05D0A68898D938A86A2C7A2A38D8A927D`.
Audio Tracks 1 and 3 are unchanged; their identities remain in the installer.

## Static artifact verification

- Exact 92-byte cooked difference from v0.845: 2 archive-boundary bytes and
  90 shared HUD font bytes. The entire remaining cooked complement is unchanged.
- All 324,000 RAW sectors checked; 17 sectors changed with valid projection and
  EDC/ECC. No unplanned RAW changes.
- Both complete native directories match Japanese, covering all 629 intervals.
  One copy each; zero remaining corrupted copies in the full-image scan.
- All 15 HUD font banks checked, 201 glyphs per bank, only `로` changed.
- All 98 catalogued scenario containers unchanged. This is a structural
  denominator, not 98 additional scenarios or a complete campaign playthrough.
- Gameplay code, stats, matchup tables, dialogue and current subtitle payload
  are unchanged outside the explicitly identified repairs.

## Runtime verification of successor288

Verification used Windows and a Beetle/Mednafen PC-FX libretro core, SHA-256
`97CFF6E559237A6528D823D850C3718AE92EE58713895A3719668F8BC53AD43A`.
The user-supplied BIOS SHA-256 was
`4B44CCF5D84CC83DAA2E6A2BEE00FDAFA14EB58BDF5859E96D8861A891675417`.
Neither component nor source saves, memory states or game screenshots are bundled.

| Route | Result and scope |
| --- | --- |
| Scenario 12 Angel → Phoenix | Cold SRAM load, 5,233 recorded controller frames. Pre-fix build freezes; Japanese finishes and returns to the field. New build finishes and returns to the field using the same route. No loaded emulator state or RAM intervention in the final run. |
| Royal Lancer HUD | Cold SRAM route, 3,904 frames. Canonical font bitmap and actual native tile verified. No loaded state or RAM intervention. |
| Scenario 10 combat / clear / results | Cold SRAM replay, 248 controller actions / 28,882 frames. All 88 sampled result images are pixel-identical to the previous verified build. The 29-unit roster and 261 native tiles match Japanese. |
| Automatic movies | 18,000-frame no-input startup: Opening 1 → Opening 2 → Opening 1. Korean subtitles observed. |
| OMAKE Opening 2 | Independently entered playback. Eight movie-frame checkpoints (180, 480, 600, 1200, 1800, 3600, 5400, 6600) match automatic playback pixel-for-pixel, including subtitled frames. |

An earlier one-byte RAM repair was used only to isolate the freeze cause, not
to establish final normal-play behavior. The final cold run uses the patched
disc directly. The second repaired directory has confirmed data corruption and
complete native comparison; no independent second gameplay hang is claimed.

## Packaging and contract tests

- Public patch/installer/native-directory suite: 11 tests passed.
- Private HUD normalization contract: 4 additional tests passed.
- Python CUE-based installer: applied the new cumulative delta to the supported
  original, producing the exact target hash in a separate folder.
- Packaged Windows executable: its `--apply-cue` path independently produced
  the exact target in another fresh output folder. It uses the same installer
  logic as the GUI; this is not a new manual GUI-click test.
- Windows tooling: Python 3.13.15, PyInstaller 6.16.0, contributed hooks 2026.7.
  No GUI redesign or game content change is part of packaging.
- ZIP creation uses a 20-member allowlist, embedded member checksums and CRC
  verification; the external `.zip.sha256` identifies the final archive.

## Evidence and limitations

Private final-media and regression reports bind these observations to the exact
hashes above. The trace, controller recordings and native captures are retained
locally for investigation; private paths and copyrighted evidence are excluded
from the public release. The public source documents the repair and its gates.

This is targeted cold gameplay plus structural regression coverage, not a fresh
all-scenario/all-branch playthrough or physical-hardware certification. Earlier
unrelated tool failures, incomplete hidden-dialogue wording review and other
historical condition-field issues remain disclosed in the README. Passing this
scope does not claim those issues are fixed.
