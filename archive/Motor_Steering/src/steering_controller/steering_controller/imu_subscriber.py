#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu


class ImuSubscriber(Node):
    def __init__(self):
        super().__init__('imu_subscriber')

        self.subscription = self.create_subscription(
            Imu,
            'imu/data',
            self.imu_callback,
            10
        )

        self.get_logger().info('IMU Subscriber started')

    def imu_callback(self, msg: Imu):
        self.get_logger().info(
            f'Accel [m/s^2]: '
            f'x={msg.linear_acceleration.x:.2f}, '
            f'y={msg.linear_acceleration.y:.2f}, '
            f'z={msg.linear_acceleration.z:.2f} | '
            f'Gyro [rad/s]: '
            f'x={msg.angular_velocity.x:.2f}, '
            f'y={msg.angular_velocity.y:.2f}, '
            f'z={msg.angular_velocity.z:.2f}'
        )


def main(args=None):
    rclpy.init(args=args)
    node = ImuSubscriber()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
