#!/usr/bin/env python3
"""
Bench check: start bench mode, then test the whole car graph on this computer.

    pixi run bench-check          (about 2 minutes; nothing else on the network sees it)

1. Starts bench.launch.py on a private ROS domain, local to this computer.
2. Checks the running graph against docs/interfaces.yaml (check_graph.py --profile bench).
3. Waits for the spine to arm, drives a scripted profile, and compares where the model car
   really is (/bench/truth) with where the car's own software thinks it is (/odometry/global).
4. Presses the e-stop while driving: the car must stop, and the spine must say so.
5. Presses the hardware e-stop the same way, then stops everything.

Prints a table and exits 1 if anything failed. Run it after changing anything between the
drivers and the spine.
"""

import math
import os
import random
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# A private domain and localhost only, set before rclpy starts: the check can't disturb a
# car or another laptop, and nothing out there can disturb it.
os.environ['ROS_DOMAIN_ID'] = os.environ.get('AAV_BENCH_DOMAIN', str(random.randint(150, 230)))
os.environ['ROS_AUTOMATIC_DISCOVERY_RANGE'] = 'LOCALHOST'

from aav_interfaces.action import ScriptedDrive  # noqa: E402
from aav_interfaces.msg import VehicleStatus  # noqa: E402
from nav_msgs.msg import Odometry  # noqa: E402
import rclpy  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.node import Node  # noqa: E402
from std_msgs.msg import Bool  # noqa: E402
from std_srvs.srv import SetBool  # noqa: E402

RESULTS = []


def result(name, ok, detail):
    RESULTS.append((name, ok, detail))
    print(f'{"PASS" if ok else "FAIL"}  {name}: {detail}', flush=True)


class Probe(Node):

    def __init__(self):
        super().__init__('bench_check')
        self.truth = self.glob = self.status = None
        self.create_subscription(Odometry, '/bench/truth', lambda m: setattr(self, 'truth', m), 10)
        self.create_subscription(Odometry, '/odometry/global',
                                 lambda m: setattr(self, 'glob', m), 10)
        self.create_subscription(VehicleStatus, '/vehicle/status',
                                 lambda m: setattr(self, 'status', m), 10)
        self.estop = self.create_publisher(Bool, '/estop', 10)
        self.hw_estop = self.create_publisher(Bool, '/bench/hw_estop', 10)
        self.arm_client = self.create_client(SetBool, '/spine/arm')
        self.drive = ActionClient(self, ScriptedDrive, '/scripted_drive')

    def spin_for(self, seconds, until=None):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)
            if until is not None and until():
                return True
        return until is None

    def xy(self, msg):
        return msg.pose.pose.position.x, msg.pose.pose.position.y

    def arm(self):
        if not self.arm_client.wait_for_service(timeout_sec=20.0):
            return False
        future = self.arm_client.call_async(SetBool.Request(data=True))
        self.spin_for(10.0, lambda: future.done())
        return future.done() and future.result().success

    def arm_and_hold(self, tries=3):
        """Arm, and wait until the spine has stayed armed for 2 s."""
        for _ in range(tries):
            self.arm()
            self.spin_for(1.0)
            if self.status.armed and not self.spin_for(2.0, lambda: not self.status.armed):
                return True
        return False

    def send_drive(self, speed=1.0, hold=5.0):
        goal = ScriptedDrive.Goal(target_speed=speed, acceleration=0.5, deceleration=1.0,
                                  hold_time=hold)
        if not self.drive.wait_for_server(timeout_sec=20.0):
            return None
        future = self.drive.send_goal_async(goal)
        self.spin_for(10.0, lambda: future.done())
        return future.result() if future.done() else None

    def press(self, publisher, value, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            publisher.publish(Bool(data=value))
            self.spin_for(0.1)


def check_estop(probe, name, publisher):
    """Drive, press `publisher`'s e-stop at 1 m/s, check the stop, release, re-arm."""
    handle = probe.send_drive(hold=8.0)
    if handle is None or not handle.accepted:
        result(name, False, 'the scripted drive was refused')
        return
    probe.spin_for(6.0)
    v_before = probe.truth.twist.twist.linear.x
    probe.press(publisher, True, 3.0)
    v_after = probe.truth.twist.twist.linear.x
    reported = probe.status is not None and probe.status.estop_active
    probe.press(publisher, False, 1.0)
    handle.cancel_goal_async()
    probe.spin_for(2.0)
    ok = v_before > 0.5 and abs(v_after) < 0.05 and reported
    result(name, ok, f'{v_before:.2f} m/s before, {v_after:.2f} m/s 3 s later, '
                     f'spine reported it: {reported}')
    probe.arm_and_hold()


def main():
    env = dict(os.environ)
    print(f'Starting bench mode on ROS domain {env["ROS_DOMAIN_ID"]} (local only)...', flush=True)
    log = open('/tmp/aav-bench-check.log', 'w')
    launch = subprocess.Popen(['ros2', 'launch', 'aav_bringup', 'bench.launch.py', 'rviz:=false'],
                              cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                              start_new_session=True)
    rclpy.init()
    probe = Probe()
    try:
        up = probe.spin_for(90.0, lambda: probe.status is not None and probe.glob is not None
                            and probe.truth is not None)
        armed = up and probe.arm_and_hold()
        result('start-up', armed, 'the spine is armed and both EKFs are running' if armed
               else 'no spine status, truth or global odometry within 90 s' if not up
               else 'the spine would not stay armed')
        if not armed:
            return 1

        graph = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'check_graph.py'),
                                '--profile', 'bench'], cwd=ROOT, env=env,
                               capture_output=True, text=True)
        fails = [line for line in graph.stdout.splitlines() if line.startswith('FAIL')]
        result('graph vs contract', graph.returncode == 0 and not fails,
               f'{len(fails)} failures' + (': ' + '; '.join(fails[:3]) if fails else ''))

        x0, y0 = probe.xy(probe.truth)
        handle = probe.send_drive()
        if handle is None or not handle.accepted:
            result('scripted drive', False, 'refused')
        else:
            done = handle.get_result_async()
            probe.spin_for(40.0, lambda: done.done())
            probe.spin_for(3.0)
            x1, y1 = probe.xy(probe.truth)
            travelled = math.hypot(x1 - x0, y1 - y0)
            result('scripted drive', 5.0 < travelled < 8.0,
                   f'{travelled:.2f} m (plan: 6.5 m at 1 m/s, then a stop)')
            gx, gy = probe.xy(probe.glob)
            error = math.hypot(gx - x1, gy - y1)
            result('global EKF vs truth', error < 1.5,
                   f'{error:.2f} m apart (GPS noise is 0.5 m)')

        check_estop(probe, 'software e-stop', probe.estop)
        check_estop(probe, 'hardware e-stop', probe.hw_estop)
    finally:
        probe.destroy_node()
        rclpy.try_shutdown()
        os.killpg(launch.pid, signal.SIGINT)
        try:
            launch.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(launch.pid, signal.SIGKILL)

    print('\n| Check | Result | Detail |\n|---|---|---|')
    for name, ok, detail in RESULTS:
        print(f'| {name} | {"✅" if ok else "❌"} | {detail} |')
    print('\nThe bench log: /tmp/aav-bench-check.log')
    return 0 if all(ok for _, ok, _ in RESULTS) else 1


if __name__ == '__main__':
    sys.exit(main())
