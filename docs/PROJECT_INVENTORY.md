# Working-project inventory

Source inspected: the private Langrisser FX Korean patch working tree.

This inventory is categorical because the development tree contains more than 96,000 files, many of them repeated captures or generated artifacts. The exact files selected for the public candidate are listed in the root `PUBLIC_FILES_SHA256.txt` manifest.

| Working-tree location | Observed purpose/content | Decision |
| --- | --- | --- |
| `tools/` | Python/PowerShell reverse engineering, builders, patch/media utilities, QA and historical probes; also bytecode cache | Curate source only |
| `dialogue_editor/` | Tkinter editor code, translation/edit JSON, extracted source catalogs, bytecode | Code + Korean-only delta; withhold full source catalogs |
| `tests/` | Unit/integration checks, many tied to private fixtures and historical artifacts | Do not bulk-copy; add standalone public patch-format tests |
| `docs/` | Survey, architecture/PoC notes, checkpoints, QA records, many host paths | Rewrite a portable current summary |
| `assets/fonts/` | Third-party TTF/BDF/OTF files and license texts | Notices only; font binaries pending review |
| `assets/title-inputs/`, `assets/title-concepts/` | User-supplied/modified game title art and generated RAINBOW payloads | Withhold pending rights decision |
| `assets/subtitles/` | Korean subtitles plus Japanese transcripts/timing | Withhold combined Japanese catalogs |
| `assets/blocks/`, `assets/graphics/`, `assets/hooks/`, `assets/glyphs/` | Extracted, modified, or generated binary game resources | Exclude/rights review |
| `analysis/` | Static reports, temporary comparisons, runtime reports, source references | Exclude by default; summarize facts only |
| `evidence/` | Screenshots, contact sheets, memory/state evidence | Exclude |
| `work/` | Original-derived media, cooked/raw tracks, emulator states, dependency caches, intermediate builds | Exclude |
| `dist/` | Historical IPS files and many full patched CUE/BIN ZIP packages | Exclude bulk directory; regenerate current patch-only artifact |
| `releases/`, `deliverables/` | Full play-test media, CUE/BIN, save bundles, reports | Exclude |
| `review/`, `outputs/` | Large extracted text tables, TSV/CSV/XLSX review exports | Withhold pending source-text review |
| root `build-*.ps1`, `run-*.ps1` | Hundreds of historical local wrappers, mostly host-specific | Exclude from curated candidate |
| old root `README.md` | Large chronological internal log with local paths and stale version context | Replace with current public README |

## File-type classification

- Source code: `*.py`, `*.ps1`, `*.mjs`, `*.cs` — potentially public after curation/path scan.
- Translation tables: JSON/TSV/CSV/XLSX — review for full Japanese source text and private paths before publication.
- Fonts: TTF/BDF/OTF/GZ/ZIP — third-party license review required.
- Game/media data: BIN/ISO/CUE/ROM/CHD, audio/video, resource dumps — not public.
- Executables/runtimes: EXE/DLL/PYD and downloaded dependencies — not public unless separately licensed and necessary; none are selected here.
- Tests/evidence: SRM/SAV/FXB/MC0/state/screenshots/logs — private or source-derived; not selected.
- Patch artifact: `.lfxpatch` — selected because it is source-gated and cannot replace ownership of the original game.

## Selected-source rationale

The final-stage source closure was computed from the newest builder/finalizer and current class/category/HUD/shop/media helpers. Twenty-three project-authored Python files were copied. Thirty-two translation-editor Python files were copied. The only working translation JSON copied is the v4 Korean edit delta; combined Japanese source catalogs were not copied.

One selected historical HUD module contained a hard-coded private project root. Only the public copy was changed to resolve the repository root from `__file__`. Two generic Windows system-font defaults were also changed into required `--font` arguments. The original working files remain untouched.
