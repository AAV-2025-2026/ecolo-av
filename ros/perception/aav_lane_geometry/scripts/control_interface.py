#!/usr/bin/env python3
import time
import numpy as np
import signal
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped
from std_msgs.msg import String
from aav_lane_geometry.msg import LaneGeometry
# aav: the slow-down rule, in a module with no ROS (lane_speed.py, beside this script).
from lane_speed import AI_SLOT_TIMEOUT_S, stopping_speed


class VehicleState:
    LANE_KEEP = "LANE_KEEP"
    LANE_CHANGING = "LANE_CHANGING"
    LANE_COMMITTED = "LANE_COMMITTED"
    NO_LANE_STOPPING = "NO_LANE_STOPPING"
    RESUMING = "RESUMING"


class PID:
    def __init__(self, kp=0.8, ki=0.01, kd=0.3):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self._integral = 0.0
        self._prev_err = 0.0
        self._prev_time = time.time()

    def compute(self, error: float) -> float:
        now = time.time()
        dt = max(now - self._prev_time, 1e-4)
        self._integral += error * dt
        derivative = (error - self._prev_err) / dt
        out = self.kp * error + self.ki * self._integral + self.kd * derivative
        self._prev_err = error
        self._prev_time = now
        return out

    def reset(self):
        self._integral = 0.0
        self._prev_err = 0.0
        self._prev_time = time.time()


class ControlInterface(Node):
    def __init__(self):
        super().__init__('control_interface')

        self.declare_parameter('base_speed_mps', 2.0)
        self.declare_parameter('max_angular_z', 0.5)
        self.declare_parameter('min_speed_mps', 0.3)
        self.declare_parameter('min_curvature_m', 20.0)
        self.declare_parameter('lane_change_rate_threshold', 0.05)
        self.declare_parameter('lane_change_offset_threshold', 0.40)
        self.declare_parameter('lane_change_speed', 1.0)
        self.declare_parameter('lane_change_timeout_s', 8.0)
        # aav: no lane message for stop_wait_s: slow down. Shorter than twist_mux's 0.5 s
        # for the AI slot, so the slow-down reaches the car before ego stops it.
        self.declare_parameter('stop_wait_s', 0.3)
        self.declare_parameter('decel_rate', 0.5)
        self.declare_parameter('accel_rate', 0.3)
        self.declare_parameter('pid_kp', 0.8)
        self.declare_parameter('pid_ki', 0.01)
        self.declare_parameter('pid_kd', 0.3)
        self.declare_parameter('invert_offset_sign', True)

        self.base_speed = float(self.get_parameter('base_speed_mps').value)
        self.max_ang = float(self.get_parameter('max_angular_z').value)
        self.min_speed = float(self.get_parameter('min_speed_mps').value)
        self.min_curv = float(self.get_parameter('min_curvature_m').value)
        self.lc_rate_thr = float(self.get_parameter('lane_change_rate_threshold').value)
        self.lc_off_thr = float(self.get_parameter('lane_change_offset_threshold').value)
        self.lc_speed = float(self.get_parameter('lane_change_speed').value)
        self.lc_timeout = float(self.get_parameter('lane_change_timeout_s').value)
        self.stop_wait = float(self.get_parameter('stop_wait_s').value)
        self.decel_rate = float(self.get_parameter('decel_rate').value)
        self.accel_rate = float(self.get_parameter('accel_rate').value)
        self.invert_offset_sign = bool(self.get_parameter('invert_offset_sign').value)

        self.pid = PID(
            kp=float(self.get_parameter('pid_kp').value),
            ki=float(self.get_parameter('pid_ki').value),
            kd=float(self.get_parameter('pid_kd').value),
        )

        self.state = VehicleState.LANE_KEEP
        self.current_speed = 0.0
        self.last_steer = 0.0
        self.last_offset = 0.0
        self.offset_rate = 0.0
        self.state_entry_t = time.time()
        # aav: the watchdog's times are on the node's clock (Gazebo's under use_sim_time,
        # as twist_mux's and ego's are).
        self.last_msg_t = self.now_s()
        self._tick_t = self.now_s()
        self._sent_t = self.now_s()
        self.lc_peak_offset = 0.0
        self._last_t = time.time()

        self.sub = self.create_subscription(LaneGeometry, '/perception/lane/geometry', self.geometry_cb, 10)
        # aav: TwistStamped on /drivers/ai/cmd_vel, twist_mux's slot for a learned driver (priority 10),
        # instead of Twist on /control_cmd. Every other driver outranks it.
        self.pub_cmd = self.create_publisher(TwistStamped, '/drivers/ai/cmd_vel', 10)
        self.pub_stat = self.create_publisher(String, '/drivers/ai/lane_status', 10)
        self.pub_vstate = self.create_publisher(String, '/drivers/ai/lane_state', 10)
        self.create_timer(0.1, self.watchdog_cb)

        self.get_logger().info('Control interface ready. Subscribing to /perception/lane/geometry and publishing /drivers/ai/cmd_vel')
        self.get_logger().info(f'invert_offset_sign={self.invert_offset_sign}')
        if self.stop_wait >= AI_SLOT_TIMEOUT_S - 0.1:
            self.get_logger().warning(
                f'stop_wait_s={self.stop_wait} is not below twist_mux\'s {AI_SLOT_TIMEOUT_S} s '
                'for the AI slot: when lane messages stop, ego stops the car first, not this '
                'node\'s slow-down')

    def now_s(self) -> float:
        """Return the node's clock in seconds (aav)."""
        return self.get_clock().now().nanoseconds * 1e-9

    def geometry_cb(self, msg: LaneGeometry):
        self.last_msg_t = self.now_s()
        now = time.time()
        dt = max(now - self._last_t, 1e-4)
        self._last_t = now
        self.offset_rate = (msg.vehicle_offset_m - self.last_offset) / dt
        self.last_offset = msg.vehicle_offset_m
        lanes_ok = msg.left_lane_detected or msg.right_lane_detected

        if self.state == VehicleState.LANE_KEEP:
            self.handle_lane_keep(msg, lanes_ok)
        elif self.state == VehicleState.LANE_CHANGING:
            self.handle_lane_changing(msg, lanes_ok)
        elif self.state == VehicleState.LANE_COMMITTED:
            self.handle_lane_committed(msg, lanes_ok)
        elif self.state == VehicleState.NO_LANE_STOPPING:
            self.handle_no_lane_stopping(msg, lanes_ok)
        elif self.state == VehicleState.RESUMING:
            self.handle_resuming(msg, lanes_ok)

        vs = String()
        vs.data = self.state
        self.pub_vstate.publish(vs)

    def handle_lane_keep(self, msg: LaneGeometry, lanes_ok: bool):
        if not lanes_ok:
            self.transition(VehicleState.NO_LANE_STOPPING)
            return

        offset_large = abs(msg.vehicle_offset_m) > self.lc_off_thr
        offset_fast = abs(self.offset_rate) > self.lc_rate_thr
        if offset_large and offset_fast:
            self.lc_peak_offset = abs(msg.vehicle_offset_m)
            self.transition(VehicleState.LANE_CHANGING)
            return

        cmd = self.build_cmd_lane_keep(msg)
        self.send(cmd)
        self.publish_status(msg, 'LANE_KEEP')

    def handle_lane_changing(self, msg: LaneGeometry, lanes_ok: bool):
        elapsed = time.time() - self.state_entry_t
        if elapsed > self.lc_timeout or not lanes_ok:
            self.transition(VehicleState.NO_LANE_STOPPING)
            return

        curr_abs = abs(msg.vehicle_offset_m)
        self.lc_peak_offset = max(self.lc_peak_offset, curr_abs)
        if curr_abs < self.lc_peak_offset * 0.5 and curr_abs < self.lc_off_thr * 0.5:
            self.transition(VehicleState.LANE_COMMITTED)
            return

        cmd = Twist()
        cmd.linear.x = self.lc_speed
        cmd.angular.z = self.last_steer
        self.send(cmd)
        self.current_speed = self.lc_speed
        self.publish_status(msg, f'LANE_CHANGING peak={self.lc_peak_offset:.2f}m')

    def handle_lane_committed(self, msg: LaneGeometry, lanes_ok: bool):
        self.pid.reset()
        self.transition(VehicleState.LANE_KEEP)
        self.handle_lane_keep(msg, lanes_ok)

    def handle_no_lane_stopping(self, msg: LaneGeometry, lanes_ok: bool):
        if lanes_ok:
            self.transition(VehicleState.RESUMING)
            return

        elapsed = time.time() - self.state_entry_t
        if self.current_speed > 0.0:
            # aav: watchdog_cb slows the car, at decel_rate, whether messages come or not.
            self.publish_status(msg, f'NO_LANE decelerating t={elapsed:.1f}s')
        else:
            self.send(Twist())
            self.publish_status(msg, f'STOPPED waiting t={elapsed:.1f}s')

    def handle_resuming(self, msg: LaneGeometry, lanes_ok: bool):
        if not lanes_ok:
            self.transition(VehicleState.NO_LANE_STOPPING)
            return

        self.current_speed = min(self.base_speed, self.current_speed + self.accel_rate * 0.1)
        cmd = self.build_cmd_lane_keep(msg)
        cmd.linear.x = self.current_speed
        self.send(cmd)
        self.publish_status(msg, f'RESUMING {self.current_speed:.2f}/{self.base_speed:.2f}')
        if self.current_speed >= self.base_speed * 0.95:
            self.transition(VehicleState.LANE_KEEP)

    def send(self, cmd: Twist):
        """Publish a Twist as the TwistStamped twist_mux expects (aav)."""
        out = TwistStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = 'base_link'
        out.twist = cmd
        self.pub_cmd.publish(out)
        self._sent_t = self.now_s()

    def build_cmd_lane_keep(self, msg: LaneGeometry) -> Twist:
        cmd = Twist()
        speed = self.base_speed
        if not msg.both_lanes_detected:
            speed *= 0.7
        if 0.0 < msg.mean_curvature_m < self.min_curv:
            speed *= max(0.4, msg.mean_curvature_m / self.min_curv)
        cmd.linear.x = float(max(self.min_speed, speed))
        self.current_speed = cmd.linear.x

        error = -msg.vehicle_offset_m if self.invert_offset_sign else msg.vehicle_offset_m
        steer = self.pid.compute(error)
        cmd.angular.z = float(np.clip(steer, -self.max_ang, self.max_ang))
        self.last_steer = cmd.angular.z
        return cmd

    def transition(self, new_state: str):
        if self.state != new_state:
            self.get_logger().info(f'State: {self.state} -> {new_state}')
        self.state = new_state
        self.state_entry_t = time.time()
        if new_state in (VehicleState.LANE_KEEP, VehicleState.LANE_COMMITTED):
            self.pid.reset()

    def publish_status(self, msg: LaneGeometry, extra: str):
        s = String()
        s.data = f'[{self.state}] offset={msg.vehicle_offset_m:+.3f}m curv={msg.mean_curvature_m:.1f}m speed={self.current_speed:.2f}m/s {extra}'
        self.pub_stat.publish(s)

    def watchdog_cb(self):
        # aav: no message for stop_wait_s slows the car at decel_rate, as lost lines do,
        # instead of one zero command after 2 s. The slow-down runs here, every 0.1 s, so
        # it goes on when the messages stop (lane_speed.stopping_speed).
        now = self.now_s()
        dt = now - self._tick_t
        self._tick_t = now
        elapsed = now - self.last_msg_t
        if elapsed > self.stop_wait and self.state != VehicleState.NO_LANE_STOPPING:
            self.get_logger().warning(f'No geometry message for {elapsed:.1f}s -> slowing down', throttle_duration_sec=2.0)
            self.transition(VehicleState.NO_LANE_STOPPING)
        if self.state == VehicleState.NO_LANE_STOPPING and self.current_speed > 0.0:
            self.current_speed = stopping_speed(self.current_speed, self.decel_rate, dt,
                                                now - self._sent_t)
            cmd = Twist()
            cmd.linear.x = self.current_speed
            cmd.angular.z = self.last_steer if self.current_speed > 0.0 else 0.0
            self.send(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = ControlInterface()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # aav: Ctrl-C arrives twice under launch, and Jazzy's handler may already have shut
        # rclpy down: ignore the second, and shut down only if it hasn't happened.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
