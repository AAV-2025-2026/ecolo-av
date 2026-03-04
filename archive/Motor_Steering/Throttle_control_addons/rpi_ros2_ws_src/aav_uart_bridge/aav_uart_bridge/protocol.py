from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
from .crc16 import crc16_ccitt_false

START1 = 0xAA
START2 = 0x55
VERSION = 0x01

# Frame layout (13 bytes total):
# [0]  START1 = 0xAA
# [1]  START2 = 0x55
# [2]  VERSION = 0x01
# [3]  SEQ (uint8)
# [4]  FLAGS (uint8): bit0=armed, bit1=estop, bit2=dir_fwd
# [5..6]   STEER (int16 LE)  range ~[-2000..2000]
# [7..8]   THROTTLE (uint16 LE) 0..1023 (DAC units)
# [9..10]  BRAKE (uint16 LE) 0..4095
# [11..12] CRC16 (uint16 LE) over bytes [0..10] (everything except CRC)

FLAG_ARMED = 1 << 0
FLAG_ESTOP = 1 << 1
FLAG_DIR_FWD = 1 << 2

FRAME_LEN = 13

@dataclass
class CmdFrame:
    seq: int
    armed: bool
    estop: bool
    dir_fwd: bool
    steer: int              # int16
    throttle: int           # uint16
    brake: int              # uint16

def pack_frame(cmd: CmdFrame) -> bytes:
    seq = cmd.seq & 0xFF
    flags = 0
    if cmd.armed:
        flags |= FLAG_ARMED
    if cmd.estop:
        flags |= FLAG_ESTOP
    if cmd.dir_fwd:
        flags |= FLAG_DIR_FWD

    steer = int(cmd.steer)
    if steer < -32768: steer = -32768
    if steer >  32767: steer =  32767

    throttle = int(cmd.throttle)
    if throttle < 0: throttle = 0
    if throttle > 65535: throttle = 65535

    brake = int(cmd.brake)
    if brake < 0: brake = 0
    if brake > 65535: brake = 65535

    b = bytearray()
    b.append(START1)
    b.append(START2)
    b.append(VERSION)
    b.append(seq)
    b.append(flags)
    b.extend(int(steer).to_bytes(2, "little", signed=True))
    b.extend(int(throttle).to_bytes(2, "little", signed=False))
    b.extend(int(brake).to_bytes(2, "little", signed=False))

    crc = crc16_ccitt_false(bytes(b))
    b.extend(int(crc).to_bytes(2, "little", signed=False))
    return bytes(b)

def unpack_frame(buf: bytes) -> Tuple[bool, CmdFrame | None]:
    if len(buf) != FRAME_LEN:
        return False, None
    if buf[0] != START1 or buf[1] != START2:
        return False, None
    if buf[2] != VERSION:
        return False, None
    crc_rx = int.from_bytes(buf[11:13], "little", signed=False)
    crc_calc = crc16_ccitt_false(buf[:11])
    if crc_rx != crc_calc:
        return False, None

    seq = buf[3]
    flags = buf[4]
    steer = int.from_bytes(buf[5:7], "little", signed=True)
    throttle = int.from_bytes(buf[7:9], "little", signed=False)
    brake = int.from_bytes(buf[9:11], "little", signed=False)

    cmd = CmdFrame(
        seq=seq,
        armed=(flags & FLAG_ARMED) != 0,
        estop=(flags & FLAG_ESTOP) != 0,
        dir_fwd=(flags & FLAG_DIR_FWD) != 0,
        steer=steer,
        throttle=throttle,
        brake=brake,
    )
    return True, cmd
