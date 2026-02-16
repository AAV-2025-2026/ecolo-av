#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from ackermann_msgs.msg import AckermannDrive
import math

class JoyToAckermann(Node):
    def __init__(self):
        super().__init__('joy_to_ackermann')
        
        # Parameters
        self.declare_parameter('joy_topic', '/joy')
        self.declare_parameter('drive_topic', '/driveData')
        self.declare_parameter('axis_steer', 0)
        self.declare_parameter('axis_throttle', 1)
        self.declare_parameter('deadman_button', 0)      # Forward button
        self.declare_parameter('deadman_button_rev', 1)  # Reverse button
        self.declare_parameter('max_speed', 1.0)
        self.declare_parameter('max_steer_deg', 30.0)
        self.declare_parameter('deadzone', 0.05)
        self.declare_parameter('invert_steer', False)
        self.declare_parameter('invert_throttle', True)

        self.joy_topic = self.get_parameter('joy_topic').value
        self.drive_topic = self.get_parameter('drive_topic').value
        self.axis_steer = self.get_parameter('axis_steer').value
        self.axis_throttle = self.get_parameter('axis_throttle').value
        self.deadman_button_fwd = self.get_parameter('deadman_button').value
        self.deadman_button_rev = self.get_parameter('deadman_button_rev').value
        self.max_speed = float(self.get_parameter('max_speed').value)
        self.max_steer_rad = math.radians(float(self.get_parameter('max_steer_deg').value))
        self.deadzone = float(self.get_parameter('deadzone').value)
        self.invert_steer = bool(self.get_parameter('invert_steer').value)
        self.invert_throttle = bool(self.get_parameter('invert_throttle').value)

        self.pub = self.create_publisher(AckermannDrive, self.drive_topic, 10)
        self.sub = self.create_subscription(Joy, self.joy_topic, self.joy_cb, 10)

        self.get_logger().info(f'Joy → {self.drive_topic} | Btn{self.deadman_button_fwd}=FWD, Btn{self.deadman_button_rev}=REV, BOTH=STOP')

    def apply_deadzone(self, v):
        return 0.0 if abs(v) < self.deadzone else v

    def joy_cb(self, msg: Joy):
        # Check forward/reverse buttons
        hold_fwd = False
        hold_rev = False
        
        if 0 <= self.deadman_button_fwd < len(msg.buttons):
            hold_fwd = bool(msg.buttons[self.deadman_button_fwd])
        if 0 <= self.deadman_button_rev < len(msg.buttons):
            hold_rev = bool(msg.buttons[self.deadman_button_rev])

        # STOP if BOTH buttons pressed (safety interlock) OR neither pressed
        if (hold_fwd and hold_rev) or (not hold_fwd and not hold_rev):
            stop = AckermannDrive()
            stop.speed = 0.0
            stop.steering_angle = 0.0
            self.pub.publish(stop)
            return

        # Read axes
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

        # Map steering
        steering_angle = steer_raw * self.max_steer_rad
        
        speed = 0.0
        
        if hold_fwd:
            # Forward: only positive throttle (push forward)
            if throttle_raw > 0:
                speed = throttle_raw * self.max_speed
        
        elif hold_rev:
            # Reverse: only negative throttle (pull back)
            if throttle_raw < 0:
                speed = throttle_raw * self.max_speed

        m = AckermannDrive()
        m.speed = float(speed)
        m.acceleration = float(speed)
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
