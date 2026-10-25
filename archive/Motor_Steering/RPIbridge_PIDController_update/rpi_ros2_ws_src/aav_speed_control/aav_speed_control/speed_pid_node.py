#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import rclpy
from rclpy.node import Node

from ackermann_msgs.msg import AckermannDrive, AckermannDriveStamped
from std_msgs.msg import Float32


@dataclass
class DesiredDrive:
    steering_angle: float = 0.0
    speed_mps: float = 0.0


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class SpeedPidNode(Node):
    def __init__(self) -> None:
        super().__init__('speed_pid')

        self.declare_parameter('input_topic', '/cmd_drive')
        self.declare_parameter('input_is_stamped', True)
        self.declare_parameter('measured_speed_topic', '/vehicle/speed_mps')
        self.declare_parameter('output_topic', '/ackermann_cmd')
        self.declare_parameter('control_rate_hz', 20.0)
        self.declare_parameter('desired_timeout_ms', 300)
        self.declare_parameter('speed_timeout_ms', 300)
        self.declare_parameter('allow_reverse', False)
        self.declare_parameter('stop_speed_threshold_mps', 0.05)
        self.declare_parameter('stop_brake_cmd', 150.0)
        self.declare_parameter('kp', 120.0)
        self.declare_parameter('ki', 20.0)
        self.declare_parameter('kd', 0.0)
        self.declare_parameter('integral_min', -50.0)
        self.declare_parameter('integral_max', 50.0)
        self.declare_parameter('max_throttle_cmd', 250.0)
        self.declare_parameter('max_brake_cmd', 800.0)
        self.declare_parameter('steer_passthrough', True)

        input_topic = str(self.get_parameter('input_topic').value)
        input_is_stamped = bool(self.get_parameter('input_is_stamped').value)
        measured_speed_topic = str(self.get_parameter('measured_speed_topic').value)
        output_topic = str(self.get_parameter('output_topic').value)

        self.last_desired = DesiredDrive()
        self.last_desired_time = self.get_clock().now()
        self.last_measured_speed = 0.0
        self.last_speed_time = self.get_clock().now()

        self.integral = 0.0
        self.prev_error: Optional[float] = None

        if input_is_stamped:
            self.drive_sub = self.create_subscription(AckermannDriveStamped, input_topic, self.on_drive_stamped, 20)
        else:
            self.drive_sub = self.create_subscription(AckermannDrive, input_topic, self.on_drive, 20)
        self.speed_sub = self.create_subscription(Float32, measured_speed_topic, self.on_speed, 20)
        self.cmd_pub = self.create_publisher(AckermannDriveStamped, output_topic, 20)

        period = 1.0 / max(1.0, float(self.get_parameter('control_rate_hz').value))
        self.timer = self.create_timer(period, self.on_timer)

        self.get_logger().info(f'Speed PID listening on {input_topic} and {measured_speed_topic}; output -> {output_topic}')

    def on_drive_stamped(self, msg: AckermannDriveStamped) -> None:
        self.last_desired_time = self.get_clock().now()
        self.last_desired = DesiredDrive(
            steering_angle=float(msg.drive.steering_angle),
            speed_mps=float(msg.drive.speed),
        )

    def on_drive(self, msg: AckermannDrive) -> None:
        self.last_desired_time = self.get_clock().now()
        self.last_desired = DesiredDrive(
            steering_angle=float(msg.steering_angle),
            speed_mps=float(msg.speed),
        )

    def on_speed(self, msg: Float32) -> None:
        self.last_speed_time = self.get_clock().now()
        self.last_measured_speed = float(msg.data)

    def publish_stop(self, brake_cmd: float = 0.0) -> None:
        out = AckermannDriveStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.drive.steering_angle = self.last_desired.steering_angle if bool(self.get_parameter('steer_passthrough').value) else 0.0
        out.drive.speed = 0.0
        out.drive.acceleration = -abs(float(brake_cmd)) if brake_cmd > 0.0 else 0.0
        self.cmd_pub.publish(out)

    def on_timer(self) -> None:
        now = self.get_clock().now()
        desired_age_ms = (now - self.last_desired_time).nanoseconds / 1e6
        speed_age_ms = (now - self.last_speed_time).nanoseconds / 1e6

        desired_timeout_ms = int(self.get_parameter('desired_timeout_ms').value)
        speed_timeout_ms = int(self.get_parameter('speed_timeout_ms').value)

        if desired_age_ms > desired_timeout_ms:
            self.integral = 0.0
            self.prev_error = None
            self.publish_stop(brake_cmd=float(self.get_parameter('stop_brake_cmd').value))
            return

        if speed_age_ms > speed_timeout_ms:
            self.integral = 0.0
            self.prev_error = None
            self.publish_stop(brake_cmd=float(self.get_parameter('stop_brake_cmd').value))
            return

        desired_speed = float(self.last_desired.speed_mps)
        measured_speed = float(self.last_measured_speed)
        allow_reverse = bool(self.get_parameter('allow_reverse').value)
        stop_threshold = float(self.get_parameter('stop_speed_threshold_mps').value)

        if not allow_reverse:
            desired_speed = max(0.0, desired_speed)
            measured_speed = max(0.0, measured_speed)

        if abs(desired_speed) < stop_threshold:
            self.integral = 0.0
            self.prev_error = None
            if abs(measured_speed) > stop_threshold:
                self.publish_stop(brake_cmd=float(self.get_parameter('stop_brake_cmd').value))
            else:
                self.publish_stop(brake_cmd=0.0)
            return

        dt = 1.0 / max(1.0, float(self.get_parameter('control_rate_hz').value))
        error = desired_speed - measured_speed

        self.integral += error * dt
        self.integral = clamp(
            self.integral,
            float(self.get_parameter('integral_min').value),
            float(self.get_parameter('integral_max').value),
        )

        derivative = 0.0 if self.prev_error is None else (error - self.prev_error) / dt
        self.prev_error = error

        kp = float(self.get_parameter('kp').value)
        ki = float(self.get_parameter('ki').value)
        kd = float(self.get_parameter('kd').value)

        u = kp * error + ki * self.integral + kd * derivative
        max_throttle_cmd = float(self.get_parameter('max_throttle_cmd').value)
        max_brake_cmd = float(self.get_parameter('max_brake_cmd').value)
        u = clamp(u, -max_brake_cmd, max_throttle_cmd)

        out = AckermannDriveStamped()
        out.header.stamp = now.to_msg()
        out.drive.steering_angle = self.last_desired.steering_angle if bool(self.get_parameter('steer_passthrough').value) else 0.0
        out.drive.speed = desired_speed
        out.drive.acceleration = float(u)
        self.cmd_pub.publish(out)


def main() -> None:
    rclpy.init()
    node = SpeedPidNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
