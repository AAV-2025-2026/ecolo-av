#!/usr/bin/env python3
"""
Controller comparison: Regulated Pure Pursuit and MPPI over the same routes in Gazebo.

Both drive the test lot, headless, and are measured against where the car really was.

    pixi run controller-compare                   (both controllers, both tours: ~15 min)
    pixi run controller-compare --tours obstacle   (only the box in the lane)
    pixi run controller-compare --controllers mppi
    pixi run controller-compare --speed 3          (Nav2 and ego up to 3 m/s: sim_speed:=3)
    pixi run controller-compare --tours lot --legs 1   (only the first leg: a quick check)
    pixi run controller-compare --reversing        (Nav2 may reverse: the car's reversing:=true)
    pixi run controller-compare --plans            (keep every plan, not just each leg's first)

For each tour and controller it:
1. starts sim.launch.py world:=test_lot gui:=false rviz:=false controller:=<rpp|mppi>
   reversing:=false (forward only, unless --reversing), on a ROS domain and Gazebo partition of
   its own, on this computer only;
2. waits for Gazebo's truth, the global EKF and Nav2;
3. sends each leg's goal in turn, each from where the last one ended, and records where the
   car really was (/vehicle/gazebo/truth), the planner's paths (/plan), the controller's
   speed (/cmd_vel_nav), ego's steering, the sensor watchdog and collision_monitor;
4. stops the simulator by its process group, and clears Fast DDS's shared memory
   (docs/path-followers.md).

Tours (map frame: the car starts at 0, 0 facing east; the walls, building and parked cars
are aav_gazebo worlds/test_lot.sdf):
  lot       a left turn; round the building to the lane north of it; a turn back in that
            14 m wide lane; home
  obstacle  30 m east with the bench's 1 m box in the lane at 15.5 m (obstacle:=true).
            Nav2's global costmap holds only the map, so the planner's path goes through the
            box: only the controller and collision_monitor can deal with it

What each number means: drive_metrics.py (COLUMNS). The results go to
log/controller-compare/<time>/: results.md, a picture of each tour (<tour>.svg: where each
controller took the car), results.json (the numbers; each leg's track, the EKF's belief,
the controller's speed command and its first plan) and each run's launch log.
"""

import argparse
import datetime
import json
import math
import os
import random
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
# On this computer only: the comparison can't disturb a car, another laptop or someone
# else's simulator. Each run also gets its own ROS domain and Gazebo partition (private()),
# so one still shutting down can't meet the next (21 Oct: the second run never came up).
os.environ['ROS_AUTOMATIC_DISCOVERY_RANGE'] = 'LOCALHOST'
os.environ['GZ_IP'] = '127.0.0.1'

from aav_description import vehicle  # noqa: E402
from aav_gazebo import worlds  # noqa: E402
from ackermann_msgs.msg import AckermannDriveStamped  # noqa: E402
from action_msgs.msg import GoalStatus  # noqa: E402
import drive_metrics  # noqa: E402
from geometry_msgs.msg import TwistStamped  # noqa: E402
from nav2_msgs.action import NavigateToPose  # noqa: E402
from nav2_msgs.msg import CollisionMonitorState  # noqa: E402
from nav_msgs.msg import Odometry, Path  # noqa: E402
import rclpy  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from std_msgs.msg import Bool, String  # noqa: E402
from std_srvs.srv import Trigger  # noqa: E402
import yaml  # noqa: E402

# (name, x m, y m, heading deg): each leg's goal, map frame.
TOURS = {
    'lot': {'obstacle': False, 'legs': [
        ('a left turn', 15.0, 15.0, 90.0),
        ('round the building', 35.0, 42.0, 0.0),
        ('turn back', 20.0, 42.0, 180.0),
        ('home', 0.0, 0.0, 0.0),
    ]},
    'obstacle': {'obstacle': True, 'legs': [
        ('past the box', 30.0, 0.0, 0.0),
    ]},
}
BOX = 1.0               # m: the bench's obstacle, a cube (aav_gazebo models/obstacle)
UP_TIME = 150.0         # s for Gazebo, the EKF, then Nav2, to come up
SETTLE = 5.0            # s after that, before the first goal
READY_TIME = 30.0       # s for the sensor watchdog to let Nav2 drive, before each leg
LEG_TIME = 60.0         # s for each leg, plus 4 s for every metre at the top speed
TRACK_EVERY = 0.5       # s between the saved track's points
# The test lot's drawing (tools/make_map.py made the map from it): the picture's background.
MAP_SPEC = os.path.join(ROOT, 'ros', 'drivers', 'aav_navigation', 'maps',
                        'example_lot.spec.yaml')
COLOURS = {'rpp': '#1f6fb4', 'mppi': '#e8590c'}


def seconds(stamp):
    return stamp.sec + stamp.nanosec * 1e-9


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def cpu_seconds(pid):
    """Return a process's CPU time so far (s), from ps: [D-]H:M:S or M:S.cc; None if gone."""
    if pid is None:
        return None
    out = subprocess.run(['ps', '-o', 'time=', '-p', str(pid)], capture_output=True,
                         text=True).stdout.strip()
    if not out:
        return None
    days, _, clock = out.rpartition('-')
    total = 0.0
    for part in clock.split(':'):
        total = total * 60.0 + float(part)
    return total + (float(days) * 86400.0 if days else 0.0)


def controller_pid(pgid):
    """Return the pid of the run's controller_server, found in its process group."""
    out = subprocess.run(['ps', '-ax', '-o', 'pid=,pgid=,command='], capture_output=True,
                         text=True).stdout
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[1] == str(pgid) and 'controller_server' in parts[2]:
            return int(parts[0])
    return None


class Recorder(Node):
    """Where the car really is, what Nav2 planned and asked for, and the safety layers."""

    def __init__(self):
        # On Gazebo's clock, like every node in the sim.
        super().__init__('controller_compare', parameter_overrides=[
            Parameter('use_sim_time', value=True)])
        self.recording = False
        self.truth, self.plans, self.steering, self.asked = [], [], [], []
        self.belief = []
        self.last_truth = self.glob = None
        self.lock, self.locked, self.states = None, False, set()
        self.monitor, self.monitor_stops = None, 0
        self.create_subscription(Odometry, '/vehicle/gazebo/truth', self.on_truth, 10)
        self.create_subscription(Odometry, '/localization/odom/global', self.on_global, 10)
        self.create_subscription(Path, '/plan', self.on_plan, 10)
        self.create_subscription(AckermannDriveStamped, '/ego/actuator_cmd', self.on_steering,
                                 10)
        self.create_subscription(TwistStamped, '/cmd_vel_nav', self.on_asked, 10)
        self.create_subscription(Bool, '/safety/sensor_watchdog/lock', self.on_lock, 10)
        self.create_subscription(String, '/safety/sensor_watchdog/state', self.on_state, 10)
        self.create_subscription(CollisionMonitorState, '/safety/collision_monitor/state',
                                 self.on_monitor, 10)
        self.nav = ActionClient(self, NavigateToPose, '/navigate_to_pose')
        self.clear = self.create_client(Trigger, '/safety/sensor_watchdog/clear')

    def start(self):
        self.truth, self.plans, self.steering, self.asked = [], [], [], []
        self.belief = []
        self.locked, self.states, self.monitor_stops = False, set(), 0
        self.recording = True

    def on_truth(self, msg):
        self.last_truth = msg
        if self.recording:
            p = msg.pose.pose.position
            self.truth.append((seconds(msg.header.stamp), p.x, p.y,
                               yaw_of(msg.pose.pose.orientation)))

    def on_global(self, msg):
        self.glob = msg
        if self.recording:
            p = msg.pose.pose.position
            self.belief.append((seconds(msg.header.stamp), p.x, p.y,
                                yaw_of(msg.pose.pose.orientation)))

    def on_plan(self, msg):
        if self.recording:
            self.plans.append((self.now(), [(s.pose.position.x, s.pose.position.y)
                                            for s in msg.poses]))

    def on_steering(self, msg):
        if self.recording:
            self.steering.append((seconds(msg.header.stamp), msg.drive.steering_angle))

    def on_asked(self, msg):
        if self.recording:
            self.asked.append((self.now(), msg.twist.linear.x))

    def on_lock(self, msg):
        self.lock = msg.data
        if self.recording and msg.data:
            self.locked = True

    def on_state(self, msg):
        if self.recording and msg.data not in ('', 'OK'):
            self.states.add(msg.data[:90])

    def on_monitor(self, msg):
        if self.recording and msg.action_type == CollisionMonitorState.STOP and (
                self.monitor != CollisionMonitorState.STOP):
            self.monitor_stops += 1
        self.monitor = msg.action_type

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def spin_for(self, wall_seconds, until=None):
        end = time.monotonic() + wall_seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)
            if until is not None and until():
                return True
        return until is None

    def wait(self, future, wall_seconds):
        self.spin_for(wall_seconds, future.done)
        return future.result() if future.done() else None

    def send(self, x, y, yaw):
        """Send Nav2 a goal in the map frame; return its handle, or None if refused."""
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.pose.position.x, goal.pose.pose.position.y = x, y
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)
        handle = self.wait(self.nav.send_goal_async(goal), 10.0)
        return handle if handle is not None and handle.accepted else None


def ready(rec):
    """Wait until the sensor watchdog lets Nav2 drive; clear a latch once. Return notes."""
    if rec.spin_for(READY_TIME, lambda: rec.lock is False):
        return []
    # Still locked: a latch (a GPS jump, the wheels against the IMU) waits for a person.
    rec.wait(rec.clear.call_async(Trigger.Request()), 5.0)
    if rec.spin_for(READY_TIME, lambda: rec.lock is False):
        return ['the sensor watchdog was latched before the goal: cleared it']
    return ['the sensor watchdog still held Nav2 when the goal went']


def drive_leg(rec, pgid, goal, speed, body, obstacle):
    """Send one goal and record it; return (drive_metrics leg, notes)."""
    notes = ready(rec)
    x, y, yaw = goal
    here = rec.last_truth.pose.pose.position
    timeout = LEG_TIME + 4.0 * math.hypot(x - here.x, y - here.y) / speed
    pid = controller_pid(pgid)
    cpu0, wall0 = cpu_seconds(pid), time.monotonic()
    rec.start()
    start = rec.now()
    reached = False
    handle = rec.send(x, y, yaw)
    if handle is None:
        notes.append('Nav2 refused the goal')
    else:
        result = handle.get_result_async()
        # Gazebo's time for the limit, and twice that in wall time in case it stalls.
        end_wall = time.monotonic() + 2.0 * timeout + 30.0
        while not result.done() and rec.now() < start + timeout and (
                time.monotonic() < end_wall):
            rclpy.spin_once(rec, timeout_sec=0.05)
        if result.done():
            done = result.result()
            reached = done.status == GoalStatus.STATUS_SUCCEEDED
            if not reached:
                why = getattr(done.result, 'error_msg', '') or f'status {done.status}'
                notes.append(f'Nav2 gave up: {why}')
        else:
            rec.wait(handle.cancel_goal_async(), 5.0)
            notes.append(f'not there in {timeout:.0f} s: cancelled')
    end = rec.now()
    rec.recording = False
    cpu1, wall1 = cpu_seconds(pid), time.monotonic()
    if rec.locked:
        notes.append('the sensor watchdog stopped Nav2' +
                     (': ' + '; '.join(sorted(rec.states)) if rec.states else ''))
    if rec.monitor_stops:
        notes.append(f'collision_monitor stopped the car {rec.monitor_stops}x')
    leg = {'truth': rec.truth, 'belief': rec.belief, 'plans': rec.plans,
           'steering': rec.steering,
           'asked': rec.asked, 'start': start, 'end': end, 'goal': goal, 'reached': reached,
           'cpu': (100.0 * (cpu1 - cpu0) / (wall1 - wall0)
                   if None not in (cpu0, cpu1) and wall1 > wall0 else None),
           'obstacle': obstacle, 'body': body}
    return leg, notes


def private(used):
    """
    Pick an unused ROS domain and Gazebo partition, and set them, before rclpy.init.

    The domain: AAV_SIM_DOMAIN's for the first run, else one from 150-230. The partition:
    AAV_SIM_PARTITION (default controller_compare), then the domain.
    """
    first = os.environ.get('AAV_SIM_DOMAIN')
    if first and first not in used:
        domain = first
    else:
        domain = str(random.choice([d for d in range(150, 231) if str(d) not in used]))
    used.add(domain)
    os.environ['ROS_DOMAIN_ID'] = domain
    prefix = os.environ.get('AAV_SIM_PARTITION', 'controller_compare')
    os.environ['GZ_PARTITION'] = f'{prefix}_{domain}'
    return domain


def alive(pgid):
    """Return True while a process group has a process that isn't a zombie (ps, any OS)."""
    out = subprocess.run(['ps', '-ax', '-o', 'pgid=,stat='], capture_output=True,
                         text=True).stdout
    return any(f[0] == str(pgid) and not f[1].startswith('Z')
               for f in (line.split() for line in out.splitlines()) if len(f) == 2)


def stop(launch, grace=30.0):
    """Stop a run's whole process group: Ctrl-C, then kill what's left; wait until it's gone."""
    for sig, wait in ((signal.SIGINT, grace), (signal.SIGKILL, 10.0)):
        try:
            os.killpg(launch.pid, sig)
        except (ProcessLookupError, PermissionError):   # gone, or only zombies (macOS)
            pass
        end = time.monotonic() + wait
        while time.monotonic() < end:
            launch.poll()               # reap the launcher, or it stays a zombie
            if not alive(launch.pid):
                return True
            time.sleep(0.5)
    return False


def tour_legs(tour, args):
    """Return the tour's legs to drive: all, or only the first --legs."""
    return TOURS[tour]['legs'][:args.legs]


def session(tour, controller, args, out_dir, body, used):
    """Start the simulator for one tour and controller, drive its legs, stop it."""
    plan = TOURS[tour]
    log_path = os.path.join(out_dir, f'sim-{tour}-{controller}.log')
    command = ['ros2', 'launch', 'aav_bringup', 'sim.launch.py', 'world:=test_lot',
               'gui:=false', 'rviz:=false', f'controller:={controller}',
               # Forward only, as on the car (the sim's default lets Nav2 reverse; MPPI
               # then dithered between forward and back at the start, 22 Oct), unless
               # --reversing: Nav2 may then back out of a dead end.
               f'reversing:={str(args.reversing).lower()}']
    if plan['obstacle']:
        command.append('obstacle:=true')
    if args.speed:
        command.append(f'sim_speed:={args.speed:g}')
    domain = private(used)
    print(f'\n== {tour}, {controller}: starting the test lot on ROS domain {domain} '
          f'(this computer only)...', flush=True)
    rows = []
    obstacle = (*worlds.OBSTACLE, BOX) if plan['obstacle'] else None
    with open(log_path, 'w') as log:
        launch = subprocess.Popen(command, cwd=ROOT, env=dict(os.environ), stdout=log,
                                  stderr=subprocess.STDOUT, start_new_session=True)
        rclpy.init()
        rec = Recorder()
        try:
            up = rec.spin_for(UP_TIME, lambda: rec.last_truth is not None and rec.glob)
            if not (up and rec.spin_for(UP_TIME, rec.nav.server_is_ready)):
                print(f'   it never came up: see {log_path}', flush=True)
                return [(tour, name, controller, None, ['never came up'], {})
                        for name, *_ in tour_legs(tour, args)]
            rec.spin_for(SETTLE)
            for name, x, y, heading in tour_legs(tour, args):
                leg, notes = drive_leg(rec, launch.pid, (x, y, math.radians(heading)),
                                       args.speed or 1.0, body, obstacle)
                row = drive_metrics.summary(leg)
                # t, x, y, yaw: where the car was, and where the global EKF put it.
                drawn = {'track': [[round(v, 3) for v in s]
                                   for s in drive_metrics.thin(leg['truth'], TRACK_EVERY)],
                         'belief': [[round(v, 3) for v in s]
                                    for s in drive_metrics.thin(leg['belief'], TRACK_EVERY)],
                         # t, speed: what the controller asked for, before the smoother.
                         'asked': [[round(v, 3) for v in s]
                                   for s in drive_metrics.thin(leg['asked'], TRACK_EVERY)],
                         'plan': [[round(x, 2), round(y, 2)]
                                  for x, y in (leg['plans'][0][1][::4] if leg['plans'] else [])]}
                if args.plans:
                    # Every plan of the leg, each with its time: where the planner sent the
                    # car as it went (TODO 17: a goal circled after a replan).
                    drawn['plans'] = [[round(t, 2), [[round(x, 2), round(y, 2)]
                                                     for x, y in pts[::4] + pts[-1:]]]
                                      for t, pts in leg['plans']]
                rows.append((tour, name, controller, row, notes, drawn))
                print(f'   {name}: ' + ('reached' if row['reached'] else 'NOT reached') +
                      f' in {row["time_s"]:.0f} s, {row["driven_m"]:.1f} m, off the path '
                      f'{row["off_path_mean_m"]:.2f} m on average' +
                      ''.join(f'; {n}' for n in notes), flush=True)
        finally:
            rec.destroy_node()
            rclpy.try_shutdown()
            if not stop(launch):
                print(f'   some of process group {launch.pid} would not stop', flush=True)
            launch.wait()
            # Programs that die leave Fast DDS's shared-memory files behind; too many of
            # those stop later runs talking (21 Oct).
            subprocess.run(['fastdds', 'shm', 'clean'], capture_output=True)
    return rows


def report(results, args, started):
    """Return results.md: for each leg, a table with one row per controller."""
    lines = [f'# Controller comparison, {started:%Y-%m-%d %H:%M}', '',
             f"Gazebo's test lot, headless, on this computer; Nav2 and ego at up to "
             f'{args.speed or 1.0:g} m/s, ' +
             ('reversing allowed' if args.reversing else 'forward only') +
             '. One run each. What each number means: '
             'tools/drive_metrics.py.', '']
    for tour in args.tours:
        for name, x, y, heading in tour_legs(tour, args):
            legs = [(c, row, notes) for t, n, c, row, notes, _ in results
                    if t == tour and n == name]
            lines += [f'## {tour}: {name} (to {x:g}, {y:g}, facing {heading:g} deg)', '']
            rows = [(c, row) for c, row, _ in legs if row is not None]
            if rows:
                lines += [drive_metrics.table(rows), '']
            lines += [f'- {c}: {"; ".join(notes)}' for c, _, notes in legs if notes]
            lines.append('')
    return '\n'.join(lines)


def picture(results, tour, args):
    """Return an SVG of one tour on the test lot: each controller's track, the first plans."""
    with open(MAP_SPEC) as f:
        spec = yaml.safe_load(f)
    (ox, oy), (w, h), wall = spec['origin'], spec['size'], spec.get('border', 0.0)
    grey, white = '#9e9e9e', 'white'
    blocks = [(ox, oy, ox + w, oy + wall, grey), (ox, oy + h - wall, ox + w, oy + h, grey),
              (ox, oy, ox + wall, oy + h, grey), (ox + w - wall, oy, ox + w, oy + h, grey)]
    blocks += [(*b, grey) for b in spec.get('blocked', [])]
    blocks += [(*b, white) for b in spec.get('free', [])]
    if TOURS[tour]['obstacle']:
        bx, by = worlds.OBSTACLE
        blocks.append((bx - BOX / 2, by - BOX / 2, bx + BOX / 2, by + BOX / 2, '#c92a2a'))
    runs = [r for r in results if r[0] == tour and r[5]]
    tracks = []
    for controller in dict.fromkeys(c for _, _, c, *_ in runs):
        legs = [r for r in runs if r[2] == controller]
        tracks.append((f'{controller}: where the car went', COLOURS.get(controller, 'black'),
                       [[(x, y) for r in legs for _, x, y, *_ in r[5]['track']]], False))
    plans = [r[5]['plan'] for r in runs if r[2] == runs[0][2]] if runs else []
    tracks.append(('the first plan of each leg', '#868e96', plans, True))
    marks = [(x, y, name) for name, x, y, _ in tour_legs(tour, args)]
    return drive_metrics.svg((ox, oy, ox + w, oy + h), tracks, blocks, marks)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0].strip())
    parser.add_argument('--controllers', nargs='+', choices=vehicle.CONTROLLERS,
                        default=list(vehicle.CONTROLLERS))
    parser.add_argument('--tours', nargs='+', choices=list(TOURS), default=list(TOURS))
    parser.add_argument('--speed', type=float, default=None,
                        help="m/s, up to 5: sim_speed:= (the car's own top speed: 1.0)")
    parser.add_argument('--reversing', action='store_true',
                        help="let Nav2 reverse (reversing:=true; the car's own default is "
                             'false until H5); forward only otherwise')
    parser.add_argument('--legs', type=int, default=None,
                        help="only each tour's first N legs (each starts where the last ended)")
    parser.add_argument('--plans', action='store_true',
                        help='save every plan of each leg in results.json, not just its first')
    parser.add_argument('--out', help='where the results go (default: log/controller-compare/)')
    args = parser.parse_args()
    started = datetime.datetime.now()
    out_dir = args.out or os.path.join(ROOT, 'log', 'controller-compare',
                                       f'{started:%Y%m%d-%H%M%S}')
    os.makedirs(out_dir, exist_ok=True)
    car = vehicle.load()['vehicle']['body']
    body = (car['length'], car['width'], car['rear_overhang'])
    results, used = [], set()
    for tour in args.tours:
        for controller in args.controllers:
            results += session(tour, controller, args, out_dir, body, used)
    text = report(results, args, started)
    with open(os.path.join(out_dir, 'results.md'), 'w') as f:
        f.write(text)
    for tour in args.tours:
        with open(os.path.join(out_dir, f'{tour}.svg'), 'w') as f:
            f.write(picture(results, tour, args))
    with open(os.path.join(out_dir, 'results.json'), 'w') as f:
        json.dump([{'tour': t, 'leg': n, 'controller': c, 'row': row, 'notes': notes, **drawn}
                   for t, n, c, row, notes, drawn in results], f, indent=1, default=str)
    print('\n' + text + f'\nSaved in {out_dir}', flush=True)
    return 0 if all(row and row['reached'] for _, _, _, row, _, _ in results) else 1


if __name__ == '__main__':
    sys.exit(main())
