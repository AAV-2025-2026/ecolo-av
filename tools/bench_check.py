#!/usr/bin/env python3
"""
Bench check: start bench mode, then test the whole car graph on this computer.

    pixi run bench-check          (about 2 minutes; nothing else on the network sees it)
    pixi run -e ml bench-check --perception    (adds YOLO and the stop sign: 3 minutes)
    pixi run bench-check --obstacle            (adds a box for the radar: 3 minutes)

1. Starts bench.launch.py on a private ROS domain, local to this computer.
2. Checks the running graph against docs/interfaces.yaml (check_graph.py --profile bench).
3. Waits for the spine to arm, drives a scripted profile, and compares where the model car
   really is (/bench/truth) with where the car's own software thinks it is (/odometry/global).
4. Presses the e-stop while driving: the car must stop, and the spine must say so.
5. Presses the hardware e-stop the same way.
6. With --perception: Nav2 drives 40 m east, past the bench's stop sign. The car must stop
   before the sign, wait, and go on to the goal. The camera's picture with YOLO's boxes, at
   the moment it stopped, is saved to /tmp/aav-bench-stop-sign.png.
7. With --obstacle: a 1 m box appears in the lane 15 m ahead, which only the pretend radar
   sees, and Nav2 drives 30 m. collision_monitor's stop zone must stop the car before the
   box; once the box is taken away, the car must go on to the goal.

Prints a table and exits 1 if anything failed. Run it after changing anything between the
drivers and the spine. The launch log goes to /tmp/aav-bench-check.log, or AAV_BENCH_LOG.
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

from aav_description import vehicle  # noqa: E402
from aav_interfaces.action import ScriptedDrive  # noqa: E402
from aav_interfaces.msg import VehicleStatus  # noqa: E402
from nav2_msgs.action import NavigateToPose  # noqa: E402
from nav2_msgs.msg import CollisionMonitorState  # noqa: E402
from nav_msgs.msg import Odometry  # noqa: E402
from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue  # noqa: E402
from rcl_interfaces.srv import SetParameters  # noqa: E402
import rclpy  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.node import Node  # noqa: E402
from sensor_msgs.msg import Image  # noqa: E402
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
        self.nav = ActionClient(self, NavigateToPose, '/navigate_to_pose')
        self.stop = False
        self.picture = None
        self.create_subscription(Bool, '/perception/stop', self.on_stop, 10)
        self.create_subscription(Image, '/perception/detections/image',
                                 lambda m: setattr(self, 'picture', m), 2)
        self.stop_picture = None
        self.monitor = []    # (time, action, polygon) from collision_monitor, as it changes
        self.create_subscription(CollisionMonitorState, '/collision_monitor_state',
                                 lambda m: self.monitor.append(
                                     (time.monotonic(), m.action_type, m.polygon_name)), 10)
        self.radar_params = self.create_client(SetParameters, '/mock_radar/set_parameters')

    def on_stop(self, msg):
        if msg.data and not self.stop and self.picture is not None:
            self.stop_picture = self.picture   # what the camera saw as the lock went on
            self.stop_time = self.get_clock().now().nanoseconds * 1e-9
        self.stop = msg.data

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

    def set_radar(self, obstacle, boxes=None):
        """Put the bench's boxes where the pretend radar sees them, or take them away."""
        params = [Parameter(name='obstacle', value=ParameterValue(
            type=ParameterType.PARAMETER_BOOL, bool_value=obstacle))]
        if boxes is not None:
            params.append(Parameter(name='boxes', value=ParameterValue(
                type=ParameterType.PARAMETER_DOUBLE_ARRAY, double_array_value=boxes)))
        if not self.radar_params.wait_for_service(timeout_sec=10.0):
            return False
        future = self.radar_params.call_async(SetParameters.Request(parameters=params))
        self.spin_for(10.0, lambda: future.done())
        return future.done() and all(r.successful for r in future.result().results)

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


def check_stop_sign(probe):
    """Nav2 drives 40 m east, past the stop sign at x = 25 m: it must stop before it."""
    goal = NavigateToPose.Goal()
    goal.pose.header.frame_id = 'map'
    goal.pose.pose.position.x = 40.0
    goal.pose.pose.orientation.w = 1.0
    if not probe.nav.wait_for_server(timeout_sec=30.0):
        result('stop sign', False, 'no Nav2')
        return
    sent = probe.nav.send_goal_async(goal)
    probe.spin_for(10.0, lambda: sent.done())
    if not sent.done() or not sent.result().accepted:
        result('stop sign', False, 'Nav2 refused the goal')
        return
    done = sent.result().get_result_async()
    stopped_at, stood_still = None, False
    end = time.monotonic() + 150.0
    while time.monotonic() < end and not done.done():
        probe.spin_for(0.1)
        if probe.stop and stopped_at is None:
            stopped_at = probe.truth.pose.pose.position.x
        if probe.stop and abs(probe.truth.twist.twist.linear.x) < 0.05:
            stood_still = True
    x = probe.truth.pose.pose.position.x
    succeeded = done.done() and done.result().status == 4
    ok = stopped_at is not None and stopped_at < 24.0 and stood_still and succeeded and x > 35
    where = f'locked at x = {stopped_at:.1f} m' if stopped_at is not None else 'never locked'
    result('stop sign', ok, f'{where} (the sign is at 25 m), stood still: {stood_still}, '
                            f'Nav2 goal {"reached" if succeeded else "not reached"} at {x:.1f} m')
    if probe.stop_picture is not None:
        try:
            from cv_bridge import CvBridge
            import cv2
            cv2.imwrite('/tmp/aav-bench-stop-sign.png',
                        CvBridge().imgmsg_to_cv2(probe.stop_picture, 'bgr8'))
            stamp = probe.stop_picture.header.stamp
            age = probe.stop_time - (stamp.sec + stamp.nanosec * 1e-9)
            print(f'The camera at the stop: /tmp/aav-bench-stop-sign.png (taken {age:.1f} s '
                  'before the lock went on)', flush=True)
        except Exception as e:  # noqa: B902 - the picture is a bonus
            print(f'could not save the picture: {e}', flush=True)


def yaw_of(msg):
    q = msg.pose.pose.orientation
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def check_obstacle(probe, ahead=15.0, goal=30.0):
    """Put a box `ahead` m in the lane: the stop zone must stop the car before it."""
    name = 'obstacle'
    if not probe.arm_and_hold():
        result(name, False, 'the spine would not stay armed')
        return
    body = vehicle.load()['vehicle']['body']
    front = body['length'] - body['rear_overhang']   # base_link to the front bumper
    t = probe.truth
    x0, y0, h = t.pose.pose.position.x, t.pose.pose.position.y, yaw_of(t)
    c, s = math.cos(h), math.sin(h)

    def along():
        p = probe.truth.pose.pose.position
        return (p.x - x0) * c + (p.y - y0) * s

    # A 1 m square, its near face `ahead` m in front of the bumper.
    bx, by = x0 + (front + ahead + 0.5) * c, y0 + (front + ahead + 0.5) * s
    if not probe.set_radar(True, [bx - 0.5, by - 0.5, bx + 0.5, by + 0.5]):
        result(name, False, 'could not place the box (mock_radar parameters)')
        return
    target = NavigateToPose.Goal()
    target.pose.header.frame_id = 'map'
    target.pose.pose.position.x, target.pose.pose.position.y = x0 + goal * c, y0 + goal * s
    orientation = target.pose.pose.orientation
    orientation.z, orientation.w = math.sin(h / 2.0), math.cos(h / 2.0)
    sent = probe.nav.send_goal_async(target)
    probe.spin_for(10.0, lambda: sent.done())
    if not sent.done() or not sent.result().accepted:
        result(name, False, 'Nav2 refused the goal')
        probe.set_radar(False)
        return
    done = sent.result().get_result_async()
    t0, seen = time.monotonic(), len(probe.monitor)
    top, still, gap, latched = 0.0, None, None, False
    while time.monotonic() - t0 < 150.0 and not done.done():
        probe.spin_for(0.1)
        v = probe.truth.twist.twist.linear.x
        top = max(top, v)
        latched = latched or (probe.status is not None and not probe.status.armed)
        if gap is None and top > 0.5 and abs(v) < 0.02:
            still = still or time.monotonic()
            if time.monotonic() - still > 3.0:      # stood still for 3 s: take the box away
                gap = ahead - along()
                probe.set_radar(False)
        else:
            still = None
    states = probe.monitor[seen:]
    stop_zone = any(a == CollisionMonitorState.STOP and p == 'StopZone' for _, a, p in states)
    reached = done.done() and done.result().status == 4
    passed = along() > front + ahead + 1.0
    ok = gap is not None and 0.0 < gap < 2.0 and stop_zone and reached and passed
    where = f'stood still {gap:.2f} m before the box' if gap is not None else 'never stopped'
    result(name, ok, f'{where} (top speed {top:.2f} m/s), stop zone fired: {stop_zone}; box '
                     f'taken away, Nav2 goal {"reached" if reached else "not reached"} '
                     f'{along():.1f} m on' + ('; the spine latched' if latched else ''))
    probe.set_radar(False)


def main():
    perception = '--perception' in sys.argv[1:]
    obstacle = '--obstacle' in sys.argv[1:]
    env = dict(os.environ)
    print(f'Starting bench mode on ROS domain {env["ROS_DOMAIN_ID"]} (local only)...', flush=True)
    log_path = env.get('AAV_BENCH_LOG', '/tmp/aav-bench-check.log')
    log = open(log_path, 'w')
    launch = subprocess.Popen(['ros2', 'launch', 'aav_bringup', 'bench.launch.py', 'rviz:=false',
                               f'perception:={str(perception).lower()}'],
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

        # Up to three tries, 10 s apart: a node's first start after a build can take 20 s
        # on a Mac (it loads PCL and VTK, and macOS checks the new binary).
        for attempt in range(3):
            graph = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'check_graph.py'),
                                    '--profile', 'bench'], cwd=ROOT, env=env,
                                   capture_output=True, text=True)
            fails = [line for line in graph.stdout.splitlines() if line.startswith('FAIL')]
            if graph.returncode == 0 and not fails:
                break
            probe.spin_for(10.0)
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
            # The plan is 6.5 m. The spine's speed loop trails a ramp by about a second, so
            # 5-6 m is normal; the range catches a stretched plan (22 m) or no motion at all.
            result('scripted drive', 4.5 < travelled < 8.0,
                   f'{travelled:.2f} m (plan: 6.5 m; the speed loop trails it by about 1 s)')
            gx, gy = probe.xy(probe.glob)
            error = math.hypot(gx - x1, gy - y1)
            result('global EKF vs truth', error < 1.5,
                   f'{error:.2f} m apart (GPS noise is 0.5 m)')

        check_estop(probe, 'software e-stop', probe.estop)
        check_estop(probe, 'hardware e-stop', probe.hw_estop)
        if perception:
            check_stop_sign(probe)
        if obstacle:
            check_obstacle(probe)
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
    print(f'\nThe bench log: {log_path}')
    return 0 if all(ok for _, ok, _ in RESULTS) else 1


if __name__ == '__main__':
    sys.exit(main())
