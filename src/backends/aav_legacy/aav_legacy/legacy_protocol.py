"""
The 2025-26 car's protocols, so the new stack can drive today's hardware.

No ROS imports. Sources (read-only clones in /home/ben/aav):

UART to the ESP32 (AAV_cortex, branch 6-pico2-aav-firmware,
AAV_uMod_Firmware/src/modules/ros2_handler.cpp:17-80):
  13 bytes, no header: three little-endian float32 (steering, speed, accel),
  then checksum = sum(bytes 0..11) & 0xFF. Each value must be within -1..1.
  - steering: -1..1 of full lock each way (Jrk targets 400..1950..3500). The
    gain differs by side: 1950 counts per unit below 0 (the Jrk clips at 400,
    i.e. -0.795) and 1550 above. to_legacy() evens it out.
  - speed: |v| < 0.03 ramps the throttle to 0; otherwise the sign sets the
    direction and throttle DAC = |v| * 700, ramped per frame. Open loop.
  - accel: below -0.05 applies the brake, clamp(|a| * 3500, 400, 3500), and
    cuts the throttle at once. Otherwise the brake is released.
  The firmware sends nothing back and has NO command timeout: if frames stop,
  the last throttle stays on. See docs/firmware.md before driving.

UDP from the wheel encoder (Wheel_Encoders, wiznet.ino:9-19,110-131):
  a 4-byte big-endian int32: signed spoke count since the previous packet,
  about every 100 ms, to port 10111. 8 spokes per wheel revolution. It sends
  only to the Motor Pi's address, 192.168.1.193 (wiznet.ino:19). Its Rust
  version (firmware/spine/boards/wheel-encoder-pico2) sends the same bytes:
  both sides check firmware/udp/wheel_encoder_vectors.txt.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import struct
from typing import Optional, Tuple

FRAME_LEN = 13

# Scale negative steering by this, so both sides get the firmware's 1550 counts per unit.
NEGATIVE_STEERING_GAIN = 1550 / 1950


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
    if s < 0:
        s *= NEGATIVE_STEERING_GAIN
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


class EncoderSpeed:
    """
    Wheel speed from encoder packets, averaged over `window` seconds.

    speed() returns None, not 0 m/s, when packets stop for longer than `timeout`,
    and until a full window has arrived since they came back. A parked car still
    sends packets, with a count of 0.
    """

    def __init__(self, metres_per_count: float, window: float = 0.5, timeout: float = 0.3):
        self.mpc = metres_per_count
        self.window = window
        self.timeout = timeout
        self.samples = deque()   # (time in s, counts)
        self.last = None         # when the latest packet arrived
        self.since = None        # when packets last started arriving

    def add(self, t: float, counts: int) -> None:
        if self.last is None or t - self.last > self.timeout:
            self.samples.clear()
            self.since = t
        self.last = t
        self.samples.append((t, counts))

    def speed(self, t: float) -> Optional[float]:
        if self.last is None or t - self.last > self.timeout or t - self.since < self.window:
            return None
        while self.samples and self.samples[0][0] < t - self.window:
            self.samples.popleft()
        return sum(c for _, c in self.samples) * self.mpc / self.window
