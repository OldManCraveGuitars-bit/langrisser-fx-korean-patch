# Third-party material

## Included notices

`third_party/unifont/` contains the inspected GNU Unifont 17.0.05 license notices. The Unifont binary/font source itself is not included in this public candidate.

The project records state that the resident 12×12 Hangul raster is byte-pinned to GNU Unifont 17.0.05. If the font or a modified font source is later added, its GPL/font-exception and SIL Open Font License terms must be reviewed and preserved.

## Referenced but not bundled

- **Galmuri7 v2.40.4**: the adopted 8×8 bottom-HUD source, including the v0.85 `로` repair. Its unchanged SIL Open Font License notice is retained at `third_party/galmuri/OFL-1.1.md` for the font-derived glyphs in the patch. The BDF source file is not bundled. Font-source SHA-256: `2A6FD090AC6D24F7392D6CC49DB02CE54B9D1C01048BF8C97CBCDBC5A885CB15`.
- **Ark Pixel Font**, **NeoDunggeunmo**, and **x12y12pxMaruMinyaHangul**: present in the private asset archive with license files, but not established as required inputs for the selected newest product path and therefore not copied.
- **Mednafen** and **Beetle PC-FX/libretro**: used for development/runtime verification. No emulator executable, core, BIOS, or downloaded runtime is included.
- **Pillow** and **NumPy**: used by parts of the development/verification tooling. NumPy is required by the public delta generator; the patch applier uses only the Python standard library.

## Original game

No license in this repository applies to Der Langrisser FX, PC-FX firmware, original game assets, or any other rights-holder material. Names and trademarks are used only to identify compatibility.
