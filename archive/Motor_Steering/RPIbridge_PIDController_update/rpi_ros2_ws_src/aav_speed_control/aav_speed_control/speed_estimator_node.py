#!/usr/bin/env python3
from __future__ import annotations

import math

import rclpy
from rclpy.node import Node

from std_msgs.msg import Float32, Int32


class SpeedEstimatorNode(Node):
    def __init__(self) -> None:
        super().__init__('speed_estimator')

        self.declare_parameter('count_topic', '/wheel_encoder/count')
        self.declare_parameter('window_s', 0.1)
        self.declare_parameter('pulses_per_sensor_rev', 8.0)
        self.declare_parameter('sensor_revs_per_wheel_rev', 1.0)
        self.declare_parameter('wheel_diameter_m', 0.30)

        count_topic = str(self.get_parameter('count_topic').value)

        self.rpm_pub = self.create_publisher(Float32, '/wheel_encoder/rpm', 20)
        self.speed_mps_pub = self.create_publisher(Float32, '/vehicle/speed_mps', 20)
        self.speed_kph_pub = self.create_publisher(Float32, '/vehicle/speed_kph', 20)

        self.sub = self.create_subscription(Int32, count_topic, self.on_count, 20)
        self.get_logger().info(f'Speed estimator listening on {count_topic}')

    def on_count(self, msg: Int32) -> None:
        count = int(msg.data)
        window_s = float(self.get_parameter('window_s').value)
        pulses_per_sensor_rev = float(self.get_parameter('pulses_per_sensor_rev').value)
        sensor_revs_per_wheel_rev = float(self.get_parameter('sensor_revs_per_wheel_rev').value)
        wheel_diameter_m = float(self.get_parameter('wheel_diameter_m').value)

        if window_s <= 1e-9 or pulses_per_sensor_rev <= 1e-9 or sensor_revs_per_wheel_rev <= 1e-9:
            self.get_logger().error('Invalid estimator parameters; check window_s, pulses_per_sensor_rev, and sensor_revs_per_wheel_rev')
            return

        sensor_rev_per_window = count / pulses_per_sensor_rev
        wheel_rev_per_window = sensor_rev_per_window / sensor_revs_per_wheel_rev
        wheel_rev_per_s = wheel_rev_per_window / window_s
        rpm = wheel_rev_per_s * 60.0

        wheel_circumference_m = math.pi * wheel_diameter_m
        speed_mps = wheel_rev_per_s * wheel_circumference_m
        speed_kph = speed_mps * 3.6

        rpm_msg = Float32()
        rpm_msg.data = float(rpm)
        speed_mps_msg = Float32()
        speed_mps_msg.data = float(speed_mps)
        speed_kph_msg = Float32()
        speed_kph_msg.data = float(speed_kph)

        self.rpm_pub.publish(rpm_msg)
        self.speed_mps_pub.publish(speed_mps_msg)
        self.speed_kph_pub.publish(speed_kph_msg)


def main() -> None:
    rclpy.init()
    node = SpeedEstimatorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
