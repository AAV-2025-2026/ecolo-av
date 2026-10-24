import random

import rclpy
from rclpy.node import Node

from std_msgs.msg import Float32MultiArray
from sensor_msgs.msg import Imu
from geometry_msgs.msg import TwistStamped


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


class LongitudinalPlant(Node):
    def __init__(self):
        super().__init__('longitudinal_plant')

        # --- parameters (match your MATLAB script) ---
        self.dt = 0.01
        self.m = 60.0        # kg
        self.c_drag = 3.0
        self.k_throt = 40.0  # N @ throttle = 1
        self.k_brake = 80.0  # N @ brake_force = 1

        # brake actuator dynamics
        self.tau_b = 0.15
        self.k_b_act = 1.0

        # state
        self.v = 0.0           # speed [m/s]
        self.a_true = 0.0      # accel [m/s^2]
        self.brake_force = 0.0 # normalized 0..1

        # last commanded throttle/brake from controller
        self.throttle_cmd = 0.0
        self.brake_cmd = 0.0

        # noise level for IMU accel
        self.imu_sigma = 0.05

        # --- ROS I/O ---
        self.sub_cmd = self.create_subscription(
            Float32MultiArray,
            'motor_cmd',
            self.cmd_callback,
            10
        )

        self.pub_imu = self.create_publisher(Imu, 'imu_sim', 10)
        self.pub_twist = self.create_publisher(TwistStamped, 'speed_sim', 10)

        # timer for integration loop
        self.timer = self.create_timer(self.dt, self.update)

        self.get_logger().info('Longitudinal plant simulator started')

    def cmd_callback(self, msg):
        # motor_cmd.data = [throttle, brake]
        if len(msg.data) >= 2:
            self.throttle_cmd = clamp(float(msg.data[0]), 0.0, 1.0)
            self.brake_cmd = clamp(float(msg.data[1]), 0.0, 1.0)
        else:
            self.get_logger().warn('motor_cmd message has < 2 elements')

    def update(self):
        # --- drive force from throttle ---
        f_drive = self.k_throt * self.throttle_cmd

        # --- brake actuator inner dynamics (normalized brake_force 0..1) ---
        u_act = clamp(self.brake_cmd, 0.0, 1.0)
        self.brake_force += self.dt * (
            (-self.brake_force + self.k_b_act * u_act) / self.tau_b
        )
        self.brake_force = clamp(self.brake_force, 0.0, 1.0)
        f_brake = self.k_brake * self.brake_force

        # --- vehicle dynamics ---
        f_drag = self.c_drag * self.v
        self.a_true = (f_drive - f_brake - f_drag) / self.m

        self.v += self.a_true * self.dt
        if self.v < 0.0:
            self.v = 0.0

        # --- publish fake sensors ---
        self.publish_imu()
        self.publish_twist()

    def publish_imu(self):
        msg = Imu()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'

        a_noise = random.gauss(0.0, self.imu_sigma)
        ax_meas = self.a_true + a_noise

        msg.linear_acceleration.x = float(ax_meas)
        msg.linear_acceleration.y = 0.0
        msg.linear_acceleration.z = 0.0

        self.pub_imu.publish(msg)

    def publish_twist(self):
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'

        msg.twist.linear.x = float(self.v)
        msg.twist.linear.y = 0.0
        msg.twist.linear.z = 0.0

        self.pub_twist.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = LongitudinalPlant()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

