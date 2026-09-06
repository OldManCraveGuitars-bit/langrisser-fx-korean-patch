# Publication audit

This report was prepared before any source file was copied into the public-repository candidate. The private working project was inspected read-only. No file in that working project was deleted, moved, renamed, or overwritten.

## Scope and current size

The working directory is an accumulated reverse-engineering workspace rather than a clean source repository. The largest areas are:

| Area | Files | Approximate size | Publication decision |
| --- | ---: | ---: | --- |
| `work/` | 40,679 | 93.136 GiB | Exclude |
| `analysis/` | 16,053 | 12.259 GiB | Exclude by default |
| `dist/` | 508 | 12.062 GiB | Exclude; contains full patched disc images |
| `evidence/` | 33,126 | 4.242 GiB | Exclude; emulator captures, states, and dumps |
| `releases/` | 28 | 2.591 GiB | Exclude; contains full BIN/CUE bundles and saves |
| `assets/` | 2,407 | 0.140 GiB | Review item by item |
| `deliverables/` | 17 | 0.060 GiB | Exclude; contains BIN/CUE and personal save data |
| `tools/` | 3,665 | 0.039 GiB | Curate source files only |
| `dialogue_editor/` | 117 | 0.039 GiB | Curate code and Korean-only edit delta |
| `review/` | 35 | 0.030 GiB | Exclude by default; extracted text requires rights review |

## A. Public candidates

The following classes can be published after portability and secret checks:

- Project-authored Python, PowerShell, JavaScript, and C# source code.
- Current final-stage patch pipeline modules, kept as a historical development snapshot.
- Translation editor source code.
- The Korean-only user edit delta `dialogue_editor/사용자_대사수정.json`.
- Project-authored documentation rewritten without host-specific paths.
- Hashes, source revision descriptions, and structural specifications that do not reproduce game content.
- A delta patch that requires a legally obtained original Track 2 and cannot run by itself.
- A source-verifying patch applier and patch creation utility.
- Third-party license notices where redistribution of the notice is permitted.

An exact manifest of the files actually selected for this candidate is generated as `PUBLIC_FILES_SHA256.txt`.

## B. Excluded from GitHub

The following are not copied into the public candidate:

- Original or patched PC-FX disc images: `*.bin`, `*.cue`, `*.iso`, and any full-image ZIP containing them.
- The existing `dist/Langrisser-FX-KR-successor*.zip` packages. They contain complete patched tracks, not patch-only distributions.
- Original-game extracts, decompressed resources, dictionary blocks, hooks copied from runtime data, VRAM/K-RAM/RAM dumps, and raw graphics/audio/video captures.
- Emulator BIOS, emulator cores, executables, DLLs, downloaded runtimes, and local dependency caches.
- Save files and states: `*.srm`, `*.sav`, `*.fxb`, `*.mc0`, `*.state`.
- Test recordings, screenshots, contact sheets, and gameplay images unless the owner later approves a separately reviewed set.
- Cache and temporary material: `__pycache__/`, `*.pyc`, `.pytest_cache/`, logs, and scratch outputs.
- Personal backups and dated play-test bundles.
- Full extracted Japanese scripts or tables where the repository would reproduce substantial original text.

The original Track 2 inspected for patch applicability is 755,535,312 bytes with SHA-256 `1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0`. It remains outside this candidate.

## C. Needs owner or rights confirmation

- The user-supplied and modified RAINBOW/title artwork. It incorporates game branding/art and is not copied.
- Original-game screenshots for a future GitHub page. They are useful documentation but need a deliberate fair-use/rights decision.
- JSON/TSV catalogs that contain full Japanese source text alongside translations.
- Binary glyph, dictionary, hook, or decompressed resource fragments under `assets/`. Some are project-produced, but their source-content proportion and provenance vary.
- Third-party font binaries. License files are present for GNU Unifont, Ark Pixel Font, Galmuri, NeoDunggeunmo, and x12y12pxMaruMinyaHangul, but the exact subset and modification/attribution obligations should be confirmed before bundling font files.
- The MIT license applies to project-owned contributions under `LICENSE_SCOPE.md`; original game and third-party rights remain excluded.

## Sensitive-information scan

The scan covered source-like files in `tools/`, `dialogue_editor/`, `tests/`, `docs/`, and the old root README.

- Credential-shaped values (API keys, GitHub tokens, bearer credentials, or password assignments): **0 matches**.
- Email addresses: **0 matches** in the scanned project source/doc set.
- Windows user-profile paths: **41 matches** in the working tree.
- Host-specific absolute project/tool paths: **767 matches** in the working tree.

The personal and host-specific paths are portability/privacy findings, not credentials. Only a curated subset is copied, and the one hard-coded project root in that subset is replaced with a repository-relative root. The original files are not edited.

## Release-readiness constraint

The exact cumulative verification report records 131 tests with 8 known failures and 1 known error, and it explicitly says that all scenarios were not played. The public material therefore describes v0.8 as a **development/pre-release candidate**, not a completed or fully verified release.

The current internal package is a filename/CUE repackaging of the verified cumulative game data. Its complete BIN/CUE ZIP is excluded. The public v0.8 Release is instead a source-hash-gated delta patch for Track 2.
