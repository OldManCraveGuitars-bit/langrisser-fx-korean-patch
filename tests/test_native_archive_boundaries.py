import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'/'dialogue_editor'))
from native_archive_boundaries import validate_directory

class DirectoryTests(unittest.TestCase):
    def blob(self, words): return struct.pack('<'+str(len(words))+'I',*words)
    def test_valid(self):
        self.assertEqual(validate_directory(self.blob([0x800,0x1000,0x1800]),0x1800),[0x800,0x1000,0x1800])
    def test_high_byte_collision(self):
        with self.assertRaises(ValueError):validate_directory(self.blob([0x800,0x1000,0xff001800]),0x1800)
    def test_truncated_word(self):
        with self.assertRaises(ValueError):validate_directory(self.blob([0x800,0x1800])[:-1],0x1800)
    def test_reversed(self):
        with self.assertRaises(ValueError):validate_directory(self.blob([0x1000,0x800,0x1800]),0x1800)
    def test_unaligned(self):
        with self.assertRaises(ValueError):validate_directory(self.blob([0x801,0x1800]),0x1800)
    def test_header_overlap(self):
        with self.assertRaises(ValueError):validate_directory(self.blob([4,0x1800]),0x1800)

if __name__=='__main__':unittest.main()
