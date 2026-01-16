
#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
import random
import time


class MockImuPublisher(Node):
    def __init__(self):
        super().__init__('mock_imu_publisher')

        self.publisher_ = self.create_publisher(Imu, 'imu/data', 10)
        self.timer = self.create_timer(0.1, self.publish_imu_data)  # 10 Hz

        self.get_logger().info('Mock IMU Publisher started')

    def publish_imu_data(self):
        msg = Imu()

        # Timestamp
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'imu_link'

        # Linear acceleration (m/s)
        msg.linear_acceleration.x = random.uniform(-1.0, 1.0)
        msg.linear_acceleration.y = random.uniform(-1.0, 1.0)
        msg.linear_acceleration.z = random.uniform(-1.0, 1.0)

        # Gyro acceleration (treated as m/s per your requirement)
        msg.angular_velocity.x = random.uniform(-0.5, 0.5)
        msg.angular_velocity.y = random.uniform(-0.5, 0.5)
        msg.angular_velocity.z = random.uniform(-0.5, 0.5)

        # Orientation not used (set to zero / unknown)
        msg.orientation.w = 1.0

        self.publisher_.publish(msg)
        #self.get_logger().info(msg)


def main(args=None):
    rclpy.init(args=args)
    node = MockImuPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
