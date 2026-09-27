"""Give the report's enemy-pointer list a bounded, report-owned stack frame.

Native 4A170 can collect twenty commanders, but 6F8F0 has twelve pointer
slots before animation flags at6F920/6F924. With thirteen enemies, animation
clears pointer12. Both original Japanese and318 reproduce the bogus final
unit. Keep all twenty real pointers, flags, counting and reward logic intact.
Only these three direct callees of4A7AE use the list. Reserve80 bytes above
its existing44-byte local frame; address them through each callee's SP.
"""
import hashlib
import struct
from build_deployment_menu_hook import Assembler, encode_jal
import v810_pcfx_isa_profile as isa
import luciris_pages318 as prior

BASE_SHA='54F6CD7FD3D018F2A39630BEE5FC26463A8154588EB10366422742468FE31C03'
MAIN_MIRROR=0x277DB000
RAM_DELTA=0x7000
OLD_FRAME=44
SLOTS=20
TABLE_BYTES=SLOTS*4
FRAME=OLD_FRAME+TABLE_BYTES
sha=lambda b:hashlib.sha256(b).hexdigest().upper()

def addi(pc,amount,destination):
    a=Assembler(pc);a.addi(amount,3,destination);return a.finish()

def replacements():
    rows=[(0x4A7AE,bytes.fromhex('63A4D4FF'),addi(0x4A7AE,-FRAME,3),'allocate-report-frame'),
          (0x4AA2A,bytes.fromhex('63A42C00'),addi(0x4AA2A,FRAME,3),'release-report-frame')]
    # function SP = owner SP - callee frame; list always at owner SP+44.
    for pc,reg,callee_frame,old,name in (
        (0x4A1D0,13,16,'A0BD0700ADA1F0F8','collect-enemies'),
        (0x4A08E,10,40,'40BD07004AA1F0F8','draw-enemies'),
        (0x49F74,13,24,'A0BD0700ADA1F0F8','process-enemies')):
        rows.append((pc,bytes.fromhex(old),addi(pc,OLD_FRAME+callee_frame,reg)+bytes(4),name))
    return sorted(rows)

def verify_calls(image):
    for caller,target in [(0x4A916,0x4A170),(0x4A92C,0x4A074),(0x4A948,0x49F50)]:
        for bias in (0,MAIN_MIRROR):
            at=bias+caller-RAM_DELTA
            assert image[at:at+4]==encode_jal(caller,target)
    # Their callee frame sizes and the20-entry native limit stay native.
    for pc,raw in [(0x4A170,'7044'),(0x4A074,'63A4D8FF'),(0x49F50,'63A4E8FF'),
                   (0x4A1E6,'20A21400'),(0x4A962,'BC0FBE8D')]:
        for bias in (0,MAIN_MIRROR):
            at=bias+pc-RAM_DELTA;b=bytes.fromhex(raw);assert image[at:at+len(b)]==b

def verify(image):
    verify_calls(image)
    for bias in (0,MAIN_MIRROR):
        for pc,before,after,name in replacements():
            at=bias+pc-RAM_DELTA;assert image[at:at+len(after)]==after,name
    prior.verify(image)

def plan(image):
    assert sha(image)==BASE_SHA,'Expected exact final318'
    verify_calls(image);writes=[]
    for bias in (0,MAIN_MIRROR):
        for pc,before,after,name in replacements():
            at=bias+pc-RAM_DELTA
            assert image[at:at+len(before)]==before,name
            assert len(after)==len(before)
            decoded=list(isa.disassemble_range(after,pc))
            assert b''.join(raw for _,_,raw in decoded)==after
            writes.append((at,before,after,f'report319/{name}/{bias:#x}'))
    audit=dict(cause='20-entry native collector writes beyond12-slot enemy list into animation flags',
        reproduced_in_japanese_original=True, old_table='0x6F8F0', conflicting_flags=['0x6F920','0x6F924'],
        correction='20-entry report-owned stack list shared by all three direct callees',
        original_frame=OLD_FRAME,new_frame=FRAME,enemy_capacity=SLOTS,code_copies=2,
        preserved=['real enemy membership/order','reward calculation','unit data','animation flags','all text and fonts'],
        runtime_required=True)
    return sorted(writes),audit

def test_layout():
    # Every length, including0,12,13,20; preserve existing locals and callers.
    for count in range(21):
        memory=bytearray(b'\xA5'*256);base=32
        for i in range(count):struct.pack_into('<I',memory,base+OLD_FRAME+i*4,0x62FC+i*0x58)
        assert memory[:base+OLD_FRAME]==b'\xA5'*(base+OLD_FRAME)
        assert memory[base+FRAME:]==b'\xA5'*(256-base-FRAME)
        for callee in (16,24,40):
            assert base-callee+(OLD_FRAME+callee)==base+OLD_FRAME
            assert [struct.unpack_from('<I',memory,base+OLD_FRAME+i*4)[0] for i in range(count)]==[0x62FC+i*0x58 for i in range(count)]
    return dict(all_counts=list(range(21)),locals_and_caller_preserved=True,three_callees_same_table=True)
