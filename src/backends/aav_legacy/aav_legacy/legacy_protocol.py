"""The 2025-26 car's protocols, so the new stack can drive today's hardware.

No ROS imports. Sources (read-only clones in /home/ben/aav):

UART to the ESP32 (AAV_cortex, branch 6-pico2-aav-firmware,
AAV_uMod_Firmware/src/modules/ros2_handler.cpp:17-80):
  13 bytes, no header: three little-endian float32 (steering, speed, accel),
  then checksum = sum(bytes 0..11) & 0xFF. Each value must be within -1..1.
  - steering: -1..1 of full lock each way (Jrk targets 400..1950..3500).
  - speed: |v| < 0.03 ramps the throttle to 0; otherwise the sign sets the
    direction and throttle DAC = |v| * 700, ramped per frame. Open loop.
  - accel: below -0.05 applies the brake, clamp(|a| * 3500, 400, 3500), and
    cuts the throttle at once. Otherwise the brake is released.
  The firmware sends nothing back and has NO command timeout: if frames stop,
  the last throttle stays on. See docs/firmware.md before driving.

UDP from the wheel encoder (Wheel_Encoders, wiznet.ino:9-19,110-131):
  a 4-byte big-endian int32: signed spoke count since the previous packet,
  about every 100 ms, to port 10111. 8 spokes per wheel revolution.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import Tuple

FRAME_LEN = 13


@dataclass
class LegacyMapping:
    max_steering_angle: float = 0.5   # rad at full lock (TODO: measure)
    steering_sign: float = 1.0        # -1 if +1 steers right on this car (TODO: check)
    full_throttle_speed: float = 3.0  # m/s the car reaches at speed = 1.0 (TODO: measure)
    stop_speed: float = 0.05          # m/s below which ego's command means stand still
    hold_brake: float = 0.3           # brake (0..1) while standing still
    stop_brake: float = 1.0           # brake (0..1) when commands go stale


def clamp1(x: float) -> float:
    return max(-1.0, min(1.0, x))


def to_legacy(speed: float, steering: float, m: LegacyMapping) -> Tuple[float, float, float]:
    """Return (steering, speed, accel), each -1..1, for an ego command in m/s and rad."""
    s = clamp1(m.steering_sign * steering / m.max_steering_angle)
    if abs(speed) < m.stop_speed:
        return s, 0.0, -abs(m.hold_brake)
    v = clamp1(speed / m.full_throttle_speed)
    if abs(v) < 0.031:            # the firmware ignores |v| < 0.03; creep instead
        v = math.copysign(0.031, v)
    return s, v, 0.0


def stop_command(m: LegacyMapping, steering_hold: float = 0.0) -> Tuple[float, float, float]:
    """Return the frame values for a stale-command stop: no throttle, brake on."""
    return clamp1(steering_hold), 0.0, -abs(m.stop_brake)


def pack_frame(steering: float, speed: float, accel: float) -> bytes:
    body = struct.pack('<fff', clamp1(steering), clamp1(speed), clamp1(accel))
    return body + bytes([sum(body) & 0xFF])


def unpack_frame(frame: bytes) -> Tuple[float, float, float]:
    """Decode a frame (for tests and bench tools). Raises ValueError if invalid."""
    if len(frame) != FRAME_LEN or sum(frame[:12]) & 0xFF != frame[12]:
        raise ValueError('bad legacy frame')
    return struct.unpack('<fff', frame[:12])


def encoder_counts(packet: bytes) -> int:
    """Decode one wheel-encoder UDP packet: a big-endian int32 spoke count."""
    if len(packet) != 4:
        raise ValueError(f'expected 4 bytes, got {len(packet)}')
    return struct.unpack('>i', packet)[0]


def metres_per_count(wheel_diameter: float, counts_per_rev: int) -> float:
    return math.pi * wheel_diameter / counts_per_rev
