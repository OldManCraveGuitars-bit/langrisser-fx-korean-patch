"""Adopted native class-change UI corrections for the pinned successor256 lineage.

Evidence: analysis/successor259-class-change-baseline-session/replay.json.
Shared records 61/73 are fixed-size, NUL-delimited, in all 105 common tables.
The small command-range caption is executable drawing code, not a string.
Only its two loader copies change; existing resource-0 glyphs remain intact.
"""
from v810_profile_codec import (encode_v, encode_rr, encode_imm5, encode_jal,
                                decode, encode)

TITLE_BEFORE = bytes.fromhex('434c415353f1e64348414e47450500')
TITLE_AFTER = bytes.fromhex('f14ef163f06bf1e8f0a8f147f0a600')
CONFIRM_BEFORE = bytes.fromhex('f09408f0a4f149f1e2f08cf08df1ba08f0a7f0f5f1e8f0abf04bf04c814805814081402000')
CONFIRM_AFTER = CONFIRM_BEFORE[:-2] + bytes([8, 0])
TEXT_FIELDS = ((0x24f, TITLE_BEFORE, TITLE_AFTER, 'class-change/title'),
               (0x2d8, CONFIRM_BEFORE, CONFIRM_AFTER, 'class-change/confirmation'))
LOOP_PC = 0x296b2
DRAW_PC = 0x11928
CODE_OFFSETS = (0x226b2, 0x277fd6b2)
LOOP_BEFORE = bytes.fromhex('6003148a3ba530000241fba41700dc00feaf66826147654fec8d')
FUNCTION_SHA = '994BAF9122C7F5F719913157519C54FE4433C9B14CCFC7315846B079AA34D517'
CALLEE_SHA = '7D10987AF772386AA8F5ACA5B0F34B26DC88F39BD496B49179EA4D087994C040'
CATALOG_SHA = '816B0D8A0FE6CAAFE54EF91A0F2AD8EF892A00B5D8E362D953509A007BA01B9A'


def command_range_caption():
    """Two C300-based Galmuri7 cells: 지/C31E, 휘/C38F, at x25/26 y2.

    11928 preserves r6/r7/r8; its scratch registers are dead here. r27's
    former loop value is dead until reinitialized at 29914. The surrounding
    function saves/restores r25-r29/r31; no stack or branch target moves.
    """
    code = (encode_v(0x28, 0x1e, 0, 9) + encode_imm5(0x10, 2, 8) +
            encode_v(0x28, 25, 0, 7) + encode_rr(0, 28, 6))
    code += encode_jal(LOOP_PC + len(code), DRAW_PC)
    code += encode_v(0x28, 0x8f, 0, 9) + encode_imm5(0x11, 1, 7)
    code += encode_jal(LOOP_PC + len(code), DRAW_PC)
    assert len(code) == len(LOOP_BEFORE)
    validate_caption(code)
    return code


def validate_caption(code):
    # Independent expected operands/boundaries, not a generated hex equality.
    expected = [(0x28, 0, 9, 0x1e, None), (0x10, 2, 8, None, None),
                (0x28, 0, 7, 25, None), (0, 28, 6, None, None),
                (0x2b, 0, 0, None, DRAW_PC), (0x28, 0, 9, 0x8f, None),
                (0x11, 1, 7, None, None), (0x2b, 0, 0, None, DRAW_PC)]
    cursor = 0
    for opcode, low, high, immediate, target in expected:
        ins = decode(code, cursor, LOOP_PC + cursor)
        if (ins.opcode != opcode or ins.immediate != immediate or
                ins.target != target or
                (target is None and (ins.low, ins.high) != (low, high))):
            raise ValueError('class caption instruction/operand mismatch')
        if encode(ins) != code[cursor:cursor + ins.size]:
            raise ValueError('class caption instruction round trip')
        cursor += ins.size
    if cursor != len(code) or cursor != 26:
        raise ValueError('class caption extent')


def replace_record(current, before, after):
    if current != before or len(before) != len(after):
        raise ValueError('class record identity/extent')
    if before.count(b'\0') != 1 or after.count(b'\0') != 1 or after[-1] != 0:
        raise ValueError('class record NUL topology')
    return after
