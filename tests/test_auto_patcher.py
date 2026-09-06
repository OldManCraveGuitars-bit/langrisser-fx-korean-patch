from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


creator = load("create_lfx_patch_auto_test", ROOT / "tools/create_lfx_patch.py")


sys.path.insert(0, str(ROOT / "patch"))
auto = load("langrisser_fx_auto_patcher", ROOT / "patch/langrisser_fx_auto_patcher.py")


class AutoPatcherTests(unittest.TestCase):
    def make_disc(self, base: Path):
        tracks = {
            1: base / "Original (Track 1).bin",
            2: base / "Original (Track 2).bin",
            3: base / "Original (Track 3).bin",
        }
        tracks[1].write_bytes(b"audio-one")
        tracks[2].write_bytes(b"original-data-track-two")
        tracks[3].write_bytes(b"audio-three")
        cue = base / "Original.cue"
        cue.write_text(
            'FILE "Original (Track 1).bin" BINARY\n'
            '  TRACK 01 AUDIO\n'
            'FILE "Original (Track 2).bin" BINARY\n'
            '  TRACK 02 MODE1/2352\n'
            'FILE "Original (Track 3).bin" BINARY\n'
            '  TRACK 03 AUDIO\n',
            encoding="ascii",
        )
        expected = {
            number: {
                "size": path.stat().st_size,
                "sha256": auto.sha256_file(path),
                "output": auto.EXPECTED_TRACKS[number]["output"],
            }
            for number, path in tracks.items()
        }
        return cue, tracks, expected

    def test_parse_three_file_cue(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            cue, tracks, _ = self.make_disc(base)
            self.assertEqual(auto.parse_cue(cue), {number: path.resolve() for number, path in tracks.items()})

    def test_complete_build_is_separate_and_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            cue, tracks, expected = self.make_disc(base)
            target_track2 = base / "target.bin"
            target_track2.write_bytes(tracks[2].read_bytes() + b"-KOREAN")
            patch_file = base / "test.lfxpatch"
            creator.create_patch(tracks[2], target_track2, patch_file)
            output_parent = base / "output"

            with (
                patch.object(auto, "EXPECTED_TRACKS", expected),
                patch.object(auto, "OUTPUT_TRACK2_SIZE", target_track2.stat().st_size),
                patch.object(auto, "OUTPUT_TRACK2_SHA256", auto.sha256_file(target_track2)),
                patch.object(auto, "MIN_FREE_MARGIN", 0),
            ):
                output = auto.build_disc_set(cue, output_parent, patch_path=patch_file)

            self.assertEqual((output / "Track-1.bin").read_bytes(), tracks[1].read_bytes())
            self.assertEqual((output / "Track-2.KR.bin").read_bytes(), target_track2.read_bytes())
            self.assertEqual((output / "Track-3.bin").read_bytes(), tracks[3].read_bytes())
            self.assertTrue((output / auto.OUTPUT_CUE_NAME).is_file())
            self.assertTrue((output / "SHA256SUMS.txt").is_file())
            self.assertEqual(tracks[2].read_bytes(), b"original-data-track-two")

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            cue, _, expected = self.make_disc(base)
            output_parent = base / "output"
            existing = output_parent / auto.OUTPUT_DIRECTORY_NAME
            existing.mkdir(parents=True)
            marker = existing / "keep.txt"
            marker.write_text("keep", encoding="ascii")
            with patch.object(auto, "EXPECTED_TRACKS", expected):
                with self.assertRaises(auto.InstallerError):
                    auto.build_disc_set(cue, output_parent, patch_path=base / "not-needed")
            self.assertEqual(marker.read_text(encoding="ascii"), "keep")


if __name__ == "__main__":
    unittest.main()
