#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Accel
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32
import time


class ImuOnlyOuterLoop(Node):
    def __init__(self):
        super().__init__('imu_only_outer_loop')

        # -------- Controller parameters --------

        #Linear Motor Specs
        #https://www.servocity.com/6-stroke-560-lb-thrust-super-duty-linear-actuator/
        #Speed: Max Load 2.63 in/s; Min Load 1.85 in/s
        #


        self.kp = 0.47                 # proportional gain
        # self.ki = 0.2               # integral (commented out)
        self.deadband = 0.05          # rad/s^2
        self.max_motor_vel = 0.047     # m/s
        self.max_pwm = 1.0
        self.control_period = 0.02    # 50 Hz

        # -------- State --------
        self.alpha_y_req = 0.0        # Forward/backward desired accel
        self.alpha_x_req = 0.0        # Horizontal desired accel
        #self.alpha_z_req = 0.0        # Vertical desired accel

        self.alpha_y_meas = 0.0
        self.alpha_x_meas = 0.0
        #self.alpha_z_meas = 0.0

        self.prev_ang_vel_x = 0.0
        self.prev_ang_vel_y = 0.0
        #self.prev_ang_vel_z = 0.0
        self.prev_time = time.time()

        # -------- ROS Interfaces --------
        # Navigation acceleration requirement
        self.create_subscription(
            Accel,
            '/nav/acceleration_requirement',
            self.nav_cb,
            10
        )

        # IMU feedback
        self.create_subscription(
            Imu,
            '/imu/data',
            self.imu_cb,
            10
        )

        # Motor velocity command
        self.motor_pub = self.create_publisher(
            Float32,
            '/motor/velocity_cmd',
            10
        )

        # Control loop timer
        self.timer = self.create_timer(
            self.control_period,
            self.control_loop
        )

        self.get_logger().info(
            "Steering System Start"
        )

    # --------------------------- NAV callback ---------------------------
    def nav_cb(self, msg):
        # Axes remapping:
        # Forward/backward → y
        # Horizontal → x
        # Vertical → z
        self.alpha_y_req = msg.angular.y
        self.alpha_x_req = msg.angular.x
        #self.alpha_z_req = msg.angular.z

    # --------------------------- IMU callback ---------------------------
    def imu_cb(self, msg):
        now = time.time()
        dt = now - self.prev_time
        self.prev_time = now

        # IMU angular velocity
        #yaw_rate = msg.angular_velocity.z      # rotation about z
        pitch_rate = msg.angular_velocity.y    # rotation about y
        roll_rate = msg.angular_velocity.x     # rotation about x

        # Numerically differentiate to get angular acceleration
        self.alpha_y_meas = (pitch_rate - self.prev_ang_vel_y) / dt
        self.alpha_x_meas = (roll_rate - self.prev_ang_vel_x) / dt
        #self.alpha_z_meas = (yaw_rate - self.prev_ang_vel_z) / dt

        # Save for next loop
        self.prev_ang_vel_x = roll_rate
        self.prev_ang_vel_y = pitch_rate
        #self.prev_ang_vel_z = yaw_rate

    # --------------------------- Control Loop ---------------------------
    def control_loop(self):
        # Forward/backward error (y-axis)
        error_y = self.alpha_y_req - self.alpha_y_meas

        # Horizontal error (x-axis)
        error_x = self.alpha_x_req - self.alpha_x_meas

        # Vertical error (z-axis)
        #error_z = self.alpha_z_req - self.alpha_z_meas

        # -------- Proportional control only (P) --------
        # Integral is commented out for slow actuator
        cmd_y = self.kp * error_y
        # cmd_y += self.ki * self.integral_y

        cmd_x = self.kp * error_x
        # cmd_x += self.ki * self.integral_x

        #cmd_z = self.kp * error_z
        # cmd_z += self.ki * self.integral_z

        # -------- Deadband --------
        if abs(error_y) < self.deadband:
            cmd_y = 0.0
        if abs(error_x) < self.deadband:
            cmd_x = 0.0
        #if abs(error_z) < self.deadband:
        #    cmd_z = 0.0

        # -------- Saturation --------
        #cmd_y = max(-self.max_motor_vel, min(self.max_motor_vel, cmd_y))
        cmd_x = max(-self.max_pwm, min(self.max_pwm, cmd_x))
        #cmd_z = max(-self.max_motor_vel, min(self.max_motor_vel, cmd_z))

        # -------- Publish motor command --------
        # Assuming 1 motor controls primary axis (forward/backward = y)
        # You can extend for multi-axis motors if needed
        self.motor_pub.publish(Float32(data=cmd_x))


def main(args=None):
    rclpy.init(args=args)
    node = ImuOnlyOuterLoop()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
