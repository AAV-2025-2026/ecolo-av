"""
reader: a thread that keeps a decoder running and reads it as fast as frames come.

Each frame goes into a Latest slot with its arrival time (wall clock, ns). When the
stream ends (the Pi restarts, the network drops), the decoder stops and starts again
after a pause that grows from `retry` to `retry_max` s, so a missing camera costs little.
"""

import threading
import time


class Reader:

    def __init__(self, make_source, latest, retry=1.0, retry_max=5.0, log=print,
                 clock_ns=time.time_ns):
        self.make_source = make_source      # () -> a source with start(), read(), stop()
        self.latest = latest
        self.retry, self.retry_max = retry, retry_max
        self.log = log
        self.clock_ns = clock_ns
        self.connected = False
        self.frames = 0
        self.starts = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name='stream-reader', daemon=True)
        self._source = None

    def start(self):
        self._thread.start()

    def stop(self, timeout=5.0):
        self._stop.set()
        source = self._source
        if source is not None:
            source.stop()               # unblocks a read() waiting on the pipe
        self._thread.join(timeout)

    def _run(self):
        pause = self.retry
        while not self._stop.is_set():
            source = self.make_source()
            self._source = source
            self.starts += 1
            got = 0
            try:
                source.start()
                while not self._stop.is_set():
                    frame = source.read()
                    if frame is None:
                        break
                    if not self.connected:
                        self.connected = True
                        self.log('stream: pictures coming')
                    got += 1
                    self.frames += 1
                    self.latest.put((frame, self.clock_ns()))
            except (OSError, ValueError) as e:
                self.log(f'stream: {e}')
            finally:
                source.stop()
                self._source = None
            if self._stop.is_set():
                break
            if self.connected:
                self.log('stream: ended; trying again')
            self.connected = False
            # A stream that ran a while starts again quickly; one that never came, slower.
            pause = self.retry if got else min(self.retry_max, pause * 2)
            self._stop.wait(pause)
