#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from ackermann_msgs.msg import AckermannDrive


class JoyToAckermann(Node):
    def __init__(self):
        super().__init__('joy_to_ackermann')

        self.declare_parameter('joy_topic',          '/joy')
        self.declare_parameter('drive_topic',        '/driveData')
        self.declare_parameter('axis_steer',         0)
        self.declare_parameter('axis_throttle',      1)
        self.declare_parameter('deadman_button',     0)   # Forward
        self.declare_parameter('deadman_button_rev', 1)   # Reverse
        self.declare_parameter('max_speed',          1.0)
        self.declare_parameter('deadzone',           0.05)
        self.declare_parameter('invert_steer',       False)
        self.declare_parameter('invert_throttle',    False)

        self.drive_topic   = self.get_parameter('drive_topic').value
        self.axis_steer    = self.get_parameter('axis_steer').value
        self.axis_throttle = self.get_parameter('axis_throttle').value
        self.btn_fwd       = self.get_parameter('deadman_button').value
        self.btn_rev       = self.get_parameter('deadman_button_rev').value
        self.max_speed     = float(self.get_parameter('max_speed').value)
        self.deadzone      = float(self.get_parameter('deadzone').value)
        self.invert_steer  = bool(self.get_parameter('invert_steer').value)
        self.invert_thr    = bool(self.get_parameter('invert_throttle').value)

        self.pub = self.create_publisher(AckermannDrive, self.drive_topic, 10)
        self.sub = self.create_subscription(
            Joy, self.get_parameter('joy_topic').value, self.joy_cb, 10)

        self.get_logger().info(
            f'Joy→Ackermann | {self.drive_topic} | '
            f'Btn{self.btn_fwd}=FWD  Btn{self.btn_rev}=REV  BOTH/NONE=BRAKE')

    def dz(self, v: float) -> float:
        return 0.0 if abs(v) < self.deadzone else v

    def joy_cb(self, msg: Joy):
        def btn(i): return bool(msg.buttons[i]) if 0 <= i < len(msg.buttons) else False
        def axis(i): return msg.axes[i]          if 0 <= i < len(msg.axes)    else 0.0

        hold_fwd = btn(self.btn_fwd)
        hold_rev = btn(self.btn_rev)

        # Neither or both held → full brake, zero speed
        if hold_fwd == hold_rev:
            m = AckermannDrive()
            m.speed          = 0.0
            m.acceleration   = -1.0   # full brake demand → ESP32 JRK brake
            m.steering_angle = 0.0
            self.pub.publish(m)
            return

        # One deadman held → brake released
        steer_raw = self.dz(axis(self.axis_steer))
        thr_raw   = self.dz(axis(self.axis_throttle))

        if self.invert_steer: steer_raw = -steer_raw
        if self.invert_thr:   thr_raw   = -thr_raw

        # Steering: axis normalized -1..+1 (ESP32 expects this range)
        steering = max(-1.0, min(1.0, steer_raw))

        # Speed: forward only accepts positive throttle, reverse only negative
        speed = 0.0
        if hold_fwd and thr_raw > 0.0:
            speed =  thr_raw * self.max_speed
        elif hold_rev and thr_raw < 0.0:
            speed = thr_raw * self.max_speed

        m = AckermannDrive()
        m.speed          = float(speed)
        m.acceleration   = 0.0        # brake released while deadman held
        m.steering_angle = float(steering)
        self.pub.publish(m)

        self.get_logger().debug(
            f'{"FWD" if hold_fwd else "REV"}  '
            f'steer={steering:.2f}  spd={speed:.2f}')


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
