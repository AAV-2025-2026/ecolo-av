#!/usr/bin/env python3
import math
import signal
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from aav_lane_geometry.msg import LaneGeometry


class FakeLaneGeometryPublisher(Node):
    def __init__(self):
        super().__init__('fake_lane_geometry_pub')
        self.declare_parameter('mode', 'straight')
        self.declare_parameter('rate_hz', 10.0)
        self.declare_parameter('lane_width_m', 3.6)
        self.mode = str(self.get_parameter('mode').value)
        self.rate_hz = float(self.get_parameter('rate_hz').value)
        self.lane_width = float(self.get_parameter('lane_width_m').value)
        self.pub = self.create_publisher(LaneGeometry, '/perception/lane/geometry', 10)
        self.t = 0.0
        self.dt = 1.0 / max(self.rate_hz, 1.0)
        self.create_timer(self.dt, self.timer_cb)
        self.get_logger().info(f'Publishing fake /perception/lane/geometry in mode={self.mode} at {self.rate_hz:.1f} Hz')

    def timer_cb(self):
        msg = LaneGeometry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'mock_bev'
        msg.lane_width_m = self.lane_width
        msg.left_confidence = 0.95
        msg.right_confidence = 0.95
        msg.left_lane_detected = True
        msg.right_lane_detected = True
        msg.both_lanes_detected = True
        msg.left_curvature_m = 500.0
        msg.right_curvature_m = 500.0
        msg.mean_curvature_m = 500.0
        msg.curve_direction = 0.0
        msg.left_poly_a = 0.0
        msg.left_poly_b = 0.0
        msg.left_poly_c = 220.0
        msg.right_poly_a = 0.0
        msg.right_poly_b = 0.0
        msg.right_poly_c = 420.0

        if self.mode == 'straight':
            msg.vehicle_offset_m = 0.0
        elif self.mode == 'drift_right':
            msg.vehicle_offset_m = 0.35
        elif self.mode == 'drift_left':
            msg.vehicle_offset_m = -0.35
        elif self.mode == 'sine':
            msg.vehicle_offset_m = 0.30 * math.sin(0.8 * self.t)
        elif self.mode == 'sharp_curve':
            msg.vehicle_offset_m = 0.05
            msg.left_curvature_m = 15.0
            msg.right_curvature_m = 18.0
            msg.mean_curvature_m = 16.5
            msg.curve_direction = 1.0
        elif self.mode == 'lane_change_right':
            if self.t < 2.0:
                msg.vehicle_offset_m = 0.25 * self.t
            elif self.t < 4.0:
                msg.vehicle_offset_m = 0.50 - 0.20 * (self.t - 2.0)
            else:
                msg.vehicle_offset_m = 0.10
        elif self.mode == 'lane_change_left':
            if self.t < 2.0:
                msg.vehicle_offset_m = -0.25 * self.t
            elif self.t < 4.0:
                msg.vehicle_offset_m = -0.50 + 0.20 * (self.t - 2.0)
            else:
                msg.vehicle_offset_m = -0.10
        elif self.mode == 'lane_loss':
            if self.t < 3.0:
                msg.vehicle_offset_m = 0.05
            elif self.t < 6.0:
                msg.left_lane_detected = False
                msg.right_lane_detected = False
                msg.both_lanes_detected = False
                msg.left_confidence = 0.0
                msg.right_confidence = 0.0
                msg.vehicle_offset_m = 0.0
                msg.mean_curvature_m = 9999.0
            else:
                msg.vehicle_offset_m = -0.05
        else:
            msg.vehicle_offset_m = 0.0

        msg.steering_hint = max(-1.0, min(1.0, msg.vehicle_offset_m))
        self.pub.publish(msg)
        self.t += self.dt


def main(args=None):
    rclpy.init(args=args)
    node = FakeLaneGeometryPublisher()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # aav: Ctrl-C arrives twice under launch, and Jazzy's handler may already have shut
        # rclpy down: ignore the second, and shut down only if it hasn't happened.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
