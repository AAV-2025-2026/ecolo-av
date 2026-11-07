"""
What legacy_uart_bridge says it wrote to the ESP32 (/control/car/link_frame). No ROS here.

  Relay.frame(now) ─> serial.write ─> LinkReport.wrote(frame, sent) ─> counts every frame
                                                   │
                  a sample, link_frame_rate_hz <───┘  frame_fields: decoded from the bytes

The values come from the bytes that went out, not from what the relay meant to send, so a
packing fault shows up here. `written` means the kernel took the bytes, no more: only the
ESP32's own count says they arrived (tools/link_check.py compares the two).
"""

from __future__ import annotations

from typing import Optional

from aav_legacy.legacy_protocol import (CAL_MODE_OFF, FRAME_LEN, FRAME_V2_LEN, FRAME_V3_LEN,
                                        unpack_frame, unpack_frame_v2, unpack_frame_v3)

UINT32 = 0xFFFFFFFF


def frame_fields(frame: bytes) -> dict:
    """
    Return aav_interfaces/LinkFrame's frame fields for one written frame.

    The length says the version (13, 17, 20 bytes): version 1 has no header to read. Version
    1 has no counter and no flags, so they are 0 and false. Raises ValueError if the bytes
    aren't a good frame.
    """
    fields = {'cal_mode': CAL_MODE_OFF, 'jog_target': 0, 'check': frame[-1] if frame else 0}
    if len(frame) == FRAME_LEN:
        steering, speed, accel = unpack_frame(frame)
        fields.update(version=1, counter=0, armed=False, estop=False)
    elif len(frame) == FRAME_V2_LEN:
        f = unpack_frame_v2(frame)
        steering, speed, accel = f.steering, f.speed, f.accel
        fields.update(version=2, counter=f.counter, armed=f.armed, estop=f.estop)
    elif len(frame) == FRAME_V3_LEN:
        f = unpack_frame_v3(frame)
        steering, speed, accel = f.steering, f.speed, f.accel
        fields.update(version=3, counter=f.counter, armed=f.armed, estop=f.estop,
                      cal_mode=f.cal_mode, jog_target=f.jog_target)
    else:
        raise ValueError(f'a frame of {len(frame)} bytes: no version has that length')
    fields.update(steering=steering, speed=speed, accel=accel)
    return fields


class LinkReport:
    """Counts every write, and says when the next sample is due. rate_hz 0: no samples."""

    def __init__(self, rate_hz: float = 10.0):
        if rate_hz < 0:
            raise ValueError(f'link_frame_rate_hz {rate_hz}: use 0 (off) or more')
        self.period = 1.0 / rate_hz if rate_hz > 0 else None
        self.next_due: Optional[float] = None
        self.written = 0
        self.write_errors = 0

    def wrote(self, frame: bytes, sent: Optional[int]) -> bool:
        """
        Note a write that returned `sent` bytes (None: pyserial didn't say); True if whole.

        Part of a frame isn't a frame: the ESP32 can't count it, so neither do we.
        """
        if sent is None or sent == len(frame):
            self.written += 1
            return True
        self.write_errors += 1
        return False

    def failed(self) -> None:
        """Note a write that raised: nothing counts as written."""
        self.write_errors += 1

    def due(self, now: float) -> bool:
        """Return True if a sample is due at `now` (s), and start the next period."""
        if self.period is None:
            return False
        if self.next_due is None or now - self.next_due >= self.period:
            # The first sample, or a gap (the port was closed): start again from now.
            self.next_due = now + self.period
            return True
        if now >= self.next_due:
            self.next_due += self.period    # keeps the rate through a tick's jitter
            return True
        return False

    def fields(self, frame: bytes) -> dict:
        """Return LinkFrame's fields for this frame, and the counts so far."""
        return {**frame_fields(frame), 'written': self.written & UINT32,
                'write_errors': self.write_errors & UINT32}
