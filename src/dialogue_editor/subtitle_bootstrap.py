"""Bounded subtitle loader: reject missing card data before copying.

The movie command remains latched during narration. Repeatedly copying a
missing 12 KiB card payload on every VBlank stalls the native raster updates.
Keep the established A/B allocations, ABI and the 0x52580 movie-route return
anchor, but validate the two spaced BRAM header bytes before the bulk copy.
"""
from __future__ import annotations

from build_deployment_menu_hook import Assembler
from build_dense_charset_engine import encode_jr
import v810_profile_codec as v810

# Current product contract, independent of historical builders' import order.
# Successor145 moved SUBTITLE.BIN from internal BRAM to the external card.
BOOT_A_RAM, BOOT_A_COOKED, BOOT_A_CAPACITY = 0x52512, 0x4B512, 0x24
BOOT_B_RAM, BOOT_B_COOKED, BOOT_B_CAPACITY = 0x52538, 0x4B538, 0x60
TARGET_RAM = 0x1A8118
BRAM_FILE_OFFSET, BRAM_BUS_ADDRESS = 0x2600, 0xE8004C00
MOVIE_COMMAND_HIGH_RAM, MOVIE_COMMAND_HIGH_EXPECTED = 0x1A1, 1


def build(payload_bytes: int, payload_signature: int) -> tuple[bytes, bytes, dict]:
    if not 0 < payload_bytes <= 0x7FFF:
        raise ValueError("subtitle payload exceeds signed MOVEA length")
    signature = payload_signature & 0xFFFF
    if signature != 0xA463:
        raise ValueError("subtitle entry instruction/header contract changed")
    signed_signature = signature - 0x10000
    b = Assembler(BOOT_B_RAM)
    b.label("check_payload")
    b.load_address(TARGET_RAM, 11)
    b.load(0x31, 0, 11, 10)
    b.movea(signature, 0, 17)
    b.reg(0x03, 17, 10)
    b.branch(0x42, "payload_ready")
    b.load_address(BRAM_BUS_ADDRESS, 10)

    b.label("check_card_header")
    # PC-FX card bytes occupy even bus addresses. LD.B sign-extends;
    # sign-extending the high byte then shifting produces the same signed
    # 16-bit header as the resident LD.H. The expected low byte is < 0x80.
    b.load(0x30, 0, 10, 31)
    b.load(0x30, 2, 10, 17)
    b.imm5(0x14, 8, 17)
    b.reg(0x0C, 31, 17)
    b.addi(-signed_signature, 17, 17)
    b.branch(0x4A, "done")

    b.movea(payload_bytes, 0, 17)
    b.label("copy_loop")
    b.load(0x30, 0, 10, 31)
    b.store(0x34, 0, 11, 31)
    b.add_i(2, 10)
    b.add_i(1, 11)
    b.add_i(-1, 17)
    b.branch(0x4A, "copy_loop")
    # Preserve the exact JAL/return anchor used to distinguish automatic
    # Opening 2. No new code space or unrelated native bytes are reclaimed.
    if b.pc != 0x5257A:
        raise ValueError(f"subtitle loader layout drift: {b.pc:#x}")
    b.code.extend(v810.encode(v810.instruction(0x4D, displacement=0)))
    b.label("payload_ready")
    b.jal(TARGET_RAM)
    b.label("done")
    b.load(0x33, 0x09C4, 0, 17)
    for offset, register in ((8, 11), (4, 10), (0, 31)):
        b.load(0x33, offset, 3, register)
    b.addi(12, 3, 3)
    b.add_i(2, 31)
    b.reg(0x06, 31, 0)
    segment_b = b.finish()
    if len(segment_b) != BOOT_B_CAPACITY or b.labels["done"] != 0x52580:
        raise ValueError("subtitle B allocation/route anchor drift")

    a = Assembler(BOOT_A_RAM)
    a.label("bootstrap")
    a.addi(-12, 3, 3)
    for offset, register in ((0, 31), (4, 10), (8, 11)):
        a.store(0x37, offset, 3, register)
    a.add_i(1, 17)
    a.store(0x37, 0x09C4, 0, 17)
    a.load(0x30, MOVIE_COMMAND_HIGH_RAM, 0, 11)
    a.mov_i(MOVIE_COMMAND_HIGH_EXPECTED, 17)
    a.reg(0x03, 17, 11)
    displacement = b.labels["done"] - a.pc
    if displacement % 2 or not -256 <= displacement <= 254:
        raise ValueError("subtitle cross-segment branch out of range")
    a.code.extend(v810.encode(v810.instruction(0x4A, displacement=displacement)))
    a.code.extend(encode_jr(a.pc, b.labels["check_payload"]))
    segment_a = a.finish()
    if len(segment_a) != BOOT_A_CAPACITY:
        raise ValueError("subtitle A allocation drift")
    for pc, code in ((BOOT_A_RAM, segment_a), (BOOT_B_RAM, segment_b)):
        offset = 0
        while offset < len(code):
            instruction = v810.decode(code, offset, pc + offset)
            if v810.encode(instruction) != code[offset:offset + instruction.size]:
                raise ValueError("subtitle instruction round-trip mismatch")
            offset += instruction.size
    return segment_a, segment_b, {**a.labels, **b.labels}


def build_disc_resident(
    target_ram: int, payload_signature: int
) -> tuple[bytes, bytes, dict]:
    """Build the guarded VBlank bridge for an already boot-loaded payload.

    Keep the native movie-command guard and, critically, the 0x52580 return
    anchor used to distinguish automatic Opening 2.  Only the external-card
    validation/copy loop is removed; the renderer is called after confirming
    that its entry signature is resident at ``target_ram``.
    """
    signature = payload_signature & 0xFFFF
    if signature != 0xA463:
        raise ValueError("subtitle entry instruction/header contract changed")
    b = Assembler(BOOT_B_RAM)
    b.label("check_payload")
    b.load_address(target_ram, 11)
    b.load(0x31, 0, 11, 10)
    b.movea(signature, 0, 17)
    b.reg(0x03, 17, 10)
    b.branch(0x4A, "done")
    while b.pc < 0x5257C:
        b.code.extend(b"\x00\x00")
    if b.pc != 0x5257C:
        raise ValueError(f"disc subtitle bridge layout drift: {b.pc:#x}")
    b.label("payload_ready")
    b.jal(target_ram)
    b.label("done")
    b.load(0x33, 0x09C4, 0, 17)
    for offset, register in ((8, 11), (4, 10), (0, 31)):
        b.load(0x33, offset, 3, register)
    b.addi(12, 3, 3)
    b.add_i(2, 31)
    b.reg(0x06, 31, 0)
    segment_b = b.finish()
    if len(segment_b) != BOOT_B_CAPACITY or b.labels["done"] != 0x52580:
        raise ValueError("disc subtitle B allocation/route anchor drift")

    a = Assembler(BOOT_A_RAM)
    a.label("bootstrap")
    a.addi(-12, 3, 3)
    for offset, register in ((0, 31), (4, 10), (8, 11)):
        a.store(0x37, offset, 3, register)
    a.add_i(1, 17)
    a.store(0x37, 0x09C4, 0, 17)
    a.load(0x30, MOVIE_COMMAND_HIGH_RAM, 0, 11)
    a.mov_i(MOVIE_COMMAND_HIGH_EXPECTED, 17)
    a.reg(0x03, 17, 11)
    displacement = b.labels["done"] - a.pc
    if displacement % 2 or not -256 <= displacement <= 254:
        raise ValueError("subtitle cross-segment branch out of range")
    a.code.extend(v810.encode(v810.instruction(0x4A, displacement=displacement)))
    a.code.extend(encode_jr(a.pc, b.labels["check_payload"]))
    segment_a = a.finish()
    if len(segment_a) != BOOT_A_CAPACITY:
        raise ValueError("disc subtitle A allocation drift")

    for pc, code in ((BOOT_A_RAM, segment_a), (BOOT_B_RAM, segment_b)):
        offset = 0
        while offset < len(code):
            instruction = v810.decode(code, offset, pc + offset)
            if v810.encode(instruction) != code[offset:offset + instruction.size]:
                raise ValueError("disc subtitle instruction round-trip mismatch")
            offset += instruction.size
    return segment_a, segment_b, {**a.labels, **b.labels}


def build_disc_staged(
    source_ram: int,
    target_ram: int,
    payload_bytes: int,
    payload_signature: int,
) -> tuple[bytes, bytes, dict]:
    """Build a bridge which restores an overwritten renderer on demand.

    ``source_ram`` is an immutable copy made by the disc startup loader.  The
    ordinary presentation loader is allowed to reuse ``target_ram``; on the
    first VBlank of a movie this bridge restores the renderer before calling
    it.  Keeping the source and executable allocations separate also leaves
    the game's low-RAM work area untouched during ordinary gameplay.
    """
    if payload_bytes <= 0 or payload_bytes % 4:
        raise ValueError("staged subtitle payload must be positive/word aligned")
    word_count = payload_bytes // 4
    if word_count > 0x7FFF:
        raise ValueError("staged subtitle payload exceeds signed word count")
    signature = payload_signature & 0xFFFF
    if signature != 0xA463:
        raise ValueError("subtitle entry instruction/header contract changed")

    b = Assembler(BOOT_B_RAM)
    b.label("check_payload")
    b.load_address(target_ram, 11)
    b.load(0x31, 0, 11, 10)
    b.movea(signature, 0, 17)
    b.reg(0x03, 17, 10)
    b.branch(0x42, "payload_ready")
    b.load_address(source_ram, 10)
    b.movea(word_count, 0, 17)
    b.label("copy_loop")
    b.load(0x33, 0, 10, 31)
    b.store(0x37, 0, 11, 31)
    b.add_i(4, 10)
    b.add_i(4, 11)
    b.add_i(-1, 17)
    b.branch(0x4A, "copy_loop")
    while b.pc < 0x5257C:
        b.code.extend(b"\x00\x00")
    if b.pc != 0x5257C:
        raise ValueError(f"staged subtitle bridge layout drift: {b.pc:#x}")
    b.label("payload_ready")
    b.jal(target_ram)
    b.label("done")
    b.load(0x33, 0x09C4, 0, 17)
    for offset, register in ((8, 11), (4, 10), (0, 31)):
        b.load(0x33, offset, 3, register)
    b.addi(12, 3, 3)
    b.add_i(2, 31)
    b.reg(0x06, 31, 0)
    segment_b = b.finish()
    if len(segment_b) != BOOT_B_CAPACITY or b.labels["done"] != 0x52580:
        raise ValueError("staged subtitle B allocation/route anchor drift")

    a = Assembler(BOOT_A_RAM)
    a.label("bootstrap")
    a.addi(-12, 3, 3)
    for offset, register in ((0, 31), (4, 10), (8, 11)):
        a.store(0x37, offset, 3, register)
    a.add_i(1, 17)
    a.store(0x37, 0x09C4, 0, 17)
    a.load(0x30, MOVIE_COMMAND_HIGH_RAM, 0, 11)
    a.mov_i(MOVIE_COMMAND_HIGH_EXPECTED, 17)
    a.reg(0x03, 17, 11)
    displacement = b.labels["done"] - a.pc
    if displacement % 2 or not -256 <= displacement <= 254:
        raise ValueError("subtitle cross-segment branch out of range")
    a.code.extend(v810.encode(v810.instruction(0x4A, displacement=displacement)))
    a.code.extend(encode_jr(a.pc, b.labels["check_payload"]))
    segment_a = a.finish()
    if len(segment_a) != BOOT_A_CAPACITY:
        raise ValueError("staged subtitle A allocation drift")

    for pc, code in ((BOOT_A_RAM, segment_a), (BOOT_B_RAM, segment_b)):
        offset = 0
        while offset < len(code):
            instruction = v810.decode(code, offset, pc + offset)
            if v810.encode(instruction) != code[offset:offset + instruction.size]:
                raise ValueError("staged subtitle instruction round-trip mismatch")
            offset += instruction.size
    return segment_a, segment_b, {**a.labels, **b.labels}


def build_kram_staged(
    copy_helper_ram: int,
    target_ram: int,
    payload_signature: int,
) -> tuple[bytes, bytes, dict]:
    """Build the VBlank bridge for a payload retained in KING K-RAM.

    The startup loader owns the one-time MAIN-to-K-RAM upload.  Ordinary game
    overlays may then reuse ``target_ram`` freely.  On the first VBlank of a
    movie, this compact bridge asks a boot-resident helper to restore the
    payload from K-RAM, then executes the ordinary subtitle renderer.  The
    automatic Opening-2 route anchor at 0x52580 remains byte-for-byte located
    at the established address.
    """
    signature = payload_signature & 0xFFFF
    if signature != 0xA463:
        raise ValueError("subtitle entry instruction/header contract changed")

    b = Assembler(BOOT_B_RAM)
    b.label("check_payload")
    b.load_address(target_ram, 11)
    b.load(0x31, 0, 11, 10)
    b.movea(signature, 0, 17)
    b.reg(0x03, 17, 10)
    b.branch(0x42, "payload_ready")
    b.jal(copy_helper_ram)
    b.label("payload_ready")
    b.jal(target_ram)
    while b.pc < 0x52580:
        b.code.extend(b"\x00\x00")
    if b.pc != 0x52580:
        raise ValueError(f"K-RAM subtitle bridge layout drift: {b.pc:#x}")
    b.label("done")
    b.load(0x33, 0x09C4, 0, 17)
    for offset, register in ((8, 11), (4, 10), (0, 31)):
        b.load(0x33, offset, 3, register)
    b.addi(12, 3, 3)
    b.add_i(2, 31)
    b.reg(0x06, 31, 0)
    segment_b = b.finish()
    if len(segment_b) != BOOT_B_CAPACITY or b.labels["done"] != 0x52580:
        raise ValueError("K-RAM subtitle B allocation/route anchor drift")

    a = Assembler(BOOT_A_RAM)
    a.label("bootstrap")
    a.addi(-12, 3, 3)
    for offset, register in ((0, 31), (4, 10), (8, 11)):
        a.store(0x37, offset, 3, register)
    a.add_i(1, 17)
    a.store(0x37, 0x09C4, 0, 17)
    a.load(0x30, MOVIE_COMMAND_HIGH_RAM, 0, 11)
    a.mov_i(MOVIE_COMMAND_HIGH_EXPECTED, 17)
    a.reg(0x03, 17, 11)
    displacement = b.labels["done"] - a.pc
    if displacement % 2 or not -256 <= displacement <= 254:
        raise ValueError("subtitle cross-segment branch out of range")
    a.code.extend(v810.encode(v810.instruction(0x4A, displacement=displacement)))
    a.code.extend(encode_jr(a.pc, b.labels["check_payload"]))
    segment_a = a.finish()
    if len(segment_a) != BOOT_A_CAPACITY:
        raise ValueError("K-RAM subtitle A allocation drift")

    for pc, code in ((BOOT_A_RAM, segment_a), (BOOT_B_RAM, segment_b)):
        offset = 0
        while offset < len(code):
            instruction = v810.decode(code, offset, pc + offset)
            if v810.encode(instruction) != code[offset:offset + instruction.size]:
                raise ValueError("K-RAM subtitle instruction round-trip mismatch")
            offset += instruction.size
    return segment_a, segment_b, {**a.labels, **b.labels}


def build_kram_staged_latched(
    copy_helper_ram: int,
    route_guard_ram: int,
    cleanup_return_ram: int,
    target_ram: int,
    payload_signature: int,
) -> tuple[bytes, bytes, dict]:
    """Build the K-RAM bridge with an external physical-movie route latch.

    Some scenario-clear callers expose the physical 0..29 movie number only
    during decoder setup, then restore their event argument at MAIN[0x1A4]
    before the first subtitle cue.  The resident route helper owns that short
    lifetime and temporarily presents a normal movie command/id to the
    renderer.  The helper also restores the two native words before returning
    to the interrupted VBlank handler.

    BOOT_B's ``done`` label deliberately remains at 0x52580.  That address is
    an independently observed native discriminator for automatic Opening 2.
    """
    signature = payload_signature & 0xFFFF
    if signature != 0xA463:
        raise ValueError("subtitle entry instruction/header contract changed")

    b = Assembler(BOOT_B_RAM)
    b.label("check_payload")
    b.load_address(target_ram, 11)
    b.load(0x31, 0, 11, 10)
    b.movea(signature, 0, 17)
    b.reg(0x03, 17, 10)
    b.branch(0x42, "payload_ready")
    b.jal(copy_helper_ram)
    b.label("payload_ready")
    b.jal(target_ram)
    while b.pc < 0x52580:
        b.code.extend(b"\x00\x00")
    if b.pc != 0x52580:
        raise ValueError(f"latched K-RAM bridge layout drift: {b.pc:#x}")
    b.label("done")
    b.code.extend(encode_jr(b.pc, cleanup_return_ram))
    while len(b.code) < BOOT_B_CAPACITY:
        b.code.extend(b"\x00\x00")
    segment_b = b.finish()
    if len(segment_b) != BOOT_B_CAPACITY or b.labels["done"] != 0x52580:
        raise ValueError("latched K-RAM B allocation/route anchor drift")

    a = Assembler(BOOT_A_RAM)
    a.label("bootstrap")
    a.addi(-12, 3, 3)
    for offset, register in ((0, 31), (4, 10), (8, 11)):
        a.store(0x37, offset, 3, register)
    a.add_i(1, 17)
    a.store(0x37, 0x09C4, 0, 17)
    a.code.extend(encode_jr(a.pc, route_guard_ram))
    while len(a.code) < BOOT_A_CAPACITY:
        a.code.extend(b"\x00\x00")
    segment_a = a.finish()
    if len(segment_a) != BOOT_A_CAPACITY:
        raise ValueError("latched K-RAM A allocation drift")

    for pc, code in ((BOOT_A_RAM, segment_a), (BOOT_B_RAM, segment_b)):
        offset = 0
        while offset < len(code):
            instruction = v810.decode(code, offset, pc + offset)
            if v810.encode(instruction) != code[offset:offset + instruction.size]:
                raise ValueError("latched subtitle instruction round-trip mismatch")
            offset += instruction.size
    return segment_a, segment_b, {**a.labels, **b.labels}
