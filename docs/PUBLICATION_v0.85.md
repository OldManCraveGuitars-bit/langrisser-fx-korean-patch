# v0.85 publication decision and audit

Decision ID: `v085-current-target-public-prerelease`.

The maintainer explicitly requested publishing the current fixes and a correction
report, then corrected the requested version from 8.5 to **0.85** before packaging
or publication. This continues the established pre-release status; it does not
convert unfinished translation review or unrelated tests into completed work.

Selected target: internal successor288, RAW Track 2 SHA-256
`3FF464E484B55064BED49C7451E8DDFAEA24896D3819DA3A3EEFBBD443824B0A`.
Delta SHA-256:
`ED4E1B06BC466BAF220DC930D41334626AC1D34BA57EA8E06E242CF775C8C939`.

See [changes and limitations](RELEASE_v0.85.md),
[technical implementation](IMPLEMENTATION_v0.85.md) and
[artifact/runtime verification](VERIFICATION_v0.85.md).

## Distribution boundary

The ZIP allowlist includes only the cumulative delta, automatic Windows patcher,
Python fallback, project-authored short-name CUE template, install instructions,
change history, selected reports and license notices. Original/patched game
images, BIOS, emulator binaries, extracted graphics/audio/video, source saves,
memory states, personal screenshots, credentials and local account paths are
excluded. A CUE template contains no game content.

Project-authored code, scripts and documents retain the existing MIT scope;
no license is granted to original game or third-party material. The unchanged
Galmuri SIL OFL notice is included for the font-derived HUD glyphs. No font source
file is added. Private needs-human-review and historical non-distribution markers
are preserved; this is a separate maintainer decision to publish the exact target
as a development pre-release, not a claim that all translation is approved.

All older releases, tags, game originals, saves and private development outputs
are preserved. The selected public source is inspectable implementation, not
a complete standalone source build.

## Publication gates

Python and the packaged Windows EXE independently applied the new patch to the
original, producing the selected target in separate output folders. EXE SHA-256:
`64BC89B6682B0189D6B3B5543E5CE152D3F04EB68185753AF367915DED73ACC1`.
The executable was tested through its CUE-based command-line path, not a new
manual GUI-click test. All original track identities remain enforced.

The packaging script pins the application-verified delta and EXE, permits only
20 selected ZIP members, verifies member contents and CRCs, and refuses an
existing archive. Member checksums are inside `SHA256SUMS.txt`; the separately
published `.zip.sha256` identifies the final archive without a self-referential
hash inside it. The repository's `PUBLIC_FILES_SHA256.txt` records selected
public files and excludes itself.

The publication audit checks the public file set for private host paths,
credential-like strings, unexpected personal email and prohibited media. Public
third-party contact information in unchanged license notices is attribution,
not a project account credential, and is deliberately retained.
