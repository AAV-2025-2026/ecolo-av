"""
encoder_udp: today's wheel encoder (Pico 2 + W5500) as /vehicle/odom.

Interim sensor until the encoder moves into the CAN spine.

Receives    UDP packets on `port`: big-endian int32 spoke counts (see legacy_protocol)
Publishes   vehicle/odom  nav_msgs/Odometry, forward speed only, in base_link

At 8 counts per revolution one count is about 0.12 m, so speed is averaged
over `window_s`. The yaw rate is left unmeasured (huge covariance); ekf_local
takes it from the IMU.
"""

from collections import deque
import socket

from aav_legacy.legacy_protocol import encoder_counts, metres_per_count
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class EncoderUdp(Node):

    def __init__(self):
        super().__init__('encoder_udp')
        port = self.declare_parameter('port', 10111).value
        bind = self.declare_parameter('bind_address', '0.0.0.0').value
        diameter = self.declare_parameter('wheel_diameter', 0.30).value   # TODO: measure
        cpr = self.declare_parameter('counts_per_rev', 8).value
        self.window = self.declare_parameter('window_s', 0.5).value
        self.speed_var = self.declare_parameter('speed_variance', 0.05).value
        self.mpc = metres_per_count(diameter, cpr)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind, port))
        self.sock.setblocking(False)
        self.samples = deque()   # (time in s, counts)
        self.pub = self.create_publisher(Odometry, 'vehicle/odom', 10)
        self.create_timer(0.02, self.poll)
        self.create_timer(0.1, self.publish)
        self.get_logger().info(f'listening on udp {bind}:{port}, {self.mpc:.3f} m per count')

    def poll(self):
        now = self.get_clock().now().nanoseconds * 1e-9
        while True:
            try:
                packet, _ = self.sock.recvfrom(64)
            except BlockingIOError:
                break
            try:
                self.samples.append((now, encoder_counts(packet)))
            except ValueError as e:
                self.get_logger().warn(str(e), throttle_duration_sec=5.0)

    def publish(self):
        now = self.get_clock().now()
        t = now.nanoseconds * 1e-9
        while self.samples and self.samples[0][0] < t - self.window:
            self.samples.popleft()
        speed = sum(c for _, c in self.samples) * self.mpc / self.window
        odom = Odometry()
        odom.header.stamp = now.to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.twist.twist.linear.x = speed
        cov = [0.0] * 36
        cov[0] = self.speed_var
        cov[7] = 1e-4
        cov[14] = cov[21] = cov[28] = cov[35] = 1e3
        odom.twist.covariance = cov
        odom.pose.covariance = [1e3 if i % 7 == 0 else 0.0 for i in range(36)]
        self.pub.publish(odom)


def main(args=None):
    rclpy.init(args=args)
    node = EncoderUdp()
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
