from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .crc16 import crc16_ccitt_false

START1 = 0xAA
START2 = 0x55
VERSION = 0x01
FRAME_LEN = 13

FLAG_ARMED = 1 << 0
FLAG_ESTOP = 1 << 1
FLAG_DIR_FWD = 1 << 2


@dataclass
class CmdFrame:
    seq: int
    armed: bool
    estop: bool
    dir_fwd: bool
    steer: int
    throttle: int
    brake: int


def pack_frame(cmd: CmdFrame) -> bytes:
    seq = cmd.seq & 0xFF
    flags = 0
    if cmd.armed:
        flags |= FLAG_ARMED
    if cmd.estop:
        flags |= FLAG_ESTOP
    if cmd.dir_fwd:
        flags |= FLAG_DIR_FWD

    steer = max(-32768, min(32767, int(cmd.steer)))
    throttle = max(0, min(65535, int(cmd.throttle)))
    brake = max(0, min(65535, int(cmd.brake)))

    buf = bytearray()
    buf.append(START1)
    buf.append(START2)
    buf.append(VERSION)
    buf.append(seq)
    buf.append(flags)
    buf.extend(steer.to_bytes(2, 'little', signed=True))
    buf.extend(throttle.to_bytes(2, 'little', signed=False))
    buf.extend(brake.to_bytes(2, 'little', signed=False))
    crc = crc16_ccitt_false(bytes(buf))
    buf.extend(crc.to_bytes(2, 'little', signed=False))
    return bytes(buf)


def unpack_frame(buf: bytes) -> Tuple[bool, CmdFrame | None]:
    if len(buf) != FRAME_LEN:
        return False, None
    if buf[0] != START1 or buf[1] != START2 or buf[2] != VERSION:
        return False, None
    crc_rx = int.from_bytes(buf[11:13], 'little', signed=False)
    crc_calc = crc16_ccitt_false(buf[:11])
    if crc_rx != crc_calc:
        return False, None

    flags = buf[4]
    cmd = CmdFrame(
        seq=buf[3],
        armed=bool(flags & FLAG_ARMED),
        estop=bool(flags & FLAG_ESTOP),
        dir_fwd=bool(flags & FLAG_DIR_FWD),
        steer=int.from_bytes(buf[5:7], 'little', signed=True),
        throttle=int.from_bytes(buf[7:9], 'little', signed=False),
        brake=int.from_bytes(buf[9:11], 'little', signed=False),
    )
    return True, cmd
