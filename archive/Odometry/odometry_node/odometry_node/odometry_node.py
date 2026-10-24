#!/usr/bin/env python3

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import SensorDataQoS

from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu


class OdometryNode(Node):
    """
    Unified odometry node:
    - Pose and orientation from SLAM odometry
    - Linear velocity from SLAM twist if present, otherwise estimated from pose deltas
    - Angular velocity from IMU gyro
    - Publishes final nav_msgs/Odometry on /odom
    """

    def __init__(self):
        super().__init__('odometry_node')

        self.slam_odom_topic = self.declare_parameter('slam_odom_topic', '/odometry').value
        self.imu_topic = self.declare_parameter('imu_topic', '/imu/data').value
        self.odom_out_topic = self.declare_parameter('odom_out_topic', '/odom').value
        self.estimate_linear_velocity = self.declare_parameter('estimate_linear_velocity', True).value

        self.last_slam_msg = None
        self.last_imu_msg = None

        self.prev_pose_time = None
        self.prev_position = None

        self.slam_sub = self.create_subscription(
            Odometry,
            self.slam_odom_topic,
            self.slam_callback,
            SensorDataQoS()
        )

        self.imu_sub = self.create_subscription(
            Imu,
            self.imu_topic,
            self.imu_callback,
            SensorDataQoS()
        )

        self.odom_pub = self.create_publisher(Odometry, self.odom_out_topic, 10)

        self.get_logger().info(f"Subscribed to SLAM odometry: {self.slam_odom_topic}")
        self.get_logger().info(f"Subscribed to IMU: {self.imu_topic}")
        self.get_logger().info(f"Publishing unified odometry: {self.odom_out_topic}")
        self.get_logger().info(f"Estimate linear velocity from pose deltas: {self.estimate_linear_velocity}")

    def slam_callback(self, msg: Odometry):
        self.last_slam_msg = msg
        self.try_publish()

    def imu_callback(self, msg: Imu):
        self.last_imu_msg = msg
        self.try_publish()

    def try_publish(self):
        if self.last_slam_msg is None or self.last_imu_msg is None:
            return

        slam = self.last_slam_msg
        imu = self.last_imu_msg

        out = Odometry()

        # Preserve SLAM timing and frames
        out.header.stamp = slam.header.stamp
        out.header.frame_id = slam.header.frame_id
        out.child_frame_id = slam.child_frame_id

        # Pose comes directly from SLAM
        out.pose = slam.pose

        # Start with SLAM twist
        out.twist = slam.twist

        # Decide whether to estimate linear velocity
        if self.estimate_linear_velocity:
            vx, vy, vz = self.estimate_linear_velocity_from_pose(slam)
            out.twist.twist.linear.x = vx
            out.twist.twist.linear.y = vy
            out.twist.twist.linear.z = vz

            # If we are estimating velocity, set reasonable covariance values
            out.twist.covariance[0] = max(out.twist.covariance[0], 0.05)    # vx
            out.twist.covariance[7] = max(out.twist.covariance[7], 0.05)    # vy
            out.twist.covariance[14] = max(out.twist.covariance[14], 0.05)  # vz

        # Angular velocity comes from IMU
        out.twist.twist.angular = imu.angular_velocity

        # If IMU covariance is valid, use it for angular velocity
        if imu.angular_velocity_covariance[0] >= 0.0:
            out.twist.covariance[21] = imu.angular_velocity_covariance[0]
            out.twist.covariance[28] = imu.angular_velocity_covariance[4]
            out.twist.covariance[35] = imu.angular_velocity_covariance[8]
        else:
            out.twist.covariance[21] = max(out.twist.covariance[21], 0.02)
            out.twist.covariance[28] = max(out.twist.covariance[28], 0.02)
            out.twist.covariance[35] = max(out.twist.covariance[35], 0.02)

        self.odom_pub.publish(out)

    def estimate_linear_velocity_from_pose(self, slam_msg: Odometry):
        current_time = self.time_from_stamp(slam_msg.header.stamp)
        position = slam_msg.pose.pose.position
        current_position = (position.x, position.y, position.z)

        if self.prev_pose_time is None or self.prev_position is None:
            self.prev_pose_time = current_time
            self.prev_position = current_position
            return 0.0, 0.0, 0.0

        dt = current_time - self.prev_pose_time
        if dt <= 1e-6:
            return 0.0, 0.0, 0.0

        dx = current_position[0] - self.prev_position[0]
        dy = current_position[1] - self.prev_position[1]
        dz = current_position[2] - self.prev_position[2]

        vx = dx / dt
        vy = dy / dt
        vz = dz / dt

        # Clamp unrealistic spikes
        vx = self.clamp(vx, -20.0, 20.0)
        vy = self.clamp(vy, -20.0, 20.0)
        vz = self.clamp(vz, -20.0, 20.0)

        self.prev_pose_time = current_time
        self.prev_position = current_position

        return vx, vy, vz

    @staticmethod
    def time_from_stamp(stamp):
        return float(stamp.sec) + float(stamp.nanosec) * 1e-9

    @staticmethod
    def clamp(value, min_value, max_value):
        return max(min_value, min(value, max_value))


def main(args=None):
    rclpy.init(args=args)
    node = OdometryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()