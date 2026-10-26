"""
scripted_driver: drive a speed profile on request (phase 1a).

Action      scripted_drive            aav_interfaces/action/ScriptedDrive
Subscribes  localization/odom/local   nav_msgs/Odometry (speed and distance, from ekf_local)
            safety/estop              std_msgs/Bool: true ends the drive at once
            control/cmd_vel           geometry_msgs/TwistStamped: twist_mux's choice, to
                                      see someone else driving
Publishes   drivers/scripted/cmd_vel  geometry_msgs/TwistStamped, at rate_hz while a goal runs

Try it:
  ros2 action send_goal /scripted_drive aav_interfaces/action/ScriptedDrive \
    "{target_speed: 1.0, acceleration: 0.5, deceleration: 1.0, hold_time: 5.0}" --feedback

The joystick outranks this driver in twist_mux, so a person can always take over. When
someone does (twist_mux passes another command for TAKEOVER_TIME), or on an e-stop, the
goal ends at once; when a hold_distance goal loses its odometry, it slows down and ends.
"""

import collections
import math
import signal
import threading

from aav_actuator_tests.safety import taken_over
from aav_interfaces.action import ScriptedDrive
from aav_scripted.speed_profile import goal_problem, SpeedProfile, stop_reason, STOPPED
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.task import Future
from std_msgs.msg import Bool

TAKEOVER_TIME = 0.3     # s of twist_mux passing someone else's command (as aav_drive_to_point)


class ScriptedDriver(Node):

    def __init__(self):
        super().__init__('scripted_driver')
        self.max_speed = self.declare_parameter('max_speed', 2.0).value
        self.rate_hz = self.declare_parameter('rate_hz', 50.0).value
        self.odom_timeout = self.declare_parameter('odom_timeout', 0.5).value
        self.lock = threading.Lock()
        self.busy = False
        self.distance = 0.0
        self.speed = 0.0
        self.last_xy = None
        self.odom_time = None
        self.estop = False
        self.ours = collections.deque(maxlen=50)   # our last commands (v, w)
        self.other_since = None                    # s: twist_mux passing someone else's
        self.pub = self.create_publisher(TwistStamped, 'drivers/scripted/cmd_vel', 10)
        self.create_subscription(Odometry, 'localization/odom/local', self.on_odom, 10)
        self.create_subscription(Bool, 'safety/estop',
                                 lambda m: setattr(self, 'estop', bool(m.data)), 10)
        self.create_subscription(TwistStamped, 'control/cmd_vel', self.on_mux, 10)
        self.server = ActionServer(
            self, ScriptedDrive, 'scripted_drive', execute_callback=self.execute,
            goal_callback=self.on_goal, cancel_callback=lambda _: CancelResponse.ACCEPT)

    def on_odom(self, msg):
        p = msg.pose.pose.position
        with self.lock:
            if self.last_xy is not None:
                self.distance += math.hypot(p.x - self.last_xy[0], p.y - self.last_xy[1])
            self.last_xy = (p.x, p.y)
            self.speed = msg.twist.twist.linear.x
            self.odom_time = self.get_clock().now()

    def odom_fresh(self):
        return self.odom_time is not None and (
            self.get_clock().now() - self.odom_time).nanoseconds * 1e-9 < self.odom_timeout

    def seconds(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_mux(self, msg):
        theirs = (msg.twist.linear.x, msg.twist.angular.z)
        if not self.busy or not self.ours or not taken_over(self.ours, theirs):
            self.other_since = None
        elif self.other_since is None:
            self.other_since = self.seconds()

    def is_taken_over(self):
        return (self.other_since is not None
                and self.seconds() - self.other_since > TAKEOVER_TIME)

    def on_goal(self, goal):
        reason = None
        if self.busy:
            reason = 'another scripted drive is running'
        elif self.estop:
            reason = 'the e-stop is on'
        else:
            reason = goal_problem(goal.target_speed, goal.acceleration, goal.deceleration,
                                  goal.hold_time, goal.hold_distance, self.max_speed)
        if reason is None and goal.hold_distance > 0 and not self.odom_fresh():
            reason = 'hold_distance needs /localization/odom/local, which is not arriving'
        if reason:
            self.get_logger().warning(f'rejected goal: {reason}')
            return GoalResponse.REJECT
        # Claimed here, not in execute: a second goal can arrive before execute runs.
        self.busy = True
        self.ours.clear()
        self.other_since = None
        return GoalResponse.ACCEPT

    def publish(self, v, curvature):
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'
        msg.twist.linear.x = v
        msg.twist.angular.z = v * curvature
        self.pub.publish(msg)
        self.ours.append((msg.twist.linear.x, msg.twist.angular.z))

    async def execute(self, handle):
        # A coroutine on one thread, driven by a timer. It used to be a blocking loop on a
        # MultiThreadedExecutor, and that executor spins a whole core whenever a
        # subscription gets messages (rclpy 7.1.12; measured 105% CPU while idle).
        try:
            return await self.drive(handle)
        finally:
            self.busy = False

    async def drive(self, handle):
        g = handle.request
        profile = SpeedProfile(g.target_speed, g.acceleration, g.deceleration,
                               g.hold_time, g.hold_distance)
        start = self.distance
        t0 = self.get_clock().now()
        feedback = ScriptedDrive.Feedback()
        finished = Future()
        loop = {'tick': 0, 'last': t0.nanoseconds * 1e-9, 'zeros': 0, 'why': None}

        def tick():
            if profile.phase == STOPPED:
                # A few zero commands at the end, so the mux sees the stop.
                self.publish(0.0, 0.0)
                loop['zeros'] += 1
                if loop['zeros'] >= 5 and not finished.done():
                    finished.set_result(None)
                return
            if handle.is_cancel_requested:
                profile.cancel()
            why = stop_reason(self.estop, self.is_taken_over(),
                              needs_odom=g.hold_distance > 0, odom_fresh=self.odom_fresh())
            if why and loop['why'] is None:
                loop['why'] = why
                self.get_logger().warning(f'scripted drive ended: {why}')
            if loop['why'] == 'odometry stopped arriving':
                profile.cancel()        # no distance to hold, but the speed still ramps down
            elif loop['why']:
                profile.stop()
            with self.lock:
                travelled = self.distance - start
                measured = self.speed
            # The time that really passed, not 1 / rate_hz: on a busy computer the timer
            # fires late, and a fixed step stretched the whole profile (bench, 10 Oct:
            # 22 m instead of 6.5 m). The cap only stops a long stall from jumping the
            # profile; ego and the spine limit how fast the speed can change anyway.
            # The node's clock, so Gazebo's time in a simulator: a simulator slower than
            # real time (no GPU, 4 cores: GitHub's runners, 23 Oct) shrank a wall-clock
            # profile instead (2.5 m instead of 6.5 m). On the car it is the wall clock.
            now = self.get_clock().now().nanoseconds * 1e-9
            dt, loop['last'] = min(max(now - loop['last'], 0.0), 0.5), now
            v = profile.step(dt, travelled)
            self.publish(v, g.curvature)
            if loop['tick'] % 5 == 0:
                feedback.phase = profile.phase
                feedback.commanded_speed = v
                feedback.measured_speed = measured
                feedback.distance_travelled = travelled
                handle.publish_feedback(feedback)
            loop['tick'] += 1

        timer = self.create_timer(1.0 / self.rate_hz, tick)
        try:
            await finished
        finally:
            self.destroy_timer(timer)

        result = ScriptedDrive.Result()
        result.distance_travelled = self.distance - start
        result.duration = (self.get_clock().now() - t0).nanoseconds * 1e-9
        if loop['why']:
            handle.abort()
            result.message = f"stopped: {loop['why']}"
        elif handle.is_cancel_requested:
            handle.canceled()
            result.message = 'cancelled; stopped'
        else:
            handle.succeed()
            result.success = True
            result.message = 'done'
        return result


def main(args=None):
    rclpy.init(args=args)
    node = ScriptedDriver()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        # Ctrl-C reaches a launched node twice (terminal and launch), and Jazzy can then
        # raise RCLError ("context is not valid"). Only a live context means a real error.
        if rclpy.ok():
            raise
    finally:
        # Ctrl-C reaches a launched node twice (the terminal, then launch): ignore the
        # second, so it can't interrupt the clean-up with a traceback.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
