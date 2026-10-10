"""
scripted_driver: drive a speed profile on request (phase 1a).

Action      scripted_drive        aav_interfaces/action/ScriptedDrive
Subscribes  odometry/local        nav_msgs/Odometry (speed and distance, from ekf_local)
Publishes   cmd_vel/scripted      geometry_msgs/TwistStamped, at rate_hz while a goal runs

Try it:
  ros2 action send_goal /scripted_drive aav_interfaces/action/ScriptedDrive \
    "{target_speed: 1.0, acceleration: 0.5, deceleration: 1.0, hold_time: 5.0}" --feedback

The joystick outranks this driver in twist_mux, so a person can always take over.
"""

import math
import threading
import time

from aav_interfaces.action import ScriptedDrive
from aav_scripted.speed_profile import SpeedProfile, STOPPED
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node


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
        group = ReentrantCallbackGroup()
        self.pub = self.create_publisher(TwistStamped, 'cmd_vel/scripted', 10)
        self.create_subscription(Odometry, 'odometry/local', self.on_odom, 10,
                                 callback_group=group)
        self.server = ActionServer(
            self, ScriptedDrive, 'scripted_drive', execute_callback=self.execute,
            goal_callback=self.on_goal, cancel_callback=lambda _: CancelResponse.ACCEPT,
            callback_group=group)

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

    def on_goal(self, goal):
        reason = None
        if self.busy:
            reason = 'another scripted drive is running'
        elif abs(goal.target_speed) > self.max_speed:
            reason = f'|target_speed| above max_speed {self.max_speed}'
        elif goal.acceleration <= 0 or goal.deceleration <= 0:
            reason = 'acceleration and deceleration must be positive'
        elif goal.hold_distance > 0 and not self.odom_fresh():
            reason = 'hold_distance needs /odometry/local, which is not arriving'
        if reason:
            self.get_logger().warning(f'rejected goal: {reason}')
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def publish(self, v, curvature):
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'
        msg.twist.linear.x = v
        msg.twist.angular.z = v * curvature
        self.pub.publish(msg)

    def execute(self, handle):
        self.busy = True
        g = handle.request
        profile = SpeedProfile(g.target_speed, g.acceleration, g.deceleration,
                               g.hold_time, g.hold_distance)
        start = self.distance
        t0 = self.get_clock().now()
        rate = self.create_rate(self.rate_hz)
        feedback = ScriptedDrive.Feedback()
        tick = 0
        last = time.monotonic()
        try:
            while rclpy.ok():
                if handle.is_cancel_requested:
                    profile.cancel()
                with self.lock:
                    travelled = self.distance - start
                    measured = self.speed
                # The time that really passed, not 1 / rate_hz: on a busy computer the loop
                # runs late, and a fixed step stretched the whole profile (bench, 10 Oct:
                # 22 m instead of 6.5 m). The cap only stops a long stall from jumping the
                # profile; ego and the spine limit how fast the speed can change anyway.
                now = time.monotonic()
                dt, last = min(now - last, 0.5), now
                v = profile.step(dt, travelled)
                self.publish(v, g.curvature)
                if tick % 5 == 0:
                    feedback.phase = profile.phase
                    feedback.commanded_speed = v
                    feedback.measured_speed = measured
                    feedback.distance_travelled = travelled
                    handle.publish_feedback(feedback)
                tick += 1
                if profile.phase == STOPPED:
                    break
                rate.sleep()
            for _ in range(5):
                self.publish(0.0, 0.0)
                rate.sleep()
        finally:
            self.destroy_rate(rate)
            self.busy = False

        result = ScriptedDrive.Result()
        result.distance_travelled = self.distance - start
        result.duration = (self.get_clock().now() - t0).nanoseconds * 1e-9
        if handle.is_cancel_requested:
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
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        # Ctrl-C reaches a launched node twice (terminal and launch), and Jazzy can then
        # raise RCLError ("context is not valid"). Only a live context means a real error.
        if rclpy.ok():
            raise
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
