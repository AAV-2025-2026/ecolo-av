#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from ackermann_msgs.msg import AckermannDrive
import math

class JoyToAckermann(Node):
    def __init__(self):
        super().__init__('joy_to_ackermann')
        # Parameters -- tune these to your joystick and vehicle
        self.declare_parameter('joy_topic', '/joy')
        self.declare_parameter('drive_topic', '/driveData')
        self.declare_parameter('axis_steer', 0)        # index of steering axis
        self.declare_parameter('axis_throttle', 1)    # index of throttle axis
        self.declare_parameter('deadman_button', 0)   # button index that must be held to enable drive
        self.declare_parameter('max_speed', 1.0)      # meters/second (or vehicle units)
        self.declare_parameter('max_steer_deg', 30.0) # degrees
        self.declare_parameter('deadzone', 0.05)
        self.declare_parameter('invert_steer', False)
        self.declare_parameter('invert_throttle', True)

        self.joy_topic = self.get_parameter('joy_topic').value
        self.drive_topic = self.get_parameter('drive_topic').value
        self.axis_steer = self.get_parameter('axis_steer').value
        self.axis_throttle = self.get_parameter('axis_throttle').value
        self.deadman_button = self.get_parameter('deadman_button').value
        self.max_speed = float(self.get_parameter('max_speed').value)
        self.max_steer_rad = math.radians(float(self.get_parameter('max_steer_deg').value))
        self.deadzone = float(self.get_parameter('deadzone').value)
        self.invert_steer = bool(self.get_parameter('invert_steer').value)
        self.invert_throttle = bool(self.get_parameter('invert_throttle').value)

        self.pub = self.create_publisher(AckermannDrive, self.drive_topic, 10)
        self.sub = self.create_subscription(Joy, self.joy_topic, self.joy_cb, 10)

        self.get_logger().info(f'Publishing AckermannDrive on {self.drive_topic}, reading Joy on {self.joy_topic}')

    def apply_deadzone(self, v):
        return 0.0 if abs(v) < self.deadzone else v

    def joy_cb(self, msg: Joy):
        # Safety: require deadman button held
        hold = False
        if 0 <= self.deadman_button < len(msg.buttons):
            hold = bool(msg.buttons[self.deadman_button])

        if not hold:
            # publish stop command (zero speed) while preserving steering 0
            stop = AckermannDrive()
            stop.speed = 0.0
            stop.steering_angle = 0.0
            self.pub.publish(stop)
            return

        # Read axes (guard index)
        steer_raw = 0.0
        throttle_raw = 0.0
        if 0 <= self.axis_steer < len(msg.axes):
            steer_raw = msg.axes[self.axis_steer]
        if 0 <= self.axis_throttle < len(msg.axes):
            throttle_raw = msg.axes[self.axis_throttle]

        if self.invert_steer:
            steer_raw = -steer_raw
        if self.invert_throttle:
            throttle_raw = -throttle_raw

        steer_raw = self.apply_deadzone(steer_raw)
        throttle_raw = self.apply_deadzone(throttle_raw)

        # Map [-1,1] to steering angle and speed
        steering_angle = steer_raw * self.max_steer_rad
        speed = throttle_raw * self.max_speed

        # Optional: small scaling curve for finer low-speed control:
        # speed = math.copysign(abs(speed)**1.3, speed)

        m = AckermannDrive()
        m.speed = float(speed)
        m.acceleration = float(speed)  # optional, set to speed for simplicity
        m.steering_angle = float(steering_angle)
        self.pub.publish(m)


def main(args=None):
    rclpy.init(args=args)
    node = JoyToAckermann()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()