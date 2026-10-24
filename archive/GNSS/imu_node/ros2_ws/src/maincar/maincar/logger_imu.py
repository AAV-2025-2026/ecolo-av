#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
import csv
import time

class ImuLoggerNode(Node):
    def __init__(self):
        super().__init__("imu_logger_node")

        # Create CSV file
        self.log_file = open("imu_log.csv", "a", newline="")
        self.writer = csv.writer(self.log_file)

        # Write header only if file is empty
        if self.log_file.tell() == 0:
            self.writer.writerow(["timestamp", "ax", "ay", "az", "gx", "gy", "gz"])

        # Subscriber to IMU data
        self.subscription = self.create_subscription(
            Imu,
            "/imu/data",
            self.imu_callback,
            10
        )

        self.get_logger().info("IMU logging node started. Subscribed to /imu/data")

    def imu_callback(self, msg: Imu):
        # Extract values
        ax = msg.linear_acceleration.x
        ay = msg.linear_acceleration.y
        az = msg.linear_acceleration.z

        gx = msg.angular_velocity.x
        gy = msg.angular_velocity.y
        gz = msg.angular_velocity.z

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            self.writer.writerow([timestamp, ax, ay, az, gx, gy, gz])
            self.log_file.flush()
        except Exception as e:
            self.get_logger().error(f"Failed to write IMU log: {e}")

    def destroy_node(self):
        self.log_file.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ImuLoggerNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()