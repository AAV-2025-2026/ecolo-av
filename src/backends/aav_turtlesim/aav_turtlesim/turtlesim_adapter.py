"""turtlesim_adapter: drive the turtlesim turtle like a car.

Subscribes  ego/actuator_cmd  ackermann_msgs/AckermannDriveStamped
            turtle1/pose      turtlesim/Pose
Publishes   turtle1/cmd_vel   geometry_msgs/Twist (bicycle model: w = v tan(d) / L)
            vehicle/odom      nav_msgs/Odometry (twist only), so ekf_local can run

The fastest way to test the joystick, mux, ego, scripted driver and ekf_local
together on a laptop. One turtlesim unit counts as one metre.
"""

import math

from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from turtlesim.msg import Pose


class TurtlesimAdapter(Node):

    def __init__(self):
        super().__init__('turtlesim_adapter')
        self.wheelbase = self.declare_parameter('wheelbase', 1.57).value
        self.cmd_pub = self.create_publisher(Twist, 'turtle1/cmd_vel', 10)
        self.odom_pub = self.create_publisher(Odometry, 'vehicle/odom', 10)
        self.create_subscription(AckermannDriveStamped, 'ego/actuator_cmd', self.on_cmd, 10)
        self.create_subscription(Pose, 'turtle1/pose', self.on_pose, 10)

    def on_cmd(self, msg):
        t = Twist()
        t.linear.x = msg.drive.speed
        t.angular.z = msg.drive.speed * math.tan(msg.drive.steering_angle) / self.wheelbase
        self.cmd_pub.publish(t)

    def on_pose(self, pose):
        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.twist.twist.linear.x = pose.linear_velocity
        odom.twist.twist.angular.z = pose.angular_velocity
        cov = [0.0] * 36
        cov[0] = cov[35] = 1e-3
        cov[7] = 1e-4
        cov[14] = cov[21] = cov[28] = 1e3
        odom.twist.covariance = cov
        odom.pose.covariance = [1e3 if i % 7 == 0 else 0.0 for i in range(36)]
        self.odom_pub.publish(odom)


def main(args=None):
    rclpy.init(args=args)
    node = TurtlesimAdapter()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        # Ctrl-C reaches a launched node twice (terminal and launch), and Jazzy can then
        # raise RCLError ("context is not valid"). Only a live context means a real error.
        if rclpy.ok():
            raise
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
