"""
The wheels against the IMU and the GPS: do they tell the same story? No ROS here.

A wheel-speed driver stuck in a loop sends its last speed again with fresh stamps. At a
steady speed that looks exactly like a car at a steady speed, so the watchdog's frozen
check can't tell (READ-ME-FULL-SIMULATION.md, "What's left", 15 Oct). The IMU can, as soon
as the car's speed or turn changes, and the GPS can once the speed is wrong for a while:

  speed   over the last `window` s, the change in the wheels' speed against the IMU's
          forward acceleration, added up over the same time. A frozen speed says 0 while
          the IMU feels the car speed up or brake. Quick, but it sees only changes
  turn    over the same window, the wheels' mean turn rate against the IMU's gyro
  gps     over the last `gps_window` s, the speed of a straight line fitted to the GPS
          fixes against the same fitted to where the wheels (and the gyro) say the car
          went. Slower, but it sees a speed that stays wrong: wheels frozen at 0.5 m/s
          while the car drives on at 1. Both tracks are fitted the same way, so a turn
          shortens both alike. Off without a GPS; a window with a jump in it is skipped

When any gap stays over its tolerance for `persist` s, the wheels count as wrong:
DISAGREE, latched like a GPS jump, until a person clears it (the watchdog's clear service).
Frozen at a speed the car really keeps, the wheels are still right, and nothing is said:
the gaps only open when the car's speed or turn changes, which is when it matters.

The IMU's forward reading also holds gravity on a slope, and a tilt in its mounting. Its
offset is first taken while the car stands still (the wheels say 0 for a whole window),
then follows a slow average of its difference from the wheels' (bias_time s), learnt only
while they agree.

Assumes imu_link's x points forward, as vehicle.yaml mounts it. Units: m/s, m/s^2, rad/s,
seconds on the node's clock (a GPS fix: its own stamp).
"""

from collections import deque
from dataclasses import dataclass
import math
from typing import Optional, Tuple

DISAGREE = 'DISAGREE'
EARTH_RADIUS = 6371000.0    # m
JUMP_SPEED = 15.0           # m/s between two fixes, + JUMP_MARGIN m: a jump, not driving
JUMP_MARGIN = 5.0           # (as the watchdog's own GPS jump check, sensor_watchdog.yaml)
GAP = 0.3                   # s without wheels, or IMU: a hole, not to be added up across


@dataclass(frozen=True)
class CrossCheck:
    """How hard to look. The numbers are tuned in Gazebo only (docs/simulation.md)."""

    window: float = 1.5             # s of samples compared, wheels against the IMU
    speed_tolerance: float = 0.3    # m/s: wheels' change vs the IMU's, over the window
    yaw_tolerance: float = 0.15     # rad/s: mean turn rates, over the window
    persist: float = 1.0            # s a gap must last before it counts
    bias_time: float = 10.0         # s: how fast the IMU's forward offset is learnt
    gps_window: float = 6.0         # s of GPS fixes fitted
    gps_tolerance: float = 0.3      # m/s: the wheels' fitted speed vs the GPS's

    def __post_init__(self):
        for name in ('window', 'speed_tolerance', 'yaw_tolerance', 'bias_time',
                     'gps_window', 'gps_tolerance'):
            if not getattr(self, name) > 0.0:
                raise ValueError(f'cross check: {name} must be positive')
        if self.persist < 0.0:
            raise ValueError('cross check: persist must not be negative')


def trapezoid(samples, start: float, end: float) -> float:
    """Return the integral over [start, end] of (t, value) samples, sorted by t."""
    total = 0.0
    for (t0, a0), (t1, a1) in zip(samples, list(samples)[1:]):
        lo, hi = max(t0, start), min(t1, end)
        if hi <= lo:
            continue

        def at(t):
            return a0 + (a1 - a0) * (t - t0) / (t1 - t0)
        total += 0.5 * (at(lo) + at(hi)) * (hi - lo)
    return total


def fitted_speed(points) -> float:
    """Return the speed (m/s) of the straight line fitted to (t, x, y) points."""
    n = len(points)
    tm = sum(p[0] for p in points) / n
    xm = sum(p[1] for p in points) / n
    ym = sum(p[2] for p in points) / n
    tt = sum((p[0] - tm) ** 2 for p in points)
    if tt <= 0.0:
        return 0.0
    vx = sum((p[0] - tm) * (p[1] - xm) for p in points) / tt
    vy = sum((p[0] - tm) * (p[2] - ym) for p in points) / tt
    return math.hypot(vx, vy)


class WheelCheck:
    """The wheels' speed and turn rate against the IMU's and the GPS's, over sliding windows."""

    def __init__(self, check: CrossCheck = CrossCheck()):
        self.check = check
        self.wheel = deque()        # (t, speed, yaw rate)
        self.accel = deque()        # (t, forward acceleration)
        self.gyro = deque()         # (t, yaw rate)
        self.fixes = deque()        # (stamp, east m, north m), from the first fix
        self.origin = None          # the first fix's (latitude, longitude), degrees
        self.last_fix = None        # the newest fix's (latitude, longitude)
        self.track = deque()        # (t, x, y): where the wheels and the gyro say it went
        self.pose = (0.0, 0.0, 0.0)  # that track's newest x, y (m) and heading (rad)
        self.bias = None            # m/s^2: what the IMU's forward reading adds (slopes)
        self.since = None           # when the gaps last went over
        self.latched = None         # why, as text, until clear()
        self.last = None            # when update() last ran
        # The biggest gaps seen before any latch, for tuning: speed, turn, GPS.
        self.worst = (0.0, 0.0, 0.0)
        self.gaps = None            # the newest (speed, turn, GPS) gaps; None: not enough

    def wheels(self, now: float, speed: float, yaw_rate: float):
        if not (math.isfinite(speed) and math.isfinite(yaw_rate)):
            return
        if self.wheel and now - self.wheel[-1][0] > GAP:
            # The wheels were quiet (STALE): start afresh, not across the hole.
            self.wheel.clear()
            self.track.clear()
        if self.wheel:
            dt = now - self.wheel[-1][0]
            if dt > 0.0:
                turn = self.gyro[-1][1] if self.gyro else yaw_rate
                x, y, h = self.pose
                h += turn * dt
                self.pose = (x + speed * math.cos(h) * dt, y + speed * math.sin(h) * dt, h)
        self.wheel.append((now, speed, yaw_rate))
        self.track.append((now, self.pose[0], self.pose[1]))
        while self.track and self.track[0][0] < now - self.check.gps_window - 2.0:
            self.track.popleft()        # no GPS to prune it (gps_gap)

    def imu(self, now: float, forward: float, yaw_rate: float):
        # A reading the same as the last, to the bit, is a frozen IMU (a real one's noise
        # never repeats): left out, so the IMU's part goes quiet instead of blaming the
        # wheels. The watchdog's imu input says FROZEN meanwhile.
        if not (math.isfinite(forward) and math.isfinite(yaw_rate)):
            return
        if self.accel and self.gyro and (forward, yaw_rate) == (self.accel[-1][1],
                                                                self.gyro[-1][1]):
            return
        if self.accel and now - self.accel[-1][0] > GAP:
            self.accel.clear()          # quiet or frozen a while: not across the hole
            self.gyro.clear()
        self.accel.append((now, forward))
        self.gyro.append((now, yaw_rate))

    def gps(self, stamp: float, latitude: float, longitude: float):
        """Note a good GPS fix: its stamp (s), and where (degrees)."""
        if not (math.isfinite(latitude) and math.isfinite(longitude)):
            return
        if self.fixes and stamp <= self.fixes[-1][0]:
            return                  # an old fix, late
        if self.last_fix == (latitude, longitude):
            return                  # frozen: the GPS's own business, as a frozen IMU's
        self.last_fix = (latitude, longitude)
        if self.origin is None:
            self.origin = (latitude, longitude)
        lat0, lon0 = self.origin
        east = math.radians(longitude - lon0) * EARTH_RADIUS * math.cos(math.radians(lat0))
        north = math.radians(latitude - lat0) * EARTH_RADIUS
        self.fixes.append((stamp, east, north))

    def measure(self, now: float) -> Optional[Tuple[float, float, float]]:
        """
        Return (speed gap m/s, turn gap rad/s, the IMU's own mean forward reading m/s^2).

        None while the window doesn't hold enough of both: the stale checks cover silence.
        """
        start = now - self.check.window
        for q in (self.wheel, self.accel, self.gyro):
            while len(q) > 2 and q[1][0] <= start:
                q.popleft()
        wheel = [w for w in self.wheel if w[0] >= start]
        if len(wheel) < 2 or len(self.accel) < 2 or len(self.gyro) < 1:
            return None
        t0, t1 = wheel[0][0], wheel[-1][0]
        span = t1 - t0
        if (span < 0.6 * self.check.window or self.accel[0][0] > t0 + 0.1
                or self.accel[-1][0] < t1 - 0.1 or self.gyro[-1][0] < t1 - 0.1):
            return None
        felt = trapezoid(self.accel, t0, t1)
        if self.bias is None:
            # The first look: a car standing still shows the IMU's own offset.
            still = all(abs(w[1]) < 0.01 for w in wheel)
            self.bias = (felt - (wheel[-1][1] - wheel[0][1])) / span if still else 0.0
        speed_gap = abs((wheel[-1][1] - wheel[0][1]) - (felt - self.bias * span))
        gyro = [g for t, g in self.gyro if t0 <= t <= t1] or [self.gyro[-1][1]]
        turn_gap = abs(sum(w[2] for w in wheel) / len(wheel) - sum(gyro) / len(gyro))
        return speed_gap, turn_gap, (felt - (wheel[-1][1] - wheel[0][1])) / span

    def gps_gap(self) -> Optional[Tuple[float, float, float]]:
        """
        Return (gap, the wheels' fitted speed, the GPS's) over the GPS window, all m/s.

        None while there aren't enough fixes, or a jump lies between two of them.
        """
        if not self.fixes:
            return None
        start = self.fixes[-1][0] - self.check.gps_window
        while self.fixes and self.fixes[0][0] < start:
            self.fixes.popleft()
        while len(self.track) > 2 and self.track[1][0] <= start:
            self.track.popleft()
        if not self.track:
            return None
        # Only the time both cover: the wheels may have started afresh after a hole.
        lo = max(self.fixes[0][0], self.track[0][0])
        hi = min(self.fixes[-1][0], self.track[-1][0])
        fixes = [f for f in self.fixes if lo <= f[0] <= hi]
        track = [p for p in self.track if lo <= p[0] <= hi]
        enough = 0.8 * self.check.gps_window
        if len(fixes) < 8 or len(track) < 8 or hi - lo < enough:
            return None
        for (t0, x0, y0), (t1, x1, y1) in zip(fixes, fixes[1:]):
            if math.hypot(x1 - x0, y1 - y0) > JUMP_SPEED * (t1 - t0) + JUMP_MARGIN:
                return None
        wheels, gps = fitted_speed(track), fitted_speed(fixes)
        return abs(wheels - gps), wheels, gps

    def update(self, now: float) -> Optional[str]:
        """Look again (each tick); return why the wheels are wrong, or None if they're not."""
        dt = 0.0 if self.last is None else max(0.0, now - self.last)
        self.last = now
        if self.latched is not None:
            return self.latched
        got = self.measure(now)
        by_gps = self.gps_gap()
        if got is None and by_gps is None:
            self.gaps, self.since = None, None
            return None
        speed_gap, turn_gap, offset = got if got is not None else (0.0, 0.0, None)
        gps_gap = by_gps[0] if by_gps is not None else 0.0
        self.gaps = (speed_gap, turn_gap, gps_gap)
        self.worst = tuple(max(w, g) for w, g in zip(self.worst, self.gaps))
        c = self.check
        imu_wrong = speed_gap > c.speed_tolerance or turn_gap > c.yaw_tolerance
        gps_wrong = gps_gap > c.gps_tolerance
        if imu_wrong or gps_wrong:
            self.since = now if self.since is None else self.since
            if now - self.since >= c.persist:
                if imu_wrong:
                    self.latched = (f'the wheels and the IMU disagree: speed {speed_gap:.2f} '
                                    f'm/s apart over {c.window:g} s, turn {turn_gap:.2f} rad/s')
                else:
                    self.latched = (f'the wheels and the GPS disagree: the wheels '
                                    f'{by_gps[1]:.2f} m/s, the GPS {by_gps[2]:.2f} m/s over '
                                    f'{c.gps_window:g} s')
            return self.latched
        self.since = None
        if offset is not None:
            self.bias += (offset - self.bias) * min(1.0, dt / c.bias_time)
        return None

    def clear(self):
        """Forget a latched disagreement, and the samples from before it: start afresh."""
        self.latched, self.since, self.gaps = None, None, None
        for q in (self.wheel, self.accel, self.gyro, self.fixes, self.track):
            q.clear()
