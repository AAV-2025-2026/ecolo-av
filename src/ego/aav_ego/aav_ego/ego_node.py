"""ego: the virtual car between the command mux and the backends.

Subscribes  cmd_vel           geometry_msgs/TwistStamped (or Twist, use_stamped:=false)
Publishes   ego/actuator_cmd  ackermann_msgs/AckermannDriveStamped, at rate_hz

Every backend (the CAN spine, the legacy serial bridge, turtlesim, Gazebo,
CARLA) consumes the same /ego/actuator_cmd, so the drivers never know which
car they are driving.

A command is stale cmd_timeout seconds after it ARRIVED (like twist_mux), not
after its header stamp: the joystick may run on a Pi whose clock is off, and a
replayed bag carries old stamps. A stamp far from now only logs a warning, so
fix the clock (chrony) rather than the car stopping for no visible reason.
"""

from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import Twist, TwistStamped
import rclpy
from rclpy.node import Node
from rclpy.time import Time

from aav_ego.ackermann import EgoModel, Limits


class Ego(Node):

    def __init__(self):
        super().__init__('ego')
        defaults = Limits()
        p = {
            name: self.declare_parameter(name, getattr(defaults, name)).value
            for name in vars(defaults)
        }
        self.limits = Limits(**p)
        self.timeout = self.declare_parameter('cmd_timeout', 0.3).value
        rate = self.declare_parameter('rate_hz', 50.0).value
        self.frame_id = self.declare_parameter('frame_id', 'base_link').value
        use_stamped = self.declare_parameter('use_stamped', True).value

        self.model = EgoModel(self.limits)
        self.cmd = None          # (v, w)
        self.cmd_time = None     # rclpy Time the command arrived
        self.last_tick = None

        if use_stamped:
            self.create_subscription(TwistStamped, 'cmd_vel', self.on_stamped, 10)
        else:
            self.create_subscription(Twist, 'cmd_vel', self.on_twist, 10)
        self.pub = self.create_publisher(AckermannDriveStamped, 'ego/actuator_cmd', 10)
        self.create_timer(1.0 / rate, self.tick)
        self.get_logger().info(
            f'wheelbase {self.limits.wheelbase} m, max steering '
            f'{self.limits.max_steering_angle} rad, max speed {self.limits.max_speed} m/s')

    def on_stamped(self, msg: TwistStamped):
        now = self.get_clock().now()
        stamp = Time.from_msg(msg.header.stamp, clock_type=now.clock_type)
        if stamp.nanoseconds and abs((now - stamp).nanoseconds) * 1e-9 > 0.5:
            self.get_logger().warn(
                'cmd_vel stamp is more than 0.5 s from this clock: check chrony on '
                'every machine (or this is a replayed bag)', throttle_duration_sec=10.0)
        self._store(msg.twist, now)

    def on_twist(self, msg: Twist):
        self._store(msg, self.get_clock().now())

    def _store(self, twist, arrived):
        self.cmd = (twist.linear.x, twist.angular.z)
        self.cmd_time = arrived

    def tick(self):
        now = self.get_clock().now()
        dt = 0.0 if self.last_tick is None else (now - self.last_tick).nanoseconds * 1e-9
        self.last_tick = now
        cmd = None
        if self.cmd is not None:
            age = (now - self.cmd_time).nanoseconds * 1e-9
            if age <= self.timeout:  # silence means stop
                cmd = self.cmd
        speed, steering, accel = self.model.step(cmd, min(dt, 0.1))

        out = AckermannDriveStamped()
        out.header.stamp = now.to_msg()
        out.header.frame_id = self.frame_id
        out.drive.speed = float(speed)
        out.drive.steering_angle = float(steering)
        out.drive.acceleration = float(accel)
        out.drive.steering_angle_velocity = float(self.limits.max_steering_rate)
        self.pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = Ego()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
