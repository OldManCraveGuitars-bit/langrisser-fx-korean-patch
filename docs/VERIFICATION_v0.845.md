# v0.845 verification

The published delta targets the exact artifact used in the recorded Scenario 10
runtime verification. It is not an untested rebuild after that verification.
Prior evidence retains its own version attribution; no full-campaign or physical
device verification is claimed.

## Artifact identities

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Supported original raw Track 2 | 755,535,312 | `1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0` |
| Verified target raw Track 2 | 762,048,000 | `18652F60B9156BFA40DF8A3A638749D05D0A68898D938A86A2C7A2A38D8A927D` |
| Verified target cooked Track 2 | 663,091,200 | `3910A39DBC354FC12FCDC2D254E792B70284FC99DA906089542805BA3652B021` |
| `Langrisser-FX-KR-v0.845.lfxpatch` | 5,001,538 | `B1C6E25E5CA0DE9C524F20CA0AEEC3226217340FE30922194067596FA056EC87` |
| `Langrisser-FX-KR-Auto-Patcher-v0.845.exe` | 16,658,061 | `66A5D2A1026018267B8146E0FFA883335483559499A54A8E7847B8BD95034725` |

The sparse delta has 694 ordered compressed ranges and requires the exact source
size/hash. It is cumulative from the original Japanese raw MODE1/2352 Track 2,
including its 225-sector pregap. Original/patched game images are not published.

## Publication application checks

- Five public synthetic installer/container tests passed: sparse/growing round
  trip, wrong-source rejection, CUE parsing, complete separate output, and
  existing-output preservation.
- Python automatic CUE application to the supported original passed in a fresh
  private output directory. Final Track 2 matches the target above.
- The packaged Windows EXE's `--apply-cue` path independently passed in a second
  fresh private directory. It uses the same build logic as the GUI. This is an
  application check of the packaged executable, not a fresh manual GUI-click test.
- Both outputs' complete audio tracks match the supported originals:
  Track 1 `1E1840205CE98F5E0DF8067BEA8B3336DB62CA071C7B67538A0312C267D9CFA9`,
  Track 3 `9D1133A7DDAB061567F6C83F3342C90CBE32DC6A94561AE5309FA74335FDDD8D`.
  Both generated CUEs match the reviewed short-name template.
- Build environment: Windows x64, Python 3.13.15, PyInstaller 6.16.0 and hooks
  2026.7. The original media, earlier outputs and source saves remain separate.

## Game-data verification

Ten selected Scenario 8/9 records passed exact wording, encoding, layout,
page/dynamic-name topology and unchanged-record checks. The preceding dialogue
target's cold native Scenario 9 load/presentation/deployment route verified all
174 loaded records against the disc. Six later conversations were not reached
through campaign play. The final menu-only correction leaves those records intact.

Six private data regression tests were rerun for this publication: complete
replica/loader population, all 46 cache slots, dependent references, only declared
word changes, unknown/already-patched input rejection and destination lifetime.
All passed. These require private source/evidence data and are not counted among
the five public tests.

The final menu correction changes exactly 400 cooked bytes / 30 sectors from
the preceding dialogue target. All other cooked bytes are identical. Raw checks
cover the complete 324,000-sector target, including changed-sector EDC/ECC and
unchanged remaining raw bytes. Ten menu and ten settings copies are covered.
All 414 native cache tiles have zero menu-upload intersections, both native
loader copies are unchanged, and all 98 catalogued field containers are unchanged.
These container counts are not numbers of playable scenarios.

## Recorded runtime route on the exact target

Cold boot from a copied user SRAM, then Scenario 10 Meteor, end turn, Elwin's
attack, Vargas defeat, dialogue events and results: 28,882 frames using controller
input. The reproduction route used no state load, RAM mutation or enemy-HP edit.
Independent diagnostic Japanese-roster comparisons were separate from that route.

All 88 dense result samples had the original Japanese pixels for the same roster's
29 unit entries / 261 tiles. Names and lower UI matched the preceding target at
the same frames. All 66 common-menu glyph pixel payloads remained unchanged.
Settings displayed all three `꺼짐` labels correctly; condition and load menus
opened and returned with one Cancel. The recorded emulator was Beetle PC-FX via
libretro, core SHA-256
`97CFF6E559237A6528D823D850C3718AE92EE58713895A3719668F8BC53AD43A`.

## Limits

The Scenario 5 smoke attempt did not reach results and is not new Scenario 5
result-screen proof. Other-stage coverage is the shared-data boundary audit,
not all-stage gameplay. Physical PC-FX/iOS and every natural movie trigger were
not replayed. Earlier v0.825 movie and v0.84 hidden-dungeon evidence remains
versioned separately. Hidden wording review, all branches, unrelated historical
tool failures and other internal-field condition issues remain open.

Private evidence includes source-derived media/state data and is not distributed.
See [release scope](RELEASE_v0.845.md) and [publication decision](PUBLICATION_v0.845.md).
