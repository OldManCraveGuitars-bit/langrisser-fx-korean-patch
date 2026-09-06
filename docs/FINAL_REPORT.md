# GitHub publication preparation — final report

## Outcome

A separate public-repository candidate was created. The private development tree, original game dump, current patched game, saves, and emulator environment were not modified. A local Git repository was initialized on `main` and prepared with a first commit; no remote was configured and nothing was pushed or published.

The only removed files were newly generated verification output/cache files inside the new public candidate. They contained no unique work and were regenerated/removed after successful checks.

## Public files selected

The candidate contains:

- Public README in English with a Korean section.
- `CHANGELOG.md`, `.gitignore`, `LICENSE`, and `LICENSE_SCOPE.md`.
- Six public documentation files under `docs/`.
- Twenty-three curated final-stage pipeline Python files under `src/patch_pipeline/`.
- Thirty-two translation-editor Python files under `src/dialogue_editor/`.
- One Korean-only v4 editor delta under `data/translations/`.
- Patch applier, Track 2 delta, CUE, and bilingual installation instructions under `patch/`.
- A Windows GUI automatic patcher source and local single-file executable build.
- One maintainer delta generator, Windows packager, and two test modules.
- GNU Unifont license notices, without the font binary.
- A local GitHub Release upload candidate and its external SHA-256 record.

`PUBLIC_FILES_SHA256.txt` is the exact file-by-file public manifest. The Release ZIP is intentionally ignored by Git and is listed separately in `release/RELEASE_SHA256.txt`.

## Files excluded

| Excluded class/location | Reason |
| --- | --- |
| `work/` | About 93.136 GiB of source-derived media, intermediates, states, caches, and full tracks |
| `analysis/` | About 12.259 GiB of host-specific reports, dumps, screenshots, and runtime artifacts |
| `dist/` | About 12.062 GiB, including complete patched BIN/CUE ZIP files |
| `evidence/` | About 4.242 GiB of game screenshots, states, RAM/VRAM/K-RAM evidence |
| `releases/` | About 2.591 GiB of full track bundles and saves |
| `deliverables/` | BIN/CUE and personal save bundles |
| `assets/` binary/game art portions | Extracted/modified game data or unclear source-content provenance |
| `review/`, `outputs/` | Large extracted text/review tables, including source-language content |
| root historical wrappers | Hundreds of host-specific build/run scripts with private absolute paths |
| `*.srm`, `*.sav`, `*.fxb`, `*.mc0`, states | Personal progress and emulator state |
| BIOS, cores, EXE/DLL/PYD dependencies | User-owned firmware or separately licensed executables |
| title art and screenshots | Original branding/game imagery; owner/rights decision required |

## README and repository structure

The new README documents the target game/platform, development status, editor-visible translation populations, implemented technical work, patch application, exact source/target hashes, font/text architecture, build limitation, known issues, environment, credits, and disclaimer. Claims are bounded to inspected source and recorded evidence.

Expected repository structure:

```text
README.md
CHANGELOG.md
.gitignore
LICENSE
LICENSE_SCOPE.md
PUBLIC_FILES_SHA256.txt
data/translations/
docs/
patch/
release/
src/dialogue_editor/
src/patch_pipeline/
tests/
third_party/unifont/
tools/
```

No empty `screenshots/` or generic `assets/` directory was created because no reviewed public asset currently belongs there.

## Release candidate

Prepared local upload artifact:

```text
Langrisser_FX_Korean_Patch_v0.8.zip
SHA-256: 093BBB0BF2EBCA0C87683C7657991D4AFAEA6DB0BC2CEBB8B1C3A8AA17206B15
```

The ZIP contains only:

- `Langrisser-FX-KR-Auto-Patcher.exe`
- `Langrisser-FX-KR-v0.8.lfxpatch`
- `langrisser_fx_auto_patcher.py`
- `apply_patch.py`
- `Langrisser-FX-KR.cue`
- `INSTALL.txt`
- `README.md`
- `CHANGELOG.md`
- `LICENSE`
- `LICENSE_SCOPE.md`
- `SHA256SUMS.txt`

It contains no BIN/ISO/ROM, save/state, BIOS, DLL, or fully patched game image.
The single-file Windows executable embeds only the sparse patch payload and
project-authored installer code; it does not embed a game image. The Python
command-line fallback is retained in the same package.

## Patch verification

The custom patch format was chosen because the latest Track 2 is larger than the original and the existing historical IPS artifacts are not the current final product. The patch header fixes the raw MODE1/2352 representation, source size/hash, target size/hash, and chunk count.

- Original Track 2: 755,535,312 bytes, SHA-256 `1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0`.
- Delta patch: 4,990,885 bytes, SHA-256 `2F3BF84FB6544EFCC97C38B7BA839AF4250367F72EA0EC5502615085F2FF3EE1`.
- Reconstructed target: 762,048,000 bytes, SHA-256 `E9F3E5D6C6AAD6C15FB554A440F2D8F9D22AE59756D3ABF11E5CF1941D3B04B3`.
- Exact source-to-target application: PASS.
- Automatic-patcher EXE against the exact original three-track CUE: PASS.
- Reconstructed Track 1/2/3 hashes from the EXE workflow: PASS.
- Artificial patch and automatic-installer tests: 5/5 PASS.
- All selected Python source files: syntax parse PASS.

## Copyright and licensing risks

- Full original and patched game media are not distributable and remain excluded.
- A binary delta is the selected distribution candidate because it requires the exact original; this is a technical risk reduction, not legal advice.
- RAINBOW/title art, gameplay screenshots, full Japanese catalogs, and source-derived binary assets need explicit owner/rights review before addition.
- GNU Unifont notices are retained; Galmuri7 and other font files are not bundled.
- The owner approved MIT with `Copyright (c) 2026 기타 깎는 노인 (GiKakNo)`.
- `LICENSE_SCOPE.md` limits that grant to project-owned contributions and explicitly excludes original game and third-party rights.

## Sensitive-information result

The private working tree contained 41 user-profile path matches and 767 host-specific absolute path matches. No credential-shaped API key/token/password value and no email address was found by the defined scan. The curated public candidate has:

- credential-shaped matches: 0;
- email matches: 0;
- true personal or host absolute filesystem paths: 0 after manual review;
- one generic description of the private-path findings in the audit report, containing no username or real path.

One copied source file's private project root and two generic Windows system-font defaults were made portable only in the public copy. The original development files were not changed.

## Additional confirmation required

1. Decide whether any title art or gameplay screenshots should be published after rights review.
2. Decide whether third-party font binaries should be bundled with full attribution or kept as external prerequisites.
3. Consolidate the historical successor chain into one original-disc-to-product build before claiming a fully reproducible source release.
4. Resolve or formally accept the 8 known test failures and 1 known error, and finish the required runtime scope before changing the status from pre-release.

No GitHub push or Release publication should occur until the owner reviews these items.
