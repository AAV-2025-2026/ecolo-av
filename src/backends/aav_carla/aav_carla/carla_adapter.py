"""carla_adapter: connect the stack to CARLA through carla_ros_bridge (stub).

Subscribes  ego/actuator_cmd                    ackermann_msgs/AckermannDriveStamped
            carla/ego_vehicle/speedometer       std_msgs/Float32 (m/s)
Publishes   carla/ego_vehicle/ackermann_cmd     ackermann_msgs/AckermannDrive
            vehicle/odom                        nav_msgs/Odometry (twist only)

CARLA's IMU and GNSS topics are remapped in launch/carla.launch.py rather than
copied here. Status: written to the carla_ros_bridge topic names the 2024-25
team used, never run. As of October 2026 nothing official runs CARLA with Jazzy:
carla_ros_bridge was last updated in 2022 (ROS 2 Foxy), CARLA 0.9.16 supports
Ubuntu 22.04, and Jazzy support in its native ROS 2 interface is only on unreleased
branches. See docs/simulation.md before spending time on this.
"""

from ackermann_msgs.msg import AckermannDrive, AckermannDriveStamped
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float32


class CarlaAdapter(Node):

    def __init__(self):
        super().__init__('carla_adapter')
        role = self.declare_parameter('role_name', 'ego_vehicle').value
        self.cmd_pub = self.create_publisher(AckermannDrive, f'carla/{role}/ackermann_cmd', 10)
        self.odom_pub = self.create_publisher(Odometry, 'vehicle/odom', 10)
        self.create_subscription(AckermannDriveStamped, 'ego/actuator_cmd', self.on_cmd, 10)
        self.create_subscription(Float32, f'carla/{role}/speedometer', self.on_speed, 10)

    def on_cmd(self, msg):
        self.cmd_pub.publish(msg.drive)

    def on_speed(self, msg):
        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.twist.twist.linear.x = float(msg.data)
        cov = [0.0] * 36
        cov[0] = 1e-3
        cov[7] = 1e-4
        cov[14] = cov[21] = cov[28] = cov[35] = 1e3
        odom.twist.covariance = cov
        odom.pose.covariance = [1e3 if i % 7 == 0 else 0.0 for i in range(36)]
        self.odom_pub.publish(odom)


def main(args=None):
    rclpy.init(args=args)
    node = CarlaAdapter()
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
