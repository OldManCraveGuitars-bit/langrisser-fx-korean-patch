"""Offline native video/audio reader using the public libretro ABI.

An isolated core instance: never opens or writes the user's emulator save files.
The interactive JSON interface is for establishing the movie-selection route.
"""
from __future__ import annotations

import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/editor-media-deps'))


class Game(C.Structure):
    _fields_ = [('path', C.c_char_p), ('data', C.c_void_p),
                ('size', C.c_size_t), ('meta', C.c_char_p)]


class Variable(C.Structure):
    _fields_ = [('key', C.c_char_p), ('value', C.c_char_p)]


class Geometry(C.Structure):
    _fields_ = [('base_width', C.c_uint), ('base_height', C.c_uint),
                ('max_width', C.c_uint), ('max_height', C.c_uint),
                ('aspect_ratio', C.c_float)]


class Timing(C.Structure):
    _fields_ = [('fps', C.c_double), ('sample_rate', C.c_double)]


class AVInfo(C.Structure):
    _fields_ = [('geometry', Geometry), ('timing', Timing)]


ENV = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
BATCH = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL = C.CFUNCTYPE(None)
INPUT = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
LOG = C.CFUNCTYPE(None, C.c_int, C.c_char_p)
BUTTONS = {'ii': 0, 'iv': 1, 'select': 2, 'run': 3, 'up': 4, 'down': 5,
           'left': 6, 'right': 7, 'i': 8, 'iii': 9, 'v': 10, 'vi': 11}


class Core:
    def __init__(self, dll: Path, cue: Path, bios: Path, scratch: Path,
                 save: Path | None = None):
        scratch.mkdir(parents=True, exist_ok=True)
        self.directory = str(bios.parent.resolve()).encode('utf-8')
        self.save_directory = str(scratch.resolve()).encode('utf-8')
        self.variables = {}
        self.overrides = {b'pcfx_rainbow_chromaip': b'disabled',
                          b'pcfx_initial_scanline': b'0',
                          b'pcfx_last_scanline': b'239',
                          b'pcfx_emulate_buggy_codec': b'disabled',
                          b'pcfx_high_dotclock_width': b'256',
                          b'pcfx_cdimagecache': b'disabled'}
        self.buttons = set()
        self.frame = None
        self.audio = bytearray()
        self.pixel_format = 0
        self.frame_number = 0
        self.callback_error = None
        self.logger = LOG(lambda level, fmt: None)
        self.lib = C.CDLL(str(dll.resolve()))
        self.callbacks = [ENV(self.environment), VIDEO(self.video),
                          AUDIO(lambda l, r: self.audio.extend(struct.pack('<hh', l, r))),
                          BATCH(self.batch), POLL(lambda: None), INPUT(self.input)]
        for name, callback in zip(('environment', 'video_refresh', 'audio_sample',
                                   'audio_sample_batch', 'input_poll', 'input_state'), self.callbacks):
            fn = getattr(self.lib, 'retro_set_' + name)
            fn.argtypes = [type(callback)]
            fn(callback)
        self.lib.retro_load_game.argtypes = [C.POINTER(Game)]
        self.lib.retro_load_game.restype = C.c_bool
        self.lib.retro_get_system_av_info.argtypes = [C.POINTER(AVInfo)]
        self.lib.retro_get_memory_data.argtypes = [C.c_uint]
        self.lib.retro_get_memory_data.restype = C.c_void_p
        self.lib.retro_get_memory_size.argtypes = [C.c_uint]
        self.lib.retro_get_memory_size.restype = C.c_size_t
        self.lib.retro_serialize_size.restype = C.c_size_t
        for name in ('serialize', 'unserialize'):
            fn = getattr(self.lib, 'retro_' + name)
            fn.argtypes = [C.c_void_p, C.c_size_t]
            fn.restype = C.c_bool
        self.lib.retro_init()
        game = Game(str(cue.resolve()).encode('utf-8'), None, 0, None)
        if not self.lib.retro_load_game(C.byref(game)):
            raise RuntimeError('원본 디스크를 열 수 없습니다.')
        self.lib.retro_set_controller_port_device(0, 1)
        if save:
            content = save.read_bytes()
            if len(content) not in (32768, 65536):
                raise ValueError('Unsupported save size')
            if content[3:11] != b'PCFXSram':
                raise ValueError('PC-FX internal SRAM header missing')
            C.memmove(self.lib.retro_get_memory_data(0), content, len(content))
        self.info = AVInfo()
        self.lib.retro_get_system_av_info(C.byref(self.info))
        if self.lib.retro_get_memory_size(2) != 0x200000:
            raise RuntimeError('PC-FX MAIN RAM size mismatch')
        self.main = self.lib.retro_get_memory_data(2)

    def environment(self, command, data):
        if command == (51 | 0x10000):
            return True
        if command in (9, 31):
            C.cast(data, C.POINTER(C.c_char_p))[0] = (
                self.directory if command == 9 else self.save_directory)
            return True
        if command == 10:
            self.pixel_format = C.cast(data, C.POINTER(C.c_int))[0]
            return self.pixel_format in (0, 1, 2)
        if command == 15:
            v = C.cast(data, C.POINTER(Variable)).contents
            value = self.overrides.get(v.key, self.variables.get(v.key))
            v.value = value
            return value is not None
        if command == 16:
            values = C.cast(data, C.POINTER(Variable))
            i = 0
            while values[i].key:
                self.variables[values[i].key] = values[i].value.split(b'; ', 1)[1].split(b'|')[0]
                i += 1
            return True
        if command == 17:
            C.cast(data, C.POINTER(C.c_bool))[0] = False
            return True
        if command in (3, 18):
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        if command == 27:
            C.cast(data, C.POINTER(C.c_void_p))[0] = C.cast(self.logger, C.c_void_p).value
            return True
        if command == 52:
            C.cast(data, C.POINTER(C.c_uint))[0] = 0
            return True
        if command in (6, 11, 35, 37):
            return True
        return False

    def video(self, data, width, height, pitch):
        if data:
            self.frame = (C.string_at(data, pitch * height), width, height, pitch,
                          self.pixel_format)

    def batch(self, data, count):
        self.audio.extend(C.string_at(data, count * 4))
        return count

    def input(self, port, device, index, button):
        if button == 256 and port == 0 and device == 1:
            return sum(1 << b for b in self.buttons)
        return int(port == 0 and device == 1 and button in self.buttons)

    def run(self, frames=1, buttons=()):
        self.buttons = {BUTTONS[name] for name in buttons}
        self.audio.clear()
        for _ in range(frames):
            self.lib.retro_run()
            self.frame_number += 1
        self.buttons.clear()

    def u32(self, address):
        return C.c_uint32.from_address(self.main + address).value

    def image(self):
        from PIL import Image
        if self.frame is None:
            raise RuntimeError('No video frame')
        data, w, h, pitch, pixel = self.frame
        if pixel == 1:
            return Image.frombytes('RGB', (w, h), data, 'raw', 'BGRX', pitch)
        import numpy as np
        words = np.frombuffer(data, dtype='<u2').reshape(h, pitch // 2)[:, :w]
        shifts = (11, 5, 0) if pixel == 2 else (10, 5, 0)
        masks = (31, 63, 31) if pixel == 2 else (31, 31, 31)
        rgb = np.stack([((words >> s) & m) * 255 // m for s, m in zip(shifts, masks)], -1)
        return Image.fromarray(rgb.astype('uint8'))

    def save_state(self, path):
        size = self.lib.retro_serialize_size()
        buffer = C.create_string_buffer(size)
        if not self.lib.retro_serialize(buffer, size):
            raise RuntimeError('State save failed')
        Path(path).write_bytes(buffer.raw)

    def load_state(self, path):
        data = Path(path).read_bytes()
        if not self.lib.retro_unserialize(data, len(data)):
            raise RuntimeError('State load failed')

    def close(self):
        self.lib.retro_unload_game()
        self.lib.retro_deinit()


def main():
    p = argparse.ArgumentParser()
    for name in ('core', 'cue', 'bios', 'scratch'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--save', type=Path)
    args = p.parse_args()
    core = Core(args.core, args.cue, args.bios, args.scratch, args.save)
    print(json.dumps({'ready': True, 'fps': core.info.timing.fps,
                      'sample_rate': core.info.timing.sample_rate}), flush=True)
    try:
        for line in sys.stdin:
            command = json.loads(line)
            if command.get('quit'):
                break
            if 'load' in command:
                core.load_state(command['load'])
            core.run(int(command.get('frames', 1)), command.get('buttons', []))
            if 'screenshot' in command:
                core.image().save(command['screenshot'])
            if 'save' in command:
                core.save_state(command['save'])
            if 'dump_memory' in command:
                dump = command['dump_memory']
                address = int(dump.get('address', 0))
                size = int(dump['size'])
                if address < 0 or size < 0 or address + size > 0x200000:
                    raise ValueError('MAIN RAM dump range is outside 2 MiB')
                Path(dump['path']).write_bytes(C.string_at(core.main + address, size))
            if 'audio' in command:
                Path(command['audio']).write_bytes(bytes(core.audio))
            print(json.dumps({'frame': core.frame_number, 'command': hex(core.u32(0x1a0)),
                              'movie_id': core.u32(0x1a4), 'movie_frame': core.u32(0x5ad20),
                              'audio_samples': len(core.audio) // 4,
                              'size': core.image().size}), flush=True)
    finally:
        core.close()


if __name__ == '__main__':
    main()
