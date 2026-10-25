"""
The uplink on ROS (TODO 50, 48): the ESP32's frames in, the car's state and the RC out.

The real nodes, on a private ROS domain on this computer: legacy_uart_bridge (uplink true),
whose serial port is a pseudo-terminal this test writes the ESP32's uplink frames into,
and rc_driver (aav_rc).

  uplink frames, switch on RC via ROS -> /vehicle/status, /vehicle/rc, /vehicle/steering,
                                         and rc_driver's /drivers/rc/cmd_vel from the sticks
  the switch back on computer         -> one zero, then nothing
  uplink false (the default)          -> none of it: the bridge reads nothing back
"""

import fcntl
import math
import os
import random
import time

import pytest

try:
    from aav_interfaces.msg import ActuatorState, RcSticks, VehicleStatus
    from aav_legacy.legacy_protocol import (MODE_COMPUTER, pack_uplink, SWITCH_COMPUTER,
                                            SWITCH_RC_VIA_ROS, Uplink)
    from aav_legacy.legacy_uart_bridge import LegacyUartBridge
    from aav_rc.rc_driver import RcDriver
    from geometry_msgs.msg import TwistStamped
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    HAVE_ROS = True
except ImportError:
    HAVE_ROS = False

pytestmark = pytest.mark.skipif(not HAVE_ROS, reason='needs ROS 2 and the built workspace')


def uplink(sequence, switch, throttle=0.5, steering=0.25):
    return Uplink(sequence=sequence & 0xFF, echo=sequence & 0xFF, mode=MODE_COMPUTER,
                  switch=switch, armed=True, estop=False, faults=0, steering=0.125,
                  brake_position=0.0, throttle_out=0.2, brake_out=0.0, rc_throttle=throttle,
                  rc_steering=steering, rc_brake=False)


class Run:
    """The bridge on a pseudo-terminal, rc_driver, and a test node, spun together."""

    def __init__(self, uplink_on=True):
        os.environ['ROS_AUTOMATIC_DISCOVERY_RANGE'] = 'LOCALHOST'
        self.master, self.slave = os.openpty()
        port = os.ttyname(self.slave)
        fcntl.fcntl(self.master, fcntl.F_SETFL,
                    fcntl.fcntl(self.master, fcntl.F_GETFL) | os.O_NONBLOCK)
        args = ['--ros-args', '-p', f'legacy_uart_bridge:port:={port}',
                '-p', 'legacy_uart_bridge:frame_version:=2',
                '-p', f'legacy_uart_bridge:uplink:={str(uplink_on).lower()}']
        rclpy.init(args=args, domain_id=random.randint(150, 230))
        self.executor = SingleThreadedExecutor()
        self.nodes = [LegacyUartBridge(), RcDriver()]
        self.test = rclpy.create_node('uplink_test')
        self.nodes.append(self.test)
        self.got = {'status': [], 'rc': [], 'steering': [], 'cmd': []}
        for kind, msg, topic in (('status', VehicleStatus, '/vehicle/status'),
                                 ('rc', RcSticks, '/vehicle/rc'),
                                 ('steering', ActuatorState, '/vehicle/steering'),
                                 ('cmd', TwistStamped, '/drivers/rc/cmd_vel')):
            self.test.create_subscription(
                msg, topic, lambda m, k=kind: self.got[k].append((time.monotonic(), m)), 100)
        for n in self.nodes:
            self.executor.add_node(n)
        self.sequence = 0

    def spin(self, seconds, switch=None, **sticks):
        """Spin for this long; the ESP32 sends an uplink frame every 20 ms if `switch`."""
        end = time.monotonic() + seconds
        next_frame = time.monotonic()
        while time.monotonic() < end:
            if switch is not None and time.monotonic() >= next_frame:
                try:
                    os.write(self.master, pack_uplink(uplink(self.sequence, switch, **sticks)))
                except BlockingIOError:
                    pass                            # nobody reads (uplink false): full
                self.sequence += 1
                next_frame += 0.02
            self.executor.spin_once(timeout_sec=0.005)
            try:
                while os.read(self.master, 4096):   # drain the bridge's frames
                    pass
            except BlockingIOError:
                pass

    def since(self, kind, t):
        return [m for at, m in self.got[kind] if at >= t]

    def close(self):
        for n in self.nodes:
            n.destroy_node()
        self.executor.shutdown()
        rclpy.shutdown()
        os.close(self.master)
        os.close(self.slave)


@pytest.fixture
def run(request):
    r = Run(**getattr(request, 'param', {}))
    yield r
    r.close()


def test_rc_via_ros_sticks_become_the_rc_drivers_command(run):
    run.spin(1.5, SWITCH_RC_VIA_ROS, throttle=0.5, steering=0.25)
    t = time.monotonic()
    run.spin(1.0, SWITCH_RC_VIA_ROS, throttle=0.5, steering=0.25)
    rc = run.since('rc', t)
    assert len(rc) > 35                                 # ~50 a second
    assert rc[-1].mode_switch == RcSticks.SWITCH_RC_VIA_ROS
    assert (rc[-1].throttle, rc[-1].steering) == (0.5, 0.25)
    cmds = run.since('cmd', t)
    assert len(cmds) > 35                               # rc_driver's 50 Hz
    want_w = 0.5 * math.tan(0.25 * 0.5) / 1.57          # the defaults: 1 m/s, 0.5 rad, 1.57 m
    assert all(c.twist.linear.x == pytest.approx(0.5) for c in cmds)
    assert all(c.twist.angular.z == pytest.approx(want_w, rel=1e-4) for c in cmds)
    assert cmds[-1].header.frame_id == 'base_link'
    status = run.since('status', t)
    assert 6 <= len(status) <= 14                       # 10 Hz
    s = status[-1]
    assert (s.mode, s.armed, s.estop_active) == (VehicleStatus.MODE_COMPUTER, True, False)
    assert math.isnan(s.speed) and s.steering_angle == pytest.approx(0.125)
    steering = run.since('steering', t)
    assert steering and steering[-1].measured == pytest.approx(0.125)
    assert math.isnan(steering[-1].command)            # no command from ego here

    # The switch back on computer: one zero, then nothing.
    t = time.monotonic()
    run.spin(1.0, SWITCH_COMPUTER, throttle=0.5, steering=0.25)
    after = run.since('cmd', t + 0.1)
    assert len(after) <= 1
    assert all(c.twist.linear.x == 0.0 for c in after)


def test_quiet_uplink_on_rc_via_ros_holds_a_stop(run):
    run.spin(1.5, SWITCH_RC_VIA_ROS, throttle=1.0)
    t = time.monotonic()
    run.spin(1.0)                                       # the uplink stops
    late = run.since('cmd', t + 0.3)
    assert len(late) > 25
    assert all(c.twist.linear.x == 0.0 and c.twist.angular.z == 0.0 for c in late)


@pytest.mark.parametrize('run', [{'uplink_on': False}], indirect=True)
def test_without_the_uplink_the_bridge_reads_nothing_back(run):
    run.spin(2.0, SWITCH_RC_VIA_ROS, throttle=1.0)
    assert run.got['status'] == [] and run.got['rc'] == [] and run.got['cmd'] == []
