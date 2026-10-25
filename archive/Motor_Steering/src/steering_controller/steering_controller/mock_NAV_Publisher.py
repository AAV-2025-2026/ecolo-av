#!/usr/bin/env python3

import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Accel


class MockAccelRequirementPublisher(Node):
    def __init__(self):
        super().__init__('mock_accel_requirement_publisher')

        # Publisher
        self.publisher_ = self.create_publisher(
            Accel,
            '/nav/acceleration_requirement',
            10
        )

        # Publish rate (Hz)
        self.publish_rate_hz = 20.0
        self.timer = self.create_timer(
            1.0 / self.publish_rate_hz,
            self.publish_callback
        )

        self.start_time = self.get_clock().now().seconds_nanoseconds()[0]

        self.get_logger().info(
            'Mock acceleration requirement publisher started'
        )

    def publish_callback(self):
        msg = Accel()

        # Time since start
        now_sec = self.get_clock().now().nanoseconds * 1e-9
        t = now_sec - self.start_time

        # ---- Linear acceleration (m/s^2) ----
        # Forward acceleration: smooth accel / decel
        msg.linear.x = 1.5 * math.sin(0.2 * t)

        # Lateral acceleration: steering-induced (small)
        msg.linear.y = 0.4 * math.sin(0.2 * t + math.pi / 4.0)

        # Vertical acceleration: near zero (flat ground)
        msg.linear.z = 0.05 * math.sin(0.5 * t)

        # ---- Angular acceleration (rad/s^2) ----
        # Roll & pitch: minimal
        msg.angular.x = 0.02 * math.sin(0.3 * t)
        msg.angular.y = 0.02 * math.sin(0.3 * t + math.pi / 6.0)

        # Yaw acceleration: realistic steering dynamics
        msg.angular.z = 0.4 * math.sin(0.2 * t)

        self.publisher_.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = MockAccelRequirementPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
