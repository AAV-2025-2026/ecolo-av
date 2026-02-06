#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32

class ImuSpd(Node):

    

    def __init__(self):
        super().__init__('imu_spd')
        self.spd = 0.0
        self.latest_imu_msg = None
        self.subscription = self.create_subscription(
            Imu,
            'imu/data',
            self.imu_spd,
            10
        )

        # Speed publisher
        self.spd_publisher = self.create_publisher(
            Float32,
            'imu/speed',
            10
        )

        self.timer = self.create_timer(0.05, self.poll_imu)
        self.get_logger().info('IMU live speed started')


    def poll_imu(self):
        # Runs every 50 ms
        #self.get_logger().info('Timer fired')

        if self.latest_imu_msg is None:
            return
        
        msg = self.latest_imu_msg

        self.spd += msg.linear_acceleration.x *0.05

        spd_msg = Float32()
        spd_msg.data = self.spd
        self.spd_publisher.publish(spd_msg)
        self.get_logger().info(f'Speed published: {self.spd:.2f} m/s')

    def imu_spd(self, msg: Imu):
        self.latest_imu_msg = msg
        


def main(args=None):
    rclpy.init(args=args)
    node = ImuSpd()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
