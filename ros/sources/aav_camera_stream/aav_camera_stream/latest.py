"""
latest: hand the newest frame from the reader thread to the worker, dropping old ones.

The decoder must be read as fast as frames come, or they queue up in the pipe and the
socket and every frame arrives later than the one before. The worker (undistort, the
detector) may be slower, so it takes only the newest frame; the ones it never saw count
as dropped. Also Rate and Delays, the numbers the node reports.
"""

import statistics
import threading
import time


class Latest:
    """A one-frame slot: put() replaces, take() waits for one newer than the last."""

    def __init__(self):
        self._cond = threading.Condition()
        self._item = None
        self._fresh = False
        self.put_count = 0
        self.dropped = 0

    def put(self, item) -> None:
        with self._cond:
            if self._fresh:
                self.dropped += 1       # replaced before anyone took it
            self._item, self._fresh = item, True
            self.put_count += 1
            self._cond.notify_all()

    def take(self, timeout: float):
        """Return the newest item not taken yet, or None after timeout s."""
        with self._cond:
            if not self._cond.wait_for(lambda: self._fresh, timeout):
                return None
            self._fresh = False
            return self._item


class Rate:
    """Events per second over the last `window` s."""

    def __init__(self, window: float = 5.0, clock=time.monotonic):
        self.window = window
        self.clock = clock
        self._times = []

    def tick(self) -> None:
        now = self.clock()
        self._times.append(now)
        self._trim(now)

    def hz(self) -> float:
        now = self.clock()
        self._trim(now)
        if len(self._times) < 2:
            return 0.0
        span = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / span if span > 0 else 0.0

    def _trim(self, now):
        while self._times and self._times[0] < now - self.window:
            self._times.pop(0)


class Delays:
    """Delays in s, kept to the last `keep`: the median, the 95th percentile, the worst."""

    def __init__(self, keep: int = 600):
        self.keep = keep
        self.values = []
        self.count = 0

    def add(self, seconds: float) -> None:
        self.values.append(seconds)
        self.count += 1
        if len(self.values) > self.keep:
            del self.values[:len(self.values) - self.keep]

    def summary(self):
        """{'n', 'median', 'p95', 'max'} in s, or None with no values yet."""
        if not self.values:
            return None
        ordered = sorted(self.values)
        p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
        return {'n': len(ordered), 'median': statistics.median(ordered), 'p95': p95,
                'max': ordered[-1]}


def stamp_ns(arrival_wall_ns: int, now_clock_ns: int, now_wall_ns: int, delay_s: float) -> int:
    """
    Return the frame's stamp on the node's clock: its arrival minus the delay.

    The arrival is wall-clock time (taken in the reader thread). The node's clock is the
    same on the car, and simulated time in a simulator: the arrival moves over by the
    difference between the two clocks now. Never before 0.
    """
    offset = now_clock_ns - now_wall_ns
    return max(0, arrival_wall_ns + offset - int(round(delay_s * 1e9)))
