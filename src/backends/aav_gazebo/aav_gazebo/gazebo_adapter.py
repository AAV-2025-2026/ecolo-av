"""gazebo_adapter: Gazebo (Harmonic) as the car, behind the same topics as the real one.

Subscribes  ego/actuator_cmd   ackermann_msgs/AckermannDriveStamped
            gazebo/odom        nav_msgs/Odometry   (bridged from the Ackermann system)
            gazebo/imu         sensor_msgs/Imu     (bridged IMU sensor)
            gazebo/navsat      sensor_msgs/NavSatFix (bridged NavSat sensor)
Publishes   gazebo/cmd_vel     geometry_msgs/Twist (bridged to /model/aav/cmd_vel)
            vehicle/odom       nav_msgs/Odometry, twist only, like aav_spine
            vehicle/status     aav_interfaces/VehicleStatus (mode COMPUTER, armed)
            imu/data_raw       sensor_msgs/Imu, with covariances
            gps/fix            sensor_msgs/NavSatFix, with a covariance

So ekf_local, ekf_global, navsat_transform and imu_filter_madgwick run in simulation
with the same configs as on the car. Gazebo's ground-truth pose is not passed on.
"""

import math

from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import Imu, NavSatFix, NavSatStatus

from aav_interfaces.msg import VehicleStatus


def turn_rate(speed, steering, wheelbase):
    """Bicycle model: the yaw rate that gives this steering angle at this speed."""
    return speed * math.tan(steering) / wheelbase


class GazeboAdapter(Node):

    def __init__(self):
        super().__init__('gazebo_adapter')
        self.wheelbase = self.declare_parameter('wheelbase', 1.57).value
        self.speed_var = self.declare_parameter('speed_variance', 0.01).value
        self.gyro_var = self.declare_parameter('gyro_stddev', 0.02).value ** 2
        self.accel_var = self.declare_parameter('accel_stddev', 0.2).value ** 2
        self.gps_var = self.declare_parameter('gps_stddev', 0.5).value ** 2
        self.steering = 0.0

        self.cmd_pub = self.create_publisher(Twist, 'gazebo/cmd_vel', 10)
        self.odom_pub = self.create_publisher(Odometry, 'vehicle/odom', 10)
        self.status_pub = self.create_publisher(VehicleStatus, 'vehicle/status', 10)
        self.imu_pub = self.create_publisher(Imu, 'imu/data_raw', 10)
        self.fix_pub = self.create_publisher(NavSatFix, 'gps/fix', 10)
        self.create_subscription(AckermannDriveStamped, 'ego/actuator_cmd', self.on_cmd, 10)
        self.create_subscription(Odometry, 'gazebo/odom', self.on_odom, 10)
        self.create_subscription(Imu, 'gazebo/imu', self.on_imu, 10)
        self.create_subscription(NavSatFix, 'gazebo/navsat', self.on_navsat, 10)

    def on_cmd(self, msg):
        d = msg.drive
        self.steering = d.steering_angle
        out = Twist()
        out.linear.x = d.speed
        out.angular.z = turn_rate(d.speed, d.steering_angle, self.wheelbase)
        self.cmd_pub.publish(out)

    def on_odom(self, msg):
        odom = Odometry()
        odom.header = msg.header
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        speed = msg.twist.twist.linear.x
        odom.twist.twist.linear.x = speed
        odom.twist.twist.angular.z = msg.twist.twist.angular.z
        cov = [0.0] * 36
        cov[0] = self.speed_var
        cov[7] = 1e-4
        cov[14] = cov[21] = cov[28] = 1e3
        cov[35] = 0.02
        odom.twist.covariance = cov
        odom.pose.covariance = [1e3 if i % 7 == 0 else 0.0 for i in range(36)]
        self.odom_pub.publish(odom)

        s = VehicleStatus()
        s.header.stamp = msg.header.stamp
        s.header.frame_id = 'base_link'
        s.mode = VehicleStatus.MODE_COMPUTER
        s.armed = True
        s.speed = speed
        s.steering_angle = self.steering
        self.status_pub.publish(s)

    def on_imu(self, msg):
        msg.header.frame_id = 'imu_link'
        msg.orientation_covariance[0] = -1.0     # like the real IMU: no orientation
        for i in (0, 4, 8):
            msg.angular_velocity_covariance[i] = self.gyro_var
            msg.linear_acceleration_covariance[i] = self.accel_var
        self.imu_pub.publish(msg)

    def on_navsat(self, msg):
        msg.header.frame_id = 'gps_link'
        msg.status.status = NavSatStatus.STATUS_FIX
        msg.position_covariance = [self.gps_var, 0.0, 0.0,
                                   0.0, self.gps_var, 0.0,
                                   0.0, 0.0, 4 * self.gps_var]
        msg.position_covariance_type = NavSatFix.COVARIANCE_TYPE_DIAGONAL_KNOWN
        self.fix_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = GazeboAdapter()
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
