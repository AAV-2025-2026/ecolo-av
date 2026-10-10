import math
import struct

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import Header


class MockRadarPublisher(Node):
    def __init__(self):
        super().__init__('mock_radar_publisher')

        self.declare_parameter('topic', '/ti_radar_0/ti_mmwave_0')
        self.declare_parameter('frame_id', 'radar_link')
        self.declare_parameter('publish_rate_hz', 10.0)
        self.declare_parameter('mode', 'moving')

        self.topic = str(self.get_parameter('topic').value)
        self.frame_id = str(self.get_parameter('frame_id').value)
        self.publish_rate_hz = float(self.get_parameter('publish_rate_hz').value)
        self.mode = str(self.get_parameter('mode').value)

        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self.publisher = self.create_publisher(PointCloud2, self.topic, qos)
        self.start_time = self.get_clock().now().nanoseconds / 1e9
        self.timer = self.create_timer(1.0 / max(self.publish_rate_hz, 0.1), self.publish_cloud)
        self.get_logger().info(
            f'Publishing mock radar points on {self.topic} at {self.publish_rate_hz:.1f} Hz (mode={self.mode})'
        )

    def publish_cloud(self) -> None:
        t = self.get_clock().now().nanoseconds / 1e9 - self.start_time

        if self.mode == 'static':
            clusters = [
                (2.2, 1.2, 0.0, 0.15, 10, 0.0),
                (2.4, -1.0, 0.0, 0.18, 12, 0.0),
                (5.0, 0.2, 0.0, 0.22, 14, 0.0),
            ]
        else:
            clusters = [
                (2.0 + 0.6 * math.sin(0.6 * t), 1.0, 0.0, 0.14, 10, 0.8),
                (2.5, -1.2 + 0.4 * math.sin(0.9 * t), 0.0, 0.16, 12, -0.5),
                (4.7 + 0.3 * math.sin(0.4 * t), 0.1, 0.0, 0.20, 14, 0.3),
            ]

        points = []
        for center_x, center_y, center_z, spread, count, velocity in clusters:
            for i in range(count):
                angle = 2.0 * math.pi * i / max(count, 1)
                radius = spread * (0.55 + 0.45 * ((i % 3) / 2.0))
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                z = center_z + 0.03 * math.sin(angle * 2.0)
                intensity = 1.0 + (i % 4) * 0.2
                points.append((x, y, z, intensity, velocity))

        cloud = self.build_cloud(points)
        self.publisher.publish(cloud)

    def build_cloud(self, points):
        msg = PointCloud2()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        msg.height = 1
        msg.width = len(points)
        msg.fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name='intensity', offset=12, datatype=PointField.FLOAT32, count=1),
            PointField(name='velocity', offset=16, datatype=PointField.FLOAT32, count=1),
        ]
        msg.is_bigendian = False
        msg.point_step = 20
        msg.row_step = msg.point_step * msg.width
        msg.is_dense = True
        msg.data = b''.join(struct.pack('fffff', *point) for point in points)
        return msg


def main(args=None):
    rclpy.init(args=args)
    node = MockRadarPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
