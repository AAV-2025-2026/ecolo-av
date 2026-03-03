#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu


class MockImuNode(Node):
    def __init__(self):
        super().__init__("mock_imu_node")

        # Parameters
        self.declare_parameter("publish_rate", 50.0)  # Hz
        self.declare_parameter("frame_id", "imu_link")

        rate = self.get_parameter("publish_rate").value
        self.frame_id = self.get_parameter("frame_id").value

        self.dt = 1.0 / rate
        self.t = 0.0

        self.pub = self.create_publisher(Imu, "/imu/data", 10)
        self.timer = self.create_timer(self.dt, self.timer_callback)

        self.get_logger().info(
            f"Mock IMU publishing on /imu/data at {rate:.1f} Hz"
        )

    def timer_callback(self):
        msg = Imu()

        # Timestamp + frame
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id

        # -------------------------------
        # Fake angular velocity (rad/s)
        # -------------------------------
        msg.angular_velocity.x = 0.1 * math.sin(self.t)
        msg.angular_velocity.y = 0.1 * math.cos(self.t)
        msg.angular_velocity.z = 0.05

        # Optional covariance (reasonable defaults)
        msg.angular_velocity_covariance = [
            0.01, 0.0,  0.0,
            0.0,  0.01, 0.0,
            0.0,  0.0,  0.01
        ]

        # -------------------------------
        # Fake linear acceleration (m/s²)
        # -------------------------------
        g = 9.80665

        msg.linear_acceleration.x = 0.5 * math.sin(0.5 * self.t)
        msg.linear_acceleration.y = 0.5 * math.cos(0.5 * self.t)
        msg.linear_acceleration.z = g   # gravity

        msg.linear_acceleration_covariance = [
            0.04, 0.0,  0.0,
            0.0,  0.04, 0.0,
            0.0,  0.0,  0.04
        ]

        # -------------------------------
        # Orientation not provided
        # -------------------------------
        msg.orientation_covariance[0] = -1.0

        self.pub.publish(msg)

        self.t += self.dt


def main(args=None):
    rclpy.init(args=args)
    node = MockImuNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
