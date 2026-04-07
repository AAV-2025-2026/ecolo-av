#!/usr/bin/env python3
import csv
import os
from datetime import datetime
import rclpy
from rclpy.node import Node
from lane_geometry.msg import LaneGeometry


class GeometryLogger(Node):
    def __init__(self):
        super().__init__('geometry_logger')
        self.declare_parameter('output_dir', os.path.expanduser('~/lane_logs'))
        out_dir = self.get_parameter('output_dir').value
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(out_dir, f'lane_geometry_{ts}.csv')
        self.file_handle = open(path, 'w', newline='')
        self.writer = csv.writer(self.file_handle)
        self.writer.writerow([
            'timestamp_s', 'left_curvature_m', 'right_curvature_m', 'mean_curvature_m',
            'curve_direction', 'vehicle_offset_m', 'lane_width_m', 'steering_hint',
            'left_confidence', 'right_confidence', 'left_detected', 'right_detected',
            'both_detected', 'left_poly_a', 'left_poly_b', 'left_poly_c',
            'right_poly_a', 'right_poly_b', 'right_poly_c'
        ])
        self.row_count = 0
        self.sub = self.create_subscription(LaneGeometry, '/lane_geometry', self.log_cb, 10)
        self.get_logger().info(f'Logging to: {path}')

    def log_cb(self, msg: LaneGeometry):
        ts = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self.writer.writerow([
            f'{ts:.4f}', f'{msg.left_curvature_m:.3f}', f'{msg.right_curvature_m:.3f}',
            f'{msg.mean_curvature_m:.3f}', f'{msg.curve_direction:.3f}',
            f'{msg.vehicle_offset_m:.5f}', f'{msg.lane_width_m:.4f}', f'{msg.steering_hint:.5f}',
            f'{msg.left_confidence:.4f}', f'{msg.right_confidence:.4f}',
            int(msg.left_lane_detected), int(msg.right_lane_detected), int(msg.both_lanes_detected),
            f'{msg.left_poly_a:.8f}', f'{msg.left_poly_b:.8f}', f'{msg.left_poly_c:.8f}',
            f'{msg.right_poly_a:.8f}', f'{msg.right_poly_b:.8f}', f'{msg.right_poly_c:.8f}'
        ])
        self.file_handle.flush()
        self.row_count += 1

    def destroy_node(self):
        self.file_handle.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = GeometryLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
