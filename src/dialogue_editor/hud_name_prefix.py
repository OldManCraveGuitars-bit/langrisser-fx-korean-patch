"""Clear native name residue without confusing it with SCENARIO digits.

The final Korean name BAT always starts with 5F28 at 6CC74. Native digits
312..31B are not a sufficient context test: Liana leaves 5380/531A before
that field. Keep the prior numeric guard for non-name rows, but give the
actual private-name field precedence. No glyph, record, tile or row moves.
"""
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_deployment_menu_hook import Assembler, encode_jal
from v810_pcfx_isa_profile import decode_instruction, encode_instruction, format_instruction
from hud_commander_class_restore import resource_starts, PRIVATE, need

RAM = 0x1E3E90
OFFSET = RAM - 0x1E2000
CALL_RAM, CALL_OFFSET = 0x1E3090, 0x1090
NAME_ROW = 0x6CC74
NAME_FIRST = 0x5F28
OLD = bytes.fromhex(
    '80BE070094A272CC54C500004AB5FF0F60A112034B0D0A8C'
    '60A11C034B0D168C40BD00534AA1005380BE070094A274CC54DDFCFF'
    '80BE1E001F18')
# Existing helper reservation ends at 1E3F01. Do not move adjacent owners.
LIMIT = 0x1E3F01


def helper():
    a = Assembler(RAM)
    a.load_address(NAME_ROW, 20)
    a.load(0x31, 0, 20, 10)
    a.movea(NAME_FIRST, 0, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x42, 'clear')
    a.load(0x31, -2, 20, 10)
    a.fmt_v(0x2D, 0xFFF, 10, 10)
    a.movea(0x312, 0, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x46, 'clear')
    a.movea(0x31C, 0, 11)
    a.reg(0x03, 11, 10)
    a.branch(0x46, 'restore')
    a.label('clear')
    a.load_address(0x53005300, 10)
    a.store(0x37, -4, 20, 10)
    a.label('restore')
    # Same overwritten movhi and return ABI; only r10/r11/r20 and flags
    # are scratch here, as in the original helper.
    a.movhi(0x1E, 0, 20)
    a.reg(0x06, 31, 0)
    code = a.finish()
    need(RAM + len(code) <= LIMIT, 'HUD prefix helper exceeds existing reservation')
    return code


def verify_code(code):
    rows, starts, branches = [], set(), []
    pos = 0
    while pos < len(code):
        ins = decode_instruction(code, pos, strict=True)
        raw = code[pos:pos+ins.size]
        need(encode_instruction(ins) == raw, 'PC-FX V810 roundtrip')
        starts.add(RAM+pos)
        if ins.spec.mode == 'III':
            branches.append(RAM+pos+ins.displacement)
        rows.append(format_instruction(ins, RAM+pos))
        pos += ins.size
    need(pos == len(code) and all(p in starts for p in branches), 'Branch boundary')
    need(code[-6:] == bytes.fromhex('80BE1E001F18'), 'Native movhi/return ABI')
    return rows


def plan(image):
    code = helper()
    disassembly = verify_code(code)
    before = OLD + bytes(len(code)-len(OLD))
    writes = []
    for i, start in enumerate(resource_starts(image)):
        base = start+PRIVATE
        need(image[base+CALL_OFFSET:base+CALL_OFFSET+4] == encode_jal(CALL_RAM, RAM),
             'Active HUD prefix call differs')
        need(image[base+OFFSET:base+OFFSET+len(before)] == before,
             'HUD prefix helper/reservation preimage differs')
        writes.append((base+OFFSET, before, code, f'hud-name-prefix/replica/{i:02d}'))
    return writes, {'replicas': len(writes), 'helper_ram': hex(RAM),
        'helper_bytes': len(code), 'disassembly': disassembly,
        'name_origin': hex(NAME_ROW), 'private_name_first_bat': hex(NAME_FIRST),
        'native_numeric_guard_retained_for_non_name_rows': True,
        'glyphs_records_tiles_and_layout_changed': False}


def verify(source, target):
    writes, audit = plan(source)
    for off, before, after, owner in writes:
        need(target[off:off+len(after)] == after, 'Final helper missing: '+owner)
        verify_code(target[off:off+len(after)])
    audit['all_final_helpers_verified'] = True
    return audit
