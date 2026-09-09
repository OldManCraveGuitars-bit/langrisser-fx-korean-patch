# v0.851 verification

## Exact artifact identity

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Required Japanese raw Track 2 | 755,535,312 | `1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0` |
| Target raw Track 2 (successor289) | 762,048,000 | `18DA706AC4D3B5867004EC9BD45FA00B449C5D9DCBA34CBC6CE3A8D54BE2A23B` |
| Target cooked Track 2 | 663,091,200 | `0FB93B7A870B9CA8465C60555A0CAD0AC6E1DB8EE8A3E2E64A9F827C25424BDE` |
| v0.851 cumulative delta | 5,001,559 | `402A4506CB9374B30E82C84BC92B56A4A59E15B86D5A490F1AF8DCC066103919` |
| v0.851 Windows EXE | 16,658,368 | `632112448FB8101AD66B737EBF52A9B35B65F538A63F0DD266EE1635E00B973C` |

The release ZIP has an external `.zip.sha256` and internal member checksums.
It contains no original/fully patched game images or saves. The delta has
694 ordered non-overlapping chunks and requires the exact original above.

## Product checks (successor289)

- Original Japanese Track 2 + pinned v0.81 implementation specification rebuilt
  through the primary conflict-checked builder; no previous patched image input.
- Exactly 735 cooked bytes differ from v0.85, only inside 15 existing HUD
  prefix-helper reservations. The entire remaining cooked image is identical.
- Final helper decoding/re-encoding and branch/return checks passed in every bank.
- PC-FX V810 profile self-test: 157,009 roundtrip and 87 invalid-encoding cases.
- Three private helper regression tests passed, including reproduction of the
  old failure and all 65,536 prefix descriptors in **each** of two contexts
  (131,072 paths). Adjacent fields, return behavior and non-name numeric policy
  were checked against actual emitted instructions, not just a text model.
- 167 native name IDs / 333 native-and-alias post-compose execution cases passed.
- 201 glyphs per bank × 15 banks compared directly with the adopted Galmuri7 BDF.
  Font bytes, name maps and record contents are unchanged.
- Raw sector regeneration and untouched audio were verified in the product build.

## Actual runtime checks

Beetle PC-FX/libretro was started from power-on with the supplied SRAM copied
into an isolated test environment. Controller inputs only: no save-state load
or gameplay RAM editing was used for these captures.

- Scenario 12: 4,681 frames; load, Liana selection, detail menu open/close,
  soldier transition, empty ground and name return.
- Five formerly failing captures differ by exactly 38 pixels inside the two
  prefix cells; every other screen pixel matches v0.85.
- Liana's three glyphs match across final MAIN BAT, KING KRAM and native screen
  pixels. SCENARIO 12 / TURN 8 pixels are identical to the baseline.
- Scenario 10: 3,708 frames; unit-name ↔ SCENARIO 10 transitions confirmed.
- Supplied SRAM originals retained their input hashes.

These are representative consumer-path tests, not every scenario or battle.
Previous v0.85 combat/movie verification remains attributed to that exact
version. Current battle/movie/subtitle data is byte-identical, but every
natural movie trigger and battle was not replayed for v0.851.

## Public before/after evidence

Both PNGs are unedited 256×240 screenshots from the same SRAM/controller route
at checkpoint `10-up3`. No recoloring, redraw, crop, upscale or annotation
was applied. Zero-based changed-pixel bounds are x161..174, y208..215.

| File | SHA-256 |
| --- | --- |
| [Before — v0.85](../screenshots/v0.851/liana-before-v0.85.png) | `57B4580C545B92843175811C870F8A7B4069694C9E7D5510E42528242A700538` |
| [After — v0.851](../screenshots/v0.851/liana-after-v0.851.png) | `918B3CC64D2310D489DD04B74D2624FBD8CC8D8C7E35FF1C0C038B8363F3D6D4` |

The private detailed artifact audit has SHA-256
`46630445D8D79DCF778E78B13490584023221FD034557355CCBF10EDB59F906D`;
the runtime report has SHA-256
`C9035904162773F105E81E8CF65B53DC5BBA606090C0C08766627C2376A1AF9F`.
Those reports/dumps are not bundled; this sanitized document records their
scope and identities without private paths or save content.

## Distribution checks

- Public synthetic suite: **11 tests passed**, including patch roundtrip,
  wrong-source rejection, original/output preservation and directory bounds.
  This is separate from the three private HUD helper tests.
- Python CUE-based application and the packaged Windows EXE's `--apply-cue`
  route each generated a separate output from the original Japanese disc.
  Both target Track 2 hashes match successor289, both audio tracks match
  the originals, and CUE/member checksums were independently checked.
- EXE environment: Windows, Python 3.13.15, PyInstaller 6.16.0 and contributed
  hooks 2026.7. The packaged application path was exercised; this publication
  pass does not claim a new manual GUI click-through.
- ZIP explicit allowlist, CRC, exact member readback and SHA-256 checks.
- Public Python syntax, secret/host-path scan, private/public adopted-source
  equality and canonical Git-blob checksum manifest checked before publication.
- Previous local release ZIPs are hash-preserved. Original game files, saves
  and historical published versions are not replaced.

## Remaining limits

No full-campaign/all-branch playthrough or physical-console/iPhone verification.
Hidden-dialogue full wording review remains pending. The earlier cumulative
tool baseline's 8 failures and 1 error are not claimed fixed. Historical
condition-text fields outside this patch remain outside its scope. Public
source snapshots still omit some source-derived authoring dependencies.
This remains a development/pre-release.
