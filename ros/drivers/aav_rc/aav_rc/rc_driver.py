"""
rc_driver: the RC transmitter's sticks as a driver, for the RC via ROS mode (TODO 48).

Subscribes  vehicle/rc           aav_interfaces/RcSticks: the mode switch and the sticks, as
                                 the ESP32 reads them (legacy_uart_bridge, from its uplink)
Publishes   drivers/rc/cmd_vel   geometry_msgs/TwistStamped, rate_hz (50), only while the mode
                                 switch is on RC via ROS (twist_mux priority 95): the throttle
                                 stick x max_speed (reverse: max_reverse_speed), the steering
                                 stick x max_steering_angle as a turn rate (the bicycle model).
                                 One zero as the switch leaves RC via ROS; zeros while
                                 vehicle/rc is quiet on RC via ROS (a stop)

The rules are in rc_drive.py. In RC direct the ESP32 drives from the sticks itself, and this
publishes nothing.
"""

import signal

from aav_interfaces.msg import RcSticks
from aav_rc.rc_drive import Limits, RcDrive, Sticks
from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class RcDriver(Node):

    def __init__(self):
        super().__init__('rc_driver')
        defaults = Limits()
        limits = Limits(**{k: float(self.declare_parameter(k, v).value)
                           for k, v in vars(defaults).items()})
        rate = self.declare_parameter('rate_hz', 50.0).value
        self.frame = self.declare_parameter('frame_id', 'base_link').value
        self.drive = RcDrive(limits)
        self.pub = self.create_publisher(TwistStamped, 'drivers/rc/cmd_vel', 10)
        self.create_subscription(RcSticks, 'vehicle/rc', self.on_rc, 10)
        self.create_timer(1.0 / rate, self.tick)
        self.switch = None

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_rc(self, msg):
        self.drive.heard(Sticks(msg.mode_switch, msg.throttle, msg.steering, msg.brake),
                         self.now())
        if msg.mode_switch != self.switch:
            names = {RcSticks.SWITCH_NONE: 'no RC signal', RcSticks.SWITCH_COMPUTER: 'computer',
                     RcSticks.SWITCH_RC_VIA_ROS: 'RC via ROS: driving from the sticks',
                     RcSticks.SWITCH_RC_DIRECT: 'RC direct (the ESP32 drives)'}
            self.get_logger().info(f'mode switch: {names.get(msg.mode_switch, msg.mode_switch)}')
            self.switch = msg.mode_switch

    def tick(self):
        was_driving = self.drive.driving
        cmd = self.drive.command(self.now())
        if cmd is None:
            return
        if was_driving and self.drive.at is not None and \
                self.now() - self.drive.at > self.drive.limits.stale:
            self.get_logger().warning('vehicle/rc quiet on RC via ROS: holding a stop',
                                      throttle_duration_sec=2.0)
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame
        msg.twist.linear.x, msg.twist.angular.z = cmd
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = RcDriver()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        # Ctrl-C reaches a launched node twice; only a live context means a real error.
        if rclpy.ok():
            raise
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
