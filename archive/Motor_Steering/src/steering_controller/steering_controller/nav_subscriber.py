#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Accel


class AccelRequirementSubscriber(Node):
    def __init__(self):
        super().__init__('accel_requirement_subscriber')

        self.subscription = self.create_subscription(
            Accel,
            '/nav/acceleration_requirement',
            self.listener_callback,
            10
        )

        self.subscription  # prevent unused variable warning

        self.get_logger().info(
            'Acceleration requirement subscriber started'
        )

    def listener_callback(self, msg: Accel):
        self.get_logger().info(
            f'\nLinear Acceleration  [m/s^2]: '
            f'x={msg.linear.x:.3f}, '
            f'y={msg.linear.y:.3f}, '
            f'z={msg.linear.z:.3f}\n'
            f'Angular Acceleration [rad/s^2]: '
            f'x={msg.angular.x:.3f}, '
            f'y={msg.angular.y:.3f}, '
            f'z={msg.angular.z:.3f}'
        )


def main(args=None):
    rclpy.init(args=args)
    node = AccelRequirementSubscriber()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
