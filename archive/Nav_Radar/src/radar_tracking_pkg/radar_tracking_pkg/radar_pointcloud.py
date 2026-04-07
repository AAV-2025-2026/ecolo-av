#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from radar_msgs.msg import RadarScan
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import Header
import struct
import math


class RadarPointCloud(Node):
    def __init__(self):
        super().__init__("radar_pointcloud")
        self.sub = self.create_subscription(
            RadarScan, "radar/scan", self.cb, 10)
        self.pub = self.create_publisher(
            PointCloud2, "radar/pointcloud", 10)

    def cb(self, msg):
        points = []
        for det in msg.returns:
            x = det.range * math.cos(det.azimuth)
            y = det.range * math.sin(det.azimuth)
            points.append((x, y, 0.0, abs(det.doppler_velocity)))

        cloud = self.make_cloud(msg.header, points)
        self.pub.publish(cloud)

def main(args=None):
    rclpy.init(args=args)
    node = RadarPointCloud()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()

