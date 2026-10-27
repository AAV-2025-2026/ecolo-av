"""
What legacy_uart_bridge writes on the serial port each tick. No ROS here.

  ego's command (/control/car/actuator_cmd) ─┐
  the Orin's counter (/control/car/heartbeat) ┼─> Relay.frame(now) ─> one frame, 50 Hz
  /safety/estop ──────────────────────────────┘

A fresh command and no e-stop: ego's values, armed. Otherwise the stale-stop values
(throttle 0, brake full, steering held), not armed. Version 2 frames carry the Orin's
counter as it last came, and the e-stop flag. The relay never makes a counter up: when
the Orin goes quiet the counter stays where it was, however many frames still go out,
and the ESP32 brakes 100 ms later (TODO 50). Version 1 is the 2025-26 13-byte frame,
for the C++ firmware: no counter, no flags.

`programs_locked` decides the no-timeout lock (/safety/legacy_uart_bridge/lock): with
version 1 the firmware has no command timeout, so twist_mux holds every program below the
actuator tests, and only people (and the tests they run) drive.
"""

from __future__ import annotations

from typing import Optional, Tuple

from aav_legacy.legacy_protocol import (LegacyMapping, pack_frame, pack_frame_v2, stop_command,
                                        to_legacy)

VERSIONS = (1, 2)
# Which frame versions go to a firmware that brakes by itself when the frames or the
# Orin's counter stop: version 2 (the Rust firmware, 100 ms). Version 1 is the 2025-26 C++.
WITH_TIMEOUT = (2,)


def programs_locked(version: int, allow_programs_without_timeout: bool = False) -> bool:
    """
    Return True if twist_mux must hold the programs (scripted, replay, point, Nav2, AI).

    True for a frame version whose firmware has no command timeout (1, the C++): if the
    bridge or the Orin dies mid-drive, the last throttle stays on, so only a person, with
    the e-stop in reach, drives. `allow_programs_without_timeout` overrides it, for a
    supervised stand (wheels off the ground) only.
    """
    if version not in VERSIONS:
        raise ValueError(f'frame_version {version}: use 1 (the C++ firmware) or 2')
    return version not in WITH_TIMEOUT and not allow_programs_without_timeout


class Relay:
    """The bridge's state: the last command, the Orin's counter, the e-stop."""

    def __init__(self, mapping: LegacyMapping, cmd_timeout: float, version: int = 2):
        if version not in VERSIONS:
            raise ValueError(f'frame_version {version}: use 1 (the C++ firmware) or 2')
        self.mapping = mapping
        self.timeout = cmd_timeout
        self.version = version
        self.cmd: Optional[Tuple[float, float]] = None   # (speed m/s, steering rad)
        self.cmd_time: Optional[float] = None
        self.counter = 0            # the Orin's, as it last came; 0 until it does
        self.heard_counter = False
        self.estop = False
        self.last_steering = 0.0

    def command(self, speed: float, steering: float, now: float) -> None:
        """Note ego's command, passed on by the output mux, at `now` (s)."""
        self.cmd = (speed, steering)
        self.cmd_time = now

    def heartbeat(self, counter: int) -> None:
        """Note the Orin's counter: it goes into every frame until the next one."""
        self.counter = counter & 0xFF
        self.heard_counter = True

    def set_estop(self, on: bool) -> bool:
        """Note /safety/estop; return True if it changed."""
        changed = on != self.estop
        self.estop = on
        return changed

    def fresh(self, now: float) -> bool:
        """Return True if ego's last command is no older than the timeout."""
        return self.cmd_time is not None and now - self.cmd_time <= self.timeout

    def frame(self, now: float) -> bytes:
        """Return this tick's frame."""
        armed = self.fresh(now) and not self.estop
        if armed:
            values = to_legacy(*self.cmd, self.mapping)
            self.last_steering = values[0]
        else:
            values = stop_command(self.mapping, self.last_steering)
        return self.pack(values, armed)

    def stop_frame(self) -> bytes:
        """Return a stale-stop frame, for leaving the car braked."""
        return self.pack(stop_command(self.mapping, self.last_steering), armed=False)

    def pack(self, values: Tuple[float, float, float], armed: bool) -> bytes:
        if self.version == 1:
            return pack_frame(*values)
        return pack_frame_v2(*values, counter=self.counter, armed=armed, estop=self.estop)
