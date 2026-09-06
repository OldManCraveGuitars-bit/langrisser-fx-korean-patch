from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


creator = load("create_lfx_patch", ROOT / "tools/create_lfx_patch.py")
applier = load("apply_lfx_patch", ROOT / "patch/apply_patch.py")


class PatchContainerTests(unittest.TestCase):
    def test_round_trip_growth_and_sparse_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source.bin"
            target = base / "target.bin"
            patch = base / "test.lfxpatch"
            output = base / "output.bin"
            source.write_bytes(bytes(range(256)) * 128)
            data = bytearray(source.read_bytes())
            data[17:23] = b"KOREAN"
            data[20000:20008] = b"LANGFXKR"
            data.extend(b"APPENDED-PAYLOAD")
            target.write_bytes(data)
            creator.create_patch(source, target, patch)
            result = applier.apply_patch(source, patch, output)
            self.assertEqual(output.read_bytes(), target.read_bytes())
            self.assertEqual(result["sha256"], creator.sha256_file(target))

    def test_rejects_wrong_source_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source.bin"
            target = base / "target.bin"
            wrong = base / "wrong.bin"
            patch = base / "test.lfxpatch"
            output = base / "output.bin"
            source.write_bytes(b"source")
            target.write_bytes(b"target-data")
            wrong.write_bytes(b"wrong!")
            creator.create_patch(source, target, patch)
            with self.assertRaises(applier.PatchError):
                applier.apply_patch(wrong, patch, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
