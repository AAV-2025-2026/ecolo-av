#!/usr/bin/env python3
"""
The HUD's real web server (aav_hud's web.py) with a fake car behind it, and no ROS.

tools/hud_test.sh runs the app's own client code (hud/flutter_pi/test_bench) against it:
the real Socket.IO and HTTP on both sides, so an app and a back end that can't talk
fail a test, not a drive. The fake car says it's armed and driving; POST /estop turns
its e-stop on, as spine_bridge would report it.

usage: tools/hud_fake_backend.py      prints "port <n>", then serves on 127.0.0.1:<n>

Needs Flask-SocketIO and simple-websocket (the pixi environment has both).
"""

from pathlib import Path
import socket
import sys

# web.py, events.py and png.py have no ROS imports: the package's folder is enough.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros' / 'hud' / 'aav_hud'))

from aav_hud import events, png  # noqa: E402
from aav_hud.web import HudWeb  # noqa: E402


class FakeCar:
    """What hud_server gives web.py: follow, cancel, estop and camera_png."""

    def __init__(self):
        self.web = None
        self.estop_on = False

    def status(self):
        return {'mode': 'computer', 'armed': not self.estop_on, 'estop': self.estop_on,
                'gear': 'P' if self.estop_on else 'D', 'speed': 0.0 if self.estop_on else 1.0,
                'steering_angle': 0.0, 'throttle': 0.0, 'brake': 1.0 if self.estop_on else 0.0,
                'faults': []}

    def follow(self, waypoints):
        return None

    def cancel(self):
        return 'no route is being followed'

    def estop(self):
        self.estop_on = True
        self.web.send(events.VEHICLE, self.status())
        return None

    def camera_png(self):
        return png.encode(2, 1, 'mono8', 2, bytes([0, 255]))


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def main():
    car = FakeCar()
    car.web = HudWeb(car)
    car.web.send(events.VEHICLE, car.status())
    car.web.send(events.SPEED, {'speed': 1.0})
    car.web.send(events.BATTERY, {'voltage': 50.9, 'percentage': 99.7, 'current': None})
    port = free_port()
    print(f'port {port}', flush=True)
    car.web.run('127.0.0.1', port)


if __name__ == '__main__':
    main()
