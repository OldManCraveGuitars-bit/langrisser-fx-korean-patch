# v0.81 artifact verification

This records the prepared public patch and Windows executable, not a complete
campaign or hardware certification. Runtime scope is in [release notes](RELEASE_v0.81.md).

## Source and target identity

| Object | Bytes | SHA-256 |
| --- | ---: | --- |
| Supported original raw Track 2 | 755,535,312 | `1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0` |
| Verified patched Track 2 | 762,048,000 | `033D1813DBD570FDABC4B8A0C53FAC7FA8DBEB5EB484F8ED0421B5B5A59EB594` |
| v0.81 LFXPAT01 delta | 4,992,081 | `AD05ACECDFEA7EC2B3E49D8FD82B74D189E789C7EB645955FA0608C5C2B07511` |

The delta contains 699 ordered compressed replacement ranges. It is generated
from the supported original, not from a previous Korean patch. Its complete
output matches the exact locally runtime-verified target.

## Application checks

- Python automatic CUE workflow: PASS; all three original tracks accepted and
  a new complete disc set created. Final Track 2 matches the target above.
- Packaged Windows EXE, `--apply-cue` workflow with the embedded payload: PASS;
  the generated Track 2 matches the same target.
- Tracks 1 and 3 remain unchanged in the generated disc set:
  `1E1840205CE98F5E0DF8067BEA8B3336DB62CA071C7B67538A0312C267D9CFA9`
  and `9D1133A7DDAB061567F6C83F3342C90CBE32DC6A94561AE5309FA74335FDDD8D`.
- Five synthetic patcher/container regression tests: PASS, covering sparse
  round trips, growth, wrong-source rejection, CUE parsing, separate output
  creation and preservation of an existing output marker. These are patcher
  tests and do not replace the older cumulative game-tool test suite.

Executable: `Langrisser-FX-KR-Auto-Patcher-v0.81.exe`

SHA-256: `BCA0A08C00D31F3E836793D2C2A82A544DA2FE837339B0FE53BC03C426F7BBDE`

Build environment: Python 3.13.15, PyInstaller 6.16.0, contributed hooks 2026.7,
Windows x64. The EXE verification uses its command-line entry into the same
installer logic; it is not a new manual GUI-button walkthrough.

## Preservation and publication boundary

Original game media, the private tested build, old v0.8 patch and release, and
user saves are preserved. The new ZIP is assembled from an explicit allowlist
by `tools/package_public_release.py`. It contains patch/installer material,
installation and change notes, license notices and checksums; no complete
game tracks, BIOS, saves, runtime memory or extracted audio/video are selected.
The reviewed CUE is only a text template referring to user-created track files.

The ZIP has its own checksum in `release/RELEASE_SHA256.txt`. The historical
public game-source snapshot is not claimed to rebuild this cumulative target
from the original disc; that existing limitation remains explicit.
