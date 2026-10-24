#!/usr/bin/env python3

import math
import rclpy
from rclpy.node import Node

from ackermann_msgs.msg import AckermannDriveStamped
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32

import serial
import time


class SteeringImuP(Node):

    def __init__(self):
        super().__init__('steering_imu_p')

        #self.declare_parameter('esp_addr', 0x00)  # PLEASE CHANGE THIS, 0X00 IS TEMPORARY, CHANGE WITH REAL ADDRESS
        #self.i2c_comm = I2CCommunication(self.esp_addr)

        self.ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1))   #THIS NEEDS TO BE CHANGED TO REAL SPECS
        time.sleep(2)


        # PARAMETERS (SI UNITS)
        self.declare_parameter('wheelbase', 1.57)  # [m]
        self.declare_parameter('delta_max', 0.55)  # [rad] max steering angle
        self.declare_parameter('motor_ratio', 0.000019)  # [rad/m] actuator geometry (1.11 deg/cm)
        self.declare_parameter('kp', 0.5)  # [1/(rad/s)]
        self.declare_parameter('control_rate', 100.0)  # [Hz]
        self.declare_parameter('use_feedforward', True)

        self.L = self.get_parameter('wheelbase').value
        self.delta_max = self.get_parameter('delta_max').value
        self.motor_ratio = self.get_parameter('motor_ratio').value
        self.kp = self.get_parameter('kp').value
        self.rate = self.get_parameter('control_rate').value
        self.use_ff = self.get_parameter('use_feedforward').value

        # STATE VARIABLES
        self.v = 0.0
        self.delta_desired = 0.0
        self.omega_measured = 0.0

        self.dt = 1.0 / self.rate

        # Subscribers
        self.create_subscription(AckermannDriveStamped, '/drive', self.drive_callback, 10)
        self.create_subscription(Imu, '/imu/data', self.imu_callback, 10)

        # Publisher
        self.cmd_pub = self.create_publisher(Float32, '/steering_motor_cmd', 10)

        # Timer-based control loop
        self.create_timer(self.dt, self.control_loop)

        self.get_logger().info("Steering IMU P Controller with actuator remap started")

    # ======================================
    # Callbacks
    # ======================================
    def drive_callback(self, msg):
        self.v = msg.drive.speed  # [m/s]
        self.delta_desired = msg.drive.steering_angle  # [rad]

    def imu_callback(self, msg):
        self.omega_measured = msg.angular_velocity.z  # [rad/s]

    # ======================================
    # Control Loop
    # ======================================
    def control_loop(self):

        byte_list = [0]*1 # I am not sure that if re-initialize the list every time or append+pop for each iteration is
        # the least performance intensive, but for the sake of not getting issues with pop a 0 size list i choose former

        # I have consulted the sands of which says re allocate ram for a size 1 list is minimal

        if abs(self.v) < 0.01:
            return

        # Desired yaw rate from bicycle model
        omega_desired = (self.v / self.L) * math.tan(self.delta_desired)

        # Error
        error = omega_desired - self.omega_measured  # [rad/s]

        # Proportional output in radians
        u_pid_rad = self.kp * error

        # Feedforward
        if self.use_ff:
            u_pid_rad += self.delta_desired

        # Map PID output (radians) to actuator
        # x_max = 0.1  # Half stroke [m]
        x_max_mod = 0.00078125

        # Linear extension required [m]
        x_cmd = u_pid_rad / self.motor_ratio

        # It should normalize to +127, -128
        u_motor = x_cmd / x_max_mod

        # Clamp final command
        u_motor = max(min(round(u_motor), 127), -128)

        # Publish
        msg = Float32()
        msg.data = float(u_motor)

        byte_list[0] = (u_motor)

        self.cmd_pub.publish(msg)
        self.ser.write(bytes(byte_list))



def main(args=None):
    rclpy.init(args=args)
    node = SteeringImuP()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
